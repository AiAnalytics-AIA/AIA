// Návrh's own part of the Lead contract (artifact-design DSN1): the elements it lets the Lead name,
// built from its items, and where each sits on the screen. The contract itself -- view operations,
// target kinds, starts, hand-offs -- is ARTIFACTS.design (lib/workbench-artifacts.ts); this file
// never redeclares it, and refuses a kind that row does not list. Pure.

import { ARTIFACTS, type TargetKind, aiaId, allowsView, parseAiaId } from "@/lib/workbench-artifacts";

export const DESIGN = ARTIFACTS.design;

/** The kinds Návrh's items carry; each must be in DESIGN.targets (checked by its test). */
export type DesignKind = Extract<TargetKind, "plan" | "rq" | "hypothesis" | "set" | "assumption">;

/** Návrh's five section anchors, `plan:<part>`, and the element each is drawn as (PlanStep). */
export const PLAN_PARTS = {
  narrative: "plan-understanding",
  variants: "plan-variants",
  sets: "plan-sets",
  questions: "plan-questions",
  comments: "plan-comments",
} as const;
export type PlanPart = keyof typeof PLAN_PARTS;

const isDesignKind = (kind: string): kind is DesignKind => (DESIGN.targets as readonly string[]).includes(kind);

/**
 * The `data-aia` id of one of Návrh's elements. A kind the design row does not list is refused, never
 * sent. `rq` (and the other items) take the item's stable id from the working copy
 * (working-copy-edit-ops#WCE1), never its position: a position moves when the list is reordered.
 */
export function designTarget(kind: DesignKind, id: string): string {
  if (!isDesignKind(kind)) throw new Error(`designTarget: ${kind} is not a Návrh target`);
  if (kind === "plan" && !(id in PLAN_PARTS)) throw new Error(`designTarget: plan:${id} is not a section of Návrh`);
  return aiaId(kind, id);
}

/**
 * An objective shown on Návrh: the Brief's `objective:<id>` (the brief row owns the kind), so the
 * Lead names one objective by one target on both screens. `id` is the objective's stable item id.
 */
export const objectiveTarget = (id: string): string => aiaId("objective", id);

/** A section anchor's `data-aia` id. */
export const planTarget = (part: PlanPart): string => designTarget("plan", part);

/** The element a `plan:<part>` target opens on, or null for one Návrh does not draw. */
export function sectionElement(target: string): string | null {
  const parsed = parseAiaId(target);
  if (!parsed || parsed.stage !== "design" || parsed.kind !== "plan") return null;
  return Object.hasOwn(PLAN_PARTS, parsed.id) ? PLAN_PARTS[parsed.id as PlanPart] : null;
}

/** The section anchor an element of Návrh is, or null: the reverse of sectionElement. */
export function sectionTargetOf(elementId: string): string | null {
  const part = (Object.keys(PLAN_PARTS) as PlanPart[]).find((p) => PLAN_PARTS[p] === elementId);
  return part ? planTarget(part) : null;
}

/** Whether the Lead may run a display operation on Návrh (the row's view_ops; anything else refused). */
export const designAllows = (op: string): boolean => allowsView("design", op);

/** How each of Návrh's targets reads in the Lead's "Vidí" chip and the @ menu. */
export const DESIGN_LABELS: Readonly<Record<DesignKind, string>> = {
  plan: "Návrh",
  rq: "Výzkumná otázka",
  hypothesis: "Hypotéza",
  set: "Sledovaná sada",
  assumption: "Předpoklad",
};

/** A Návrh target in words: a section by its name, an item by its kind; null for anything not Návrh's. */
export function designLabel(target: string): string | null {
  const parsed = parseAiaId(target);
  if (!parsed || parsed.stage !== "design" || !isDesignKind(parsed.kind)) return null;
  if (parsed.kind !== "plan") return DESIGN_LABELS[parsed.kind];
  return Object.hasOwn(PLAN_PARTS, parsed.id) ? `${DESIGN_LABELS.plan}: ${PART_WORDS[parsed.id as PlanPart]}` : null;
}

const PART_WORDS: Readonly<Record<PlanPart, string>> = {
  narrative: "porozumění zadání",
  variants: "rozsah",
  sets: "sledované sady",
  questions: "otázky AI",
  comments: "komentáře",
};
