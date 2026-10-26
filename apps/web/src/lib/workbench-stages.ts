// The research workbench's stages (plan research-lead-workbench D2, ADR 0026): the prototype's
// eleven stages in six phases (prototypes/research-lead-v2/src/model/terms.ts @ 9b50963f), each
// one of today's routes and, on Výsledky, one of ResultsWorkspace's views (its hash). A stage's
// state is the lane's (src/research/lane.ts): nothing here decides a tone of its own.

import type { LaneStage, LaneTone } from "@/research/lane";
import type { StepKey } from "@/research/steps";

export type WorkbenchStage =
  | "brief" | "design" | "questionnaire" | "audience" | "dimensions" | "sample"
  | "fieldwork" | "results" | "sociomap" | "analysis" | "report";
export type Phase = "design" | "sample" | "execution" | "evidence" | "interpretation" | "delivery";
/** The status glyph's tone (Glyph.tsx), after the design system's grammar. */
export type Tone = "done" | "running" | "you" | "fault" | "inert" | "ready";

export const STAGE_ORDER: readonly WorkbenchStage[] = [
  "brief", "design", "questionnaire", "audience", "dimensions", "sample",
  "fieldwork", "results", "sociomap", "analysis", "report",
];

export const STAGES: Record<WorkbenchStage, { label: string; short: string; phase: Phase; step: StepKey; view?: string }> = {
  brief: { label: "Zadání", short: "Zadání", phase: "design", step: "brief" },
  design: { label: "Návrh", short: "Návrh", phase: "design", step: "plan" },
  questionnaire: { label: "Dotazník", short: "Dotazník", phase: "design", step: "questionnaire" },
  audience: { label: "Cílová skupina", short: "Cíl. skupina", phase: "sample", step: "audience" },
  dimensions: { label: "Dimenze", short: "Dimenze", phase: "sample", step: "persona" },
  sample: { label: "Vzorek", short: "Vzorek", phase: "sample", step: "persona", view: "sample" },
  fieldwork: { label: "Sběr dat", short: "Sběr dat", phase: "execution", step: "run" },
  results: { label: "Výsledky", short: "Výsledky", phase: "evidence", step: "results", view: "data" },
  sociomap: { label: "Sociomapa", short: "Sociomapa", phase: "evidence", step: "results", view: "maps" },
  analysis: { label: "Analýza", short: "Analýza", phase: "interpretation", step: "results", view: "analysis" },
  report: { label: "Zpráva", short: "Zpráva", phase: "delivery", step: "results", view: "report" },
};

export const PHASES: readonly { id: Phase; label: string }[] = [
  { id: "design", label: "Návrh výzkumu" },
  { id: "sample", label: "Vymezení vzorku" },
  { id: "execution", label: "Sběr" },
  { id: "evidence", label: "Evidence" },
  { id: "interpretation", label: "Interpretace" },
  { id: "delivery", label: "Předání" },
];

export const isWorkbenchStage = (x: string): x is WorkbenchStage => (STAGE_ORDER as readonly string[]).includes(x);

/** The URL of a stage: its step's, with the view as the hash ResultsWorkspace reads. */
export function stageHref(stage: WorkbenchStage, stepHref: (step: StepKey) => string): string {
  const s = STAGES[stage];
  return s.view ? `${stepHref(s.step)}#${s.view}` : stepHref(s.step);
}

/** The stage a route shows: its step, and on Výsledky or Dimenze the view its hash names. */
export function stageOf(step: StepKey, hash: string): WorkbenchStage {
  const view = hash.replace(/^#/, "");
  if (step === "persona") return view === "sample" ? "sample" : "dimensions";
  if (step === "results") {
    if (view.startsWith("measure-") || view === "data" || view === "res-aggregate") return "results";
    if (view === "maps" || view === "res-sociomap" || view === "res-sociomapping") return "sociomap";
    if (view === "analysis" || view === "res-analysis") return "analysis";
    if (view === "report" || view === "res-report" || view === "res-literature") return "report";
    return "results";
  }
  if (step === "run" || step === "progress") return "fieldwork";
  if (step === "plan") return "design";
  if (step === "brief" || step === "questionnaire" || step === "audience") return step;
  return "brief";
}

const TONE: Record<LaneTone, Tone> = { done: "done", you: "you", running: "running", fault: "fault", idle: "inert" };

/** A stage's status in one word, by its tone: what the navigator shows under the stage's name. */
const WORD: Record<Tone, string> = { done: "Hotovo", running: "Běží", you: "Čeká na vás", fault: "Chyba", ready: "Připraveno", inert: "" };

/**
 * A stage's tone, line and word from the lane, keyed by step. Dimenze and Vzorek read their own
 * entries (`dimensions`, `sample`), not the classic track's shared persona step (#945); the result
 * data reads Výsledky's. Unknown says nothing: an empty word and the inert tone, never a guess, and
 * a stage is done only where the lane says that stage is:
 * - Sběr dat is done when the newest run's results are ready, moving, waiting or at fault as that
 *   run is; a newest run cancelled or unread says so in its line, inert. Kontrola's "Spuštěno"
 *   only says a run was started, never that the fieldwork is done.
 * - Sociomapa, Analýza and Zpráva are Výsledky's views; the lane knows no map, module or report of
 *   their own (research-lead-workbench F25), so they are inert, with Výsledky's line.
 */
export function stageState(stage: WorkbenchStage, lane: Partial<Record<StepKey | "dimensions" | "sample", LaneStage>>): { tone: Tone; line: string; word: string } {
  const said = (tone: Tone, line: string) => ({ tone, line, word: WORD[tone] });
  const from = (step: StepKey | "dimensions" | "sample") => {
    const s = lane[step];
    return s ? said(TONE[s.tone], s.line) : said("inert", "");
  };
  if (stage === "fieldwork") {
    const p = lane.progress;
    if (p && p.tone !== "idle") return from("progress");
    // No run yet: Kontrola's "Nespuštěno". A run whose state says nothing: its own line, inert.
    return lane.run?.tone === "done" && p ? said("inert", p.line) : said("inert", lane.run?.line ?? "");
  }
  if (stage === "sociomap" || stage === "analysis" || stage === "report") return said("inert", lane.results?.line ?? "");
  if (stage === "dimensions" || stage === "sample") return from(stage);
  return from(STAGES[stage].step);
}
