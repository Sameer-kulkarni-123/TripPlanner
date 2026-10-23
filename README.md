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
uvicorn backend.app.main:app --reload
```

Open your browser to:
- **Swagger Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

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
│   │   │   └── travel.py             # /travel API routes
│   │   ├── orchestrator/
│   │   │   └── state.py              # LangGraph shared TripState
│   │   └── agents/
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
│       └── test_travel_agent.py      # Unit tests
└── scripts/
    └── test_flight_search.py         # Live search verification script
```
