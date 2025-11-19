# services/text_extraction.py
from typing import TypedDict


class ExplanationData(TypedDict):
    step: int
    magicNumber: int
    explanation: str


def get_step_explanation(step_id: int) -> ExplanationData:
    """
    Service function that returns explanation data for a given step.
    Right now it's hard-coded with the magic number 42, but you can
    later plug in real text extraction / ML logic here.
    """
    magic_number = 42 

    explanation = (
        f"This is example server data for step {step_id}. "
        f"The magic number is {magic_number}."
    )

    return {
        "step": step_id,
        "magicNumber": magic_number,
        "explanation": explanation,
    }
