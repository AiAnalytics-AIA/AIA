// What the working copy means for each workbench stage (working-copy-edit-ops WCE7d): the server's
// pipeline impact (GET …/research/impact, domain/pipeline.py `stage_impacts`) read onto the
// workbench's stages. Pure. The server decides; a stage it did not answer for, or answered with a
// word this client does not know, shows nothing, never CURRENT.

import type { StageImpact, WorkingImpact } from "./api";
import type { WorkbenchStage } from "./workbench-stages";

/**
 * The pipeline stages each workbench stage reads, every one of domain/pipeline.py RESEARCH_STAGES
 * (held to packages/aia_core/tests/fixtures/pipeline_stages/stages.json). The Brief's materials are
 * what DEEP_RESEARCH reads; AGGREGATION computes both the results and the Sociomap; VALIDATION's
 * policy reads on the results, DELIVERY's on the report.
 */
export const PIPELINE_STAGES: Readonly<Record<WorkbenchStage, readonly string[]>> = {
  brief: ["BRIEF", "DEEP_RESEARCH"],
  design: ["RESEARCH_DESIGN"],
  questionnaire: ["QUESTIONNAIRE"],
  audience: ["AUDIENCE"],
  dimensions: ["DIMENSIONS"],
  sample: ["SAMPLE_PLAN"],
  fieldwork: ["FIELDWORK"],
  results: ["AGGREGATION", "VALIDATION"],
  sociomap: ["AGGREGATION"],
  analysis: ["ANALYSIS"],
  report: ["REPORT", "DELIVERY"],
};

/** Worst first: a stage that reads several pipeline stages takes the worst answer among them. */
const RANK: Readonly<Record<StageImpact, number>> = { CHANGED: 0, RECHECK: 1, CURRENT: 2 };

const known = (word: string | undefined): word is StageImpact => word !== undefined && Object.hasOwn(RANK, word);

/** Each workbench stage's impact, only where the server answered every pipeline stage it reads with a known word. */
export function stageImpacts(impact: WorkingImpact | null | undefined): Partial<Record<WorkbenchStage, StageImpact>> {
  if (!impact) return {};
  const answers = new Map(impact.stages.map((s) => [s.stage, s.impact] as const));
  const out: Partial<Record<WorkbenchStage, StageImpact>> = {};
  for (const [stage, pipeline] of Object.entries(PIPELINE_STAGES) as [WorkbenchStage, readonly string[]][]) {
    const words = pipeline.map((p) => answers.get(p));
    if (words.every(known)) out[stage] = words.reduce((a, b) => (RANK[b] < RANK[a] ? b : a));
  }
  return out;
}
