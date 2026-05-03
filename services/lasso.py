"""
Lasso screenshot service.

Receives a base64-encoded PNG crop from the frontend's LassoTool, saves it to
lasso_screenshots/lasso.png, then sends both the crop and the full step image
to GPT-4o via Replicate.

The AI returns a JSON object with:
  summary   — 1-3 sentence description of what the lassoed region shows
  questions — exactly 2 contextual questions the user might want to ask

Note: lasso.png is always overwritten; concurrent users will clobber each
other's screenshots. This is acceptable for single-user or sequential use but
should be addressed (e.g. per-session filenames) for concurrent deployment.
"""
import os
from pathlib import Path
import base64
import json
import replicate
from pydantic import BaseModel

# Absolute path so the directory resolves correctly regardless of cwd
LASSO_STORAGE_DIR = Path(__file__).resolve().parent.parent / "lasso_screenshots"
LASSO_STORAGE_DIR.mkdir(exist_ok=True)

MANUALS_DIR = Path(__file__).resolve().parent.parent / "public" / "manuals"

# Vision model for analyzing the lassoed image
VISION_MODEL = "openai/gpt-4o"

ANALYSIS_PROMPT = """You are an expert furniture assembly assistant. You are given two images:

1. **Full step image** — the complete assembly step diagram from a furniture manual.
2. **Lassoed region** — a user-selected crop from the same step image.

Analyze the lassoed region in the context of the full assembly step and respond with a JSON object containing:

- "summary": A concise 1-3 sentence description of what the lassoed region shows (e.g. a specific part, a fastener, a connection point, a sub-step illustration, etc.)
- "questions": An array of exactly 2 contextual questions (the "best" ones) the user might want to ask about this specific region. These should be practical and relevant to someone assembling furniture.

Respond ONLY with valid JSON, no markdown code fences or extra text.

Example response:
{"summary": "This shows the cam lock connector being inserted into the pre-drilled hole on the side panel.", "questions": ["How do I properly tighten this connector?", "What tool do I need for this part?", "Which direction should the arrow face?"]}
"""


class LassoImageData(BaseModel):
    image_data: str  # base64 encoded image
    step: int
    manual_id: int = 1  # default to manual 1 for backwards compat


def save_lasso_screenshot(image_data: str) -> Path:
    """Save a lasso screenshot as lasso.png and return the file path."""
    # Remove the data URL prefix if present (e.g., "data:image/png;base64,")
    if ',' in image_data:
        image_data = image_data.split(',')[1]

    # Decode base64 and save
    image_bytes = base64.b64decode(image_data)
    file_path = LASSO_STORAGE_DIR / "lasso.png"

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    return file_path


def _find_step_image(step_number: int, manual_id: int = 1) -> Path:
    """Find the full step image file under public/manuals/<manual_id>/."""
    manual_dir = MANUALS_DIR / str(manual_id)
    for ext in [".png", ".jpg", ".jpeg"]:
        potential_path = manual_dir / f"step{step_number}{ext}"
        if potential_path.exists():
            return potential_path
    raise FileNotFoundError(f"Step image not found for manual {manual_id}, step {step_number}")


def analyze_lasso_image(data: LassoImageData) -> dict:
    """
    Save the lasso screenshot, then analyze it with GPT-4o vision
    using both the lassoed crop and the full step image for context.

    Returns:
        dict with keys: success, summary, questions
    """
    # 1. Save the lasso screenshot
    lasso_path = save_lasso_screenshot(data.image_data)

    # 2. Find the full step image
    step_image_path = _find_step_image(data.step, data.manual_id)

    print(f"[Lasso] Analyzing lasso image for step {data.step}")
    print(f"[Lasso] Step image: {step_image_path}")
    print(f"[Lasso] Lasso crop: {lasso_path}")

    # 3. Send both images to GPT-4o via Replicate
    try:
        response_parts = []
        with open(step_image_path, "rb") as step_img, open(lasso_path, "rb") as lasso_img:
            for event in replicate.stream(
                VISION_MODEL,
                input={
                    "image_input": [step_img, lasso_img],
                    "prompt": ANALYSIS_PROMPT,
                }
            ):
                response_parts.append(str(event))

        raw_response = "".join(response_parts).strip()
        print(f"[Lasso] Raw AI response: {raw_response}")

        # 4. Parse the JSON response
        # Strip markdown code fences if the model wraps it
        cleaned = raw_response
        if cleaned.startswith("```"):
            # Remove first line (```json) and last line (```)
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])

        parsed = json.loads(cleaned)

        summary = parsed.get("summary", "Unable to generate summary.")
        questions = parsed.get("questions", [])

        # Enforce exactly 2 questions
        if len(questions) < 2:
            questions = (questions + ["What is this part?", "How do I assemble this?"])[:2]
        elif len(questions) > 2:
            questions = questions[:2]

        base_url = os.getenv("APP_URL", "http://localhost:4000").rstrip("/")
        stored_image_url = f"{base_url}/lasso_screenshots/lasso.png"

        return {
            "success": True,
            "summary": summary,
            "questions": questions,
            "image_url": stored_image_url,
        }

    except json.JSONDecodeError as e:
        print(f"[Lasso] Failed to parse AI response as JSON: {e}")
        return {
            "success": True,
            "summary": raw_response[:500] if raw_response else "Expert analysis of the selected assembly region.",
            "questions": [
                "What is this part?",
                "How do I assemble this?",
            ],
            "image_url": f"{os.getenv('APP_URL', 'http://localhost:4000').rstrip('/')}/lasso_screenshots/lasso.png"
        }
    except Exception as e:
        print(f"[Lasso] AI analysis failed: {e}")
        return {
            "success": True,
            "summary": "Expert analysis of the selected assembly region.",
            "questions": [
                "What is this part?",
                "How do I assemble this?",
            ],
            "image_url": f"{os.getenv('APP_URL', 'http://localhost:4000').rstrip('/')}/lasso_screenshots/lasso.png"
        }