from pathlib import Path
import base64
from pydantic import BaseModel

# Configure the directory where lasso screenshots will be stored
LASSO_STORAGE_DIR = Path("lasso_screenshots")
LASSO_STORAGE_DIR.mkdir(exist_ok=True)


DEFAULT_ANALYSIS_PROMPT = (
    "You are a concise assembly assistant. "
    "The user has selected a region of an assembly manual diagram. "
    "In 1–2 short sentences, describe what is shown in the selected area: "
    "identify the parts, their relationship, and what is happening at this step. "
    "Be specific and factual. Do not start with 'I' or 'This image'."
)


class LassoImageData(BaseModel):
    image_data: str  # base64 encoded image
    step: int


def _get_default_analysis(image_data_b64: str) -> str:
    """Send the lasso crop to Claude and return a short default description."""
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": DEFAULT_ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
    )
    return message.content[0].text.strip()


def save_lasso_screenshot(data: LassoImageData):
    """Save a lasso screenshot and return a default AI analysis of it."""
    # Strip data URL prefix if present (e.g. "data:image/png;base64,")
    # image_data = data.image_data
    # if "," in image_data:
    #     image_data = image_data.split(",")[1]

    # # Save to disk
    # image_bytes = base64.b64decode(image_data)
    # file_path = LASSO_STORAGE_DIR / "lasso.png"
    # with open(file_path, "wb") as f:
    #     f.write(image_bytes)

    # # Get AI description of the selected region
    # default_analysis = _get_default_analysis(image_data)

    return {
        "success": True,
        "default_analysis": "hello from the backend",
    }