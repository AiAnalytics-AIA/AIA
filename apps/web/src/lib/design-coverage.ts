// Návrh's research questions with their coverage (artifact-design DSN2). The coverage is the
// server's: readiness's research_trace on the working revision (domain/research_trace.py, WCE7).
// This module adds no rule; it reads that trace against the working copy's research questions, and a
// research question the trace does not hold reads "not checked", never covered.

import type { OutlookVerdict, QuestionOutlook, ResearchTrace } from "@/lib/api";
import { type TraceMeasure, traceMeasures } from "@/lib/research-execution";
import type { ResearchProject } from "@/research/model";
import { linkKey, researchQuestionsOf } from "@/research/trace";

/** V2's chip: pokryto / částečně / mezera, and unknown, which is never pokryto (CLAUDE.md § 8). */
export type CoverageStatus = "covered" | "partial" | "gap" | "unknown";

/** The trace's own verdict in V2's words; a verdict this client does not know is unknown. */
export function coverageStatus(verdict: OutlookVerdict | string): CoverageStatus {
  if (verdict === "ANSWERABLE") return "covered";
  if (verdict === "AT_RISK") return "partial";
  if (verdict === "UNANSWERABLE") return "gap";
  return "unknown";
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

/** What the coverage is computed from: the research questions, their comparisons and the questionnaire. */
export type CoverageInputs = readonly [string, unknown, unknown];

export function coverageInputs(p: ResearchProject): CoverageInputs {
  const plan = (p.research_plan ?? {}) as { research_question_comparisons?: unknown };
  return [researchQuestionsOf(p).join("\n"), plan.research_question_comparisons, p.sections];
}

/**
 * Whether the coverage must be read again: something it is computed from changed. The store keeps an
 * unchanged part's object as it was, so a save that touched only a comment or a set's name (which
 * cannot move the coverage) is not a reason to recompute the whole readiness.
 */
export const coverageInputsChanged = (a: CoverageInputs | null, b: CoverageInputs): boolean =>
  a === null || a[0] !== b[0] || a[1] !== b[1] || a[2] !== b[2];

/** The working revision the coverage is read on, and the inputs it holds; null inputs: not known to be saved. */
export type CoverageAt = { revision: number | null; inputs: CoverageInputs | null };
type Copy = { revision: number | null; save: { kind: string }; project: ResearchProject };

/**
 * Where the coverage starts. A copy whose change is not saved yet (the stage opened within another's
 * autosave) holds inputs its revision does not: they are not taken as read, so the save that lands
 * moves the coverage on and nothing older is shown as current.
 */
export const seedCoverageAt = (c: Copy): CoverageAt => ({ revision: c.revision, inputs: c.save.kind === "saved" ? coverageInputs(c.project) : null });

/** The coverage's revision after `c`: a saved revision that changed what it is computed from, else as it was. */
export function nextCoverageAt(at: CoverageAt, c: Copy): CoverageAt {
  if (c.save.kind !== "saved" || c.revision === null || c.revision === at.revision) return at;
  const inputs = coverageInputs(c.project);
  return coverageInputsChanged(at.inputs, inputs) ? { revision: c.revision, inputs } : at;
}
