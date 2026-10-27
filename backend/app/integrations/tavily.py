"""Minimal async client for the Tavily web search API (https://docs.tavily.com)."""
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.tavily.com/search"


class TavilyError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.TAVILY_API_KEY.strip())


async def search(query: str, *, max_results: int = 6, include_domains: Optional[List[str]] = None,
                 search_depth: str = "basic", timeout: float = 25.0) -> List[Dict[str, Any]]:
    """Return [{title, url, content, score}] for a query. Raises TavilyError on failure."""
    if not is_configured():
        raise TavilyError("TAVILY_API_KEY is not set in .env.")
    key = settings.TAVILY_API_KEY.strip()
    body: Dict[str, Any] = {
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
        # Older API versions read the key from the body, newer ones from the header; send both.
        "api_key": key,
    }
    if include_domains:
        body["include_domains"] = include_domains
    headers = {"Authorization": f"Bearer {key}", "content-type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(SEARCH_URL, json=body, headers=headers)
    except httpx.HTTPError as e:
        raise TavilyError(f"Could not reach Tavily: {e}") from e
    if resp.status_code in (401, 403):
        raise TavilyError(f"Tavily rejected the API key (HTTP {resp.status_code}). Check TAVILY_API_KEY.")
    if resp.status_code == 429:
        raise TavilyError("Tavily rate limit or credit limit reached (HTTP 429).")
    if resp.status_code != 200:
        raise TavilyError(f"Tavily returned HTTP {resp.status_code}: {resp.text[:200]}")
    out = []
    for r in resp.json().get("results") or []:
        if isinstance(r, dict) and r.get("url"):
            out.append({
                "title": (r.get("title") or r["url"])[:200],
                "url": r["url"],
                "content": (r.get("content") or "")[:1200],
                "score": r.get("score"),
            })
    return out
