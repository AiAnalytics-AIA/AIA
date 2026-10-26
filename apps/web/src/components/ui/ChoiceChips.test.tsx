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

  it("is touch-sized at phone width (44 px), the look contract's 24 px chip at radius 6 from 640 px", () => {
    render(<ChoiceChips label="Věk" options={AGES} value="a" onChange={() => {}} />);
    const [chosen, other] = screen.getAllByRole("radio");
    expect(other.className).toContain("min-h-11");
    expect(other.className).toContain("sm:min-h-6");
    expect(other.className).toContain("rounded-control");
    expect(other.className).not.toContain("rounded-pill");
    expect(chosen.className).toContain("bg-signal");
  });

  it("segmented: one bordered bar, the chosen segment filled, the same radio group and keys, touch-sized on a phone", () => {
    const onChange = vi.fn();
    render(<ChoiceChips look="segmented" small label="Věk" options={AGES} value={AGES[1].key} onChange={onChange} />);
    const group = screen.getByRole("radiogroup", { name: "Věk" });
    expect(group.getAttribute("data-look")).toBe("segmented");
    expect(group.className).toContain("border-border-strong");
    const radios = screen.getAllByRole("radio");
    expect(radios[1].getAttribute("aria-checked")).toBe("true");
    expect(radios[1].className).toContain("bg-signal");
    expect(radios[0].className).not.toContain("bg-signal");
    // Its own height where a page enlarges every button (Settings), 44 px on a phone, dense from 640 px.
    for (const r of radios) { expect(r.hasAttribute("data-dense")).toBe(true); expect(r.className).toContain("min-h-11"); expect(r.className).toContain("sm:min-h-7"); }
    fireEvent.keyDown(radios[1], { key: "ArrowRight" });
    expect(onChange).toHaveBeenCalled();
  });

  it("segmented, full size: a long label wraps and is never clipped; a small bar stays on one line (review of #870)", () => {
    const long = "Velmi dlouhý název klienta ".repeat(5).trim().slice(0, 120);
    expect(long).toHaveLength(120);
    const { unmount } = render(<ChoiceChips look="segmented" label="Klient" options={[{ key: "a", label: long }, { key: "b", label: "Krátký" }]} value={null} onChange={() => {}} />);
    const radio = screen.getByRole("radio", { name: long });
    expect(radio.textContent).toBe(long);
    expect(radio.className).not.toContain("whitespace-nowrap");
    expect(radio.className).not.toContain("truncate");
    expect(radio.className).toContain("break-words");
    unmount();
    render(<ChoiceChips look="segmented" small label="Role" options={AGES} value={null} onChange={() => {}} />);
    expect(screen.getAllByRole("radio")[0].className).toContain("whitespace-nowrap");
  });
});
