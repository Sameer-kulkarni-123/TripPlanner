import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { api } from "../api/client";
import type { TripDraftResult } from "../api/types";
import { byCity, type Place } from "../data/places";
import { addDays, dayShort, dayNum, daysBetween, monthShort, plural, todayISO } from "../lib/format";
import { draftProblem, type Draft } from "../lib/trip";
import { PlacePicker } from "./Composer";
import { Icon, Mark, Segmented, Sheet, Stepper } from "./ui";

const REPO = "https://github.com/Sameer-kulkarni-123/TripPlanner";

const EXAMPLES = [
  "Goa from Bengaluru next weekend, 2 of us, beaches and seafood",
  "3 relaxed days in Jaipur from Delhi in December, forts and food",
  "Kochi with my parents and a 6-year-old, backwaters, no nightlife",
];

type Motif = "waves" | "arch" | "peaks" | "river" | "dome";

/** Popular picks. Seasons are the commonly recommended months, shown as a guide only. */
const DESTINATIONS: { city: string; tag: string; season: string; hue: number; motif: Motif }[] = [
  { city: "Goa", tag: "Beaches and old Portuguese quarters", season: "Nov to Feb", hue: 196, motif: "waves" },
  { city: "Jaipur", tag: "Forts, bazaars and block prints", season: "Oct to Mar", hue: 18, motif: "arch" },
  { city: "Leh", tag: "High passes and monasteries", season: "May to Sep", hue: 222, motif: "peaks" },
  { city: "Kochi", tag: "Backwaters and spice markets", season: "Sep to Mar", hue: 150, motif: "river" },
  { city: "Udaipur", tag: "Lakes and palaces", season: "Sep to Mar", hue: 268, motif: "dome" },
  { city: "Hyderabad", tag: "Biryani, Charminar, Golconda", season: "Oct to Feb", hue: 330, motif: "arch" },
  { city: "Rishikesh", tag: "Ganga, yoga and rafting", season: "Sep to Nov", hue: 172, motif: "peaks" },
  { city: "Varanasi", tag: "Ghats and evening aarti", season: "Oct to Mar", hue: 38, motif: "river" },
];

const AGENTS: { icon: Parameters<typeof Icon>[0]["name"]; title: string; body: string; source: string }[] = [
  { icon: "plane", title: "Flights agent", body: "Searches fares both ways and ranks them by what you care about: price, time or fewest stops.", source: "Nuitee" },
  { icon: "route", title: "Itinerary agent", body: "Picks things you'll like, keeps nearby places on the same day and leaves time to eat and get around.", source: "Nuitee, Gemini" },
  { icon: "bed", title: "Stays agent", body: "Ranks hotels by distance to the places you'll actually visit, using the full price with fees.", source: "Nuitee" },
  { icon: "bulb", title: "Local tips agent", body: "Reads what travellers wrote on Reddit and travel sites about scams, transport and timing, and links every tip to its source.", source: "Tavily, Gemini" },
];

const CHECKS = ["Opening hours", "Travel time between stops", "Airport arrival buffers", "Your activity budget", "Step-free access", "Every AI suggestion labelled"];

/** Outlined, glowing shapes behind the hero (one gradient, drawn twice: blurred glow + crisp line). */
function Constellation() {
  const shapes = (
    <>
      <rect x="40" y="70" width="190" height="190" rx="58" />
      <circle cx="1090" cy="120" r="78" />
      <path d="M1010 330c-30 0-54 23-54 52 0 40 54 86 54 86s54-46 54-86c0-29-24-52-54-52Z" />
      <rect x="150" y="340" width="120" height="120" rx="60" transform="rotate(18 210 400)" />
      <path d="M260 560 C 480 470, 760 640, 960 520" />
    </>
  );
  return (
    <svg className="constellation" viewBox="0 0 1200 640" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id="cg" x1="0" y1="640" x2="1200" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#4F8CFF" />
          <stop offset="0.45" stopColor="#9B72FF" />
          <stop offset="0.8" stopColor="#FF7A8A" />
          <stop offset="1" stopColor="#FFB36B" />
        </linearGradient>
        <filter id="cglow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="10" /></filter>
      </defs>
      <g fill="#161618" stroke="url(#cg)" strokeWidth="6" opacity="0.55" filter="url(#cglow)">{shapes}</g>
      <g fill="none" stroke="url(#cg)" strokeWidth="1.6" strokeDasharray="0" opacity="0.9">{shapes}</g>
    </svg>
  );
}

function TileArt({ motif }: { motif: Motif }) {
  const d: Record<Motif, ReactNode> = {
    waves: <><path d="M0 120c30-14 50-14 80 0s50 14 80 0 50-14 80 0" /><path d="M0 145c30-14 50-14 80 0s50 14 80 0 50-14 80 0" /><circle cx="180" cy="62" r="24" /></>,
    arch: <><path d="M40 170V95a60 60 0 0 1 120 0v75" /><path d="M70 170v-62a30 30 0 0 1 60 0v62" /><path d="M20 170h160" /></>,
    peaks: <><path d="M0 170 70 70l40 50 30-36 80 86" /><path d="m55 92 15-22 15 20" /></>,
    river: <><path d="M0 100c60 0 60 40 120 40s60-40 120-40" /><path d="M0 130c60 0 60 40 120 40s60-40 120-40" /><path d="M150 40v40m-12-28h24" /></>,
    dome: <><path d="M60 170v-50a40 40 0 0 1 80 0v50" /><path d="M100 80V60m0 0c8-6 8-14 0-20-8 6-8 14 0 20" /><path d="M20 170h160M40 150h120" /></>,
  };
  return (
    <svg className="tile__art" viewBox="0 0 200 180" aria-hidden="true">
      <g fill="none" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">{d[motif]}</g>
    </svg>
  );
}

function DateCell({ label, value, min, onChange }: { label: string; value: string; min: string; onChange: (v: string) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <label className="sf__cell sf__cell--date" onClick={() => { try { ref.current?.showPicker(); } catch { /* not supported */ } }}>
      <span className="sf__label"><Icon name="calendar" size={15} />{label}</span>
      <span className="sf__value num">{dayNum(value)} <small>{monthShort(value)} '{value.slice(2, 4)}</small></span>
      <span className="sf__sub">{dayShort(value)}</span>
      <input ref={ref} type="date" value={value} min={min} aria-label={label}
        onChange={(e) => e.target.value && onChange(e.target.value)} />
    </label>
  );
}

function PlaceCell({ label, place, onClick, flash }: { label: string; place: Place; onClick: () => void; flash?: boolean }) {
  return (
    <button type="button" className={`sf__cell ${flash ? "is-flash" : ""}`} onClick={onClick} aria-label={`${label}: ${place.city}. Change`}>
      <span className="sf__label"><Icon name="pin" size={15} />{label}</span>
      <span className="sf__value">{place.city}</span>
      <span className="sf__sub">
        {place.iata ? <><b className="num">{place.iata}</b>, {place.airport}</> : place.kind === "region" ? `Region in ${place.country}` : "No airport nearby"}
      </span>
    </button>
  );
}

export function Landing({ apiOnline, geminiReady, draft, setDraft, onDraft, onPlan, onMore }: {
  apiOnline: boolean | null;
  geminiReady: boolean;
  draft: Draft;
  setDraft: (d: Draft) => void;
  onDraft: (d: TripDraftResult, text: string) => void;
  onPlan: () => void;
  onMore: () => void;
}) {
  const [mode, setMode] = useState<"ask" | "search">("ask");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [picker, setPicker] = useState<null | "from" | "to">(null);
  const [who, setWho] = useState(false);
  const [flashTo, setFlashTo] = useState(false);
  const card = useRef<HTMLDivElement>(null);

  // Without a Gemini key the describe-it box can't work, so open on the search form instead.
  useEffect(() => { if (apiOnline !== null && !geminiReady) setMode("search"); }, [apiOnline, geminiReady]);

  const ask = async (value = text) => {
    const t = value.trim();
    if (t.length < 3 || busy) return;
    setBusy(true);
    setError(null);
    try {
      onDraft(await api.tripDraft({ text: t, today: todayISO(), home_city: draft.from.city }), t);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const pickDestination = (city: string) => {
    const p = byCity(city);
    if (!p) return;
    setDraft({ ...draft, to: p, from: draft.from.city === p.city ? byCity("Bengaluru") ?? draft.from : draft.from });
    setMode("search");
    setFlashTo(true);
    window.setTimeout(() => setFlashTo(false), 1400);
    card.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const nights = daysBetween(draft.start, draft.end);
  const problem = draftProblem(draft);
  const people = draft.adults + draft.childAges.length;
  const canAsk = apiOnline !== false && geminiReady;

  return (
    <div className="landing">
      <section className="hero">
        <Constellation />
        <div className="hero__inner">
          <p className="eyebrow"><Icon name="spark" size={14} /> Flights, stays, a day-by-day plan and local tips</p>
          <h1 className="hero__h1">Travel more.<br /><span className="grad-text">Plan less.</span></h1>
          <p className="hero__sub">
            Say where you want to go. Four agents search at the same time, then code checks that the plan actually works.
          </p>
        </div>

        <div className="finder" ref={card}>
          <div className="finder__tabs" role="tablist" aria-label="How to start">
            <button type="button" role="tab" aria-selected={mode === "ask"} onClick={() => setMode("ask")}>
              <Icon name="spark" size={16} /> Describe it
            </button>
            <button type="button" role="tab" aria-selected={mode === "search"} onClick={() => setMode("search")}>
              <Icon name="search" size={16} /> Search
            </button>
          </div>

          {mode === "ask" ? (
            <form className="prompt" onSubmit={(e) => { e.preventDefault(); ask(); }}>
              <div className={`prompt__box ${busy ? "is-busy" : ""}`}>
                <label htmlFor="ask" className="sr-only">Describe your trip</label>
                <textarea id="ask" rows={3} value={text} disabled={!canAsk || busy}
                  placeholder={canAsk ? EXAMPLES[0] : "Describing a trip needs a Gemini key. Use Search for now."}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } }} />
                <div className="prompt__bar">
                  <span className="prompt__hint">{busy ? "Reading your trip…" : "Where, when, who, and what you're into"}</span>
                  <button type="submit" className="prompt__send" aria-label="Plan it" disabled={!canAsk || busy || text.trim().length < 3}>
                    <Icon name="arrow" size={20} />
                  </button>
                </div>
              </div>
              {error && (
                <p className="prompt__error" role="alert">
                  {error}{" "}
                  <button type="button" className="link" onClick={() => setMode("search")}>Fill in the search instead</button>
                </p>
              )}
              {!geminiReady && apiOnline !== false && (
                <p className="prompt__note">Add <code>GEMINI_API_KEY</code> to <code>.env</code> and restart the API to describe trips in words.</p>
              )}
              {canAsk && (
                <div className="prompt__examples">
                  {EXAMPLES.map((ex) => (
                    <button key={ex} type="button" className="pill" disabled={busy} onClick={() => { setText(ex); ask(ex); }}>{ex}</button>
                  ))}
                </div>
              )}
            </form>
          ) : (
            <form className="sf" onSubmit={(e) => { e.preventDefault(); if (!problem) onPlan(); }}>
              <div className="sf__grid">
                <PlaceCell label="From" place={draft.from} onClick={() => setPicker("from")} />
                <button type="button" className="sf__swap" aria-label="Swap origin and destination"
                  onClick={() => setDraft({ ...draft, from: draft.to, to: draft.from })}>
                  <Icon name="swap" size={16} />
                </button>
                <PlaceCell label="To" place={draft.to} onClick={() => setPicker("to")} flash={flashTo} />
                <DateCell label="Depart" value={draft.start} min={todayISO()}
                  onChange={(start) => setDraft({ ...draft, start, end: addDays(start, Math.max(1, nights)) })} />
                <DateCell label="Return" value={draft.end} min={addDays(draft.start, 1)}
                  onChange={(end) => setDraft({ ...draft, end })} />
                <button type="button" className="sf__cell" onClick={() => setWho(true)}>
                  <span className="sf__label"><Icon name="users" size={15} />Travellers</span>
                  <span className="sf__value num">{people} <small>{people === 1 ? "person" : "people"}</small></span>
                  <span className="sf__sub">{draft.pace[0].toUpperCase() + draft.pace.slice(1)} pace, {plural(draft.rooms, "room")}</span>
                </button>
              </div>
              <div className="sf__foot">
                <p className={`sf__status num ${problem ? "is-problem" : ""}`}>
                  {problem ?? `${plural(nights + 1, "day")}, ${plural(nights, "night")}${draft.interests.length ? `. Into ${draft.interests.slice(0, 3).join(", ")}` : ""}`}
                </p>
                <button type="button" className="link" onClick={onMore}>Interests, budget and more</button>
              </div>
              <button type="submit" className="btn btn--glow sf__go" disabled={!!problem || apiOnline === false}>
                Plan this trip <Icon name="arrow" size={18} />
              </button>
            </form>
          )}
          {apiOnline === false && (
            <p className="finder__offline">The Planless API isn't running. Start it with <code>uvicorn app.main:app --app-dir backend --reload</code></p>
          )}
        </div>
      </section>

      <section className="section" id="destinations" aria-labelledby="dest-h">
        <header className="section__head">
          <h2 id="dest-h">Where people are going</h2>
          <p>Tap one to start from it. Any other city, state or region works too.</p>
        </header>
        <ul className="tiles">
          {DESTINATIONS.map((d) => {
            const p = byCity(d.city);
            if (!p) return null;
            return (
              <li key={d.city}>
                <button type="button" className="tile" style={{ "--h": d.hue } as CSSProperties} onClick={() => pickDestination(d.city)}>
                  <TileArt motif={d.motif} />
                  <span className="tile__code num">{p.iata}</span>
                  <span className="tile__body">
                    <strong>{d.city}</strong>
                    <span>{d.tag}</span>
                    <small>Usually best {d.season}</small>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="section" id="how" aria-labelledby="how-h">
        <header className="section__head">
          <h2 id="how-h">Four agents, one plan</h2>
          <p>They run in parallel. Stays wait for the day plan so they can be ranked by where you'll actually be.</p>
        </header>
        <div className="bento">
          {AGENTS.map((a) => (
            <article key={a.title} className="bento__card">
              <span className="orb"><Icon name={a.icon} size={22} /></span>
              <h3>{a.title}</h3>
              <p>{a.body}</p>
              <small>{a.source}</small>
            </article>
          ))}
          <article className="bento__card bento__card--wide">
            <span className="orb"><Icon name="shield" size={22} /></span>
            <h3>Checked in code, not guessed</h3>
            <p>Language models suggest; code decides. A plan is only marked validated when every check passes.</p>
            <ul className="checklist">
              {CHECKS.map((c) => <li key={c}><Icon name="check" size={16} />{c}</li>)}
            </ul>
          </article>
        </div>
      </section>

      <footer className="foot">
        <div className="foot__brand"><Mark size={28} /> <span>Planless</span></div>
        <p>Built by Aman Chandra H, Sameer Kulkarni and S Nithin.</p>
        <a href={REPO} target="_blank" rel="noreferrer"><Icon name="github" size={18} /> Source on GitHub</a>
      </footer>

      <PlacePicker open={picker !== null} onClose={() => setPicker(null)}
        title={picker === "from" ? "Starting from" : "Going to"}
        exclude={picker === "from" ? draft.to : draft.from} prefer={draft.from.countryCode}
        onPick={(p) => setDraft({ ...draft, [picker === "from" ? "from" : "to"]: p })} />

      <Sheet open={who} onClose={() => setWho(false)} title="Who's going">
        <Stepper label="Adults" value={draft.adults} min={1} max={9}
          onChange={(v) => setDraft({ ...draft, adults: v, rooms: Math.min(draft.rooms, v) })} />
        <Stepper label="Children" hint="0–17" value={draft.childAges.length} min={0} max={6}
          onChange={(n) => {
            const ages = draft.childAges.slice(0, n);
            while (ages.length < n) ages.push(8);
            setDraft({ ...draft, childAges: ages });
          }} />
        <Stepper label="Rooms" value={draft.rooms} min={1} max={Math.min(5, draft.adults)} onChange={(v) => setDraft({ ...draft, rooms: v })} />
        <p className="field__sub">Pace</p>
        <Segmented label="Pace" value={draft.pace} onChange={(v) => setDraft({ ...draft, pace: v })} options={[
          { value: "relaxed", label: "Relaxed", sub: "2 a day" },
          { value: "moderate", label: "Moderate", sub: "3 a day" },
          { value: "packed", label: "Packed", sub: "4 a day" },
        ]} />
        <button type="button" className="btn btn--light sheet__done" onClick={() => setWho(false)}>Done</button>
      </Sheet>
    </div>
  );
}
