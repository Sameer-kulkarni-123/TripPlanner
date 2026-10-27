# AI Trip Planning Agent

An intelligent, multi-agent trip-planning application built with FastAPI, LangGraph, and Nuitee / LiteAPI travel integrations.

---

## Quick Start & Running Tests

### 1. Prerequisites & Environment Setup

Ensure the virtual environment is set up and your dependencies are installed:

```powershell
# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

Make sure your [`.env`](file:///c:/Users/Sameer/MyProjects/TripPlanner/.env) file exists in the root directory and contains your Nuitee API key:

```env
NUITEE_API_KEY=YOUR_API_KEY
NUITEE_API_BASE_URL=https://api.liteapi.travel/v3.0
```

---

### 2. Running Unit Tests with Pytest

To run the automated test suite (validates deterministic ranking, journey duration calculations, and constraint filtering):

```powershell
# Run all unit tests
pytest

# Run with verbose test details
pytest -v
```

---

### 3. Running Live Flight Search (`test_flight_search.py`)

To verify live flight fetching and ranking directly against the Nuitee / LiteAPI endpoint:

```powershell
# From the project root directory:
python .\scripts\test_flight_search.py
```

**What this script does:**
1. Loads credentials from `.env`
2. Formats a legs-based search request compliant with LiteAPI (`JFK` $\rightarrow$ `LHR` 30 days ahead).
3. Queries LiteAPI `/flights/rates`.
4. Normalizes segments, pricing, and baggage allowances into `TransportOption` models.
5. Deterministically ranks the options using $S = w_c C + w_t T + w_x X + w_p P$ and displays the scored results.

---

### 3b. Running Live Hotel Search (`test_hotel_search.py`)

```powershell
python .\scripts\test_hotel_search.py
```

Searches Paris hotels 30 days ahead via LiteAPI (`GET /data/hotels` for property content, then
`POST /hotels/rates`), normalizes results into `HotelOption` models, applies hard constraints, and ranks
them deterministically. Prices are **total stay for all rooms**; fees payable at the property are reported
separately and included in `all_in_price`.

---

### 4. Running the FastAPI Server (Interactive Swagger UI)

To test the agents over HTTP:

```powershell
uvicorn app.main:app --app-dir backend --reload
```

Open your browser to:
- **Swagger Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

### 5. Running the Web Frontend

With the API running (step 4), in a second terminal:

```bash
cd frontend
npm install
npm run dev          # http://127.0.0.1:5173
```

Mobile-first React + Vite + TypeScript client that calls the real endpoints: flights and itinerary in parallel, then hotels ranked against the planned stops, and `/itinerary/revise` when you pick flights or a stay. See [`frontend/README.md`](frontend/README.md).

---

## Gemini, any-city search and the landing page

- **Describe your trip** (`POST /api/v1/assistant/trip-draft`): Gemini extracts destination, dates, travellers, interests and pace from free text. Code then checks the dates and numbers, finds the places on the map and lists anything missing. The form is filled in for review before planning.
- **Any city** (`GET /api/v1/places/search?q=Mysuru`): coordinates and time zone from the Open-Meteo geocoding API (GeoNames, no key needed), plus the nearest airport from LiteAPI's IATA list. Places with no airport within 250 km skip flight search.
- **Activities when Nuitee has none**: discovery order is live Nuitee experiences, then Gemini suggestions, then offline demo data. Gemini suggestions are validated (far-away or malformed items dropped), tagged "AI suggestion", and keep the plan `provisional`.

- **Local tips** (`POST /api/v1/insights/local-tips`): Tavily web search runs three queries (scams, advice from locals on reddit.com, things to know), Gemini turns the pages into short tips, and code keeps only tips that cite a page that was actually retrieved. Shown in the **Tips** tab, each tip linked to its sources.

Setup: put `GEMINI_API_KEY=...` and `TAVILY_API_KEY=...` in `.env` and restart uvicorn. Without it, everything else still works and the app says what's missing.

---

### Place search, regions and airports

- Place search covers cities **and** states/regions. "Goa" resolves to the Indian state (based around Panaji, flying into GOI) instead of a small namesake abroad; results in the traveller's own country rank higher.
- The airport is chosen by distance, but international airports get a head start and fields without airline service are pushed back, so Hyderabad uses HYD, not Begumpet (BPM).
- If the geocoder finds nothing (nicknames like "Coorg"), Gemini suggests what was meant and each suggestion is kept only if the geocoder confirms a real place near it.

### Checking your API keys

```bash
python backend/scripts/check_keys.py
```

Prints one line each for Gemini, Tavily, Nuitee and place search (never the keys). Newer Gemini keys that start with `AQ.` are tried with the header, query-string and bearer styles, then the Interactions API.

## Itinerary Agent

Implements Section 7 of the TDD: discovers experiences, filters them against hard constraints, scores them, builds a day-by-day schedule and validates it in code.

**Pipeline** (`backend/app/agents/itinerary/`)

1. **Discovery** (`providers/experiences_nuitee.py`) - Nuitee / LiteAPI `GET /experiences/tours` (radius search when coordinates are given, otherwise `textSearch`), then `GET /experiences/tours/{id}/availability` for the top candidates. Without `NUITEE_API_KEY`, and with `ITINERARY_DEMO_MODE=true`, an offline demo provider is used; every demo activity is flagged.
2. **Filtering & scoring** (`calculations/filtering.py`) - avoid-list, wheelchair needs, child age limits, max price per activity, max duration, date availability, de-duplication; deterministic relevance score (interest match, rating, price, data completeness).
3. **Scheduling** (`calculations/scheduling.py`) - per-day windows after arrival (+120 min) and departure (-180 min) buffers; pace sets activities per day (relaxed 2 / moderate 3 / packed 4); geographically tight grouping; tries every visiting order to minimise travel and idle time; respects opening hours; inserts lunch, dinner and rest blocks; travel times estimated via haversine (walk <=1.2 km, otherwise transit) and marked as estimates.
4. **Validation** (`calculations/validation.py`) - overlaps, travel buffers, trip boundaries, duplicates, opening-hour conflicts, availability, budget, unknown price/hours/accessibility. Plans are `validated` only when transport and hotel are confirmed and there are no errors; otherwise `provisional`.
5. **Targeted revision** (`services/planner.py`) - when arrival/departure changes, only the affected days are rebuilt; preference/date/hotel-location changes trigger a full rebuild.

**Endpoints** (see `/docs`, the example body is prefilled)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/itinerary/activities` | Discover + filter + rank activities |
| POST | `/api/v1/itinerary/plan` | Build a day-by-day itinerary |
| POST | `/api/v1/itinerary/revise` | Revise only the affected days |

**Orchestrator hooks** - `ItineraryAgent.execute(dict)`, `ItineraryAgent.execute_from_state(TripState)` (returns a partial state update), `ItineraryAgent.revise(dict)`, and LangChain tools `search_activities` / `plan_itinerary`.

**Tests** - `pytest backend/tests/test_itinerary_agent.py -v`

---

## Hotel Agent

Implements Section 8 of the TDD: searches Nuitee hotels, normalizes property + room/rate options, filters hard constraints, ranks deterministically, and reports why options are missing instead of relaxing constraints.

**Pipeline** (`backend/app/agents/hotel/`)

1. **Validate stay** (`validation/stay.py`) - dates, nights (<= 30), rooms (<= 5), horizon, currency.
2. **Search** (`providers/hotel_nuitee.py`) - `GET /data/hotels` for property content, then `POST /hotels/rates` (falls back to city search). Provider failures raise and are reported, never shown as "no hotels".
3. **Normalize & price** (`calculations/pricing.py`) - total stay for all rooms, per-night price, taxes/fees split into included vs payable at property, `all_in_price`.
4. **Validate options** (`validation/results.py`) - currency, dates, nights, room count.
5. **Hard constraints** (`services/search.py`) - max total / per-night price (all-in when known), min stars, refundable only, board type, occupancy, max distance, amenities/accessibility (kept but flagged when the provider gives no amenity data). Removed counts are returned in `rejected_counts`.
6. **Ranking** (`calculations/ranking.py`) - `S = w_c C + w_q Q + w_l L + w_f F` (cost, stars, distance to reference points, cancellation/meal fit); components with no data are dropped and weights re-normalized.

**Endpoint**: `POST /api/v1/hotel/search`

**Orchestrator hooks** - `HotelAgent.execute(dict)`, `HotelAgent.rerank(dict)` (re-rank by itinerary locations without a new search), LangChain tool `search_hotels`.

**Tests** - `pytest backend/tests/test_hotel_agent.py -v`

---

## Project Structure

```
TripPlanner/
├── .env                              # Environment configuration (ignored by git)
├── .env.example                      # Template for environment variables
├── pyproject.toml                    # Build config and pytest settings
├── requirements.txt                  # Python dependencies
├── nuitee_flights_search_api_documentation.md # LiteAPI documentation
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI application entrypoint
│   │   ├── core/
│   │   │   └── config.py             # App settings & credentials
│   │   ├── api/
│   │   │   ├── travel.py             # /travel API routes
│   │   │   ├── itinerary.py          # /itinerary API routes
│   │   │   └── hotel.py              # /hotel API routes
│   │   ├── orchestrator/
│   │   │   └── state.py              # LangGraph shared TripState
│   │   └── agents/
│   │       ├── itinerary/            # Itinerary Agent Specialist
│   │       │   ├── agent.py          # Agent + TripState mapping
│   │       │   ├── schemas.py        # Request / activity / schedule models
│   │       │   ├── tools.py          # LangChain tools
│   │       │   ├── services/planner.py      # discover -> filter -> schedule -> validate -> revise
│   │       │   ├── providers/        # Nuitee experiences adapter + demo provider
│   │       │   └── calculations/     # geo, filtering, scheduling, validation
│   │       ├── hotel/                # Hotel Agent Specialist
│   │       │   ├── agent.py          # Agent logic (execute / rerank)
│   │       │   ├── schemas.py        # Stay request / HotelOption models
│   │       │   ├── tools.py          # LangChain tool search_hotels
│   │       │   ├── services/search.py        # fan-out, validation, hard constraints, ranking
│   │       │   ├── providers/        # Nuitee hotels adapter
│   │       │   ├── calculations/     # pricing, distance, ranking
│   │       │   └── validation/       # stay + result checks
│   │       └── travel/               # Travel Agent Specialist
│   │           ├── agent.py          # Agent logic
│   │           ├── schemas.py        # Pydantic data models
│   │           ├── tools.py          # LangChain / LangGraph callable tools
│   │           ├── services/
│   │           │   └── search.py     # Aggregation & constraint filtering
│   │           ├── providers/
│   │           │   ├── base.py       # Base provider adapter
│   │           │   └── flight_nuitee.py # Nuitee / LiteAPI adapter
│   │           └── calculations/
│   │               └── ranking.py    # Deterministic multi-factor scoring
│   └── tests/
│       ├── test_travel_agent.py      # Travel Agent unit tests
│       ├── test_itinerary_agent.py   # Itinerary Agent unit tests
│       └── test_hotel_agent.py       # Hotel Agent unit tests
└── scripts/
    ├── test_flight_search.py         # Live flight search verification script
    └── test_hotel_search.py          # Live hotel search verification script
```

## Deploying to Render

The repo ships a Render Blueprint (`render.yaml`) that creates two services:

| Service | Type | What it runs |
|---|---|---|
| `planless-api` | Python web service (free) | `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT` |
| `planless-web` | Static site | `npm ci && npm run build` in `frontend/`, publishes `frontend/dist` |

1. Push this branch to GitHub (the Blueprint currently deploys `feature/itinerary-agent`; switch the two `branch:` lines to `main` after merging).
2. In Render: **New → Blueprint**, connect `Sameer-kulkarni-123/TripPlanner`, and pick the branch that contains `render.yaml`.
3. When prompted, paste the secrets: `NUITEE_API_KEY`, `GEMINI_API_KEY`, `TAVILY_API_KEY`. Click **Apply**.
4. Once `planless-api` is live, open its URL — `/` should return `{"status": "healthy", ...}` with the three `*_configured` flags `true`.
5. Check the API's public URL. If it isn't exactly `https://planless-api.onrender.com`, set `VITE_API_BASE` on `planless-web` to the real URL (Environment tab) and trigger **Manual Deploy → Clear build cache & deploy** (Vite bakes it in at build time).
6. Open the `planless-web` URL.

Notes: Python 3.11 is pinned via `.python-version` and `PYTHON_VERSION`; Node 22 via `NODE_VERSION`. The free API instance sleeps after ~15 min idle, so the first request can take ~50 s. Never commit `.env` or `api.env` — set keys only in the Render dashboard.
