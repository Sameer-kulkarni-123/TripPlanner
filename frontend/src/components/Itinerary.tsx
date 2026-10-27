import { Fragment, useMemo, useState } from "react";
import type { Activity, DayPlan, ItineraryRequest, ItineraryResult, ScheduledItem } from "../api/types";
import {
  activityTitle, dateLong, dayNum, dayShort, duration, hhmm, money, num, plural, titleCase,
} from "../lib/format";
import { RouteMap, type MapStop } from "./RouteMap";
import { Empty } from "./ui";

const DAY_TYPE: Record<DayPlan["day_type"], string> = {
  arrival: "Arrival day",
  full: "Full day",
  departure: "Departure day",
  arrival_and_departure: "Arrive & leave",
};

function travelLine(it: ScheduledItem) {
  const t = it.travel_from_previous;
  if (!t || t.mode === "none") return null;
  if (t.mode === "unknown") return { mode: "unknown", text: "Travel time unknown, 30 min allowed", title: t.method };
  const km = t.distance_km != null ? `${t.distance_km < 1 ? t.distance_km.toFixed(2) : t.distance_km.toFixed(1)} km` : "";
  return {
    mode: t.mode,
    text: `${t.mode === "walk" ? "Walk" : "Transit"} ${km}, about ${t.minutes} min`,
    title: `Estimated with ${t.method}, from ${t.from_label}`,
  };
}

function flagText(a: Activity): string[] {
  const out: string[] = [];
  if (a.is_demo_data) out.push("Demo data");
  if (a.is_ai_suggested) out.push("AI suggestion");
  if (a.opening_hours.status === "unknown") out.push("Hours unknown");
  if (a.confidence_flags.includes("accessibility_unverified")) out.push("Access unverified");
  if (a.price_basis === "unknown" && a.price != null) out.push("Price basis unknown");
  return out;
}

function DayView({ day, itin, request, city, revised }: {
  day: DayPlan; itin: ItineraryResult; request: ItineraryRequest; city: string; revised: boolean;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const byId = useMemo(() => new Map(itin.activities.map((a) => [a.activity_id, a])), [itin.activities]);
  const cur = itin.cost_summary.currency;

  let n = 0;
  const numbered = day.items.map((it) => ({ it, n: it.kind === "activity" ? ++n : 0 }));
  const stops: MapStop[] = [];
  if (request.hotel.latitude != null && request.hotel.longitude != null) {
    stops.push({ id: "hotel", lat: request.hotel.latitude, lon: request.hotel.longitude, kind: "hotel", label: request.hotel.name ?? "Hotel" });
  }
  numbered.forEach(({ it, n: k }) => {
    const a = it.activity_id ? byId.get(it.activity_id) : undefined;
    if (a && a.latitude != null && a.longitude != null) {
      stops.push({ id: it.item_id, lat: a.latitude, lon: a.longitude, kind: "stop", n: k, label: activityTitle(a.name, a.is_demo_data, city) });
    }
  });
  const dayIssues = itin.validation_issues.filter((i) => i.day_number === day.day_number && i.severity !== "info");

  return (
    <article className="day" aria-labelledby={`day-${day.day_number}`}>
      <header className="day__head">
        <p className="day__kicker">Day {day.day_number}, {DAY_TYPE[day.day_type].toLowerCase()}{revised && <span className="tag tag--brand">Rebuilt</span>}</p>
        <h2 id={`day-${day.day_number}`}>{dateLong(day.date)}</h2>
        <dl className="day__meta">
          {day.available_from && day.available_until && (
            <div><dt>Free</dt><dd className="num">{hhmm(day.available_from)}–{hhmm(day.available_until)}</dd></div>
          )}
          <div><dt>Est.</dt><dd className="num">{money(day.estimated_cost, cur)}</dd></div>
          {day.area_label && <div className="day__area"><dt>Area</dt><dd>{activityTitle(day.area_label.replace(/^Around /, ""), true, city)}</dd></div>}
        </dl>
      </header>

      {stops.length > 0 && <RouteMap stops={stops} active={hover} onHover={setHover} />}

      {day.notes.map((t) => <p key={t} className="day__note">{t}</p>)}

      <ol className="timeline">
        {numbered.map(({ it, n: k }) => {
          const a = it.activity_id ? byId.get(it.activity_id) : undefined;
          const tl = it.kind === "activity" ? travelLine(it) : null;
          return (
            <Fragment key={it.item_id}>
              {tl && (
                <li className={`timeline__travel is-${tl.mode}`} title={tl.title}>
                  <span className="num">{tl.text}</span>
                </li>
              )}
              <li className={`timeline__item is-${it.kind} ${hover === it.item_id ? "is-hover" : ""}`}
                onPointerEnter={(e) => e.pointerType === "mouse" && setHover(it.item_id)} onPointerLeave={() => setHover(null)}>
                <div className="timeline__time num">
                  <strong>{hhmm(it.start)}</strong>
                  <span>{hhmm(it.end)}</span>
                </div>
                <div className="timeline__node" aria-hidden="true">{it.kind === "activity" ? k : null}</div>
                <div className="timeline__body">
                  <h3>{a ? activityTitle(a.name, a.is_demo_data, city) : it.title}</h3>
                  {a?.description && a.is_ai_suggested && <p className="timeline__desc">{a.description}</p>}
                  {a && (
                    <p className="timeline__meta">
                      {[a.category, duration(a.duration_minutes), it.estimated_cost != null ? `${money(it.estimated_cost, cur)} est.` : "Price unknown"]
                        .filter(Boolean).join(", ")}
                    </p>
                  )}
                  {a && a.matched_interests.length > 0 && (
                    <p className="timeline__why">Matches {a.matched_interests.join(", ")}</p>
                  )}
                  {(a ? flagText(a) : []).length > 0 && (
                    <div className="timeline__flags">{flagText(a!).map((f) => <span key={f} className="tag">{f}</span>)}</div>
                  )}
                  {it.kind !== "activity" && it.notes.length > 0 && <p className="timeline__note">{it.notes[0]}</p>}
                </div>
              </li>
            </Fragment>
          );
        })}
      </ol>

      {dayIssues.length > 0 && (
        <ul className="day__issues">
          {dayIssues.map((i) => <li key={i.code + i.item_id} className={`sev sev--${i.severity}`}>{i.message}</li>)}
        </ul>
      )}
    </article>
  );
}

export function Itinerary({ itin, request, city, revisedDays }: {
  itin: ItineraryResult; request: ItineraryRequest; city: string; revisedDays: number[];
}) {
  const [sel, setSel] = useState(1);
  const day = itin.days.find((d) => d.day_number === sel) ?? itin.days[0];
  if (!day) return <Empty title="No days were planned." />;
  const cur = itin.cost_summary.currency;

  return (
    <section className="itin" aria-label="Itinerary">
      <nav className="daystrip" aria-label="Days">
        {itin.days.map((d) => {
          const acts = d.items.filter((i) => i.kind === "activity").length;
          return (
            <button key={d.day_number} type="button" aria-current={d.day_number === day.day_number ? "true" : undefined}
              onClick={() => setSel(d.day_number)} className={revisedDays.includes(d.day_number) ? "is-revised" : ""}>
              <small className="num">{dayShort(d.date)}</small>
              <strong>{dayNum(d.date)}</strong>
              <span>{acts ? plural(acts, "stop") : "No stops"}</span>
            </button>
          );
        })}
      </nav>

      <DayView key={day.day_number + itin.generated_at} day={day} itin={itin} request={request} city={city}
        revised={revisedDays.includes(day.day_number)} />

      {itin.alternatives.length > 0 && (
        <details className="alts">
          <summary>
            <span>Also fits your constraints</span>
            <small className="num">{itin.alternatives.length}</small>
          </summary>
          <ul>
            {itin.alternatives.map((a) => (
              <li key={a.activity_id}>
                <span>{activityTitle(a.name, a.is_demo_data, city)}</span>
                <small className="num">{duration(a.duration_minutes)}, {a.price != null ? money(num(a.price), a.currency ?? cur) : "price unknown"}
                  {a.matched_interests.length ? `, ${a.matched_interests.map(titleCase).join(", ")}` : ""}</small>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
