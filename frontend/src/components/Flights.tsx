import type { TransportOption, TravelSearchResult } from "../api/types";
import { dateMed, daysBetween, duration, hhmm, money, plural } from "../lib/format";
import type { Settled } from "../lib/trip";
import { Empty } from "./ui";

function stopsText(o: TransportOption) {
  if (!o.transfers) return "Nonstop";
  const via = o.segments.slice(0, -1).map((s) => s.arrival_location).filter(Boolean);
  return `${plural(o.transfers, "stop")}${via.length ? ` via ${via.join(", ")}` : ""}`;
}

function carriers(o: TransportOption) {
  const names = [...new Set(o.segments.map((s) => s.carrier_name || s.carrier_code).filter(Boolean))];
  return names.join(" + ") || o.provider_name;
}

function FlightRow({ o, selected, onSelect, disabled, best }: {
  o: TransportOption; selected: boolean; onSelect: () => void; disabled: boolean; best: boolean;
}) {
  const plusDays = daysBetween(o.departure_time, o.arrival_time);
  return (
    <li>
      <button type="button" className={`fare ${selected ? "is-selected" : ""}`} aria-pressed={selected} onClick={onSelect} disabled={disabled}>
        <div className="fare__times">
          <span className="num fare__t">{hhmm(o.departure_time)}</span>
          <span className="fare__line" aria-hidden="true">
            {Array.from({ length: o.transfers }, (_, i) => <i key={i} />)}
          </span>
          <span className="num fare__t">{hhmm(o.arrival_time)}{plusDays > 0 && <sup>+{plusDays}</sup>}</span>
        </div>
        <span className="radio" aria-hidden="true" />
        <div className="fare__price">
          <strong className="num">{money(o.price, o.currency)}</strong>
          {best && <span className="tag tag--brand">Top ranked</span>}
        </div>
        <div className="fare__meta">
          <span>{duration(o.duration_minutes)}, {stopsText(o).toLowerCase()}</span>
          <span>{carriers(o)}</span>
          {o.baggage_summary && <span>{o.baggage_summary}</span>}
        </div>
        {o.ranking_score != null && (
          <div className="fare__score" title="Ranking score from the Travel Agent (0–1)">
            <span style={{ width: `${Math.round(o.ranking_score * 100)}%` }} />
            <small className="num">{o.ranking_score.toFixed(2)}</small>
          </div>
        )}
      </button>
    </li>
  );
}

function Leg({ title, date, res, selected, onSelect, busy }: {
  title: string; date: string; res: Settled<TravelSearchResult>;
  selected: TransportOption | null; onSelect: (o: TransportOption | null) => void; busy: boolean;
}) {
  return (
    <section className="leg">
      <header className="leg__head">
        <h3>{title}</h3>
        <span className="num">{dateMed(date)}</span>
      </header>
      {!res.ok ? (
        <Empty title="The flight search failed.">
          <p className="num">{res.error}</p>
        </Empty>
      ) : res.data.options.length === 0 ? (
        <Empty title="No fares came back for this leg.">
          {res.data.limitations.length > 0
            ? res.data.limitations.map((l) => <p key={l}>{l}</p>)
            : <p>Nuitee had no fares for this route and date.</p>}
        </Empty>
      ) : (
        <ul className="fares">
          {res.data.options.slice(0, 10).map((o, i) => (
            <FlightRow key={o.option_id} o={o} best={i === 0} disabled={busy}
              selected={selected?.option_id === o.option_id}
              onSelect={() => onSelect(selected?.option_id === o.option_id ? null : o)} />
          ))}
        </ul>
      )}
      {res.ok && res.data.options.length > 0 && res.data.limitations.map((l) => <p key={l} className="limit">{l}</p>)}
    </section>
  );
}

export function Flights({ out, back, from, to, start, end, selOut, selBack, onSelect, busy }: {
  out: Settled<TravelSearchResult>; back: Settled<TravelSearchResult>;
  from: string; to: string; start: string; end: string;
  selOut: TransportOption | null; selBack: TransportOption | null;
  onSelect: (dir: "out" | "back", o: TransportOption | null) => void; busy: boolean;
}) {
  return (
    <div className="panel">
      <p className="panel__lede">
        Choosing both legs confirms your transport. The itinerary then rebuilds only the days your arrival and
        departure touch.
      </p>
      <Leg title={`${from} → ${to}`} date={start} res={out} selected={selOut} onSelect={(o) => onSelect("out", o)} busy={busy} />
      <Leg title={`${to} → ${from}`} date={end} res={back} selected={selBack} onSelect={(o) => onSelect("back", o)} busy={busy} />
    </div>
  );
}
