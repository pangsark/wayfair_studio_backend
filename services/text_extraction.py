# services/text_extraction.py
"""
Step description extraction using GPT-4o vision (via Replicate).

get_step_explanation() is the main entry point. It:
  1. Checks the DB cache (steps.description); returns cached value if present
  2. Reads the step image from public/manuals/<id>/stepN.png
  3. Calls GPT-4o via Replicate with the image + a description prompt
  4. Stores the result back into the DB for subsequent calls

preload_manual_step_explanations() is called at startup in a background thread
to warm the cache for all existing manuals so the first user request is fast.
"""
import os
import re
import replicate
from pathlib import Path
from typing import List
from dotenv import load_dotenv

from . import db as db_helper
from .db_columns import StepColumn

parent_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(parent_env_path)

MANUALS_DIR = Path(__file__).resolve().parent.parent / "public" / "manuals"


def discover_step_numbers(manual_id: int) -> List[int]:
    """
    Find all step numbers that have an image in public/manuals/<manual_id>/ (step1.png, step2.jpg, etc.).
    Returns sorted list of step numbers for that manual.
    """
    manual_dir = MANUALS_DIR / str(manual_id)
    if not manual_dir.exists():
        return []
    step_nums = set()
    pattern = re.compile(r"^step(\d+)\.(png|jpg|jpeg)$", re.IGNORECASE)
    for path in manual_dir.iterdir():
        if path.is_file():
            m = pattern.match(path.name)
            if m:
                step_nums.add(int(m.group(1)))
    return sorted(step_nums)


def preload_manual_step_explanations(manual_id: int = 1) -> None:
    """
    Run get_step_explanation for every step discovered in public/manuals/<manual_id>/.
    Intended to be run in a background thread at startup. Skips steps that
    already have a description in the DB. Continues on per-step errors.
    """
    step_numbers = discover_step_numbers(manual_id)
    if not step_numbers:
        print(f"Preload: no step images found in public/manuals/{manual_id}")
        return
    print(f"Preload: filling step explanations for manual_id = {manual_id}, steps = {step_numbers}")
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

    # Find the image file in public/manuals/<manual_id>/
    manual_dir = MANUALS_DIR / str(manual_id)
    image_path = None
    for ext in [".png", ".jpg"]:
        potential_path = manual_dir / f"step{step_number}{ext}"
        if potential_path.exists():
            image_path = potential_path
            break

    if not image_path:
        raise FileNotFoundError(f"Step image not found for manual {manual_id} step {step_number}")

    # Ensure manual and step rows exist so we can store the description later
    base_url = os.getenv("APP_URL", "http://localhost:4000").rstrip("/")
    image_url = f"{base_url}/manuals/{manual_id}/step{step_number}{image_path.suffix}"
    db_helper.ensure_manual_and_step(manual_id, step_number, image_url)

    # Call GPT-4o via Replicate with the step image
    response_parts = []
    with open(image_path, "rb") as img_file:
        try:
            for event in replicate.stream(
                "openai/gpt-4o",
                input={
                    "image_input": [img_file],
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