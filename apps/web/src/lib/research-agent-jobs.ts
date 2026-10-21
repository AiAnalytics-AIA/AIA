// Native Research job following. Durable identity/state live on the server.
import { ApiError, researchAgents, type ResearchAgentAction, type ResearchAgentJob } from "./api";
import { money } from "@/i18n/cs";
import { JobError, jobMeta, type JobUpdate } from "@/research/jobs";
import { agentJobOrb } from "./activity-orb";

/**
 * The AI steps a research stage asks for, by the name the stages have always used
 * (the classic job endpoints' keys), and the AIA research agent action each one
 * runs. Deep research has no action yet (ADR 0017): asking for it says so.
 */
export const ACTIONS = {
  researchAnalyze: "analyze_brief", researchBuildQuestionnaire: "build_questionnaire",
  questionnaireOptimize: "optimize_questionnaire", audiencePropose: "propose_audience",
  personaSuggest: "suggest_dimensions",
} as const satisfies Record<string, ResearchAgentAction>;
export type ResearchJobKey = keyof typeof ACTIONS;
export const ACTION_LABELS: Record<ResearchAgentAction, string> = {
  analyze_brief: "Analýza zadání", build_questionnaire: "Návrh dotazníku",
  optimize_questionnaire: "Úprava dotazníku", propose_audience: "Návrh audience",
  suggest_dimensions: "Návrh dimenzí", critique_design: "Kontrola návrhu",
  design_copilot: "Pomoc s návrhem", answer_memory: "Klientské znalosti",
};
export const isNativeResult = (result: unknown): result is { native: true } =>
  !!result && typeof result === "object" && "native" in result && result.native === true;

/**
 * Where an agent job stands, as the stage acts on it. A job stopped at the study's budget cap is
 * waiting, not failed: the same job goes on once a person lifts the budget, and nothing new is
 * started for it (CR-2). Unknown statuses read as still running, never as done.
 */
export type AgentJobState = "completed" | "running" | "awaiting_budget" | "waiting" | "cancelled" | "failed";

export function agentJobState(job: Pick<ResearchAgentJob, "status" | "is_terminal" | "needs_attention" | "steps">): AgentJobState {
  if (job.status === "COMPLETED") return "completed";
  if (job.status === "CANCELLED") return "cancelled";
  if (job.is_terminal) return "failed";
  if (job.status === "AWAITING_BUDGET" || job.steps.some((s) => s.status === "AWAITING_BUDGET")) return "awaiting_budget";
  if (job.needs_attention || job.status.startsWith("WAITING") || job.status.startsWith("AWAITING") || job.status === "RECOVERY_REQUIRED") return "waiting";
  return "running";
}

/**
 * The server refused to create a job because its ceiling reaches the study's confirmation threshold
 * (409 cost_confirmation_required, lead-orchestration LO15): the ceiling it worked out and the
 * threshold. Anything else, or details that are not both numbers, is not a question to put to a person.
 */
export function jobCostAsked(e: unknown): { ceiling: number; limit: number } | null {
  if (!(e instanceof ApiError) || e.code !== "cost_confirmation_required") return null;
  const { ceiling_usd, limit_usd } = e.details as { ceiling_usd?: unknown; limit_usd?: unknown };
  return typeof ceiling_usd === "number" && Number.isFinite(ceiling_usd) && typeof limit_usd === "number" && Number.isFinite(limit_usd)
    ? { ceiling: ceiling_usd, limit: limit_usd } : null;
}

const usd = (n: number) => n.toLocaleString("cs-CZ", { maximumFractionDigits: 2 });
/** The question a person answers before a job that reaches the threshold starts. */
export const jobCostQuestion = (asked: { ceiling: number; limit: number }) =>
  `AI krok může stát až ${usd(asked.ceiling)} USD, což dosahuje hodnoty „${money.confirmThreshold}“ studie (${usd(asked.limit)} USD). Spustit?`;

/**
 * Create a job, asking the person once when the server's threshold asks: `create(undefined)` first,
 * then, on a yes, `create(ceiling)` with exactly the ceiling the server named. A no, or a second
 * refusal, is thrown as it came; nothing is started without the server's own figure confirmed.
 */
export async function withJobCostConfirmation<T>(create: (confirmCostUsd?: number) => Promise<T>, confirm: (message: string) => Promise<boolean>): Promise<T> {
  try {
    return await create(undefined);
  } catch (e) {
    const asked = jobCostAsked(e);
    if (!asked || !(await confirm(jobCostQuestion(asked)))) throw e;
    return create(asked.ceiling);
  }
}

/** What a stage says of a job stopped at the study's budget: it waits, it did not fail. */
export const BUDGET_WAIT_MESSAGE = "AI krok čeká na rozpočet studie: zastavil se, protože by jej překročil. Po zvýšení rozpočtu pokračuje tatáž úloha.";

export function agentJobUpdate(job: ResearchAgentJob, title: string): JobUpdate {
  const startedAt = Date.parse(job.created_at || "") || Date.now();
  const state = agentJobState(job);
  const waiting = state === "waiting" || state === "awaiting_budget";
  const last = job.steps.find((s) => s.error_message);
  return { jobId: job.run_id, title,
    phase: job.status === "COMPLETED" ? "Návrh je připravený k revizi" : state === "awaiting_budget" ? "Čeká na rozpočet studie" : waiting ? "Čeká na zásah" : "AI zpracovává návrh",
    startedAt, orb: agentJobOrb(job), stepId: job.steps[0]?.step_id ?? null,
    paused: state === "awaiting_budget" ? BUDGET_WAIT_MESSAGE : waiting ? last?.error_message || "Krok čeká na schválení nebo dostupnost prostředí." : null,
    meta: jobMeta({ telemetry: { provider: "AWS Bedrock", actual_cost_usd: job.actual_cost_usd ?? undefined } },
      { elapsed: (Date.now() - startedAt) / 1000 }),
  };
}

export async function followAgentJob(studyId: string, jobId: string, title: string,
  onUpdate: (u: JobUpdate) => void, signal?: AbortSignal): Promise<ResearchAgentJob> {
  while (!signal?.aborted) {
    const job = await researchAgents.job(studyId, jobId);
    if (signal?.aborted) break;
    onUpdate(agentJobUpdate(job, title));
    const state = agentJobState(job);
    if (state === "completed") return job;
    // Never a failure: the stage shows the study's budget lift for this same job, no retry.
    if (state === "awaiting_budget") throw new JobError(BUDGET_WAIT_MESSAGE, "awaiting_budget", jobId);
    if (state !== "running") {
      throw new JobError(job.steps.find((s) => s.error_message)?.error_message ||
        (job.status === "CANCELLED" ? "AI krok byl zrušen. Zadání zůstává uložené." : `AI krok čeká na zásah (${job.status}).`),
      "error", jobId);
    }
    await new Promise<void>((resolve) => {
      const finish = () => { clearTimeout(timer); signal?.removeEventListener("abort", finish); resolve(); };
      const timer = setTimeout(finish, 1000);
      signal?.addEventListener("abort", finish, { once: true });
    });
  }
  throw new JobError("Sledování přerušeno; běh zůstává uložený.", "cancelled", jobId);
}
