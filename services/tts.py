import traceback
import replicate

# Kokoro-82m TTS model on Replicate
KOKORO_MODEL = "jaaari/kokoro-82m"
KOKORO_VERSION = "f559560eb822dc509045f3921a1921234918b91739db4bf3daab2169b71c7a13"

# Default voice — American English female
DEFAULT_VOICE = "am_adam"


def synthesize_speech(text: str, voice: str = DEFAULT_VOICE) -> str:
    """
    Convert text to speech using Kokoro-82m via Replicate.

    Args:
        text: The text to speak (should be a sentence or short paragraph)
        voice: Voice ID (default: af_bella — American English female)

    Returns:
        URL to the generated audio file
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    # Strip markdown formatting for cleaner speech
    clean_text = text.strip()
    for ch in ["**", "*", "#", "`", "- ", "• "]:
        clean_text = clean_text.replace(ch, "")

    print(f"[TTS] Synthesizing: '{clean_text[:80]}...' (voice={voice})")

    try:
        output = replicate.run(
            f"{KOKORO_MODEL}:{KOKORO_VERSION}",
            input={
                "text": clean_text,
                "voice": voice,
            },
        )

        print(f"[TTS] Raw output type: {type(output)}, value: {repr(output)[:200]}")

        # Output is typically a FileOutput URL
        audio_url = str(output)
        print(f"[TTS] Audio URL: {audio_url}")

        return audio_url

    except Exception as e:
        print(f"[TTS] FAILED: {repr(e)}")
        traceback.print_exc()
        raise
