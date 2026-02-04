from enum import Enum

class StepColumn(str, Enum):
    DESCRIPTION = "description"
    TOOLS = "tools"
    IMAGE_URL = "image_url"
    IMAGE_ALT = "image_alt"
    COLORIZED_IMAGE_URL = "colorized_image_url"