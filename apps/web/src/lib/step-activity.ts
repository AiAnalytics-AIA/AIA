// What a running step is doing, from its run's event feed (.planning/plans/step-activity.md).
// The worker writes every event (StepContext.progress, the engine's own transitions); this
// module only folds them into words, per step. A line says only what an event says: its
// message, or a known code with its counts. Never a percentage, never an estimate, never a
// payload dump -- an unknown payload field is left out, not shown raw.

import { t, tv } from "@/i18n/t";
import type { RunEvent } from "./api";
import { isWaiting } from "./research-execution";

/** Feed lines kept per step: the latest few, newest last. */
export const KEEP_LINES = 6;

export type ActivityLine = { id: number; at: string | null; text: string; level: "info" | "warn" };

export type StepActivity = {
  stepId: string;
  /** The latest lines, newest last, at most KEEP_LINES. */
  lines: ActivityLine[];
  /** A count the step reported, as it reported it ("respondent 40 of 300"); null until it does. */
  progress: { done: number; of: number } | null;
  /** Fieldwork blocks answered from the checkpoint, not paid again (RQC7a `replayed`); 0 until reported. */
  replayed: number;
  /**
   * A panel run's quota cells (RQC7b `fieldwork_sample`), each with the respondents answered in it
   * as `fieldwork_respondent` reported them; null until the cells are reported.
   */
  quota: { cells: QuotaFill[] } | null;
  /**
   * Model requests the step reported answered (AIA_AI_STEP_EVENTS), summed from their events.
   * `tokens` is null once any answer came without its counts: unknown, never counted as none.
   */
  model: { answered: number; tokens: number | null; costUsd: number };
  /** Web tool calls that completed, from Deep Research's tool events. */
  toolCalls: number;
};

export type QuotaFill = { key: string; values: string[]; n: number; answered: number };

export type ActivityState = { cursor: number; steps: Readonly<Record<string, StepActivity>> };
export const EMPTY_ACTIVITY: ActivityState = { cursor: 0, steps: {} };

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" && v ? v : null);
/** "{node}: {reason}" -> the reason; the engine prefixes its own messages with the node key. */
const reason = (message: string) => message.replace(/^[a-z0-9_/]+:\s*/, "");

/** As the job panel prints a cost (research/jobs.ts jobMeta): three decimals. */
const usd = (v: number) => `$${v.toFixed(3)}`;
export const formatUsd = usd;

const TOOL_PREFIX = "deep_research_tool_";

/** A fieldwork count with the blocks answered from the checkpoint, said only when there are any. */
const withReplayed = (text: string, replayed: number) =>
  replayed ? `${text} · ${tv("research.exec.activity.fieldworkReplayed", { replayed })}` : text;

/** A Deep Research code with its counts filled; the placeholders a payload lacks stay out. */
function deepResearchLine(code: string, payload: Record<string, unknown>): string | null {
  const key = `research.exec.activity.dr.${code}`;
  const template = t(key);
  if (template === key) return null;
  const vars: Record<string, string | number> = {};
  for (const [k, v] of Object.entries(payload)) {
    const value = num(v) ?? (typeof v === "boolean" ? null : str(v));
    if (value !== null) vars[k] = value;
  }
  // A template naming a field the event did not carry would print "{field}": leave it out.
  return /\{\w+\}/.test(tv(key, vars)) ? null : tv(key, vars);
}

function toolLine(outcome: string, payload: Record<string, unknown>): string | null {
  const kind = str(payload.tool);
  const noun = kind ? t(`research.exec.activity.tool.${kind}`) : null;
  const key = `research.exec.activity.toolOutcome.${outcome.toUpperCase()}`;
  if (!noun || noun.startsWith("research.") || t(key) === key) return null;
  return tv(key, { tool: noun });
}

/** One event in words, or null when it says nothing a person needs about the step. */
export function describe(event: RunEvent): ActivityLine | null {
  const line = (text: string, level: ActivityLine["level"] = "info"): ActivityLine => ({
    id: event.event_id,
    at: event.created_at,
    text,
    level,
  });
  const p = event.payload ?? {};
  switch (event.event_type) {
    case "ATTEMPT_CLAIMED":
      return line(t("research.exec.activity.claimed"));
    case "STEP_SUCCEEDED":
      return line(t("research.exec.activity.succeeded"));
    case "STEP_DEFERRED":
      return line(tv("research.exec.activity.deferred", { reason: reason(event.message) }), "warn");
    case "STEP_RECOVERY":
      return line(tv("research.exec.activity.recovery", { reason: reason(event.message) }), "warn");
    case "ATTEMPT_ABANDONED":
      return line(tv("research.exec.activity.abandoned", { reason: reason(event.message) }), "warn");
    case "STEP_PROGRESS":
      break;
    default:
      return null;
  }
  const code = event.message;
  if (code === "ai_request_sent") return line(t("research.exec.activity.aiSent"));
  if (code === "ai_request_answered") {
    const tokensIn = num(p.input_tokens);
    const tokensOut = num(p.output_tokens);
    const cost = num(p.cost_usd);
    const ms = num(p.latency_ms);
    if (cost === null || ms === null) return null;
    const vars = { cost: usd(cost), seconds: (ms / 1000).toFixed(1) };
    return tokensIn === null || tokensOut === null
      ? line(tv("research.exec.activity.aiAnsweredNoTokens", vars))
      : line(tv("research.exec.activity.aiAnswered", { ...vars, tokensIn, tokensOut }));
  }
  // The fieldwork event contract (run-qc-and-checkpoint RQC7a): counts as reported.
  if (code === "fieldwork_progress") {
    const done = num(p.respondents);
    const of = num(p.of);
    if (done === null || of === null) return null;
    return line(withReplayed(tv("research.exec.activity.fieldworkProgress", { done, of }), num(p.replayed) ?? 0));
  }
  if (code === "fieldwork_sample") {
    const cells = quotaCells(p.cells);
    return cells ? line(tv("research.exec.activity.fieldworkSample", { cells: cells.length })) : null;
  }
  // Folded into the cells' fill (foldActivity), one per respondent: never a log line each.
  if (code === "fieldwork_respondent") return null;
  if (code.startsWith(TOOL_PREFIX)) {
    const text = toolLine(code.slice(TOOL_PREFIX.length), p);
    return text ? line(text, code.endsWith("failed") || code.endsWith("uncertain") ? "warn" : "info") : null;
  }
  if (code.startsWith("deep_research_")) {
    const text = deepResearchLine(code, p);
    return text ? line(text) : null;
  }
  // A step's own words (research, fieldwork, analysis, agents): already a sentence.
  const done = num(p.respondents);
  const of = num(p.of);
  if (done !== null && of !== null) return line(`${code} · ${tv("research.exec.activity.respondents", { done, of })}`);
  const mod = str(p.module);
  const turn = num(p.turn);
  if (mod && turn !== null) return line(`${code} · ${tv("research.exec.activity.module", { module: mod, turn })}`);
  return line(code);
}

function blank(stepId: string): StepActivity {
  return { stepId, lines: [], progress: null, replayed: 0, quota: null, model: { answered: 0, tokens: 0, costUsd: 0 }, toolCalls: 0 };
}

/** A `fieldwork_sample`'s cells, each readable or the whole list refused (never a partial table); none is no table. */
function quotaCells(raw: unknown): QuotaFill[] | null {
  if (!Array.isArray(raw) || !raw.length) return null;
  const cells: QuotaFill[] = [];
  for (const c of raw) {
    const r = (c ?? {}) as Record<string, unknown>;
    const key = str(r.key);
    const n = num(r.n);
    const values = Array.isArray(r.values) && r.values.every((v) => typeof v === "string") ? (r.values as string[]) : null;
    if (!key || n === null || !values) return null;
    cells.push({ key, values, n, answered: 0 });
  }
  return cells;
}

/** Fold events read after the state's cursor; the same events twice change nothing. */
export function foldActivity(state: ActivityState, events: readonly RunEvent[], keep = KEEP_LINES): ActivityState {
  let cursor = state.cursor;
  const steps: Record<string, StepActivity> = { ...state.steps };
  // The steps whose quota this fold copied already, so it may count into it.
  const owned = new Set<string>();
  for (const event of [...events].sort((a, b) => a.event_id - b.event_id)) {
    if (event.event_id <= cursor) continue;
    cursor = event.event_id;
    if (!event.step_id) continue;
    const prev = steps[event.step_id] ?? blank(event.step_id);
    const next: StepActivity = { ...prev, model: { ...prev.model } };
    const p = event.payload ?? {};
    if (event.event_type === "STEP_PROGRESS") {
      const done = num(p.respondents);
      const of = num(p.of);
      if (done !== null && of !== null) next.progress = { done, of };
      // Each event carries its attempt's own total: one without it says nothing was replayed.
      if (event.message === "fieldwork_progress") next.replayed = num(p.replayed) ?? 0;
      // A new attempt reports its cells again and counts its respondents from the first.
      if (event.message === "fieldwork_sample") {
        const cells = quotaCells(p.cells);
        next.quota = cells ? { cells } : null;
        if (cells) owned.add(event.step_id);
      }
      if (event.message === "fieldwork_respondent" && next.quota) {
        // Copied once per fold, then counted in place: a long feed never copies every cell per row.
        if (!owned.has(event.step_id)) {
          next.quota = { cells: next.quota.cells.map((c) => ({ ...c })) };
          owned.add(event.step_id);
        }
        const cell = next.quota.cells.find((c) => c.key === str(p.cell));
        if (cell) cell.answered += 1;
      }
      if (event.message === "ai_request_answered") {
        next.model.answered += 1;
        const tokensIn = num(p.input_tokens);
        const tokensOut = num(p.output_tokens);
        next.model.tokens = next.model.tokens === null || tokensIn === null || tokensOut === null ? null : next.model.tokens + tokensIn + tokensOut;
        next.model.costUsd += num(p.cost_usd) ?? 0;
      }
      if (event.message === `${TOOL_PREFIX}succeeded`) next.toolCalls += 1;
    }
    const line = describe(event);
    if (line) next.lines = [...prev.lines, line].slice(-keep);
    steps[event.step_id] = next;
  }
  return { cursor, steps };
}

/**
 * How far a step that stopped short got, as it last reported it (artifact-fieldwork FLD3): a
 * waiting, parked, failed or cancelled step keeps its count on Průběh once its activity panel
 * closes, and so does a step still marked running in a run that has ended. Null for a step that
 * runs (its panel says it), is queued for another attempt, succeeded or was skipped, and when it
 * reported nothing.
 */
export function lastReported(activity: StepActivity | null, status: string, runEnded: boolean): string | null {
  const stopped = isWaiting(status) || status === "FAILED" || status === "CANCELLED" || (status === "RUNNING" && runEnded);
  if (!activity?.progress || !stopped) return null;
  return withReplayed(tv("research.exec.activity.lastReported", activity.progress), activity.replayed);
}

/** The activity of the steps given, by step id; a step that reported nothing has none. */
export function activityOf(state: ActivityState, stepId: string | null | undefined): StepActivity | null {
  return stepId ? (state.steps[stepId] ?? null) : null;
}
