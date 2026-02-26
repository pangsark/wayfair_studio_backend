# services/chat_service.py
import os
from typing import Optional
from dotenv import load_dotenv
import replicate

from .text_extraction import get_step_explanation

load_dotenv()

# Model to use (via Replicate)
MODEL = "openai/gpt-4.1-mini"

# System prompt template
SYSTEM_PROMPT_TEMPLATE = """You are a helpful assembly assistant for Wayfair furniture. Your role is to use the context you have from user input, the given assembly manual/step, 
and general furniture assembly process to help users who are building furniture and have questions about the assembly process. If the user's question is not related to the assembly process, you should say so and suggest they contact customer service.

You are currently helping with:
- Manual ID: {manual_id}
- Step {step_number}

## Current Step Information

**Description:**
{step_description}

**Tools needed for this step:**
{tools_list}

## Guidelines

1. Be clear, concise, and encouraging
2. Reference the specific step details when answering
3. If the user seems confused, break down the instructions into smaller sub-steps
4. Warn about common mistakes when relevant
5. If you don't have enough information to answer, say so honestly
6. Do not add generic closing sentences (e.g. "Make sure you have these ready before starting…", "Let me know if you need more help!", "Feel free to ask if you have questions"). End with the direct answer.

## Response formatting

- When listing steps, parts, or options, always use a proper list format—do not put everything in one paragraph.
- For step-by-step instructions: use a numbered list (1. 2. 3.) for the main steps.
- Under each numbered step, use a separate bullet list for the descriptions or sub-items (use "- " or "• " for each bullet). Do not put those sub-items in a single paragraph.
- For unordered items (e.g. parts, tools, options), use a bullet list.
- Put each list item on its own line with a line break between items so the list is easy to read.

Example format:
1. **Identify Panels:**
   - Find the panels labeled "01" and "03."
   - Lay them on a flat surface.
2. **Arrange the "01" Panels:**
   - Stand the two "01" panels vertically.
   - Position them parallel, facing inward.
"""


def _build_system_prompt(manual_id: int, step_number: int) -> str:
    """
    Build a system prompt with context from the current step.
    """
    # Get step description (which includes tools info from GPT analysis of the image)
    try:
        explanation_data = get_step_explanation(manual_id=manual_id, step_number=step_number)
        step_description = explanation_data.get("description", "No description available.")
    except Exception:
        step_description = "No description available for this step."

    tools_list = "(Tools mentioned in the step description above)"

    return SYSTEM_PROMPT_TEMPLATE.format(
        manual_id=manual_id,
        step_number=step_number,
        step_description=step_description,
        tools_list=tools_list
    )

def get_chat_response(
    manual_id: int,
    step_number: int,
    user_message: str,
    conversation_history: Optional[list[dict]] = None,
    image_url: Optional[str] = None
) -> dict:
    """
    Get an AI response for a user's assembly question using Replicate's hosted OpenAI.

    Args:
        manual_id: The manual ID
        step_number: The current step number
        user_message: The user's question
        conversation_history: Optional list of previous messages for multi-turn chat
                              Format: [{"role": "user"|"assistant", "content": "..."}]
        image_url: Optional image URL for vision-based questions

    Returns:
        dict with "response" key containing the AI's answer
    """
    # Build the system prompt with step context
    system_prompt = _build_system_prompt(manual_id, step_number)

    # Build the prompt with conversation history
    prompt_parts = []
    
    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role.capitalize()}: {content}")
    
    prompt_parts.append(f"User: {user_message}")
    prompt = "\n\n".join(prompt_parts)

    # Build input for Replicate
    input_data = {
        "prompt": prompt,
        "system_prompt": system_prompt
    }

    # Add image if provided (for vision-based questions)
    if image_url:
        input_data["image_input"] = [image_url]

    # Call Replicate API and collect streamed response
    response_parts = []
    for event in replicate.stream(MODEL, input=input_data):
        response_parts.append(str(event))

    assistant_message = "".join(response_parts)

    return {
        "response": assistant_message,
        "manual_id": manual_id,
        "step_number": step_number
    }
