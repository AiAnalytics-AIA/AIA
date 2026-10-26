// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Switch } from "./Switch";

afterEach(cleanup);

describe("Switch", () => {
  it("is a named switch that reports the other state when pressed", () => {
    const onChange = vi.fn();
    render(<Switch on={false} onChange={onChange} label="Štítek Metodik" />);
    const sw = screen.getByRole("switch", { name: "Štítek Metodik" });
    expect(sw.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(sw);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("says its state and does nothing while disabled", () => {
    const onChange = vi.fn();
    render(<Switch on label="Štítek Metodik" disabled onChange={onChange} />);
    const sw = screen.getByRole("switch", { name: "Štítek Metodik" });
    expect(sw.getAttribute("aria-checked")).toBe("true");
    expect((sw as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(sw);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("draws the look contract's 40 x 24 track, round, signal when on", () => {
    const { rerender } = render(<Switch on={false} onChange={() => {}} label="Štítek Metodik" />);
    const track = () => screen.getByRole("switch").querySelector("[data-switch-track]") as HTMLElement;
    expect(track().className).toContain("h-6");
    expect(track().className).toContain("w-10");
    expect(track().className).toContain("rounded-pill");
    expect(track().className).not.toContain("bg-signal");
    rerender(<Switch on onChange={() => {}} label="Štítek Metodik" />);
    expect(track().className).toContain("bg-signal");
  });

  it("shows its words beside the track when asked, and keeps them as its name", () => {
    render(<Switch on={false} onChange={() => {}} label="Technické údaje" showLabel />);
    expect(screen.getByRole("switch", { name: "Technické údaje" }).textContent).toBe("Technické údaje");
  });
});
