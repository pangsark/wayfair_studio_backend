from pathlib import Path
import base64
from pydantic import BaseModel

# Configure the directory where lasso screenshots will be stored
LASSO_STORAGE_DIR = Path("lasso_screenshots")
LASSO_STORAGE_DIR.mkdir(exist_ok=True)

class LassoImageData(BaseModel):
    image_data: str  # base64 encoded image
    step: int


def save_lasso_screenshot(data: LassoImageData):
    """Save a lasso screenshot as lasso.png"""
    # Remove the data URL prefix if present (e.g., "data:image/png;base64,")
    image_data = data.image_data
    if ',' in image_data:
        image_data = image_data.split(',')[1]
    
    # Decode base64 and save
    image_bytes = base64.b64decode(image_data)
    file_path = LASSO_STORAGE_DIR / "lasso.png"
    
    with open(file_path, "wb") as f:
        f.write(image_bytes)
    
    return {"success": True}