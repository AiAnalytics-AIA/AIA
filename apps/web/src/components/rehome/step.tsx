"use client";

// The research steps' shared pieces, drawn as Studio v3: a step is a column of
// numbered sections, closed by one sticky action dock. Each piece only draws a
// value and reports a change; what the change does to the project stays with the
// step and src/research. Token utilities only, as in ui.tsx.

import Link from "next/link";
import { createContext, type KeyboardEvent, type ReactNode, useContext, useId, useRef, useState } from "react";

import { FOCUS, TOUCH } from "@/components/ui/parts";
import { t, tv } from "@/i18n/t";
import { rovingIndex, tabStop } from "@/lib/roving";
import { Icon } from "./icons";
import { InlineText } from "../ui/InlineText";

/**
 * One section of a step: a card whose header carries the title, its help under it,
 * and anything the section acts with on the right (a count, its own AI action).
 * Optional sections say so; `done` marks a section already answered. The track
 * above the page carries the order, so sections are not numbered
 * (research-lane-redesign); `n` stays for callers and is not drawn.
 */
export function StepSection({
  id, title, hint, optional = false, done = false, lead = false, aside, children,
}: {
  id?: string;
  n?: number;
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
  return (
    <section id={id} aria-labelledby={headingId} className={`scroll-mt-40 rounded-card border border-border bg-surface-raised ${FOCUS}`}>
      <div className={`flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 ${children ? "border-b border-border" : ""}`}>
        {done ? (
          <span aria-hidden="true" className="inline-flex size-[18px] shrink-0 items-center justify-center rounded-full bg-status-done text-surface-raised">
            <Icon name="done" size={10} />
          </span>
        ) : null}
        <div className="min-w-0 flex-1 basis-48">
          <h2 id={headingId} className={`font-semibold ${lead ? "text-base leading-6" : "text-[15px] leading-[22px]"}`}>
            {title}
            {optional ? <span className="text-xs font-normal text-ink-faint"> · {t("research.step.optional")}</span> : null}
          </h2>
          {hint ? <p className="text-xs leading-4 text-ink-muted">{hint}</p> : null}
        </div>
        {aside ? <div className="max-w-full">{aside}</div> : null}
      </div>
      {children ? <div className="px-4 pb-4 pt-3.5">{children}</div> : null}
    </section>
  );
}

/**
 * The step's dock, in the page's flow (never over an input): the way back on the left, why the step is or is not
 * ready in the middle, the one primary action on the right. It replaces each
 * step's bottom row; the action keeps the conditions it had there.
 */
/** The frame's next stage, as a stage's forward action names and opens it. */
export type FrameNext = { label: string; go: () => void };

/**
 * Set inside a frame whose own navigator names the neighbouring stages (the research workbench,
 * whose stages and their order are lib/workbench-stages.ts); null outside. A dock there leaves its
 * back link out: the classic flow's "4. Audience" names a step the workbench calls otherwise, in
 * another order. A stage's forward action reads `next`: the stage after it in the frame's order,
 * with its label, opened by the frame (its route or hash, its leave guard, the focus moved to the
 * new stage's heading), never by the stage itself. `next` is null on the last stage.
 */
export const FrameNavigation = createContext<{ next: FrameNext | null } | null>(null);

export function ActionDock({ back, note, ready = true, children }: {
  back?: { href: string; label: string };
  note?: ReactNode;
  /** false: the note is a reason the step is not ready yet. */
  ready?: boolean;
  children: ReactNode;
}) {
  const framed = useContext(FrameNavigation) !== null;
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface-raised px-3 py-2.5">
      {back && !framed ? (
        <Link href={back.href} className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-sm text-sm text-ink-muted no-underline hover:text-ink ${TOUCH} ${FOCUS}`}>
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

/**
 * A small segmented control: one of a few views or modes. One Tab stop; the arrows move and
 * choose, as radios do (input-interactions I11, roving tabindex).
 */
export function Segmented<K extends string>({ value, options, onChange, label }: {
  value: K;
  options: readonly { key: K; label: ReactNode }[];
  onChange: (key: K) => void;
  label: string;
}) {
  const group = useRef<HTMLDivElement>(null);
  const stop = tabStop(options.length, options.findIndex((o) => o.key === value));
  const onKey = (i: number) => (e: KeyboardEvent<HTMLButtonElement>) => {
    const next = rovingIndex(i, e.key, options.length);
    if (next === null) return;
    e.preventDefault();
    group.current?.querySelectorAll<HTMLButtonElement>("[role=radio]")[next]?.focus();
    onChange(options[next].key);
  };
  return (
    <div ref={group} role="radiogroup" aria-label={label} className="inline-flex gap-0.5 rounded-card bg-surface-sunken p-[3px]">
      {options.map((o, i) => {
        const on = o.key === value;
        return (
          <button
            key={o.key}
            type="button"
            role="radio"
            aria-checked={on}
            tabIndex={i === stop ? 0 : -1}
            onKeyDown={onKey(i)}
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
 * With `rename`, each value is reworded in its place (I1), keeping the order; `rename.label` names
 * one ("Položka" -> "Položka · 2").
 */
export function ChipInput({ values, onAdd, onRemove, rename, label, placeholder, backspaceRemoves = false, disabled = false, refuse }: {
  values: readonly string[];
  onAdd: (value: string) => void;
  onRemove: (index: number) => void;
  rename?: { label: string; onRename: (index: number, value: string) => void };
  label: string;
  placeholder?: string;
  backspaceRemoves?: boolean;
  disabled?: boolean;
  /**
   * Why a typed value is not one, or null (input-interactions I9): a refused value stays in the
   * field with the reason beside it, never added and never cleared; the reason goes once the
   * text changes. A rename asks it with the value's own index, which it does not repeat.
   */
  refuse?: (value: string, index?: number) => string | null;
}) {
  const [draft, setDraft] = useState("");
  const [refusal, setRefusal] = useState<string | null>(null);
  // A reason shown only while it still holds: a refusal that depends on the list (a full set)
  // goes when the list changes, not only when the text does.
  const shown = refusal !== null && refuse?.(draft.trim()) ? refusal : null;
  const errorId = useId();
  const key = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const v = draft.trim();
      if (!v) return setDraft("");
      const why = refuse?.(v) ?? null;
      if (why) return setRefusal(why);
      onAdd(v);
      setDraft("");
      setRefusal(null);
    } else if (e.key === "Backspace" && backspaceRemoves && !draft && values.length) {
      onRemove(values.length - 1);
    }
  };
  return (
    <div className="flex flex-col gap-1">
    <div data-chips className={`flex min-h-9 flex-wrap items-center gap-1.5 rounded-control border bg-surface-raised px-2 py-1 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus-ring ${shown ? "border-status-fault" : "border-border-strong"}`}>
      {values.map((v, i) => (
        <span key={`${i}-${v}`} className="inline-flex max-w-full items-center gap-1 rounded-md border border-border bg-surface px-2 py-0.5 text-[13px] leading-5">
          {rename ? (
            <InlineText
              value={v}
              label={tv("research.step.chip", { label: rename.label, n: i + 1 })}
              disabled={disabled}
              rules={{ validate: (next) => refuse?.(next, i) ?? null }}
              className="min-w-0"
              onCommit={(next) => rename.onRename(i, next)}
            />
          ) : (
            <span className="min-w-0 break-words">{v}</span>
          )}
          <button disabled={disabled} type="button" aria-label={`${t("research.step.remove")} ${v}`} onClick={() => onRemove(i)} className={`-my-1 -mr-1.5 inline-flex size-6 shrink-0 items-center justify-center rounded-sm text-ink-faint hover:text-ink ${FOCUS}`}>
            ×
          </button>
        </span>
      ))}
      <input
        aria-label={label} disabled={disabled}
        placeholder={placeholder}
        value={draft}
        aria-invalid={shown ? true : undefined}
        aria-describedby={shown ? errorId : undefined}
        onChange={(e) => {
          setDraft(e.target.value);
          setRefusal(null);
        }}
        onKeyDown={key}
        className="min-h-7 min-w-32 flex-1 border-0 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
      />
    </div>
    {shown ? <span id={errorId} role="alert" className="text-xs text-status-fault">{shown}</span> : null}
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
