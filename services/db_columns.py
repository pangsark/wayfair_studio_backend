from enum import Enum

class StepColumn(str, Enum):
    DESCRIPTION = "description"
    TOOLS = "tools"
    IMAGE_URL = "image_url"
    ORIENTATION_TEXT = "orientation_text"
