// Editing a methodology in the Metodika tab (ADR 0023, plan S4a): the pure part. An edit is the
// whole specification of a preset or a stored version, with the fields the methodologist
// changed, and the formula expressions they replace. Nothing here decides whether an edit is
// valid: the API asks the domain (POST .../check) and the page shows its answer field by field.
// What this module does is keep the specification exact -- a value keeps its own type, a
// field the base omits is not invented, and nothing but the changed fields moves.

import type { MethodBound, MethodModuleDetail, MethodStepOut, MethodValue } from "./api";

/** A rule's reading with each `{dotted.path}` replaced by its draft value: a whole number in
 *  Czech groups (10 000), anything else as typed; a path with no value stays as written. */
export function fillReading(reading: string, value: (path: string) => string | undefined): string {
  return reading.replace(/\{([^{}]+)\}/g, (whole, path: string) => {
    const raw = value(path);
    if (raw === undefined || raw.trim() === "") return whole;
    const n = Number(raw.trim());
    return Number.isInteger(n) ? n.toLocaleString("cs-CZ") : raw.trim();
  });
}

/** One editable field: a specification leaf a step reads, as the catalogue names it, with the
 *  range its check holds it to (null: none does). */
export type EditField = { reference: string; label_cs: string; unit: string; effect: MethodValue["effect"]; bound: MethodBound | null };

/** One side of a bound as it stands under the draft: the limit, and whether it is itself outside. */
export type BoundSide = { at: number; strict: boolean };

/** A field's text read as a number, the decimal comma or point; null for anything else. */
function numberOf(raw: string | undefined): number | null {
  if (raw === undefined || raw.trim() === "") return null;
  const n = Number(raw.trim().replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

/**
 * The bound on each side under the draft (settings-redesign F13): the tightest limit, a limit read
 * from another field taken from that field's draft value. A strict limit on a whole number reads as
 * the next whole one (> 20 is ≥ 21). A reference whose draft is not a number is left out: the
 * check still runs, and says so. Never a limit the API did not send.
 */
export function boundUnder(bound: MethodBound, value: (path: string) => string | undefined): { low: BoundSide | null; high: BoundSide | null } {
  const sides: { low: BoundSide | null; high: BoundSide | null } = { low: null, high: null };
  for (const limit of bound.limits) {
    let at = limit.reference !== null ? numberOf(value(limit.reference)) : limit.value;
    if (at === null) continue;
    let strict = limit.strict;
    if (strict && bound.whole) { at = limit.side === "low" ? Math.floor(at) + 1 : Math.ceil(at) - 1; strict = false; }
    const held = sides[limit.side];
    const tighter = !held || (limit.side === "low" ? at > held.at || (at === held.at && strict) : at < held.at || (at === held.at && strict));
    if (tighter) sides[limit.side] = { at, strict };
  }
  return sides;
}

const czech = (n: number) => n.toLocaleString("cs-CZ", { maximumFractionDigits: 12 });

/** A bound in words, as the prototype writes it beside a field: "mez 0–3", "mez ≥ 1", "mez > 0 a ≤ 1";
 *  empty when neither side stands. */
export function boundWords(sides: { low: BoundSide | null; high: BoundSide | null }): string {
  const { low, high } = sides;
  if (low && high && !low.strict && !high.strict) return `mez ${czech(low.at)}–${czech(high.at)}`;
  const parts = [low ? `${low.strict ? ">" : "≥"} ${czech(low.at)}` : "", high ? `${high.strict ? "<" : "≤"} ${czech(high.at)}` : ""].filter(Boolean);
  return parts.length ? `mez ${parts.join(" a ")}` : "";
}

/** Whether the field's text is a number outside the bound; text that is not a number is the
 *  check's to refuse, never called outside here. */
export function outsideBound(sides: { low: BoundSide | null; high: BoundSide | null }, raw: string): boolean {
  const n = numberOf(raw);
  if (n === null) return false;
  const { low, high } = sides;
  return (low !== null && (low.strict ? n <= low.at : n < low.at)) || (high !== null && (high.strict ? n >= high.at : n > high.at));
}

/** The fields and formula slots of each step that has any, in computation order. */
export function editableSteps(detail: MethodModuleDetail): { step: MethodStepOut; fields: EditField[] }[] {
  return detail.step_details
    .map((step) => ({
      step,
      fields: step.values
        .filter((v) => v.origin === "specification" && !v.absent)
        .map(({ reference, label_cs, unit, effect, bound }) => ({ reference, label_cs, unit, effect: effect ?? "", bound: bound ?? null })),
    }))
    .filter(({ step, fields }) => fields.length > 0 || step.formulas.length > 0);
}

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** The value at a dotted path; `undefined` where the path does not exist. */
export function readPath(root: unknown, path: string): unknown {
  let node: unknown = root;
  for (const part of path.split(".")) {
    if (!isRecord(node) || !(part in node)) return undefined;
    node = node[part];
  }
  return node;
}

/** A copy of `root` with the value at an existing dotted path replaced. A path the base does
 *  not have is refused, never created: an edit does not invent a part of the method. */
export function withPath(root: Record<string, unknown>, path: string, value: unknown): Record<string, unknown> {
  const [head, ...rest] = path.split(".");
  if (!(head in root)) throw new Error(`no field ${path}`);
  if (!rest.length) return { ...root, [head]: value };
  const child = root[head];
  if (!isRecord(child)) throw new Error(`no field ${path}`);
  return { ...root, [head]: withPath(child, rest.join("."), value) };
}

/** How a value is typed into a field: text as itself, anything else as JSON. */
export function toInput(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

export type Parsed = { ok: true; value: unknown } | { ok: false; reason: "number" | "boolean" | "json" };

/** A typed value read back with the type the base value has. A number accepts a Czech decimal
 *  comma; nothing is coerced across types, so "30" never becomes a text where a number was.
 *  A number may also be cleared to `null` (a line no longer checked, plan G1d): whether the
 *  specification allows that is the domain's to say, as for every other value. */
export function fromInput(original: unknown, raw: string): Parsed {
  if (typeof original === "string") return { ok: true, value: raw };
  const text = raw.trim();
  if (typeof original === "number") {
    if (text === "null") return { ok: true, value: null };
    const n = text === "" ? Number.NaN : Number(text.replace(",", "."));
    return Number.isFinite(n) ? { ok: true, value: n } : { ok: false, reason: "number" };
  }
  if (typeof original === "boolean") {
    if (text === "true" || text === "false") return { ok: true, value: text === "true" };
    return { ok: false, reason: "boolean" };
  }
  try {
    return { ok: true, value: JSON.parse(text) as unknown };
  } catch {
    return { ok: false, reason: "json" };
  }
}

/** Every dotted leaf where `next` differs from `base`, in a stable order. */
export function changedPaths(base: unknown, next: unknown, prefix = ""): string[] {
  if (isRecord(base) && isRecord(next)) {
    const keys = [...new Set([...Object.keys(base), ...Object.keys(next)])].sort();
    return keys.flatMap((k) => changedPaths(base[k], next[k], prefix ? `${prefix}.${k}` : k));
  }
  return JSON.stringify(base) === JSON.stringify(next) ? [] : [prefix];
}

/** The domain's problems that belong to a field: its own key, or a key inside it. */
export function problemsFor(problems: Record<string, string>, key: string): string[] {
  return Object.entries(problems)
    .filter(([k]) => k === key || k.startsWith(`${key}.`))
    .map(([k, message]) => (k === key ? message : `${k.slice(key.length + 1)}: ${message}`));
}

/** The problems no field on the page shows (a field outside the catalogue, the module, the
 *  base): said once, above the form, so none is lost. */
export function unplacedProblems(problems: Record<string, string>, placed: string[]): [string, string][] {
  return Object.entries(problems).filter(([k]) => !placed.some((p) => k === p || k.startsWith(`${p}.`)));
}
