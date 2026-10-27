import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { HotelOption, HotelPriority, ItineraryRequest, ItineraryResult, TransportOption } from "../api/types";
import { dateRange, money, plural } from "../lib/format";
import {
  hotelRequest, referencePoints, tripCost, withSelection, type Selection, type Settled, type TripData,
} from "../lib/trip";
import { Checks } from "./Checks";
import { Flights } from "./Flights";
import { Itinerary } from "./Itinerary";
import { Stays } from "./Stays";
import { Tips } from "./Tips";
import { Empty, Icon } from "./ui";

type Tab = "plan" | "flights" | "stays" | "tips" | "checks";

function useWide(query = "(min-width: 1080px)") {
  const [wide, setWide] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const on = () => setWide(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, [query]);
  return wide;
}

export function Trip({ data, onEdit }: { data: TripData; onEdit: () => void }) {
  const { draft } = data;
  const to = draft.to, from = draft.from;

  const [itin, setItin] = useState<ItineraryResult | null>(data.itin.ok ? data.itin.data : null);
  const [req, setReq] = useState<ItineraryRequest>(data.itinRequest);
  const [sel, setSel] = useState<Selection>({ out: null, back: null, hotel: null });
  const [hotels, setHotels] = useState(data.hotels);
  const [hotelPriority, setHotelPriority] = useState<HotelPriority>(draft.hotelPriority);
  const [busy, setBusy] = useState(false);
  const [reloadingStays, setReloadingStays] = useState(false);
  const [notice, setNotice] = useState<{ text: string; tone: "ok" | "err" } | null>(null);
  const [revised, setRevised] = useState<number[]>([]);
  const [tab, setTab] = useState<Tab>("plan");
  const noticeTimer = useRef<number>();
  const wide = useWide();

  const flash = (text: string, tone: "ok" | "err" = "ok") => {
    setNotice({ text, tone });
    window.clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setNotice(null), 6000);
  };

  const applySelection = useCallback(async (next: Selection) => {
    if (!itin) { setSel(next); return; }
    const nextReq = withSelection(data.itinRequest, next);
    setBusy(true);
    try {
      const res = await api.reviseItinerary({ previous: itin, request: nextReq, previous_request: req });
      setItin(res);
      setReq(nextReq);
      setSel(next);
      const days = res.revised_days ?? [];
      setRevised(days);
      const all = days.length === res.days.length;
      flash(days.length === 0
        ? "Nothing in the schedule had to change."
        : all ? `Re-planned all ${plural(days.length, "day")} around the new context.`
          : `Rebuilt day ${days.join(", ")}. The other days are unchanged.`);
    } catch (e) {
      flash(`Couldn't update the plan: ${(e as Error).message}`, "err");
    } finally {
      setBusy(false);
    }
  }, [itin, req, data.itinRequest]);

  const pickFlight = (dir: "out" | "back", o: TransportOption | null) => applySelection({ ...sel, [dir]: o });
  const pickHotel = (h: HotelOption | null) => applySelection({ ...sel, hotel: h });

  const rerankStays = async (p: HotelPriority) => {
    setHotelPriority(p);
    setReloadingStays(true);
    try {
      const r = await api.searchHotels(hotelRequest(draft, referencePoints(itin, draft), p));
      setHotels({ ok: true, data: r });
    } catch (e) {
      setHotels({ ok: false, error: (e as Error).message } as Settled<never>);
    } finally {
      setReloadingStays(false);
    }
  };

  const cost = useMemo(() => tripCost(draft, sel, itin), [draft, sel, itin]);
  const issueCount = itin ? itin.validation_issues.filter((i) => i.severity !== "info").length : 0;
  const status = itin?.plan_status ?? "failed";
  const fareCount = (data.out.ok ? data.out.data.options.length : 0) + (data.back.ok ? data.back.data.options.length : 0);
  const stayCount = hotels.ok ? hotels.data.options.length : 0;
  const tipCount = data.tips.ok ? data.tips.data.tips.length || data.tips.data.sources.length : 0;
  const extraLimits = [
    ...(data.out.ok ? data.out.data.limitations : []),
    ...(hotels.ok ? hotels.data.limitations : []),
  ];

  const flightsPanel = (
    <Flights out={data.out} back={data.back} from={from.iata ?? from.city} to={to.iata ?? to.city} start={draft.start} end={draft.end}
      selOut={sel.out} selBack={sel.back} onSelect={pickFlight} busy={busy} />
  );
  const staysPanel = (
    <Stays res={hotels} selected={sel.hotel} onSelect={pickHotel} busy={busy} priority={hotelPriority}
      onPriority={rerankStays} checkIn={draft.start} checkOut={draft.end} reloading={reloadingStays} />
  );
  const tipsPanel = <Tips res={data.tips} city={to.city} />;
  const checksPanel = itin
    ? <Checks itin={itin} request={req} extraLimits={extraLimits} />
    : <Empty title="No plan to check." />;

  const summary = (
    <section className="summary" aria-label="Trip cost">
      <ul className="summary__lines">
        {cost.lines.map((l) => (
          <li key={l.label}>
            <span>{l.label}<small>{l.note}</small></span>
            <strong className="num">{l.amount === null ? "–" : money(l.amount, l.currency)}</strong>
          </li>
        ))}
      </ul>
      <div className="summary__total">
        <span>{cost.complete ? "Trip total" : "So far"}</span>
        <strong className="num">{cost.total === null ? "Mixed currencies" : money(cost.total, draft.currency)}</strong>
      </div>
      {itin?.cost_summary.within_budget === false && (
        <p className="summary__warn">Activities exceed your {money(itin.cost_summary.budget_limit, itin.cost_summary.currency)} budget.</p>
      )}
    </section>
  );

  return (
    <div className="trip">
      <header className="trip__head">
        <button type="button" className="icon-btn" onClick={onEdit} aria-label="Edit trip"><Icon name="back" /></button>
        <div className="trip__title">
          <h1>{to.city}</h1>
          <p className="num">{dateRange(draft.start, draft.end)}, {plural(draft.adults + draft.childAges.length, "traveller")}</p>
        </div>
        <button type="button" className={`status status--${status}`} onClick={() => setTab("checks")}>
          {status === "validated" ? "Validated" : status === "failed" ? "No plan" : "Provisional"}
        </button>
      </header>

      {notice && <div className={`notice notice--${notice.tone}`} role="status">{notice.text}</div>}
      {busy && <div className="progress" aria-label="Updating plan" />}

      {(() => {
        const plan = itin ? (
          <Itinerary itin={itin} request={req} city={to.city} revisedDays={revised} />
        ) : (
          <Empty title="The itinerary couldn't be planned.">
            {data.itin.ok
              ? data.itin.data.limitations.map((l) => <p key={l}>{l}</p>)
              : <p className="num">{data.itin.error}</p>}
            <button type="button" className="btn btn--ghost" onClick={onEdit}>Change the trip</button>
          </Empty>
        );
        if (!wide) {
          return (
            <main className="trip__main">
              {tab === "plan" && <>{summary}{plan}</>}
              {tab === "flights" && flightsPanel}
              {tab === "stays" && staysPanel}
              {tab === "tips" && tipsPanel}
              {tab === "checks" && checksPanel}
            </main>
          );
        }
        const side: Tab = tab === "plan" ? "flights" : tab;
        return (
          <div className="trip__grid">
            <main className="trip__main">{plan}</main>
            <aside className="trip__side" aria-label="Flights, stays, tips and checks">
              {summary}
              <div className="sidetabs" role="tablist">
                {(["flights", "stays", "tips", "checks"] as Tab[]).map((t) => (
                  <button key={t} role="tab" type="button" aria-selected={side === t} onClick={() => setTab(t)}>
                    {t === "flights" ? "Flights" : t === "stays" ? "Stays" : t === "tips" ? "Tips" : "Checks"}
                    <small className="num">{t === "flights" ? fareCount : t === "stays" ? stayCount : t === "tips" ? tipCount : issueCount}</small>
                  </button>
                ))}
              </div>
              <div className="sidetabs__panel" role="tabpanel">
                {side === "flights" && flightsPanel}
                {side === "stays" && staysPanel}
                {side === "tips" && tipsPanel}
                {side === "checks" && checksPanel}
              </div>
            </aside>
          </div>
        );
      })()}

      {!wide && <nav className="tabbar" aria-label="Trip sections">
        {([
          ["plan", "Plan", "plan", null],
          ["flights", "Flights", "plane", sel.out && sel.back ? "✓" : fareCount || null],
          ["stays", "Stays", "bed", sel.hotel ? "✓" : stayCount || null],
          ["tips", "Tips", "chat", tipCount || null],
          ["checks", "Checks", "shield", issueCount || null],
        ] as const).map(([key, label, icon, badge]) => (
          <button key={key} type="button" aria-current={tab === key ? "page" : undefined} onClick={() => { setTab(key); window.scrollTo({ top: 0 }); }}>
            <Icon name={icon} size={22} />
            <span>{label}</span>
            {badge !== null && <small className="num">{badge}</small>}
          </button>
        ))}
      </nav>}
    </div>
  );
}
