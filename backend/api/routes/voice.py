import logging
import base64

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from utils.stt import speech_to_text
from utils.tts import text_to_speech, text_to_speech_stream

router = APIRouter()
logger = logging.getLogger("sahayai.voice")


@router.post("/voice/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form(default="en"),
):
    """
    Server-side STT — send an audio file, get back text.
    Uses Groq Whisper (free tier). Flutter can use this instead
    of on-device STT when higher accuracy is needed.
    """
    audio_bytes = await audio.read()
    logger.info(f"Transcribing audio: {len(audio_bytes)} bytes, lang={language}")

    result = await speech_to_text(
        audio_bytes=audio_bytes,
        filename=audio.filename or "audio.wav",
        language=language,
    )

    return result


@router.post("/voice/speak")
async def speak_text(request: dict):
    """
    Server-side TTS — send text, get back human-like audio via ElevenLabs.
    Returns base64-encoded audio so Flutter can play it directly.

    Request: {"text": "Hello Ramesh", "voice_id": "optional_override"}
    Response: {"audio_base64": "...", "content_type": "audio/mpeg", "provider": "elevenlabs"}

    If ElevenLabs isn't available, returns audio_base64: null and Flutter
    falls back to its local flutter_tts.
    """
    text = request.get("text", "")
    voice_id = request.get("voice_id")

    if not text:
        return {"audio_base64": None, "provider": "none", "error": "No text provided"}

    logger.info(f"TTS request: '{text[:60]}...'")
    result = await text_to_speech(text=text, voice_id=voice_id)
    return result


@router.post("/voice/speak/stream")
async def speak_text_stream(request: dict):
    """
    Streaming TTS — audio starts playing ~200ms after request.
    Returns chunked audio stream instead of base64.
    Flutter uses this for real-time voice responses where latency matters.
    """
    text = request.get("text", "")
    voice_id = request.get("voice_id")

    if not text:
        return {"error": "No text provided"}

    logger.info(f"Streaming TTS: '{text[:60]}...'")

    return StreamingResponse(
        text_to_speech_stream(text=text, voice_id=voice_id),
        media_type="audio/mpeg",
    )