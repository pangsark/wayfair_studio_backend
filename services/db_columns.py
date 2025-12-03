from enum import Enum

class StepColumn(str, Enum):
    DESCRIPTION = "description"
    TOOLS = "tools"
    IMAGE_URL = "image_url"
    IMAGE_ALT = "image_alt"
