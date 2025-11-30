# services/text_extraction.py
import os
from typing import TypedDict

from . import db as db_helper
from .db_columns import StepColumn


def get_step_explanation(manual_id: int = 1, step_number: int = None):
    """
    Service function that returns explanation data for a given step.
    Right now it's hard-coded with the magic number 42, but you can
    later plug in real text extraction / ML logic here.
    """
    # Try DB cache -- if DB not configured or entry not found,
    # generate explanation and store in DB for next time

    cached = db_helper.get_cached_value(manual_id, step_number, StepColumn.DESCRIPTION)
    if cached and cached["description"]:
        return cached

    magic_number = 42

    # hardcoded descriptions if not in DB
    descriptions = {1:"Begin by placing the two long horizontal panels labeled 01 on a flat surface. Insert the vertical panel labeled 02 into the slots on the horizontal panels. Ensure the edges are aligned and the central partition is secured within the grooves for stability.",
    2:"Take the panel labeled 01 and align it with the previously assembled structure. Using the tool A12, insert and tighten screws A13 into the side, securing the panel in place. Repeat this process for the opposite side to ensure the panels are firmly attached."}

    # If requested step_number not present in our hard-coded map, raise KeyError
    description_text = descriptions[step_number]

    # store into DB (safe no-op if DB not configured)
    try:
        db_helper.store_value(manual_id, step_number, StepColumn.DESCRIPTION, description_text)
    except Exception:
        # log in the future.
        pass

    return {"manual_id": manual_id, "step": step_number, "description": description_text}

def get_checklist(manual_id: int = 1, step_number: int = None):

    cached = db_helper.get_cached_value(manual_id, step_number, StepColumn.CHECKLIST)
    if cached and cached["checklist"]:
        return cached

    checklist = {1:["Rubber Mallet (optional)", "Rubber Mallet 2 (optional)"], 2:["Allen Wrench (A13)"]}
    checklist_text = checklist[step_number]

    # store into DB (safe no-op if DB not configured)
    try:
        db_helper.store_value(manual_id, step_number, StepColumn.CHECKLIST, checklist_text)
    except Exception:
        # log in the future.
        pass

    return {"manual_id": manual_id, "step": step_number, "tools": checklist_text}