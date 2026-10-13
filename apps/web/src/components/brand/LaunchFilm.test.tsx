// @vitest-environment jsdom
// The film waits out of sight for the mark, takes over on its first frame and is
// never in the way: it ends, fails, stalls or is skipped, and each is the way in, once.
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MARK_FORMED_EVENT } from "@/lib/dot-field";
import { FILM_CEILING_MS, FILM_FRAME0_WAIT_MS, FILM_SOURCES, LaunchFilm } from "./LaunchFilm";

let play: ReturnType<typeof vi.fn>;

beforeEach(() => {
  play = vi.fn(() => Promise.resolve());
  vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(play as () => Promise<void>);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const video = (c: HTMLElement) => c.querySelector("video") as HTMLVideoElement;
const formMark = () => act(() => void window.dispatchEvent(new CustomEvent(MARK_FORMED_EVENT)));
const setup = () => {
  const onFirstFrame = vi.fn();
  const onDone = vi.fn();
  const view = render(<LaunchFilm onFirstFrame={onFirstFrame} onDone={onDone} />);
  return { ...view, onFirstFrame, onDone, v: video(view.container) };
};

describe("LaunchFilm", () => {
  it("loads both sources, muted and out of sight, full-screen on the film's ground, and does not play before the mark forms", () => {
    const { v, onDone } = setup();
    expect([...v.querySelectorAll("source")].map((s) => s.getAttribute("src"))).toEqual(FILM_SOURCES.map((s) => s.src));
    expect(v.muted).toBe(true);
    expect(v.getAttribute("preload")).toBe("auto");
    expect(v.getAttribute("aria-hidden")).toBe("true");
    expect(v.className).toContain("invisible");
    expect(v.className).toContain("object-contain");
    expect(v.className).toContain("bg-brand-stage");
    expect(play).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("shows frame 0 when the mark forms, lets the canvas go, then plays, and is done when it ends, once", async () => {
    const { v, onFirstFrame, onDone } = setup();
    formMark();
    expect(v.dataset.film).toBe("rolling");
    expect(v.className).not.toContain("invisible");
    expect(play).not.toHaveBeenCalled();
    v.dispatchEvent(new Event("loadeddata"));
    await vi.waitFor(() => expect(onFirstFrame).toHaveBeenCalledTimes(1));
    // The canvas goes before the film moves.
    await vi.waitFor(() => expect(play).toHaveBeenCalledTimes(1));
    expect(onFirstFrame.mock.invocationCallOrder[0]).toBeLessThan(play.mock.invocationCallOrder[0]);
    v.dispatchEvent(new Event("ended"));
    v.dispatchEvent(new Event("ended"));
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("does not wait when frame 0 is already loaded", async () => {
    Object.defineProperty(HTMLMediaElement.prototype, "readyState", { configurable: true, get: () => 2 });
    try {
      const { onFirstFrame } = setup();
      formMark();
      await vi.waitFor(() => expect(onFirstFrame).toHaveBeenCalledTimes(1));
      await vi.waitFor(() => expect(play).toHaveBeenCalledTimes(1));
    } finally {
      delete (HTMLMediaElement.prototype as { readyState?: unknown }).readyState;
    }
  });

  it("plays to get frame 0 when the browser will not load it first, the canvas going on the first presented frame", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    let presented: (() => void) | null = null;
    Object.defineProperty(HTMLVideoElement.prototype, "requestVideoFrameCallback", {
      configurable: true,
      value: (cb: () => void) => ((presented = cb), 1),
    });
    try {
      const { onFirstFrame } = setup();
      formMark();
      vi.advanceTimersByTime(FILM_FRAME0_WAIT_MS - 1);
      expect(play).not.toHaveBeenCalled();
      vi.advanceTimersByTime(1);
      expect(play).toHaveBeenCalledTimes(1);
      expect(onFirstFrame).not.toHaveBeenCalled();
      presented!();
      expect(onFirstFrame).toHaveBeenCalledTimes(1);
    } finally {
      delete (HTMLVideoElement.prototype as { requestVideoFrameCallback?: unknown }).requestVideoFrameCallback;
    }
  });

  it("says a failed source when the mark has formed, not while it is forming", () => {
    const { v, onDone } = setup();
    const sources = v.querySelectorAll("source");
    sources[sources.length - 1].dispatchEvent(new Event("error"));
    expect(onDone).not.toHaveBeenCalled();
    formMark();
    expect(play).not.toHaveBeenCalled();
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("is done at once when play() is refused", async () => {
    play.mockImplementation(() => Promise.reject(new DOMException("blocked", "NotAllowedError")));
    const { v, onDone } = setup();
    formMark();
    v.dispatchEvent(new Event("loadeddata"));
    await vi.waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });

  it("is done at the ceiling when the film stalls", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    play.mockImplementation(() => new Promise<void>(() => {}));
    const { onDone } = setup();
    formMark();
    vi.advanceTimersByTime(FILM_CEILING_MS - 1);
    expect(onDone).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("does not play under reduced motion: the formed mark is the way in", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("reduce"), addEventListener() {}, removeEventListener() {} }));
    const { onDone, onFirstFrame } = setup();
    formMark();
    expect(play).not.toHaveBeenCalled();
    expect(onFirstFrame).not.toHaveBeenCalled();
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
