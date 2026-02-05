# services/text_extraction.py
import os
import replicate
import base64
from pathlib import Path
from typing import TypedDict
from dotenv import load_dotenv

from . import db as db_helper
from .db_columns import StepColumn

parent_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(parent_env_path)


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
    images_dir = Path(__file__).parent.parent / "public" / "images"
    image_path = None
    
    # Try both .png and .jpg extensions
    for ext in [".png", ".jpg"]:
        potential_path = images_dir / f"step{step_number}{ext}"
        if potential_path.exists():
            image_path = potential_path
            break
    
    if not image_path:
        raise FileNotFoundError(f"Step image not found for step {step_number}")
    
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