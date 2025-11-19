# services/step_colorizer.py
import os
from pathlib import Path
from typing import Dict


# You can override this via an env var, e.g. IMAGE_ROOT=/Users/sangeonpark/Desktop/WayfairstudioImages
IMAGE_ROOT = Path(os.getenv("IMAGE_ROOT", "static/images")).resolve()


# change the path so that it uploads the right images
STEP_IMAGE_MAP: Dict[int, Dict[bool, str]] = {
    1: {
        False: "/Users/sangeonpark/Desktop/step1_base.png",
        True: "/Users/sangeonpark/Desktop/step1_colorized.png",
    },
    2: {
        False: "/Users/sangeonpark/Desktop/step2_base.png",
        True: "/Users/sangeonpark/Desktop/step2_colorized.png",
    },
}


def _resolve_image_path(path_str: str) -> Path:
    """
    Given a path string that might be absolute or relative,
    return an absolute Path object.
    """
    p = Path(path_str)

    # If it's already absolute, just return it.
    if p.is_absolute():
        return p

    # Otherwise, treat it as relative to IMAGE_ROOT.
    return (IMAGE_ROOT / p).resolve()


def get_step_image_path(step_id: int, colorized: bool) -> Path:
    """
    Service function that returns the absolute filesystem path
    to the image for a given step and toggle state.
    """
    step_mapping = STEP_IMAGE_MAP.get(step_id)

    # Fallback if step is not defined
    if step_mapping is None:
        # Use step 1 as a default, or raise an error if you prefer
        step_mapping = STEP_IMAGE_MAP.get(1, {})

    path_str = step_mapping.get(colorized)

    if path_str is None:
        # Fallback: pick any defined variant for that step
        if step_mapping:
            path_str = next(iter(step_mapping.values()))
        else:
            raise FileNotFoundError(f"No image mapping defined for step {step_id}")

    image_path = _resolve_image_path(path_str)

    return image_path
