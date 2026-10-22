// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChoiceChips } from "./ChoiceChips";

afterEach(cleanup);

const AGES = [
  { key: "a", label: "18–29" },
  { key: "b", label: "30–45" },
  { key: "c", label: "46–60", disabled: true },
  { key: "d", label: "61+" },
] as const;

describe("ChoiceChips (I3, I11)", () => {
  it("single: a radio group, one Tab stop, arrows move and choose, skipping a disabled chip", () => {
    const pick = vi.fn();
    render(<ChoiceChips label="Věková skupina" options={AGES} value="b" onChange={pick} />);
    const radios = screen.getAllByRole("radio");
    expect(screen.getByRole("radiogroup", { name: "Věková skupina" })).toBeTruthy();
    expect(radios.map((r) => r.tabIndex)).toEqual([-1, 0, -1, -1]);
    expect(radios[1].getAttribute("aria-checked")).toBe("true");
    fireEvent.keyDown(radios[1], { key: "ArrowRight" });
    expect(pick).toHaveBeenLastCalledWith("d");
    expect(document.activeElement).toBe(radios[3]);
    fireEvent.click(radios[0]);
    expect(pick).toHaveBeenLastCalledWith("a");
    // Choosing the chosen one again changes nothing.
    pick.mockClear();
    fireEvent.click(radios[1]);
    expect(pick).not.toHaveBeenCalled();
  });

  it("multi: toggles in the options' order; the arrows only move", () => {
    const pick = vi.fn();
    render(<ChoiceChips multiple label="Kraje" options={AGES} value={["d"]} onChange={pick} />);
    const chips = screen.getAllByRole("button");
    expect(chips[3].getAttribute("aria-pressed")).toBe("true");
    expect(chips.map((c) => c.tabIndex)).toEqual([-1, -1, -1, 0]);
    fireEvent.click(chips[0]);
    expect(pick).toHaveBeenLastCalledWith(["a", "d"]);
    fireEvent.click(chips[3]);
    expect(pick).toHaveBeenLastCalledWith([]);
    pick.mockClear();
    fireEvent.keyDown(chips[3], { key: "ArrowLeft" });
    expect(pick).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(chips[1]);
  });

  it("gives Tab to the first enabled chip when none is chosen", () => {
    render(<ChoiceChips label="Věk" options={AGES} value={null} onChange={() => {}} />);
    expect(screen.getAllByRole("radio").map((r) => r.tabIndex)).toEqual([0, -1, -1, -1]);
  });

  it("is touch-sized at phone width (44 px), comfortable from 640 px", () => {
    render(<ChoiceChips label="Věk" options={AGES} value={null} onChange={() => {}} />);
    expect(screen.getAllByRole("radio")[0].className).toContain("min-h-11");
    expect(screen.getAllByRole("radio")[0].className).toContain("sm:min-h-8");
  });
});
