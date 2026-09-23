/**
 * The two 13-stage lifecycles, mirrored from the domain.
 *
 * Source of truth: `packages/aia_core/src/aia_core/domain/pipeline.py`
 * (`RESEARCH_STAGES`, `SIMULATION_STAGES`). Stage ids and their Czech labels are
 * domain copy — they live with the domain so the list and its names cannot drift.
 * This file mirrors them for rendering only; the API also returns `label` on every
 * stage, and a rendered stage prefers the API's label.
 */

export const PROJECT_TYPES = ["research", "simulation"] as const;
export type ProjectType = (typeof PROJECT_TYPES)[number];

export const RESEARCH_STAGES = [
  ["BRIEF", "Zadání"],
  ["DEEP_RESEARCH", "Deep Research"],
  ["RESEARCH_DESIGN", "Výzkumný design"],
  ["QUESTIONNAIRE", "Dotazník"],
  ["AUDIENCE", "Cílová skupina"],
  ["DIMENSIONS", "Dimenze"],
  ["SAMPLE_PLAN", "Výběrový plán"],
  ["FIELDWORK", "Respondenti"],
  ["AGGREGATION", "Agregace"],
  ["VALIDATION", "Validace"],
  ["ANALYSIS", "Analýza"],
  ["REPORT", "Report"],
  ["DELIVERY", "Předání"],
] as const;

export const SIMULATION_STAGES = [
  ["BRIEF", "Kontext"],
  ["DEEP_RESEARCH", "Deep Research"],
  ["BASELINE", "Baseline"],
  ["SCENARIO_CONTRACT", "Kontrakt scénáře"],
  ["AUDIENCE", "Cílová skupina"],
  ["DIMENSIONS", "Dimenze"],
  ["VARIANTS", "Varianty"],
  ["WORLDS", "Simulované světy"],
  ["FROZEN_RESULTS", "Zmrazené výsledky"],
  ["COMPARISON", "Srovnání"],
  ["INTERPRETATION", "Interpretace"],
  ["REPORT", "Report"],
  ["DELIVERY", "Předání"],
] as const;

export type ResearchStageId = (typeof RESEARCH_STAGES)[number][0];
export type SimulationStageId = (typeof SIMULATION_STAGES)[number][0];
export type StageId = ResearchStageId | SimulationStageId;

export function stagesFor(projectType: ProjectType) {
  return projectType === "simulation" ? SIMULATION_STAGES : RESEARCH_STAGES;
}

/** Czech label for a stage id, or null when the id is not in this lifecycle. */
export function stageLabel(projectType: ProjectType, stageId: string): string | null {
  const hit = stagesFor(projectType).find(([id]) => id === stageId);
  return hit ? hit[1] : null;
}
