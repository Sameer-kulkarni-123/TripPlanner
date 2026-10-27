import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { api } from "../api/client";
import { CURRENCIES, INTERESTS, PLACES, fromResult, longestWord, placeKey, type Place } from "../data/places";
import { addDays, coord, daysBetween, plural, todayISO } from "../lib/format";
import { draftProblem, type Draft } from "../lib/trip";
import { Chip, Icon, Segmented, Sheet, Stepper, Toggle } from "./ui";

const list = (xs: string[]) =>
  xs.length <= 2 ? xs.join(" and ") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;

function useLocalTime(tz: string) {
  const fmt = () => {
    if (!tz) return null;
    try {
      return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: tz }).format(new Date());
    } catch {
      return null;
    }
  };
  const [t, setT] = useState(fmt);
  useEffect(() => {
    setT(fmt());
    const id = setInterval(() => setT(fmt()), 20_000);
    return () => clearInterval(id);
  }, [tz]);
  return t;
}

function PlaceRow({ p, onPick }: { p: Place; onPick: (p: Place) => void }) {
  return (
    <li>
      <button type="button" onClick={() => onPick(p)}>
        <span className="place-list__city">
          {p.city}
          {p.kind === "region" && <em className="place-list__kind">Region</em>}
        </span>
        <span className="place-list__meta">
          {[p.region, p.country].filter(Boolean).join(", ")}
          {p.kind === "region" && p.base ? `. Based around ${p.base}` : ""}
          {p.iata ? `. Fly into ${p.airport}${p.airportKm ? ` (${Math.round(p.airportKm)} km)` : ""}` : ". No airport nearby"}
        </span>
        <span className="place-list__code">{p.iata ?? "–"}</span>
      </button>
    </li>
  );
}

/** Any city or region in the world: quick picks first, then live results from GET /places/search. */
export function PlacePicker({ open, onClose, onPick, exclude, title, prefer }: {
  open: boolean; onClose: () => void; onPick: (p: Place) => void; exclude: Place; title: string; prefer?: string;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Place[] | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState("");
  const ctl = useRef<AbortController | null>(null);
  useEffect(() => { if (open) { setQ(""); setResults(null); setState("idle"); } }, [open]);

  useEffect(() => {
    const term = q.trim();
    ctl.current?.abort();
    if (term.length < 2) { setResults(null); setState("idle"); return; }
    const c = new AbortController();
    ctl.current = c;
    setState("loading");
    const id = window.setTimeout(() => {
      api.searchPlaces(term, c.signal, prefer)
        .then((r) => { setResults(r.results.map(fromResult)); setState("idle"); })
        .catch((e: Error) => { if (e.name !== "AbortError") { setState("error"); setError(e.message); } });
    }, 250);
    return () => { window.clearTimeout(id); c.abort(); };
  }, [q, prefer]);

  const quick = useMemo(() => {
    const s = q.trim().toLowerCase();
    return PLACES.filter((p) => placeKey(p) !== placeKey(exclude))
      .filter((p) => !s || `${p.city} ${p.country} ${p.iata ?? ""}`.toLowerCase().includes(s));
  }, [q, exclude]);
  const pick = (p: Place) => { onPick(p); onClose(); };
  const live = (results ?? []).filter((p) => placeKey(p) !== placeKey(exclude));
  const shownKeys = new Set(live.map((p) => p.city.toLowerCase()));

  return (
    <Sheet open={open} onClose={onClose} title={title}>
      <label className="search">
        <Icon name="search" size={18} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="City, state or region, e.g. Goa"
          aria-label="Search places" />
      </label>
      {state === "loading" && <p className="place-list__status">Searching…</p>}
      {state === "error" && <p className="place-list__status is-error">City search is unavailable: {error}</p>}
      <ul className="place-list">
        {live.map((p) => <PlaceRow key={placeKey(p)} p={p} onPick={pick} />)}
        {results && !live.length && state === "idle" && <li className="place-list__none">Nothing called “{q.trim()}” found.</li>}
      </ul>
      {quick.filter((p) => !shownKeys.has(p.city.toLowerCase())).length > 0 && (
        <>
          <p className="place-list__head">{q.trim().length >= 2 ? "Also matching" : "Popular"}</p>
          <ul className="place-list">
            {quick.filter((p) => !shownKeys.has(p.city.toLowerCase())).map((p) => <PlaceRow key={placeKey(p)} p={p} onPick={pick} />)}
          </ul>
        </>
      )}
    </Sheet>
  );
}

export function Composer({ draft, setDraft, onSubmit, apiOnline, banner, onDismissBanner }: {
  draft: Draft; setDraft: (d: Draft) => void; onSubmit: () => void; apiOnline: boolean | null;
  banner?: { title: string; notes: string[] } | null; onDismissBanner?: () => void;
}) {
  const [picker, setPicker] = useState<null | "from" | "to">(null);
  const [tuneOpen, setTuneOpen] = useState(false);
  const to = draft.to;
  const from = draft.from;
  const localTime = useLocalTime(to.tz);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft({ ...draft, [k]: v });

  const nights = daysBetween(draft.start, draft.end);
  const today = todayISO();
  const problem = draftProblem(draft);

  const toggleIn = (k: "interests" | "avoid", v: string) => {
    const other = k === "interests" ? "avoid" : "interests";
    const has = draft[k].includes(v);
    setDraft({
      ...draft,
      [k]: has ? draft[k].filter((x) => x !== v) : [...draft[k], v],
      [other]: draft[other].filter((x) => x !== v),
    });
  };

  const setChildren = (n: number) => {
    const ages = draft.childAges.slice(0, n);
    while (ages.length < n) ages.push(8);
    set("childAges", ages);
  };

  return (
    <div className="composer">
      <section className="composer__hero" aria-label="Destination">
        <p className="hero__label">Going to</p>
        <h1 className="hero__title">
          <button type="button" className="hero__city" onClick={() => setPicker("to")} aria-label={`Destination: ${to.city}. Change`}
            style={{ "--word": longestWord(to.city) } as CSSProperties}>
            {to.city}
            <Icon name="chevron" size={30} className="hero__chev" />
          </button>
        </h1>
        <p className="hero__meta">
          <span>{[to.kind === "region" ? (to.base ? `Region, based in ${to.base}` : "Region") : to.region, to.country].filter(Boolean).join(", ")}</span>
          <span className="num">{coord(to.lat, to.lon)}</span>
          {localTime && <span className="num" title={to.tz}>{localTime} local time</span>}
        </p>

        <p className="hero__brief">
          {nights + 1} days at a {draft.pace} pace.
          {draft.interests.length > 0 && <> Into {list(draft.interests)}.</>}
          {draft.avoid.length > 0 && <> Skipping {list(draft.avoid)}.</>}
        </p>

        <div className="route" aria-label="Route">
          <button type="button" className="route__end" onClick={() => setPicker("from")}>
            <small>From</small>
            <strong className="num">{from.iata ?? "–"}</strong>
            <span>{from.city}</span>
          </button>
          <div className="route__line" aria-hidden="true">
            <span className="route__dot" />
            <span className="route__dash" />
            <button type="button" className="route__swap" aria-label="Swap origin and destination"
              onClick={() => setDraft({ ...draft, from: draft.to, to: draft.from })}>
              <Icon name="swap" size={16} />
            </button>
            <span className="route__dash" />
            <span className="route__dot route__dot--fill" />
          </div>
          <button type="button" className="route__end route__end--to" onClick={() => setPicker("to")}>
            <small>To</small>
            <strong className="num">{to.iata ?? "–"}</strong>
            <span>{to.city}</span>
          </button>
        </div>
        {(!from.iata || !to.iata) && (
          <p className="route__warn">
            No airport near {!from.iata ? from.city : to.city}, so flights won't be searched. Stays and the day plan still work.
          </p>
        )}
      </section>

      <form className="composer__form" onSubmit={(e) => { e.preventDefault(); if (!problem) onSubmit(); }}>
        {banner && (
          <div className="filled" role="status">
            <div>
              <p className="filled__title">{banner.title}</p>
              {banner.notes.map((n) => <p key={n} className="filled__note">{n}</p>)}
            </div>
            {onDismissBanner && <button type="button" className="icon-btn" aria-label="Dismiss" onClick={onDismissBanner}><Icon name="close" size={18} /></button>}
          </div>
        )}
        <fieldset className="field">
          <legend>Dates</legend>
          <div className="dates">
            <label>
              <small>Depart</small>
              <input type="date" value={draft.start} min={today}
                onChange={(e) => {
                  const start = e.target.value;
                  if (!start) return;
                  const len = Math.max(1, daysBetween(draft.start, draft.end));
                  setDraft({ ...draft, start, end: addDays(start, len) });
                }} />
            </label>
            <label>
              <small>Return</small>
              <input type="date" value={draft.end} min={addDays(draft.start, 1)}
                onChange={(e) => e.target.value && set("end", e.target.value)} />
            </label>
          </div>
          <p className="field__note num">{plural(nights + 1, "day")}, {plural(nights, "night")}</p>
        </fieldset>

        <fieldset className="field">
          <legend>Who's going</legend>
          <Stepper label="Adults" value={draft.adults} min={1} max={9}
            onChange={(v) => setDraft({ ...draft, adults: v, rooms: Math.min(draft.rooms, v) })} />
          <Stepper label="Children" hint="0–17" value={draft.childAges.length} min={0} max={6} onChange={setChildren} />
          {draft.childAges.length > 0 && (
            <div className="ages">
              {draft.childAges.map((age, i) => (
                <label key={i}>
                  <small>Child {i + 1}</small>
                  <select value={age} onChange={(e) => {
                    const ages = [...draft.childAges];
                    ages[i] = Number(e.target.value);
                    set("childAges", ages);
                  }}>
                    {Array.from({ length: 18 }, (_, a) => <option key={a} value={a}>{a === 0 ? "Under 1" : `${a} yrs`}</option>)}
                  </select>
                </label>
              ))}
            </div>
          )}
          <Stepper label="Rooms" value={draft.rooms} min={1} max={Math.min(5, draft.adults)} onChange={(v) => set("rooms", v)} />
        </fieldset>

        <fieldset className="field">
          <legend>Pace</legend>
          <Segmented label="Pace" value={draft.pace} onChange={(v) => set("pace", v)} options={[
            { value: "relaxed", label: "Relaxed", sub: "2 a day" },
            { value: "moderate", label: "Moderate", sub: "3 a day" },
            { value: "packed", label: "Packed", sub: "4 a day" },
          ]} />
        </fieldset>

        <fieldset className="field">
          <legend>Into</legend>
          <div className="chips">
            {INTERESTS.map((i) => <Chip key={i} on={draft.interests.includes(i)} onClick={() => toggleIn("interests", i)}>{i}</Chip>)}
          </div>
          <p className="field__sub">Skip</p>
          <div className="chips">
            {INTERESTS.filter((i) => !draft.interests.includes(i)).map((i) => (
              <Chip key={i} tone="avoid" on={draft.avoid.includes(i)} onClick={() => toggleIn("avoid", i)}>{i}</Chip>
            ))}
          </div>
        </fieldset>

        <fieldset className="field">
          <legend>Activity budget</legend>
          <div className="budget">
            <input type="number" inputMode="numeric" min={0} step={10} placeholder="No limit"
              value={draft.activityBudget ?? ""} aria-label="Maximum spend on activities for the whole trip"
              onChange={(e) => set("activityBudget", e.target.value === "" ? null : Math.max(0, Number(e.target.value)))} />
            <Segmented size="sm" label="Currency" value={draft.currency as (typeof CURRENCIES)[number]}
              onChange={(v) => set("currency", v)} options={CURRENCIES.map((c) => ({ value: c, label: c }))} />
          </div>
          <p className="field__note">For the whole party, all days. The scheduler won't pick activities past it.</p>
        </fieldset>

        <div className="field field--tune">
          <button type="button" className="disclosure" aria-expanded={tuneOpen} onClick={() => setTuneOpen(!tuneOpen)}>
            <span>Fine-tune</span>
            <small>{tuneOpen ? "Hide" : "Flights, stays, access"}</small>
          </button>
          {tuneOpen && (
            <div className="tune">
              <p className="field__sub">Rank flights by</p>
              <Segmented size="sm" label="Flight priority" value={draft.flightPriority} onChange={(v) => set("flightPriority", v)} options={[
                { value: "balanced", label: "Balanced" }, { value: "cheapest", label: "Price" },
                { value: "fastest", label: "Speed" }, { value: "fewest_transfers", label: "Stops" },
              ]} />
              <p className="field__sub">Cabin</p>
              <Segmented size="sm" label="Cabin" value={draft.cabin} onChange={(v) => set("cabin", v)} options={[
                { value: "economy", label: "Economy" }, { value: "premium_economy", label: "Premium" },
                { value: "business", label: "Business" }, { value: "first", label: "First" },
              ]} />
              <p className="field__sub">Rank stays by</p>
              <Segmented size="sm" label="Stay priority" value={draft.hotelPriority} onChange={(v) => set("hotelPriority", v)} options={[
                { value: "balanced", label: "Balanced" }, { value: "cheapest", label: "Price" },
                { value: "best_rated", label: "Stars" }, { value: "location", label: "Location" },
                { value: "flexible_cancellation", label: "Flexible" },
              ]} />
              <Toggle label="Refundable stays only" on={draft.refundableOnly} onChange={(v) => set("refundableOnly", v)} />
              <Toggle label="Step-free access" hint="Drops activities marked not wheelchair-accessible" on={draft.stepFree} onChange={(v) => set("stepFree", v)} />
            </div>
          )}
        </div>

        <div className="cta">
          <div className="cta__summary">
            {problem ? <span className="cta__problem">{problem}</span> : (
              <>
                <strong>{from.iata ?? from.city} → {to.iata ?? to.city}</strong>
                <span>{plural(nights + 1, "day")}, {plural(draft.adults + draft.childAges.length, "traveller")}</span>
              </>
            )}
          </div>
          <button type="submit" className="btn btn--primary" disabled={!!problem || apiOnline === false}>
            Plan this trip
          </button>
        </div>
        {apiOnline === false && (
          <p className="offline">Can't reach the API. Start it with <code>uvicorn app.main:app --app-dir backend --reload</code></p>
        )}
      </form>

      <PlacePicker open={picker !== null} onClose={() => setPicker(null)}
        title={picker === "from" ? "Flying from" : "Going to"}
        exclude={picker === "from" ? draft.to : draft.from} prefer={draft.from.countryCode}
        onPick={(p) => set(picker === "from" ? "from" : "to", p)} />
    </div>
  );
}
