"use client";

// The conversation / artifact split (research-lead-workbench chunk 3), ported from the
// prototype (prototypes/research-lead-v2/src/components/Split.tsx @ 9b50963f). Its rules are
// lib/workbench-split.ts: 28-62 %, 2 % per arrow, Home / Enter / double-click back to 40 %, and
// focus modes that never change the width the person chose.

import { type ReactNode, type RefObject, useEffect, useRef, useState } from "react";

import type { WorkbenchLayout } from "@/lib/workbench-layout";
import { type FocusMode, SPLIT_DEFAULT, SPLIT_MAX, SPLIT_MIN, leftWidth, splitFromKey, splitFromPointer } from "@/lib/workbench-split";

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** The open drawer or sheet is modal: Tab and Shift+Tab go round inside it, never to the artifact behind
 * (which is inert as well; the wrap keeps focus off the browser's own controls between the ends). Read
 * on the document, so a Tab from nowhere -- the focused control removed, focus fallen to the body --
 * is brought back inside as well. */
export function trapTab(container: HTMLElement, e: KeyboardEvent) {
  if (e.key !== "Tab") return;
  const items = [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => !el.closest("[hidden]"));
  if (!items.length) {
    e.preventDefault();
    return;
  }
  const first = items[0]!;
  const last = items[items.length - 1]!;
  const active = document.activeElement;
  const inside = active instanceof HTMLElement && container.contains(active);
  if (e.shiftKey && (!inside || active === first)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && (!inside || active === last)) {
    e.preventDefault();
    first.focus();
  }
}

/** Where focus goes back to inside the open drawer or sheet when the control that held it is gone:
 *  the composer while it takes text, else the conversation's log, else the dialog itself. */
export function recoveryTarget(container: HTMLElement): HTMLElement {
  const composer = container.querySelector<HTMLTextAreaElement>("textarea:not([disabled])");
  if (composer && !composer.closest("[hidden]")) return composer;
  return container.querySelector<HTMLElement>('[role="log"]') ?? container;
}

/** Whether an element still in the page can no longer hold the focus: disabled, hidden or inert. */
function cannotHoldFocus(el: HTMLElement): boolean {
  return (el as HTMLButtonElement).disabled === true || el.closest("[hidden], [inert]") !== null;
}

/** While the drawer or sheet is open, a focused card control that unmounts (an approve button
 *  replaced by its result, "Na nejnovější" scrolled away) leaves focus on the body, outside the
 *  modal and behind an inert page: it is brought back inside (recoveryTarget). Watched by mutation,
 *  because a browser need not fire focusout for a removed element. */
function useFocusRecovery(dialog: RefObject<HTMLDivElement | null>, modal: boolean) {
  useEffect(() => {
    const el = dialog.current;
    if (!modal || !el) return;
    let held: HTMLElement | null = null;
    const onIn = (e: FocusEvent) => {
      held = e.target instanceof HTMLElement ? e.target : null;
    };
    const recover = () => {
      const active = document.activeElement;
      const lost = !active || active === document.body || !active.isConnected;
      if (held && !held.isConnected && lost) {
        held = null;
        recoveryTarget(el).focus();
      }
    };
    // A focusout from an element still in the page is the person moving focus away: nothing is
    // held any more, so a later re-render that removes that element takes nothing back. Read
    // after the event: Chromium fires focusout during removeChild, while the element is still
    // connected, so the check waits a microtask, which runs before the mutation callback.
    // A control that became disabled while it had the focus (an approve button while its decision
    // is sent) blurs too, still connected: Chromium drops the focus to the body. The person did not
    // move it, so it comes back at once.
    const onOut = (e: FocusEvent) => {
      const target = e.target;
      queueMicrotask(() => {
        if (!(target instanceof HTMLElement) || !target.isConnected) return recover();
        const active = document.activeElement;
        const toBody = !active || active === document.body;
        if (toBody && cannotHoldFocus(target)) {
          held = null;
          recoveryTarget(el).focus();
        } else {
          held = null;
        }
      });
    };
    const watch = new MutationObserver(recover);
    el.addEventListener("focusin", onIn);
    el.addEventListener("focusout", onOut);
    watch.observe(el, { childList: true, subtree: true });
    return () => {
      watch.disconnect();
      el.removeEventListener("focusin", onIn);
      el.removeEventListener("focusout", onOut);
    };
  }, [dialog, modal]);
}

export function Split({ split, mode, layout = "split", shown = true, leftLabel, onSplit, onCommit, left, right, rail }: {
  split: number;
  mode: FocusMode;
  /** The workbench's layout (lib/workbench-layout.ts): in the drawer and the sheet there is no
   * handle, the rail is the launcher and the conversation opens over the artifact. */
  layout?: WorkbenchLayout;
  /** In the drawer and the sheet: whether the conversation is open. It stays mounted either way. */
  shown?: boolean;
  /** The open drawer's or sheet's accessible name: it is a modal dialog then. */
  leftLabel?: string;
  /** While dragging: the width shown, not yet kept. */
  onSplit: (v: number) => void;
  /** The width the person settled on: kept for this browser. */
  onCommit: (v: number) => void;
  left: ReactNode;
  right: ReactNode;
  rail: ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState(false);
  const compact = layout !== "split";
  const dialog = useRef<HTMLDivElement>(null);
  const modal = compact && shown;
  useFocusRecovery(dialog, modal);
  useEffect(() => {
    if (!modal) return;
    const onKey = (e: KeyboardEvent) => dialog.current && trapTab(dialog.current, e);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [modal]);
  const width = compact ? null : leftWidth(split, mode);
  const fromPointer = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    return r ? splitFromPointer(clientX, { left: r.left, width: r.width }, split) : split;
  };
  return (
    <div className={`split split--${compact ? layout : mode === "split" ? "normal" : mode}`} ref={box}>
      {width === null ? <div className="split__rail" inert={compact && shown}>{rail}</div> : null}
      {/* In artifact focus, and in a closed drawer, the conversation is hidden, not unmounted: its
          draft, queue, poll and once-only view ops survive (D21: one tree, no remount). */}
      {compact ? (
        <div className="split__left" hidden={!shown} role={shown ? "dialog" : undefined} aria-modal={shown ? true : undefined} aria-label={shown ? leftLabel : undefined} ref={dialog}>{left}</div>
      ) : (
        <div className="split__left" hidden={width === null} style={width === null ? undefined : { width: `${width}%` }}>{left}</div>
      )}
      {!compact && mode === "split" ? (
        <div
          className={`split__handle${drag ? " is-drag" : ""}`}
          role="separator"
          aria-orientation="vertical"
          aria-label="Změnit poměr konverzace a artefaktu"
          aria-valuemin={SPLIT_MIN}
          aria-valuemax={SPLIT_MAX}
          aria-valuenow={Math.round(split)}
          tabIndex={0}
          title="Táhněte, nebo šipkami. Dvojklik vrátí 40 / 60."
          onPointerDown={(e) => {
            (e.target as HTMLElement).setPointerCapture(e.pointerId);
            setDrag(true);
          }}
          onPointerMove={(e) => {
            if (drag) onSplit(fromPointer(e.clientX));
          }}
          onPointerUp={(e) => {
            if (!drag) return;
            setDrag(false);
            onCommit(fromPointer(e.clientX));
          }}
          onDoubleClick={() => onCommit(SPLIT_DEFAULT)}
          onKeyDown={(e) => {
            const next = splitFromKey(split, e.key);
            if (next === null) return;
            e.preventDefault();
            onCommit(next);
          }}
        />
      ) : null}
      {/* Behind the open drawer or sheet nothing answers a pointer, a key or assistive technology:
          aria-modal is true of the page, not only declared (the header and navigator likewise). */}
      <div className="split__right" inert={compact && shown}>{right}</div>
    </div>
  );
}
