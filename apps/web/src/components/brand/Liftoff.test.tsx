// @vitest-environment jsdom
// The film is decoration and never in the way: it ends, fails, stalls or is
// skipped for reduced motion, and every one of those is the way in -- once.
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Liftoff, LIFTOFF_CEILING_MS, LIFTOFF_SOURCES } from "./Liftoff";

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

describe("Liftoff", () => {
  it("loads the film muted and hidden from assistive tech, and does not start it before it is told to", () => {
    const onDone = vi.fn();
    const { container } = render(<Liftoff playing={false} onDone={onDone} />);
    const v = video(container);
    expect([...v.querySelectorAll("source")].map((s) => s.getAttribute("src"))).toEqual(LIFTOFF_SOURCES.map((s) => s.src));
    expect(v.muted).toBe(true);
    expect(v.getAttribute("aria-hidden")).toBe("true");
    expect(v.getAttribute("preload")).toBe("auto");
    expect(play).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("plays when told to and is done when the film ends, once", () => {
    const onDone = vi.fn();
    const { container, rerender } = render(<Liftoff playing={false} onDone={onDone} />);
    rerender(<Liftoff playing onDone={onDone} />);
    expect(play).toHaveBeenCalledTimes(1);
    video(container).dispatchEvent(new Event("ended"));
    video(container).dispatchEvent(new Event("ended"));
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("is done at once when the film cannot play", async () => {
    play.mockImplementation(() => Promise.reject(new DOMException("blocked", "NotAllowedError")));
    const onDone = vi.fn();
    render(<Liftoff playing onDone={onDone} />);
    await vi.waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });

  it("is done when no source can be played", () => {
    const onDone = vi.fn();
    const { container } = render(<Liftoff playing onDone={onDone} />);
    const sources = video(container).querySelectorAll("source");
    sources[0].dispatchEvent(new Event("error"));
    expect(onDone).not.toHaveBeenCalled();
    sources[sources.length - 1].dispatchEvent(new Event("error"));
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("is done at the ceiling when the film stalls", () => {
    vi.useFakeTimers();
    play.mockImplementation(() => new Promise<void>(() => {}));
    const onDone = vi.fn();
    render(<Liftoff playing onDone={onDone} />);
    vi.advanceTimersByTime(LIFTOFF_CEILING_MS - 1);
    expect(onDone).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("does not play under reduced motion", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("reduce"), addEventListener() {}, removeEventListener() {} }));
    const onDone = vi.fn();
    render(<Liftoff playing onDone={onDone} />);
    expect(play).not.toHaveBeenCalled();
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
