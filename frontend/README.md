# Planless (web)

*Travel more. Plan less.*

React + Vite + TypeScript client for the TripPlanner backend. Mobile first; from 1080px wide it switches to a two-column desktop layout.

## Run it

```bash
# 1. backend (from the repo root)
uvicorn app.main:app --app-dir backend --reload        # http://127.0.0.1:8000

# 2. frontend
cd frontend
npm install
npm run dev                                            # http://127.0.0.1:5173
```

In development, Vite forwards every request under `/__backend` to FastAPI, so the browser never deals with CORS. If uvicorn runs on another port, set `BACKEND_URL` in `frontend/.env` (see `.env.example`). For a production build served separately from the API, set `VITE_API_BASE` to the API origin and run `npm run build`.

## What it does

The app runs the agents in the order the TDD gives the orchestrator. Until the LangGraph orchestrator exists, the client does this sequencing itself:

1. **Flights out and back + itinerary, in parallel.** `POST /api/v1/travel/search` (one call per leg) and `POST /api/v1/itinerary/plan`.
2. **Stays after the itinerary.** `POST /api/v1/hotel/search`, with the planned stops passed as `reference_points`, so hotels are ranked by distance to where you'll actually go.
3. **Selections trigger targeted revision.** Choosing both flight legs or a stay calls `POST /api/v1/itinerary/revise`. The UI shows which days were rebuilt (`revised_days`).

The client does no maths beyond adding the API's own prices into a trip total. Every time, distance, score, warning and status shown comes from the backend. The **Checks** tab shows exactly why a plan is `provisional` and what would make it `validated`.

Without a `NUITEE_API_KEY`, flights come back empty, the hotel search reports the missing key, and the itinerary uses the backend's offline demo activities. The UI labels each of these as such.

## Structure

```
src/
├── api/          types.ts (mirrors the Pydantic schemas), client.ts (fetch wrapper)
├── data/         places.ts (city coordinates, time zones, airport codes)
├── lib/          trip.ts (request builders + orchestration), format.ts
├── components/   Composer, PlanningBoard, Trip, Itinerary, RouteMap, Flights, Stays, Checks, ui
└── styles.css    design tokens and all component styles
```

To add a destination, add a row to `src/data/places.ts`.
