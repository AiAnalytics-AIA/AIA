// @vitest-environment jsdom
// The field draws 144 dots without reading layout per frame, forms the mark at the
// film's frame-0 places when the sign-in has gone through, and says so once.
import { cleanup, render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DOT_COUNT, markTargets, MARK_FORMED_EVENT } from "@/lib/dot-field";
import { DotField } from "./DotField";

type Arc = { x: number; y: number; r: number; fill: string };
let arcs: Arc[];
let frames: FrameRequestCallback[];
let now: number;
let panelReads: number;

function fakeContext() {
  const ctx = {
    fillStyle: "",
    setTransform: () => {},
    clearRect: () => {
      arcs = [];
    },
    fillRect: () => {},
    beginPath: () => {},
    arc: (x: number, y: number, r: number) => arcs.push({ x, y, r, fill: ctx.fillStyle }),
    fill: () => {},
  };
  return ctx;
}

/** Runs the queued animation frames at `ms` on the page's clock. */
function tick(ms: number) {
  now = ms;
  const due = frames;
  frames = [];
  due.forEach((cb) => cb(ms));
}

function Field({ leaving }: { leaving: boolean }) {
  const panel = useRef<HTMLElement>(null);
  return (
    <>
      <aside ref={panel} />
      <DotField panel={panel} leaving={leaving} />
    </>
  );
}

beforeEach(() => {
  arcs = [];
  frames = [];
  now = 0;
  panelReads = 0;
  vi.spyOn(performance, "now").mockImplementation(() => now);
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => frames.push(cb));
  vi.stubGlobal("cancelAnimationFrame", () => {});
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    if (this.tagName === "ASIDE") panelReads += 1;
    return { left: 0, top: 0, width: 380, height: 768, right: 380, bottom: 768, x: 0, y: 0, toJSON: () => ({}) } as DOMRect;
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("DotField", () => {
  it("is a full-viewport canvas nobody can point at or hear", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const { container } = render(<Field leaving={false} />);
    const canvas = container.querySelector("canvas")!;
    expect(canvas.getAttribute("aria-hidden")).toBe("true");
    expect(canvas.className).toContain("pointer-events-none");
    expect(canvas.className).toContain("fixed");
  });

  it("draws every dot each frame and never measures the panel inside the loop", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext() as never);
    render(<Field leaving={false} />);
    const measured = panelReads;
    for (let f = 1; f <= 30; f++) tick(f * 16.7);
    expect(arcs).toHaveLength(DOT_COUNT);
    expect(panelReads).toBe(measured);
    expect(arcs.every((a) => a.x >= -40 && a.x <= 420)).toBe(true);
  });

  it("forms the mark at the film's frame-0 places, then says so once and stops", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext() as never);
    const formed = vi.fn();
    window.addEventListener(MARK_FORMED_EVENT, formed);
    const { rerender } = render(<Field leaving={false} />);
    tick(1000);
    rerender(<Field leaving />);
    for (let ms = 1000; ms <= 2700; ms += 50) tick(ms);
    expect(formed).not.toHaveBeenCalled();
    tick(2760);
    expect(formed).toHaveBeenCalledTimes(1);
    const targets = markTargets(window.innerWidth, window.innerHeight);
    expect(arcs).toHaveLength(25);
    for (const target of targets) {
      expect(arcs.some((a) => Math.abs(a.x - target.x) < 1e-6 && Math.abs(a.y - target.y) < 1e-6 && Math.abs(a.r - target.r) < 1e-6)).toBe(true);
    }
    const apex = targets.find((tg) => tg.apex)!;
    expect(arcs.find((a) => Math.abs(a.x - apex.x) < 1e-6 && Math.abs(a.y - apex.y) < 1e-6)?.fill).toMatch(/^rgba\(106,197,232,1\.000\)$/);
    // A formed mark stands still: no further frame is asked for.
    expect(frames).toHaveLength(0);
    window.removeEventListener(MARK_FORMED_EVENT, formed);
  });

  it("still calls the mark formed on time without a 2D context", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    const formed = vi.fn();
    window.addEventListener(MARK_FORMED_EVENT, formed);
    render(<Field leaving />);
    vi.advanceTimersByTime(1749);
    expect(formed).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(formed).toHaveBeenCalledTimes(1);
    window.removeEventListener(MARK_FORMED_EVENT, formed);
  });

  it("holds still and forms the mark in half a second under reduced motion", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("reduce"), addEventListener() {}, removeEventListener() {} }));
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(fakeContext() as never);
    const formed = vi.fn();
    window.addEventListener(MARK_FORMED_EVENT, formed);
    const { rerender } = render(<Field leaving={false} />);
    tick(100);
    const first = arcs.map((a) => [a.x, a.y]);
    window.dispatchEvent(new PointerEvent("pointermove", { clientX: first[0][0], clientY: first[0][1] }));
    tick(5000);
    expect(arcs.map((a) => [a.x, a.y])).toEqual(first);
    rerender(<Field leaving />);
    tick(5490);
    expect(formed).not.toHaveBeenCalled();
    tick(5500);
    expect(formed).toHaveBeenCalledTimes(1);
    window.removeEventListener(MARK_FORMED_EVENT, formed);
  });
});
