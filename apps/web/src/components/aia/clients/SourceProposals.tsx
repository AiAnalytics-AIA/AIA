"use client";

// Navrhnout znalosti on a document (lifecycle K2d5): ask AI for knowledge proposals from one
// of the client's sources, follow the run, and say where its proposals wait. The run is the
// client's own work, paid by the client's budget; a run stopped at that budget offers the lift
// to a person who may set it. Nothing here decides anything: the proposals wait in Ke schválení.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { ApiError, type ProposalsRun, type SourceDetail, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { PROPOSALS_STEP, POLL_MS, isMoving, mayAsk, proposalsLine, proposalsPhase, proposalsReason } from "@/lib/source-proposals";
import { AiButton, Button, Chip, Field, TextInput } from "../../rehome/ui";
import { errorText } from "@/lib/error-words";

/** What the person may do with AI proposals on this client. */
export type AiRights = {
  /** PROPOSE_CLIENT_KNOWLEDGE and RUN_CLIENT_WORK. */
  ask: boolean;
  /** MANAGE_CLIENT_BUDGET: raise the client's budget for a run stopped at it. */
  lift: boolean;
};

/** A request's refusal in words: a reason AIA knows, else the message. */
function said(e: unknown): string {
  if (e instanceof ApiError && e.status === 422 && e.code !== "budget_not_raised") return proposalsReason(e.code);
  return errorText(e);
}

export function SourceProposals({ clientId, source, rights }: { clientId: string; source: SourceDetail; rights: AiRights }) {
  // undefined: not read yet; null: nobody has asked.
  const [run, setRun] = useState<ProposalsRun | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [amount, setAmount] = useState("");

  const load = useCallback(
    () =>
      workspace.sourceProposals(clientId, source.source_id).then(
        (r) => {
          setRun(r);
          return r;
        },
        (e: unknown) => {
          setError(said(e));
          return undefined;
        },
      ),
    [clientId, source.source_id],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const phase = proposalsPhase(run ?? null);
  const moving = isMoving(phase);
  // Read again while it moves on its own; a wait for a person or the world is read on return.
  useEffect(() => {
    if (!moving) return;
    const timer = setTimeout(() => void load(), POLL_MS);
    return () => clearTimeout(timer);
  }, [moving, run, load]);

  if (run === undefined && !error) return null;

  const ask = () => {
    setBusy(true);
    setError(null);
    workspace.proposeFromSource(clientId, source.source_id).then(
      (r) => {
        setRun(r);
        setBusy(false);
      },
      (e: unknown) => {
        setError(said(e));
        setBusy(false);
      },
    );
  };

  const lift = () => {
    const budget = Number(amount.replace(",", "."));
    if (phase.phase !== "budget" || !Number.isFinite(budget) || budget <= 0) return;
    setBusy(true);
    setError(null);
    workspace.liftClientWork(clientId, phase.runId, PROPOSALS_STEP, budget).then(
      () => {
        setAmount("");
        setBusy(false);
        void load();
      },
      (e: unknown) => {
        setError(said(e));
        setBusy(false);
      },
    );
  };

  const line = proposalsLine(phase);
  const again = run !== undefined && mayAsk(run);
  return (
    <section aria-label={t("aia.sources.ai.action")} className="flex flex-col gap-2 border-t border-border pt-2 text-xs" data-proposals={run?.run_id ?? ""}>
      {run === null ? <p className="text-ink-muted">{t("aia.sources.ai.hint")}</p> : null}
      <div aria-live="polite" className="flex flex-col gap-1.5">
        {line ? (
          <span>
            <Chip tone={line.tone}>{line.text}</Chip>
          </span>
        ) : null}
        {phase.phase === "done" && phase.dropped ? (
          <p className="text-ink-faint">{tv("aia.sources.ai.dropped", { n: phase.dropped })}</p>
        ) : null}
        {run && !run.current ? <p className="text-status-you-ink">{t("aia.sources.ai.stale")}</p> : null}
      </div>
      {phase.phase === "done" && phase.proposed ? (
        <Link className="w-fit text-signal underline" href={`${appRoutes.area(clientId, "knowledge")}?view=review`}>
          {t("aia.sources.ai.review")}
        </Link>
      ) : null}
      {phase.phase === "budget" && rights.lift ? (
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t("aia.sources.ai.liftAmount")}>
            <TextInput inputMode="decimal" value={amount} disabled={busy} onChange={(e) => setAmount(e.target.value)} className="w-28" />
          </Field>
          <Button small disabled={busy || !amount.trim()} onClick={lift}>{t("aia.sources.ai.lift")}</Button>
          <p className="basis-full text-ink-faint">{t("aia.sources.ai.liftHint")}</p>
        </div>
      ) : null}
      {rights.ask && again ? (
        <span>
          {/* The AI colour says a click is paid; the title says by whom: the client, never a study. */}
          <AiButton small title={t("aia.sources.ai.title")} disabled={busy} onClick={ask}>
            {busy ? t("aia.sources.ai.asking") : run?.resumable ? t("aia.sources.ai.resume") : run ? t("aia.sources.ai.again") : t("aia.sources.ai.action")}
          </AiButton>
        </span>
      ) : null}
      {error ? <p role="alert" className="text-status-fault">{error}</p> : null}
    </section>
  );
}
