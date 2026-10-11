// Direct human edits of the working proposal. Legacy plan functions stay parity-tested.
// Keep the project (what a native design job receives) and analysis (the stage's view)
// together. Editing a proposal never edits an existing questionnaire or frozen run.
import type { Json } from "./model";
import type { Analysis } from "./store";
import { MAX_OBJECTS, trackedSets, type PlanState, type TrackedSet } from "./plan";

const narrativeKeys = ["problem_summary", "research_questions", "objectives", "hypotheses"] as const;
export type Narrative = { problem_summary: string; research_questions: string[]; objectives: string[]; hypotheses: string[] };
export const lines = (text: string): string[] => text.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);

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

/** Form validation only: readiness and execution still validate their own contracts. */
export function validMeasurement(set: TrackedSet): boolean {
  const objects = set.objects ?? [];
  return !!set.title?.trim() && !!set.purpose?.trim() && objects.length >= 4 && objects.length <= MAX_OBJECTS &&
    objects.every((s) => !!s.trim()) && new Set(objects.map((s) => s.trim().toLocaleLowerCase("cs"))).size === objects.length &&
    !!set.object_question?.includes("{object}") && !!set.scale_labels?.[0]?.trim() && !!set.scale_labels?.[1]?.trim();
}
