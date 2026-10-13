// How the Metodika tab reads the methodology the API serves (ADR 0023): a value as a reader
// sees it, the steps in their groups, and a formula as MathML. Pure, so it is tested under
// Node against the API's own document (src/lib/fixtures/methodology.json).

import temml from "temml";

import type { MethodGroup, MethodModuleDetail, MethodStepOut, MethodValue } from "./api";

const SUPERSCRIPT: Record<string, string> = {
  "-": "⁻", "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
};
const decimal = new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 6 });

/** A number in Czech notation; a very small one as "1 × 10⁻¹²", never rounded to 0. */
export function showNumber(n: number): string {
  if (n !== 0 && Math.abs(n) < 1e-4) {
    const [mantissa, exponent] = n.toExponential().split("e");
    const power = String(Number(exponent)).replace(/./g, (c) => SUPERSCRIPT[c] ?? c);
    const m = Number(mantissa);
    return `${m === 1 ? "" : `${decimal.format(m)} × `}10${power}`;
  }
  return decimal.format(n);
}

export type ValueWords = { absent: string; none: string; yes: string; no: string };

/** A value as the page shows it. Absent and null are said in words, never shown as 0. */
export function showValue(v: MethodValue, words: ValueWords): string {
  if (v.absent) return words.absent;
  return showPlain(v.value, words);
}

function showPlain(value: unknown, words: ValueWords): string {
  if (value === null || value === undefined) return words.none;
  if (typeof value === "boolean") return value ? words.yes : words.no;
  if (typeof value === "number") return showNumber(value);
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map((x) => (Array.isArray(x) ? `(${showPlain(x, words)})` : showPlain(x, words))).join(", ");
  return JSON.stringify(value);
}

export type GroupedSteps = { group: MethodGroup | null; steps: MethodStepOut[] }[];

/** The steps under their groups in the module's order; without groups, one unnamed block. */
export function groupSteps(detail: MethodModuleDetail): GroupedSteps {
  if (!detail.groups.length) return [{ group: null, steps: detail.step_details }];
  const byId = new Map(detail.step_details.map((s) => [s.id, s]));
  return detail.groups.map((group) => ({
    group,
    steps: group.step_ids.map((id) => byId.get(id)).filter((s): s is MethodStepOut => s !== undefined),
  }));
}

/** A formula as MathML, or null when Temml cannot read it (the page then shows the LaTeX). */
export function formulaMathML(latex: string, display = true): string | null {
  // Typesetting is pure in its input, and the editor redraws every step's formulas on each
  // keystroke: the same LaTeX is typeset once. Bounded: the catalogue has a few hundred.
  const key = `${display ? "D" : "I"}${latex}`;
  const cached = TYPESET.get(key);
  if (cached !== undefined) return cached;
  let mathml: string | null;
  try {
    mathml = temml.renderToString(latex, { displayMode: display, throwOnError: true, trust: false, strict: false });
  } catch {
    mathml = null;
  }
  if (TYPESET.size >= TYPESET_LIMIT) TYPESET.clear();
  TYPESET.set(key, mathml);
  return mathml;
}
const TYPESET = new Map<string, string | null>();
const TYPESET_LIMIT = 2000;
