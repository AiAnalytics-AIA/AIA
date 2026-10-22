import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import type { WorkingImpact } from "./api";
import { PIPELINE_STAGES, stageImpacts } from "./working-impact";
import { STAGE_ORDER } from "./workbench-stages";

// domain/pipeline.py's research stage ids, held there by test_pipeline_stage_fixture.py.
const PIPELINE: string[] = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/pipeline_stages/stages.json"), "utf8")).research;

const impact = (stages: [string, string][]): WorkingImpact => ({
  working_revision: 4, design_revision_id: "REV-1", design_revision: 1, changed: ["sections"],
  stages: stages.map(([stage, word]) => ({ stage, impact: word })),
});
const all = (word: string, over: Record<string, string> = {}) => impact(PIPELINE.map((s) => [s, over[s] ?? word]));

describe("PIPELINE_STAGES", () => {
  it("reads every pipeline stage the server answers for, and names only those", () => {
    expect(new Set(Object.values(PIPELINE_STAGES).flat())).toEqual(new Set(PIPELINE));
    expect(Object.keys(PIPELINE_STAGES).sort()).toEqual([...STAGE_ORDER].sort());
  });
});

describe("stageImpacts", () => {
  it("reads a questionnaire edit: Dotazník changed, everything after it to re-check, aggregation on both results and the Sociomap", () => {
    const after = Object.fromEntries(PIPELINE.slice(PIPELINE.indexOf("AUDIENCE")).map((s) => [s, "RECHECK"]));
    expect(stageImpacts(all("CURRENT", { ...after, QUESTIONNAIRE: "CHANGED" }))).toEqual({
      brief: "CURRENT", design: "CURRENT", questionnaire: "CHANGED", audience: "RECHECK", dimensions: "RECHECK", sample: "RECHECK",
      fieldwork: "RECHECK", results: "RECHECK", sociomap: "RECHECK", analysis: "RECHECK", report: "RECHECK",
    });
  });

  it("takes the worst answer where a stage reads several: a Brief material changed is the Brief changed", () => {
    expect(stageImpacts(all("CURRENT", { DEEP_RESEARCH: "CHANGED" }))).toMatchObject({ brief: "CHANGED", design: "CURRENT" });
    expect(stageImpacts(all("CURRENT", { DELIVERY: "RECHECK" }))).toMatchObject({ report: "RECHECK" });
  });

  it("shows nothing for a stage whose pipeline stages are not all answered with a known word, never CURRENT", () => {
    const got = stageImpacts(impact([["BRIEF", "CURRENT"], ["RESEARCH_DESIGN", "CURRENT"], ["QUESTIONNAIRE", "UNKNOWN"], ["REPORT", "CURRENT"], ["DELIVERY", "toString"]]));
    expect(got).toEqual({ design: "CURRENT" });
  });

  it("shows nothing without an answer", () => {
    expect(stageImpacts(null)).toEqual({});
    expect(stageImpacts(undefined)).toEqual({});
    expect(stageImpacts(impact([]))).toEqual({});
  });
});
