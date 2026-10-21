// A bounded number as a person types it (input-interactions I2, I9): the pure part of Stepper.
// A typed value is read in Czech (a decimal comma, spaces between thousands) and is either
// accepted as it is or refused with its reason. It is never clamped, rounded or replaced: a value
// out of range is said at the field and not saved (audit IA-1: 20 stored as 50, silently).

import { t, tv } from "@/i18n/t";

export type NumberBounds = {
  min: number;
  max: number;
  /** What one press of − / + moves (default 1); Shift moves ten of them. */
  step?: number;
  /** Decimal places a value may carry (default 0: whole numbers only). */
  decimals?: number;
};

export type NumberProblem =
  | { kind: "empty" }
  | { kind: "notNumber"; raw: string }
  | { kind: "ambiguous"; raw: string }
  | { kind: "tooPrecise"; decimals: number }
  | { kind: "outOfRange"; value: number };

export type NumberReading = { ok: true; value: number } | { ok: false; problem: NumberProblem };

// Spaces a person (or a pasted Czech figure) puts between thousands: space, NBSP, narrow NBSP.
const GROUPING = /[\s  ]/g;
const NUMERAL = /^-?\d+(?:\.(\d+))?$/;
const AMBIGUOUS_DOT = /^-?\d+\.\d{3}$/;
// Minus signs a value can carry back into the field: formatNumber's own U+2212, and the dashes a
// pasted figure or a keyboard's autocorrect writes for it (figure dash, en dash, small and
// full-width hyphen-minus). Each is read as "-", so a displayed negative value edits and saves.
const MINUS = /[−‒–﹣－]/g;

/** A typed value read against its bounds: the number as typed, or why it is refused. */
export function readNumber(raw: string, bounds: NumberBounds): NumberReading {
  const text = raw.replace(GROUPING, "").replace(MINUS, "-").replace(",", ".");
  if (!text) return { ok: false, problem: { kind: "empty" } };
  // "1.000" is a thousand to a Czech eye and one to an English one; "1.250" likewise. A dot with
  // exactly three digits after it is refused as ambiguous, never guessed (review of #532).
  if (AMBIGUOUS_DOT.test(raw.replace(GROUPING, "").replace(MINUS, "-"))) return { ok: false, problem: { kind: "ambiguous", raw: raw.trim() } };
  const m = NUMERAL.exec(text);
  if (!m) return { ok: false, problem: { kind: "notNumber", raw: raw.trim() } };
  const decimals = bounds.decimals ?? 0;
  // "5,0" is five: trailing zeros carry no precision the value does not have.
  const places = (m[1] ?? "").replace(/0+$/, "").length;
  if (places > decimals) return { ok: false, problem: { kind: "tooPrecise", decimals } };
  const value = Number(text);
  if (value < bounds.min || value > bounds.max) return { ok: false, problem: { kind: "outOfRange", value } };
  return { ok: true, value };
}

/**
 * Where one press of − (`direction` -1) or + (+1) takes `value`; `big` is Shift (×10). A press
 * that would cross a bound stops on it, and a value outside the range moves to the nearer bound
 * in the direction pressed: the button shows what it sets, so nothing is set unseen. Null when
 * the button has nowhere to go (it is drawn disabled).
 */
export function stepNumber(value: number | null, direction: 1 | -1, bounds: NumberBounds, big = false): number | null {
  const step = (bounds.step ?? 1) * (big ? 10 : 1);
  if (value === null || !Number.isFinite(value)) return direction > 0 ? bounds.min : bounds.max;
  if (direction > 0 && value >= bounds.max) return null;
  if (direction < 0 && value <= bounds.min) return null;
  let next = value + direction * step;
  if (next > bounds.max) next = bounds.max;
  if (next < bounds.min) next = bounds.min;
  return fix(next, bounds.decimals ?? 0);
}

/** Whether − / + can move from `value` at all. */
export function canStep(value: number | null, direction: 1 | -1, bounds: NumberBounds): boolean {
  return stepNumber(value, direction, bounds) !== null;
}

// 0.1 + 0.2 is not 0.3 in binary; a step lands on the decimals the value may carry.
function fix(v: number, decimals: number): number {
  return Number(v.toFixed(decimals));
}

/**
 * A number as Czech prints it: a decimal comma, a no-break space between thousands from 1 000.
 * Written here rather than by Intl.NumberFormat, so the characters do not depend on the ICU data a
 * runtime ships (a small-ICU build falls back to English "5,000"). `decimals` fixes the places
 * shown; omitted, the value's own.
 */
export function formatNumber(value: number, decimals?: number): string {
  const text = decimals === undefined ? String(value) : value.toFixed(decimals);
  const negative = text.startsWith("-");
  const [whole, fraction] = (negative ? text.slice(1) : text).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return `${negative ? "−" : ""}${grouped}${fraction ? `,${fraction}` : ""}`;
}

/** The bounds as stated beside a field: "50–5 000", with a unit when one is given. */
export function rangeWords(bounds: NumberBounds, unit?: string): string {
  const d = bounds.decimals ?? 0;
  const show = (v: number) => formatNumber(v, Number.isInteger(v) ? undefined : d);
  return `${show(bounds.min)}–${show(bounds.max)}${unit ? ` ${unit}` : ""}`;
}

/** Why a typed value was not saved, in words, at the field. */
export function numberProblemWords(problem: NumberProblem, bounds: NumberBounds, unit?: string): string {
  const range = rangeWords(bounds, unit);
  switch (problem.kind) {
    case "empty":
      return tv("input.number.empty", { range });
    case "notNumber":
      return tv("input.number.notNumber", { raw: problem.raw });
    case "ambiguous":
      return tv("input.number.ambiguous", { raw: problem.raw });
    case "tooPrecise":
      if (problem.decimals === 0) return t("input.number.notInteger");
      if (problem.decimals === 1) return t("input.number.oneDecimal");
      return tv("input.number.tooPrecise", { decimals: problem.decimals });
    case "outOfRange":
      return tv("input.number.outOfRange", { range });
  }
}
