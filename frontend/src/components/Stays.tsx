import { useMemo, useState } from "react";
import type { HotelOption, HotelSearchResult } from "../api/types";
import { dateMed, money, num, plural, titleCase } from "../lib/format";
import type { Settled } from "../lib/trip";
import { Chip, Empty } from "./ui";

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
            {h.guest_rating != null && <span className="stay__rating num" title="Guest rating">{h.guest_rating.toFixed(1)}</span>}
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

type Sort = "recommended" | "price_asc" | "price_desc" | "rating" | "stars" | "distance";
type StarBucket = "unrated" | "1-2" | "3" | "4" | "5";

const SORTS: { value: Sort; label: string }[] = [
  { value: "recommended", label: "Recommended" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "rating", label: "Guest rating" },
  { value: "stars", label: "Stars" },
  { value: "distance", label: "Near my stops" },
];
const STAR_BUCKETS: { value: StarBucket; label: string }[] = [
  { value: "unrated", label: "Unrated" }, { value: "1-2", label: "1–2★" },
  { value: "3", label: "3★" }, { value: "4", label: "4★" }, { value: "5", label: "5★" },
];
const RATINGS = [0, 7, 8, 9];

const nightly = (h: HotelOption) => {
  const total = num(h.all_in_price != null ? h.all_in_price : h.total_price) ?? 0;
  return h.nights > 0 ? total / h.nights : total;
};
const bucketOf = (h: HotelOption): StarBucket => {
  const s = h.star_rating ? Math.round(h.star_rating) : 0;
  return s === 0 ? "unrated" : s <= 2 ? "1-2" : (String(Math.min(s, 5)) as StarBucket);
};
const BREAKFAST = new Set<HotelOption["board_type"]>(["breakfast", "half_board", "full_board", "all_inclusive"]);

/** Round a slider bound to a tidy step for the currency's scale. */
const step = (max: number) => (max > 20000 ? 1000 : max > 5000 ? 500 : max > 1000 ? 100 : max > 200 ? 10 : 5);

function useStayFilters(options: HotelOption[]) {
  const [sort, setSort] = useState<Sort>("recommended");
  const [maxNightly, setMaxNightly] = useState<number | null>(null);
  const [stars, setStars] = useState<StarBucket[]>([]);
  const [minRating, setMinRating] = useState(0);
  const [freeCancel, setFreeCancel] = useState(false);
  const [breakfast, setBreakfast] = useState(false);

  const range = useMemo(() => {
    const ps = options.map(nightly).filter((x) => x > 0);
    if (!ps.length) return null;
    const lo = Math.min(...ps), hi = Math.max(...ps), st = step(hi);
    return { lo: Math.floor(lo / st) * st, hi: Math.ceil(hi / st) * st, step: st };
  }, [options]);
  const hasRatings = options.some((h) => h.guest_rating != null);
  const hasDistance = options.some((h) => h.distance_km_to_reference != null);

  const shown = useMemo(() => {
    const out = options.filter((h) =>
      (maxNightly == null || nightly(h) <= maxNightly)
      && (!stars.length || stars.includes(bucketOf(h)))
      && (!minRating || (h.guest_rating ?? 0) >= minRating)
      && (!freeCancel || h.refundable === true)
      && (!breakfast || BREAKFAST.has(h.board_type)));
    const by: Record<Sort, ((a: HotelOption, b: HotelOption) => number) | null> = {
      recommended: null,
      price_asc: (a, b) => nightly(a) - nightly(b),
      price_desc: (a, b) => nightly(b) - nightly(a),
      rating: (a, b) => (b.guest_rating ?? -1) - (a.guest_rating ?? -1) || nightly(a) - nightly(b),
      stars: (a, b) => (b.star_rating ?? -1) - (a.star_rating ?? -1) || nightly(a) - nightly(b),
      distance: (a, b) => (a.distance_km_to_reference ?? 1e9) - (b.distance_km_to_reference ?? 1e9),
    };
    const f = by[sort];
    return f ? [...out].sort(f) : out;
  }, [options, sort, maxNightly, stars, minRating, freeCancel, breakfast]);

  const active = maxNightly != null || stars.length > 0 || minRating > 0 || freeCancel || breakfast;
  const clear = () => { setMaxNightly(null); setStars([]); setMinRating(0); setFreeCancel(false); setBreakfast(false); };
  const budget = () => {
    setSort("price_asc");
    if (range) {
      // Cheapest third of what's available
      const ps = options.map(nightly).sort((a, b) => a - b);
      const cut = ps[Math.max(0, Math.ceil(ps.length / 3) - 1)];
      setMaxNightly(Math.ceil(cut / range.step) * range.step);
    }
  };
  return {
    sort, setSort, maxNightly, setMaxNightly, stars, setStars, minRating, setMinRating,
    freeCancel, setFreeCancel, breakfast, setBreakfast, range, hasRatings, hasDistance, shown, active, clear, budget,
  };
}

function Filters({ f, currency, total }: { f: ReturnType<typeof useStayFilters>; currency: string; total: number }) {
  const [open, setOpen] = useState(false);
  const toggleStar = (b: StarBucket) => f.setStars(f.stars.includes(b) ? f.stars.filter((x) => x !== b) : [...f.stars, b]);
  return (
    <div className="stayfilters">
      <div className="stayfilters__row">
        <label className="stayfilters__sort">
          <span className="sr-only">Sort stays</span>
          <select value={f.sort} onChange={(e) => f.setSort(e.target.value as Sort)}>
            {SORTS.filter((o) => (o.value !== "distance" || f.hasDistance) && (o.value !== "rating" || f.hasRatings))
              .map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <Chip on={f.sort === "price_asc" && f.maxNightly != null} onClick={f.budget}>Budget picks</Chip>
        <Chip on={f.freeCancel} onClick={() => f.setFreeCancel(!f.freeCancel)}>Free cancellation</Chip>
        <Chip on={f.breakfast} onClick={() => f.setBreakfast(!f.breakfast)}>Breakfast included</Chip>
        <button type="button" className="stayfilters__more" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Fewer filters" : "More filters"}
        </button>
      </div>
      {open && (
        <div className="stayfilters__panel">
          {f.range && f.range.hi > f.range.lo && (
            <label className="stayfilters__price">
              <span>Max per night <strong className="num">{f.maxNightly == null ? "Any" : money(f.maxNightly, currency)}</strong></span>
              <input type="range" min={f.range.lo} max={f.range.hi} step={f.range.step}
                value={f.maxNightly ?? f.range.hi}
                onChange={(e) => { const v = Number(e.target.value); f.setMaxNightly(v >= f.range!.hi ? null : v); }} />
              <span className="stayfilters__ends num"><small>{money(f.range.lo, currency)}</small><small>{money(f.range.hi, currency)}</small></span>
            </label>
          )}
          <div className="stayfilters__group" role="group" aria-label="Star rating">
            <span>Stars</span>
            <div className="chips">{STAR_BUCKETS.map((b) => <Chip key={b.value} on={f.stars.includes(b.value)} onClick={() => toggleStar(b.value)}>{b.label}</Chip>)}</div>
          </div>
          {f.hasRatings && (
            <div className="stayfilters__group" role="group" aria-label="Guest rating">
              <span>Guest rating</span>
              <div className="chips">{RATINGS.map((r) => <Chip key={r} on={f.minRating === r} onClick={() => f.setMinRating(r)}>{r ? `${r}+` : "Any"}</Chip>)}</div>
            </div>
          )}
        </div>
      )}
      <p className="stayfilters__count num">
        Showing {f.shown.length} of {plural(total, "stay")}
        {f.active && <> · <button type="button" className="linkbtn" onClick={f.clear}>Clear filters</button></>}
      </p>
    </div>
  );
}

export function Stays({ res, selected, onSelect, busy, checkIn, checkOut, reloading, radiusKm, onSearchWider }: {
  res: Settled<HotelSearchResult>; selected: HotelOption | null; onSelect: (h: HotelOption | null) => void;
  busy: boolean; checkIn: string; checkOut: string; reloading: boolean;
  radiusKm: number; onSearchWider?: () => void;
}) {
  const options = res.ok ? res.data.options : [];
  const f = useStayFilters(options);
  const rejected = res.ok ? Object.entries(res.data.rejected_counts).filter(([, n]) => n > 0) : [];
  const currency = options[0]?.currency ?? "USD";
  const wider = onSearchWider && (
    <p className="limit">
      Searched within {radiusKm} km.{" "}
      <button type="button" className="linkbtn" onClick={onSearchWider} disabled={reloading || busy}>
        {reloading ? "Searching…" : "Search a wider area"}
      </button>
    </p>
  );
  return (
    <div className="panel">
      <div className="panel__bar">
        <span className="num">{dateMed(checkIn)} → {dateMed(checkOut)}</span>
      </div>
      <div className={reloading ? "is-loading" : ""}>
        {!res.ok ? (
          <Empty title="The hotel search failed."><p className="num">{res.error}</p></Empty>
        ) : options.length === 0 ? (
          <Empty title="No stays to show.">
            {res.data.limitations.map((l) => <p key={l}>{l}</p>)}
            {wider}
          </Empty>
        ) : (
          <>
            <Filters f={f} currency={currency} total={options.length} />
            <p className="panel__lede">
              Prices are the whole stay for every room. Picking one moves your daily start point, so every day is re-planned.
            </p>
            {f.shown.length === 0 ? (
              <Empty title="No stays match these filters.">
                <p><button type="button" className="linkbtn" onClick={f.clear}>Clear filters</button></p>
              </Empty>
            ) : (
              <ul className="stays">
                {f.shown.map((h) => (
                  <StayRow key={h.option_id} h={h} disabled={busy} selected={selected?.option_id === h.option_id}
                    onSelect={() => onSelect(selected?.option_id === h.option_id ? null : h)} />
                ))}
              </ul>
            )}
            {wider}
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
