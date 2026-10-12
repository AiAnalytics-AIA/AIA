// @vitest-environment jsdom
// The front door's frame: the identity is named aloud, the motif is not, and the
// page's own content sits under its heading.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FrontDoor } from "./FrontDoor";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("FrontDoor", () => {
  it("names the product once, as an image, and hides the mark and the lattice from assistive tech", () => {
    const { container } = render(<FrontDoor title="Přihlášení"><p>obsah</p></FrontDoor>);
    expect(screen.getAllByRole("img", { name: "AIA" })).toHaveLength(1);
    expect(screen.getByText("Agentic AI Analytics")).toBeTruthy();
    expect(container.querySelectorAll('svg[aria-hidden="true"]')).toHaveLength(2);
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

  it("has no film unless a lift-off is asked for", () => {
    const { container } = render(<FrontDoor title="Přihlášení"><p>obsah</p></FrontDoor>);
    expect(container.querySelector("video")).toBeNull();
    expect(container.querySelector("aside")?.hasAttribute("data-liftoff")).toBe(false);
  });

  it("readies the film over the mark, then gives the mark's place to it on the film's own ground", () => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    const onDone = vi.fn();
    const { container, rerender } = render(<FrontDoor liftoff={{ playing: false, onDone }}><p>obsah</p></FrontDoor>);
    const aside = container.querySelector("aside") as HTMLElement;
    expect(aside.dataset.liftoff).toBe("ready");
    expect(container.querySelector("video")?.dataset.liftoff).toBe("loading");
    rerender(<FrontDoor liftoff={{ playing: true, onDone }}><p>obsah</p></FrontDoor>);
    expect(aside.dataset.liftoff).toBe("playing");
    expect(container.querySelector(".bg-brand-stage")?.className).toContain("opacity-100");
    // The film sits in the mark's own slot, so it plays where the mark was.
    const mark = container.querySelector('svg[viewBox="0 0 32 32"]') as SVGElement;
    expect(mark.parentElement?.contains(container.querySelector("video"))).toBe(true);
    expect(mark.getAttribute("class")).toContain("opacity-0");
    // The name stays named once, as an image.
    expect(screen.getAllByRole("img", { name: "AIA" })).toHaveLength(1);
  });
});
