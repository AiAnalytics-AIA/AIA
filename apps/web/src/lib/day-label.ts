// A feed's day dividers: before the first entry of each calendar day, "Dnes", "Včera", the
// weekday and date within the past week, else the date. The viewer's local day, never UTC; an
// unknown or invalid moment has no day and gets no divider, never "Dnes".

const DAY_MS = 86_400_000;
const date = new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "long", year: "numeric" });
const weekday = new Intl.DateTimeFormat("cs-CZ", { weekday: "long" });

function parse(at: Date | number | string | null | undefined): Date | null {
  if (at === null || at === undefined || at === "") return null;
  const d = at instanceof Date ? at : new Date(at);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** The local calendar day as a key ("2026-10-21"), or null for an unknown moment. */
export function dayKey(at: Date | number | string | null | undefined): string | null {
  const d = parse(at);
  if (!d) return null;
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Whole local calendar days from ``d`` to ``now``: DST-proof, since it compares dates, not hours. */
function daysBefore(d: Date, now: Date): number {
  const day = (x: Date) => Date.UTC(x.getFullYear(), x.getMonth(), x.getDate());
  return Math.round((day(now) - day(d)) / DAY_MS);
}

/** The divider's words for ``at``'s day as seen at ``now``, or null for an unknown moment. */
export function dayLabel(at: Date | number | string | null | undefined, now: Date = new Date()): string | null {
  const d = parse(at);
  if (!d) return null;
  const ago = daysBefore(d, now);
  if (ago === 0) return "Dnes";
  if (ago === 1) return "Včera";
  if (ago > 1 && ago < 7) return `${weekday.format(d)} ${date.format(d)}`;
  return date.format(d);
}

export type DayBreak = { kind: "day"; key: string; label: string };

/** ``items`` with a day divider before the first of each local day; an item with no day breaks
 * nothing and keeps its place. */
export function withDayBreaks<T>(
  items: readonly T[],
  at: (item: T) => Date | number | string | null | undefined,
  now: Date = new Date(),
): (T | DayBreak)[] {
  const out: (T | DayBreak)[] = [];
  let last: string | null = null;
  for (const item of items) {
    const key = dayKey(at(item));
    const label = key === null ? null : dayLabel(at(item), now);
    if (key !== null && label !== null && key !== last) {
      out.push({ kind: "day", key, label });
      last = key;
    }
    out.push(item);
  }
  return out;
}

export function isDayBreak<T>(x: T | DayBreak): x is DayBreak {
  return typeof x === "object" && x !== null && (x as { kind?: unknown }).kind === "day" && "label" in x;
}
