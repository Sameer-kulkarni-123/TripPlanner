"""Local Insights: what travellers say about a place (scams, getting around, etiquette...).

1. Tavily web search runs a few focused queries, one of them limited to reddit.com.
2. Gemini summarises the results into short tips, and must cite the numbered sources it used.
3. Code drops any tip whose citations don't point to a page that was actually retrieved, so
   every tip shown links back to real pages. Without Gemini, the raw sources are returned.
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.integrations import gemini, tavily

logger = logging.getLogger(__name__)

CATEGORIES = {
    "scams": "Scams to avoid",
    "getting_around": "Getting around",
    "money": "Money and bargaining",
    "culture": "Culture and etiquette",
    "safety": "Safety",
    "food": "Food and drink",
    "timing": "When to go and crowds",
}
MAX_SOURCES = 16
MAX_TIPS = 14
CACHE_SECONDS = 6 * 3600
_cache: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}


def queries(city: str, country: str) -> List[Tuple[str, Optional[List[str]]]]:
    place = f"{city}, {country}" if country else city
    return [
        (f"{place} tourist scams to avoid", None),
        (f"{city} travel tips advice from locals", ["reddit.com"]),
        (f"{place} things to know before visiting, getting around, etiquette", None),
    ]


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


async def gather_sources(city: str, country: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    qs = queries(city, country)
    results = await asyncio.gather(*(tavily.search(q, max_results=6, include_domains=d) for q, d in qs),
                                   return_exceptions=True)
    sources: List[Dict[str, Any]] = []
    seen = set()
    notes: List[str] = []
    errors = [r for r in results if isinstance(r, Exception)]
    for r in results:
        if isinstance(r, Exception):
            continue
        for item in r:
            if item["url"] in seen or not item.get("content"):
                continue
            seen.add(item["url"])
            sources.append({**item, "domain": _domain(item["url"])})
    if errors and not sources:
        raise tavily.TavilyError(str(errors[0]))
    if errors:
        notes.append(f"{len(errors)} of {len(qs)} web searches failed: {errors[0]}")
    return sources[:MAX_SOURCES], notes


def _prompt(city: str, country: str, sources: List[Dict[str, Any]]) -> str:
    blocks = "\n\n".join(f"[{i + 1}] {s['title']} ({s['domain']})\n{s['content']}" for i, s in enumerate(sources))
    cats = ", ".join(f'"{k}"' for k in CATEGORIES)
    return f"""You are writing practical advice for a visitor to {city}{', ' + country if country else ''}.
Use ONLY the numbered web results below (forum posts, Reddit threads, travel sites). Do not add facts that are
not in them. Prefer specific, useful advice: named scams and how they work, what fair prices look like if a
source gives them, transport tips, etiquette, areas or times to avoid. Skip generic advice like "be careful".

{blocks}

Return JSON:
{{"summary": one sentence on the overall picture,
  "tips": [{{"category": one of [{cats}],
             "title": 3-8 words,
             "advice": 1-2 sentences,
             "sources": list of the result numbers that support it (at least one)}}]}}
Give at most {MAX_TIPS} tips, most useful first."""


def validate_tips(raw: Any, sources: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Optional[str], int]:
    """Keep only well-formed tips whose citations point at retrieved pages."""
    items = raw.get("tips") if isinstance(raw, dict) else None
    summary = raw.get("summary") if isinstance(raw, dict) and isinstance(raw.get("summary"), str) else None
    tips, dropped = [], 0
    for t in items if isinstance(items, list) else []:
        if not isinstance(t, dict):
            dropped += 1
            continue
        refs = [n for n in (t.get("sources") or []) if isinstance(n, int) and 1 <= n <= len(sources)]
        title, advice = str(t.get("title") or "").strip(), str(t.get("advice") or "").strip()
        if not refs or not title or not advice:
            dropped += 1
            continue
        cat = t.get("category") if t.get("category") in CATEGORIES else "culture"
        tips.append({
            "category": cat,
            "category_label": CATEGORIES[cat],
            "title": title[:90],
            "advice": advice[:400],
            "sources": [{"title": sources[n - 1]["title"], "url": sources[n - 1]["url"], "domain": sources[n - 1]["domain"]}
                        for n in dict.fromkeys(refs)],
        })
        if len(tips) >= MAX_TIPS:
            break
    return tips, (summary[:300] if summary else None), dropped


async def local_tips(city: str, country: str = "") -> Dict[str, Any]:
    key = (city.strip().lower(), country.strip().lower())
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]

    sources, limitations = await gather_sources(city, country)
    tips: List[Dict[str, Any]] = []
    summary = None
    if not sources:
        limitations.append(f"The web search found nothing useful about {city}.")
    elif gemini.is_configured():
        try:
            raw = await gemini.generate_json(_prompt(city, country, sources), temperature=0.1)
            tips, summary, dropped = validate_tips(raw, sources)
            if dropped:
                limitations.append(f"{dropped} suggested tip(s) were left out because they didn't cite a retrieved page.")
        except gemini.GeminiError as e:
            limitations.append(f"Couldn't summarise with Gemini ({e}); showing the pages found instead.")
    else:
        limitations.append("Add GEMINI_API_KEY to .env to turn these pages into short tips; showing the pages found instead.")

    result = {
        "destination": city,
        "summary": summary,
        "tips": tips,
        "sources": [{"title": s["title"], "url": s["url"], "domain": s["domain"], "snippet": s["content"][:280]}
                    for s in sources],
        "limitations": limitations,
        "method": "Tavily web search" + (" + Gemini summary" if tips else ""),
    }
    if tips or sources:
        _cache[key] = (time.time(), result)
    return result
