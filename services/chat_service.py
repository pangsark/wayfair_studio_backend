# services/chat_service.py
import os
from typing import Optional
from dotenv import load_dotenv
import replicate

from .text_extraction import get_step_explanation, discover_step_numbers
from .db import get_session_history, save_chat_message

HISTORY_WINDOW = 10

load_dotenv()

# Model to use (via Replicate)
MODEL = "openai/gpt-4.1-mini"

# System prompt template
SYSTEM_PROMPT_TEMPLATE = """You are a helpful assembly assistant for Wayfair furniture. Your role is to use the context you have from user input, the given assembly manual/step, 
and general furniture assembly process to help users who are building furniture and have questions about the assembly process. If the user's question is not related to the assembly process, you should say so and suggest they contact customer service.

You are currently helping with:
- Manual ID: {manual_id}
- The user is currently on **Step {step_number}**

## Full Assembly Manual — All Steps

{all_steps_context}

## Guidelines

1. Be clear, concise, and encouraging
2. You have the full manual above — use it to answer questions about any step, not just the current one
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
    Build a system prompt with descriptions for every step in the manual so the
    AI can answer questions about any step, not just the current one.
    Descriptions come from the DB cache (populated at startup), so no AI calls
    are made here in the normal case.
    """
    valid_steps = sorted(discover_step_numbers(manual_id))

    step_sections = []
    for n in valid_steps:
        try:
            data = get_step_explanation(manual_id=manual_id, step_number=n)
            desc = data.get("description", "No description available.")
        except Exception:
            desc = "No description available."
        current_marker = " ← **USER IS CURRENTLY ON THIS STEP**" if n == step_number else ""
        step_sections.append(f"### Step {n}{current_marker}\n{desc}")

    all_steps_context = "\n\n".join(step_sections) if step_sections else "No step information available."

    return SYSTEM_PROMPT_TEMPLATE.format(
        manual_id=manual_id,
        step_number=step_number,
        all_steps_context=all_steps_context,
    )

def get_chat_response(
    manual_id: int,
    step_number: int,
    user_message: str,
    session_id: str,
    image_url: Optional[str] = None
) -> dict:
    """
    Get an AI response for a user's assembly question using Replicate's hosted OpenAI.

    Conversation history is loaded from the DB using `session_id` and windowed to
    the last HISTORY_WINDOW messages. Both the user message and assistant reply are
    persisted to the DB before returning.

    Args:
        manual_id: The manual ID
        step_number: The current step number
        user_message: The user's question
        session_id: UUID identifying this conversation session
        image_url: Optional image URL for vision-based questions

    Returns:
        dict with "response" and "session_id" keys
    """
    # Build the system prompt with step context
    system_prompt = _build_system_prompt(manual_id, step_number)

    # Load windowed history from DB and append the new user message
    history = get_session_history(session_id, limit=HISTORY_WINDOW)
    prompt_parts = []
    for msg in history:
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

    # Persist the user message before calling the AI
    save_chat_message(session_id, manual_id, step_number, "user", user_message)

    # Call Replicate API and collect streamed response
    response_parts = []
    for event in replicate.stream(MODEL, input=input_data):
        response_parts.append(str(event))

    assistant_message = "".join(response_parts)

    # Persist the assistant reply
    save_chat_message(session_id, manual_id, step_number, "assistant", assistant_message)

    return {
        "response": assistant_message,
        "session_id": session_id,
        "manual_id": manual_id,
        "step_number": step_number
    }
