import os
import uuid
import threading
import tempfile
from pathlib import Path
from typing import List, Tuple, Dict

import cv2
import numpy as np
from pdf2image import convert_from_path
import replicate
import requests

from .db import (
    _get_connection,
    ensure_manual_and_step,
    store_value,
    get_manuals,
    get_manual,
)
from .db_columns import StepColumn

# environment/config
BASE_DIR = Path(__file__).resolve().parent.parent
MANUALS_DIR = BASE_DIR / "public" / "manuals"
NANO_MODEL = "google/nano-banana-pro"

# Prompt for boundary detection
STEP_SEGMENTATION_PROMPT = (
    "Process the assembly manual and determine the boundaries for each step in "
    "the assembly process. Steps can include parts, inline diagrams, and text "
    "descriptions. Place thin magenta borders with hex code #FF00FF around the "
    "content, without covering or modifying any of the elements. "
    "Borders must be rectangles. There should be no overlap of rectangles."
)

# in‑memory job tracker
JOBS: Dict[str, Dict] = {}


def _create_manual_record(name: str = None, slug: str = None, description: str = None) -> int:
    """Insert a row into the manuals table and return the generated id.
    Adds a status column if it does not already exist.  If name/slug are
    omitted we generate simple defaults (slug becomes manual-<id> later).
    """
    try:
        conn = _get_connection()
    except RuntimeError:
        # no database configured; fall back to a simple counter so the rest of the
        # pipeline can execute without failing.  This mirrors the "safe no-op"
        # pattern used elsewhere in the project.
        if not hasattr(_create_manual_record, "_counter"):
            _create_manual_record._counter = 1000
        _create_manual_record._counter += 1
        return _create_manual_record._counter

    with conn:
        with conn.cursor() as cur:
            # ensure status column exists (ALTER TABLE will no-op if already present)
            cur.execute("ALTER TABLE manuals ADD COLUMN IF NOT EXISTS status TEXT")
            cur.execute(
                """
                INSERT INTO manuals (name, slug, description, status)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (name or "", slug or "", description, "PROCESSING"),
            )
            m_id = cur.fetchone()[0]
            # if slug was empty we update it to a sane value
            if not slug:
                new_slug = f"manual-{m_id}"
                cur.execute("UPDATE manuals SET slug = %s WHERE id = %s", (new_slug, m_id))
            return m_id


def _update_manual_status(manual_id: int, status: str):
    try:
        conn = _get_connection()
    except RuntimeError:
        return
    with conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE manuals SET status = %s WHERE id = %s", (status, manual_id))


def _download_from_url(url: str, dest_path: Path) -> None:
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def _call_annotator(page_path: Path) -> Path:
    """Send page image to Nano Banana Pro, return path to
    annotated image to feed into the CV stage.

    If REPLICATE_API_TOKEN is not set, copy original image
    """
    if not os.getenv("REPLICATE_API_TOKEN"):
        return page_path

    with open(page_path, "rb") as f:
        print(f"calling replicate model {NANO_MODEL} for {page_path}")
        # following prompt structure in orientation_generator.py
        input_data = {
            "prompt": STEP_SEGMENTATION_PROMPT,
            "image_input": [f],
        }
        output = replicate.run(NANO_MODEL, input=input_data)

    # model output is often a URL or list; convert to string
    result_url = None
    if isinstance(output, list) and output:
        result_url = str(output[0])
    else:
        result_url = str(output)

    annotated_path = page_path.with_suffix(".annotated.png")
    _download_from_url(result_url, annotated_path)
    return annotated_path


def _extract_bounding_boxes(orig_path: Path, annot_path: Path) -> List[Tuple[int, int, int, int]]:
    """Detect the coloured rectangles drawn by the annotator.
    Specifically looks for magenta (#FF00FF).
    Returns a list of (x,y,w,h) tuples.
    """
    orig = cv2.imread(str(orig_path))
    annot = cv2.imread(str(annot_path))
    if orig is None or annot is None:
        return []

    # Ensure images have the same size. Some models resize images.
    if orig.shape[:2] != annot.shape[:2]:
        print(f"Resizing annot ({annot.shape[:2]}) to match orig ({orig.shape[:2]})")
        annot = cv2.resize(annot, (orig.shape[1], orig.shape[0]))

    # Convert to HSV to detect Magenta (#FF00FF)
    # Magenta is ~300 degrees. HSV range: H(0-180), S(0-255), V(0-255)
    # 300 deg -> H = 150
    hsv = cv2.cvtColor(annot, cv2.COLOR_BGR2HSV)
    lower_magenta = np.array([140, 50, 50])
    upper_magenta = np.array([170, 255, 255])
    mask = cv2.inRange(hsv, lower_magenta, upper_magenta)

    # Alternative: check specifically for pixels that changed significantly AND are magenta-ish
    # This helps if the original manual has magenta (unlikely but possible)
    diff = cv2.absdiff(orig, annot)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, change_mask = cv2.threshold(diff_gray, 30, 255, cv2.THRESH_BINARY)
    
    # Combined mask: must have changed AND be magenta
    final_mask = cv2.bitwise_and(mask, change_mask)

    contours, _ = cv2.findContours(final_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Filter very small boxes (noise)
        if w > 10 and h > 10:
            boxes.append((x, y, w, h))

    # filter redundant boxes (90% contained)
    filtered: List[Tuple[int, int, int, int]] = []
    for box in boxes:
        x, y, w, h = box
        contained = False
        for other in boxes:
            if other == box:
                continue
            ox, oy, ow, oh = other
            # if box inside other
            if x >= ox and y >= oy and x + w <= ox + ow and y + h <= oy + oh:
                # check area ratio
                area = w * h
                other_area = ow * oh
                if area <= other_area * 0.9:
                    contained = True
                    break
        if not contained:
            filtered.append(box)
    return filtered


def _process_pdf(path: Path, manual_id: int) -> int:
    """
    Main method: convert PDF, call AI, crop steps, update DB
    Returns total number of steps produced.
    """
    # convert pdf -> list of PIL images
    pages = convert_from_path(str(path), dpi=300)
    step_counter = 0

    for page_idx, pil_img in enumerate(pages):
        # save the clean page temporarily and also load it with OpenCV once
        page_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        pil_img.save(page_file.name, "PNG")
        page_path = Path(page_file.name)
        orig_cv = cv2.imread(str(page_path))

        # run annotation model
        try:
            annot_path = _call_annotator(page_path)
            # Save a copy of the annotated image for debugging
            manual_subdir = MANUALS_DIR / str(manual_id)
            manual_subdir.mkdir(parents=True, exist_ok=True)
            debug_annot_path = manual_subdir / f"debug_page_{page_idx}_annotated.png"
            import shutil
            if annot_path.exists():
                shutil.copy(annot_path, debug_annot_path)
        except Exception as e:
            print(f"warning: annotation failed for page {page_idx}: {e}")
            # fall back to original image
            annot_path = page_path

        # detect boxes
        boxes = _extract_bounding_boxes(page_path, annot_path)
        if not boxes:
            # treat whole page as single step
            boxes = [(0, 0, pil_img.width, pil_img.height)]
            print(f"no boxes detected on page {page_idx}, using entire page")

        # sort boxes top-to-bottom then left-to-right
        boxes.sort(key=lambda b: (b[1], b[0]))

        # crop & save steps
        manual_subdir = MANUALS_DIR / str(manual_id)
        manual_subdir.mkdir(parents=True, exist_ok=True)

        for box in boxes:
            x, y, w, h = box
            crop = orig_cv[y : y + h, x : x + w]
            step_counter += 1
            step_filename = f"step{step_counter}.png"
            step_path = manual_subdir / step_filename
            cv2.imwrite(str(step_path), crop)

            # insert into database
            base_url = os.getenv("APP_URL", "http://localhost:4000").rstrip("/")
            image_url = f"{base_url}/manuals/{manual_id}/{step_filename}"
            ensure_manual_and_step(manual_id, step_counter, image_url)

        # cleanup temp files
        try:
            page_path.unlink()
            if annot_path != page_path and annot_path.exists():
                annot_path.unlink()
        except Exception:
            pass

    return step_counter


def start_manual_processing(file_path: Path, name: str = None, slug: str = None, description: str = None) -> str:
    """
    Starts a background thread that preprocesses a manual, returns a job_id immediately
    """
    job_id = str(uuid.uuid4())
    manual_id = _create_manual_record(name=name, slug=slug, description=description)

    JOBS[job_id] = {"status": "processing", "manual_id": manual_id, "step_count": 0, "error": None}

    def _background():
        try:
            total = _process_pdf(file_path, manual_id)
            _update_manual_status(manual_id, "COMPLETED")
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["step_count"] = total
        except Exception as e:
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["error"] = str(e)

    thread = threading.Thread(target=_background, daemon=True)
    thread.start()
    return job_id


def get_job_status(job_id: str) -> Dict:
    return JOBS.get(job_id, None)
