import os
import logging
import httpx

logger = logging.getLogger("sahayai.stt")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Persistent client
_stt_client: httpx.AsyncClient | None = None


def _get_stt_client() -> httpx.AsyncClient:
    global _stt_client
    if _stt_client is None or _stt_client.is_closed:
        _stt_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
        )
    return _stt_client


async def close_stt_client():
    global _stt_client
    if _stt_client and not _stt_client.is_closed:
        await _stt_client.aclose()


async def speech_to_text(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    language: str = "en",
) -> dict:
    """
    Transcribe audio to text via Groq Whisper (free tier).
    
    This is the server-side STT option. Used when:
    - Flutter's on-device STT isn't good enough (noisy environment)
    - We want more accurate transcription for CCT scoring
    - The audio was recorded and sent as a file

    For real-time voice, Flutter still uses its local speech_to_text
    plugin and sends the text to /conversation. This function is
    for cases where we want server-quality transcription.
    
    Returns: {"text": "transcribed text", "language": "en", "provider": "groq"}
    """

    # --- Groq Whisper (free, fast) ---
    if GROQ_API_KEY:
        try:
            result = await _groq_whisper(audio_bytes, filename, language)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Groq Whisper failed: {e}")

    logger.error("STT failed — no providers available")
    return {"text": "", "language": language, "provider": "none", "error": "No STT provider available"}


async def _groq_whisper(audio_bytes: bytes, filename: str, language: str) -> dict | None:
    """
    Groq's Whisper endpoint — free tier, fast inference.
    Supports: wav, mp3, m4a, webm, mp4, mpeg, mpga, oga, ogg, flac
    """
    client = _get_stt_client()

    # Groq uses multipart form upload for audio
    files = {"file": (filename, audio_bytes, "audio/wav")}
    data = {
        "model": "whisper-large-v3-turbo",
        "language": language,
        "response_format": "json",
    }

    resp = await client.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        files=files,
        data=data,
    )
    resp.raise_for_status()
    result = resp.json()

    text = result.get("text", "")
    logger.info(f"Groq Whisper transcribed: '{text[:80]}...'")

    return {
        "text": text,
        "language": language,
        "provider": "groq_whisper",
    }