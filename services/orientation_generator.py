"""
Background service for generating and storing orientation text.
Runs Replicate analysis asynchronously and stores results in database.
"""
import threading
import os
import replicate
from pathlib import Path
from typing import Dict
from services.db_columns import StepColumn
from services.db import store_value
import json

# Global dictionary to track active background tasks
_background_tasks = {}

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "public" / "images"

def _get_step_image_path(manual_id: int = 1, step_number: int = None):
    """
    Helper to get local file path for a given step
    """

    image_path = IMAGES_DIR / f"step{step_number}.png"
    if not image_path.exists():
        raise FileNotFoundError(f"Step image not found: {image_path}")
    return image_path

def start_orientation_generation(manual_id: int, from_step: int, to_step: int) -> None:
    """
    Start background orientation text generation.
    Non-blocking - returns immediately while analysis runs in background.
    """
    key = f"{manual_id}:{from_step}"
    
    # Don't start if already running
    if key in _background_tasks:
        return
    
    # Start background thread
    thread = threading.Thread(
        target=_generate_and_store_orientation,
        args=(manual_id, from_step, to_step),
        daemon=True
    )
    _background_tasks[key] = thread
    thread.start()


def _generate_and_store_orientation(manual_id: int, from_step: int, to_step: int) -> None:
    """
    Background worker: Generate orientation text and store in database.
    This runs in a separate thread.
    """
    try:
        # Get image URLs
        current_image_path = _get_step_image_path(manual_id, from_step)
        next_image_path = _get_step_image_path(manual_id, to_step)
        
        # Run orientation analysis
        result = analyze_orientation_change(current_image_path, next_image_path)
        
        # Store as JSON string in database
        orientation_json = json.dumps(result)
        store_value(manual_id, from_step, StepColumn.ORIENTATION_TEXT, orientation_json)
        
        print(f"Stored orientation text for manual {manual_id}, step {from_step}: {result}")
        
    except Exception as e:
        print(f"Error generating orientation text: {e}")
    finally:
        # Clean up task tracking
        key = f"{manual_id}:{from_step}"
        if key in _background_tasks:
            del _background_tasks[key]


# -----------------------------------------------
# PROMPT AND TEXT GENERATION WITH REPLICATE
# -----------------------------------------------

MODEL = "openai/gpt-4.1-mini"

SYSTEM_PROMPT = """
You compare two images representing consecutive steps in a workflow.

Your job is to determine whether a deliberate orientation change is required
between the current step and the next step.

Only comment on user-actionable orientation changes:
- Rotation (90°, 180°)
- Flipping or mirroring
- Portrait ↔ landscape
- Alignment changes that require user action

Ignore color, styling, annotations, and content differences.

You must return a JSON object and nothing else.
""".strip()


PROMPT = """
Image A is the current step.
Image B is the next step reference.

If NO orientation change is required, return:
{"show_popup": false, "message": ""}

If an orientation change IS required, return:
{"show_popup": true, "message": "<concise actionable guidance (≤80 words)>"}
""".strip()


def analyze_orientation_change(
    current_image_url: str,
    next_image_url: str,
) -> Dict[str, str]:

    safe_default = {"show_popup": False, "message": ""}

    if not os.getenv("REPLICATE_API_TOKEN"):
        return safe_default

    input_data = {
        "system_prompt": SYSTEM_PROMPT,
        "prompt": PROMPT,
        "image_input": [
            open(current_image_url,"rb"),
            open(next_image_url,"rb"),
        ],
        "max_output_tokens": 200,
    }

    response_parts = []

    try:
        for event in replicate.stream(MODEL, input=input_data):
            response_parts.append(str(event))
    except Exception as e:
        print(f"Warning: replicate call failed: {e}")
        return safe_default

    response_text = "".join(response_parts).strip()

    # Hard safety checks
    if not response_text or not response_text.startswith("{"):
        return safe_default

    try:
        result = json.loads(response_text)
    except json.JSONDecodeError:
        return safe_default

    if not isinstance(result, dict):
        return safe_default

    show_popup = bool(result.get("show_popup", False))
    message = result.get("message", "")

    if not show_popup:
        return safe_default

    # Enforce word limit
    words = message.split()
    if len(words) > 80:
        message = " ".join(words[:80])

    return {
        "show_popup": show_popup,
        "message": message,
    }
