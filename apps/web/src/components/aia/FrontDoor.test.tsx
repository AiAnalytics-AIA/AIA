// @vitest-environment jsdom
// The front door's frame: the identity is named aloud, the motif is not, and the
// page's own content sits under its heading.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { FrontDoor } from "./FrontDoor";

afterEach(cleanup);

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
});
