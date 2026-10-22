"use client";

// I1: a value the screen shows is edited where it is shown. Click it, or focus it and press
// Enter/F2, and it becomes a field of the same size in the same spot; Enter saves (Ctrl/Cmd+Enter
// in multi-line text), blur saves, Esc restores. The pencil shows on hover and on focus (touch has
// no hover). The save state sits beside the value: Ukládám… / Uloženo / Neuloženo – Zkusit znovu.
// A refused draft is said at the field and stays in it (I9). Reference: `Item`,
// prototypes/research-lead-v2/src/components/ui.tsx:52.

import { type KeyboardEvent, type MouseEvent, type RefObject, useEffect, useId, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type SaveState, type TextRules, editKeyAction, isThenable, opensEdit, readDraft } from "@/lib/inline-edit";
import { Icon } from "../rehome/icons";
import { EDIT_FIELD, FIELD_ERROR, FOCUS, SaveNote } from "./parts";

const SAVED_MS = 3000;
/** How long a selectable value waits for a second click before a click opens it. */
export const SELECT_SETTLE_MS = 300;

export function InlineText({
  value, onCommit, label, multiline = false, placeholder, disabled = false, disabledReason, rules, autoOpen = false, onSettled, selectable = false, className = "",
}: {
  value: string;
  /** Saves the new value. A returned promise drives the save state; a rejection is "Neuloženo". */
  onCommit: (value: string) => void | PromiseLike<unknown>;
  /** What the value is ("Název studie"): the field's accessible name. */
  label: string;
  multiline?: boolean;
  /** Shown when the value is empty. */
  placeholder?: string;
  disabled?: boolean;
  /** Why it cannot be edited now ("zmrazeno během běhu"), said beside it. */
  disabledReason?: string;
  rules?: TextRules;
  /**
   * The value's words can be selected (to quote a part of them, a comment on Návrh): drawn as a
   * focusable role="button" span, since a browser selects no text inside a <button>. A single click
   * that leaves nothing selected opens the field (after SELECT_SETTLE_MS, so a double-click selects a
   * word instead); Enter, F2 and Space open it at once. Disabled, it is the words alone, no focus.
   */
  selectable?: boolean;
  /**
   * Opens in place as it mounts: a rename asked for from somewhere else (a row's menu, F2 on a
   * row whose own click does something else), where the caller swaps its row for this field.
   */
  autoOpen?: boolean;
  /**
   * Called once the value is at rest after it was opened: closed by Esc or by a commit that sent
   * nothing, or its save answered. Never while a save is in flight or after one failed, so a caller
   * that swaps this field back for its row keeps "Neuloženo – Zkusit znovu" on screen until it went.
   */
  onSettled?: () => void;
  className?: string;
}) {
  const [draft, setDraft] = useState<string | null>(() => (autoOpen && !disabled ? value : null));
  const [problem, setProblem] = useState<string | null>(null);
  // Once a draft was refused, it is checked as it is typed (I9: from the first blur, then live).
  const [checked, setChecked] = useState(false);
  const [save, setSave] = useState<SaveState>("idle");
  // The newest save's value while it is in flight: shown, opened and compared against, so a revert
  // typed meanwhile is sent and is not lost behind it (review of #532, P2-1).
  const [pending, setPending] = useState<string | null>(null);
  // The value whose save failed: shown, so nothing typed is lost, and "Zkusit znovu" resends it.
  const [failed, setFailed] = useState<string | null>(null);
  const current = pending ?? failed ?? value;
  const actionId = useId();
  const textId = useId();
  const shown = useRef<HTMLElement>(null);
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Set once the field is closed, so the blur that follows an Enter or an Esc saves nothing twice.
  const settled = useRef(false);
  const errorId = useId();
  const editing = draft !== null;

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
    if (clickTimer.current) clearTimeout(clickTimer.current);
  }, []);

  // At rest after an opening: the caller is told once per opening (autoOpen counts as one).
  const opened = useRef(autoOpen && !disabled);
  const settledNote = useRef(onSettled);
  useEffect(() => {
    settledNote.current = onSettled;
  }, [onSettled]);
  useEffect(() => {
    if (!opened.current || editing || pending !== null || failed !== null || save === "saving") return;
    opened.current = false;
    settledNote.current?.();
  }, [editing, pending, failed, save]);

  const open = () => {
    if (disabled) return;
    opened.current = true;
    settled.current = false;
    setDraft(current);
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

  // Each save is numbered; only the newest one's answer may set the state. An older save that
  // answers late says nothing about the value on screen (Codex on #532).
  const latest = useRef(0);
  const fail = (next: string) => {
    setPending(null);
    setFailed(next);
    setSave("failed");
  };
  const send = (next: string) => {
    const op = ++latest.current;
    setFailed(null);
    if (timer.current) clearTimeout(timer.current);
    let result: unknown;
    try {
      result = onCommit(next);
    } catch {
      fail(next);
      return;
    }
    if (!isThenable(result)) {
      setPending(null);
      setSave("idle");
      return;
    }
    setPending(next);
    setSave("saving");
    result.then(
      () => {
        if (op !== latest.current) return;
        setPending(null);
        setSave("saved");
        timer.current = setTimeout(() => setSave("idle"), SAVED_MS);
      },
      () => {
        if (op === latest.current) fail(next);
      },
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
    if (pending !== null) {
      // A save is in flight: anything but its own value, the stored one included, is a new save.
      if (read.value !== pending) send(read.value);
    } else if (read.value !== value) {
      send(read.value);
    } else if (failed !== null) {
      // Back to the stored value after a failed save: nothing to send, and nothing failed any more
      // (review of #532, P2-2). Any late answer of the failed save is ignored.
      latest.current++;
      setFailed(null);
      setSave("idle");
    }
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

  const text = current;
  const look = `group inline-flex min-h-8 min-w-0 max-w-full items-baseline gap-1.5 rounded-sm px-1 -mx-1 text-left ${multiline ? "whitespace-pre-wrap" : ""} hover:bg-surface-sunken disabled:cursor-default disabled:hover:bg-transparent ${FOCUS}`;
  const words = (
    <>
      <span id={textId} className={`min-w-0 break-words underline decoration-transparent decoration-dotted underline-offset-4 group-hover:decoration-border-strong group-focus-visible:decoration-border-strong ${text ? "" : "text-ink-faint"}`}>
        {text || placeholder || t("input.empty")}
      </span>
      {disabled ? null : (
        <span aria-hidden="true" className="self-center text-ink-faint opacity-0 transition-opacity duration-[var(--duration-confirm)] group-hover:opacity-100 group-focus-visible:opacity-100">
          <Icon name="pencil" size={12} />
        </span>
      )}
    </>
  );
  // Enter would also click; taking it here opens the field once, as F2 does. A span drawn as a
  // button answers Space as a <button> would.
  const onShownKey = (e: KeyboardEvent<HTMLElement>) => {
    if (opensEdit(e.key) || (selectable && e.key === " ")) {
      e.preventDefault();
      open();
    }
  };
  // A selectable value opens once a single click has settled with nothing selected in it: the first
  // click of a double-click (a word being selected) or the click that ends a drag opens nothing.
  const onSelectableClick = (e: MouseEvent<HTMLElement>) => {
    if (clickTimer.current) clearTimeout(clickTimer.current);
    clickTimer.current = null;
    if (e.detail > 1) return;
    const el = e.currentTarget;
    clickTimer.current = setTimeout(() => {
      clickTimer.current = null;
      if (!selectedWithin(el)) open();
    }, SELECT_SETTLE_MS);
  };
  return (
    <span className={`inline-flex min-w-0 max-w-full flex-wrap items-baseline gap-x-2 gap-y-1 ${className}`}>
      {/* The button's name is the action and the value it shows: "Upravit: Název studie Ranní
          pečivo", never the action alone (review of #532). */}
      {/* Never part of a selection of the words: a quote is what the reader sees. */}
      <span id={actionId} className="sr-only select-none">{tv("input.edit", { label })}</span>
      {!selectable ? (
        <button ref={shown as RefObject<HTMLButtonElement>} type="button" disabled={disabled} aria-labelledby={`${actionId} ${textId}`} onClick={open} onKeyDown={onShownKey} className={look}>
          {words}
        </button>
      ) : disabled ? (
        // Nothing to open: the words alone, selectable, taking no focus.
        <span className={`${look} select-text`}>{words}</span>
      ) : (
        <span ref={shown as RefObject<HTMLSpanElement>} role="button" tabIndex={0} aria-labelledby={`${actionId} ${textId}`} onClick={onSelectableClick} onKeyDown={onShownKey} className={`${look} cursor-text select-text`}>
          {words}
        </span>
      )}
      {disabled && disabledReason ? <span className="text-xs text-ink-faint">{disabledReason}</span> : null}
      <SaveNote state={save} onRetry={failed !== null ? () => send(failed) : undefined} />
    </span>
  );
}

/** Whether the page's selection holds words inside `el` (a drag over the value, not a plain click). */
function selectedWithin(el: HTMLElement): boolean {
  const s = window.getSelection();
  return !!s && !s.isCollapsed && s.toString().trim() !== "" && !!s.anchorNode && el.contains(s.anchorNode);
}
