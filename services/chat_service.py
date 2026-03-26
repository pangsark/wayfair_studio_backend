# services/chat_service.py
import os
import json
from pathlib import Path
from typing import Any, Optional
from dotenv import load_dotenv
import replicate

from .text_extraction import get_step_explanation, discover_step_numbers

load_dotenv()

# Model to use (via Replicate)
MODEL = "openai/gpt-4.1-mini"

# System prompt template
SYSTEM_PROMPT_TEMPLATE = """You are a helpful assembly assistant for Wayfair furniture. Your role is to use the context you have from user input, the given assembly manual/step, 
and general furniture assembly process to help users who are building furniture and have questions about the assembly process. If the user's question is not related to the assembly process, you should say so and suggest they contact customer service.

You are currently helping with:
- Manual ID: {manual_id}
- Step {step_number}

## Previous Step (Step {prev_step_number}) — for context

{prev_step_context}

## Current Step Information

**Description:**
{step_description}

**Tools needed for this step:**
{tools_list}

## Next Step (Step {next_step_number}) — for context

{next_step_context}

## Guidelines

1. Be clear, concise, and encouraging
2. Reference the specific step details when answering
3. If the user seems confused, break down the instructions into smaller sub-steps
4. Warn about common mistakes when relevant
5. If you don't have enough information to answer, say so honestly
6. Do not add generic closing sentences (e.g. "Make sure you have these ready before starting…", "Let me know if you need more help!", "Feel free to ask if you have questions"). End with the direct answer.

## Output Type (MUST)
Choose exactly one:
- `procedural` when the user is asking for how to do the assembly at this step (or what to do next), including tools, sub-steps, parts identification, or common mistakes.
- `qa` when the user is asking a non-procedural question that needs a short explanation rather than an instruction sequence.

## Intent Guidance (MUST)
Preset intent for this message: `{intent}` (one of: explain_step, orientation, stuck, none).
- If intent is `explain_step`: prefer `procedural` and do NOT include `common_mistakes`.
- If intent is `orientation`: prefer concise orientation-focused guidance; usually `qa` unless stepwise orientation instructions are needed.
- If intent is `stuck`: use `procedural`; include `common_mistakes` only when it helps troubleshoot.
- If intent is `none`: use your best judgment and include `common_mistakes` only when explicitly helpful.

## Output Format (MUST)
Output ONLY valid JSON. No markdown fences, no surrounding text, no commentary.

If `type` is `procedural`, output this exact JSON schema:
{{
  "type": "procedural",
  "summary": "string",
  "steps": ["string", "string"]
}}
Optional field (include only when relevant, mainly when intent is `stuck`):
{{ "common_mistakes": ["string"] }}

If `type` is `qa`, output this exact JSON schema:
{{
  "type": "qa",
  "answer": "string",
  "why": "string (optional, omit if not applicable)"
}}

## Hard Word Cap (CRITICAL)
The total word count across all string fields in the selected JSON object MUST be <= 150 words.
If the content is too long, shorten it until it fits.
"""

STRUCTURED_WORD_CAP = 150


def _count_words(text: str) -> int:
    return len(text.strip().split())


def _extract_json_candidate(text: str) -> str:
    """
    Extract a JSON object substring from the model output.
    This is a best-effort recovery for cases where the model includes
    minor surrounding whitespace or code fences.
    """
    t = text.strip()
    # Best-effort: keep the outermost {...} region if present.
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        return t[start : end + 1]
    return t


def _normalize_intent(intent: Optional[str]) -> str:
    value = (intent or "none").strip().lower()
    if value in {"explain_step", "orientation", "stuck"}:
        return value
    return "none"


def _validate_structured_payload(payload: Any, intent: Optional[str]) -> tuple[bool, Optional[str]]:
    if not isinstance(payload, dict):
        return False, "Output JSON must be an object."

    payload_type = payload.get("type")
    if payload_type not in {"procedural", "qa"}:
        return False, "JSON field `type` must be exactly `procedural` or `qa`."

    if payload_type == "procedural":
        allowed_keys = {"type", "summary", "steps", "common_mistakes"}
        required_keys = {"type", "summary", "steps"}
        keys = set(payload.keys())
        if not required_keys.issubset(keys) or not keys.issubset(allowed_keys):
            return False, "Procedural JSON must include type, summary, steps and only optional common_mistakes."

        summary = payload.get("summary")
        steps = payload.get("steps")
        common_mistakes = payload.get("common_mistakes", [])

        if not isinstance(summary, str) or not summary.strip():
            return False, "`summary` must be a non-empty string."
        if not isinstance(steps, list) or not steps or any(not isinstance(s, str) for s in steps):
            return False, "`steps` must be a non-empty list of strings."
        if not isinstance(common_mistakes, list) or any(not isinstance(s, str) for s in common_mistakes):
            return False, "`common_mistakes` must be a list of strings."
        normalized_intent = _normalize_intent(intent)
        if normalized_intent != "stuck" and common_mistakes:
            return False, "`common_mistakes` must be omitted unless intent is `stuck`."

        word_text = " ".join([summary] + steps + common_mistakes)
        if _count_words(word_text) > STRUCTURED_WORD_CAP:
            return False, f"Word cap exceeded (>{STRUCTURED_WORD_CAP} words) in procedural JSON."

        return True, None

    # qa
    if not set(payload.keys()).issubset({"type", "answer", "why"}):
        return False, "QA JSON must only contain keys: type, answer, and optional why."

    answer = payload.get("answer")
    why = payload.get("why", None)

    if not isinstance(answer, str) or not answer.strip():
        return False, "`answer` must be a non-empty string."
    if why is not None and not isinstance(why, str):
        return False, "`why` must be a string when present."

    word_text = " ".join([answer, why or ""])
    if _count_words(word_text) > STRUCTURED_WORD_CAP:
        return False, f"Word cap exceeded (>{STRUCTURED_WORD_CAP} words) in qa JSON."

    return True, None


def _prepare_image_input(
    image_url: Optional[str],
    secondary_image_url: Optional[str],
) -> tuple[list[Any], list[Any]]:
    """
    Build Replicate `image_input`.

    Returns:
      (image_inputs, opened_files_to_close)
    """

    def resolve_to_file(url: str) -> Optional[object]:
        if not url:
            return None
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            path_parts = parsed.path.strip("/").split("/")
            base_dir = Path(__file__).resolve().parent.parent
            if path_parts[0] == "manuals" and len(path_parts) >= 3:
                # /manuals/{id}/stepN.png -> public/manuals/{id}/stepN.png
                file_path = base_dir / "public" / "manuals" / path_parts[1] / path_parts[-1]
            elif path_parts[0] == "lasso_screenshots":
                file_path = base_dir / "lasso_screenshots" / path_parts[-1]
            else:
                return None
            if file_path.exists():
                return open(file_path, "rb")
            return None
        except Exception as e:
            print(f"Error resolving URL {url}: {e}")
            return None

    image_inputs: list[Any] = []
    opened_files: list[Any] = []
    for url in [image_url, secondary_image_url]:
        if not url:
            continue
        file_obj = resolve_to_file(url)
        if file_obj:
            image_inputs.append(file_obj)
            opened_files.append(file_obj)
        elif "localhost" not in url and "127.0.0.1" not in url:
            # Fallback to URL if it's not a localhost URL (e.g. external)
            image_inputs.append(url)

    return image_inputs, opened_files


def _call_replicate_text(system_prompt: str, prompt: str, images: list[Any]) -> str:
    input_data: dict[str, Any] = {"prompt": prompt, "system_prompt": system_prompt}
    if images:
        input_data["image_input"] = images

    response_parts: list[str] = []
    for event in replicate.stream(MODEL, input=input_data):
        response_parts.append(str(event))
    return "".join(response_parts)


def _get_validated_structured_payload(
    manual_id: int,
    step_number: int,
    user_message: str,
    conversation_history: Optional[list[dict]],
    image_url: Optional[str],
    secondary_image_url: Optional[str],
    intent: Optional[str] = None,
    *,
    max_attempts: int = 3,
) -> dict[str, Any]:
    normalized_intent = _normalize_intent(intent)
    system_prompt = _build_system_prompt(manual_id, step_number, normalized_intent)

    prompt_parts = []
    if conversation_history:
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role.capitalize()}: {content}")
    prompt_parts.append(f"User: {user_message}")
    base_prompt = "\n\n".join(prompt_parts)

    images, opened_files = _prepare_image_input(image_url, secondary_image_url)
    try:
        last_error: Optional[str] = None
        for attempt_idx in range(max_attempts):
            retry_suffix = ""
            if attempt_idx > 0:
                retry_suffix = (
                    "\n\nYour previous output was invalid. "
                    "Output ONLY valid JSON matching the required schema exactly. "
                    "No markdown fences and no extra fields."
                )

            prompt = base_prompt + retry_suffix

            # Reset file pointers before each attempt (Replicate may read streams).
            for img in opened_files:
                try:
                    img.seek(0)
                except Exception:
                    pass

            raw_text = _call_replicate_text(system_prompt, prompt, images)
            candidate = _extract_json_candidate(raw_text)
            try:
                payload = json.loads(candidate)
            except Exception:
                last_error = "Model output was not valid JSON."
                continue

            valid, validation_error = _validate_structured_payload(payload, normalized_intent)
            if valid:
                return payload
            last_error = validation_error

        raise ValueError(last_error or "Model output did not validate after retries.")
    finally:
        for img in opened_files:
            try:
                img.close()
            except Exception:
                pass


def _build_system_prompt(manual_id: int, step_number: int, intent: str = "none") -> str:
    """
    Build a system prompt with context from the current step, as well as the
    previous and next steps when they exist.
    """
    valid_steps = set(discover_step_numbers(manual_id))

    try:
        explanation_data = get_step_explanation(manual_id=manual_id, step_number=step_number)
        step_description = explanation_data.get("description", "No description available.")
    except Exception:
        step_description = "No description available for this step."

    prev_num = step_number - 1
    if prev_num in valid_steps:
        try:
            prev_data = get_step_explanation(manual_id=manual_id, step_number=prev_num)
            prev_step_context = prev_data.get("description", "No description available.")
        except Exception:
            prev_step_context = "No description available for this step."
        prev_step_number = str(prev_num)
    else:
        prev_step_number = "N/A"
        prev_step_context = "(none — this is the first step)"

    next_num = step_number + 1
    if next_num in valid_steps:
        try:
            next_data = get_step_explanation(manual_id=manual_id, step_number=next_num)
            next_step_context = next_data.get("description", "No description available.")
        except Exception:
            next_step_context = "No description available for this step."
        next_step_number = str(next_num)
    else:
        next_step_number = "N/A"
        next_step_context = "(none — this is the last step)"

    tools_list = "(Tools mentioned in the step description above)"

    return SYSTEM_PROMPT_TEMPLATE.format(
        manual_id=manual_id,
        step_number=step_number,
        step_description=step_description,
        tools_list=tools_list,
        prev_step_number=prev_step_number,
        prev_step_context=prev_step_context,
        next_step_number=next_step_number,
        next_step_context=next_step_context,
        intent=intent,
    )

def get_chat_response(
    manual_id: int,
    step_number: int,
    user_message: str,
    conversation_history: Optional[list[dict]] = None,
    image_url: Optional[str] = None,
    secondary_image_url: Optional[str] = None,
    intent: Optional[str] = None,
) -> dict:
    """
    Get a validated structured chat payload for a user's assembly question.

    Args:
        manual_id: The manual ID
        step_number: The current step number
        user_message: The user's question
        conversation_history: Optional list of previous messages for multi-turn chat
                              Format: [{"role": "user"|"assistant", "content": "..."}]
        image_url: Optional image URL for vision-based questions
        secondary_image_url: Optional second image URL for additional context (e.g. lassoed crop)

    Returns:
        dict with "payload", "manual_id", and "step_number"
    """
    payload = _get_validated_structured_payload(
        manual_id=manual_id,
        step_number=step_number,
        user_message=user_message,
        conversation_history=conversation_history,
        image_url=image_url,
        secondary_image_url=secondary_image_url,
        intent=intent,
    )

    return {
        "payload": payload,
        "manual_id": manual_id,
        "step_number": step_number,
    }


def get_chat_response_stream(
    manual_id: int,
    step_number: int,
    user_message: str,
    conversation_history: Optional[list[dict]] = None,
    image_url: Optional[str] = None,
    secondary_image_url: Optional[str] = None,
    intent: Optional[str] = None,
):
    """
    Yield newline-safe structured stream events.
    """
    payload = _get_validated_structured_payload(
        manual_id=manual_id,
        step_number=step_number,
        user_message=user_message,
        conversation_history=conversation_history,
        image_url=image_url,
        secondary_image_url=secondary_image_url,
        intent=intent,
    )
    yield {"event": "final", "payload": payload}
