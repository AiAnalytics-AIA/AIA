// Návrh's narrative as items (artifact-design DSN3, input-interactions 4, audit A30): the problem
// summary and each research question, objective and hypothesis edited where it is shown, one item
// at a time, through applyNarrative -- so the project and the analysis stay together as they did
// under the retired ProposalEditor. The store settles the stable item ids around every update
// (item-ids.ts settleItemIds: a reworded item keeps its id). Pure: every function returns the next
// state, or the refusal in words; nothing here saves.

import { t, tv } from "@/i18n/t";
import { type PlanState } from "./plan";
import { type Narrative, applyNarrative, proposalAnalysis } from "./plan-edit";
import { MAX_RESEARCH_QUESTIONS } from "./trace";

export type NarrativeList = "research_questions" | "objectives" | "hypotheses";
export const NARRATIVE_LISTS: readonly NarrativeList[] = ["research_questions", "objectives", "hypotheses"];

const strings = (raw: unknown): string[] => (Array.isArray(raw) ? raw.map(String) : []);

/** The narrative as the stage shows it: the analysis's, the goal standing in for an empty summary. */
export function narrativeOf(state: PlanState): Narrative {
  const a = proposalAnalysis(state) ?? {};
  return {
    problem_summary: String(a.problem_summary || state.project.goal || ""),
    research_questions: strings(a.research_questions),
    objectives: strings(a.objectives),
    hypotheses: strings(a.hypotheses),
  };
}

export type Edited = { state: PlanState } | { refused: string };

/** Case and spacing aside, as the plan's lists compare (InlineCreateRow's rule). */
const same = (a: string, b: string) => a.replace(/\s+/g, " ").trim().toLocaleLowerCase("cs") === b.replace(/\s+/g, " ").trim().toLocaleLowerCase("cs");

/** Why `text` cannot stand at `index` of `list` (a repeat of another item), or null. */
export function itemProblem(n: Narrative, list: NarrativeList, text: string, index: number | null): string | null {
  return n[list].some((x, i) => i !== index && same(x, text)) ? t("research.plan.narrative.duplicate") : null;
}

const write = (state: PlanState, n: Narrative): Edited => ({ state: applyNarrative(state, n) });

/** The problem summary, reworded; an empty one is refused (the stage's rule since ProposalEditor). */
export function setSummary(state: PlanState, text: string): Edited {
  const value = text.trim();
  if (!value) return { refused: t("research.plan.requiredSummary") };
  return write(state, { ...narrativeOf(state), problem_summary: value });
}

/** Item `index` of `list`, reworded in its place. */
export function setItem(state: PlanState, list: NarrativeList, index: number, text: string): Edited {
  const n = narrativeOf(state);
  const value = text.trim();
  if (index < 0 || index >= n[list].length) return { refused: t("research.plan.narrative.gone") };
  if (!value) return { refused: t("research.plan.narrative.empty") };
  const problem = itemProblem(n, list, value, index);
  if (problem) return { refused: problem };
  return write(state, { ...n, [list]: n[list].map((x, i) => (i === index ? value : x)) });
}

/** Whether another item can be added to `list`, and why not: the analysis reads at most eight research questions. */
export function addProblem(n: Narrative, list: NarrativeList): string | null {
  return list === "research_questions" && n.research_questions.length >= MAX_RESEARCH_QUESTIONS
    ? tv("research.plan.narrative.tooManyQuestions", { max: MAX_RESEARCH_QUESTIONS })
    : null;
}

/** A new item at the end of `list`, or at `at` (an undone removal goes back where it was). */
export function addItem(state: PlanState, list: NarrativeList, text: string, at?: number): Edited {
  const n = narrativeOf(state);
  const value = text.trim();
  if (!value) return { refused: t("research.plan.narrative.empty") };
  const problem = addProblem(n, list) ?? itemProblem(n, list, value, null);
  if (problem) return { refused: problem };
  const items = [...n[list]];
  items.splice(at === undefined ? items.length : Math.max(0, Math.min(at, items.length)), 0, value);
  return write(state, { ...n, [list]: items });
}

/** Item `index` of `list` removed; the last objective stays (a study states at least one). */
export function removeItem(state: PlanState, list: NarrativeList, index: number): Edited {
  const n = narrativeOf(state);
  if (index < 0 || index >= n[list].length) return { refused: t("research.plan.narrative.gone") };
  if (list === "objectives" && n.objectives.length === 1) return { refused: t("research.plan.requiredObjectives") };
  return write(state, { ...n, [list]: n[list].filter((_, i) => i !== index) });
}
