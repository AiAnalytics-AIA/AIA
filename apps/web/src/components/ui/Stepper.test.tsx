// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Stepper } from "./Stepper";

afterEach(cleanup);

const field = () => screen.getByRole("spinbutton", { name: "Počet respondentů" });
const plus = () => screen.getByRole("button", { name: "Zvýšit: Počet respondentů" }) as HTMLButtonElement;
const minus = () => screen.getByRole("button", { name: "Snížit: Počet respondentů" }) as HTMLButtonElement;

function n(value: number | null, onCommit = vi.fn(), extra: Record<string, unknown> = {}) {
  render(<Stepper label="Počet respondentů" value={value} onCommit={onCommit} min={50} max={5000} step={10} {...extra} />);
  return onCommit;
}

describe("Stepper (I2): bounded numbers, refused and never clamped", () => {
  it("states its bounds beside it and exposes them", () => {
    n(400);
    // The bounds are the field's description, so a screen reader hears them too.
    const bounds = document.getElementById(field().getAttribute("aria-describedby") ?? "");
    expect(bounds?.textContent).toBe("50–5 000 · ↑ ↓ o krok, Shift ×10");
    expect(field().getAttribute("aria-valuemin")).toBe("50");
    expect(field().getAttribute("aria-valuemax")).toBe("5000");
    expect(field().getAttribute("aria-valuenow")).toBe("400");
    expect((field() as HTMLInputElement).value).toBe("400");
  });

  it("refuses a typed 20 at the field and saves nothing: never stored as 50 (audit IA-1)", () => {
    const save = n(400);
    fireEvent.change(field(), { target: { value: "20" } });
    fireEvent.blur(field());
    expect(save).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toBe("Musí být 50–5 000; neuloženo.");
    expect(field().getAttribute("aria-invalid")).toBe("true");
    expect((field() as HTMLInputElement).value).toBe("20");
  });

  it("refuses an empty field and a decimal where whole numbers go (audit IA-2)", () => {
    const save = n(400);
    fireEvent.change(field(), { target: { value: "" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(screen.getByRole("alert").textContent).toBe("Zadejte číslo 50–5 000; neuloženo.");
    fireEvent.change(field(), { target: { value: "2,5" } });
    // Once said, the field is checked as it is typed (I9).
    expect(screen.getByRole("alert").textContent).toBe("Jen celé číslo; neuloženo.");
    expect(save).not.toHaveBeenCalled();
  });

  it("saves a valid typed value on Enter, Czech spaces included", () => {
    const save = n(400);
    fireEvent.change(field(), { target: { value: "1 200" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(save).toHaveBeenCalledWith(1200);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("Esc restores the saved value and clears the refusal", () => {
    const save = n(400);
    fireEvent.change(field(), { target: { value: "9" } });
    fireEvent.blur(field());
    fireEvent.keyDown(field(), { key: "Escape" });
    expect((field() as HTMLInputElement).value).toBe("400");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(save).not.toHaveBeenCalled();
  });

  it("steps by one step with the arrows and the buttons, by ten with Shift", () => {
    const save = n(400);
    fireEvent.keyDown(field(), { key: "ArrowUp" });
    expect(save).toHaveBeenLastCalledWith(410);
    fireEvent.keyDown(field(), { key: "ArrowDown", shiftKey: true });
    expect(save).toHaveBeenLastCalledWith(300);
    fireEvent.click(plus());
    expect(save).toHaveBeenLastCalledWith(410);
    fireEvent.click(minus(), { shiftKey: true });
    expect(save).toHaveBeenLastCalledWith(300);
  });

  it("disables a button at its bound", () => {
    n(5000);
    expect(plus().disabled).toBe(true);
    expect(minus().disabled).toBe(false);
    cleanup();
    n(50);
    expect(minus().disabled).toBe(true);
  });

  it("is one Tab stop: the buttons are for the pointer, the arrows for the keyboard", () => {
    n(400);
    expect(plus().tabIndex).toBe(-1);
    expect(minus().tabIndex).toBe(-1);
    expect(field().tabIndex).toBe(0);
  });

  it("tells its caller when it holds a refused value, and when it no longer does", () => {
    const problem = vi.fn();
    n(400, vi.fn(), { onProblem: problem });
    fireEvent.change(field(), { target: { value: "1" } });
    fireEvent.blur(field());
    expect(problem).toHaveBeenLastCalledWith("Musí být 50–5 000; neuloženo.");
    fireEvent.change(field(), { target: { value: "60" } });
    expect(problem).toHaveBeenLastCalledWith(null);
  });

  it("shows money with its unit and its decimals", () => {
    render(<Stepper label="Rozpočet" value={85} onCommit={() => {}} min={80.86} max={500} decimals={2} unit="USD" />);
    expect((screen.getByRole("spinbutton", { name: "Rozpočet" }) as HTMLInputElement).value).toBe("85,00");
    expect(screen.getByText("USD")).toBeTruthy();
    const money = screen.getByRole("spinbutton", { name: "Rozpočet" });
    expect(document.getElementById(money.getAttribute("aria-describedby") ?? "")?.textContent).toContain("80,86–500");
  });
});
