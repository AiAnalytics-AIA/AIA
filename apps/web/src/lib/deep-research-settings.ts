// How the Deep Research settings tab reads and writes a policy value (ADR 0022).
//
// The catalogue and every rule about a value are the API's (aia_core
// domain/deep_research/settings.py): its type, its bounds, whether a cap may only be
// lowered. The page only turns what a person typed into the JSON shape of the type --
// a whole number, a decimal, yes/no, a list of lines -- and lets the API refuse the
// rest, shown as it said it. A value the code does not hold is unknown, never zero.

import type { DrSetting, DrSettingValue, DrSettingsOverview } from "@/lib/api";

/** The form control a setting's type is edited with. */
export type InputKind = "whole" | "decimal" | "decision" | "status" | "lines" | "date" | "url" | "text";

const KINDS: Record<string, InputKind> = {
  integer: "whole",
  days: "whole",
  usd: "decimal",
  decision: "decision",
  status: "status",
  host_list: "lines",
  pattern_list: "lines",
  date: "date",
  url: "url",
  text: "text",
  model_id: "text",
};

/** A type the page does not know is edited as text; the API still checks it. */
export function inputKind(type: string): InputKind {
  return KINDS[type] ?? "text";
}

/** The values a status setting takes, in order: proposed is recorded, only approved signs off. */
export const STATUS_VALUES = ["proposed", "approved"] as const;

export type Parsed = { ok: true; value: DrSettingValue } | { ok: false; reason: "empty" | "not_whole" | "not_number" };

/** What a person typed, as the JSON the API expects for `type`. Bounds are the API's to check. */
export function parseInput(type: string, raw: string): Parsed {
  const kind = inputKind(type);
  if (kind === "lines") {
    // One entry per line; blank lines dropped. An empty list is a value (no extra hosts).
    return { ok: true, value: raw.split(/\r?\n/).map((s) => s.trim()).filter(Boolean) };
  }
  const text = raw.trim();
  if (!text) return { ok: false, reason: "empty" };
  if (kind === "whole") {
    return /^\d+$/.test(text) ? { ok: true, value: Number(text) } : { ok: false, reason: "not_whole" };
  }
  if (kind === "decimal") {
    // Czech writes the decimal comma; the API takes a JSON number.
    const normal = text.replace(/\s/g, "").replace(",", ".");
    return /^\d+(\.\d+)?$/.test(normal) ? { ok: true, value: Number(normal) } : { ok: false, reason: "not_number" };
  }
  if (kind === "decision") return { ok: true, value: text === "true" };
  return { ok: true, value: text };
}

/** A value as the form shows it before editing: what is in force, or empty when unknown. */
export function toInput(type: string, value: DrSettingValue): string {
  if (value === null) return inputKind(type) === "status" ? STATUS_VALUES[0] : inputKind(type) === "decision" ? "false" : "";
  if (Array.isArray(value)) return value.join("\n");
  return String(value);
}

/** The settings still missing for live, in the catalogue's order. */
export function missingForLive(overview: DrSettingsOverview): DrSetting[] {
  const missing = new Set(overview.missing_for_live);
  return overview.settings.filter((s) => missing.has(s.key));
}

/** The catalogue's groups, in the order its settings come. */
export function groupsInOrder(settings: DrSetting[]): { group: string; settings: DrSetting[] }[] {
  const groups = new Map<string, DrSetting[]>();
  for (const s of settings) groups.set(s.group, [...(groups.get(s.group) ?? []), s]);
  return [...groups].map(([group, list]) => ({ group, settings: list }));
}
