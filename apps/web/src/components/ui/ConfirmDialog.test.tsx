// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

// jsdom has <dialog> without showModal/close: the modal's open state, as a browser sets it.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
    this.querySelector<HTMLElement>("button:not([disabled]), input:not([disabled]), [tabindex]")?.focus();
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
});
afterEach(cleanup);

describe("ConfirmDialog (I7b)", () => {
  it("names the change and its consequence, focuses the safe choice, and names the act", () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog open title="Schválit pravidlo rešerše" rows={[{ label: "V platnosti", value: "365 dní" }, { label: "Schválíte", value: "90 dní" }]}
      text="Platí pro běhy zařazené od teď." confirmLabel="Schválit" marker="test-confirm" onConfirm={onConfirm} onCancel={() => {}} />);
    expect(screen.getByRole("heading", { name: "Schválit pravidlo rešerše" })).toBeTruthy();
    expect(screen.getByText("365 dní")).toBeTruthy();
    expect(screen.getByText("90 dní")).toBeTruthy();
    expect(document.activeElement?.textContent).toBe("Zrušit");
    expect(document.querySelector("[data-test-confirm]")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Schválit" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("cancels on Esc unless busy, and says a refusal inside", () => {
    const onCancel = vi.fn();
    const { rerender } = render(<ConfirmDialog open title="T" text="x" confirmLabel="Ano" onConfirm={() => {}} onCancel={onCancel} />);
    fireEvent(document.querySelector("dialog") as HTMLDialogElement, new Event("cancel", { cancelable: true }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    rerender(<ConfirmDialog open busy title="T" text="x" confirmLabel="Ano" error="HTTP 403 · forbidden" onConfirm={() => {}} onCancel={onCancel} />);
    fireEvent(document.querySelector("dialog") as HTMLDialogElement, new Event("cancel", { cancelable: true }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert").textContent).toBe("HTTP 403 · forbidden");
  });

  it("is the look contract's dialog: 560 px, radius 10, padding 24, over a 10 % ink scrim", () => {
    render(<ConfirmDialog open title="T" text="x" confirmLabel="Ano" onConfirm={() => {}} onCancel={() => {}} />);
    const d = document.querySelector("dialog") as HTMLDialogElement;
    expect(d.className).toContain("w-[min(35rem,calc(100vw-2rem))]");
    expect(d.className).toContain("rounded-panel");
    expect(d.className).toContain("backdrop:bg-ink/10");
    expect((d.firstElementChild as HTMLElement).className).toContain("p-6");
  });
});
