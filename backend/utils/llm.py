import os
import json
import base64
import logging
import httpx

logger = logging.getLogger("sahayai.llm")

# -----------------------------------------------------------------------
# LLM client helper — tries Groq free → Gemini free → OpenAI paid
# Every function in this file follows the same fallback chain so we
# never pay a cent unless both free tiers are down or rate-limited.
# -----------------------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Timeouts — Groq is fast (~1s), Gemini is decent (~3s), OpenAI varies
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# =====================================================
# TEXT COMPLETIONS (no vision)
# Used by: Reasoning Agent, Assistance Agent, Caregiver Agent, CCT
# =====================================================

async def chat_completion(
    messages: list[dict],
    model_preference: str = "fast",  # "fast" = 8b for speed, "quality" = 70b for reasoning
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """
    Send a chat completion request. Tries Groq first, then Gemini, then OpenAI.
    model_preference controls which Groq model we pick:
      - "fast" → llama-3.1-8b-instant (user-facing, lowest latency)
      - "quality" → llama-3.3-70b-versatile (reasoning, summaries)
      - "thinking" → deepseek-r1-distill-llama-70b (complex reasoning)
      - "structured" → qwen/qwen3-32b (JSON output, CCT scoring)
    """

    groq_models = {
        "fast": "llama-3.1-8b-instant",
        "quality": "llama-3.3-70b-versatile",
        "thinking": "deepseek-r1-distill-llama-70b",
        "structured": "qwen/qwen3-32b",
    }

    # --- Attempt 1: Groq (free, fastest) ---
    if GROQ_API_KEY:
        try:
            model = groq_models.get(model_preference, "llama-3.3-70b-versatile")
            result = await _groq_chat(messages, model, temperature, max_tokens)
            if result:
                logger.info(f"Groq [{model}] responded")
                return result
        except Exception as e:
            logger.warning(f"Groq failed: {e}")

    # --- Attempt 2: Gemini (free fallback) ---
    if GEMINI_API_KEY:
        try:
            result = await _gemini_chat(messages, temperature, max_tokens)
            if result:
                logger.info("Gemini [flash] responded")
                return result
        except Exception as e:
            logger.warning(f"Gemini failed: {e}")

    # --- Attempt 3: OpenAI (paid, last resort) ---
    if OPENAI_API_KEY:
        try:
            result = await _openai_chat(messages, "gpt-4o-mini", temperature, max_tokens)
            if result:
                logger.info("OpenAI [gpt-4o-mini] responded (paid!)")
                return result
        except Exception as e:
            logger.warning(f"OpenAI failed: {e}")

    logger.error("All LLM providers failed!")
    return "I'm having trouble responding right now. Please try again in a moment."


# =====================================================
# VISION COMPLETIONS (image + text)
# Used by: Perception Agent for /analyze-scene
# =====================================================

async def vision_completion(
    base64_image: str,
    prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """
    Send an image to a vision model and get back text.
    Tries Groq (llama-4-scout) → Gemini Flash → OpenAI GPT-4o-mini.
    """

    # --- Attempt 1: Groq vision (free, llama-4-scout is multimodal) ---
    if GROQ_API_KEY:
        try:
            result = await _groq_vision(base64_image, prompt, temperature, max_tokens)
            if result:
                logger.info("Groq [llama-4-scout] vision responded")
                return result
        except Exception as e:
            logger.warning(f"Groq vision failed: {e}")

    # --- Attempt 2: Gemini Flash vision (free) ---
    if GEMINI_API_KEY:
        try:
            result = await _gemini_vision(base64_image, prompt, temperature, max_tokens)
            if result:
                logger.info("Gemini [flash] vision responded")
                return result
        except Exception as e:
            logger.warning(f"Gemini vision failed: {e}")

    # --- Attempt 3: OpenAI (paid) ---
    if OPENAI_API_KEY:
        try:
            result = await _openai_vision(base64_image, prompt, "gpt-4o-mini", temperature, max_tokens)
            if result:
                logger.info("OpenAI [gpt-4o-mini] vision responded (paid!)")
                return result
        except Exception as e:
            logger.warning(f"OpenAI vision failed: {e}")

    logger.error("All vision providers failed!")
    return "I couldn't analyze the scene right now. Please try again."


# =====================================================
# PROVIDER IMPLEMENTATIONS
# =====================================================

async def _groq_chat(messages, model, temperature, max_tokens) -> str | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _groq_vision(base64_image, prompt, temperature, max_tokens) -> str | None:
    # Groq's llama-4-scout supports images via the OpenAI-compatible format
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _gemini_chat(messages, temperature, max_tokens) -> str | None:
    # Gemini uses a different API format — convert from OpenAI-style messages
    # to Gemini's contents format
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def _gemini_vision(base64_image, prompt, temperature, max_tokens) -> str | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": base64_image,
                                },
                            },
                        ],
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


async def _openai_chat(messages, model, temperature, max_tokens) -> str | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _openai_vision(base64_image, prompt, model, temperature, max_tokens) -> str | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
