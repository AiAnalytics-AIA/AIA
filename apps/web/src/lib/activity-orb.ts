// When AIA shows an activity orb, and which one (.planning/plans/thinking-orbs.md).
// An orb means "this step is executing now": the API reports it RUNNING. Queued,
// waiting, failed and finished steps have none, so the orb never claims activity
// the backend has not reported (design brief §Motion). A step that calls a model
// is tinted as AI (`ai`); a step that is code is tinted as work in progress
// (`running`), so the two stay told apart. The states are taste, one table each;
// which steps call a model is not.

import type { OrbState } from "thinking-orbs";

import type { ResearchAgentAction, ResearchAgentJob, ResearchRun, ResearchStep } from "./api";

export type { OrbState };

/** `ai`: a model is thinking (--ai-ink). `running`: code is working (--status-running). */
export type OrbInk = "ai" | "running";
export type Orb = { state: OrbState; ink: OrbInk };

/** The status of a step whose attempt is executing: the only status that shows an orb. */
const RUNNING = "RUNNING";
/** A running step no table names (a step kind added later): still shown, as work. */
const UNNAMED: Orb = { state: "working", ink: "running" };

const ai = (state: OrbState): Orb => ({ state, ink: "ai" });
const code = (state: OrbState): Orb => ({ state, ink: "running" });

/** What each research agent does while it thinks. */
export const AGENT_ORB: Record<ResearchAgentAction, OrbState> = {
  analyze_brief: "searching",
  build_questionnaire: "composing",
  optimize_questionnaire: "solving",
  propose_audience: "connecting",
  suggest_dimensions: "shaping",
  critique_design: "searching",
  design_copilot: "working",
  answer_memory: "weaving",
};

/**
 * A research run's steps. Fieldwork thinks when AI respondents answer it
 * (aia_executors.ai_fieldwork) and the analysis modules think (aia_executors.analysis);
 * the rest is code.
 */
export const RUN_STEP_ORB: Readonly<Record<string, Orb>> = {
  compile: code("shaping"),
  preflight: code("solving"),
  aggregate: code("weaving"),
  sociomap: code("connecting"),
  sociomapping: code("connecting"),
  sociomapping_report: code("composing"),
  report: code("composing"),
};

/** Deep Research's steps: plan, investigate, verify and synthesize call models; merge and publish are code. */
export const DEEP_RESEARCH_ORB: Readonly<Record<string, Orb>> = {
  plan: ai("shaping"),
  investigate: ai("searching"),
  merge: code("weaving"),
  verify: ai("solving"),
  synthesize: ai("composing"),
  publish: code("composing"),
};

/** A research agent job: its one agent step calls the model. */
export function agentJobOrb(job: Pick<ResearchAgentJob, "action" | "steps">): Orb | null {
  return job.steps.some((s) => s.status === RUNNING) ? ai(AGENT_ORB[job.action]) : null;
}

/** A step of a research run while it executes. */
export function researchStepOrb(run: Pick<ResearchRun, "fieldwork_source">, step: Pick<ResearchStep, "node_key" | "status">): Orb | null {
  if (step.status !== RUNNING) return null;
  if (step.node_key === "run") return run.fieldwork_source === "ai_runtime" ? ai("listening") : code("listening");
  if (step.node_key.startsWith("analysis_")) return ai("working");
  return RUN_STEP_ORB[step.node_key] ?? UNNAMED;
}

/** A Deep Research step; an investigate track is `investigate/<track>` (domain workflow.child_node_key). */
export function deepResearchStepOrb(step: { node_key: string; status: string }): Orb | null {
  if (step.status !== RUNNING) return null;
  return DEEP_RESEARCH_ORB[step.node_key.split("/", 1)[0]] ?? UNNAMED;
}

/** The orb for a Deep Research run as a whole: the first running step that thinks, else the first running step. */
export function deepResearchRunOrb(steps: readonly { node_key: string; status: string }[]): Orb | null {
  const running = steps.map(deepResearchStepOrb).filter((o): o is Orb => o !== null);
  return running.find((o) => o.ink === "ai") ?? running[0] ?? null;
}
