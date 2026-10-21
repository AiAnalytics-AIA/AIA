// The questionnaire's length on Dotazník (artifact-questionnaire QST7; the product owner, QQ1 (a),
// 2026-10-21): an estimate by a declared rule, seconds per answer of each question type and per
// object of a tracked set, whose constants the methodology owner sets on Metodika. AIA stores no
// duration, so without a rule there is no length: the rule unset is said, never a number assumed;
// an item of a type the rule does not price leaves the total unknown, never counted as zero.

import type { ResearchProject } from "./model";
import { sections } from "./questionnaire";

/** What a rule prices: each question type the compiler knows, and one object of a tracked set. */
export const PRICED = ["vyber", "multi", "skala", "otevrena", "set_object"] as const;
export type Priced = (typeof PRICED)[number];

/** The rule as Metodika states it: seconds per answer, and the methodology version it is from. */
export type LengthRule = { seconds: Record<Priced, number>; version: string };

export type Length =
  | { kind: "unset" }
  | { kind: "unknown"; unpriced: number }
  | { kind: "estimate"; seconds: number; minutes: number; rule: LengthRule };

const texts = (raw: unknown): string[] =>
  Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string" && x.trim() !== "").map((x) => x.trim()) : [];

/**
 * A question's type as the compiler reads it (research_design.py:731, `_text(raw.get("typ") or
 * "vyber")`): none or empty is a single choice; anything but the four types is not priced.
 */
function typeOf(raw: unknown): Exclude<Priced, "set_object"> | null {
  if (raw === undefined || raw === null || raw === "" || raw === false || raw === 0) return "vyber";
  const typ = typeof raw === "string" ? raw.trim() : "";
  return typ === "vyber" || typ === "multi" || typ === "skala" || typ === "otevrena" ? typ : null;
}

/** A rule read from the server, kept only when every price is a finite number of seconds, 0 or more. */
export function readRule(raw: unknown): LengthRule | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as { seconds?: unknown; version?: unknown };
  if (typeof r.version !== "string" || !r.seconds || typeof r.seconds !== "object") return null;
  const s = r.seconds as Record<string, unknown>;
  const seconds = {} as Record<Priced, number>;
  for (const k of PRICED) {
    const v = s[k];
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0) return null;
    seconds[k] = v;
  }
  return { seconds, version: r.version };
}

/**
 * The questionnaire's length under `rule`: every question a respondent answers at its type's price,
 * every distinct object of a tracked set at the set price (the items the strip counts, coverageOf).
 * Minutes rounded to the half minute; the seconds are the sum as stated.
 */
export function questionnaireLength(p: ResearchProject, rule: LengthRule | null): Length {
  if (!rule) return { kind: "unset" };
  let seconds = 0;
  let unpriced = 0;
  for (const s of sections(p)) {
    const kind = s.type || "questions";
    if (kind === "object_battery") seconds += new Set(texts(s.objects)).size * rule.seconds.set_object;
    else if (kind === "questions")
      for (const q of s.questions || []) {
        const typ = typeOf(q.typ);
        if (typ) seconds += rule.seconds[typ];
        else unpriced += 1;
      }
  }
  if (unpriced) return { kind: "unknown", unpriced };
  return { kind: "estimate", seconds, minutes: Math.round(seconds / 30) / 2, rule };
}
