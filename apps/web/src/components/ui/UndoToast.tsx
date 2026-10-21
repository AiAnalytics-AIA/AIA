"use client";

// I6: a reversible delete happens at once, with "Vrátit" for 8 s. One offer at a time: a new one
// replaces the last (whose deletion then simply stands). The time stops while the pointer or the
// keyboard is on the toast, so it never runs out under a person reading it (WCAG 2.2.1), and runs
// its full 8 s again when they leave. On z-toast, in one polite live region. A field error is never
// reported here (I9); this is for what a person did and may take back.

import { useCallback, useEffect, useRef, useState } from "react";

import { t } from "@/i18n/t";
import { Icon } from "../rehome/icons";
import { FOCUS } from "./parts";

/** How long "Vrátit" is offered (input-interactions I6). */
export const UNDO_MS = 8000;

export type UndoOffer = {
  /** What just happened, in words ("Složka „Archiv 2024“ smazána"). */
  message: string;
  /**
   * Takes it back. Called once, at most, after the toast is gone; awaited by nothing, so the
   * caller owns its errors (a failed re-create is said where the item is, never here: I9).
   */
  undo: () => void;
};

/** One undo offer at a time: `offer` shows it (replacing any other), `clear` takes it down. */
export function useUndo(): { current: UndoOffer | null; offer: (o: UndoOffer) => void; clear: () => void } {
  const [current, setCurrent] = useState<UndoOffer | null>(null);
  const offer = useCallback((o: UndoOffer) => setCurrent(o), []);
  const clear = useCallback(() => setCurrent(null), []);
  return { current, offer, clear };
}

export function UndoToast({ offer, onDone, ms = UNDO_MS }: { offer: UndoOffer | null; onDone: () => void; ms?: number }) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The pointer and the keyboard each hold the time on their own: leaving with the pointer must not
  // end a hold the focus still makes, nor the reverse (Codex on #532). It runs only when neither is
  // on the toast.
  const [pointerInside, setPointerInside] = useState(false);
  const [focusInside, setFocusInside] = useState(false);
  const held = pointerInside || focusInside;
  // A hold ends with the toast. Activating "Vrátit" or "Zavřít" removes it with focus inside, and
  // no blur follows: without this the next offer would never expire. (An offer that replaces
  // another while focus stays on the toast keeps the hold: the person is still on it.)
  if (!offer && held) {
    setPointerInside(false);
    setFocusInside(false);
  }
  const finish = () => {
    setPointerInside(false);
    setFocusInside(false);
    onDone();
  };

  // The newest onDone, read when the time runs out: a caller passing a new function on each render
  // must not restart the 8 s (the sweep after Codex on #532).
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  }, [onDone]);

  useEffect(() => {
    if (!offer || held) return;
    timer.current = setTimeout(() => done.current(), ms);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [offer, held, ms]);

  return (
    <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-6 z-[var(--z-toast)] flex justify-center px-4">
      {offer ? (
        <div
          role="status"
          onPointerEnter={() => setPointerInside(true)}
          onPointerLeave={() => setPointerInside(false)}
          onFocus={() => setFocusInside(true)}
          onBlur={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setFocusInside(false);
          }}
          className="pointer-events-auto flex max-w-full items-center gap-3 rounded-md border border-border-strong bg-surface-inverse py-1.5 pl-4 pr-1.5 text-sm text-ink-inverse shadow-[var(--shadow-overlay)]"
        >
          <span className="min-w-0">{offer.message}</span>
          <button
            type="button"
            onClick={() => {
              const o = offer;
              finish();
              o.undo();
            }}
            className={`min-h-11 shrink-0 rounded-sm px-2 font-semibold text-ink-inverse underline underline-offset-2 sm:min-h-8 ${FOCUS}`}
          >
            {t("input.undo")}
          </button>
          <button
            type="button"
            aria-label={t("input.undoClose")}
            onClick={finish}
            className={`inline-flex size-11 shrink-0 items-center justify-center rounded-sm text-ink-inverse/70 hover:text-ink-inverse sm:size-8 ${FOCUS}`}
          >
            <Icon name="fault" size={12} />
          </button>
        </div>
      ) : null}
    </div>
  );
}
