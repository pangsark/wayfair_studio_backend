# services/step_colorizer.py
import os
import replicate
from typing import Optional
from dotenv import load_dotenv

from .db import get_cached_value, store_value, get_product_image_url
from .db_columns import StepColumn

load_dotenv()

# Replicate model for reference-based colorization
COLORIZER_MODEL = "google/nano-banana"

# Default prompt for colorizing diagrams
DEFAULT_PROMPT = "Colorize the product dimensions diagram to be the same color as the real furniture. Only colorize the diagram, keeping the lines, arrows, and numbers."


def get_colorized_image_from_db(manual_id: int, step_number: int) -> Optional[str]:
    """
    Check if a colorized image URL exists in the database for this step.
    Returns the URL string if found, None otherwise.
    """
    result = get_cached_value(manual_id, step_number, StepColumn.COLORIZED_IMAGE_URL)
    if result and result.get("colorized_image_url"):
        return result["colorized_image_url"]
    return None


def get_base_image_url_from_db(manual_id: int, step_number: int) -> Optional[str]:
    """
    Get the base (non-colorized) diagram image URL from the database.
    """
    result = get_cached_value(manual_id, step_number, StepColumn.IMAGE_URL)
    if result and result.get("image_url"):
        return result["image_url"]
    return None


def colorize_with_replicate(colored_image_path: str, diagram_path: str, prompt: str = None) -> str:
    """
    Call Replicate API to colorize a diagram based on a reference colored image.
    
    Args:
        colored_image_path: Path or URL to the colored product reference image
        diagram_path: Path or URL to the diagram to colorize
        prompt: Optional custom prompt (defaults to furniture colorization prompt)
    
    Returns the URL of the colorized image.
    """
    if prompt is None:
        prompt = DEFAULT_PROMPT
    
    # Handle both file paths and URLs
    def open_image(path):
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return open(path, "rb")
    
    colored_img = open_image(colored_image_path)
    diagram_img = open_image(diagram_path)
    
    try:
        input_data = {
            "prompt": prompt,
            "image_input": [colored_img, diagram_img]
        }
        
        print(f"Running model {COLORIZER_MODEL}...")
        output = replicate.run(COLORIZER_MODEL, input=input_data)
        
        # Handle different output formats
        if hasattr(output, 'url'):
            return output.url()
        elif isinstance(output, list):
            return str(output[0])
        return str(output)
    finally:
        # Close file handles if we opened them
        if not isinstance(colored_img, str):
            colored_img.close()
        if not isinstance(diagram_img, str):
            diagram_img.close()


def get_step_image_url(
    manual_id: int, 
    step_number: int, 
    colorized: bool = False,
    product_image_path: str = None
) -> str:
    """
    Service function that returns the image URL for a given manual step.
    
    If colorized=True:
        1. Check database for cached colorized image
        2. If not found, get base diagram + product reference image
        3. Call Replicate to colorize using both images
        4. Cache the colorized result in the database
    
    If colorized=False:
        Return the base diagram image URL from the database
    
    Args:
        manual_id: The manual ID
        step_number: The step number within the manual
        colorized: Whether to return colorized version
        product_image_path: Optional override for the product reference image
    """
    if not colorized:
        # Just return the base diagram image
        base_url = get_base_image_url_from_db(manual_id, step_number)
        if not base_url:
            raise FileNotFoundError(f"No image found for manual {manual_id}, step {step_number}")
        return base_url
    
    # Check if colorized version is already cached
    cached_colorized_url = get_colorized_image_from_db(manual_id, step_number)
    if cached_colorized_url:
        return cached_colorized_url
    
    # Not cached - need to generate via Replicate
    # Get the diagram image
    diagram_url = get_base_image_url_from_db(manual_id, step_number)
    if not diagram_url:
        raise FileNotFoundError(f"No base diagram found for manual {manual_id}, step {step_number}")
    
    # Get the colored product reference image
    colored_ref = product_image_path or get_product_image_url(manual_id)
    if not colored_ref:
        raise FileNotFoundError(f"No product reference image found for manual {manual_id}")
    
    # Call Replicate API to colorize
    colorized_url = colorize_with_replicate(colored_ref, diagram_url)
    
    # Cache the result in the database
    store_value(manual_id, step_number, StepColumn.COLORIZED_IMAGE_URL, colorized_url)
    
    return colorized_url
