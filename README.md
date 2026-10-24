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

### 4. Running the FastAPI Server (Interactive Swagger UI)

To test the Travel Agent over HTTP:

```powershell
uvicorn app.main:app --app-dir backend --reload
```

Open your browser to:
- **Swagger Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

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
│   │   │   └── itinerary.py          # /itinerary API routes
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
│       └── test_itinerary_agent.py   # Itinerary Agent unit tests
└── scripts/
    └── test_flight_search.py         # Live search verification script
```
