"use client";

// What lets a Deep Research run that waits for a person go on (PC4): a step parked because the
// AI runtime was not there goes on when the person says so, once it is; a step stopped at the
// study's budget cap goes on when they raise it. Neither starts a new run, and neither clears
// by itself (domain/workflow.py resume_due), so without these the run waited until cancelled.

import { useState } from "react";

import { t } from "@/i18n/t";
import { deepResearch, type DeepResearchRun } from "@/lib/api";
import { RUNTIME_UNAVAILABLE } from "@/lib/research-execution";

import { Button } from "../ui";
import { BudgetLift } from "./BudgetLift";

export function DeepResearchWaits({ run, studyId, canEdit, onChanged, onError }: {
  run: DeepResearchRun;
  studyId: string;
  canEdit: boolean;
  onChanged: () => void;
  onError: (e: unknown) => void;
}) {
  const [busy, setBusy] = useState(false);
  if (run.is_terminal || !canEdit) return null;
  const parked = run.steps.some((s) => s.status === "WAITING_PROVIDER" && s.waiting_reason === RUNTIME_UNAVAILABLE);
  const budget = run.steps.some((s) => s.status === "AWAITING_BUDGET");
  if (!parked && !budget) return null;
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try { await fn(); onChanged(); }
    catch (e) { onError(e); }
    finally { setBusy(false); }
  };
  return (
    <div className="mt-2 flex flex-col gap-2 text-sm">
      {parked ? (
        <div role="status" className="flex flex-col gap-2 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3">
          <p>{t("research.exec.parkedResume")}</p>
          <div><Button small variant="primary" disabled={busy} onClick={() => void act(() => deepResearch.resume(studyId, run.run_id))}>{t("research.exec.resume")}</Button></div>
        </div>
      ) : null}
      {budget ? <BudgetLift studyId={studyId} busy={busy} lift={(total, note) => void act(() => deepResearch.liftBudget(studyId, run.run_id, total, note))} /> : null}
    </div>
  );
}
