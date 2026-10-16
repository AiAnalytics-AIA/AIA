// One rule for a run's internal report (run-recovery-and-truth 6e): the report card, the internal
// report panel, project memory and Interpretation Research all read a report's state here, in the
// same words. The API answers the report's artifact when one is stored (READY, with its review), the
// report step's own status until then, or NOT_IN_RUN. Unknown is never good: a report not read, or a
// state this client does not know, is UNKNOWN -- never composing, never approved.

import { t } from "@/i18n/t";
import { ApiError, type ResearchReport } from "@/lib/api";
import type { Tone } from "@/lib/tone";

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

export function reportStatus(report: Pick<ResearchReport, "state" | "reason" | "review_state"> | null | undefined): ReportStatus {
  if (!report) return "UNKNOWN";
  if (report.state === "READY") return reviewStatus(report.review_state);
  if (report.state === "NOT_IN_RUN") return "NONE";
  if (report.state === "FAILED") return report.reason === "report_inputs_refused" ? "REFUSED" : "FAILED";
  if (report.state === "CANCELLED" || report.state === "SKIPPED" || report.state === "SUCCEEDED") return "NOT_MADE";
  return COMPOSING.test(report.state) ? "COMPOSING" : "UNKNOWN";
}

const TONE: Record<ReportStatus, Tone> = {
  NONE: "neutral",
  COMPOSING: "running",
  NOT_MADE: "neutral",
  FAILED: "fault",
  REFUSED: "fault",
  DRAFT: "you",
  APPROVED: "done",
  UNKNOWN: "neutral",
};

export const reportStatusTone = (status: ReportStatus): Tone => TONE[status];
export const reportStatusWords = (status: ReportStatus): string => t(`research.exec.report.status.${status}`);

/** Why an approval was refused, in words: the one refusal a person can act on is the separation of duties. */
export function approvalRefusal(e: unknown): string {
  if (e instanceof ApiError && e.code === "separation_of_duties") return t("research.exec.results.reportApproveIndependent");
  return e instanceof Error ? e.message : String(e);
}
