import type {
  Health,
  LocalTips,
  PlaceResult,
  TripDraftResult,
  HotelSearchRequest,
  HotelSearchResult,
  ItineraryRequest,
  ItineraryResult,
  TravelSearchRequest,
  TravelSearchResult,
} from "./types";

/** Dev: "/__backend" (proxied by Vite). Production: set VITE_API_BASE to the FastAPI origin. */
const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") || "/__backend";
const V1 = `${BASE}/api/v1`;

export class ApiError extends Error {
  constructor(message: string, public status: number, public detail?: unknown) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI 422: [{loc, msg, type}]
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string }) =>
        `${(d.loc || []).filter((p) => p !== "body").join(".")}: ${d.msg ?? "invalid"}`)
      .join("; ");
  }
  return "Unexpected response";
}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) }, signal);
}

async function request<T>(path: string, init: RequestInit, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${V1}${path}`, {
      ...init,
      headers: { "content-type": "application/json", accept: "application/json" },
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(
      import.meta.env.VITE_API_BASE
        ? "Can't reach the Planless API. It may be waking up (free hosting sleeps when idle) — try again in a minute."
        : "Can't reach the Planless API. Is uvicorn running on port 8000?",
      0,
    );
  }
  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    /* non-JSON error page */
  }
  if (!res.ok) {
    const detail = (json as { detail?: unknown } | null)?.detail;
    throw new ApiError(detail ? describe(detail) : `HTTP ${res.status}`, res.status, detail);
  }
  return json as T;
}

export const api = {
  searchTravel: (req: TravelSearchRequest, signal?: AbortSignal) =>
    post<TravelSearchResult>("/travel/search", req, signal),
  searchHotels: (req: HotelSearchRequest, signal?: AbortSignal) =>
    post<HotelSearchResult>("/hotel/search", req, signal),
  planItinerary: (req: ItineraryRequest, signal?: AbortSignal) =>
    post<ItineraryResult>("/itinerary/plan", req, signal),
  reviseItinerary: (
    body: { previous: ItineraryResult; request: ItineraryRequest; previous_request: ItineraryRequest },
    signal?: AbortSignal,
  ) => post<ItineraryResult>("/itinerary/revise", body, signal),

  searchPlaces: (q: string, signal?: AbortSignal, prefer?: string) =>
    request<{ query: string; results: PlaceResult[] }>(
      `/places/search?q=${encodeURIComponent(q)}&count=8${prefer ? `&prefer=${encodeURIComponent(prefer)}` : ""}`,
      { method: "GET" }, signal),
  localTips: (body: { city: string; country: string }, signal?: AbortSignal) =>
    post<LocalTips>("/insights/local-tips", body, signal),
  tripDraft: (body: { text: string; today: string; home_city?: string }, signal?: AbortSignal) =>
    post<TripDraftResult>("/assistant/trip-draft", body, signal),

  async health(): Promise<Health | null> {
    try {
      const res = await fetch(`${BASE}/`, { headers: { accept: "application/json" } });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  },
};
