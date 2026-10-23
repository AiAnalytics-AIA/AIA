"use client";

// I7b: the modal for a consequential action that is not money (input-interactions I7; SpendDialog
// is money's). It names the thing changed, what holds now beside what the action makes of it, and
// what follows, in a sentence; the primary button names the act ("Schválit"), never "OK". The safe
// choice has the focus, Esc cancels, and a refusal from the server is said inside, beside the
// action it refused. Optional fields (a reason) come as children.

import { type ReactNode, useId, useLayoutEffect, useRef } from "react";

import { t } from "@/i18n/t";
import { Button } from "../rehome/ui";

export type ConfirmRow = { label: string; value: ReactNode };

export function ConfirmDialog({ open, title, rows = [], text, children, confirmLabel, cancelLabel, busy = false, error, marker, onConfirm, onCancel }: {
  open: boolean;
  title: string;
  /** What the action changes, a row each: "V platnosti 365 dní", "Schválíte 90 dní". */
  rows?: readonly ConfirmRow[];
  /** What follows from it, in a sentence or two. */
  text: ReactNode;
  children?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  error?: string | null;
  /** A data attribute on the dialog's body (`data-<marker>`), for the page's own tests and journeys. */
  marker?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useLayoutEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      // showModal focuses the first focusable element; the safe choice takes it instead.
      d.querySelector<HTMLElement>("[data-confirm-safe]")?.focus();
    }
    if (!open && d.open) d.close();
  }, [open]);
  const body = marker ? { [`data-${marker}`]: "" } : {};
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => { e.preventDefault(); if (!busy) onCancel(); }}
      className="m-auto w-[min(30rem,calc(100vw-2rem))] rounded-md border border-border-strong bg-surface-overlay p-0 text-ink shadow-[var(--shadow-overlay)] backdrop:bg-surface-inverse/40"
    >
      {open ? (
        <div {...body} className="flex flex-col gap-4 p-5">
          <h2 id={titleId} className="text-base font-semibold leading-6">{title}</h2>
          {rows.length ? (
            <dl className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] gap-x-3 gap-y-2 text-[13px] leading-5">
              {rows.map((r) => (
                <div key={r.label} className="contents">
                  <dt className="text-ink-muted">{r.label}</dt>
                  <dd className="break-words font-medium">{r.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          <div className="text-sm leading-6">{text}</div>
          {children}
          {error ? <p role="alert" className="rounded-sm border border-status-fault/40 bg-status-fault-wash p-2 text-[13px] text-status-fault">{error}</p> : null}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="quiet" data-confirm-safe="" disabled={busy} onClick={onCancel}>{cancelLabel ?? t("dialog.cancel")}</Button>
            <Button variant="primary" disabled={busy} onClick={onConfirm}>{confirmLabel}</Button>
          </div>
        </div>
      ) : null}
    </dialog>
  );
}
