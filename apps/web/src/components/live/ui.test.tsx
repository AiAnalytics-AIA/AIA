// @vitest-environment jsdom
// A run's or a step's status chip on the live /studies pages: done reads as an ink ✓, never green;
// green is the interface's colour for "in force" alone (the product owner, 2026-10-23, Q83).
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Status } from "./ui";

afterEach(cleanup);

describe("a status chip", () => {
  it("shows a finished run or step as an ink ✓, never green", () => {
    for (const value of ["COMPLETED", "SUCCEEDED"]) {
      render(<Status value={value} />);
      const chip = screen.getByText(new RegExp(value)).closest("span") as HTMLElement;
      expect(chip.textContent).toBe(`✓ ${value}`);
      expect(chip.className).not.toMatch(/emerald|green|in-force/);
      cleanup();
    }
  });

  it("marks only a finished state with ✓", () => {
    render(<Status value="RUNNING" />);
    expect(screen.getByText("RUNNING").textContent).toBe("RUNNING");
  });
});
