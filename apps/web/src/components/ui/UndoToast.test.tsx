// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UNDO_MS, type UndoOffer, UndoToast, useUndo } from "./UndoToast";

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

// A page that deletes things: each button stands for a deletion that offers its undo.
const pending: UndoOffer[] = [];
function Host() {
  const undo = useUndo();
  return (
    <>
      <button type="button" onClick={() => undo.offer(pending.shift()!)}>smazat</button>
      <UndoToast offer={undo.current} onDone={undo.clear} />
    </>
  );
}
const offerIt = (o: UndoOffer) => {
  pending.push(o);
  fireEvent.click(screen.getByRole("button", { name: "smazat" }));
};

describe("UndoToast (I6): Vrátit for 8 s, one at a time", () => {
  it("offers Vrátit for 8 s and then goes, the deletion standing", () => {
    const undo = vi.fn();
    render(<Host />);
    act(() => offerIt({ message: "Složka „Archiv“ smazána", undo }));
    expect(UNDO_MS).toBe(8000);
    expect(screen.getByRole("status").textContent).toContain("Složka „Archiv“ smazána");
    act(() => vi.advanceTimersByTime(7999));
    expect(screen.getByRole("button", { name: "Vrátit" })).toBeTruthy();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByRole("status")).toBeNull();
    expect(undo).not.toHaveBeenCalled();
  });

  it("takes it back once on Vrátit and goes", () => {
    const undo = vi.fn();
    render(<Host />);
    act(() => offerIt({ message: "Smazáno", undo }));
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    expect(undo).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("shows one offer at a time: a new one replaces the last and runs its own 8 s", () => {
    const first = vi.fn();
    const second = vi.fn();
    render(<Host />);
    act(() => offerIt({ message: "První", undo: first }));
    act(() => vi.advanceTimersByTime(5000));
    act(() => offerIt({ message: "Druhá", undo: second }));
    expect(screen.queryByText("První")).toBeNull();
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByText("Druhá")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    expect(second).toHaveBeenCalledTimes(1);
    expect(first).not.toHaveBeenCalled();
  });

  it("stops the time while the pointer is on it, and runs it again in full after", () => {
    render(<Host />);
    act(() => offerIt({ message: "Smazáno", undo: () => {} }));
    fireEvent.pointerEnter(screen.getByRole("status"));
    act(() => vi.advanceTimersByTime(20000));
    expect(screen.getByRole("status")).toBeTruthy();
    fireEvent.pointerLeave(screen.getByRole("status"));
    act(() => vi.advanceTimersByTime(7999));
    expect(screen.getByRole("status")).toBeTruthy();
    act(() => vi.advanceTimersByTime(1));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("a hold made by focus ends with its offer: the next offer still expires (Codex #532)", () => {
    render(<Host />);
    act(() => offerIt({ message: "První", undo: () => {} }));
    const undo = screen.getByRole("button", { name: "Vrátit" });
    act(() => undo.focus());
    // Activating removes the toast with focus inside it; no blur event follows.
    fireEvent.click(undo);
    expect(screen.queryByRole("status")).toBeNull();
    act(() => offerIt({ message: "Druhá", undo: () => {} }));
    act(() => vi.advanceTimersByTime(UNDO_MS));
    expect(screen.queryByRole("status")).toBeNull();

    // The same through "Zavřít".
    act(() => offerIt({ message: "Třetí", undo: () => {} }));
    const close = screen.getByRole("button", { name: "Zavřít" });
    act(() => close.focus());
    fireEvent.click(close);
    act(() => offerIt({ message: "Čtvrtá", undo: () => {} }));
    act(() => vi.advanceTimersByTime(UNDO_MS));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("can be closed without undoing", () => {
    const undo = vi.fn();
    render(<Host />);
    act(() => offerIt({ message: "Smazáno", undo }));
    fireEvent.click(screen.getByRole("button", { name: "Zavřít" }));
    expect(screen.queryByRole("status")).toBeNull();
    expect(undo).not.toHaveBeenCalled();
  });
});
