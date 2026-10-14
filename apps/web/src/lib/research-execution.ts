// What a research run's state and results mean to a person (ADR 0016). The API
// computes everything; this module only decides how it reads -- which words,
// which tone, what is hidden -- so the three stages (Run, Progress, Results)
// agree, and so the rules are tested without React.
//
// Two rules are carried here because the screens must not forget them:
// * a cell below the unit's donor threshold (SUPPRESS) shows no number at all;
// * anything computed from the fictional dataset says so, every time.

import { t, tv } from "@/i18n/t";
import type { OutlookVerdict, QuestionOutlook, ResearchPhase, ResearchQuestionTrace, ResearchRun, ResearchRunSummary, ResearchStep } from "@/lib/api";
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

/** An analysis step whose module was stored BLOCKED: finished as a step, not as a result. */
export const needsRepair = (step: ResearchStep): boolean =>
  step.status === "SUCCEEDED" && step.analysis_outcome === "BLOCKED";

export function stepTone(step: ResearchStep): Tone {
  if (needsRepair(step)) return "fault";
  if (step.status === "SUCCEEDED") return "done";
  if (step.status === "RUNNING" || step.status === "RUNNABLE") return "running";
  if (step.status === "FAILED") return "fault";
  if (step.status.startsWith("WAITING") || step.status.startsWith("AWAITING")) return "you";
  return "neutral";
}

export function stepStatusLabel(step: ResearchStep): string {
  if (needsRepair(step)) return t("research.exec.stepStatus.ANALYSIS_BLOCKED");
  const label = t(`research.exec.stepStatus.${step.status}`);
  return label.startsWith("research.") ? step.status : label;
}

/** Whether a finished run may have analysis modules to ask again: worth asking the API. */
export function mayRetryAnalysis(run: ResearchRun): boolean {
  return (
    run.is_terminal &&
    run.steps.some((s) => s.node_key.startsWith("analysis_") && (needsRepair(s) || s.status === "FAILED" || s.status === "CANCELLED"))
  );
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

/** A step that holds the internal report back, and why, in the words the step recorded. */
export type ReportHold = { step: ResearchStep; detail: string | null };

/**
 * What keeps a run's report from being ready (run-gate-visibility chunk 2): every analysis
 * module's step that has not succeeded, then the report step itself when it waits or failed, in
 * the run's order. Each carries what it recorded: the wait's reason (`waitingDetail`) or a failed
 * step's message. A step that only has not started yet has no detail: unknown, never invented.
 */
export function reportHolds(run: ResearchRun): ReportHold[] {
  const holds: ReportHold[] = [];
  for (const step of run.steps) {
    const analysis = step.kind === "research_analysis";
    if (!analysis && step.kind !== "research_report") continue;
    // A module stored BLOCKED succeeded as a step and still holds the report.
    if (step.status === "SUCCEEDED" && !needsRepair(step)) continue;
    const detail = needsRepair(step)
      ? t("research.exec.analysisRetry.held")
      : (waitingDetail(step) ?? (step.status === "FAILED" ? step.error_message : null));
    if (analysis || detail !== null) holds.push({ step, detail });
  }
  return holds;
}

/** Origins that are never evidence: the fictional fixture, and AI respondents on fictional personas. */
export const SYNTHETIC_ORIGINS: ReadonlySet<string> = new Set(["SYNTHETIC_FIXTURE", "SYNTHETIC_AI_FICTIONAL"]);
/** Origins of modelled evidence: AI respondents built from the run's own population (ADR 0024). */
export const MODELLED_ORIGINS: ReadonlySet<string> = new Set(["MODELLED_AI_PANEL"]);
/** What every modelled number says beside it (ADR 0024 §7); never "respondents said" or "measured". */
export const MODELLED_DISCLOSURE = "modelováno: AI respondenti z populace";

/**
 * How a label reads an origin, the same three ways as `domain/fieldwork.py` `origin_kind`:
 * fictional (SIMULATED), modelled from the population (MODELLED), or anything else (UNKNOWN).
 * There is no measured kind: an origin this page has no word for is unknown, never fieldwork.
 */
export type OriginKind = "SIMULATED" | "MODELLED" | "UNKNOWN";
const KINDS: ReadonlySet<string> = new Set(["SIMULATED", "MODELLED", "UNKNOWN"]);

export function originKind(origin: string | null | undefined): OriginKind {
  if (!origin) return "UNKNOWN";
  if (SYNTHETIC_ORIGINS.has(origin)) return "SIMULATED";
  if (MODELLED_ORIGINS.has(origin)) return "MODELLED";
  return "UNKNOWN";
}

/** The kind the API states, when it is one of the three; otherwise read from the origin. */
const statedKind = (stated: string | null | undefined, origin: string | null | undefined): OriginKind =>
  stated && KINDS.has(stated) ? (stated as OriginKind) : originKind(origin);

/** A step's kind; `null` when it stamped no origin (it made no respondent data). */
export const stepOriginKind = (step: ResearchStep): OriginKind | null =>
  step.data_origin === null ? null : statedKind(step.data_origin_kind, step.data_origin);

/**
 * Every kind a run's data is: the fictional fixture source is SIMULATED; each step that stamped an
 * origin adds its kind. Empty: nothing is known yet (a summary carries no steps).
 */
export function runOriginKinds(run: ResearchRun | ResearchRunSummary): ReadonlySet<OriginKind> {
  const kinds = new Set<OriginKind>();
  if (run.fieldwork_source === SYNTHETIC_SOURCE) kinds.add("SIMULATED");
  if ("steps" in run) {
    for (const step of run.steps) {
      const kind = stepOriginKind(step);
      if (kind) kinds.add(kind);
    }
  }
  return kinds;
}

/**
 * A run is synthetic when its source is the fictional fixture, or when any step says its data is
 * synthetic -- an `ai_runtime` run on the fictional roster is labelled like the fixture, every time.
 * A summary carries no steps; it is labelled once the run is read in full.
 */
export const isSynthetic = (run: ResearchRun | ResearchRunSummary): boolean => runOriginKinds(run).has("SIMULATED");
/** Some step's data is modelled from the population: said every time, never as fieldwork. */
export const isModelled = (run: ResearchRun | ResearchRunSummary): boolean => runOriginKinds(run).has("MODELLED");
/** Some step stamped an origin this page has no word for: said as unknown, never as real. */
export const hasUnknownOrigin = (run: ResearchRun | ResearchRunSummary): boolean => runOriginKinds(run).has("UNKNOWN");

/**
 * The kind of an analysis or a report the API returned: its stated `data_origin_kind`; `null` when
 * the API states none because nothing with an origin exists yet (an analysis whose modules have not
 * stored an outcome). An API from before the field: SIMULATED when it said `synthetic`, else
 * UNKNOWN -- never read as real.
 */
export function resultOriginKind(result: { synthetic?: boolean; data_origin_kind?: string | null }): OriginKind | null {
  const stated = result.data_origin_kind;
  if (stated && KINDS.has(stated)) return stated as OriginKind;
  if (stated === null && !result.synthetic) return null;
  return result.synthetic ? "SIMULATED" : "UNKNOWN";
}

/**
 * What a run says about its population: the version it recorded, and whether its respondents
 * were drawn from it (the run's pinned persona source, `read_by_fieldwork`). Null: it recorded
 * none.
 */
export function populationNote(run: Pick<ResearchRun, "population">): string | null {
  const p = run.population;
  if (!p) return null;
  const vars = { label: p.version_label, population: p.population_id ?? p.version_id };
  return tv(p.read_by_fieldwork ? "research.exec.populationRead" : "research.exec.populationRecorded", vars);
}

export function stepOf(run: ResearchRun, nodeKey: string): ResearchStep | null {
  return run.steps.find((s) => s.node_key === nodeKey) ?? null;
}

// ---- aggregate tables ------------------------------------------------------

export type SupportStatus = "REPORTABLE" | "INDICATIVE" | "SUPPRESS";
/**
 * One result row. `bar` is the share and its 95 % interval as percentages, for the
 * row's bar (Studio v3): only a share has a known scale (0–100), and a suppressed
 * row has none, as it has no number.
 */
export type ResultRow = { label: string; value: string | null; interval: string | null; bar?: { value: number; low: number | null; high: number | null } };
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

/**
 * How an aggregate departs from 18.6.6's port (plan methodology-tab G2c): every value the
 * methodology in use changed, with the unit's and the one used, and every replaced formula.
 * Null: the aggregate is the unit's port. A deviation the page cannot read is still a
 * deviation -- it says so with nothing named, never passes as the port.
 */
export type AggregateDeviation = {
  version: string | null;
  changed: { path: string; unit: unknown; used: unknown }[];
  formulas: string[];
};

export function aggregateDeviation(aggregate: Record<string, unknown> | null | undefined): AggregateDeviation | null {
  if (!aggregate || !("deviation" in aggregate)) return null;
  const raw = aggregate.deviation;
  if (typeof raw !== "object" || raw === null) return { version: null, changed: [], formulas: [] };
  const d = raw as Record<string, unknown>;
  const changed = Array.isArray(d.changed)
    ? d.changed.filter((c): c is { path: string; unit: unknown; used: unknown } => typeof c === "object" && c !== null && typeof (c as { path?: unknown }).path === "string")
    : [];
  const formulas = Array.isArray(d.replaced_formulas) ? d.replaced_formulas.filter((f): f is string => typeof f === "string") : [];
  return { version: typeof d.methodology_version === "string" ? d.methodology_version : null, changed, formulas };
}

/** How many top points the aggregate's top box holds: the unit's two, unless a version changed it. */
export function topBoxWidth(deviation: AggregateDeviation | null): number {
  const used = deviation?.changed.find((c) => c.path === "top_box")?.used;
  return typeof used === "number" && Number.isInteger(used) && used >= 1 ? used : 2;
}

/** One question's aggregate as rows. A suppressed cell has rows but no values. `topBox` is how
 *  many top points its top box holds (2 unless the aggregate's methodology changed it). */
export function resultTable(id: string, result: QuestionResult, topBox = 2): ResultTable {
  const suppressed = result.support_status === "SUPPRESS";
  const hide = (value: string | null) => (suppressed ? null : value);
  const rows: ResultRow[] = [];
  if (result.typ === "vyber" || result.typ === "multi") {
    const pct = (result.celkem_pct ?? {}) as Record<string, number>;
    const intervals = (result.intervaly_95 ?? {}) as Record<string, Interval>;
    for (const [label, value] of Object.entries(pct)) {
      const iv = intervals[label];
      rows.push({
        label,
        value: hide(`${num(value, 1)} %`),
        interval: hide(range(iv, 1)),
        ...(suppressed || typeof value !== "number" ? {} : { bar: { value, low: iv?.low ?? null, high: iv?.high ?? null } }),
      });
    }
  } else if (result.typ === "skala") {
    const mean = result.prumer as number | null;
    rows.push({
      label: t("research.exec.results.mean"),
      value: hide(mean === null || mean === undefined ? null : num(mean, 2)),
      interval: hide(range(result.prumer_interval_95 as Interval, 2)),
    });
    const top = result.top2box_pct as number | null;
    const topIv = result.top2box_interval_95 as Interval;
    rows.push({
      label: topBox === 2 ? t("research.exec.results.top2") : tv("research.exec.results.topN", { n: topBox }),
      value: hide(top === null || top === undefined ? null : `${num(top, 1)} %`),
      interval: hide(range(topIv, 1)),
      ...(suppressed || typeof top !== "number" ? {} : { bar: { value: top, low: topIv?.low ?? null, high: topIv?.high ?? null } }),
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

// --------------------------------------------------------------------------- //
// Before a run: which questions it will answer (plan run-recovery-and-truth 2b)
// --------------------------------------------------------------------------- //

/** Worst first: what a run will not answer is read before what it will. */
export const VERDICT_ORDER: readonly OutlookVerdict[] = ["UNANSWERABLE", "AT_RISK", "UNKNOWN", "ANSWERABLE"];

export function verdictTone(verdict: OutlookVerdict): Tone {
  if (verdict === "UNANSWERABLE") return "fault";
  if (verdict === "AT_RISK") return "you";
  if (verdict === "UNKNOWN") return "neutral";
  return "done";
}

/** How many items carry each verdict; every verdict present, zero when none. */
export function outlookCounts(items: readonly QuestionOutlook[]): Record<OutlookVerdict, number> {
  const counts: Record<OutlookVerdict, number> = { UNANSWERABLE: 0, AT_RISK: 0, UNKNOWN: 0, ANSWERABLE: 0 };
  for (const item of items) counts[item.verdict] += 1;
  return counts;
}

/** The items worst first, questionnaire order kept within a verdict. */
export function outlookByVerdict(items: readonly QuestionOutlook[]): QuestionOutlook[] {
  const rank = (v: OutlookVerdict) => VERDICT_ORDER.indexOf(v);
  return items.map((item, i) => [item, i] as const).sort((a, b) => rank(a[0].verdict) - rank(b[0].verdict) || a[1] - b[1]).map(([item]) => item);
}

/** A reason in words; a code this client does not know is named, never hidden. */
export function outlookReason(code: string): string {
  const key = `research.exec.outlook.reason.${code}`;
  const words = t(key);
  return words === key ? tv("research.exec.outlook.reason.other", { code }) : words;
}

/** Where an item's reason is fixed: support (n) on Dimenze, everything else in the questionnaire. */
export function outlookFixStep(reasons: readonly string[]): "persona" | "questionnaire" | null {
  if (reasons.some((r) => r !== "support_unknown" && !r.startsWith("support_"))) return "questionnaire";
  if (reasons.some((r) => r === "support_suppressed" || r === "support_analysis_excluded" || r === "support_indicative")) return "persona";
  return null;
}

/** One measure of a research question as it reads: a question by its wording, a tracked set once. */
export type TraceMeasure = { key: string; text: string; verdict: OutlookVerdict };

/**
 * A research question's measures in words (run-recovery-and-truth 3b): each question by its
 * wording with its verdict; a tracked set once, by its first object's wording and how many
 * objects it rates, with its best verdict. An id the outlook does not list reads unknown.
 */
export function traceMeasures(question: ResearchQuestionTrace, outlook: readonly QuestionOutlook[]): TraceMeasure[] {
  const byId = new Map(outlook.map((o) => [o.question_id, o]));
  const best = (a: OutlookVerdict, b: OutlookVerdict) => (VERDICT_ORDER.indexOf(a) >= VERDICT_ORDER.indexOf(b) ? a : b);
  const out: TraceMeasure[] = [];
  const sets = new Map<string, { measure: TraceMeasure; count: number }>();
  for (const id of question.measures) {
    const item = byId.get(id);
    if (!item) {
      out.push({ key: id, text: id, verdict: "UNKNOWN" });
      continue;
    }
    if (item.battery_id === null) {
      out.push({ key: id, text: item.text, verdict: item.verdict });
      continue;
    }
    const seen = sets.get(item.battery_id);
    if (seen) {
      seen.count += 1;
      seen.measure.verdict = best(seen.measure.verdict, item.verdict);
      continue;
    }
    const measure: TraceMeasure = { key: item.battery_id, text: item.text, verdict: item.verdict };
    sets.set(item.battery_id, { measure, count: 1 });
    out.push(measure);
  }
  for (const { measure, count } of sets.values()) {
    if (count > 1) measure.text = tv("research.exec.trace.set", { first: measure.text, count });
  }
  return out;
}
