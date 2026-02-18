# services/step_checklist.py
import os
import json
import replicate
from typing import List
from dotenv import load_dotenv

from .text_extraction import get_step_explanation

load_dotenv()

CHECKLIST_PROMPT_TEMPLATE = """Based on the following assembly step description, generate a concise checklist of 3-5 specific actions and verifications the user should perform.

Step Description:
{step_description}

Generate ONLY a valid JSON response with this structure:
{{
  "checklist": [
    "action or verification 1",
    "action or verification 2",
    "action or verification 3"
  ]
}}

Guidelines:
- Each item should be 10-15 words max
- Include specific actions to perform
- Include verifications to check
- Mix practical steps with safety checks
- Make items actionable and clear

Return ONLY valid JSON, no other text."""


def generate_checklist(manual_id: int, step_number: int) -> dict:
    """
    Generate a checklist for a given step using GPT-4o.
    Always regenerates on each call (no caching).
    
    Args:
        manual_id: The manual ID
        step_number: The step number
    
    Returns:
        dict with structure:
        {
            "manual_id": int,
            "step": int,
            "checklist": [list of strings]
        }
    
    Raises:
        ValueError: If step description cannot be retrieved or checklist generation fails
    """
    # Get the step description from DB or generate it
    try:
        explanation_data = get_step_explanation(manual_id=manual_id, step_number=step_number)
        step_description = explanation_data.get("description", "")
    except Exception as e:
        raise ValueError(f"Could not get step description: {e}")
    
    if not step_description:
        raise ValueError(f"No description found for step {step_number}")
    
    # Build the prompt for GPT-4o
    prompt = CHECKLIST_PROMPT_TEMPLATE.format(step_description=step_description)
    
    # Call GPT-4o via Replicate
    response_parts = []
    try:
        for event in replicate.stream(
            "openai/gpt-4o",
            input={"prompt": prompt}
        ):
            response_parts.append(str(event))
    except Exception as e:
        print(f"Warning: replicate call failed: {e}")
        raise ValueError(f"Failed to generate checklist: {e}")
    
    response_text = "".join(response_parts).strip()
    
    # Parse the JSON response
    try:
        # Try to extract JSON from the response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON object found in response")
        
        json_str = response_text[json_start:json_end]
        parsed = json.loads(json_str)
        checklist = parsed.get("checklist", [])
        
        if not isinstance(checklist, list):
            raise ValueError("Checklist is not a list")
        
        if not checklist:
            raise ValueError("Checklist is empty")
    
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse checklist JSON response: {e}")
    
    return {
        "manual_id": manual_id,
        "step": step_number,
        "checklist": checklist
    }
