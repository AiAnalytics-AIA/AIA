// What the working copy means for each workbench stage (working-copy-edit-ops WCE7d): the server's
// pipeline impact (GET …/research/impact, domain/pipeline.py `stage_impacts`) read onto the
// workbench's stages. Pure. The server decides; a stage it did not answer for, or answered with a
// word this client does not know, shows nothing, never CURRENT.

import type { ResearchRun, StageImpact, WorkingImpact } from "./api";
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

/**
 * What the stage track measures the working copy against: the newest run's Design Revision, so a run
 * whose design is older than the copy says so on every stage the copy reopened; before any run, the
 * newest Design Revision (`id` undefined, the server's default). Null while the runs are not known:
 * nothing is read, rather than a base guessed.
 */
export type ImpactBase = { id?: string; run: number | null };

export function impactBase(runs: readonly Pick<ResearchRun, "design_revision_id" | "design_revision">[] | null): ImpactBase | null {
  if (!runs) return null;
  const latest = runs[0];
  return latest ? { id: latest.design_revision_id, run: latest.design_revision } : { run: null };
}

/** A stage's impact in words for the stage track; CURRENT says nothing. */
export function impactWords(impact: StageImpact, base: ImpactBase, designRevision: number): string | null {
  if (impact === "CHANGED") return base.run !== null ? `změněno od běhu (revize ${base.run})` : `změněno od revize ${designRevision}`;
  if (impact === "RECHECK") return base.run !== null ? "ověřit znovu: návrh se od běhu změnil" : "ověřit znovu: změna dříve v návrhu";
  return null;
}

export type ImpactMark = { impact: Exclude<StageImpact, "CURRENT">; words: string };

/**
 * Each stage the working copy reopened, with its words, from the server's answer against `base`. An
 * answer about another Design Revision than the base asked for names nothing.
 */
export function impactMarks(impact: WorkingImpact | null | undefined, base: ImpactBase | null): Partial<Record<WorkbenchStage, ImpactMark>> {
  if (!impact || !base || (base.id !== undefined && impact.design_revision_id !== base.id)) return {};
  const out: Partial<Record<WorkbenchStage, ImpactMark>> = {};
  for (const [stage, word] of Object.entries(stageImpacts(impact)) as [WorkbenchStage, StageImpact][]) {
    const words = impactWords(word, base, impact.design_revision);
    if (words && word !== "CURRENT") out[stage] = { impact: word, words };
  }
  return out;
}
