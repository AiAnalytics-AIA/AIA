"use client";

// The research steps' shared pieces, drawn as Studio v3: a step is a column of
// numbered sections, closed by one sticky action dock. Each piece only draws a
// value and reports a change; what the change does to the project stays with the
// step and src/research. Token utilities only, as in ui.tsx.

import Link from "next/link";
import { type KeyboardEvent, type ReactNode, useId, useState } from "react";

import { t } from "@/i18n/t";
import { Icon } from "./icons";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

/**
 * One numbered section of a step: a card whose body lines up with its title.
 * Required sections number in the signal; optional ones say so and stay quiet;
 * `done` marks a section already answered.
 */
export function StepSection({
  id, n, title, hint, optional = false, done = false, lead = false, aside, children,
}: {
  id?: string;
  n: number;
  title: string;
  hint?: ReactNode;
  optional?: boolean;
  done?: boolean;
  /** The step's lead question: a larger title. */
  lead?: boolean;
  /** Something at the right of the header (a count, an action). */
  aside?: ReactNode;
  children?: ReactNode;
}) {
  const headingId = useId();
  const mark = done ? "bg-status-done/14 text-status-done" : optional ? "bg-surface-sunken text-ink-muted" : "bg-signal-wash text-signal";
  return (
    <section id={id} aria-labelledby={headingId} className="scroll-mt-60 rounded-card border border-border bg-surface-raised p-5">
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className={`inline-flex size-6 shrink-0 items-center justify-center rounded-full font-mono text-xs font-semibold ${mark}`}>
          {done ? <Icon name="done" size={12} /> : n}
        </span>
        <div className="min-w-0 flex-1">
          <h2 id={headingId} className={`font-semibold ${lead ? "text-lg leading-[26px]" : "text-base leading-6"}`}>
            {title}
            {optional ? <span className="text-[13px] font-normal text-ink-faint"> · {t("research.step.optional")}</span> : null}
          </h2>
          {hint ? <p className="mt-0.5 text-[13px] leading-5 text-ink-muted">{hint}</p> : null}
        </div>
        {aside}
      </div>
      {children ? <div className="mt-3.5 pl-9">{children}</div> : null}
    </section>
  );
}

/**
 * The step's sticky dock: the way back on the left, why the step is or is not
 * ready in the middle, the one primary action on the right. It replaces each
 * step's bottom row; the action keeps the conditions it had there.
 */
export function ActionDock({ back, note, ready = true, children }: {
  back?: { href: string; label: string };
  note?: ReactNode;
  /** false: the note is a reason the step is not ready yet. */
  ready?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="sticky bottom-4 z-[6] flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface-raised px-3 py-2.5 shadow-[var(--shadow-overlay)]">
      {back ? (
        <Link href={back.href} className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm text-sm text-ink-muted no-underline hover:text-ink ${FOCUS}`}>
          <Icon name="back" size={14} />
          {back.label}
        </Link>
      ) : null}
      <span aria-live="polite" className={`ml-auto min-w-0 flex-[1_1_160px] text-right text-[13px] leading-5 ${ready ? "text-ink-muted" : "text-status-you-ink"}`}>
        {note}
      </span>
      <div className="flex shrink-0 items-center gap-2">{children}</div>
    </div>
  );
}

/** One choice of a radio group, as a card. The group is the caller's `role="radiogroup"`. */
export function RadioCard({ checked, onSelect, disabled, title, children }: {
  checked: boolean;
  onSelect: () => void;
  disabled?: boolean;
  title: ReactNode;
  children?: ReactNode;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      disabled={disabled}
      onClick={onSelect}
      className={`flex w-full items-start gap-3 rounded-card p-3.5 text-left disabled:opacity-50 ${FOCUS} ${
        checked ? "border-2 border-signal bg-signal-wash" : "m-px border border-border bg-surface-raised hover:border-border-strong"
      }`}
    >
      <span aria-hidden="true" className={`mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full border ${checked ? "border-signal" : "border-border-strong"}`}>
        {checked ? <i className="block size-2 rounded-full bg-signal" /> : null}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">{title}</span>
        {children ? <span className="mt-0.5 block text-[13px] leading-5 text-ink-muted">{children}</span> : null}
      </span>
    </button>
  );
}

/** An on/off setting. */
export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (on: boolean) => void; label: ReactNode; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`inline-flex items-center gap-2.5 rounded-sm text-left text-sm disabled:opacity-50 ${FOCUS}`}
    >
      <span aria-hidden="true" className={`relative inline-block h-5 w-[34px] shrink-0 rounded-pill transition-colors ${checked ? "bg-signal" : "bg-border-strong"}`}>
        <i className={`absolute top-0.5 block size-4 rounded-full bg-surface-raised shadow-sm transition-[left] ${checked ? "left-4" : "left-0.5"}`} />
      </span>
      <span>{label}</span>
    </button>
  );
}

/** A small segmented control: one of a few views or modes. */
export function Segmented<K extends string>({ value, options, onChange, label }: {
  value: K;
  options: readonly { key: K; label: ReactNode }[];
  onChange: (key: K) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex gap-0.5 rounded-card bg-surface-sunken p-[3px]">
      {options.map((o) => {
        const on = o.key === value;
        return (
          <button
            key={o.key}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(o.key)}
            className={`min-h-8 whitespace-nowrap rounded-control px-3 text-[13px] ${FOCUS} ${on ? "bg-surface-raised font-semibold text-ink shadow-[0_1px_2px_rgba(0,0,0,0.08)]" : "text-ink-muted hover:text-ink"}`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/**
 * A list of short values typed in: Enter adds the trimmed value, × removes one.
 * `backspaceRemoves` lets Backspace in an empty field take the last one back.
 */
export function ChipInput({ values, onAdd, onRemove, label, placeholder, backspaceRemoves = false }: {
  values: readonly string[];
  onAdd: (value: string) => void;
  onRemove: (index: number) => void;
  label: string;
  placeholder?: string;
  backspaceRemoves?: boolean;
}) {
  const [draft, setDraft] = useState("");
  const key = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const v = draft.trim();
      if (v) onAdd(v);
      setDraft("");
    } else if (e.key === "Backspace" && backspaceRemoves && !draft && values.length) {
      onRemove(values.length - 1);
    }
  };
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-1.5 rounded-control border border-border-strong bg-surface-raised px-2 py-1 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus-ring">
      {values.map((v, i) => (
        <span key={`${i}-${v}`} className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-border bg-surface px-2 py-0.5 text-[13px] leading-5">
          {v}
          <button type="button" aria-label={`${t("research.step.remove")} ${v}`} onClick={() => onRemove(i)} className={`rounded-sm px-0.5 text-ink-faint hover:text-ink ${FOCUS}`}>
            ×
          </button>
        </span>
      ))}
      <input
        aria-label={label}
        placeholder={placeholder}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={key}
        className="min-h-7 min-w-32 flex-1 border-0 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
      />
    </div>
  );
}

/**
 * A destructive action confirmed on the card itself, instead of a browser
 * confirm(): the question, the action in the fault colour, and a way to keep it.
 */
export function InlineConfirm({ message, action, onConfirm, onCancel }: { message: ReactNode; action: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <div role="alertdialog" aria-label={typeof message === "string" ? message : undefined} className="flex flex-wrap items-center gap-2">
      <span className="text-[13px] text-status-fault">{message}</span>
      <button
        type="button"
        onClick={onConfirm}
        className={`min-h-7 whitespace-nowrap rounded-control border border-status-fault bg-status-fault px-2.5 text-xs font-medium text-on-status-fault ${FOCUS}`}
      >
        {action}
      </button>
      <button
        type="button"
        autoFocus
        onClick={onCancel}
        className={`min-h-7 whitespace-nowrap rounded-control border border-border-strong bg-surface-raised px-2.5 text-xs font-medium text-ink hover:bg-surface-sunken ${FOCUS}`}
      >
        {t("research.step.keep")}
      </button>
    </div>
  );
}
