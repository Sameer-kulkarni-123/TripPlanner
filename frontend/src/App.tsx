import { useEffect, useRef, useState } from "react";
import { api } from "./api/client";
import { Composer } from "./components/Composer";
import { Landing } from "./components/Landing";
import { PlanningBoard } from "./components/PlanningBoard";
import { Trip } from "./components/Trip";
import { Mark } from "./components/ui";
import type { Health, TripDraftResult } from "./api/types";
import { fromResult } from "./data/places";
import { addDays, daysBetween, todayISO } from "./lib/format";
import { defaultDraft, runPlan, type Draft, type Lane, type LaneKey, type TripData } from "./lib/trip";

const KEY = "planless.draft.v3"; // v3: places carry kind/base and the airport picker changed

function loadDraft(): Draft {
  const base = defaultDraft();
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return base;
    const d = { ...base, ...JSON.parse(raw) } as Draft;
    if (typeof d.from !== "object" || typeof d.to !== "object" || !d.to?.city || !d.from?.city) return base;
    if (d.start < todayISO()) return { ...d, start: base.start, end: addDays(base.start, 3) };
    return d;
  } catch {
    return base;
  }
}

const IDLE: Record<LaneKey, Lane> = {
  out: { status: "waiting" }, back: { status: "waiting" }, itinerary: { status: "waiting" }, hotels: { status: "waiting" },
  tips: { status: "waiting" },
};

export function App() {
  const [draft, setDraft] = useState<Draft>(loadDraft);
  const [view, setView] = useState<"home" | "compose" | "planning" | "trip">("home");
  const [banner, setBanner] = useState<{ title: string; notes: string[] } | null>(null);
  const [lanes, setLanes] = useState(IDLE);
  const [trip, setTrip] = useState<TripData | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    try { localStorage.setItem(KEY, JSON.stringify(draft)); } catch { /* storage unavailable */ }
  }, [draft]);

  useEffect(() => {
    let alive = true;
    const check = () => api.health().then((h) => { if (!alive) return; setApiOnline(!!h); setHealth(h); });
    check();
    const id = setInterval(check, 15000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  useEffect(() => { window.scrollTo({ top: 0 }); }, [view]);

  const applyDraft = (r: TripDraftResult) => {
    const d: Draft = { ...draft };
    const filled: string[] = [];
    if (r.destination) { d.to = fromResult(r.destination); filled.push(d.to.city); }
    if (r.origin) d.from = fromResult(r.origin);
    if (r.start_date) d.start = r.start_date;
    if (r.end_date) d.end = r.end_date;
    else if (r.start_date) d.end = addDays(r.start_date, Math.max(1, daysBetween(draft.start, draft.end)));
    if (r.adults) d.adults = r.adults;
    d.childAges = r.children_ages ?? d.childAges;
    d.rooms = Math.min(d.rooms, d.adults);
    if (r.interests.length) d.interests = r.interests;
    if (r.avoid.length) d.avoid = r.avoid;
    if (r.pace) d.pace = r.pace;
    if (r.activity_budget) d.activityBudget = r.activity_budget;
    if (r.currency) d.currency = r.currency;
    if (r.wheelchair) d.stepFree = true;
    setDraft(d);
    const missing = r.missing.map((m) => (m === "dates" ? "the dates" : "where you're going"));
    setBanner({
      title: missing.length
        ? `Filled in what you described. Please add ${missing.join(" and ")}.`
        : "Filled in from your description. Check the details, then plan.",
      notes: r.notes,
    });
    setView("compose");
  };

  const plan = async () => {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setLanes(IDLE);
    setTrip(null);
    setView("planning");
    try {
      const data = await runPlan(draft, (k, l) => setLanes((s) => ({ ...s, [k]: l })), ctl.signal);
      if (!ctl.signal.aborted) setTrip(data);
    } catch {
      /* aborted */
    }
  };

  return (
    <div className={`app app--${view}`}>
      {view !== "planning" && (
        <header className="topbar">
          <a className="brand" href="/" onClick={(e) => { e.preventDefault(); setView("home"); }}>
            <Mark className="brand__mark" />
            Planless
          </a>
          {view === "home" && (
            <nav className="topnav" aria-label="Sections">
              <a href="#destinations">Destinations</a>
              <a href="#how">How it works</a>
            </nav>
          )}
          <span className={`api api--${apiOnline === null ? "unknown" : apiOnline ? "up" : "down"}`}
            title={health ? `Gemini ${health.gemini_configured ? "on" : "off"}, Nuitee ${health.nuitee_configured ? "on" : "off"}, Tavily ${health.tavily_configured ? "on" : "off"}` : undefined}>
            {apiOnline === null ? "Checking API" : apiOnline ? "API online" : "API offline"}
          </span>
        </header>
      )}
      {view === "home" && (
        <Landing apiOnline={apiOnline} geminiReady={!!health?.gemini_configured} draft={draft} setDraft={setDraft}
          onDraft={applyDraft} onPlan={plan} onMore={() => { setBanner(null); setView("compose"); }} />
      )}
      {view === "compose" && (
        <Composer draft={draft} setDraft={setDraft} onSubmit={plan} apiOnline={apiOnline}
          banner={banner} onDismissBanner={() => setBanner(null)} />
      )}
      {view === "planning" && (
        <PlanningBoard draft={draft} lanes={lanes} finished={!!trip} onOpen={() => setView("trip")}
          onCancel={() => { abort.current?.abort(); setView("compose"); }} />
      )}
      {view === "trip" && trip && <Trip data={trip} onEdit={() => setView("compose")} />}
    </div>
  );
}
