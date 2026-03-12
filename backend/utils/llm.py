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


# ====================================================