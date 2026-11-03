// A day's stops on a real map (Leaflet + OpenStreetMap data, CARTO dark tiles), joined in visiting
// order along actual roads/paths from the free OSRM routing service run by FOSSGIS
// (routing.openstreetmap.de). If routing is unavailable the stops are joined by straight dashed
// lines and the caption says so. Travel times shown in the timeline still come from the itinerary agent.
import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export interface MapStop {
  id: string;
  lat: number;
  lon: number;
  label: string;
  kind: "hotel" | "stop";
  n?: number;
}

type Route = { coords: [number, number][]; km: number; minutes: number; profile: "foot" | "car" } | null;

// OpenStreetMap's own tiles (free, no key; CARTO's basemaps now need an API key). They are light,
// so .lmap__map darkens them with a CSS filter to match the app.
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const routeCache = new Map<string, Route>();

function straightKm(stops: MapStop[]) {
  let km = 0;
  for (let i = 1; i < stops.length; i++) {
    const a = stops[i - 1], b = stops[i];
    const dLat = ((b.lat - a.lat) * Math.PI) / 180, dLon = ((b.lon - a.lon) * Math.PI) / 180;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos((a.lat * Math.PI) / 180) * Math.cos((b.lat * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
    km += 12742 * Math.asin(Math.sqrt(h));
  }
  return km;
}

/** Road/path geometry through the stops in order. Walking paths for compact days, roads otherwise. */
async function fetchRoute(stops: MapStop[], signal: AbortSignal): Promise<Route> {
  if (stops.length < 2) return null;
  const profile: "foot" | "car" = straightKm(stops) / (stops.length - 1) < 2.5 ? "foot" : "car";
  const coords = stops.map((s) => `${s.lon.toFixed(5)},${s.lat.toFixed(5)}`).join(";");
  const key = `${profile}:${coords}`;
  if (routeCache.has(key)) return routeCache.get(key)!;
  const url = `https://routing.openstreetmap.de/routed-${profile}/route/v1/${profile === "foot" ? "foot" : "driving"}/${coords}?overview=full&geometries=geojson`;
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`routing HTTP ${res.status}`);
  const j = await res.json();
  const r = j?.routes?.[0];
  if (!r?.geometry?.coordinates?.length) throw new Error("no route");
  const route: Route = {
    coords: (r.geometry.coordinates as [number, number][]).map(([lon, lat]) => [lat, lon]),
    km: r.distance / 1000,
    minutes: r.duration / 60,
    profile,
  };
  routeCache.set(key, route);
  return route;
}

function icon(s: MapStop, on: boolean) {
  const html = s.kind === "hotel"
    ? `<span class="lmap__pin lmap__pin--hotel${on ? " is-active" : ""}">H</span>`
    : `<span class="lmap__pin${on ? " is-active" : ""}">${s.n ?? ""}</span>`;
  return L.divIcon({ html, className: "lmap__icon", iconSize: [28, 28], iconAnchor: [14, 14] });
}

export function RouteMap({ stops, active, onHover }: {
  stops: MapStop[];
  active?: string | null;
  onHover?: (id: string | null) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef(new Map<string, L.Marker>());
  const line = useRef<L.Polyline | null>(null);
  const [route, setRoute] = useState<Route | "loading" | "failed">("loading");
  const hover = useRef(onHover);
  hover.current = onHover;

  const sig = useMemo(() => stops.map((s) => `${s.id}@${s.lat.toFixed(5)},${s.lon.toFixed(5)}`).join("|"), [stops]);

  // Create the map once
  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { zoomControl: true, scrollWheelZoom: false, attributionControl: false });
    // Plain "Leaflet" credit, without the flag icon Leaflet adds by default
    L.control.attribution({ prefix: '<a href="https://leafletjs.com">Leaflet</a>' }).addTo(m);
    L.tileLayer(TILES, { attribution: ATTRIBUTION, maxZoom: 19 }).addTo(m);
    m.on("focus", () => m.scrollWheelZoom.enable());
    m.on("blur", () => m.scrollWheelZoom.disable());
    map.current = m;
    return () => { m.remove(); map.current = null; markers.current.clear(); line.current = null; };
  }, []);

  // Pins + fit to the day's stops
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    markers.current.forEach((mk) => mk.remove());
    markers.current.clear();
    stops.forEach((s) => {
      const mk = L.marker([s.lat, s.lon], { icon: icon(s, false), keyboard: true, title: s.label, zIndexOffset: s.kind === "hotel" ? 500 : 0 })
        .bindTooltip(s.kind === "hotel" ? s.label : `${s.n}. ${s.label}`, { direction: "top", offset: [0, -12] })
        .on("mouseover", () => hover.current?.(s.id))
        .on("mouseout", () => hover.current?.(null))
        .addTo(m);
      markers.current.set(s.id, mk);
    });
    const b = L.latLngBounds(stops.map((s) => [s.lat, s.lon] as [number, number]));
    if (stops.length === 1) m.setView(b.getCenter(), 14);
    else m.fitBounds(b, { padding: [36, 36], maxZoom: 16 });

  }, [sig]);

  // Route along roads; straight dashed lines while loading or if routing fails
  useEffect(() => {
    const c = new AbortController();
    setRoute("loading");
    fetchRoute(stops, c.signal).then(setRoute).catch(() => { if (!c.signal.aborted) setRoute("failed"); });
    return () => c.abort();

  }, [sig]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    line.current?.remove();
    if (stops.length < 2) return;
    const real = route && route !== "loading" && route !== "failed" ? route : null;
    line.current = real
      ? L.polyline(real.coords, { className: "lmap__route", weight: 4, opacity: 0.95 })
      : L.polyline(stops.map((s) => [s.lat, s.lon] as [number, number]), { className: "lmap__route lmap__route--straight", weight: 2.5, dashArray: "4 8" });
    line.current.addTo(m);
    line.current.bringToBack();
  }, [route, sig]);

  // Highlight the stop hovered in the timeline
  useEffect(() => {
    markers.current.forEach((mk, id) => {
      const s = stops.find((x) => x.id === id);
      if (s) mk.setIcon(icon(s, id === active));
      if (id === active) mk.setZIndexOffset(1000); else mk.setZIndexOffset(s?.kind === "hotel" ? 500 : 0);
    });
  }, [active, sig]);

  const n = stops.filter((s) => s.kind === "stop").length;
  const caption = stops.length < 2 ? null
    : route === "loading" ? "Finding the route…"
      : route === "failed" || !route ? "Straight lines show visiting order (road routing unavailable)."
        : `${route.profile === "foot" ? "Walking" : "Road"} route in visiting order, about ${route.km < 10 ? route.km.toFixed(1) : Math.round(route.km)} km.`;

  return (
    <figure className="lmap">
      <div ref={el} className="lmap__map" role="region" aria-label={`Map of ${n} stops`} tabIndex={0} />
      {caption && <figcaption className="lmap__caption">{caption}</figcaption>}
    </figure>
  );
}
