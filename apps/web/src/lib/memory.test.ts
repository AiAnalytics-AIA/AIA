import { describe, expect, it } from "vitest";

import type { MemoryHit, ResearchReport, ResearchRun, ResearchRunSummary, ResearchStep } from "./api";
import { designSummary, evidence, ofKind, runLabels, sendable, sourceLabelWords } from "./memory";

const hit = (over: Partial<MemoryHit> = {}): MemoryHit => ({
  study_id: "STU-1",
  name: "Ranní káva",
  kind: "RESEARCH",
  status: "ACTIVE",
  modified_at: null,
  source: "design",
  design_revision: 1,
  matches: [
    { field: "name", texts: ["Ranní káva"] },
    { field: "research_questions", texts: ["Kdo pije kávu ráno?", "Kde ji kupuje?"] },
    { field: "dimensions", texts: ["Zdraví"] },
  ],
  ...over,
});

describe("project memory search", () => {
  it("sends nothing shorter than two characters", () => {
    expect(sendable(" k ")).toBeNull();
    expect(sendable("  ká ")).toBe("ká");
  });

  it("keeps the hits of one kind, or all", () => {
    const hits = [hit(), hit({ study_id: "STU-2", kind: "SIMULATION" })];
    expect(ofKind(hits, "RESEARCH").map((h) => h.study_id)).toEqual(["STU-1"]);
    expect(ofKind(hits, null)).toHaveLength(2);
  });

  it("says what matched, without repeating the study's name", () => {
    expect(evidence(hit())).toEqual([
      { field: "research_questions", text: "Kdo pije kávu ráno?" },
      { field: "research_questions", text: "Kde ji kupuje?" },
      { field: "dimensions", text: "Zdraví" },
    ]);
    expect(evidence(hit({ matches: [{ field: "name", texts: ["Ranní káva"] }] }))).toEqual([]);
  });
});

const step = (node_key: string, kind: string, extra: Partial<ResearchStep> = {}): ResearchStep => ({
  step_id: `STEP-${node_key}`, node_key, kind, stage_type: "BRIEF", status: "SUCCEEDED", waiting_reason: null, attempts_recorded: 1, max_attempts: 3,
  started_at: null, finished_at: null, failure_class: null, error_message: null, artifact_id: null, data_origin: null, ...extra,
});
const fullRun = (fieldwork_source: string, steps: ResearchStep[]): ResearchRun => ({
  run_id: "RUN-1", study_id: "STU-1", design_revision_id: "REV-1", design_revision: 1, status: "COMPLETED", phase: "COMPLETED",
  needs_attention: false, is_terminal: true, retryable: false, cancel_requested: false, fieldwork_source, retry_of: null,
  created: null, created_at: "2026-10-01T08:00:00Z", started_at: null, finished_at: null, steps, artifact_ids: [],
  actual_cost_usd: null, population: null,
} as ResearchRun);
const report = (review_state: ResearchReport["review_state"]): ResearchReport =>
  ({ run_id: "RUN-1", state: "READY", internal_only: true, review_state, synthetic: true } as ResearchReport);

describe("a past run's labels", () => {
  const fictional = fullRun("ai_runtime", [
    step("run", "research_fieldwork", { artifact_id: "ART-3", data_origin: "SYNTHETIC_AI_FICTIONAL" }),
    step("sociomap", "research_sociomap", { artifact_id: "ART-5" }),
    step("report", "research_report", { artifact_id: "ART-r" }),
  ]);

  it("labels AI respondents on fictional personas synthetic, the report a draft, the run internal", () => {
    expect(runLabels(fictional, report("DRAFT_UNAPPROVED"))).toEqual({ data: "synthetic", report: "draft", internal: true });
    expect(runLabels(fictional, report("APPROVED_INTERNAL")).report).toBe("approved_internal");
  });

  it("never reads a report it did not read as approved, nor a summary as real data", () => {
    expect(runLabels(fictional).report).toBe("unknown");
    expect(runLabels(fictional, { ...report(undefined), state: "NOT_IN_RUN" }).report).toBe("unknown");
    const summary: Partial<ResearchRun> = { ...fullRun("ai_runtime", []) };
    delete summary.steps;
    delete summary.artifact_ids;
    expect(runLabels(summary as ResearchRunSummary)).toEqual({ data: "unknown", report: "unknown", internal: false });
    expect(runLabels({ ...summary, fieldwork_source: "synthetic_fixture" } as ResearchRunSummary).data).toBe("synthetic");
  });

  it("says a run whose fieldwork made nothing has no data and no report", () => {
    const parked = fullRun("ai_runtime", [step("compile", "research_compile", { artifact_id: "ART-1" }), step("run", "research_fieldwork", { status: "WAITING_PROVIDER" })]);
    expect(runLabels(parked)).toEqual({ data: "no_data", report: "none", internal: false });
  });
});

describe("a past design, as the page draws it", () => {
  it("reads the fields the search reads, a dimension by its title, an unknown one by its id, nothing empty", () => {
    const content = {
      title: "Ranní káva", goal: " ", decision_use: "Uvést nápoj?",
      research_plan: { research_questions: ["Kdo pije kávu ráno?", ""], objectives: [] },
      sections: [{ title: "Návyky" }, { type: "battery", title: "Značky", object_family: "Značky" }, "x"],
      persona_dimensions: { approved: ["zdravi", "KNI-1", "neznama"] },
    };
    expect(designSummary(content, { zdravi: "Zdraví", "KNI-1": "Ranní rituály" })).toEqual([
      { field: "title", values: ["Ranní káva"] },
      { field: "decision_use", values: ["Uvést nápoj?"] },
      { field: "research_questions", values: ["Kdo pije kávu ráno?"] },
      { field: "sections", values: ["Návyky", "Značky"] },
      { field: "dimensions", values: ["Zdraví", "Ranní rituály", "neznama"] },
    ]);
    expect(designSummary({}, {})).toEqual([]);
  });
});

describe("a reused design's labels, in words", () => {
  const base = { synthetic: false, draft: false, never_run: false, unlabelled_data: false, run_ids: [], report_artifact_ids: [] };
  it("says every label the source carries, in a fixed order, and none for a clean source", () => {
    expect(sourceLabelWords({ ...base, synthetic: true, draft: true, never_run: false, unlabelled_data: true })).toEqual(["synthetic", "unlabelled", "draft"]);
    expect(sourceLabelWords({ ...base, never_run: true })).toEqual(["neverRun"]);
    expect(sourceLabelWords(base)).toEqual([]);
  });
});
