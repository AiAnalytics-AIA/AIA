"use client";

// The AI analysis of the brief, shared by Zadání and Návrh: analyzeBrief ->
// ensureAnalysis1776 (src/research/brief.ts), with the provider check and
// the classic error card. Návrh runs it again after the follow-up answers and,
// forced, after the comments.

import { useState } from "react";

import { t } from "@/i18n/t";
import {
  ANALYSIS_JOB_TITLE,
  ANALYSIS_WARN_MS,
  BRIEF_EMPTY,
  analysisPayload,
  briefEmpty,
  mergeAnalysis,
  reusableAnalysis,
  withAttachmentContext,
} from "@/research/brief";
import { isNativeResult } from "@/lib/research-agent-jobs";
import { useResearch } from "./context";
import { AiFailureCard, failureOf } from "./useAiStep";

export type AnalysisFailure =
  | { kind: "analysis"; message: string; jobId: string | null }
  | { kind: "provider"; message: string }
  /** The analysis job stopped at the study's budget: it waits for a lift (CR-2). */
  | { kind: "budget"; jobId: string };

const analysisFailureOf = (e: unknown): AnalysisFailure => {
  const f = failureOf(e);
  return f.kind === "job" ? { kind: "analysis", message: f.message, jobId: f.jobId } : f;
};

export function useAnalysis() {
  const { store, template, runJob, continueJob } = useResearch();
  const [failure, setFailure] = useState<AnalysisFailure | null>(null);
  const [busy, setBusy] = useState(false);

  /**
   * Analyse the brief as it is in the store. Resolves true when there is an
   * analysis of it (reused or new), false when it failed (the failure is kept).
   * `byComments` marks the plan as changed by the person's comments; any other
   * new analysis clears that mark.
   */
  const analyse = async ({ force = false, byComments = false }: { force?: boolean; byComments?: boolean } = {}): Promise<boolean> => {
    setFailure(null);
    const existing = store.get();
    if (!force && reusableAnalysis(withAttachmentContext(existing.project), existing.analysis)) return true;
    setBusy(true);
    try {
      const current = store.get();
      const withCtx = withAttachmentContext(current.project);
      if (briefEmpty(withCtx)) throw new Error(BRIEF_EMPTY);
      // The job is addressed to the saved project: a new or edited brief is saved first.
      if (current.revision === null || current.save.kind !== "saved") await store.flush();
      const result = await runJob("researchAnalyze", analysisPayload(withCtx), { title: ANALYSIS_JOB_TITLE, warnMs: ANALYSIS_WARN_MS });
      if (isNativeResult(result)) {
        store.update(({ project }) => ({ project: { ...project, ui_state: { ...project.ui_state, plan_changed26: byComments } } }), { reason: "native_analysis_reviewed" });
        return true;
      }
      store.update(() => {
        const merged = mergeAnalysis(withCtx, result, template);
        return { ...merged, project: { ...merged.project, ui_state: { ...merged.project.ui_state, plan_changed26: byComments } } };
      }, { reason: "ai_analysis_1780" });
      return true;
    } catch (e) {
      setFailure(analysisFailureOf(e));
      return false;
    } finally {
      setBusy(false);
    }
  };

  /**
   * After a budget lift: follow the same analysis job on to its proposal (CR-2). Starts nothing.
   * Resolves true when it completed, as `analyse` does.
   */
  const resume = async (jobId: string): Promise<boolean> => {
    setFailure(null);
    setBusy(true);
    try {
      // Whether the person's comments asked for it is not known here, so the mark is left as it is.
      await continueJob(jobId);
      return true;
    } catch (e) {
      setFailure(analysisFailureOf(e));
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { analyse, resume, failure, clearFailure: () => setFailure(null), busy };
}

/**
 * The classic analysis error card, with what failed said in words, or the provider notice, or the
 * study's budget lift for a job that waits (`onContinue` follows the same job).
 */
export function AnalysisFailureCard({ failure, onRetry, onContinue }: { failure: AnalysisFailure; onRetry: () => void; onContinue: (jobId: string) => void }) {
  return (
    <AiFailureCard
      failure={failure.kind === "analysis" ? { kind: "job", message: failure.message, jobId: failure.jobId } : failure}
      title={t("research.brief.failedTitle")}
      sub={t("research.brief.failedSub")}
      onRetry={onRetry}
      onContinue={onContinue}
    />
  );
}
