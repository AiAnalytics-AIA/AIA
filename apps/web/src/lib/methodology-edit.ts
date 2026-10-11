// Editing a methodology in the Metodika tab (ADR 0023, plan S4a): the pure part. An edit is the
// whole specification of a preset or a stored version, with the fields the methodologist
// changed, and the formula expressions they replace. Nothing here decides whether an edit is
// valid: the API asks the domain (POST .../check) and the page shows its answer field by field.
// What this module does is keep the specification exact -- a value keeps its own type, a
// field the base omits is not invented, and nothing but the changed fields moves.

import type { MethodModuleDetail, MethodStepOut } from "./api";

/** One editable field: a specification leaf a step reads, as the catalogue names it. */
export type EditField = { reference: string; label_cs: string; unit: string };

/** The fields and formula slots of each step that has any, in computation order. */
export function editableSteps(detail: MethodModuleDetail): { step: MethodStepOut; fields: EditField[] }[] {
  return detail.step_details
    .map((step) => ({
      step,
      fields: step.values
        .filter((v) => v.origin === "specification" && !v.absent)
        .map(({ reference, label_cs, unit }) => ({ reference, label_cs, unit })),
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
 *  comma; nothing is coerced across types, so "30" never becomes a text where a number was. */
export function fromInput(original: unknown, raw: string): Parsed {
  if (typeof original === "string") return { ok: true, value: raw };
  const text = raw.trim();
  if (typeof original === "number") {
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
