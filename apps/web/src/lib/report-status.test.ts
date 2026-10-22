// One rule for a run's internal report (run-recovery-and-truth 6e): a report not read, or a state
// this client does not know, is never composing and never approved.
import { describe, expect, it } from "vitest";

import { t } from "@/i18n/t";
import { ApiError } from "@/lib/api";
import { approvalRefusal, reportStatus, reportStatusWords, reviewStatus } from "./report-status";

const r = (state: string, extra: Record<string, unknown> = {}) => ({ state, ...extra }) as Parameters<typeof reportStatus>[0];

describe("reportStatus", () => {
  it("reads a stored report by its review, only APPROVED_INTERNAL being approved", () => {
    expect(reportStatus(r("READY", { review_state: "APPROVED_INTERNAL" }))).toBe("APPROVED");
    expect(reportStatus(r("READY", { review_state: "DRAFT_UNAPPROVED" }))).toBe("DRAFT");
    expect(reportStatus(r("READY"))).toBe("DRAFT");
    expect(reviewStatus(undefined)).toBe("DRAFT");
  });

  it("reads the report step's own status until a report is stored", () => {
    expect(reportStatus(r("NOT_IN_RUN"))).toBe("NONE");
    expect(reportStatus(r("PENDING"))).toBe("COMPOSING");
    expect(reportStatus(r("WAITING_PROVIDER"))).toBe("COMPOSING");
    expect(reportStatus(r("AWAITING_BUDGET"))).toBe("COMPOSING");
    expect(reportStatus(r("FAILED", { reason: "report_inputs_refused" }))).toBe("REFUSED");
    expect(reportStatus(r("FAILED", { reason: "renderer_crashed" }))).toBe("FAILED");
    expect(reportStatus(r("CANCELLED"))).toBe("NOT_MADE");
    expect(reportStatus(r("SKIPPED"))).toBe("NOT_MADE");
  });

  it("says a finished run's report step that never started makes no report, never composing (PC14)", () => {
    for (const state of ["PENDING", "RUNNABLE", "BLOCKED"]) {
      expect(reportStatus(r(state), true)).toBe("NOT_MADE");
      expect(reportStatus(r(state), false)).toBe("COMPOSING");
    }
    // A step still running when its run failed may yet finish: still composing.
    expect(reportStatus(r("RUNNING"), true)).toBe("COMPOSING");
  });

  it("never reads an unread report or a state it does not know as composing or approved", () => {
    expect(reportStatus(null)).toBe("UNKNOWN");
    expect(reportStatus(r("SOMETHING_NEW"))).toBe("UNKNOWN");
    expect(reportStatusWords("UNKNOWN")).toBe("Stav zprávy se nepodařilo zjistit.");
  });

  it("says why an approval was refused, in words where a person can act on it", () => {
    expect(approvalRefusal(new ApiError(409, "separation_of_duties", "x", null))).toBe("Tuto zprávu musí schválit někdo jiný než ten, kdo ji vytvořil.");
    expect(approvalRefusal(new Error("Síť selhala."))).toBe("Síť selhala.");
    // A module with no supported finding holds the report (evidence-integrity 9b): named, never the API's English.
    const held = approvalRefusal(new ApiError(409, "context_report_refused", "all eight … waiting on: executive", null, { reason: "analysis_holds_report", modules: ["executive"] }));
    expect(held).toMatch(/^Zpráva čeká, dokud tyto části analýzy neuvedou doložené zjištění: .+\.$/);
    expect(held).not.toContain("executive");
  });
});

describe("approvalRefusal (PC17)", () => {
  it("says a literature report refused for an analysis an earlier AIA built in words, anything else as the API said", () => {
    const stale = new ApiError(409, "context_report_refused", "the harness no longer matches", null, { reason: "fingerprint_mismatch" });
    expect(approvalRefusal(stale)).toBe(t("research.exec.results.analysisStale"));
    const other = new ApiError(409, "context_report_refused", "bundle not ready", null, {});
    expect(approvalRefusal(other)).toBe("bundle not ready");
  });
});
