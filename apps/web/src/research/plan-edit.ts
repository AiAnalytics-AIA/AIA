// Direct human edits of the working proposal. Legacy plan functions stay parity-tested.
// Keep the project (what a native design job receives) and analysis (the stage's view)
// together. Editing a proposal never edits an existing questionnaire or frozen run.
import type { Json } from "./model";
import type { Analysis } from "./store";
import { t } from "@/i18n/t";
import { MAX_OBJECTS, SCALE_DEFAULT, SET_FULL, trackedSets, type PlanState, type TrackedSet } from "./plan";

const narrativeKeys = ["problem_summary", "research_questions", "objectives", "hypotheses"] as const;
export type Narrative = { problem_summary: string; research_questions: string[]; objectives: string[]; hypotheses: string[] };

/** The stored plan is usable even when no legacy analysis was saved alongside it. */
export function proposalAnalysis(state: PlanState): Analysis | null {
  if (state.analysis) return state.analysis;
  const plan = state.project.research_plan;
  const hasNarrative = narrativeKeys.some((k) => Array.isArray(plan[k]) ? (plan[k] as Json[]).length > 0 : typeof plan[k] === "string" && !!plan[k]);
  return hasNarrative || trackedSets(plan).length ? { ...plan } : null;
}

export function applyNarrative(state: PlanState, narrative: Narrative): PlanState {
  return {
    project: { ...state.project, research_plan: { ...state.project.research_plan, ...narrative },
      ui_state: { ...state.project.ui_state, plan_manual_changed: true } },
    analysis: { ...proposalAnalysis(state), ...narrative },
  };
}

export function applyPlanSets(state: PlanState, sets: TrackedSet[]): PlanState {
  return {
    project: { ...state.project, research_plan: { ...state.project.research_plan, tracked_sets: sets },
      ui_state: { ...state.project.ui_state, plan_manual_changed: true } },
    analysis: { ...proposalAnalysis(state), tracked_sets: sets },
  };
}

/** A tracked set's measurement fields, each edited where the set's card shows it (audit A33). */
export type SetField = "purpose" | "object_question" | "scale_low" | "scale_high";

/** Why `value` cannot be the set's `field`, in words (a set is measured on a question naming {object} and two labelled ends), or null. */
export function setFieldProblem(field: SetField, value: string): string | null {
  if (!value.trim()) return t(`research.plan.setField.empty.${field}`);
  if (field === "object_question" && !value.includes("{object}")) return t("research.plan.setField.needsObject");
  return null;
}

/**
 * The set with `field` written as typed (trimmed); the other fields, and any the set carries, kept.
 * A scale end written on a set that states no ends keeps the other end the person saw (the
 * preview's default); a set that states them keeps its other end as stored.
 */
export function withSetField(set: TrackedSet, field: SetField, value: string): TrackedSet {
  const v = value.trim();
  if (field === "purpose" || field === "object_question") return { ...set, [field]: v };
  const labels = set.scale_labels ? [set.scale_labels[0] ?? "", set.scale_labels[1] ?? ""] : [...SCALE_DEFAULT];
  labels[field === "scale_low" ? 0 : 1] = v;
  return { ...set, scale_labels: labels };
}

/**
 * Why `value` cannot be one of the set's items: a repeat of another (case aside), or, added
 * (`except` unset), one past addObject's limit (MAX_OBJECTS); else null. A rename names its own
 * place in `except`.
 */
export function objectProblem(set: TrackedSet, value: string, except?: number): string | null {
  const objects = set.objects ?? [];
  if (except === undefined && objects.length >= MAX_OBJECTS) return SET_FULL;
  const key = value.trim().toLocaleLowerCase("cs");
  return objects.some((o, i) => i !== except && o.trim().toLocaleLowerCase("cs") === key) ? t("research.plan.setField.duplicate") : null;
}

/** The set with item `index` reworded in its place, the order kept. */
export function withObject(set: TrackedSet, index: number, value: string): TrackedSet {
  return { ...set, objects: (set.objects ?? []).map((o, i) => (i === index ? value.trim() : o)) };
}
