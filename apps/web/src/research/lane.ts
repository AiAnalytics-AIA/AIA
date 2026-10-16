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
import { withApproval } from "./persona";
import { questionnaireHasQuestions, sections } from "./questionnaire";
import type { ResearchState } from "./store";
import type { StepKey } from "./steps";
import type { ResearchRunSummary } from "@/lib/api";

/** done: nothing missing; you: a person must act; running: the machine works; idle: not started or nothing to say. */
export type LaneTone = "done" | "you" | "running" | "fault" | "idle";
export type LaneStage = { tone: LaneTone; line: string };
/** Something that stops the design from running, with the stage that fixes it. */
export type Blocker = { step: StepKey; label: string; detail: string };

export const SET_MIN = 4;
export const SET_MAX = 15;
const setSizeOk = (n: number) => n >= SET_MIN && n <= SET_MAX;

const plural = (n: number, one: string, few: string, many: string) => (n === 1 ? one : n >= 2 && n <= 4 ? few : many);

export function briefStage(p: ResearchProject): LaneStage {
  return canAnalyse(p) ? { tone: "done", line: "Hotovo" } : { tone: "you", line: "Chybí cíl" };
}

export function planStage(state: Pick<ResearchState, "project" | "analysis">): LaneStage {
  const a = proposalAnalysis(state);
  if (!a) return { tone: "idle", line: "Bez návrhu" };
  const bad = trackedSets(a).filter((s) => !setSizeOk((s.objects || []).length)).length;
  if (bad) return { tone: "you", line: `${bad} ${plural(bad, "sada mimo 4–15", "sady mimo 4–15", "sad mimo 4–15")}` };
  return { tone: "done", line: "Hotovo" };
}

/** Questions without wording, sets outside 4-15, and the total, as the questionnaire's dock counts them. */
export function questionnaireIssues(p: ResearchProject): { questions: number; sets: number; empty: number; badSets: number } {
  let questions = 0, sets = 0, empty = 0, badSets = 0;
  for (const s of sections(p)) {
    if (s.type === "questions") {
      for (const q of s.questions || []) {
        questions += 1;
        if (!String(q.text || "").trim()) empty += 1;
      }
    } else if (s.type === "object_battery") {
      sets += 1;
      if (!setSizeOk((s.objects || []).length)) badSets += 1;
    }
  }
  return { questions, sets, empty, badSets };
}

export function questionnaireStage(p: ResearchProject): LaneStage {
  const { questions, sets, empty, badSets } = questionnaireIssues(p);
  if (!questions && !sets) return { tone: "idle", line: "Zatím prázdný" };
  const count = [questions ? `${questions} ${plural(questions, "otázka", "otázky", "otázek")}` : "", sets ? `${sets} ${plural(sets, "sada", "sady", "sad")}` : ""].filter(Boolean).join(" · ");
  if (empty) return { tone: "you", line: `${count} · ${empty} bez znění` };
  if (badSets) return { tone: "you", line: `${count} · ${badSets} ${plural(badSets, "sada", "sady", "sad")} mimo 4–15` };
  return { tone: "done", line: count };
}

export function audienceStage(p: ResearchProject): LaneStage {
  return audienceReady(p) ? { tone: "done", line: "Vybráno" } : { tone: "idle", line: "Nevybráno" };
}

export function personaStage(p: ResearchProject): LaneStage {
  const { approved } = withApproval(p);
  const n = Number(p.n) || 0;
  const d = `${approved.length} ${plural(approved.length, "dimenze", "dimenze", "dimenzí")}`;
  return n ? { tone: "done", line: `${d} · N=${n}` } : { tone: "idle", line: d };
}

/** Each design stage's state; the run stages are the caller's (they come from the runs). */
export function designLane(state: Pick<ResearchState, "project" | "analysis">): Record<"brief" | "plan" | "questionnaire" | "audience" | "persona", LaneStage> {
  const p = state.project;
  return {
    brief: briefStage(p),
    plan: planStage(state),
    questionnaire: questionnaireStage(p),
    audience: audienceStage(p),
    persona: personaStage(p),
  };
}

/**
 * What still stands between the design and a run, in stage order. Only the
 * conditions the stages themselves enforce; the server's readiness on Kontrola
 * stays the authority and may find more.
 */
export function blockers(state: Pick<ResearchState, "project" | "analysis">): Blocker[] {
  const p = state.project;
  const out: Blocker[] = [];
  if (!canAnalyse(p)) out.push({ step: "brief", label: "Zadání", detail: "Chybí cíl vlastními slovy" });
  const a = proposalAnalysis(state);
  for (const s of trackedSets(a)) {
    const n = (s.objects || []).length;
    if (!setSizeOk(n)) out.push({ step: "plan", label: `Návrh · sada „${s.title || "bez názvu"}“`, detail: `${n} položek, potřebuje 4–15` });
  }
  const q = questionnaireIssues(p);
  if (!questionnaireHasQuestions(p)) out.push({ step: "questionnaire", label: "Dotazník", detail: "Zatím nemá žádnou běžnou otázku" });
  if (q.empty) out.push({ step: "questionnaire", label: "Dotazník", detail: `${q.empty} ${plural(q.empty, "otázka nemá", "otázky nemají", "otázek nemá")} znění` });
  if (q.badSets) out.push({ step: "questionnaire", label: "Dotazník", detail: `${q.badSets} ${plural(q.badSets, "sledovaná sada je", "sledované sady jsou", "sledovaných sad je")} mimo 4–15 položek` });
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
