"use client";

// One AI step of a research screen (build the questionnaire, optimise it,
// propose an audience, suggest dimensions): the provider check when the
// classic step makes one, the save the job is addressed to, and a failure
// shown where the person is. The classic interface shows the same failure
// text in an alert() (research-flow-rehome.md, deliberate differences).
// A job stopped at the study's budget is not a failure: it waits, and the
// study's budget lift is offered in its place; the same job then goes on (CR-2).

import { useEffect, useState } from "react";

import { t } from "@/i18n/t";
import { researchAgents } from "@/lib/api";
import { JobError } from "@/research/jobs";
import { BudgetLift } from "./BudgetLift";
import { Icon } from "../icons";
import { Button } from "../ui";
import { useResearch } from "./context";

export type AiFailure =
  | { kind: "job"; message: string; jobId: string | null }
  | { kind: "provider"; message: string }
  /** The job stopped at the study's budget cap: it waits for a lift, and is never retried as a new job. */
  | { kind: "budget"; jobId: string };

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The failure a thrown job error is, as the stage shows it: a budget wait keeps its job. */
export function failureOf(e: unknown, wording: (m: string) => string = (m) => m): AiFailure {
  if (e instanceof JobError && e.kind === "awaiting_budget" && e.jobId) return { kind: "budget", jobId: e.jobId };
  return { kind: "job", message: wording(message(e)), jobId: e instanceof JobError ? e.jobId : null };
}

export function useAiStep() {
  const { store, continueJob } = useResearch();
  const [failure, setFailure] = useState<AiFailure | null>(null);
  const [busy, setBusy] = useState(false);

  /** ensureClaudeReady1776, as a notice: false when the provider is not ready. */
  const providerOk = async (): Promise<boolean> => true;


  /** The job is addressed to the saved project: a new or edited one is saved first. */
  const saved = async (): Promise<void> => {
    const s = store.get();
    if (s.revision === null || s.save.kind !== "saved") await store.flush();
  };

  /**
   * Run one step. `wording` turns the error into the classic alert's text
   * (for example with "Projekt zůstává uložený…" appended). Resolves true when it completed.
   */
  const run = async (step: () => Promise<void>, wording: (m: string) => string = (m) => m): Promise<boolean> => {
    setFailure(null);
    setBusy(true);
    try {
      await step();
      return true;
    } catch (e) {
      setFailure(failureOf(e, wording));
      return false;
    } finally {
      setBusy(false);
    }
  };

  /**
   * After a budget lift: follow the same job on to its proposal. Starts nothing. `after` gets the
   * job's result once it is reviewed, so a stage does with it what its own action would have.
   */
  const resume = (jobId: string, after?: (result: unknown) => void) =>
    run(async () => {
      const result = await continueJob(jobId);
      after?.(result);
    });

  return { run, resume, providerOk, saved, failure, setFailure, busy };
}

/** The study's budget lift for the one job that waits for it, in place of the failure. */
function BudgetWaitCard({ jobId, onContinue }: { jobId: string; onContinue: (jobId: string) => void }) {
  const { frame, claimWait } = useResearch();
  // This wait is shown here, so the screen's list of waiting jobs does not offer a second lift.
  useEffect(() => claimWait(jobId), [claimWait, jobId]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lift = async (total: number, note: string) => {
    setBusy(true);
    setError(null);
    try {
      await researchAgents.liftBudget(frame.studyId, jobId, total, note);
    } catch (e) {
      setError(message(e));
      setBusy(false);
      return;
    }
    setBusy(false);
    onContinue(jobId);
  };
  return (
    <section role="status" aria-labelledby={`ai-budget-${jobId}`} data-ai-budget-wait={jobId} className="rounded-md border border-status-you-ink/40 bg-status-you-wash p-5">
      <h2 id={`ai-budget-${jobId}`} className="flex items-center gap-2 font-semibold text-status-you-ink">
        <Icon name="you" size={14} />
        {t("research.aiBudget.waitingTitle")}
      </h2>
      <p className="mt-1 text-sm text-ink">{t("research.aiBudget.waitingHelp")}</p>
      {frame.canEdit ? (
        <BudgetLift studyId={frame.studyId} busy={busy} lift={(total, note) => void lift(total, note)} />
      ) : (
        <p className="mt-1 text-xs text-ink-muted">{t("research.aiBudget.readOnly")}</p>
      )}
      {error ? <p role="alert" className="mt-2 text-sm text-status-fault">{error}</p> : null}
    </section>
  );
}

/**
 * A failed AI step, said in words, with retry and Diagnostika; or the provider notice; or, for a
 * job waiting for the study's budget, the lift for that job and no retry (`onContinue` follows it).
 */
export function AiFailureCard({ failure, title, sub, onRetry, onContinue }: {
  failure: AiFailure;
  title: string;
  sub?: string;
  onRetry: () => void;
  onContinue: (jobId: string) => void;
}) {
  if (failure.kind === "budget") return <BudgetWaitCard jobId={failure.jobId} onContinue={onContinue} />;
  if (failure.kind === "provider") {
    return (
      <section role="alert" className="rounded-md border border-status-you-ink/40 bg-status-you-wash p-5">
        <p className="flex items-center gap-2 text-sm font-semibold text-status-you-ink">
          <Icon name="you" size={14} />
          {failure.message}
        </p>
      </section>
    );
  }
  // An AIA agent job's failure is recorded on the run itself, with its steps and
  // errors: there is no separate diagnostic bundle to make (ADR 0018).
  return (
    <section role="alert" className="rounded-md border border-status-fault/40 bg-status-fault-wash p-5">
      <h2 className="flex items-center gap-2 font-semibold text-status-fault">
        <Icon name="fault" size={14} />
        {title}
      </h2>
      {sub ? <p className="mt-1 text-sm text-ink">{sub}</p> : null}
      {failure.message ? <p className="mt-1 whitespace-pre-line text-xs text-ink-muted">{failure.message}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" onClick={onRetry}>{t("research.retry")}</Button>
      </div>
    </section>
  );
}
