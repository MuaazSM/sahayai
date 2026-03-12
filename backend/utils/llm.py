import os
import json
import logging
import httpx

logger = logging.getLogger("sahayai.llm")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

TIMEOUT = httpx.Timeout(20.0, connect=5.0)

# =====================================================
# PERSISTENT HTTP CLIENTS
# Creating a new httpx client per request is slow — TCP handshake,
# TLS negotiation, connection setup each time. Instead we keep
# persistent clients that reuse connections across calls.
# This alone saves ~200ms per LLM call.
# =====================================================
_groq_client: httpx.AsyncClient | None = None
_gemini_client: httpx.AsyncClient | None = None
_openai_client: httpx.AsyncClient | None = None


def _get_groq_client() -> httpx.AsyncClient:
    global _groq_client
    if _groq_client is None or _groq_client.is_closed:
        _groq_client = httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            http2=True,  # HTTP/2 multiplexing — multiple requests over one connection
        )
    return _groq_client


def _get_gemini_client() -> httpx.AsyncClient:
    global _gemini_client
    if _gemini_client is None or _gemini_client.is_closed:
        _gemini_client = httpx.AsyncClient(
            timeout=TIMEOUT,
            http2=True,
        )
    return _gemini_client


def _get_openai_client() -> httpx.AsyncClient:
    global _openai_client
    if _openai_client is None or _openai_client.is_closed:
        _openai_client = httpx.AsyncClient(
            timeout=TIMEOUT,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            http2=True,
        )
    return _openai_client


async def close_llm_clients():
    """Called on server shutdown to close persistent connections cleanly"""
    global _groq_client, _gemini_client, _openai_client
    for client in [_groq_client, _gemini_client, _openai_client]:
        if client and not client.is_closed:
            await client.aclose()
    logger.info("LLM HTTP clients closed")


# =====================================================
# TEXT COMPLETIONS
# =====================================================

async def chat_completion(
    messages: list[dict],
    model_preference: str = "fast",
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    groq_models = {
        "fast": "llama-3.1-8b-instant",
        "quality": "llama-3.3-70b-versatile",
        "thinking": "deepseek-r1-distill-llama-70b",
        "structured": "qwen/qwen3-32b",
    }

    # --- Groq (free, fastest) ---
    if GROQ_API_KEY:
        try:
            model = groq_models.get(model_preference, "llama-3.3-70b-versatile")
            result = await _groq_chat(messages, model, temperature, max_tokens)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Groq failed: {e}")

    # --- Gemini (free fallback) ---
    if GEMINI_API_KEY:
        try:
            result = await _gemini_chat(messages, temperature, max_tokens)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Gemini failed: {e}")

    # --- OpenAI (paid last resort) ---
    if OPENAI_API_KEY:
        try:
            result = await _openai_chat(messages, "gpt-4o-mini", temperature, max_tokens)
            if result:
                return result
        except Exception as e:
            logger.warning(f"OpenAI failed: {e}")

    return "I'm having trouble responding right now. Please try again in a moment."


# =====================================================
# VISION COMPLETIONS
# =====================================================

async def vision_completion(
    base64_image: str,
    prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    if GROQ_API_KEY:
        try:
            result = await _groq_vision(base64_image, prompt, temperature, max_tokens)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Groq vision failed: {e}")

    if GEMINI_API_KEY:
        try:
            result = await _gemini_vision(base64_image, prompt, temperature, max_tokens)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Gemini vision failed: {e}")

    if OPENAI_API_KEY:
        try:
            result = await _openai_vision(base64_image, prompt, "gpt-4o-mini", temperature, max_tokens)
            if result:
                return result
        except Exception as e:
            logger.warning(f"OpenAI vision failed: {e}")

    return "I couldn't analyze the scene right now. Please try again."


# =====================================================
# PROVIDER IMPLEMENTATIONS — now using persistent clients
# =====================================================

async def _groq_chat(messages, model, temperature, max_tokens) -> str | None:
    client = _get_groq_client()
    resp = await client.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _groq_vision(base64_image, prompt, temperature, max_tokens) -> str | None:
    client = _get_groq_client()
    resp = await client.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json={
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _gemini_chat(messages, temperature, max_tokens) -> str | None:
    client = _get_gemini_client()
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    resp = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
        json={
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        },
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _gemini_vision(base64_image, prompt, temperature, max_tokens) -> str | None:
    client = _get_gemini_client()
    resp = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
        json={
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}},
                ],
            }],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        },
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


async def _openai_chat(messages, model, temperature, max_tokens) -> str | None:
    client = _get_openai_client()
    resp = await client.post(
        "https://api.openai.com/v1/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def _openai_vision(base64_image, prompt, model, temperature, max_tokens) -> str | None:
    client = _get_openai_client()
    resp = await client.post(
        "https://api.openai.com/v1/chat/completions",
        json={
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]