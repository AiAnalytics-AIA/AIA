"use client";

// An AI job stopped at the study's budget cap (PC4). Asking the same action again on the same
// design returns that job, so without a lift it waited until cancelled. The person raises the
// budget here and the same job goes on; nothing new is started.

import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { researchAgents, type ResearchAgentJob } from "@/lib/api";
import { ACTION_LABELS } from "@/lib/research-agent-jobs";

import { BudgetLift } from "./BudgetLift";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function AgentBudgetWaits({ jobs, studyId, canEdit, onChanged }: {
  jobs: ResearchAgentJob[];
  studyId: string;
  canEdit: boolean;
  onChanged: () => Promise<unknown>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const waiting = jobs.filter((j) => !j.is_terminal && j.steps.some((s) => s.status === "AWAITING_BUDGET"));
  if (!waiting.length) return null;
  const lift = async (job: ResearchAgentJob, total: number, note: string) => {
    setBusy(true); setError(null);
    try { await researchAgents.liftBudget(studyId, job.run_id, total, note); await onChanged(); }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };
  return (
    <section aria-labelledby="agent-budget-title" className="my-4 flex flex-col gap-3 rounded-md border border-status-you-ink/40 bg-status-you-wash p-4 text-sm">
      <h2 id="agent-budget-title" className="font-semibold">{t("research.aiBudget.title")}</h2>
      <p>{t("research.aiBudget.help")}</p>
      {waiting.map((job) => (
        <div key={job.run_id} className="flex flex-col gap-1">
          <p className="font-medium">{tv("research.aiBudget.job", { action: ACTION_LABELS[job.action], when: job.created_at ? new Date(job.created_at).toLocaleString("cs-CZ") : "" })}</p>
          {canEdit ? <BudgetLift studyId={studyId} busy={busy} label={ACTION_LABELS[job.action]} lift={(total, note) => void lift(job, total, note)} /> : null}
        </div>
      ))}
      {error ? <p role="alert" className="text-status-fault">{error}</p> : null}
    </section>
  );
}
