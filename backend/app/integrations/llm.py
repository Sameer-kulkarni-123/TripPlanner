"""Language-model router: tries providers in the order set by LLM_PROVIDER_ORDER (default: groq, then gemini).

Callers use only this module (`llm.is_configured()`, `llm.generate_json()`, `llm.LLMError`).
A provider that is not configured is skipped; a provider that fails (rate limit, outage, bad key,
bad JSON) hands over to the next one. Nothing else in the app needs to know which model answered.
"""
import logging
from typing import Any, List, Optional

from app.core.config import settings
from app.integrations import gemini, groq
from app.integrations.llm_errors import LLMError

logger = logging.getLogger(__name__)

__all__ = ["LLMError", "is_configured", "generate_json", "provider_order"]


def provider_order() -> List[str]:
    names = [n.strip().lower() for n in settings.LLM_PROVIDER_ORDER.split(",") if n.strip()]
    return list(dict.fromkeys(names))  # drop duplicates, keep order


def _providers():
    # Looked up at call time so tests can patch the provider modules.
    table = {"groq": groq, "gemini": gemini}
    return [(name, table[name]) for name in provider_order() if name in table]


def is_configured() -> bool:
    return any(mod.is_configured() for _, mod in _providers())


async def generate_json(prompt: str, *, system: Optional[str] = None, temperature: float = 0.2,
                        timeout: float = 60.0) -> Any:
    """JSON answer from the first provider that works. Raises LLMError if none does."""
    errors = []
    for name, mod in _providers():
        if not mod.is_configured():
            continue
        try:
            return await mod.generate_json(prompt, system=system, temperature=temperature, timeout=timeout)
        except LLMError as e:
            logger.warning("LLM provider %s failed, trying the next one: %s", name, e)
            errors.append(f"{name}: {e}")
    if not errors:
        raise LLMError("No language model is configured. Add GROQ_API_KEY and/or GEMINI_API_KEY to .env.")
    raise LLMError(" | ".join(errors))
