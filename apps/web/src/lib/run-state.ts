// One research run's state, the one every screen reads (run-recovery-and-truth 6a). The
// steps decide it, in the order of the run's own gates: a run that has not ended runs or
// waits; an ended run without fieldwork data has no evidence; one whose analysis or report
// a person must repair needs repair; otherwise its results are ready, and its report once
// the report step made it. A phase this module does not know reads as waiting, with no
// reason invented, and an ended run read without its steps (an older API's listing) is
// UNKNOWN in its phase's own word: unknown is never good.

import { t, tv } from "@/i18n/t";
import type { ResearchRun, ResearchStep } from "@/lib/api";
import { needsRepair, phaseLabel, stepLabel, stepOf, waitingDetail } from "@/lib/research-execution";
import type { Tone } from "@/lib/tone";

export type RunState =
  | "RUNNING"
  | "WAITING"
  | "NEEDS_REPAIR"
  | "EVIDENCE_UNAVAILABLE"
  | "RESULTS_READY"
  | "REPORT_READY"
  | "CANCELLED"
  | "UNKNOWN";

export type RunReading = { state: RunState; tone: Tone; label: string; reason: string | null };

/** What a run's state is read from: a listed run carries its steps without their attempts. */
export type RunLike = Pick<ResearchRun, "phase" | "is_terminal" | "steps">;

const TONE: Record<RunState, Tone> = {
  RUNNING: "running",
  WAITING: "you",
  NEEDS_REPAIR: "fault",
  EVIDENCE_UNAVAILABLE: "fault",
  RESULTS_READY: "done",
  REPORT_READY: "done",
  CANCELLED: "neutral",
  UNKNOWN: "neutral",
};

const reading = (state: RunState, reason: string | null = null): RunReading => ({
  state,
  tone: TONE[state],
  label: t(`research.exec.state.${state}`),
  reason,
});

/** A step that stopped the run, in words: where it stopped, then what it recorded, if anything. */
function failedAt(step: ResearchStep): string {
  const where = tv("research.exec.state.reason.failedAt", { step: stepLabel(step.node_key) });
  return step.error_message ? `${where} ${step.error_message}` : where;
}

const unfinished = (step: ResearchStep): boolean =>
  needsRepair(step) || step.status === "FAILED" || step.status === "CANCELLED";

export function runState(given: RunLike): RunReading {
  // A run sent without its steps (absent, or an empty listing) has them unread.
  const run = { ...given, steps: given.steps ?? [] };
  if (!run.is_terminal) {
    if (run.phase === "RUNNING" || run.phase === "QUEUED") return reading("RUNNING");
    const waiting = run.steps.map(waitingDetail).find((detail) => detail !== null) ?? null;
    return reading("WAITING", waiting);
  }
  if (run.phase === "CANCELLED") return reading("CANCELLED");
  // Every run has steps from its creation: none means they were not read, not that none ran.
  if (!run.steps.length) return { state: "UNKNOWN", tone: TONE.UNKNOWN, label: phaseLabel(run.phase), reason: null };
  const failed = run.steps.find((s) => s.status === "FAILED") ?? null;
  if (!stepOf(run, "aggregate")?.artifact_id) {
    return reading("EVIDENCE_UNAVAILABLE", failed ? failedAt(failed) : null);
  }
  const modules = run.steps.filter((s) => s.kind === "research_analysis");
  const repair = modules.filter(unfinished);
  if (repair.length) {
    return reading("NEEDS_REPAIR", tv("research.exec.state.reason.modules", { n: repair.length, total: modules.length }));
  }
  if (failed) return reading("NEEDS_REPAIR", failedAt(failed));
  if (run.phase !== "COMPLETED") return reading("WAITING");
  const report = run.steps.find((s) => s.kind === "research_report");
  return reading(report?.status === "SUCCEEDED" ? "REPORT_READY" : "RESULTS_READY");
}

/** Where a run is read next: its results once they are ready, else Progress, where a repair is offered. */
export const runDestination = (run: RunLike): "results" | "progress" => {
  const { state } = runState(run);
  return state === "RESULTS_READY" || state === "REPORT_READY" ? "results" : "progress";
};
