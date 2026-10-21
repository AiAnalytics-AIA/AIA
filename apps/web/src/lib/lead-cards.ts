// The AI work of a study as cards in the Research Lead's conversation (plan research-lead-workbench
// chunk 23, D15): every design job (the eight ResearchAgentActions) and every research run, however
// it was started, read as a card that says what it is, how it stands, what it cost and, once it is
// done, where its result is. Pure: the words come from the existing readers (agentJobState,
// runState, stepLabel), the orb from lib/activity-orb.ts; nothing here calls the API.

import type { ResearchAgentAction, ResearchAgentJob, ResearchRun, ResearchStep, Readiness } from "./api";
import { agentJobOrb, researchStepOrb, type Orb } from "./activity-orb";
import { needsAcknowledgement } from "./answerability";
import { ACTION_LABELS, agentJobState, jobCostUsd } from "./research-agent-jobs";
import { stepLabel, stepOf } from "./research-execution";
import { runState, type RunReading } from "./run-state";
import type { Tone as StateTone } from "./tone";
import type { WorkbenchStage } from "./workbench-stages";

/** The status glyph's tones a card uses (workbench Glyph.tsx). */
export type CardTone = "done" | "running" | "you" | "world" | "fault" | "cancelled" | "inert";

/** The advice jobs: their answer is read, never applied to the design. */
export const ADVICE_ACTIONS: ReadonlySet<ResearchAgentAction> = new Set(["critique_design", "design_copilot", "answer_memory"]);

/**
 * The stage a design job's proposal changes, where its review is opened: the stage it is submitted
 * from (useResearchAgents sourceOf) and whose content it proposes. Advice changes no stage: null.
 */
export const JOB_STAGE: Readonly<Record<ResearchAgentAction, WorkbenchStage | null>> = {
  analyze_brief: "design",
  build_questionnaire: "questionnaire",
  optimize_questionnaire: "questionnaire",
  propose_audience: "audience",
  suggest_dimensions: "dimensions",
  critique_design: null,
  design_copilot: null,
  answer_memory: null,
};

/** A job's state in the card's words: queued and running told apart, a budget wait never a failure. */
const JOB_WORDS: Record<"queued" | ReturnType<typeof agentJobState>, { word: string; tone: CardTone }> = {
  queued: { word: "ve frontě", tone: "running" },
  running: { word: "běží", tone: "running" },
  awaiting_budget: { word: "čeká na rozpočet studie", tone: "world" },
  waiting: { word: "čeká", tone: "world" },
  completed: { word: "hotovo", tone: "done" },
  failed: { word: "selhalo", tone: "fault" },
  cancelled: { word: "zrušeno", tone: "cancelled" },
};

/** Where a finished job's proposal stands (ADR 0026 decision 8), in words; null: nothing to say. */
const PROPOSAL_WORDS: Record<NonNullable<ResearchAgentJob["proposal_state"]>, string> = {
  pending: "návrh čeká na vaše rozhodnutí",
  accepted: "návrh přijat",
  dismissed: "návrh zahozen",
  superseded: "návrh nahrazen novějším",
};

/** What a cost reads as: the API's figure, or that none was reported (never a zero). */
export const costWords = (usd: number | null | undefined): string =>
  typeof usd === "number" && Number.isFinite(usd) ? `${jobCostUsd(usd)} USD` : "náklady nevykázány";

export type WorkerCard = {
  id: string;
  title: string;
  state: "queued" | ReturnType<typeof agentJobState>;
  word: string;
  tone: CardTone;
  cost: string;
  /** The orb while the API reports the job's step RUNNING; null otherwise. */
  orb: Orb | null;
  /** The step whose events the live feed shows. */
  stepId: string | null;
  startedAt: string | null;
  advice: boolean;
  /** The stage its proposal changes (null for advice). */
  stage: WorkbenchStage | null;
  proposal: string | null;
  /** A finished job whose answer or proposal can be opened: advice always, a proposal while pending. */
  reviewable: boolean;
  /** What stopped it, as the step recorded it. */
  problem: string | null;
};

export function workerCard(job: ResearchAgentJob): WorkerCard {
  const base = agentJobState(job);
  const state = base === "running" && job.status === "QUEUED" ? "queued" : base;
  const w = JOB_WORDS[state];
  const advice = ADVICE_ACTIONS.has(job.action);
  const done = state === "completed";
  const step = job.steps.find((s) => s.status === "RUNNING") ?? job.steps[0] ?? null;
  return {
    id: job.run_id,
    title: ACTION_LABELS[job.action] ?? job.action,
    state,
    word: w.word,
    tone: w.tone,
    cost: costWords(job.actual_cost_usd),
    orb: agentJobOrb(job),
    stepId: step?.step_id ?? null,
    startedAt: step?.started_at ?? job.created_at,
    advice,
    stage: JOB_STAGE[job.action] ?? null,
    proposal: !advice && done && job.proposal_state ? PROPOSAL_WORDS[job.proposal_state] : null,
    // A proposal no longer pending (accepted, dismissed, superseded) is not offered again; one from
    // an API that does not say is offered, as the saved list offered it.
    reviewable: done && (advice || !job.proposal_state || job.proposal_state === "pending"),
    problem: state === "failed" || state === "waiting" ? job.steps.find((s) => s.error_message)?.error_message ?? null : null,
  };
}

const RUN_TONE: Record<StateTone, CardTone> = { running: "running", you: "you", world: "world", fault: "fault", done: "done", neutral: "inert" };

export type RunCard = {
  id: string;
  title: string;
  reading: RunReading;
  tone: CardTone;
  cost: string;
  revision: number;
  /** The step that runs now, its words, its orb and its id for the live feed; null when none runs. */
  running: { step: ResearchStep; label: string; orb: Orb | null } | null;
  /** Steps finished of all the run lists, as Průběh counts them; null when its steps were not read. */
  steps: { done: number; total: number } | null;
  /** Its data exists: Výsledky has something to show. */
  hasResults: boolean;
};

export function runCard(run: ResearchRun): RunCard {
  const reading = runState(run);
  const steps = run.steps ?? [];
  const step = steps.find((s) => s.status === "RUNNING") ?? null;
  // An orb only where the API reports the step RUNNING (researchStepOrb), the AI ones first.
  const orbed = steps.flatMap((s) => {
    const orb = researchStepOrb(run, s);
    return orb ? [{ step: s, orb }] : [];
  });
  const shown = orbed.find((o) => o.orb.ink === "ai") ?? orbed[0] ?? (step ? { step, orb: null } : null);
  const done = steps.filter((s) => s.status === "SUCCEEDED" || s.status === "SKIPPED").length;
  return {
    id: run.run_id,
    title: "Výzkumný běh",
    reading,
    tone: RUN_TONE[reading.tone] ?? "inert",
    cost: costWords(run.actual_cost_usd),
    revision: run.design_revision,
    running: shown ? { step: shown.step, label: stepLabel(shown.step.node_key), orb: shown.orb } : null,
    steps: steps.length ? { done, total: steps.length } : null,
    hasResults: !!stepOf(run, "aggregate")?.artifact_id,
  };
}

/** What may be placed in the conversation: a Lead turn, a design job, a research run. */
export type Placed<T> =
  | { kind: "turn"; turn: T; at: number }
  | { kind: "job"; job: ResearchAgentJob; at: number }
  | { kind: "run"; run: ResearchRun; at: number };

/**
 * The conversation in the order it happened. A job a turn's card approved is shown with that turn
 * (`request_decision.run_id`), as is a run started from a turn's card (`runOfTurn`); every other job
 * and run, however it was started, stands on its own at the moment it was created.
 */
export function conversationTimeline<T extends { turn_id: string; created_at: string; request_decision?: { run_id: string } | null }>(
  turns: T[], jobs: ResearchAgentJob[], runs: ResearchRun[], runOfTurn: ReadonlyMap<string, string> = new Map(),
): Placed<T>[] {
  const linked = new Set<string>([
    ...turns.flatMap((t) => (t.request_decision?.run_id ? [t.request_decision.run_id] : [])),
    ...runOfTurn.values(),
  ]);
  const at = (iso: string | null | undefined) => Date.parse(iso ?? "") || 0;
  return [
    ...turns.map((turn) => ({ kind: "turn" as const, turn, at: at(turn.created_at) })),
    ...jobs.filter((j) => !linked.has(j.run_id)).map((job) => ({ kind: "job" as const, job, at: at(job.created_at) })),
    ...runs.filter((r) => !linked.has(r.run_id)).map((run) => ({ kind: "run" as const, run, at: at(run.created_at) })),
  ].sort((a, b) => a.at - b.at);
}

/**
 * What a Lead's prepared research run can do from its card, read from the readiness of the design
 * the person sees: start (with the ceiling a confirmation names when the study's limit asks), or
 * be sent to Spuštění, where the run's own checks are met -- a readiness that fails, gaps the person
 * must acknowledge in their own words, or a ceiling that cannot be worked out under a limit. The
 * card never decides any of these for the person.
 */
export type RunRequestPlan =
  | { kind: "start"; ceiling: number | null; confirm: { ceiling: number; limit: number } | null; source: string | null }
  | { kind: "not_ready"; reasons: string[] }
  | { kind: "acknowledge" }
  | { kind: "ceiling_unknown" };

const fin = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

export function runRequestPlan(readiness: Readiness): RunRequestPlan {
  if (!readiness.ready) {
    return { kind: "not_ready", reasons: readiness.checks.filter((c) => c.status === "FAIL").map((c) => c.message) };
  }
  if (needsAcknowledgement(readiness.answerability)) return { kind: "acknowledge" };
  const ceiling = fin(readiness.cost_ceiling_usd);
  const limit = fin(readiness.spend_confirm_usd);
  // A limit with no ceiling is refused by the server as unknown: never let through as zero.
  if (limit !== null && ceiling === null) return { kind: "ceiling_unknown" };
  const confirm = readiness.confirmation_required && ceiling !== null && limit !== null ? { ceiling, limit } : null;
  return { kind: "start", ceiling, confirm, source: readiness.persona_source ?? null };
}

/**
 * Whether the Research Lead owns a layout's AI starts (AI pomoc, the stage cards' "Navrhnout", the
 * job panel's starts), the value of ResearchContext.leadOwnsAiStarts: in the workbench every one goes
 * through the Lead (D15), so none renders; the classic layout, which has no Lead yet (chunk 26),
 * keeps them. Not a worker start, and shown in both: the research run's own Start on Spuštění.
 */
export function leadOwnsAiStarts(layout: "workbench" | "classic"): boolean {
  return layout === "workbench";
}

/** A card's state pill: the workbench's statepill modifier for its tone. */
export function pillClass(tone: CardTone): string {
  if (tone === "running") return "statepill statepill--running";
  if (tone === "fault") return "statepill statepill--fault";
  if (tone === "you" || tone === "world") return "statepill statepill--proposed";
  if (tone === "done") return "statepill statepill--accepted";
  return "statepill";
}

/** The prepared run card's state pill: before the check, then what the check found, then the decision. */
export function runRequestPill(plan: RunRequestPlan | null, state: "open" | "kept" | "started" | "existing"): { word: string; tone: CardTone } {
  if (state === "started") return { word: "Spuštěno", tone: "done" };
  if (state === "existing") return { word: "Už běží", tone: "inert" };
  if (state === "kept") return { word: "Ponecháno", tone: "inert" };
  if (!plan) return { word: "Ke kontrole", tone: "you" };
  if (plan.kind === "start") return { word: "Připraveno", tone: "done" };
  if (plan.kind === "not_ready") return { word: "Blokuje: připravenost", tone: "fault" };
  if (plan.kind === "acknowledge") return { word: "Blokuje: nezodpovězené otázky", tone: "fault" };
  return { word: "Blokuje: neznámá cena", tone: "fault" };
}

const usdOrNull = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** What a run can cost at most, as its card's key fact: the API's figure, or that it is unknown. */
export const ceilingWords = (ceiling: number | null): string => (ceiling === null ? "Neznámá: AIA ji předem neumí určit" : `${jobCostUsd(ceiling)} USD`);

/**
 * The study's budget beside a run's ceiling, as the card's row reads it: what remains now, and what
 * at least remains after the run at its ceiling -- or that it may cost more than remains. Unknown is
 * said, never zero; the remainder leaves out what running steps hold, which `note` says.
 */
export function budgetFacts(study: { remaining_usd?: number | null } | null, ceiling: number | null): { value: string; note: string | null } {
  const remaining = usdOrNull(study?.remaining_usd);
  if (remaining === null) return { value: "Kolik zbývá, AIA nyní neví", note: null };
  const before = `zbývá ${jobCostUsd(remaining)} USD`;
  const note = "Bez částek, které právě drží běžící kroky.";
  if (ceiling === null) return { value: `${before} → po běhu neznámo`, note };
  if (ceiling > remaining) return { value: `${before} → běh může stát víc`, note: `Přesáhne-li cena zbytek, běh se zastaví, dokud rozpočet nezvýšíte. ${note}` };
  return { value: `${before} → nejméně ${jobCostUsd(remaining - ceiling)} USD`, note };
}

/**
 * Whether a job moves on its own, so its card is worth reading again on a timer: queued or running.
 * A job waiting for budget, for recovery or for the AI runtime moves only when a person acts; it is
 * read again on their action, a budget change or the window's focus, never polled.
 */
export function jobMovesByItself(job: Pick<ResearchAgentJob, "status" | "is_terminal" | "needs_attention" | "steps">): boolean {
  return agentJobState(job) === "running";
}
