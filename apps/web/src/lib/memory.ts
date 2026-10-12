// How a project-memory search reads (plans/project-memory-reuse.md M1d). The server decides
// what matches (one client, every word, accent-folded); this says when a query is worth
// sending and how a hit explains itself.

import type { MemoryHit, ResearchReport, ResearchRun, ResearchRunSummary, StudyKind } from "./api";
import { isSynthetic } from "./research-execution";

/** The server refuses a shorter query (MIN_QUERY_LENGTH); the page does not send one. */
export const MIN_QUERY = 2;

/** The query to send, or null while it is too short to say anything. */
export function sendable(q: string): string | null {
  const trimmed = q.trim();
  return trimmed.length >= MIN_QUERY ? trimmed : null;
}

/** The hits of one kind: Výzkumy shows research, the memory page shows every kind. */
export function ofKind(hits: MemoryHit[], kind: StudyKind | null): MemoryHit[] {
  return kind ? hits.filter((h) => h.kind === kind) : hits;
}

/** What a hit says matched, field by field, without repeating the study's own name. */
export function evidence(hit: MemoryHit): { field: MemoryHit["matches"][number]["field"]; text: string }[] {
  return hit.matches.filter((m) => m.field !== "name").flatMap((m) => m.texts.map((text) => ({ field: m.field, text })));
}

/**
 * What a past run's data is, as far as the page knows:
 * - `synthetic`: fictional, by its source or by a step's origin, never evidence;
 * - `no_data`: read in full, and no step produced respondent data;
 * - `unknown`: a summary (no steps) of a run not on the fixture, or an origin AIA has no word
 *   for. Never "measured": no origin AIA stamps today is evidence.
 */
export type RunDataLabel = "synthetic" | "no_data" | "unknown";
/** A run's report: none in the run, a draft, approved for internal use, or not yet known. */
export type RunReportLabel = "none" | "draft" | "approved_internal" | "unknown";

export type RunLabels = {
  data: RunDataLabel;
  report: RunReportLabel;
  /** A Sociomap, an analysis or a report: each is internal only (PROGRESS D6, ADR 0016). */
  internal: boolean;
};

const INTERNAL_KINDS = new Set(["research_sociomap", "research_sociomapping", "research_analysis", "research_report"]);

/**
 * The labels of one past run (plans/project-memory-reuse.md M2b), from what the API returned
 * and nothing else. Unknown is said, never scored as good: a report not read is not approved,
 * and a run read as a summary is not real data.
 */
export function runLabels(run: ResearchRun | ResearchRunSummary, report?: ResearchReport | null): RunLabels {
  const steps = "steps" in run ? run.steps : null;
  let data: RunDataLabel = "unknown";
  if (isSynthetic(run)) data = "synthetic";
  // Fieldwork is the step that makes respondent data; without its artifact there is none.
  else if (steps && !steps.some((s) => s.node_key === "run" && s.artifact_id)) data = "no_data";
  const hasReport = steps ? steps.some((s) => s.kind === "research_report") : null;
  let reportLabel: RunReportLabel = "unknown";
  if (hasReport === false) reportLabel = "none";
  else if (report?.state === "READY") reportLabel = report.review_state === "APPROVED_INTERNAL" ? "approved_internal" : "draft";
  const internal = steps ? steps.some((s) => INTERNAL_KINDS.has(s.kind)) : false;
  return { data, report: reportLabel, internal };
}
