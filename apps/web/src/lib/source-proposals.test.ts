import { describe, expect, it } from "vitest";

import type { ProposalsRun } from "@/lib/api";
import { canPropose, isMoving, mayAsk, proposalsLine, proposalsPhase, proposalsReason } from "@/lib/source-proposals";

const run = (over: Partial<ProposalsRun> = {}): ProposalsRun => ({
  run_id: "RUN-1",
  source_id: "SRC-0123456789abcdef",
  reading_sha256: "a".repeat(64),
  status: "RUNNING",
  step_status: "RUNNABLE",
  reason: null,
  current: true,
  created_at: null,
  finished_at: null,
  output: {},
  created: true,
  ...over,
});

describe("which sources AI may be asked about", () => {
  it("is a document something was read from, never a table or a file without text", () => {
    expect(canPropose({ family: "DOCUMENT", outcome: "READ", segments: 3 })).toBe(true);
    expect(canPropose({ family: "DOCUMENT", outcome: "PARTIAL", segments: 1 })).toBe(true);
    expect(canPropose({ family: "DOCUMENT", outcome: "UNREADABLE", segments: 0 })).toBe(false);
    expect(canPropose({ family: "DOCUMENT", outcome: "READ", segments: 0 })).toBe(false);
    expect(canPropose({ family: "DATASET", outcome: "READ", segments: 40 })).toBe(false);
    expect(canPropose({ family: "IMAGE", outcome: "UNSUPPORTED", segments: 0 })).toBe(false);
  });
});

describe("a proposals run's state", () => {
  it("reads the step: queued, running, waiting for budget, parked, done, failed", () => {
    expect(proposalsPhase(null)).toEqual({ phase: "none" });
    expect(proposalsPhase(run())).toEqual({ phase: "queued" });
    expect(proposalsPhase(run({ step_status: "RUNNING" }))).toEqual({ phase: "running" });
    expect(proposalsPhase(run({ step_status: "AWAITING_BUDGET", reason: "budget_exceeded" }))).toEqual({ phase: "budget", runId: "RUN-1" });
    expect(proposalsPhase(run({ step_status: "WAITING_PROVIDER", reason: "client_source_proposals_unconfigured" }))).toEqual({
      phase: "waiting",
      reason: "client_source_proposals_unconfigured",
    });
    expect(
      proposalsPhase(run({ step_status: "SUCCEEDED", status: "COMPLETED", output: { proposed: 4, dropped: { quote_not_found: 2, unknown_segment: 1 } } })),
    ).toEqual({ phase: "done", proposed: 4, dropped: 3 });
    expect(proposalsPhase(run({ step_status: "FAILED", reason: "reading_changed" }))).toEqual({ phase: "failed", reason: "reading_changed" });
  });

  it("never reads a step state it does not know as done", () => {
    expect(proposalsPhase(run({ step_status: "SOMETHING_NEW" })).phase).toBe("waiting");
  });

  it("is read again only while it moves on its own", () => {
    expect(isMoving(proposalsPhase(run()))).toBe(true);
    expect(isMoving(proposalsPhase(run({ step_status: "RUNNING" })))).toBe(true);
    expect(isMoving(proposalsPhase(run({ step_status: "AWAITING_BUDGET" })))).toBe(false);
    expect(isMoving(proposalsPhase(run({ step_status: "SUCCEEDED" })))).toBe(false);
  });

  it("may be asked again when none was asked, the last failed, or the document was read again", () => {
    expect(mayAsk(null)).toBe(true);
    expect(mayAsk(run({ step_status: "FAILED" }))).toBe(true);
    expect(mayAsk(run({ step_status: "SUCCEEDED", current: false }))).toBe(true);
    expect(mayAsk(run({ step_status: "SUCCEEDED" }))).toBe(false);
    expect(mayAsk(run())).toBe(false);
    expect(mayAsk(run({ step_status: "AWAITING_BUDGET" }))).toBe(false);
  });
});

describe("in words", () => {
  it("says what happened, with the reason where AIA has words for it", () => {
    expect(proposalsLine(proposalsPhase(null))).toBeNull();
    expect(proposalsLine({ phase: "done", proposed: 3, dropped: 0 })).toEqual({ tone: "done", text: "AI navrhla 3 návrhy. Čekají v Ke schválení." });
    expect(proposalsLine({ phase: "done", proposed: 0, dropped: 2 })?.tone).toBe("neutral");
    expect(proposalsLine({ phase: "budget", runId: "RUN-1" })?.tone).toBe("you");
    expect(proposalsLine({ phase: "waiting", reason: "egress_retention_unspecified" })).toEqual({
      tone: "world",
      text: "Čeká: u trasy k modelu není uvedena doba uchování dat.",
    });
    expect(proposalsLine({ phase: "failed", reason: "reading_changed" })?.text).toContain("přečten znovu");
  });

  it("shows a reason it has no words for as its code, and a missing one as unknown", () => {
    expect(proposalsReason("brand_new_reason")).toContain("brand_new_reason");
    expect(proposalsReason(null)).toBe("důvod AIA nezná");
  });
});
