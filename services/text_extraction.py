# services/text_extraction.py
import os
import re
import replicate
import base64
from pathlib import Path
from typing import List
from dotenv import load_dotenv

from . import db as db_helper
from .db_columns import StepColumn

parent_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(parent_env_path)

IMAGES_DIR = Path(__file__).resolve().parent.parent / "public" / "images"


def discover_step_numbers() -> List[int]:
    """
    Find all step numbers that have an image in public/images (step1.png, step2.jpg, etc.).
    Returns sorted list of step numbers.
    """
    if not IMAGES_DIR.exists():
        return []
    step_nums = set()
    pattern = re.compile(r"^step(\d+)\.(png|jpg|jpeg)$", re.IGNORECASE)
    for path in IMAGES_DIR.iterdir():
        if path.is_file():
            m = pattern.match(path.name)
            if m:
                step_nums.add(int(m.group(1)))
    return sorted(step_nums)


def preload_manual_step_explanations(manual_id: int = 1) -> None:
    """
    Run get_step_explanation for every step discovered in public/images.
    Intended to be run in a background thread at startup. Skips steps that
    already have a description in the DB. Continues on per-step errors.
    """
    step_numbers = discover_step_numbers()
    if not step_numbers:
        print("Preload: no step images found in public/images")
        return
    print(f"Preload: filling step explanations for manual_id={manual_id}, steps={step_numbers}")
    for step_number in step_numbers:
        try:
            get_step_explanation(manual_id=manual_id, step_number=step_number)
            print(f"Preload: step {step_number} done")
        except Exception as e:
            print(f"Preload: step {step_number} failed: {e}")


def get_step_explanation(manual_id: int = 1, step_number: int = None):
    """
    Service function that returns explanation data for a given step.
    Uses GPT-4o vision model via Replicate to analyze the step image.
    """
    # Try DB cache -- if DB not configured or entry not found,
    # generate explanation and store in DB for next time

    cached = db_helper.get_cached_value(manual_id, step_number, StepColumn.DESCRIPTION)
    if cached and cached["description"]:
        return cached

    # Find the image file in public/images
    image_path = None
    for ext in [".png", ".jpg"]:
        potential_path = IMAGES_DIR / f"step{step_number}{ext}"
        if potential_path.exists():
            image_path = potential_path
            break
    
    if not image_path:
        raise FileNotFoundError(f"Step image not found for step {step_number}")

    # Ensure manual and step rows exist so we can store the description later
    base_url = os.getenv("APP_URL", "http://localhost:4000").rstrip("/")
    image_url = f"{base_url}/images/step{step_number}{image_path.suffix}"
    db_helper.ensure_manual_and_step(manual_id, step_number, image_url)

    # Read image file and encode as base64
    with open(image_path, "rb") as f:
        image_bytes = f.read()
        image_data = base64.b64encode(image_bytes).decode("utf-8")
    
    media_type = "image/png" if image_path.suffix == ".png" else "image/jpeg"
    
    print(f"DEBUG: Using image from: {image_path}")
    print(f"DEBUG: Image file size: {len(image_bytes)} bytes")
    print(f"DEBUG: Base64 size: {len(image_data)} characters")
    print(f"DEBUG: Media type: {media_type}")
    
    # Call GPT-4o via Replicate using stream with file object
    response_parts = []
    
    try:
        for event in replicate.stream(
            "openai/gpt-4o",
            input={
                "image_input": [open(image_path, "rb")],
                "prompt": "Provide a detailed step-by-step description of the assembly instructions shown in this image. Be clear and concise."
            }
        ):
            response_parts.append(str(event))
    except Exception as e:
        print(f"Warning: replicate call failed: {e}")
        raise
    
    description_text = "".join(response_parts).strip()
    
    # store into DB (safe no-op if DB not configured)
    try:
        db_helper.store_value(manual_id, step_number, StepColumn.DESCRIPTION, description_text)
    except Exception:
        # log in the future.
        pass

    return {"manual_id": manual_id, "step": step_number, "description": description_text}