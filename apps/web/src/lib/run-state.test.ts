// One research run's state (run-recovery-and-truth 6a): every screen reads this, so a run
// with a blocked module is never "done" anywhere, and an unknown phase is never good.
import { describe, expect, it } from "vitest";

import type { ResearchRun, ResearchStep } from "@/lib/api";
import { runDestination, runState } from "./run-state";

const step = (node_key: string, extra: Partial<ResearchStep> = {}): ResearchStep =>
  ({ node_key, kind: node_key.startsWith("analysis_") ? "research_analysis" : node_key === "report" ? "research_report" : "research", status: "SUCCEEDED", waiting_reason: null, error_message: null, artifact_id: null, ...extra }) as ResearchStep;
const run = (extra: Partial<ResearchRun>): ResearchRun =>
  ({ phase: "COMPLETED", is_terminal: true, steps: [], ...extra }) as ResearchRun;

const data = step("aggregate", { artifact_id: "ART-1" });
const modules = (blocked = 0) =>
  ["executive", "objects", "audience"].map((m, i) => step(`analysis_${m}`, { analysis_outcome: i < blocked ? "BLOCKED" : "COMPLETED" }));

describe("run state", () => {
  it("runs or waits until the run has ended, with the wait's own reason", () => {
    expect(runState(run({ phase: "QUEUED", is_terminal: false })).state).toBe("RUNNING");
    expect(runState(run({ phase: "RUNNING", is_terminal: false })).tone).toBe("running");
    const waiting = runState(run({ phase: "WAITING", is_terminal: false, steps: [step("run", { status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded" })] }));
    expect(waiting).toMatchObject({ state: "WAITING", tone: "you" });
    expect(waiting.reason).toBeTruthy();
  });

  it("reads a phase it does not know as waiting, with no reason invented", () => {
    const strange = runState(run({ phase: "SOMETHING_NEW" as ResearchRun["phase"], is_terminal: false }));
    expect(strange).toMatchObject({ state: "WAITING", reason: null });
    // An ended run whose phase is not COMPLETED is not called ready either.
    expect(runState(run({ phase: "SOMETHING_NEW" as ResearchRun["phase"], steps: [data] })).state).toBe("WAITING");
  });

  it("has no evidence when fieldwork stored no data, and says where it stopped", () => {
    const stopped = runState(run({ phase: "FAILED", steps: [step("compile"), step("run", { status: "FAILED", error_message: "Brána odmítla." })] }));
    expect(stopped.state).toBe("EVIDENCE_UNAVAILABLE");
    expect(stopped.reason).toContain("Brána odmítla.");
    expect(runState(run({ steps: [step("aggregate")] })).state).toBe("EVIDENCE_UNAVAILABLE");
  });

  it("needs repair when a module was stored BLOCKED, though every step succeeded", () => {
    const blocked = runState(run({ steps: [data, ...modules(2), step("report", { status: "PENDING" })] }));
    expect(blocked).toMatchObject({ state: "NEEDS_REPAIR", tone: "fault" });
    expect(blocked.reason).toBe("2 z 3 částí analýzy potřebuje opravu.");
    expect(runState(run({ phase: "FAILED", steps: [data, step("sociomap", { status: "FAILED" })] })).state).toBe("NEEDS_REPAIR");
  });

  it("has its results ready, and its report once the report step made it", () => {
    expect(runState(run({ steps: [data, ...modules()] })).state).toBe("RESULTS_READY");
    expect(runState(run({ steps: [data, ...modules(), step("report")] })).state).toBe("REPORT_READY");
    expect(runState(run({ steps: [data, ...modules(), step("report", { status: "SKIPPED" })] })).state).toBe("RESULTS_READY");
  });

  it("calls an ended run read without its steps unknown, in its phase's word, never done or empty", () => {
    expect(runState(run({ steps: [] }))).toMatchObject({ state: "UNKNOWN", tone: "neutral", label: "Dokončeno" });
    expect(runDestination(run({ steps: [] }))).toBe("progress");
  });

  it("keeps a cancelled run cancelled, data or not", () => {
    expect(runState(run({ phase: "CANCELLED", steps: [data] })).state).toBe("CANCELLED");
  });

  it("opens results only when they are ready; a repair is offered on Progress", () => {
    expect(runDestination(run({ steps: [data, ...modules()] }))).toBe("results");
    expect(runDestination(run({ steps: [data, ...modules(1)] }))).toBe("progress");
    expect(runDestination(run({ phase: "RUNNING", is_terminal: false }))).toBe("progress");
  });
});
