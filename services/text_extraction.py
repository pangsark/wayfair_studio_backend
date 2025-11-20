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

    # later this will come from db
    explanations = {1:"Begin by placing the two long horizontal panels labeled 01 on a flat surface. Insert the vertical panel labeled 02 into the slots on the horizontal panels. Ensure the edges are aligned and the central partition is secured within the grooves for stability.",
    2:"Take the panel labeled 01 and align it with the previously assembled structure. Using the tool A12, insert and tighten screws A13 into the side, securing the panel in place. Repeat this process for the opposite side to ensure the panels are firmly attached."}


    return {
        "step": step_id,
        "magicNumber": magic_number,
        "explanation": explanations[step_id],
    }

def get_checklist(step_id):
    checklist = {1:["Rubber Mallet (optional)"], 2:["Allen Wrench (A13)"]}
    
    return checklist[step_id]