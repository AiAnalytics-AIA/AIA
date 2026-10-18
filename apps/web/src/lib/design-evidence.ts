// What Design Research found for each research question (plan run-recovery-and-truth 3d).
// The run's proposal lists, per subject, its accepted findings (EVIDENCE) or none (GAP);
// its bundle keeps every rejected finding with the reason it was quarantined. This module
// joins the two to one research question, by its text as the run studied it. Pure: no
// fetch. External evidence informs the design; it is never respondent evidence.

import type { DeepResearchBundle, DeepResearchRun, DesignFinding, DesignProposal } from "@/lib/api";
import { linkKey } from "@/research/trace";

export type QuestionEvidence = {
  /** Whether the run researched this research question at all (it may predate it). */
  studied: boolean;
  findings: DesignFinding[];
  /** Every rejected finding on it or on a question x object cross of it, by reason. */
  rejected: { reason: string; count: number }[];
};

/**
 * A run of the design checkpoint (ADR 0021): Design Research, or a run made before purposes were
 * recorded (legacy-unversioned), which only the design stage could start. An Interpretation
 * Research run belongs to a run's results, never to the questionnaire (PC18).
 */
export const isDesignRun = (run: Pick<DeepResearchRun, "purpose">): boolean => run.purpose === "DESIGN_RESEARCH" || run.purpose == null;

/** The study's newest finished Design Research run; runs come newest first. */
export function latestDesignRun(runs: readonly DeepResearchRun[]): DeepResearchRun | null {
  return runs.find((r) => r.purpose === "DESIGN_RESEARCH" && r.phase === "COMPLETED") ?? null;
}

export function questionEvidence(rq: string, proposal: DesignProposal, bundle: DeepResearchBundle): QuestionEvidence {
  const subjects = bundle.subjects ?? [];
  const own = new Set(subjects.filter((s) => s.kind === "QUESTION" && linkKey(s.text) === linkKey(rq)).map((s) => s.key));
  const related = new Set([...own, ...subjects.filter((s) => s.question_key && own.has(s.question_key)).map((s) => s.key)]);
  const findings = proposal.items.filter((i) => own.has(i.subject_key)).flatMap((i) => i.findings);
  const trackSubject = new Map((bundle.tracks ?? []).map((t) => [t.track_id, t.subject_key]));
  const counts = new Map<string, number>();
  for (const q of bundle.quarantined) {
    const subject = q.evidence?.subject_key ?? (q.track_id ? trackSubject.get(q.track_id) : undefined);
    if (subject && related.has(subject)) counts.set(q.reason, (counts.get(q.reason) ?? 0) + 1);
  }
  const rejected = [...counts].map(([reason, count]) => ({ reason, count })).sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason));
  return { studied: own.size > 0, findings, rejected };
}
