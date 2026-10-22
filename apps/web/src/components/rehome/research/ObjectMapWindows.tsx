"use client";

// The AIA panel's floating windows over the map (ui_app.html, somecs-floating-panels): a window drags
// by its header, resizes from any of its four corners, comes to the front when clicked, and only its
// body scrolls. The panel keeps the windows in the browser window; here they live inside the map
// stage, so they stay usable when the stage alone is in full screen, and a moved window is kept
// within the stage (at least 100 px of it across, its header reachable). Positions and sizes are
// presentation state, kept for the page's lifetime as the panel keeps them in memory.

import { type CSSProperties, type PointerEvent as ReactPointerEvent, type ReactNode, useCallback, useEffect, useRef, useState } from "react";

export type WindowRect = { x: number; y: number; w: number; h: number };
type Corner = "tl" | "tr" | "bl" | "br";

/** The panel's grip size, minimum size, and how much of a moved window stays in view. */
export const EDGE = 14, MIN_W = 260, MIN_H = 140, KEEP_X = 100, KEEP_Y = 40;
/** Windows stack from here up, over the dock (300). */
export const Z_BASE = 400;
// A press on one of these in a header is that control's, not a drag (the panel's list).
const INTERACTIVE = "button,input,select,textarea,a,label";

const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);

/** Where a window of width w may sit in a stage: at least KEEP_X of it across, the header inside. */
export function clampMove(x: number, y: number, w: number, stageW: number, stageH: number): { x: number; y: number } {
  return { x: clamp(x, KEEP_X - w, stageW - KEEP_X), y: clamp(y, 0, stageH - KEEP_Y) };
}

/** The corner of a box the point is within EDGE of (the panel's `corner`), or "". */
export function cornerAt(r: { left: number; top: number; right: number; bottom: number; width: number; height: number }, x: number, y: number): Corner | "" {
  if (!r.width || !r.height || x < r.left || x > r.right || y < r.top || y > r.bottom) return "";
  const L = x - r.left < EDGE, R = r.right - x < EDGE, T = y - r.top < EDGE, B = r.bottom - y < EDGE;
  return T && L ? "tl" : T && R ? "tr" : B && L ? "bl" : B && R ? "br" : "";
}

/** A window resized from a corner by (dx, dy): never under MIN_W x MIN_H, never past the stage's edges. */
export function resized(r0: WindowRect, corner: Corner, dx: number, dy: number, stageW: number, stageH: number): WindowRect {
  let { x, y, w, h } = r0;
  if (corner[1] === "r") w = Math.max(MIN_W, Math.min(r0.w + dx, stageW - r0.x));
  else { w = Math.max(MIN_W, Math.min(r0.w - dx, r0.x + r0.w)); x = r0.x + r0.w - w; }
  if (corner[0] === "b") h = Math.max(MIN_H, Math.min(r0.h + dy, stageH - r0.y));
  else { h = Math.max(MIN_H, Math.min(r0.h - dy, r0.y + r0.h)); y = r0.y + r0.h - h; }
  return { x, y, w, h };
}

/** Follows the pointer over the whole document until it is released. */
function follow(onMove: (e: PointerEvent) => void) {
  const end = () => {
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", end);
    window.removeEventListener("pointercancel", end);
  };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", end);
  window.addEventListener("pointercancel", end);
}

/** The stage's windows: where each one is (once moved or resized), their stacking, and the handlers. */
export function useMapWindows(stage: HTMLElement | null, size: { width: number; height: number }) {
  const [rects, setRects] = useState<Record<string, WindowRect>>({});
  const [order, setOrder] = useState<Record<string, number>>({});
  const [cursor, setCursor] = useState<"" | "nwse" | "nesw">("");
  const top = useRef(Z_BASE);
  const orderNow = useRef(order);
  useEffect(() => { orderNow.current = order; }, [order]);

  const front = useCallback((id: string) => {
    if (orderNow.current[id] === top.current && top.current > Z_BASE) return;
    const z = ++top.current;
    setOrder((o) => ({ ...o, [id]: z }));
  }, []);

  const local = useCallback((el: Element): WindowRect => {
    const s = stage!.getBoundingClientRect(), r = el.getBoundingClientRect();
    return { x: r.left - s.left, y: r.top - s.top, w: r.width, h: r.height };
  }, [stage]);

  /** The topmost open window with a corner under the point. */
  const cornerHit = useCallback((x: number, y: number) => {
    if (!stage) return null;
    let best: { el: HTMLElement; id: string; corner: Corner; z: number } | null = null;
    stage.querySelectorAll<HTMLElement>("[data-window]").forEach((el) => {
      const corner = cornerAt(el.getBoundingClientRect(), x, y);
      const id = el.dataset.window!, z = orderNow.current[id] ?? Z_BASE;
      if (corner && (!best || z >= best.z)) best = { el, id, corner, z };
    });
    return best as { el: HTMLElement; id: string; corner: Corner; z: number } | null;
  }, [stage]);

  /** On the stage, before anything under it: a press at a window's corner resizes that window. */
  const onPointerDownCapture = useCallback((e: ReactPointerEvent<HTMLElement>) => {
    if ((e.button ?? 0) !== 0 || !stage) return;
    const hit = cornerHit(e.clientX, e.clientY);
    if (!hit) return;
    e.preventDefault();
    e.stopPropagation();
    front(hit.id);
    const r0 = local(hit.el), s = stage.getBoundingClientRect(), x0 = e.clientX, y0 = e.clientY;
    setRects((rs) => ({ ...rs, [hit.id]: r0 }));
    follow((ev) => setRects((rs) => ({ ...rs, [hit.id]: resized(r0, hit.corner, ev.clientX - x0, ev.clientY - y0, s.width, s.height) })));
  }, [stage, cornerHit, front, local]);

  const onPointerMove = useCallback((e: ReactPointerEvent<HTMLElement>) => {
    if (e.buttons) return;
    const hit = cornerHit(e.clientX, e.clientY);
    setCursor(!hit ? "" : hit.corner === "tl" || hit.corner === "br" ? "nwse" : "nesw");
  }, [cornerHit]);

  /** A press on a window's header (not on a control in it) drags the window. */
  const drag = useCallback((id: string) => (e: ReactPointerEvent<HTMLElement>) => {
    if ((e.button ?? 0) !== 0 || !stage) return;
    if ((e.target as Element).closest(INTERACTIVE)) return;
    const el = e.currentTarget.closest("[data-window]");
    if (!el) return;
    e.preventDefault();
    const r0 = local(el), s = stage.getBoundingClientRect();
    const dx = e.clientX - s.left - r0.x, dy = e.clientY - s.top - r0.y;
    setRects((rs) => ({ ...rs, [id]: r0 }));
    follow((ev) => setRects((rs) => ({ ...rs, [id]: { ...r0, ...clampMove(ev.clientX - s.left - dx, ev.clientY - s.top - dy, r0.w, s.width, s.height) } })));
  }, [stage, local]);

  /** A window's place: its own default until moved; a moved one kept within the stage as it is now. */
  const frame = useCallback((id: string): CSSProperties | undefined => {
    const r = rects[id], z = order[id];
    if (!r) return z ? { zIndex: z } : undefined;
    const w = Math.min(r.w, Math.max(MIN_W, size.width)), h = Math.min(r.h, Math.max(MIN_H, size.height));
    const p = clampMove(r.x, r.y, w, size.width, size.height);
    return { left: p.x, top: p.y, width: w, height: h, right: "auto", bottom: "auto", maxWidth: "none", maxHeight: "none", zIndex: z };
  }, [rects, order, size.width, size.height]);

  return { frame, front, drag, cursor, stageHandlers: { onPointerDownCapture, onPointerMove } };
}

/** One floating window: a non-modal dialog named by its title, its header the drag handle. */
export function MapWindow({ id, title, kind, style, onFront, onDrag, onClose, closeLabel, focusOnOpen = false, testId, children }: {
  id: string; title: string; kind: "work" | "detail"; style: CSSProperties | undefined;
  onFront: (id: string) => void; onDrag: (e: ReactPointerEvent<HTMLElement>) => void; onClose: () => void; closeLabel: string;
  focusOnOpen?: boolean; testId?: string; children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  // A window opened from a button takes the focus, so the keyboard continues inside it.
  useEffect(() => { if (focusOnOpen) ref.current?.focus({ preventScroll: true }); }, [focusOnOpen]);
  return (
    <section ref={ref} role="dialog" aria-label={title} tabIndex={-1} data-window={id} data-testid={testId}
      className={`omw-win omw-win--${kind}`} style={style} onPointerDown={() => onFront(id)}>
      <header className={kind === "detail" ? "omw-side-title" : "omw-head"} onPointerDown={onDrag} data-testid={`object-map-window-head-${id}`}>
        <b>{title}</b>
        <button type="button" className="omw-close" aria-label={closeLabel} title={closeLabel} onClick={onClose}>×</button>
      </header>
      <div className="omw-body">{children}</div>
      {(["tl", "tr", "bl", "br"] as const).map((c) => <span key={c} aria-hidden className={`omw-grip omw-grip--${c}`} />)}
    </section>
  );
}
