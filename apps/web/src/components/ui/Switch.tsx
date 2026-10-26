"use client";

// I4: an on/off choice is a switch, changed where it is shown, never a select of "ano/ne". A press
// reports the other state; the caller saves it and says what happened (Uloženo beside it, or Vrátit
// for a reversible change). Its name is its label, shown beside the track or only to assistive
// technology when the row already says what it switches.

import { FOCUS } from "./parts";

export function Switch({ on, onChange, label, showLabel = false, disabled = false, className = "" }: {
  on: boolean;
  onChange: (on: boolean) => void;
  /** What it switches ("Štítek Metodik"): its accessible name. */
  label: string;
  /** Show the label beside the track (else it is the name alone). */
  showLabel?: boolean;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={showLabel ? undefined : label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`inline-flex shrink-0 items-center gap-2 rounded-sm px-1 text-sm text-ink-muted hover:text-ink disabled:cursor-not-allowed disabled:opacity-60 ${FOCUS} ${className}`}
    >
      <span aria-hidden="true" className={`relative inline-block h-5 w-[34px] shrink-0 rounded-pill transition-colors ${on ? "bg-signal" : "bg-border-strong"}`}>
        <i className={`absolute top-0.5 block size-4 rounded-full bg-surface-raised transition-[left] ${on ? "left-4" : "left-0.5"}`} />
      </span>
      {showLabel ? label : null}
    </button>
  );
}
