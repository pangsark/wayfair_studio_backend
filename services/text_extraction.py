# services/text_extraction.py
from typing import TypedDict
import os
import replicate
import json


class ExplanationData(TypedDict):
    step: int
    magicNumber: int
    explanation: str

BASE_IMAGE_PATH = "/Users/graceeverts/Desktop/clinic/pdfs/shelf_2/Step{}.png"

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

# helper functions calling replicate api
def get_text(step_num):
    image_path = BASE_IMAGE_PATH.format(step_num)
    input = {
        "prompt": ("For the given furniture manual step, give a textual description of the procedure and objects. The textual description should be 3-5 sentences. Rules: \n" 
                    "If parts are labeled, refer to them with that label. Otherwise, infer what the part is.\n The output should ONLY include a textual description for the step."),
        "system_prompt": "You are an expert in furnature assembly manuals.",
        "image_input":[open(image_path,"rb")]
    }

    output = "".join(replicate.run("openai/gpt-4o", input))
    print("Text Description:\n",output,'\n\n\n')
    return output

def get_tools(step_num, tool_list = []):
    image_path = BASE_IMAGE_PATH.format(step_num)
    input = {
        "prompt": ("For the given furniture manual step, give a list of tool(s) needed to complete the step. If a tool is explicitely labeled and shown, include it in the list. Otherwise, infer from the step what tools (if any) are required. Include only TOOLS, not PARTS. Output should ONLY be an array of tools"),
        "system_prompt": "You are an expert in furnature assembly manuals.",
        "image_input":[open(image_path,"rb")]
    }

    output = json.loads("".join(replicate.run("openai/gpt-4o", input)))
    print("Tools:\n",output,'\n\n\n')
    return output