"""Minimal async client for the Google Gemini API (JSON responses only).

Gemini is used where the TDD allows a language model: interpreting a free-text trip
request and suggesting activities when no live inventory is available. Everything it
returns is validated and flagged as an estimate by the calling code; nothing here is
trusted as a verified price, opening time or availability.
"""
import asyncio
import json
import logging
import re
from typing import Any, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
# Overloaded / temporary server errors: retry briefly, then try the next model.
TRANSIENT = {500, 502, 503, 504}
RETRY_DELAYS = (1.0, 2.5)


class GeminiError(Exception):
    """Raised when Gemini is not configured, unreachable, or returns unusable output."""


def is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY.strip())


def _models() -> List[str]:
    seen, out = set(), []
    for m in [settings.GEMINI_MODEL, *settings.GEMINI_FALLBACK_MODELS.split(",")]:
        m = m.strip()
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _extract_json(text: str) -> Any:
    """Parse JSON text, tolerating ```json fences or leading prose."""
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start = min([i for i in (t.find("{"), t.find("[")) if i >= 0], default=-1)
        if start >= 0:
            end = max(t.rfind("}"), t.rfind("]"))
            if end > start:
                return json.loads(t[start : end + 1])
        raise


def _response_text(payload: dict) -> Optional[str]:
    """Text of the first candidate in a generateContent response."""
    for cand in payload.get("candidates") or []:
        parts = ((cand or {}).get("content") or {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
        if texts:
            return "".join(texts)
    return None


_auth_mode: Optional[str] = None  # remembered after the first successful call


def _auth(mode: str, key: str):
    """Header, query or bearer. Newer 'AQ.' auth keys are rejected by some endpoints in some modes."""
    if mode == "query":
        return {"content-type": "application/json"}, {"key": key}
    if mode == "bearer":
        return {"content-type": "application/json", "authorization": f"Bearer {key}"}, {}
    return {"content-type": "application/json", "x-goog-api-key": key}, {}


def _find_text(obj: Any) -> Optional[str]:
    """First text field in an Interactions API response (shape varies by version)."""
    if isinstance(obj, dict):
        for k in ("output_text", "outputText", "text"):
            if isinstance(obj.get(k), str) and obj[k].strip():
                return obj[k]
        for v in obj.values():
            t = _find_text(v)
            if t:
                return t
    elif isinstance(obj, list):
        for v in obj:
            t = _find_text(v)
            if t:
                return t
    return None


async def generate_json(prompt: str, *, system: Optional[str] = None, temperature: float = 0.2,
                        timeout: float = 60.0) -> Any:
    """Ask Gemini for a JSON answer. Tries each configured model (and auth style) until one responds."""
    global _auth_mode
    if not is_configured():
        raise GeminiError("GEMINI_API_KEY is not set in .env.")
    key = settings.GEMINI_API_KEY.strip()

    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    modes = [_auth_mode] if _auth_mode else ["header", "query", "bearer"]
    last_error = "no model configured"
    busy = False
    async with httpx.AsyncClient(timeout=timeout) as client:
        for model in _models():
            url = f"{BASE_URL}/models/{model}:generateContent"
            resp = None
            for attempt in range(len(RETRY_DELAYS) + 1):
                for mode in modes:
                    headers, params = _auth(mode, key)
                    try:
                        resp = await client.post(url, json=body, headers=headers, params=params or None)
                    except httpx.HTTPError as e:
                        raise GeminiError(f"Could not reach Gemini: {e}") from e
                    if resp.status_code != 401:
                        if resp.status_code != 403:
                            _auth_mode = mode   # the key was accepted in this style
                        break
                if resp.status_code not in TRANSIENT or attempt == len(RETRY_DELAYS):
                    break
                logger.warning("Gemini %s busy (HTTP %s), retrying", model, resp.status_code)
                await asyncio.sleep(RETRY_DELAYS[attempt])
            assert resp is not None
            if resp.status_code in TRANSIENT or resp.status_code == 429:
                last_error = f"'{model}' is busy (HTTP {resp.status_code})"
                logger.warning("Gemini %s unavailable (HTTP %s), trying the next model", model, resp.status_code)
                busy = True
                continue
            if resp.status_code == 404:
                last_error = f"model '{model}' not found"
                logger.warning("Gemini model %s not available, trying the next one", model)
                continue
            if resp.status_code == 401:
                last_error = f"the key was refused (HTTP 401): {resp.text[:160]}"
                break  # try the Interactions API below
            if resp.status_code == 403:
                raise GeminiError("Gemini rejected the API key (HTTP 403). Check GEMINI_API_KEY and that the "
                                  "Generative Language API is enabled for its project.")
            if resp.status_code != 200:
                raise GeminiError(f"Gemini returned HTTP {resp.status_code}: {resp.text[:300]}")
            text = _response_text(resp.json())
            if not text:
                raise GeminiError("Gemini returned no text (the response may have been blocked).")
            try:
                return _extract_json(text)
            except (json.JSONDecodeError, ValueError) as e:
                raise GeminiError(f"Gemini did not return valid JSON: {e}") from e

        if busy:
            raise GeminiError("Gemini is overloaded right now (every configured model returned a busy error). "
                              "This is on Google's side and usually clears in a few minutes; try again shortly.")
        # Fallback: the newer Interactions API, which Google recommends for new keys.
        full = (system + "\n\n" if system else "") + prompt
        for model in _models():
            headers, _ = _auth("header", key)
            try:
                resp = await client.post(f"{BASE_URL}/interactions", headers=headers, json={
                    "model": model, "input": full,
                    "response_format": {"type": "text", "mime_type": "application/json"},
                })
            except httpx.HTTPError as e:
                raise GeminiError(f"Could not reach Gemini: {e}") from e
            if resp.status_code == 200:
                text = _find_text(resp.json())
                if text:
                    try:
                        return _extract_json(text)
                    except (json.JSONDecodeError, ValueError) as e:
                        raise GeminiError(f"Gemini did not return valid JSON: {e}") from e
            last_error = f"HTTP {resp.status_code} from the Interactions API: {resp.text[:160]}"
            if resp.status_code not in (400, 404):
                break
    raise GeminiError(f"No Gemini model responded ({last_error}). Check GEMINI_API_KEY and GEMINI_MODEL in .env.")
