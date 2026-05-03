"""
Audio transcription using OpenAI Whisper large-v3 via Replicate.

transcribe_audio() accepts base64-encoded audio (with or without a data URI
prefix), writes it to a temp file with the correct extension, calls Replicate,
and returns {"text": "transcription string"}.

Supported input formats: webm/opus (default from frontend), wav, mp3, ogg.
The frontend sends MediaRecorder output as webm/opus.
"""
import os
import base64
import tempfile
import traceback
from pathlib import Path

import replicate

# Use the Replicate-hosted OpenAI Whisper large-v3 model
# Version hash from https://replicate.com/openai/whisper/versions
WHISPER_VERSION = "3c08daf437fe359eb158a5123c395673f0a113dd8b4bd01ddce5936850e2a981"


def transcribe_audio(audio_base64: str) -> dict:
    """
    Transcribe base64-encoded audio using Replicate's Whisper model.

    Args:
        audio_base64: Base64-encoded audio data (may include data URI prefix)

    Returns:
        dict with "text" key containing the transcription
    """
    # Detect file extension from data URI prefix if present
    ext = ".webm"  # default — frontend sends webm/opus
    if "," in audio_base64:
        header = audio_base64.split(",", 1)[0]  # e.g. "data:audio/webm;base64"
        if "wav" in header:
            ext = ".wav"
        elif "mp3" in header:
            ext = ".mp3"
        elif "ogg" in header:
            ext = ".ogg"
        audio_base64 = audio_base64.split(",", 1)[1]

    audio_bytes = base64.b64decode(audio_base64)
    print(f"[Transcription] Received {len(audio_bytes)} bytes of audio (ext={ext})")

    # Write to a temp file so Replicate can read it
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        print(f"[Transcription] Calling Whisper via replicate (version={WHISPER_VERSION[:12]}...)")

        # Use the version-based API to avoid 404 with model shortname
        output = replicate.run(
            f"openai/whisper:{WHISPER_VERSION}",
            input={"audio": open(tmp_path, "rb")},
        )

        print(f"[Transcription] Raw output: {repr(output)}")

        # The Whisper model returns a dict with "transcription" key
        transcription = ""
        if isinstance(output, dict):
            transcription = output.get("transcription", output.get("text", ""))
        elif isinstance(output, str):
            transcription = output
        else:
            transcription = str(output)

        print(f"[Transcription] Result: '{transcription.strip()}'")
        return {"text": transcription.strip()}

    except Exception as e:
        print(f"[Transcription] Whisper failed: {repr(e)}")
        traceback.print_exc()
        raise
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
