"use client";

/**
 * The front door's dot field (lib/dot-field.ts is its maths): 144 dots homed in
 * the panel, drawn on one full-viewport canvas over the page and under its text.
 * They drift, and part around the cursor; once `leaving` turns true -- a sign-in
 * that has opened AIA's session -- 25 primes fly into the AIA mark where the
 * launch film's first frame has it, the rest fade, the canvas paints the film's
 * ground under them, and `aia:mark-formed` fires on window when the mark stands.
 *
 * Decoration: hidden from assistive technology, never a pointer target. No
 * layout is read inside the animation loop: the panel is measured on resize and
 * scroll only. Under prefers-reduced-motion there is no drift and no push, and
 * the handoff is a 0.45 s move. Without a 2D context (a test, a refusing
 * browser) nothing is drawn and the mark is still called formed on time.
 */

import { useEffect, useRef, type RefObject } from "react";

import {
  assignMark,
  drift,
  formedAt,
  groundAlpha,
  handoffDot,
  makeDots,
  makeSprings,
  markTargets,
  MARK_FORMED_EVENT,
  parseHex,
  pushStep,
  type Point,
  type Rect,
  type Target,
} from "@/lib/dot-field";

type Handoff = { start: number; from: Point[]; assign: Int16Array; targets: Target[]; formed: boolean };

function reducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function announceFormed() {
  window.dispatchEvent(new CustomEvent(MARK_FORMED_EVENT));
}

export function DotField({ panel, leaving }: { panel: RefObject<HTMLElement | null>; leaving: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const begin = useRef<() => void>(() => {});

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext("2d");
    const still = reducedMotion();
    const dots = makeDots();
    const springs = makeSprings(dots.length);
    const style = getComputedStyle(el);
    const colour = (name: string, fallback: [number, number, number]) => parseHex(style.getPropertyValue(name)) ?? fallback;
    const ink = colour("--ink", [236, 233, 228]);
    const apex = colour("--brand-apex", [106, 197, 232]);
    const ground = colour("--brand-stage", [17, 16, 21]);

    let W = 0;
    let H = 0;
    let dpr = 1;
    let box: Rect = { x: 0, y: 0, w: 0, h: 0 };
    let pointer: Point | null = null;
    let handoff: Handoff | null = null;
    let raf = 0;
    let timer = 0;
    const t0 = performance.now();
    let last = 0;

    const measure = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      W = window.innerWidth;
      H = window.innerHeight;
      el.width = Math.round(W * dpr);
      el.height = Math.round(H * dpr);
      const r = panel.current?.getBoundingClientRect();
      if (r) box = { x: r.left, y: r.top, w: r.width, h: r.height };
      if (handoff) handoff.targets = markTargets(W, H);
    };

    const draw = (t: number) => {
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const h = handoff ? t - handoff.start : 0;
      if (handoff) {
        ctx.fillStyle = `rgba(${ground[0]},${ground[1]},${ground[2]},${groundAlpha(h, still).toFixed(3)})`;
        ctx.fillRect(0, 0, W, H);
      }
      for (let i = 0; i < dots.length; i++) {
        const d = dots[i];
        const p = drift(d, box, t, still);
        const now = { x: p.x + springs.ox[i], y: p.y + springs.oy[i] };
        let x = now.x;
        let y = now.y;
        let r = d.r;
        let a = d.a;
        let mix = 0;
        if (handoff) {
          const k = handoff.assign[i];
          const drawn = handoffDot(d, i, handoff.from[i], now, k >= 0 ? handoff.targets[k] : null, h, still);
          ({ x, y, r, a } = drawn);
          mix = drawn.apex;
        }
        if (a <= 0.002) continue;
        const c = mix ? ink.map((v, j) => Math.round(v + (apex[j] - v) * mix)) : ink;
        ctx.fillStyle = `rgba(${c[0]},${c[1]},${c[2]},${a.toFixed(3)})`;
        ctx.beginPath();
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    const frame = (ms: number) => {
      const t = (ms - t0) / 1000;
      const dt = Math.min(0.05, Math.max(0, t - last));
      last = t;
      if (!handoff) pushStep(dots, springs, box, pointer, t, dt, still);
      draw(t);
      if (handoff && !handoff.formed && t - handoff.start >= formedAt(still)) {
        handoff.formed = true;
        announceFormed();
      }
      // A formed mark stands still: nothing to draw until a resize.
      if (!handoff?.formed) raf = requestAnimationFrame(frame);
    };

    begin.current = () => {
      if (handoff) return;
      const t = (performance.now() - t0) / 1000;
      const from = dots.map((d, i) => {
        const p = drift(d, box, t, still);
        return { x: p.x + springs.ox[i], y: p.y + springs.oy[i] };
      });
      handoff = { start: t, from, assign: assignMark(dots, from), targets: markTargets(W, H), formed: false };
      if (!ctx) timer = window.setTimeout(announceFormed, formedAt(still) * 1000);
    };

    const onMove = (e: PointerEvent) => {
      pointer = { x: e.clientX, y: e.clientY };
    };
    const onLeave = () => {
      pointer = null;
    };
    const onResize = () => {
      measure();
      if (handoff?.formed) draw(last);
    };
    measure();
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(onResize) : null;
    if (panel.current) observer?.observe(panel.current);
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onResize, { passive: true });
    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    window.addEventListener("blur", onLeave);
    if (ctx) raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(timer);
      observer?.disconnect();
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onResize);
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("blur", onLeave);
      begin.current = () => {};
    };
  }, [panel]);

  useEffect(() => {
    if (leaving) begin.current();
  }, [leaving]);

  return (
    <canvas
      ref={canvas}
      data-dot-field={leaving ? "leaving" : "idle"}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-10 h-full w-full"
    />
  );
}
