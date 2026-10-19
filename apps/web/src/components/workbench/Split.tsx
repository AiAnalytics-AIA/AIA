"use client";

// The conversation / artifact split (research-lead-workbench chunk 3), ported from the
// prototype (prototypes/research-lead-v2/src/components/Split.tsx @ 9b50963f). Its rules are
// lib/workbench-split.ts: 28-62 %, 2 % per arrow, Home / Enter / double-click back to 40 %, and
// focus modes that never change the width the person chose.

import { type ReactNode, useRef, useState } from "react";

import { type FocusMode, SPLIT_DEFAULT, SPLIT_MAX, SPLIT_MIN, leftWidth, splitFromKey, splitFromPointer } from "@/lib/workbench-split";

export function Split({ split, mode, onSplit, onCommit, left, right, rail }: {
  split: number;
  mode: FocusMode;
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
  const width = leftWidth(split, mode);
  const fromPointer = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    return r ? splitFromPointer(clientX, { left: r.left, width: r.width }, split) : split;
  };
  return (
    <div className={`split split--${mode === "split" ? "normal" : mode}`} ref={box}>
      {width === null ? <div className="split__rail">{rail}</div> : null}
      {/* In artifact focus the conversation is hidden, not unmounted: its draft and queue survive. */}
      <div className="split__left" hidden={width === null} style={width === null ? undefined : { width: `${width}%` }}>{left}</div>
      {mode === "split" ? (
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
