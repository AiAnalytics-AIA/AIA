/** Czech number formatting. Tabular figures come from the face; the unit is always explicit. */
const cache = new Map<string, Intl.NumberFormat>();
function nf(min: number, max: number) {
  const k = `${min}:${max}`;
  let f = cache.get(k);
  if (!f) { f = new Intl.NumberFormat("cs-CZ", { minimumFractionDigits: min, maximumFractionDigits: max }); cache.set(k, f); }
  return f;
}
export function formatNumber(v: number, digits?: number): string {
  return digits == null ? nf(0, 2).format(v) : nf(digits, digits).format(v);
}
export function formatMoney(v: number, currency: string, digits = 2): string {
  return `${nf(digits, digits).format(v)} ${currency}`;
}
export function formatPercent(v: number, digits = 1): string {
  return `${nf(digits, digits).format(v)} %`;
}

const dtf = new Intl.DateTimeFormat("cs-CZ", { dateStyle: "short", timeStyle: "short", timeZone: "Europe/Prague" });
/**
 * An API timestamp in Prague time, or null when it is absent or unparseable — the
 * caller renders null as "chybí", never as a made-up date. The zone is fixed so
 * the server render and the browser agree.
 */
export function formatDateTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : dtf.format(d);
}
