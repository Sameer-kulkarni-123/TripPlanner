import { useState } from "react";
import type { HotelOption, HotelPriority, HotelSearchResult } from "../api/types";
import { dateMed, money, num, plural, titleCase } from "../lib/format";
import type { Settled } from "../lib/trip";
import { Empty, Segmented } from "./ui";

const BOARD: Record<HotelOption["board_type"], string> = {
  room_only: "Room only",
  breakfast: "Breakfast",
  half_board: "Half board",
  full_board: "Full board",
  all_inclusive: "All inclusive",
  unknown: "",
};

const REJECT: Record<string, string> = {
  max_total_price: "over budget",
  max_price_per_night: "over nightly limit",
  min_star_rating: "below star minimum",
  refundable_only: "not refundable",
  required_board_types: "wrong meal plan",
  occupancy: "too small",
  max_distance_km: "too far",
  required_amenities: "missing amenities",
};

function Photo({ h }: { h: HotelOption }) {
  const [broken, setBroken] = useState(false);
  if (!h.main_photo_url || broken) {
    return <div className="stay__photo stay__photo--none" aria-hidden="true">{h.hotel_name.slice(0, 1)}</div>;
  }
  return <img className="stay__photo" src={h.main_photo_url} alt="" loading="lazy" onError={() => setBroken(true)} />;
}

function StayRow({ h, selected, onSelect, disabled }: { h: HotelOption; selected: boolean; onSelect: () => void; disabled: boolean }) {
  const excluded = num(h.excluded_charges_total) ?? 0;
  const price = h.all_in_price != null ? h.all_in_price : h.total_price;
  return (
    <li>
      <button type="button" className={`stay ${selected ? "is-selected" : ""}`} aria-pressed={selected} onClick={onSelect} disabled={disabled}>
        <Photo h={h} />
        <span className="radio" aria-hidden="true" />
        <div className="stay__body">
          <div className="stay__top">
            <h3>{h.hotel_name}</h3>
            {h.star_rating ? <span className="stay__stars" aria-label={`${h.star_rating} stars`}>{"★".repeat(Math.round(h.star_rating))}</span> : null}
          </div>
          <p className="stay__room">{[h.room_name, BOARD[h.board_type]].filter(Boolean).join(", ")}</p>
          <p className={`stay__cancel ${h.refundable ? "is-ok" : h.refundable === false ? "is-no" : ""}`}>
            {h.refundable && h.free_cancellation_until
              ? `Free cancellation until ${dateMed(h.free_cancellation_until)}`
              : h.cancellation_summary ?? "Cancellation terms not provided"}
          </p>
          {h.distance_km_to_reference != null && (
            <p className="stay__dist num" title="Average straight-line distance to the stops in your plan, not travel time">
              {h.distance_km_to_reference.toFixed(1)} km from your stops
            </p>
          )}
        </div>
        <div className="stay__price">
          <strong className="num">{money(price, h.currency)}</strong>
          <small>{plural(h.nights, "night")}{excluded ? ", all-in" : ""}</small>
          <small className="num">{money(h.price_per_night, h.currency)}/night</small>
        </div>
        {h.warnings.length > 0 && (
          <ul className="stay__warn">{h.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        )}
      </button>
    </li>
  );
}

export function Stays({ res, selected, onSelect, busy, priority, onPriority, checkIn, checkOut, reloading }: {
  res: Settled<HotelSearchResult>; selected: HotelOption | null; onSelect: (h: HotelOption | null) => void;
  busy: boolean; priority: HotelPriority; onPriority: (p: HotelPriority) => void;
  checkIn: string; checkOut: string; reloading: boolean;
}) {
  const rejected = res.ok ? Object.entries(res.data.rejected_counts).filter(([, n]) => n > 0) : [];
  return (
    <div className="panel">
      <div className="panel__bar">
        <span className="num">{dateMed(checkIn)} → {dateMed(checkOut)}</span>
        <Segmented size="sm" label="Rank stays by" value={priority} onChange={onPriority} options={[
          { value: "balanced", label: "Balanced" }, { value: "cheapest", label: "Price" },
          { value: "location", label: "Near stops" }, { value: "best_rated", label: "Stars" },
        ]} />
      </div>
      <div className={reloading ? "is-loading" : ""}>
        {!res.ok ? (
          <Empty title="The hotel search failed."><p className="num">{res.error}</p></Empty>
        ) : res.data.options.length === 0 ? (
          <Empty title="No stays to show.">
            {res.data.limitations.map((l) => <p key={l}>{l}</p>)}
          </Empty>
        ) : (
          <>
            <p className="panel__lede">
              Prices are the whole stay for every room. Picking one moves your daily start point, so every day is re-planned.
            </p>
            <ul className="stays">
              {res.data.options.map((h) => (
                <StayRow key={h.option_id} h={h} disabled={busy} selected={selected?.option_id === h.option_id}
                  onSelect={() => onSelect(selected?.option_id === h.option_id ? null : h)} />
              ))}
            </ul>
            {rejected.length > 0 && (
              <p className="limit">Filtered out: {rejected.map(([k, n]) => `${n} ${REJECT[k] ?? titleCase(k)}`).join(", ")}.</p>
            )}
            {res.data.limitations.map((l) => <p key={l} className="limit">{l}</p>)}
          </>
        )}
      </div>
    </div>
  );
}
