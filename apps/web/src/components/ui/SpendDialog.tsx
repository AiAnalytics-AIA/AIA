"use client";

// I7a: the one modal for money (D-01; the approval cards' anatomy, screen 14 of the design
// artifact). Four questions share it -- Potvrzení útraty, Zvýšení rozpočtu studie, Zvýšení
// rozpočtu klienta, Navýšení peněženky -- and four sums keep their own names: Rozpočet klienta,
// Rozpočet studie, Peněženka, Práh potvrzení. It states what the action buys, its ceiling as
// "horní mez, ne odhad" (an unknown one in words, never zero), the sums it is held against and
// what is left at the highest price. A lift sets its new amount with a money stepper. The
// primary button names the act and the price ("Spustit běh · do 28,40 USD"), never "OK"; the
// safe choice has the focus, and Esc cancels.

import { type ReactNode, useId, useLayoutEffect, useRef, useState } from "react";

import { t } from "@/i18n/t";
import {
  type MoneyLine, type MoneyName, type SpendKind,
  afterWords, ceilingWords, lineWords, moneyName, remainingAfter, spendTitle,
} from "@/lib/spend";
import { Button } from "../rehome/ui";
import { Stepper } from "./Stepper";

export type SpendAmount = {
  /** The amount proposed (the new budget or wallet), USD. */
  value: number;
  min: number;
  max: number;
  /** Whole dollars by default (I2: money steps in whole dollars). */
  step?: number;
};

type Question = {
  kind: SpendKind;
  /** What the action buys, in a sentence or two. */
  summary: ReactNode;
  /** The API's upper bound for the action; null when it cannot be worked out. */
  ceilingUsd: number | null;
  /** What the ceiling is made of ("600 dotazů × rezervace + 8 modulů"). */
  ceilingNote?: string;
  /** The named sums beside it, each once, in the order given. */
  lines: readonly MoneyLine[];
  /** The sum the ceiling is held against: what is left of it is said after the highest price. */
  pays?: MoneyName;
  /** A lift: the new amount of `pays`, set here; the confirmation carries it. */
  amount?: SpendAmount;
  /** Names the act and the price; with an amount, a function of it (null: no amount, never 0 USD). */
  confirmLabel: string | ((amountUsd: number | null) => string);
  /** What leaving it does ("Nechat čekat", "Zrušit"). */
  cancelLabel?: string;
  busy?: boolean;
  /** A refusal from the server, said in the dialog beside the action it refused. */
  error?: string | null;
  /**
   * The person's yes. The dialog awaits nothing: the caller owns the spend, sets `busy` while it
   * runs, and gives a refusal back through `error`, said inside the dialog.
   */
  onConfirm: (amountUsd?: number) => void;
  onCancel: () => void;
};

export function SpendDialog({ open, question, ...q }: Question & {
  open: boolean;
  /**
   * The question's identity (the step, run or job it asks about). Each question is its own form,
   * mounted per identity (AGENTS.md: a dialog's initial value is a child mounted per question),
   * so a question queued behind another never inherits the amount typed into the one before it.
   */
  question: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useLayoutEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      // React runs a child's autoFocus before this effect, on a dialog not yet shown, and
      // showModal then focuses the first focusable element (a lift's stepper button). The safe
      // choice takes the focus here instead (review of #532, P2-4).
      d.querySelector<HTMLElement>("[data-spend-safe]")?.focus();
    }
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        if (!q.busy) q.onCancel();
      }}
      className="m-auto w-[min(35rem,calc(100vw-2rem))] rounded-panel bg-surface-overlay p-0 text-ink shadow-[var(--shadow-overlay)] backdrop:bg-ink/10 backdrop:backdrop-blur-[2px]"
    >
      {open ? <SpendForm key={question} titleId={titleId} {...q} /> : null}
    </dialog>
  );
}

function SpendForm({
  titleId, kind, summary, ceilingUsd, ceilingNote, lines, pays, amount, confirmLabel, cancelLabel, busy = false, error, onConfirm, onCancel,
}: Question & { titleId: string }) {
  const [newAmount, setNewAmount] = useState<number | null>(amount?.value ?? null);
  // A refused amount in the stepper: the confirmation waits until the field holds a valid one.
  const [amountProblem, setAmountProblem] = useState<string | null>(null);

  const payer = pays ? lines.find((l) => l.name === pays) : undefined;
  const after = remainingAfter(payer, ceilingUsd, amount ? newAmount : undefined);
  const ceiling = ceilingWords(ceilingUsd);
  const label = typeof confirmLabel === "function" ? confirmLabel(amount ? newAmount : null) : confirmLabel;
  const amountMissing = amount !== undefined && (newAmount === null || amountProblem !== null);

  return (
    <div className="flex flex-col gap-4 p-6">
      <h2 id={titleId} className="text-base font-semibold leading-6">{spendTitle(kind)}</h2>
      <div className="text-sm leading-6">{summary}</div>
      <dl className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] gap-x-3 gap-y-2 text-[13px] leading-5">
        <dt className="text-ink-muted">{t("input.spend.ceiling")}</dt>
        <dd data-testid="spend-ceiling">
          <b className="font-semibold">{ceiling.value}</b>
          <span className="text-ink-muted"> · {ceiling.note}</span>
          {ceilingNote ? <span className="block text-xs text-ink-faint">{ceilingNote}</span> : null}
        </dd>
        {lines.map((line) => (
          <div key={line.name} className="contents">
            <dt className="text-ink-muted">{moneyName(line.name)}</dt>
            <dd>
              {amount && line.name === pays ? (
                <Stepper
                  label={t("input.spend.newAmount")}
                  value={newAmount}
                  onCommit={setNewAmount}
                  onProblem={setAmountProblem}
                  min={amount.min}
                  max={amount.max}
                  step={amount.step ?? 1}
                  decimals={2}
                  unit="USD"
                  note={lineWords(line)}
                />
              ) : (
                <>
                  {lineWords(line)}
                  {line.note ? <span className="block text-xs text-ink-faint">{line.note}</span> : null}
                </>
              )}
            </dd>
          </div>
        ))}
      </dl>
      {pays ? (
        <p className="text-[13px] leading-5" data-testid="spend-after">
          {afterWords(after)} <span className="text-ink-faint">{t("input.spend.held")}</span>
        </p>
      ) : null}
      {error ? <p role="alert" className="rounded-sm border border-status-fault/40 bg-status-fault-wash p-2 text-[13px] text-status-fault">{error}</p> : null}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="quiet" data-spend-safe="" disabled={busy} onClick={onCancel}>
          {cancelLabel ?? t("dialog.cancel")}
        </Button>
        <Button variant="primary" disabled={busy || amountMissing} onClick={() => onConfirm(amount ? (newAmount ?? undefined) : undefined)}>
          {label}
        </Button>
      </div>
    </div>
  );
}
