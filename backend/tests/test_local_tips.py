"""Local tips: Tavily results + Gemini summary, with citation checks (network mocked)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.agents.insights import service
from app.core.config import settings
from app.integrations import tavily

PAGES = {
    "scams": [{"title": "Jaipur scams thread", "url": "https://www.reddit.com/r/india/jaipur_scams", "content": "Gem shop scam: rickshaw drivers take you to gem shops...", "score": 0.9}],
    "reddit": [{"title": "Tips for Jaipur", "url": "https://www.reddit.com/r/travel/jaipur_tips", "content": "Use the metered or app cabs from the railway station...", "score": 0.8},
               {"title": "Jaipur scams thread", "url": "https://www.reddit.com/r/india/jaipur_scams", "content": "duplicate", "score": 0.7}],
    "know": [{"title": "Know before you go", "url": "https://example-travel.com/jaipur", "content": "Amber Fort is busiest after 10am; go early.", "score": 0.6}],
}


@pytest.fixture(autouse=True)
def clear_cache():
    service._cache.clear()
    yield
    service._cache.clear()


async def fake_search(query, max_results=6, include_domains=None, **kw):
    if include_domains == ["reddit.com"]:
        return PAGES["reddit"]
    return PAGES["scams"] if "scams" in query else PAGES["know"]


@pytest.mark.asyncio
async def test_tips_keep_only_cited_and_dedupe_sources(monkeypatch):
    monkeypatch.setattr(service.tavily, "search", fake_search)
    monkeypatch.setattr(service.gemini, "is_configured", lambda: True)

    async def fake_gen(prompt, **kw):
        assert "[1] Jaipur scams thread" in prompt and "Gem shop scam" in prompt
        return {"summary": "Mostly friendly, watch out for gem shop detours.", "tips": [
            {"category": "scams", "title": "Skip the gem shop detour", "advice": "Drivers earn commission.", "sources": [1]},
            {"category": "getting_around", "title": "Use app cabs at the station", "advice": "Avoid touts.", "sources": [2, 2]},
            {"category": "timing", "title": "Invented tip", "advice": "No source.", "sources": []},
            {"category": "weird", "title": "Out of range", "advice": "Bad ref.", "sources": [99]},
        ]}

    monkeypatch.setattr(service.gemini, "generate_json", fake_gen)
    r = await service.local_tips("Jaipur", "India")
    assert len(r["sources"]) == 3                                   # duplicate URL removed
    assert [t["title"] for t in r["tips"]] == ["Skip the gem shop detour", "Use app cabs at the station"]
    assert r["tips"][0]["sources"][0]["domain"] == "reddit.com"
    assert len(r["tips"][1]["sources"]) == 1                         # repeated citation collapsed
    assert any("didn't cite" in l for l in r["limitations"])
    assert r["method"] == "Tavily web search + Gemini summary"


@pytest.mark.asyncio
async def test_without_gemini_returns_sources(monkeypatch):
    monkeypatch.setattr(service.tavily, "search", fake_search)
    monkeypatch.setattr(service.gemini, "is_configured", lambda: False)
    r = await service.local_tips("Jaipur", "India")
    assert r["tips"] == [] and len(r["sources"]) == 3
    assert any("GEMINI_API_KEY" in l for l in r["limitations"])


@pytest.mark.asyncio
async def test_tavily_client_sends_key_and_parses(monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly-test")

    async def fake_post(self, url, json=None, headers=None):
        assert headers["Authorization"] == "Bearer tvly-test" and json["include_domains"] == ["reddit.com"]
        return httpx.Response(200, json={"results": [{"title": "T", "url": "https://reddit.com/x", "content": "c", "score": 1}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    out = await tavily.search("q", include_domains=["reddit.com"])
    assert out == [{"title": "T", "url": "https://reddit.com/x", "content": "c", "score": 1}]


def test_endpoint_without_tavily_key_is_503(monkeypatch):
    from app.main import app
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    r = TestClient(app).post("/api/v1/insights/local-tips", json={"city": "Jaipur", "country": "India"})
    assert r.status_code == 503 and "TAVILY_API_KEY" in r.json()["detail"]
