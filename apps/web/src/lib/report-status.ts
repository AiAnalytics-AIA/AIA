// One rule for a run's internal report (run-recovery-and-truth 6e): the report card, the internal
// report panel, project memory and Interpretation Research all read a report's state here, in the
// same words. The API answers the report's artifact when one is stored (READY, with its review), the
// report step's own status until then, or NOT_IN_RUN. Unknown is never good: a report not read, or a
// state this client does not know, is UNKNOWN -- never composing, never approved.

import { t } from "@/i18n/t";
import { ApiError, type ResearchReport } from "@/lib/api";
import { stepLabel } from "@/lib/research-execution";

export type ReportStatus =
  | "NONE" //       the run makes no report
  | "COMPOSING" //  its step has not finished
  | "NOT_MADE" //   its step ended without making one (cancelled, skipped)
  | "FAILED" //     its step failed
  | "REFUSED" //    its inputs were refused (an analysis module did not pass)
  | "DRAFT" //      stored, not approved
  | "APPROVED" //   stored and approved for internal use
  | "UNKNOWN"; //   not read, or a state this client does not know

const COMPOSING = /^(PENDING|RUNNABLE|RUNNING|BLOCKED|WAITING_.*|AWAITING_.*|RECOVERY_REQUIRED)$/;

/** A stored document's review, as the API states it: only APPROVED_INTERNAL is approved. */
export const reviewStatus = (reviewState: string | null | undefined): "DRAFT" | "APPROVED" =>
  reviewState === "APPROVED_INTERNAL" ? "APPROVED" : "DRAFT";

/** The report step's states before it starts: once the run has ended, it never will (PC14). */
const NOT_STARTED = /^(PENDING|RUNNABLE|BLOCKED)$/;

export function reportStatus(report: Pick<ResearchReport, "state" | "reason" | "review_state"> | null | undefined, runEnded = false): ReportStatus {
  if (!report) return "UNKNOWN";
  // A finished run's report step that never started makes no report: never "still composing".
  if (runEnded && NOT_STARTED.test(report.state)) return "NOT_MADE";
  if (report.state === "READY") return reviewStatus(report.review_state);
  if (report.state === "NOT_IN_RUN") return "NONE";
  if (report.state === "FAILED") return report.reason === "report_inputs_refused" ? "REFUSED" : "FAILED";
  if (report.state === "CANCELLED" || report.state === "SKIPPED" || report.state === "SUCCEEDED") return "NOT_MADE";
  return COMPOSING.test(report.state) ? "COMPOSING" : "UNKNOWN";
}

export const reportStatusWords = (status: ReportStatus): string => t(`research.exec.report.status.${status}`);

/**
 * Why a report action was refused, in words where a person can act on it: the separation of duties
 * on an approval, and a report with literature refused because the run's analysis was built by an
 * earlier version of AIA (repaired on Průběh, PC3/PC17); anything else as the API said it.
 */
/** The report waits on analysis modules that state no supported finding (evidence-integrity 9b),
 *  named by their labels; a module this client does not know keeps its code. */
export function holdingWords(modules: readonly string[]): string {
  return `Zpráva čeká, dokud tyto části analýzy neuvedou doložené zjištění: ${modules.map((m) => stepLabel(`analysis_${m}`)).join(", ")}.`;
}

export function approvalRefusal(e: unknown): string {
  if (e instanceof ApiError && e.code === "separation_of_duties") return t("research.exec.results.reportApproveIndependent");
  if (e instanceof ApiError && e.code === "context_report_refused" && e.details.reason === "fingerprint_mismatch") return t("research.exec.results.analysisStale");
  if (e instanceof ApiError && e.code === "context_report_refused" && e.details.reason === "analysis_holds_report" && Array.isArray(e.details.modules)) {
    return holdingWords(e.details.modules.filter((m): m is string => typeof m === "string"));
  }
  return e instanceof Error ? e.message : String(e);
}
