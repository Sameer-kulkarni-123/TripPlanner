"""Groq first, Gemini as fallback (app/integrations/llm.py)."""
import pytest

from app.core.config import settings
from app.integrations import gemini, groq, llm
from app.integrations.llm_errors import LLMError


@pytest.fixture
def providers(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER_ORDER", "groq,gemini")
    calls = []

    def make(name, configured, result=None, error=None):
        async def gen(prompt, **kw):
            calls.append(name)
            if error:
                raise LLMError(error)
            return result
        return gen

    return calls, make


@pytest.mark.asyncio
async def test_groq_answers_first_gemini_not_called(monkeypatch, providers):
    calls, make = providers
    monkeypatch.setattr(groq, "is_configured", lambda: True)
    monkeypatch.setattr(groq, "generate_json", make("groq", True, result={"from": "groq"}))
    monkeypatch.setattr(gemini, "is_configured", lambda: True)
    monkeypatch.setattr(gemini, "generate_json", make("gemini", True, result={"from": "gemini"}))

    assert await llm.generate_json("hi") == {"from": "groq"}
    assert calls == ["groq"]


@pytest.mark.asyncio
async def test_falls_back_to_gemini_when_groq_fails(monkeypatch, providers):
    calls, make = providers
    monkeypatch.setattr(groq, "is_configured", lambda: True)
    monkeypatch.setattr(groq, "generate_json", make("groq", True, error="rate limited"))
    monkeypatch.setattr(gemini, "is_configured", lambda: True)
    monkeypatch.setattr(gemini, "generate_json", make("gemini", True, result={"from": "gemini"}))

    assert await llm.generate_json("hi") == {"from": "gemini"}
    assert calls == ["groq", "gemini"]


@pytest.mark.asyncio
async def test_skips_unconfigured_groq(monkeypatch, providers):
    calls, make = providers
    monkeypatch.setattr(groq, "is_configured", lambda: False)
    monkeypatch.setattr(gemini, "is_configured", lambda: True)
    monkeypatch.setattr(gemini, "generate_json", make("gemini", True, result={"ok": 1}))

    assert await llm.generate_json("hi") == {"ok": 1}
    assert calls == ["gemini"]


@pytest.mark.asyncio
async def test_all_fail_reports_both(monkeypatch, providers):
    _, make = providers
    monkeypatch.setattr(groq, "is_configured", lambda: True)
    monkeypatch.setattr(groq, "generate_json", make("groq", True, error="groq down"))
    monkeypatch.setattr(gemini, "is_configured", lambda: True)
    monkeypatch.setattr(gemini, "generate_json", make("gemini", True, error="gemini down"))

    with pytest.raises(LLMError, match="groq down.*gemini down"):
        await llm.generate_json("hi")


def test_toggle_order_in_config(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER_ORDER", "gemini,groq")
    monkeypatch.setattr(groq, "is_configured", lambda: True)
    monkeypatch.setattr(gemini, "is_configured", lambda: True)
    assert llm.provider_order() == ["gemini", "groq"]
    assert [n for n, _ in llm._providers()] == ["gemini", "groq"]


def test_nothing_configured(monkeypatch):
    monkeypatch.setattr(groq, "is_configured", lambda: False)
    monkeypatch.setattr(gemini, "is_configured", lambda: False)
    assert llm.is_configured() is False
