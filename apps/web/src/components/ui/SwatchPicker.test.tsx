// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SwatchPicker } from "./SwatchPicker";

afterEach(cleanup);

const COLOURS = ["BLUE", "TEAL", "GREEN"] as const;
type C = (typeof COLOURS)[number];
const SWATCH: Record<C, string> = { BLUE: "bg-hue-blue", TEAL: "bg-hue-teal", GREEN: "bg-hue-green" };
const NAME: Record<C, string> = { BLUE: "Modrá", TEAL: "Tyrkysová", GREEN: "Zelená" };
const props = { colours: COLOURS, swatch: SWATCH, name: (c: C) => NAME[c], label: "Barva štítku" };

describe("SwatchPicker (I3, I5): a colour chosen by its swatch, named in words", () => {
  it("inline: a radio group of named swatches painted by token utilities; arrows choose", () => {
    const pick = vi.fn();
    render(<SwatchPicker {...props} value="TEAL" onChange={pick} />);
    expect(screen.getByRole("radiogroup", { name: "Barva štítku" })).toBeTruthy();
    const teal = screen.getByRole("radio", { name: "Tyrkysová" });
    expect(teal.getAttribute("aria-checked")).toBe("true");
    expect(teal.tabIndex).toBe(0);
    expect(teal.querySelector("span")?.className).toContain("bg-hue-teal");
    fireEvent.keyDown(teal, { key: "ArrowRight" });
    expect(pick).toHaveBeenLastCalledWith("GREEN");
    fireEvent.click(screen.getByRole("radio", { name: "Modrá" }));
    expect(pick).toHaveBeenLastCalledWith("BLUE");
  });

  it("popover: one swatch button; arrows only move, a click chooses once and closes (audit IA-6)", () => {
    const pick = vi.fn();
    render(<SwatchPicker {...props} popover value="BLUE" onChange={pick} />);
    const trigger = screen.getByRole("button", { name: "Barva štítku: Modrá" });
    expect(screen.queryByRole("radiogroup")).toBeNull();
    fireEvent.click(trigger);
    const blue = screen.getByRole("radio", { name: "Modrá" });
    expect(document.activeElement).toBe(blue);
    fireEvent.keyDown(blue, { key: "ArrowRight" });
    expect(pick).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("radio", { name: "Zelená" }));
    expect(pick).toHaveBeenCalledTimes(1);
    expect(pick).toHaveBeenCalledWith("GREEN");
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("popover: choosing the colour it already has changes nothing; Esc closes", () => {
    const pick = vi.fn();
    render(<SwatchPicker {...props} popover value="BLUE" onChange={pick} />);
    fireEvent.click(screen.getByRole("button", { name: "Barva štítku: Modrá" }));
    fireEvent.click(screen.getByRole("radio", { name: "Modrá" }));
    expect(pick).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Barva štítku: Modrá" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });
});
