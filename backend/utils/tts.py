import os
import base64
import logging
import httpx

logger = logging.getLogger("sahayai.tts")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# ElevenLabs voice IDs — pick one that sounds warm and caring
# "Rachel" is great for a calm, reassuring female voice
# "Adam" for a warm male voice
# You can browse voices at https://elevenlabs.io/voice-library
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel by default

# Persistent client for connection reuse
_eleven_client: httpx.AsyncClient | None = None


def _get_eleven_client() -> httpx.AsyncClient:
    global _eleven_client
    if _eleven_client is None or _eleven_client.is_closed:
        _eleven_client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"xi-api-key": ELEVENLABS_API_KEY},
        )
    return _eleven_client


async def close_tts_client():
    """Called on server shutdown"""
    global _eleven_client
    if _eleven_client and not _eleven_client.is_closed:
        await _eleven_client.aclose()


async def text_to_speech(
    text: str,
    voice_id: str = None,
    model: str = "eleven_turbo_v2_5",
) -> dict:
    """
    Convert text to human-like speech via ElevenLabs.
    Returns base64-encoded audio that Flutter can play directly.

    Falls back to None if ElevenLabs is unavailable — Flutter
    then uses its local flutter_tts as backup (robotic but works).

    Models:
      eleven_turbo_v2_5  — fastest, good quality, cheapest (use this)
      eleven_multilingual_v2 — best quality, supports Hindi, slower
    """
    if not ELEVENLABS_API_KEY:
        logger.info("No ElevenLabs key — Flutter will use local TTS")
        return {"audio_base64": None, "provider": "none"}

    voice = voice_id or VOICE_ID

    try:
        client = _get_eleven_client()
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            json={
                "text": text,
                "model_id": model,
                "voice_settings": {
                    "stability": 0.6,        # slightly less stable = more natural
                    "similarity_boost": 0.75, # stay close to the voice but not robotic
                    "style": 0.3,             # some expressiveness
                    "use_speaker_boost": True, # clearer audio
                },
            },
            headers={
                "Accept": "audio/mpeg",
            },
        )
        resp.raise_for_status()

        # ElevenLabs returns raw audio bytes — encode to base64
        # so we can send it as JSON to the Flutter app
        audio_b64 = base64.b64encode(resp.content).decode()

        logger.info(f"ElevenLabs TTS generated: {len(resp.content)} bytes, voice={voice}")
        return {
            "audio_base64": audio_b64,
            "content_type": "audio/mpeg",
            "provider": "elevenlabs",
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error("ElevenLabs API key invalid")
        elif e.response.status_code == 429:
            logger.warning("ElevenLabs rate limit hit — Flutter will use local TTS")
        else:
            logger.warning(f"ElevenLabs error {e.response.status_code}: {e}")
        return {"audio_base64": None, "provider": "none"}

    except Exception as e:
        logger.warning(f"ElevenLabs TTS failed: {e}")
        return {"audio_base64": None, "provider": "none"}


async def text_to_speech_stream(
    text: str,
    voice_id: str = None,
    model: str = "eleven_turbo_v2_5",
):
    """
    Streaming TTS — starts returning audio chunks before the full
    text is processed. Flutter can start playing audio ~200ms after
    the request instead of waiting for the full generation.

    Yields raw audio bytes chunks.
    """
    if not ELEVENLABS_API_KEY:
        return

    voice = voice_id or VOICE_ID

    try:
        client = _get_eleven_client()
        async with client.stream(
            "POST",
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream",
            json={
                "text": text,
                "model_id": model,
                "voice_settings": {
                    "stability": 0.6,
                    "similarity_boost": 0.75,
                    "style": 0.3,
                    "use_speaker_boost": True,
                },
            },
            headers={"Accept": "audio/mpeg"},
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(chunk_size=4096):
                yield chunk

    except Exception as e:
        logger.warning(f"ElevenLabs streaming TTS failed: {e}")