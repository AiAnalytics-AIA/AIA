"use client";

// What the input standard's controls share (input-interactions, Tokens): an editing field on
// surface-raised with border-strong, focus in focus-ring, an error at the field in status-fault on
// status-fault-wash, state changes at duration-confirm. Token utilities only, as in rehome/ui.tsx.

import { type RefObject, useEffect } from "react";

import { t } from "@/i18n/t";
import type { SaveState } from "@/lib/inline-edit";

/** A popover on z-overlay (a menu, the swatches), anchored under its trigger: no side yet. */
const POPOVER_AT = "absolute top-full z-[var(--z-overlay)] mt-1 rounded-md border border-border bg-surface-overlay p-1 shadow-[var(--shadow-overlay)]";
/** A popover under its trigger, opening rightwards from its left edge. */
export const POPOVER = `${POPOVER_AT} left-0`;
/** A popover under its trigger, opening leftwards from its right edge (a trigger at a row's end). */
export const POPOVER_END = `${POPOVER_AT} right-0`;

/**
 * Closes an open popover on a press outside `box` or on Esc, and gives focus back to its trigger
 * (I11: focus returns to the trigger after cancel).
 */
export function useDismiss(open: boolean, close: () => void, box: RefObject<HTMLElement | null>, trigger: RefObject<HTMLElement | null>) {
  useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) close();
    };
    const key = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      close();
      trigger.current?.focus();
    };
    document.addEventListener("pointerdown", down);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("pointerdown", down);
      document.removeEventListener("keydown", key);
    };
  }, [open, close, box, trigger]);
}

export const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

export const EDIT_FIELD = `min-h-8 min-w-0 rounded-sm border border-border-strong bg-surface-raised px-2 py-1 text-sm leading-5 text-ink placeholder:text-ink-faint ${FOCUS}`;

export const FIELD_ERROR = "border-status-fault bg-status-fault-wash";

/**
 * 44 px at phone width, the comfortable 32 px from 640 px (I11: steppers and chips are touched
 * there; WCAG 2.2 target size).
 */
export const TOUCH = "min-h-11 sm:min-h-8";

/** The save state beside a value: Ukládám… / Uloženo / Neuloženo – Zkusit znovu. Idle says nothing. */
export function SaveNote({ state, onRetry }: { state: SaveState; onRetry?: () => void }) {
  // One live region that stays mounted, so each change of state is announced.
  return (
    <span aria-live="polite" className={`inline-flex items-baseline gap-1 text-xs ${state === "failed" ? "text-status-fault" : "text-ink-faint"}`}>
      {state === "saving" ? t("input.saving") : null}
      {state === "saved" ? t("input.saved") : null}
      {state === "failed" ? (
        <>
          {t("input.unsaved")}
          {onRetry ? (
            <>
              {" – "}
              <button type="button" onClick={onRetry} className={`rounded-sm font-medium underline underline-offset-2 ${FOCUS}`}>
                {t("input.retry")}
              </button>
            </>
          ) : null}
        </>
      ) : null}
    </span>
  );
}
