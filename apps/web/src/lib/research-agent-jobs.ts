// Native Research job following. Durable identity/state live on the server.
import { researchAgents, type ResearchAgentAction, type ResearchAgentJob } from "./api";
import { JobError, jobMeta, type JobUpdate } from "@/unit/research/jobs";
import type { UnitRouteKey } from "@/unit/routes";

export const ACTIONS: Partial<Record<UnitRouteKey, ResearchAgentAction>> = {
  researchAnalyze: "analyze_brief", researchBuildQuestionnaire: "build_questionnaire",
  questionnaireOptimize: "optimize_questionnaire", audiencePropose: "propose_audience",
  personaSuggest: "suggest_dimensions",
};
export const ACTION_LABELS: Record<ResearchAgentAction, string> = {
  analyze_brief: "Analýza zadání", build_questionnaire: "Návrh dotazníku",
  optimize_questionnaire: "Úprava dotazníku", propose_audience: "Návrh audience",
  suggest_dimensions: "Návrh dimenzí", critique_design: "Kontrola návrhu",
  design_copilot: "Pomoc s návrhem", answer_memory: "Klientské znalosti",
};
export const isNativeResult = (result: unknown): result is { native: true } =>
  !!result && typeof result === "object" && "native" in result && result.native === true;

export function agentJobUpdate(job: ResearchAgentJob, title: string): JobUpdate {
  const startedAt = Date.parse(job.created_at || "") || Date.now();
  const waiting = job.status.startsWith("WAITING") || job.status === "RECOVERY_REQUIRED";
  const last = job.steps.find((s) => s.error_message);
  return { jobId: job.run_id, title,
    phase: job.status === "COMPLETED" ? "Návrh je připravený k revizi" : waiting ? "Čeká na zásah" : "AI zpracovává návrh",
    startedAt, paused: waiting ? last?.error_message || "Krok čeká na schválení nebo dostupnost prostředí." : null,
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
    if (job.status === "COMPLETED") return job;
    if (job.is_terminal || job.needs_attention || job.status.startsWith("WAITING")) {
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
