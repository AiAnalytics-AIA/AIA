"use client";

// I3: a known set is chosen, never typed. One of a few short values, or several of a small set,
// as chips that wrap (at phone width a segmented control over three options becomes these, I11).
// The group is one Tab stop; the arrows move within it (roving tabindex). Single choice is a radio
// group whose arrows choose as they move, as radios do; multiple choice is a group of toggles whose
// arrows only move and Space/Enter toggle.
// `look="segmented"` draws the same control as the prototype's segmented bar (Settings, v51): one
// bordered bar, the chosen segment filled with the signal; still a touch target on a phone.

import { type KeyboardEvent, type ReactNode, useRef } from "react";

import { rovingIndex, tabStop } from "@/lib/roving";
import { FOCUS, TOUCH } from "./parts";

export type Choice<K extends string> = { key: K; label: ReactNode; disabled?: boolean };

// onChange reports a choice and awaits nothing: a caller that saves on it owns the save's errors
// and says them (with SaveNote beside the chips, or at the field). Its return value is ignored.
type Common<K extends string> = {
  options: readonly Choice<K>[];
  /** The group's accessible name ("Věková skupina"). */
  label: string;
  disabled?: boolean;
  className?: string;
  /** Chips that wrap (the default), or one segmented bar; `small` the bar's dense row size. */
  look?: "chips" | "segmented";
  small?: boolean;
};

export function ChoiceChips<K extends string>(
  props: Common<K> & ({ multiple?: false; value: K | null; onChange: (key: K) => void } | { multiple: true; value: readonly K[]; onChange: (keys: K[]) => void }),
) {
  const { options, label, disabled = false, className = "", look = "chips", small = false } = props;
  const segmented = look === "segmented";
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const off = (i: number) => disabled || !!options[i]?.disabled;
  const isOn = (k: K) => (props.multiple ? props.value.includes(k) : props.value === k);
  const chosen = options.findIndex((o) => isOn(o.key));
  const stop = tabStop(options.length, chosen, off);

  const choose = (k: K) => {
    if (props.multiple) {
      const has = props.value.includes(k);
      // In the options' order, whatever order they were picked in.
      props.onChange(options.map((o) => o.key).filter((key) => (key === k ? !has : props.value.includes(key))));
    } else if (props.value !== k) {
      props.onChange(k);
    }
  };

  const onKey = (i: number) => (e: KeyboardEvent<HTMLButtonElement>) => {
    const next = rovingIndex(i, e.key, options.length, off);
    if (next === null) return;
    e.preventDefault();
    refs.current[next]?.focus();
    if (!props.multiple) choose(options[next].key);
  };

  return (
    <div role={props.multiple ? "group" : "radiogroup"} aria-label={label} data-look={look}
      // A full-size bar on a phone is a list, one segment a row: a long one (Správa dat's clients)
      // wrapped into a ragged bar otherwise. A small bar (a table cell's) stays a row and wraps.
      className={`${segmented ? `max-w-full overflow-hidden rounded-[6px] border border-border-strong bg-surface-raised ${small ? "inline-flex flex-wrap" : "flex flex-col sm:inline-flex sm:flex-row sm:flex-wrap"}` : "flex flex-wrap gap-1.5"} ${className}`}>
      {options.map((o, i) => {
        const on = isOn(o.key);
        return (
          <button
            key={o.key}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role={props.multiple ? undefined : "radio"}
            aria-checked={props.multiple ? undefined : on}
            aria-pressed={props.multiple ? on : undefined}
            disabled={off(i)}
            tabIndex={i === stop ? 0 : -1}
            onClick={() => choose(o.key)}
            onKeyDown={onKey(i)}
            // data-dense: the bar keeps its own height where a page enlarges every button (Settings).
            data-dense={segmented ? "" : undefined}
            className={segmented
              // A full-size bar's labels wrap (a client's name may be long, review of #870); a small
              // bar holds fixed short choices and stays on one line.
              ? `inline-flex min-h-11 min-w-0 items-center border-border px-2.5 text-left text-xs last:border-0 ${small ? "whitespace-nowrap border-r" : "break-words py-1.5 border-b sm:border-b-0 sm:border-r [overflow-wrap:anywhere]"} disabled:cursor-not-allowed disabled:opacity-50 focus-visible:relative focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring ${small ? "sm:min-h-7 sm:px-2" : "sm:min-h-8"} ${
                on ? "bg-signal text-on-signal" : "text-ink hover:bg-surface-sunken"
              }`
              : `inline-flex ${TOUCH} items-center gap-1.5 rounded-pill border px-3 text-[13px] transition-colors duration-[var(--duration-confirm)] disabled:opacity-50 ${FOCUS} ${
              on ? "border-signal bg-signal-wash font-semibold text-signal" : "border-border bg-surface-raised text-ink hover:border-border-strong"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
