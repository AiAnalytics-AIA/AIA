"use client";

// I1: a value the screen shows is edited where it is shown. Click it, or focus it and press
// Enter/F2, and it becomes a field of the same size in the same spot; Enter saves (Ctrl/Cmd+Enter
// in multi-line text), blur saves, Esc restores. The pencil shows on hover and on focus (touch has
// no hover). The save state sits beside the value: Ukládám… / Uloženo / Neuloženo – Zkusit znovu.
// A refused draft is said at the field and stays in it (I9). Reference: `Item`,
// prototypes/research-lead-v2/src/components/ui.tsx:52.

import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type SaveState, type TextRules, editKeyAction, opensEdit, readDraft } from "@/lib/inline-edit";
import { Icon } from "../rehome/icons";
import { EDIT_FIELD, FIELD_ERROR, FOCUS, SaveNote } from "./parts";

const SAVED_MS = 3000;

export function InlineText({
  value, onCommit, label, multiline = false, placeholder, disabled = false, disabledReason, rules, className = "",
}: {
  value: string;
  /** Saves the new value. A returned promise drives the save state; a rejection is "Neuloženo". */
  onCommit: (value: string) => void | Promise<unknown>;
  /** What the value is ("Název studie"): the field's accessible name. */
  label: string;
  multiline?: boolean;
  /** Shown when the value is empty. */
  placeholder?: string;
  disabled?: boolean;
  /** Why it cannot be edited now ("zmrazeno během běhu"), said beside it. */
  disabledReason?: string;
  rules?: TextRules;
  className?: string;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  // Once a draft was refused, it is checked as it is typed (I9: from the first blur, then live).
  const [checked, setChecked] = useState(false);
  const [save, setSave] = useState<SaveState>("idle");
  // What was last sent: on a failure it is shown, so nothing typed is lost, and "Zkusit znovu" resends it.
  const [sent, setSent] = useState<string | null>(null);
  const shown = useRef<HTMLButtonElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Set once the field is closed, so the blur that follows an Enter or an Esc saves nothing twice.
  const settled = useRef(false);
  const errorId = useId();
  const editing = draft !== null;

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const open = () => {
    if (disabled) return;
    settled.current = false;
    setDraft(save === "failed" && sent !== null ? sent : value);
    setProblem(null);
    setChecked(false);
  };
  const close = (refocus: boolean) => {
    settled.current = true;
    setDraft(null);
    setProblem(null);
    setChecked(false);
    if (refocus) requestAnimationFrame(() => shown.current?.focus());
  };

  const send = (next: string) => {
    setSent(next);
    if (timer.current) clearTimeout(timer.current);
    let result: void | Promise<unknown>;
    try {
      result = onCommit(next);
    } catch {
      setSave("failed");
      return;
    }
    if (!(result instanceof Promise)) {
      setSave("idle");
      return;
    }
    setSave("saving");
    result.then(
      () => {
        setSave("saved");
        timer.current = setTimeout(() => setSave("idle"), SAVED_MS);
      },
      () => setSave("failed"),
    );
  };

  const commit = (refocus: boolean) => {
    if (draft === null || settled.current) return;
    const read = readDraft(draft, multiline, rules);
    if (read.problem) {
      setProblem(read.problem);
      setChecked(true);
      return;
    }
    if (read.value !== value) send(read.value);
    close(refocus);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const action = editKeyAction(e, multiline);
    if (action === "cancel") {
      e.preventDefault();
      close(true);
    } else if (action === "commit") {
      e.preventDefault();
      commit(true);
    }
  };

  const change = (next: string) => {
    setDraft(next);
    if (checked) setProblem(readDraft(next, multiline, rules).problem);
  };

  if (editing) {
    const common = {
      "aria-label": label,
      "aria-invalid": problem ? true : undefined,
      "aria-describedby": problem ? errorId : undefined,
      autoFocus: true,
      value: draft,
      onFocus: (e: { currentTarget: HTMLInputElement | HTMLTextAreaElement }) => e.currentTarget.select(),
      onKeyDown: onKey,
      onBlur: () => commit(false),
      className: `${EDIT_FIELD} ${problem ? FIELD_ERROR : ""} w-full`,
    };
    return (
      <span className={`flex min-w-0 flex-col gap-1 ${className}`}>
        {multiline ? (
          <textarea {...common} rows={3} onChange={(e) => change(e.target.value)} />
        ) : (
          <input {...common} onChange={(e) => change(e.target.value)} />
        )}
        {problem ? (
          <span id={errorId} className="text-xs leading-4 text-status-fault">{problem}</span>
        ) : (
          <span className="text-xs leading-4 text-ink-faint">{t(multiline ? "input.editHintMulti" : "input.editHint")}</span>
        )}
      </span>
    );
  }

  const text = save === "failed" && sent !== null ? sent : value;
  return (
    <span className={`inline-flex min-w-0 max-w-full flex-wrap items-baseline gap-x-2 gap-y-1 ${className}`}>
      <button
        ref={shown}
        type="button"
        disabled={disabled}
        aria-label={tv("input.edit", { label })}
        onClick={open}
        onKeyDown={(e) => {
          // Enter would also click; taking it here opens the field once, as F2 does.
          if (opensEdit(e.key)) {
            e.preventDefault();
            open();
          }
        }}
        className={`group inline-flex min-h-8 min-w-0 max-w-full items-baseline gap-1.5 rounded-sm px-1 -mx-1 text-left ${multiline ? "whitespace-pre-wrap" : ""} hover:bg-surface-sunken disabled:cursor-default disabled:hover:bg-transparent ${FOCUS}`}
      >
        <span className={`min-w-0 break-words underline decoration-transparent decoration-dotted underline-offset-4 group-hover:decoration-border-strong group-focus-visible:decoration-border-strong ${text ? "" : "text-ink-faint"}`}>
          {text || placeholder || t("input.empty")}
        </span>
        {disabled ? null : (
          <span aria-hidden="true" className="self-center text-ink-faint opacity-0 transition-opacity duration-[var(--duration-confirm)] group-hover:opacity-100 group-focus-visible:opacity-100">
            <Icon name="pencil" size={12} />
          </span>
        )}
      </button>
      {disabled && disabledReason ? <span className="text-xs text-ink-faint">{disabledReason}</span> : null}
      <SaveNote state={save} onRetry={sent !== null ? () => send(sent) : undefined} />
    </span>
  );
}
