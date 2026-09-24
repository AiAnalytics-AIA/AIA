"use client";

// The AI analysis of the brief, shared by Zadání and Návrh: analyzeBrief ->
// ensureAnalysis1776 (src/unit/research/brief.ts), with the provider check and
// the classic error card. Návrh runs it again after the follow-up answers and,
// forced, after the comments.

import { useState } from "react";

import { classicHref } from "@/lib/interface-handoff";
import { t, tv } from "@/i18n/t";
import {
  ANALYSIS_JOB_TITLE,
  ANALYSIS_REUSED,
  ANALYSIS_WARN_MS,
  BRIEF_EMPTY,
  analysisPayload,
  briefEmpty,
  mergeAnalysis,
  reusableAnalysis,
  withAttachmentContext,
} from "@/unit/research/brief";
import { JobError } from "@/unit/research/jobs";
import { activeProvider, notReadyMessage, providerReady } from "@/unit/research/provider";
import { createSupportBundle } from "@/unit/support";
import { Icon } from "../icons";
import { Button, ClassicLink } from "../ui";
import { useResearch } from "./context";

export type AnalysisFailure = { kind: "analysis"; message: string; jobId: string | null } | { kind: "provider"; message: string };

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function useAnalysis() {
  const { store, boot, runJob, toast } = useResearch();
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
    setBusy(true);
    try {
      const current = store.get();
      const withCtx = withAttachmentContext(current.project);
      if (!force && reusableAnalysis(withCtx, current.analysis)) {
        if (withCtx.briefing.attachments_context !== current.project.briefing.attachments_context) {
          store.update(() => ({ project: withCtx }), { reason: "brief_attachments_context", invalidateCheck: false });
        }
        toast(ANALYSIS_REUSED);
        return true;
      }
      if (briefEmpty(withCtx)) throw new Error(BRIEF_EMPTY);
      const provider = activeProvider(current.preferredProvider, current.project.run_policy?.provider, boot);
      if (!(await providerReady(provider, { boot, model: String(current.project.model || "") }))) {
        setFailure({ kind: "provider", message: notReadyMessage(provider) });
        return false;
      }
      // The job is addressed to the saved project: a new or edited brief is saved first.
      if (!current.projectId || current.save.kind !== "saved") await store.flush();
      const result = await runJob("researchAnalyze", analysisPayload(withCtx), { title: ANALYSIS_JOB_TITLE, warnMs: ANALYSIS_WARN_MS });
      store.update(() => {
        const merged = mergeAnalysis(withCtx, result, boot);
        return { ...merged, project: { ...merged.project, ui_state: { ...merged.project.ui_state, plan_changed26: byComments } } };
      }, { reason: "ai_analysis_1780" });
      return true;
    } catch (e) {
      setFailure({ kind: "analysis", message: message(e), jobId: e instanceof JobError ? e.jobId : null });
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { analyse, failure, clearFailure: () => setFailure(null), busy };
}

/** The classic error card, with what failed said in words, or the provider notice. */
export function AnalysisFailureCard({ failure, onRetry }: { failure: AnalysisFailure; onRetry: () => void }) {
  const { toast } = useResearch();
  if (failure.kind === "provider") {
    return (
      <section role="alert" className="rounded-md border border-status-you-ink/40 bg-status-you-wash p-5">
        <p className="flex items-center gap-2 text-sm font-semibold text-status-you-ink">
          <Icon name="you" size={14} />
          {failure.message}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={onRetry}>{t("research.retry")}</Button>
          <ClassicLink href={classicHref({ go: "settings" })}>{t("research.openSettings")}</ClassicLink>
        </div>
      </section>
    );
  }
  const diagnostics = () =>
    createSupportBundle(failure.jobId).then(
      (url) => {
        toast(t("research.supportCreated"));
        window.location.href = url;
      },
      (e: unknown) => toast(tv("research.supportFailed", { message: message(e) })),
    );
  return (
    <section role="alert" className="rounded-md border border-status-fault/40 bg-status-fault-wash p-5">
      <h2 className="flex items-center gap-2 font-semibold text-status-fault">
        <Icon name="fault" size={14} />
        {t("research.brief.failedTitle")}
      </h2>
      <p className="mt-1 text-sm text-ink">{t("research.brief.failedSub")}</p>
      {failure.message ? <p className="mt-1 text-xs text-ink-muted">{failure.message}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" onClick={onRetry}>{t("research.retry")}</Button>
        <Button onClick={() => void diagnostics()}>{t("research.diagnostics")}</Button>
      </div>
    </section>
  );
}
