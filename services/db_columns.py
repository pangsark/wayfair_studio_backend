from enum import Enum

class StepColumn(str, Enum):
    DESCRIPTION = "description"
    CHECKLIST = "checklist"
    IMAGE_URL = "image_url"
    IMAGE_ALT = "image_alt"
