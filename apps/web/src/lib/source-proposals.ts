// AI knowledge proposals from a client's document (lifecycle K2d5): which sources may be
// asked about, and a run's state in words. The run is the client's own work, paid by the
// client's budget; its proposals wait in Ke schválení until a person decides. Only what the
// API reports is said: a reason AIA has no words for is shown as its code, never guessed.

import { t, tv } from "@/i18n/t";
import type { ClientSource, ProposalsRun } from "@/lib/api";
import { plural } from "@/lib/format";
import type { Tone } from "@/lib/tone";

/** The run's one step (application.source_proposals.STEP). */
export const PROPOSALS_STEP = "extract";

/** How often a queued or running run is read again, in ms. */
export const POLL_MS = 2000;

/** Whether AI may be asked about a source: a document something was read from. A table is
 *  refused by the API (dataset_not_extracted) until its personal columns can be left out. */
export function canPropose(s: Pick<ClientSource, "family" | "outcome" | "segments">): boolean {
  return s.family === "DOCUMENT" && (s.outcome === "READ" || s.outcome === "PARTIAL") && s.segments > 0;
}

export type ProposalsPhase =
  | { phase: "none" }
  | { phase: "queued" }
  | { phase: "running" }
  | { phase: "budget"; runId: string }
  | { phase: "waiting"; reason: string | null }
  | { phase: "done"; proposed: number; dropped: number }
  | { phase: "failed"; reason: string | null };

const QUEUED = new Set(["RUNNABLE", "BLOCKED"]);
const RUNNING = new Set(["RUNNING", "CLAIMED"]);

/** A run's state, from its step's. A step state AIA does not know is a wait, never done. */
export function proposalsPhase(run: ProposalsRun | null): ProposalsPhase {
  if (!run) return { phase: "none" };
  const s = run.step_status;
  if (s === "SUCCEEDED") {
    const dropped = Object.values(run.output.dropped ?? {}).reduce((a, b) => a + b, 0);
    return { phase: "done", proposed: run.output.proposed ?? 0, dropped };
  }
  if (s === "AWAITING_BUDGET") return { phase: "budget", runId: run.run_id };
  if (s === "FAILED" || s === "CANCELLED" || s === "SKIPPED") return { phase: "failed", reason: run.reason };
  if (QUEUED.has(s)) return { phase: "queued" };
  if (RUNNING.has(s)) return { phase: "running" };
  // WAITING_PROVIDER, WAITING_CAPACITY, RECOVERY_REQUIRED, and any state AIA does not know.
  return { phase: "waiting", reason: run.reason };
}

/** Whether the screen reads the run again: it is still moving on its own. */
export const isMoving = (p: ProposalsPhase): boolean => p.phase === "queued" || p.phase === "running";

/** Whether asking again would start a new run: none asked, the last one ended without a
 *  result, or the document has been read again since. */
export function mayAsk(run: ProposalsRun | null): boolean {
  const p = proposalsPhase(run);
  return p.phase === "none" || p.phase === "failed" || (run !== null && !run.current);
}

/** Whether AIA has words for a proposals reason. */
const reasonKnown = (code: string): boolean => t(`aia.sources.ai.reasons.${code}`) !== `aia.sources.ai.reasons.${code}`;

/** A reason in words; one AIA has no words for is shown as its code. */
export function proposalsReason(code: string | null | undefined): string {
  if (!code) return t("aia.sources.ai.reasons.unknown");
  return reasonKnown(code) ? t(`aia.sources.ai.reasons.${code}`) : tv("aia.sources.reasonCode", { code });
}

/** The run in one line, and its tone. */
export function proposalsLine(p: ProposalsPhase): { tone: Tone; text: string } | null {
  switch (p.phase) {
    case "none":
      return null;
    case "queued":
      return { tone: "neutral", text: t("aia.sources.ai.queued") };
    case "running":
      return { tone: "running", text: t("aia.sources.ai.running") };
    case "budget":
      return { tone: "you", text: t("aia.sources.ai.budget") };
    case "waiting":
      return { tone: "world", text: tv("aia.sources.ai.waiting", { reason: proposalsReason(p.reason) }) };
    case "failed":
      return { tone: "fault", text: tv("aia.sources.ai.failed", { reason: proposalsReason(p.reason) }) };
    case "done":
      return p.proposed
        ? { tone: "done", text: tv("aia.sources.ai.done", { n: plural(p.proposed, "návrh", "návrhy", "návrhů") }) }
        : { tone: "neutral", text: t("aia.sources.ai.doneNone") };
  }
}
