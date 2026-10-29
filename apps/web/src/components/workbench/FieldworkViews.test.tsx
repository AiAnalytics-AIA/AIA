// @vitest-environment jsdom
// Sběr dat's two views (FLD9, spec sber F1): the header's "Pohled" says which view is open, opens
// the other, and is one Tab stop with the arrows moving inside it.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FieldworkViews } from "./FieldworkViews";

afterEach(cleanup);

describe("FieldworkViews", () => {
  it("marks the open view selected, and follows the route", () => {
    const { rerender } = render(<FieldworkViews current="run" open={() => {}} />);
    expect(screen.getByRole("tablist", { name: "Pohled" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Kontrola a spuštění" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tab", { name: "Průběh" }).getAttribute("aria-selected")).toBe("false");
    rerender(<FieldworkViews current="progress" open={() => {}} />);
    expect(screen.getByRole("tab", { name: "Průběh" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tab", { name: "Kontrola a spuštění" }).getAttribute("aria-selected")).toBe("false");
  });

  it("opens the other view on a click, and nothing on the open one", () => {
    const open = vi.fn();
    render(<FieldworkViews current="run" open={open} />);
    fireEvent.click(screen.getByRole("tab", { name: "Kontrola a spuštění" }));
    expect(open).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("tab", { name: "Průběh" }));
    expect(open).toHaveBeenCalledWith("progress");
  });

  it("is one Tab stop; the arrows move between the views without opening one", () => {
    const open = vi.fn();
    render(<FieldworkViews current="progress" open={open} />);
    const check = screen.getByRole("tab", { name: "Kontrola a spuštění" });
    const progress = screen.getByRole("tab", { name: "Průběh" });
    expect(progress.tabIndex).toBe(0);
    expect(check.tabIndex).toBe(-1);
    progress.focus();
    fireEvent.keyDown(progress, { key: "ArrowRight" });
    expect(document.activeElement).toBe(check);
    fireEvent.keyDown(check, { key: "ArrowLeft" });
    expect(document.activeElement).toBe(progress);
    expect(open).not.toHaveBeenCalled();
  });
});
