// Návrh's research questions with their coverage (artifact-design DSN2). The coverage is the
// server's: readiness's research_trace over a Design Revision (domain/research_trace.py). This
// module adds no rule; it reads that trace against the working copy's research questions and says
// how old the reading is. Until coverage is computed on the working revision
// (working-copy-edit-ops#WCE7) it is read from the study's newest Design Revision, and a research
// question that revision does not hold reads "not checked", never covered.

import type { DesignRevision, OutlookVerdict, QuestionOutlook, ResearchTrace } from "@/lib/api";
import { type TraceMeasure, traceMeasures } from "@/lib/research-execution";
import { linkKey } from "@/research/trace";

/** V2's chip: pokryto / částečně / mezera, and unknown, which is never pokryto (CLAUDE.md § 8). */
export type CoverageStatus = "covered" | "partial" | "gap" | "unknown";

/** The trace's own verdict in V2's words; a verdict this client does not know is unknown. */
export function coverageStatus(verdict: OutlookVerdict | string): CoverageStatus {
  if (verdict === "ANSWERABLE") return "covered";
  if (verdict === "AT_RISK") return "partial";
  if (verdict === "UNANSWERABLE") return "gap";
  return "unknown";
}

/** The study's newest Design Revision, by its number, whatever order the list came in. */
export function newestRevision(revisions: readonly DesignRevision[]): DesignRevision | null {
  let out: DesignRevision | null = null;
  for (const r of revisions) if (!out || r.revision > out.revision) out = r;
  return out;
}

/**
 * Whether the revision's coverage is the working copy's: true when the revision was made from the
 * working revision the copy is at; false when the copy has moved since; null when either is not
 * recorded (a revision made before ADR 0026, a copy never saved) -- unknown, never "current".
 */
export function revisionIsCurrent(revision: Pick<DesignRevision, "workspace_revision">, working: number | null): boolean | null {
  const from = revision.workspace_revision;
  if (typeof from !== "number" || working === null) return null;
  return from === working;
}

/** One measure as Návrh draws it: its words, its verdict, and where Dotazník shows it. */
export type CoverageMeasure = TraceMeasure & { anchor: string };

export type RqCoverage = {
  text: string;
  /** False: the revision read does not hold this research question; its status is unknown. */
  checked: boolean;
  status: CoverageStatus;
  measures: CoverageMeasure[];
  /** The comparison the plan declares for it, as the trace reads it; null when none. */
  comparison: string | null;
  /** The trace's reason codes (gaps), in its order. */
  reasons: string[];
};

/** Where Dotazník draws a measure (QuestionnaireStep's ids, lib/answerability.ts). */
function anchorOf(key: string, outlook: readonly QuestionOutlook[]): string {
  const item = outlook.find((o) => o.question_id === key);
  if (item) return item.battery_id ? `qset_${item.battery_id}` : `qedit_${item.question_id}`;
  if (outlook.some((o) => o.battery_id === key)) return `qset_${key}`;
  return `qedit_${key}`;
}

/**
 * Each of the working copy's research questions with its coverage from `trace`, in the working
 * copy's order. A question is matched by its text as the server compares a link (linkKey); one the
 * trace does not hold is not checked. A trace question the copy no longer states is left out.
 */
export function rqCoverage(working: readonly string[], trace: ResearchTrace | null, outlook: readonly QuestionOutlook[]): RqCoverage[] {
  const byKey = new Map((trace?.questions ?? []).map((q) => [linkKey(q.text), q]));
  return working.map((text) => {
    const q = byKey.get(linkKey(text));
    if (!q) return { text, checked: false, status: "unknown", measures: [], comparison: null, reasons: [] };
    return {
      text,
      checked: true,
      status: coverageStatus(q.verdict),
      measures: traceMeasures(q, outlook).map((m) => ({ ...m, anchor: anchorOf(m.key, outlook) })),
      comparison: q.comparison ?? null,
      reasons: [...q.reasons],
    };
  });
}
