import { useEffect, useState } from "react";
import { dateRange } from "../lib/format";
import { type Draft, type Lane, type LaneKey } from "../lib/trip";

const STATUS_TEXT: Record<Lane["status"], string> = {
  waiting: "Queued",
  running: "Searching",
  done: "Done",
  empty: "Nothing back",
  error: "Failed",
};

export function PlanningBoard({ draft, lanes, finished, onOpen, onCancel }: {
  draft: Draft;
  lanes: Record<LaneKey, Lane>;
  finished: boolean;
  onOpen: () => void;
  onCancel: () => void;
}) {
  const from = draft.from;
  const to = draft.to;
  const code = (p: typeof from) => p.iata ?? p.city;
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (finished) return;
    const t0 = performance.now();
    const id = setInterval(() => setElapsed(Math.round((performance.now() - t0) / 100) / 10), 100);
    return () => clearInterval(id);
  }, [finished]);

  const rows: { key: LaneKey; code: string; what: string; how: string }[] = [
    { key: "out", code: "FLT", what: `${code(from)} → ${code(to)}`, how: "Travel agent, POST /travel/search" },
    { key: "back", code: "RTN", what: `${code(to)} → ${code(from)}`, how: "Travel agent, POST /travel/search" },
    { key: "itinerary", code: "DAY", what: `${to.city}, day by day`, how: "Itinerary agent, POST /itinerary/plan" },
    { key: "hotels", code: "BED", what: "Stays near your stops", how: "Hotel agent, POST /hotel/search" },
    { key: "tips", code: "TIP", what: "What travellers say", how: "Tavily web search + Gemini, POST /insights/local-tips" },
  ];

  return (
    <div className="board" role="status" aria-live="polite">
      <div className="board__inner">
        <header className="board__head">
          <p className="board__kicker">{finished ? "Your plan is ready" : "Planning your trip"}</p>
          <h1>{to.city}</h1>
          <p className="num">{dateRange(draft.start, draft.end)}, {from.city} → {to.city}</p>
        </header>

        <ol className="board__rows">
          {rows.map((r) => {
            const l = lanes[r.key];
            return (
              <li key={r.key} className={`board__row is-${l.status}`}>
                <span className="board__code num">{r.code}</span>
                <span className="board__what">
                  <strong>{r.what}</strong>
                  <small className="num">{r.how}</small>
                  {l.error && <small className="board__err">{l.error}</small>}
                </span>
                <span className="board__status num">
                  {l.status === "done" || l.status === "empty" ? l.summary ?? STATUS_TEXT[l.status] : STATUS_TEXT[l.status]}
                  {l.ms !== undefined && <small>{(l.ms / 1000).toFixed(1)}s</small>}
                </span>
              </li>
            );
          })}
        </ol>

        <p className="board__note">
          Flights and the day plan are searched together. Stays wait for the plan so they can be ranked by distance to
          the places you'll visit.
        </p>

        <footer className="board__foot">
          <span className="num board__clock">{finished ? "All agents finished" : `${elapsed.toFixed(1)}s`}</span>
          {finished ? (
            <button type="button" className="btn btn--signal" onClick={onOpen} autoFocus>
              See the plan
            </button>
          ) : (
            <button type="button" className="btn btn--ghost-dark" onClick={onCancel}>Cancel</button>
          )}
        </footer>
      </div>
    </div>
  );
}
