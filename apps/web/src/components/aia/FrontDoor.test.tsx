// @vitest-environment jsdom
// The front door's frame: Graphite whatever the theme, the identity named once,
// the field decorative, the page's content under its heading; and with a handoff,
// the film waiting beside the field until it takes over.
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MARK_FORMED_EVENT } from "@/lib/dot-field";
import { FrontDoor } from "./FrontDoor";

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("FrontDoor", () => {
  it("is Graphite, names the product once as an image, and keeps the field from assistive tech", () => {
    const { container } = render(<FrontDoor title="Přihlášení"><p>obsah</p></FrontDoor>);
    const root = container.firstElementChild as HTMLElement;
    expect(root.dataset.theme).toBe("dark");
    // The identity's cyan is the signal here: the wordmark's point, the button, the focus ring.
    expect(root.style.getPropertyValue("--signal")).toBe("var(--brand-apex)");
    expect(root.style.getPropertyValue("--focus-ring")).toBe("var(--brand-apex)");
    expect(screen.getAllByRole("img", { name: "AIA" })).toHaveLength(1);
    expect(screen.getByText("Agentic AI Analytics")).toBeTruthy();
    expect(screen.getByText("Výzkum a simulace nad kalibrovanou syntetickou populací.")).toBeTruthy();
    expect(container.querySelector("canvas")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector("video")).toBeNull();
  });

  it("labels the section with its heading when there is one", () => {
    render(<FrontDoor title="Přihlášení"><p>obsah</p></FrontDoor>);
    const heading = screen.getByRole("heading", { level: 1, name: "Přihlášení" });
    expect(screen.getByRole("region", { name: "Přihlášení" }).contains(screen.getByText("obsah"))).toBe(true);
    expect(heading).toBeTruthy();
  });

  it("renders without a heading for the transient pages", () => {
    render(<FrontDoor><p role="status">Odhlašuji…</p></FrontDoor>);
    expect(screen.queryByRole("heading")).toBeNull();
    expect(screen.getByRole("status").textContent).toBe("Odhlašuji…");
  });

  it("readies the film, fades to the film's ground when leaving, and lets the field go on the film's first frame", async () => {
    const onDone = vi.fn();
    const { container, rerender } = render(<FrontDoor handoff={{ leaving: false, onDone }}><p>obsah</p></FrontDoor>);
    const root = container.firstElementChild as HTMLElement;
    expect(root.dataset.handoff).toBe("ready");
    expect(container.querySelector("video")?.dataset.film).toBe("standby");
    rerender(<FrontDoor handoff={{ leaving: true, onDone }}><p>obsah</p></FrontDoor>);
    expect(root.dataset.handoff).toBe("leaving");
    expect(root.className).toContain("bg-brand-stage");
    expect(container.querySelector("aside")?.className).toContain("bg-brand-stage");
    expect(container.querySelector("canvas")?.dataset.dotField).toBe("leaving");
    act(() => void window.dispatchEvent(new CustomEvent(MARK_FORMED_EVENT)));
    expect(container.querySelector("canvas")).not.toBeNull();
    act(() => void container.querySelector("video")!.dispatchEvent(new Event("loadeddata")));
    await vi.waitFor(() => expect(container.querySelector("canvas")).toBeNull());
    expect(onDone).not.toHaveBeenCalled();
    container.querySelector("video")!.dispatchEvent(new Event("ended"));
    expect(onDone).toHaveBeenCalledTimes(1);
  });
});
