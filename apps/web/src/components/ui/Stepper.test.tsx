// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
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
    // The caller never moves `value` here: each press steps from what the last one sent.
    const save = n(400);
    fireEvent.keyDown(field(), { key: "ArrowUp" });
    expect(save).toHaveBeenLastCalledWith(410);
    fireEvent.keyDown(field(), { key: "ArrowDown", shiftKey: true });
    expect(save).toHaveBeenLastCalledWith(310);
    fireEvent.click(plus());
    expect(save).toHaveBeenLastCalledWith(320);
    fireEvent.click(minus(), { shiftKey: true });
    expect(save).toHaveBeenLastCalledWith(220);
    expect((field() as HTMLInputElement).value).toBe("220");
  });

  it("commits a button press once, stepped from the typed draft (Codex #532)", () => {
    const save = vi.fn();
    render(<Stepper label="Počet" value={80} onCommit={save} min={0} max={500} />);
    const input = screen.getByRole("spinbutton", { name: "Počet" });
    act(() => input.focus());
    fireEvent.change(input, { target: { value: "90" } });
    const up = screen.getByRole("button", { name: "Zvýšit: Počet" });
    // A browser moves focus on mousedown unless it is prevented; then the field would blur.
    const focusMoves = fireEvent.mouseDown(up);
    if (focusMoves) fireEvent.blur(input);
    fireEvent.mouseUp(up);
    fireEvent.click(up);
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith(91);
    expect(document.activeElement).toBe(input);
  });

  it("steps from what it sent while an async parent has not answered yet, then follows the parent (Codex #532)", async () => {
    const calls: number[] = [];
    let answer!: () => void;
    function Parent() {
      const [value, setValue] = useState(80);
      return (
        <Stepper
          label="Počet"
          value={value}
          min={0}
          max={500}
          onCommit={(v) => {
            calls.push(v);
            // Saved on the server first; the parent's value moves only when it answers.
            answer = () => setValue(v);
          }}
        />
      );
    }
    render(<Parent />);
    const input = screen.getByRole("spinbutton", { name: "Počet" }) as HTMLInputElement;
    const up = screen.getByRole("button", { name: "Zvýšit: Počet" });
    fireEvent.change(input, { target: { value: "90" } });
    fireEvent.click(up);
    fireEvent.click(up);
    expect(calls).toEqual([91, 92]);
    expect(input.value).toBe("92");
    await act(async () => answer());
    expect(input.value).toBe("92");
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(calls).toEqual([91, 92, 93]);
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

  it("saves an in-place edit of a displayed negative value, its printed minus sign included (Codex #532)", () => {
    const save = vi.fn();
    render(<Stepper label="Posun" value={-3} onCommit={save} min={-10} max={10} />);
    const input = screen.getByRole("spinbutton", { name: "Posun" }) as HTMLInputElement;
    expect(input.value).toBe("−3");
    // The person edits the shown text: the digit changes, the printed minus stays.
    fireEvent.change(input, { target: { value: input.value.replace("3", "5") } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(save).toHaveBeenCalledWith(-5);
  });

  it("announces what the field holds now, not the saved value behind a draft (Codex #532)", () => {
    render(<Stepper label="Rozpočet" value={80} onCommit={() => {}} min={50} max={500} decimals={2} unit="USD" />);
    const money = screen.getByRole("spinbutton", { name: "Rozpočet" });
    expect(money.getAttribute("aria-valuetext")).toBe("80,00 USD");
    fireEvent.change(money, { target: { value: "90" } });
    expect(money.getAttribute("aria-valuenow")).toBe("90");
    expect(money.getAttribute("aria-valuetext")).toBe("90,00 USD");
    expect(money.hasAttribute("aria-invalid")).toBe(false);
    // Garbage: nothing is announced as the value; the field says it is invalid.
    fireEvent.change(money, { target: { value: "abc" } });
    expect(money.hasAttribute("aria-valuenow")).toBe(false);
    expect(money.hasAttribute("aria-valuetext")).toBe(false);
    expect(money.getAttribute("aria-invalid")).toBe("true");
    // Out of range is not announced either; after the refused commit the words join the description.
    fireEvent.change(money, { target: { value: "9" } });
    expect(money.hasAttribute("aria-valuetext")).toBe(false);
    fireEvent.blur(money);
    const described = (money.getAttribute("aria-describedby") ?? "").split(" ").map((id) => document.getElementById(id)?.textContent);
    expect(described[0]).toBe("Musí být 50–500 USD; neuloženo.");
    // Esc: back to the saved value, announced as it.
    fireEvent.keyDown(money, { key: "Escape" });
    expect(money.getAttribute("aria-valuetext")).toBe("80,00 USD");
    expect(money.hasAttribute("aria-invalid")).toBe(false);
  });

  it("shows money with its unit and its decimals", () => {
    render(<Stepper label="Rozpočet" value={85} onCommit={() => {}} min={80.86} max={500} decimals={2} unit="USD" />);
    expect((screen.getByRole("spinbutton", { name: "Rozpočet" }) as HTMLInputElement).value).toBe("85,00");
    expect(screen.getByText("USD")).toBeTruthy();
    const money = screen.getByRole("spinbutton", { name: "Rozpočet" });
    // The unit reaches a screen reader with the bounds and the value (Codex #532).
    expect(document.getElementById(money.getAttribute("aria-describedby") ?? "")?.textContent).toBe("80,86–500 USD · ↑ ↓ o krok, Shift ×10");
    expect(money.getAttribute("aria-valuetext")).toBe("85,00 USD");
  });
});
