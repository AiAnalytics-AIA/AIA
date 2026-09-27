"use client";

// One AI step of a research screen (build the questionnaire, optimise it,
// propose an audience, suggest dimensions): the provider check when the
// classic step makes one, the save the job is addressed to, and a failure
// shown where the person is. The classic interface shows the same failure
// text in an alert() (research-flow-rehome.md, deliberate differences).

import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { JobError } from "@/unit/research/jobs";
import { activeProvider, notReadyMessage, providerReady } from "@/unit/research/provider";
import { createSupportBundle } from "@/unit/support";
import { Icon } from "../icons";
import { Button } from "../ui";
import { useResearch } from "./context";

export type AiFailure = { kind: "job"; message: string; jobId: string | null } | { kind: "provider"; message: string };

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function useAiStep() {
  const { store, boot } = useResearch();
  const [failure, setFailure] = useState<AiFailure | null>(null);
  const [busy, setBusy] = useState(false);

  /** ensureClaudeReady1776, as a notice: false when the provider is not ready. */
  const providerOk = async (): Promise<boolean> => {
    const s = store.get();
    const provider = activeProvider(s.preferredProvider, s.project.run_policy?.provider, boot);
    if (await providerReady(provider, { boot, model: String(s.project.model || "") })) return true;
    setFailure({ kind: "provider", message: notReadyMessage() });
    return false;
  };

  /** The job is addressed to the saved project: a new or edited one is saved first. */
  const saved = async (): Promise<void> => {
    const s = store.get();
    if (!s.projectId || s.save.kind !== "saved") await store.flush();
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
      setFailure({ kind: "job", message: wording(message(e)), jobId: e instanceof JobError ? e.jobId : null });
      return false;
    } finally {
      setBusy(false);
    }
  };

  return { run, providerOk, saved, failure, setFailure, busy };
}

/** A failed AI step, said in words, with retry and Diagnostika; or the provider notice. */
export function AiFailureCard({ failure, title, sub, onRetry }: { failure: AiFailure; title: string; sub?: string; onRetry: () => void }) {
  const { toast } = useResearch();
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
        {title}
      </h2>
      {sub ? <p className="mt-1 text-sm text-ink">{sub}</p> : null}
      {failure.message ? <p className="mt-1 whitespace-pre-line text-xs text-ink-muted">{failure.message}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" onClick={onRetry}>{t("research.retry")}</Button>
        <Button onClick={() => void diagnostics()}>{t("research.diagnostics")}</Button>
      </div>
    </section>
  );
}
