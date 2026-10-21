"use client";

// The conversation / artifact split (research-lead-workbench chunk 3), ported from the
// prototype (prototypes/research-lead-v2/src/components/Split.tsx @ 9b50963f). Its rules are
// lib/workbench-split.ts: 28-62 %, 2 % per arrow, Home / Enter / double-click back to 40 %, and
// focus modes that never change the width the person chose.

import { type KeyboardEvent, type ReactNode, useRef, useState } from "react";

import type { WorkbenchLayout } from "@/lib/workbench-layout";
import { type FocusMode, SPLIT_DEFAULT, SPLIT_MAX, SPLIT_MIN, leftWidth, splitFromKey, splitFromPointer } from "@/lib/workbench-split";

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** The open drawer or sheet is modal: Tab and Shift+Tab go round inside it, never to the artifact behind. */
export function trapTab(e: KeyboardEvent<HTMLElement>) {
  if (e.key !== "Tab") return;
  const items = [...e.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => !el.closest("[hidden]"));
  if (!items.length) {
    e.preventDefault();
    return;
  }
  const first = items[0]!;
  const last = items[items.length - 1]!;
  const active = document.activeElement;
  const inside = active instanceof HTMLElement && e.currentTarget.contains(active);
  if (e.shiftKey && (!inside || active === first)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && (!inside || active === last)) {
    e.preventDefault();
    first.focus();
  }
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
  const width = compact ? null : leftWidth(split, mode);
  const fromPointer = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    return r ? splitFromPointer(clientX, { left: r.left, width: r.width }, split) : split;
  };
  return (
    <div className={`split split--${compact ? layout : mode === "split" ? "normal" : mode}`} ref={box}>
      {width === null ? <div className="split__rail">{rail}</div> : null}
      {/* In artifact focus, and in a closed drawer, the conversation is hidden, not unmounted: its
          draft, queue, poll and once-only view ops survive (D21: one tree, no remount). */}
      {compact ? (
        <div className="split__left" hidden={!shown} role={shown ? "dialog" : undefined} aria-modal={shown ? true : undefined} aria-label={shown ? leftLabel : undefined} onKeyDown={shown ? trapTab : undefined}>{left}</div>
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
      <div className="split__right">{right}</div>
    </div>
  );
}
