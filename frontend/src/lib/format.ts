import type { Money } from "../api/types";

export const num = (v: Money | null | undefined): number | null =>
  v === null || v === undefined || v === "" ? null : Number(v);

const SYMBOL: Record<string, string> = { USD: "$", EUR: "€", GBP: "£", INR: "₹" };

export function money(v: Money | null | undefined, currency: string, opts: { decimals?: boolean } = {}): string {
  const n = num(v);
  if (n === null || Number.isNaN(n)) return "–";
  const decimals = opts.decimals ?? (n % 1 !== 0 && n < 1000);
  const body = n.toLocaleString(currency === "INR" ? "en-IN" : "en-US", {
    minimumFractionDigits: decimals ? 2 : 0,
    maximumFractionDigits: decimals ? 2 : 0,
  });
  const sym = SYMBOL[currency];
  return sym ? `${sym}${body}` : `${body} ${currency}`;
}

/**
 * Wall-clock time from an ISO string *as written by the API*. The itinerary returns
 * destination-local times with an offset; we must not convert them to the viewer's zone.
 */
export const hhmm = (iso: string | null | undefined): string => (iso ? iso.slice(11, 16) : "--:--");

/** "2026-11-20" (or an ISO datetime) -> parts without any time-zone conversion */
function ymd(iso: string) {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return { y, m, d, date: new Date(Date.UTC(y, m - 1, d)) };
}

export const dayShort = (iso: string) =>
  ymd(iso).date.toLocaleDateString("en-GB", { weekday: "short", timeZone: "UTC" });
export const dayNum = (iso: string) => ymd(iso).d;
export const monthShort = (iso: string) =>
  ymd(iso).date.toLocaleDateString("en-GB", { month: "short", timeZone: "UTC" });
export const dateLong = (iso: string) =>
  ymd(iso).date.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
export const dateMed = (iso: string) =>
  ymd(iso).date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });

export function dateRange(a: string, b: string): string {
  const A = ymd(a), B = ymd(b);
  const mA = monthShort(a), mB = monthShort(b);
  if (A.y === B.y && A.m === B.m) return `${A.d}–${B.d} ${mA}`;
  return `${A.d} ${mA} – ${B.d} ${mB}`;
}

export function daysBetween(a: string, b: string): number {
  return Math.round((ymd(b).date.getTime() - ymd(a).date.getTime()) / 86400000);
}

export function addDays(iso: string, n: number): string {
  const d = ymd(iso).date;
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function todayISO(): string {
  const d = new Date();
  return new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())).toISOString().slice(0, 10);
}

export function duration(min: number): string {
  if (!min && min !== 0) return "–";
  const h = Math.floor(min / 60), m = min % 60;
  if (!h) return `${m} min`;
  return m ? `${h}h ${String(m).padStart(2, "0")}` : `${h}h`;
}

export function coord(lat: number, lon: number): string {
  const f = (v: number, p: string, n: string) => `${Math.abs(v).toFixed(4)}° ${v >= 0 ? p : n}`;
  return `${f(lat, "N", "S")}  ${f(lon, "E", "W")}`;
}

/** Demo activities are named "Rome: Old Town walking tour (demo)" — show the title, flag the source. */
export function activityTitle(title: string, isDemo: boolean, city?: string): string {
  if (!isDemo) return title;
  let t = title.replace(/\s*\(demo\)\s*$/i, "");
  if (city && t.startsWith(`${city}: `)) t = t.slice(city.length + 2);
  return t;
}

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export const titleCase = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
