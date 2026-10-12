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

/** The fields of a design the page draws, in the order the search reads them (domain/project_memory.py). */
export const DESIGN_FIELDS = ["title", "goal", "decision_use", "research_questions", "objectives", "sections", "dimensions"] as const;
export type DesignField = (typeof DESIGN_FIELDS)[number];

const text = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);
const texts = (v: unknown): string[] => (Array.isArray(v) ? v.map(text).filter((x): x is string => x !== null) : []);
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/**
 * What a past design says, field by field, as project memory's search reads it: a dimension by its
 * title (`labels`: the canonical ones and the client's own), else by the id the design stored.
 * Empty fields are left out.
 */
export function designSummary(content: Record<string, unknown>, labels: Readonly<Record<string, string>>): { field: DesignField; values: string[] }[] {
  const plan = isObj(content.research_plan) ? content.research_plan : {};
  const sections: string[] = [];
  for (const s of Array.isArray(content.sections) ? content.sections : []) {
    if (!isObj(s)) continue;
    for (const key of ["title", "object_family"]) {
      const found = text(s[key]);
      if (found && !sections.includes(found)) sections.push(found);
    }
  }
  const persona = isObj(content.persona_dimensions) ? content.persona_dimensions : {};
  const dimensions: string[] = [];
  for (const id of texts(persona.approved)) {
    const title = labels[id] ?? id;
    if (!dimensions.includes(title)) dimensions.push(title);
  }
  const values: Record<DesignField, string[]> = {
    title: [text(content.title)].filter((x): x is string => x !== null),
    goal: [text(content.goal)].filter((x): x is string => x !== null),
    decision_use: [text(content.decision_use)].filter((x): x is string => x !== null),
    research_questions: texts(plan.research_questions),
    objectives: texts(plan.objectives),
    sections,
    dimensions,
  };
  return DESIGN_FIELDS.filter((f) => values[f].length).map((field) => ({ field, values: values[field] }));
}
