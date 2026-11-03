"""Minimal async client for the Groq API (OpenAI-compatible chat completions, JSON responses only).

Groq is the first choice for the language-model calls in this app; Gemini is the fallback
(see app/integrations/llm.py). Callers validate everything it returns, as they do for Gemini.
"""
import asyncio
import logging
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.integrations.gemini import _extract_json  # same tolerant JSON parsing as Gemini
from app.integrations.llm_errors import LLMError

logger = logging.getLogger(__name__)

BASE_URL = "https://api.groq.com/openai/v1"
TRANSIENT = {500, 502, 503, 504}
RETRY_DELAYS = (1.0, 2.5)


class GroqError(LLMError):
    """Raised when Groq is not configured, unreachable, or returns unusable output."""


def is_configured() -> bool:
    return bool(settings.GROQ_API_KEY.strip())


async def generate_json(prompt: str, *, system: Optional[str] = None, temperature: float = 0.2,
                        timeout: float = 60.0) -> Any:
    if not is_configured():
        raise GroqError("GROQ_API_KEY is not set in .env.")
    messages = []
    # JSON mode requires the word "JSON" to appear in the messages.
    messages.append({"role": "system", "content": ((system + "\n\n") if system else "")
                     + "Respond with a single valid JSON object only."})
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    headers = {"authorization": f"Bearer {settings.GROQ_API_KEY.strip()}", "content-type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = None
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                resp = await client.post(f"{BASE_URL}/chat/completions", json=body, headers=headers)
            except httpx.HTTPError as e:
                raise GroqError(f"Could not reach Groq: {e}") from e
            if resp.status_code not in TRANSIENT and resp.status_code != 429:
                break
            if attempt == len(RETRY_DELAYS):
                break
            logger.warning("Groq busy (HTTP %s), retrying", resp.status_code)
            await asyncio.sleep(RETRY_DELAYS[attempt])

    assert resp is not None
    if resp.status_code == 401:
        raise GroqError("Groq rejected the API key (HTTP 401). Check GROQ_API_KEY in .env.")
    if resp.status_code != 200:
        raise GroqError(f"Groq returned HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        text = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise GroqError(f"Groq returned an unexpected response: {e}") from e
    if not text:
        raise GroqError("Groq returned no text.")
    try:
        return _extract_json(text)
    except ValueError as e:  # json.JSONDecodeError is a ValueError
        raise GroqError(f"Groq did not return valid JSON: {e}") from e
