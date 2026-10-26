// Zadání's contract with the Research Lead, as data (artifact-brief BRF1): what on the Brief the
// Lead can name, and which element of the screen each name is. The stage's row in the shared
// registry (lib/workbench-artifacts.ts ARTIFACTS.brief) says which view operations and target kinds
// it has; this file says which targets of those kinds exist for a given study, and how the screen
// marks them, so focusSelector (lib/lead.ts) and the person's "@" (targetOfElement) find exactly one
// element for each. A target this file does not name is refused, never guessed. Pure.

import { type BriefingField, type TopField, storedAttachmentId } from "@/research/brief";
import { objectivesOf } from "@/research/brief-objectives";
import type { ResearchProject } from "@/research/model";
import type { Analysis } from "@/research/store";
import { ARTIFACTS, type ViewOpKind, aiaId, parseAiaId } from "../workbench-artifacts";

/** The Brief's view operations: its row in the registry, never a copy. */
export const BRIEF_VIEW_OPS: readonly ViewOpKind[] = ARTIFACTS.brief.view_ops;

/**
 * Every field and section of the Brief the Lead can name as `brief:<field>`, in the screen's
 * order. A field's name is the one the Lead's edits use (lead.ts TextField): `briefing.situation`,
 * never `situation`; `type`, `files` and `context` are the sections that hold the problem types,
 * the materials and the further context.
 */
export const BRIEF_FIELDS = [
  "goal",
  "title",
  "objectives",
  "decision_use",
  "type",
  "context",
  "briefing.product_description",
  "briefing.situation",
  "briefing.what_is_known",
  "briefing.constraints",
  "files",
] as const;

export type BriefField = (typeof BRIEF_FIELDS)[number];

/** A further-context field as the screen lists it (BriefStep's CONTEXT), as the Lead names it. */
export function contextField(field: TopField | BriefingField): BriefField {
  return field === "decision_use" || field === "title" || field === "goal" ? field : `briefing.${field}`;
}

/**
 * The DOM id the screen gives the element that stands for `field`: what focusSelector resolves
 * `brief:<field>` to (`#brief-<field>`), and what targetOfElement reads back. One builder, so the
 * screen never spells it.
 */
export function briefElementId(field: BriefField): string {
  return `brief-${field}`;
}

/** A target on the Brief, read: a field, an objective, or a stored file. */
export type BriefTarget = { kind: "brief"; field: BriefField } | { kind: "objective"; id: string } | { kind: "material"; id: string };

/**
 * A Lead target the Brief carries, or null. Only a field this file names and a material in the
 * registry's grammar are taken; anything else -- an unknown field, a short `brief:situation`, a
 * kind another stage owns -- is refused rather than mapped to something near it.
 */
export function briefTarget(target: string): BriefTarget | null {
  const parsed = parseAiaId(target);
  if (!parsed || parsed.stage !== "brief") return null;
  if (parsed.kind === "brief") return (BRIEF_FIELDS as readonly string[]).includes(parsed.id) ? { kind: "brief", field: parsed.id as BriefField } : null;
  if (parsed.kind === "objective") return { kind: "objective", id: parsed.id };
  if (parsed.kind === "material") return { kind: "material", id: parsed.id };
  return null;
}

/** The `data-aia` of a stored file's row: `material:<attachment_id>`. A link has no stable id yet;
 * a file attached twice is marked on its first row only, so the name finds one element. */
export function materialAia(attachmentId: string): string {
  return aiaId("material", attachmentId);
}

/**
 * Every target the Brief shows for a study: each field, each objective (by item_ids' id), and each
 * file kept in AIA. A link, and a record whose file never came into AIA, have no id to name and are
 * not targets.
 */
export function briefTargets(project: ResearchProject, analysis: Analysis | null = null): string[] {
  const files = (project.briefing?.attachments || []).map(storedAttachmentId).filter((id): id is string => id !== null);
  const objectives = objectivesOf({ project, analysis }).map((o) => aiaId("objective", o.id));
  return [...BRIEF_FIELDS.map((f) => aiaId("brief", f)), ...objectives, ...[...new Set(files)].map(materialAia)];
}
