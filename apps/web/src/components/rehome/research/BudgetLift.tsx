"use client";

// The one form that lets work stopped at the study's budget cap go on: a research run's step,
// an agent job or a Deep Research run (PC4). The person names a new total, never lower than
// the budget now, and the cap stays hard -- the work stops again if that is still not enough.
// The decision is recorded by the API; nothing here decides it.

import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { api } from "@/lib/api";
import { budgetLine, type StudyBudget } from "@/lib/budget-line";

import { Button, Field, TextArea, TextInput } from "../ui";

export function BudgetLift({ studyId, lift, busy, label }: {
  studyId: string;
  /** Raise the study's budget to `total` and let the waiting work go on; the caller shows any refusal. */
  lift: (total: number, note: string) => void;
  busy: boolean;
  /** What the form is for, read by a screen reader: the step or job that waits. */
  label?: string;
}) {
  const [current, setCurrent] = useState<{ budget: number; spent: number | null; study: StudyBudget } | null | undefined>(undefined);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => {
    let live = true;
    api.study(studyId).then(
      (s) => {
        if (!live) return;
        const budget = typeof s.budget_usd === "number" ? s.budget_usd : null;
        // A spend the API did not report is unknown, never zero.
        setCurrent(budget === null ? null : { budget, spent: typeof s.spent_usd === "number" ? s.spent_usd : null, study: s });
        if (budget !== null) setAmount(String(budget));
      },
      () => live && setCurrent(null),
    );
    return () => {
      live = false;
    };
  }, [studyId]);
  const total = amount.trim() === "" ? Number.NaN : Number(amount);
  const valid = current != null && Number.isFinite(total) && total >= current.budget;
  return (
    <form
      aria-label={label ?? t("research.exec.budget.title")}
      className="mt-1 flex flex-col gap-2 rounded-sm border border-border bg-surface p-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) lift(total, note.trim());
      }}
    >
      {current === undefined ? (
        <p className="text-xs text-ink-muted">{t("research.loading")}</p>
      ) : current === null ? (
        <p role="alert" className="text-xs text-status-fault">{t("research.exec.budget.unknown")}</p>
      ) : (
        <p className="text-xs">
          {current.spent === null ? tv("research.exec.budget.statusSpentUnknown", { budget: current.budget.toFixed(2) }) : tv("research.exec.budget.status", { budget: current.budget.toFixed(2), spent: current.spent.toFixed(2) })}{" "}
          {budgetLine(current.study)}
        </p>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("research.exec.budget.amount")} className="w-48">
          <TextInput type="number" inputMode="decimal" min={current?.budget ?? 0} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} disabled={current == null} />
        </Field>
        <Field label={t("research.exec.budget.note")} className="min-w-48 flex-1">
          <TextArea rows={1} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} className="min-h-9 w-full" />
        </Field>
        <Button type="submit" variant="primary" disabled={!valid || busy}>{t("research.exec.budget.lift")}</Button>
      </div>
      <p className="text-xs text-ink-muted">{t("research.exec.budget.hardCap")}</p>
    </form>
  );
}
