"""Check that the API keys in .env work. Run from the repo root:

    python backend/scripts/check_keys.py

Prints one line per service. Never prints the keys themselves.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings  # noqa: E402
from app.integrations import gemini, places, tavily  # noqa: E402


async def main() -> None:
    print("Gemini :", end=" ", flush=True)
    if not gemini.is_configured():
        print("no GEMINI_API_KEY")
    else:
        try:
            out = await gemini.generate_json('Return {"ok": true} as JSON.', temperature=0)
            print(f"OK (auth: {gemini._auth_mode or 'interactions'}) ->", out)
        except gemini.GeminiError as e:
            print("FAILED:", e)

    print("Tavily :", end=" ", flush=True)
    if not tavily.is_configured():
        print("no TAVILY_API_KEY")
    else:
        try:
            r = await tavily.search("Goa travel scams", max_results=2)
            print(f"OK, {len(r)} results")
        except tavily.TavilyError as e:
            print("FAILED:", e)

    print("Nuitee :", end=" ", flush=True)
    if not settings.NUITEE_API_KEY:
        print("no NUITEE_API_KEY")
    else:
        airports = await places._load_airports()
        print(f"OK, {len(airports)} airports" if airports else "FAILED: could not load /data/iataCodes")

    print("Places :", end=" ", flush=True)
    try:
        for q in ("Hyderabad", "Goa", "Coorg"):
            hit = (await places.search_places(q, count=1, prefer="IN") or [None])[0]
            if hit:
                ap = (hit.get("airport") or {}).get("code") or "no airport"
                print(f"{q} -> {hit['city']}, {hit.get('country_code')} ({hit.get('kind')}, {ap})", end="; ")
            else:
                print(f"{q} -> not found", end="; ")
        print()
    except places.PlacesError as e:
        print("FAILED:", e)


if __name__ == "__main__":
    asyncio.run(main())
