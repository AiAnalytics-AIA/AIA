"use client";

// I2: a bounded number is a stepper. `− [value] +`, the value typeable, its bounds stated beside
// it, ↑/↓ or − / + by one step and Shift by ten, the buttons disabled at the bound. A typed value
// is saved on Enter or blur only when it is a number within the bounds; otherwise the field says
// why, in words, and nothing is saved -- never clamped, never replaced (audit IA-1, IA-2). Esc
// restores the saved value. Money passes `unit="USD"` and whole-dollar steps.

import { type KeyboardEvent, type ReactNode, useId, useRef, useState } from "react";

import { tv, t } from "@/i18n/t";
import type { SaveState } from "@/lib/inline-edit";
import { type NumberBounds, canStep, formatNumber, numberProblemWords, rangeWords, readNumber, stepNumber } from "@/lib/number-input";
import { Icon } from "../rehome/icons";
import { FIELD_ERROR, FOCUS, SaveNote } from "./parts";

export function Stepper({
  value, onCommit, onProblem, label, min, max, step = 1, decimals = 0, unit, disabled = false, showBounds = true, note, className = "",
}: {
  /** The saved value; null when none is set yet (the field is empty until one is chosen). */
  value: number | null;
  /**
   * Saves a value. Return a promise to have the stepper wait for the answer (Ukládám… while it
   * is pending, Neuloženo – Zkusit znovu when it rejects); return nothing for a value kept at once.
   */
  onCommit: (value: number) => void | Promise<unknown>;
  /**
   * Told when the field holds a refused value (the words) and when it no longer does (null): what
   * is typed there is then not the saved value, and an action beside it must not act on either.
   */
  onProblem?: (problem: string | null) => void;
  /** What the number is ("Počet respondentů"): the field's accessible name. */
  label: string;
  min: number;
  max: number;
  step?: number;
  /** Decimal places a value may carry (0: whole numbers). */
  decimals?: number;
  /** Shown beside the value and in the bounds ("USD"). */
  unit?: string;
  disabled?: boolean;
  /** false: the caller states the bounds elsewhere (they are still in the field's description). */
  showBounds?: boolean;
  /** A line under the field (a recommendation, a save state); an error takes its place. */
  note?: ReactNode;
  className?: string;
}) {
  const bounds: NumberBounds = { min, max, step, decimals };
  const [draft, setDraft] = useState<string | null>(null);
  // I9: an error is shown from the first refused commit, then checked live as the person types.
  const [problem, setShownProblem] = useState<string | null>(null);
  const setProblem = (next: string | null) => {
    setShownProblem(next);
    if (next !== problem) onProblem?.(next);
  };
  // True from a refused commit until the field holds the saved value again: typing is checked live.
  const [checked, setChecked] = useState(false);
  const settle = () => {
    setDraft(null);
    setProblem(null);
    setChecked(false);
  };
  // The caller's answer to a save, explicitly (Codex on #532: equality of `value` cannot tell
  // "still saving" from "answered with the same value"). An onCommit that returns a promise is
  // pending until it settles: meanwhile the field shows and steps from what was sent, so a second
  // press does not step from the stale prop. Resolved, `value` is the truth again; rejected, the
  // field goes back to `value` and says Neuloženo, with the failed value to resend. A synchronous
  // onCommit keeps no optimistic state at all. Only the newest save's answer counts.
  const [sent, setSent] = useState<number | null>(null);
  const [save, setSave] = useState<SaveState>("idle");
  const [failed, setFailed] = useState<number | null>(null);
  const latest = useRef(0);
  const saved = sent ?? value;
  const commit = (next: number) => {
    if (next === saved) return;
    const op = ++latest.current;
    const result = onCommit(next);
    if (!(result instanceof Promise)) {
      setSent(null);
      setSave("idle");
      return;
    }
    setSent(next);
    setSave("saving");
    result.then(
      () => {
        if (op !== latest.current) return;
        setSent(null);
        setSave("idle");
      },
      () => {
        if (op !== latest.current) return;
        setSent(null);
        setFailed(next);
        setSave("failed");
      },
    );
  };
  const errorId = useId();
  const boundsId = useId();
  // The bounds carry the unit: they are the field's description, and a screen reader hears them
  // apart from the unit drawn beside the value (Codex on #532).
  const range = rangeWords(bounds, unit);
  const shownValue = draft ?? (saved === null ? "" : formatNumber(saved, decimals > 0 ? decimals : undefined));

  const commitDraft = (): boolean => {
    if (draft === null) return true;
    const read = readNumber(draft, bounds);
    if (!read.ok) {
      setProblem(numberProblemWords(read.problem, bounds, unit));
      setChecked(true);
      return false;
    }
    settle();
    commit(read.value);
    return true;
  };

  // The base a press moves from: a valid draft (what the person sees), else what was saved.
  const base = (): number | null => {
    if (draft !== null) {
      const read = readNumber(draft, { ...bounds, min: -Infinity, max: Infinity });
      if (read.ok) return read.value;
    }
    return saved;
  };
  // One press, one commit: the step from the draft. The draft itself is not committed first.
  const press = (direction: 1 | -1, big: boolean) => {
    const next = stepNumber(base(), direction, bounds, big);
    if (next === null) return;
    settle();
    commit(next);
  };

  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      press(e.key === "ArrowUp" ? 1 : -1, e.shiftKey);
    } else if (e.key === "Enter") {
      e.preventDefault();
      commitDraft();
    } else if (e.key === "Escape" && draft !== null) {
      e.preventDefault();
      settle();
    }
  };

  const current = base();
  // What the field holds now, for assistive technology: a draft is announced as itself when it is a
  // valid value, and not at all when it is not -- never the saved value behind it (Codex on #532).
  // aria-invalid follows the draft as it is typed; the words come with the first refused commit (I9).
  const reading = draft === null ? null : readNumber(draft, bounds);
  const announced = reading === null ? saved : reading.ok ? reading.value : null;
  const invalid = problem !== null || (reading !== null && !reading.ok);
  // The buttons are for the pointer; the keyboard has the same moves on the field itself (↑ ↓,
  // Shift ×10), so the stepper is one Tab stop (the ARIA spin button pattern).
  const button = (direction: 1 | -1) => (
    <button
      type="button"
      tabIndex={-1}
      disabled={disabled || !canStep(current, direction, bounds)}
      aria-label={tv(direction > 0 ? "input.increase" : "input.decrease", { label })}
      // Pressing a button must not take the focus from the field: its blur would commit the draft,
      // and the click would then commit again (Codex on #532). The press steps from the draft.
      onMouseDown={(e) => e.preventDefault()}
      onClick={(e) => press(direction, e.shiftKey)}
      className={`inline-flex size-11 shrink-0 items-center justify-center text-ink-muted hover:bg-surface-sunken hover:text-ink disabled:opacity-40 disabled:hover:bg-transparent sm:size-8 ${FOCUS}`}
    >
      <Icon name={direction > 0 ? "plus" : "minus"} size={14} />
    </button>
  );

  return (
    <span className={`inline-flex min-w-0 flex-col gap-1 ${className}`}>
      <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
        <span
          className={`inline-flex items-stretch overflow-hidden rounded-control border focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus-ring ${problem ? FIELD_ERROR : "border-border-strong bg-surface-raised"}`}
        >
          {button(-1)}
          <input
            role="spinbutton"
            inputMode={decimals > 0 ? "decimal" : "numeric"}
            aria-label={label}
            aria-valuemin={min}
            aria-valuemax={max}
            aria-valuenow={announced ?? undefined}
            aria-valuetext={announced !== null && unit ? `${formatNumber(announced, decimals > 0 ? decimals : undefined)} ${unit}` : undefined}
            aria-invalid={invalid ? true : undefined}
            aria-describedby={problem ? `${errorId} ${boundsId}` : boundsId}
            disabled={disabled}
            value={shownValue}
            onChange={(e) => {
              setDraft(e.target.value);
              if (checked) {
                const read = readNumber(e.target.value, bounds);
                setProblem(read.ok ? null : numberProblemWords(read.problem, bounds, unit));
              }
            }}
            onKeyDown={onKey}
            onBlur={() => commitDraft()}
            className="w-[7ch] min-w-0 border-x border-border bg-transparent px-1 text-center text-sm tabular-nums text-ink outline-none disabled:text-ink-faint"
          />
          {button(1)}
        </span>
        {unit ? <span className="text-sm text-ink-muted">{unit}</span> : null}
        <span id={boundsId} className={showBounds ? "text-xs text-ink-faint" : "sr-only"}>
          {range} · {t("input.stepHint")}
        </span>
        <SaveNote state={save} onRetry={failed !== null ? () => commit(failed) : undefined} />
      </span>
      {problem ? (
        <span id={errorId} role="alert" className="text-xs leading-4 text-status-fault">{problem}</span>
      ) : note ? (
        <span className="text-xs leading-4 text-ink-muted">{note}</span>
      ) : null}
    </span>
  );
}
