// Cíle on the Brief (artifact-brief BRF2): the study's objectives as items, read and written where
// Návrh keeps them -- `research_plan.objectives` and, when the stage has one, the analysis's
// `objectives` (plan-edit.ts keeps the two together; this does the same) -- so the Brief and Návrh
// show one list. Each item's id is item_ids' (WCE1): the stored one, or the one derived from its
// wording, the same on every read and on the server. Pure.

import { listIds, withItemIds } from "./item-ids";
import type { Json, ResearchProject } from "./model";
import type { Analysis } from "./store";

/** The longest objective the edit vocabulary takes (edit_ops ItemText, 1500). */
export const OBJECTIVE_MAX = 1500;

export type Objective = { id: string; text: string };
type Design = { project: ResearchProject; analysis: Analysis | null };

/** The stored list when it is one of strings (or absent: none yet); null when it cannot be read
 * as one, so an edit never drops an entry it does not understand. */
const readable = (v: unknown): string[] | null =>
  v === undefined || v === null ? [] : Array.isArray(v) && v.every((x) => typeof x === "string") ? (v as string[]) : null;

/** Where the objectives are read from: the analysis when the stage has one, else the stored plan. */
const holderOf = ({ project, analysis }: Design): { [k: string]: unknown } => analysis ?? project.research_plan ?? {};

/** The objectives as Návrh shows them, each with its id. None stated: an empty list, never the goal. */
export function objectivesOf(design: Design): Objective[] {
  const texts = readable(holderOf(design).objectives);
  if (!texts?.length) return [];
  const [content, analysis] = withItemIds(design.project as unknown as { [k: string]: Json }, design.analysis);
  const ids = listIds(analysis ?? content.research_plan, "objectives", "objective_ids");
  return ids ? texts.map((text, i) => ({ id: ids[i]!, text })) : [];
}

/** The design with `objectives` as its list, in the plan and in the analysis alike. */
export function withObjectives({ project, analysis }: Design, objectives: string[]): Design {
  return {
    project: {
      ...project,
      research_plan: { ...project.research_plan, objectives },
      ui_state: { ...project.ui_state, plan_manual_changed: true },
    },
    analysis: analysis ? { ...analysis, objectives } : null,
  };
}

/** Whether the objectives can be edited here: a list of strings, or none yet. */
export const objectivesEditable = (design: Design): boolean => readable(holderOf(design).objectives) !== null;

/** `change` applied to the list; the design unchanged when the stored list cannot be read. */
function edited(design: Design, change: (list: string[]) => string[]): Design {
  const list = readable(holderOf(design).objectives);
  return list === null ? design : withObjectives(design, change(list));
}

/** The objective at `index` reworded. */
export const setObjective = (design: Design, index: number, text: string): Design =>
  edited(design, (list) => list.map((x, i) => (i === index ? text : x)));

/** A new objective at the end. */
export const addObjective = (design: Design, text: string): Design => edited(design, (list) => [...list, text]);

/** The objective at `index` removed, and its wording for the undo; nothing removed out of range. */
export function removeObjective(design: Design, index: number): { design: Design; removed: string | null } {
  const list = readable(holderOf(design).objectives);
  if (list === null || index < 0 || index >= list.length) return { design, removed: null };
  return { design: withObjectives(design, list.filter((_, i) => i !== index)), removed: list[index]! };
}

/** `text` back at `index` (or at the end, when the list has since grown shorter): the undo. */
export const restoreObjective = (design: Design, index: number, text: string): Design =>
  edited(design, (list) => {
    const at = Math.min(Math.max(index, 0), list.length);
    return [...list.slice(0, at), text, ...list.slice(at)];
  });
