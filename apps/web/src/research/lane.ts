// Each design stage's state, read from the study's working content: what the stage
// track shows beside a stage's name, and what the inspector lists as still standing
// between the design and a run. The same conditions the stages' docks already use
// (canAnalyse, the 4-15 set rule, questions without wording, audienceReady); nothing
// here is a new rule. The run stages (run, progress, results) take their state from
// the study's runs, which the caller passes when it has them; without them they say
// nothing rather than guess (CLAUDE.md § 8: never stamp a guess).

import { runState, type RunLike } from "@/lib/run-state";

import { canAnalyse } from "./brief";
import { audienceReady } from "./audience";
import type { ResearchProject } from "./model";
import { trackedSets } from "./plan";
import { proposalAnalysis } from "./plan-edit";
import { chosenDimensions } from "./persona";
import { SET_PRESET, type SetLimits, questionnaireHasQuestions, sections, setSizeRefused } from "./questionnaire";
import type { ResearchState } from "./store";
import type { StepKey } from "./steps";
import type { ResearchRunSummary } from "@/lib/api";

/** done: nothing missing; you: a person must act; running: the machine works; idle: not started or nothing to say. */
export type LaneTone = "done" | "you" | "running" | "fault" | "idle";
export type LaneStage = { tone: LaneTone; line: string };
/** Something that stops the design from running, with the stage that fixes it. */
export type Blocker = { step: StepKey; label: string; detail: string };

// A tracked set's size by the limits in force (GET …/research/limits tracked_set); a caller that has
// not read them passes nothing and is held to the code's preset.
const setRange = (l: SetLimits) => `${l.recommended_min}–${l.max}`;

const plural = (n: number, one: string, few: string, many: string) => (n === 1 ? one : n >= 2 && n <= 4 ? few : many);

function briefStage(p: ResearchProject): LaneStage {
  return canAnalyse(p) ? { tone: "done", line: "Hotovo" } : { tone: "you", line: "Chybí cíl" };
}

function planStage(state: Pick<ResearchState, "project" | "analysis">, l: SetLimits = SET_PRESET): LaneStage {
  const a = proposalAnalysis(state);
  if (!a) return { tone: "idle", line: "Bez návrhu" };
  const bad = trackedSets(a).filter((s) => setSizeRefused((s.objects || []).length, l)).length;
  if (bad) return { tone: "you", line: `${bad} ${plural(bad, "sada", "sady", "sad")} mimo ${setRange(l)}` };
  return { tone: "done", line: "Hotovo" };
}

/** Questions without wording, sets the editors stop (setSizeRefused), and the total, as the questionnaire's dock counts them. */
export function questionnaireIssues(p: ResearchProject, l: SetLimits = SET_PRESET): { questions: number; sets: number; empty: number; badSets: number } {
  let questions = 0, sets = 0, empty = 0, badSets = 0;
  for (const s of sections(p)) {
    if (s.type === "questions") {
      for (const q of s.questions || []) {
        questions += 1;
        if (!String(q.text || "").trim()) empty += 1;
      }
    } else if (s.type === "object_battery") {
      sets += 1;
      if (setSizeRefused((s.objects || []).length, l)) badSets += 1;
    }
  }
  return { questions, sets, empty, badSets };
}

function questionnaireStage(p: ResearchProject, l: SetLimits = SET_PRESET): LaneStage {
  const { questions, sets, empty, badSets } = questionnaireIssues(p, l);
  if (!questions && !sets) return { tone: "idle", line: "Zatím prázdný" };
  const count = [questions ? `${questions} ${plural(questions, "otázka", "otázky", "otázek")}` : "", sets ? `${sets} ${plural(sets, "sada", "sady", "sad")}` : ""].filter(Boolean).join(" · ");
  if (empty) return { tone: "you", line: `${count} · ${empty} bez znění` };
  if (badSets) return { tone: "you", line: `${count} · ${badSets} ${plural(badSets, "sada", "sady", "sad")} mimo ${setRange(l)}` };
  return { tone: "done", line: count };
}

function audienceStage(p: ResearchProject): LaneStage {
  return audienceReady(p) ? { tone: "done", line: "Vybráno" } : { tone: "idle", line: "Nevybráno" };
}

function personaStage(p: ResearchProject): LaneStage {
  const approved = chosenDimensions(p);
  const n = Number(p.n) || 0;
  const d = approved.length ? `${approved.length} ${plural(approved.length, "dimenze", "dimenze", "dimenzí")}` : "Bez dimenzí";
  return n ? { tone: "done", line: `${d} · N=${n}` } : { tone: "idle", line: d };
}

/** Each design stage's state; the run stages are the caller's (they come from the runs). */
export function designLane(state: Pick<ResearchState, "project" | "analysis">, l: SetLimits = SET_PRESET): Record<"brief" | "plan" | "questionnaire" | "audience" | "persona", LaneStage> {
  const p = state.project;
  return {
    brief: briefStage(p),
    plan: planStage(state, l),
    questionnaire: questionnaireStage(p, l),
    audience: audienceStage(p),
    persona: personaStage(p),
  };
}

/**
 * What still stands between the design and a run, in stage order. Only the
 * conditions the stages themselves enforce; the server's readiness on Kontrola
 * stays the authority and may find more.
 */
export function blockers(state: Pick<ResearchState, "project" | "analysis">, l: SetLimits = SET_PRESET): Blocker[] {
  const p = state.project;
  const out: Blocker[] = [];
  if (!canAnalyse(p)) out.push({ step: "brief", label: "Zadání", detail: "Chybí cíl vlastními slovy" });
  const a = proposalAnalysis(state);
  for (const s of trackedSets(a)) {
    const n = (s.objects || []).length;
    if (setSizeRefused(n, l)) out.push({ step: "plan", label: `Návrh · sada „${s.title || "bez názvu"}“`, detail: `${n} položek, potřebuje ${setRange(l)}` });
  }
  const q = questionnaireIssues(p, l);
  if (!questionnaireHasQuestions(p)) out.push({ step: "questionnaire", label: "Dotazník", detail: "Zatím nemá žádnou běžnou otázku" });
  if (q.empty) out.push({ step: "questionnaire", label: "Dotazník", detail: `${q.empty} ${plural(q.empty, "otázka nemá", "otázky nemají", "otázek nemá")} znění` });
  if (q.badSets) out.push({ step: "questionnaire", label: "Dotazník", detail: `${q.badSets} ${plural(q.badSets, "sledovaná sada je", "sledované sady jsou", "sledovaných sad je")} mimo ${setRange(l)} položek` });
  if (!audienceReady(p)) out.push({ step: "audience", label: "Cílová skupina", detail: "Vyberte zdroj respondentů" });
  return out;
}

/**
 * The run stages' state from the study's runs, newest first as the API lists them, each read by
 * `runState` as every screen reads it; null: not loaded (says nothing).
 */
export function runLane(runs: readonly (RunLike & Pick<ResearchRunSummary, "design_revision">)[] | null): Record<"run" | "progress" | "results", LaneStage> {
  const idle = (line: string): LaneStage => ({ tone: "idle", line });
  if (!runs) return { run: idle(""), progress: idle(""), results: idle("") };
  if (!runs.length) return { run: idle("Nespuštěno"), progress: idle("Zatím žádný běh"), results: idle("Zatím nic") };
  const latest = runState(runs[0]!);
  const ready = runs.find((r) => {
    const { state } = runState(r);
    return state === "RESULTS_READY" || state === "REPORT_READY";
  });
  const n = runs.length;
  const line = `Běh ${n}: ${latest.label.toLowerCase()}`;
  return {
    run: { tone: "done", line: `Spuštěno ${n}×` },
    progress: { tone: latest.tone === "neutral" || latest.tone === "world" ? "idle" : latest.tone, line },
    results: ready ? { tone: "done", line: `Revize ${ready.design_revision}` } : idle("Zatím nic"),
  };
}
