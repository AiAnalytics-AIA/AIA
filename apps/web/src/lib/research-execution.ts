// What a research run's state and results mean to a person (ADR 0016). The API
// computes everything; this module only decides how it reads -- which words,
// which tone, what is hidden -- so the three stages (Run, Progress, Results)
// agree, and so the rules are tested without React.
//
// Two rules are carried here because the screens must not forget them:
// * a cell below the unit's donor threshold (SUPPRESS) shows no number at all;
// * anything computed from the fictional dataset says so, every time.

import { t, tv } from "@/i18n/t";
import type { ResearchPhase, ResearchRun, ResearchRunSummary, ResearchStep } from "@/lib/api";
import type { Tone } from "@/lib/tone";

export const RUNTIME_UNAVAILABLE = "ai_runtime_unavailable";
export const SYNTHETIC_SOURCE = "synthetic_fixture";
export const STEP_ORDER = ["compile", "preflight", "run", "aggregate", "sociomap", "sociomapping", "sociomapping_report"] as const;
export const ANALYSIS_ORDER = ["executive", "research_questions", "objects", "audience", "segments", "hypotheses", "implications", "limitations"] as const;

export function phaseTone(phase: ResearchPhase): Tone {
  switch (phase) {
    case "RUNNING":
    case "QUEUED":
      return "running";
    case "WAITING":
      return "you";
    case "FAILED":
      return "fault";
    case "COMPLETED":
      return "done";
    default:
      return "neutral";
  }
}

export const phaseLabel = (phase: ResearchPhase): string => t(`research.exec.phase.${phase}`);

export function stepLabel(nodeKey: string): string {
  const label = t(`research.exec.steps.${nodeKey}`);
  return label.startsWith("research.") ? nodeKey : label;
}

export function stepTone(step: ResearchStep): Tone {
  if (step.status === "SUCCEEDED") return "done";
  if (step.status === "RUNNING" || step.status === "RUNNABLE") return "running";
  if (step.status === "FAILED") return "fault";
  if (step.status.startsWith("WAITING") || step.status.startsWith("AWAITING")) return "you";
  return "neutral";
}

export function stepStatusLabel(step: ResearchStep): string {
  const label = t(`research.exec.stepStatus.${step.status}`);
  return label.startsWith("research.") ? step.status : label;
}

/** Keep reading while something can still change on its own; a parked run cannot. */
export function shouldPoll(run: ResearchRun): boolean {
  return !run.is_terminal && (run.phase === "QUEUED" || run.phase === "RUNNING");
}

/** The step the run is waiting at because the AI runtime is not deployed, if any. */
export function parkedForRuntime(run: ResearchRun): ResearchStep | null {
  return run.steps.find((s) => s.waiting_reason === RUNTIME_UNAVAILABLE) ?? null;
}

const WAITING_STATUS = /^(WAITING|AWAITING)_|^RECOVERY_REQUIRED$/;

/**
 * Why a step waits, in words, or null when the step is not waiting. What the step recorded
 * (the gate that refused it, as the executor wrote it) comes first; a wait that records none
 * -- budget, provider quota, a decision owed -- is told from its machine reason. It says only
 * what is known: that the step waits, and why. It promises no action the page cannot take.
 */
export function waitingDetail(step: ResearchStep): string | null {
  if (!WAITING_STATUS.test(step.status)) return null;
  if (step.error_message) return step.error_message;
  const reason = step.waiting_reason ?? "";
  if (reason === "budget_exceeded" || reason === "provider_quota_exhausted" || reason === "approval_required") {
    return t(`research.exec.wait.${reason}`);
  }
  if (reason.startsWith("gate:")) return t("research.exec.wait.approval_required");
  return null;
}

/** Origins that are never evidence: the fictional fixture, and AI respondents on fictional personas. */
export const SYNTHETIC_ORIGINS: ReadonlySet<string> = new Set(["SYNTHETIC_FIXTURE", "SYNTHETIC_AI_FICTIONAL"]);

/**
 * A run is synthetic when its source is the fictional fixture, or when any step says its data is
 * synthetic -- an `ai_runtime` run on the fictional roster is labelled like the fixture, every time.
 * A summary carries no steps; it is labelled once the run is read in full.
 */
export const isSynthetic = (run: ResearchRun | ResearchRunSummary): boolean =>
  run.fieldwork_source === SYNTHETIC_SOURCE ||
  ("steps" in run && run.steps.some((s) => s.data_origin !== null && SYNTHETIC_ORIGINS.has(s.data_origin)));

export function stepOf(run: ResearchRun, nodeKey: string): ResearchStep | null {
  return run.steps.find((s) => s.node_key === nodeKey) ?? null;
}

// ---- aggregate tables ------------------------------------------------------

export type SupportStatus = "REPORTABLE" | "INDICATIVE" | "SUPPRESS";
export type ResultRow = { label: string; value: string | null; interval: string | null };
export type ResultTable = {
  id: string;
  typ: string;
  support: SupportStatus;
  /** SUPPRESS: no number is shown, whatever was computed. */
  suppressed: boolean;
  respondents: number;
  donors: number;
  effectiveN: number;
  rows: ResultRow[];
  verbatims: string[];
};

type Interval = { low: number; high: number } | null | undefined;
type QuestionResult = Record<string, unknown> & {
  typ: string;
  support_status: SupportStatus;
  n_platnych: number;
  n_unique_layer_donors: number;
  effective_n: number;
};

const num = (x: number, decimals: number) => x.toLocaleString("cs-CZ", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
const range = (i: Interval, decimals: number) => (i ? `${num(i.low, decimals)}–${num(i.high, decimals)}` : null);

/** One question's aggregate as rows. A suppressed cell has rows but no values. */
export function resultTable(id: string, result: QuestionResult): ResultTable {
  const suppressed = result.support_status === "SUPPRESS";
  const hide = (value: string | null) => (suppressed ? null : value);
  const rows: ResultRow[] = [];
  if (result.typ === "vyber" || result.typ === "multi") {
    const pct = (result.celkem_pct ?? {}) as Record<string, number>;
    const intervals = (result.intervaly_95 ?? {}) as Record<string, Interval>;
    for (const [label, value] of Object.entries(pct)) {
      rows.push({ label, value: hide(`${num(value, 1)} %`), interval: hide(range(intervals[label], 1)) });
    }
  } else if (result.typ === "skala") {
    const mean = result.prumer as number | null;
    rows.push({
      label: t("research.exec.results.mean"),
      value: hide(mean === null || mean === undefined ? null : num(mean, 2)),
      interval: hide(range(result.prumer_interval_95 as Interval, 2)),
    });
    const top = result.top2box_pct as number | null;
    rows.push({
      label: t("research.exec.results.top2"),
      value: hide(top === null || top === undefined ? null : `${num(top, 1)} %`),
      interval: hide(range(result.top2box_interval_95 as Interval, 1)),
    });
  }
  return {
    id,
    typ: result.typ,
    support: result.support_status,
    suppressed,
    respondents: result.n_platnych,
    donors: result.n_unique_layer_donors,
    effectiveN: result.effective_n,
    rows,
    verbatims: suppressed ? [] : ((result.verbatimy as string[] | undefined) ?? []).slice(0, 5),
  };
}

export function supportNote(table: ResultTable): string {
  return tv(`research.exec.support.${table.support}`, { donors: table.donors, n: table.respondents });
}

// ---- the internal Sociomap ---------------------------------------------------

export type SociomapObject = { id: string; label: string; score: number | null; x: number; y: number };

type SociomapBattery = {
  battery_id: string;
  title: string;
  objects: { id: string; label: string }[];
  methodology_status: string;
  relation: { scores: (number | null)[] };
  sociomap: { object_ids: string[]; layout: { object_xy: [number, number][] } };
};

/** The objects of one battery's map, with the unit's score and AIA's layout position. */
export function sociomapObjects(battery: SociomapBattery): SociomapObject[] {
  const xy = new Map(battery.sociomap.object_ids.map((id, i) => [id, battery.sociomap.layout.object_xy[i]]));
  return battery.objects.map((o, i) => {
    const [x, y] = xy.get(o.id) ?? [0, 0];
    return { id: o.id, label: o.label, score: battery.relation.scores[i] ?? null, x, y };
  });
}
