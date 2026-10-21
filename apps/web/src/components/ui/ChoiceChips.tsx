"use client";

// I3: a known set is chosen, never typed. One of a few short values, or several of a small set,
// as chips that wrap (at phone width a segmented control over three options becomes these, I11).
// The group is one Tab stop; the arrows move within it (roving tabindex). Single choice is a radio
// group whose arrows choose as they move, as radios do; multiple choice is a group of toggles whose
// arrows only move and Space/Enter toggle.

import { type KeyboardEvent, type ReactNode, useRef } from "react";

import { rovingIndex, tabStop } from "@/lib/roving";
import { FOCUS, TOUCH } from "./parts";

export type Choice<K extends string> = { key: K; label: ReactNode; disabled?: boolean };

type Common<K extends string> = {
  options: readonly Choice<K>[];
  /** The group's accessible name ("Věková skupina"). */
  label: string;
  disabled?: boolean;
  className?: string;
};

export function ChoiceChips<K extends string>(
  props: Common<K> & ({ multiple?: false; value: K | null; onChange: (key: K) => void } | { multiple: true; value: readonly K[]; onChange: (keys: K[]) => void }),
) {
  const { options, label, disabled = false, className = "" } = props;
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
    <div role={props.multiple ? "group" : "radiogroup"} aria-label={label} className={`flex flex-wrap gap-1.5 ${className}`}>
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
            className={`inline-flex ${TOUCH} items-center gap-1.5 rounded-pill border px-3 text-[13px] transition-colors duration-[var(--duration-confirm)] disabled:opacity-50 ${FOCUS} ${
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
