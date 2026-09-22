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
