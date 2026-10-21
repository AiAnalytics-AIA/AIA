// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MenuButton } from "./MenuButton";

afterEach(cleanup);

const ITEMS = [
  { key: "f1", label: "Trh a konkurence" },
  { key: "f2", label: "Smlouvy", disabled: true },
  { key: "f3", label: "Archiv" },
] as const;

const button = () => screen.getByRole("button", { name: "Přesunout do složky" });

describe("MenuButton (I3): an action is a menu, never a select that fires on change", () => {
  it("opens a menu with focus on the first item; arrows move without acting (audit IA-6)", async () => {
    const act = vi.fn();
    render(<MenuButton label="Přesunout do složky" items={ITEMS} onSelect={act} />);
    expect(button().getAttribute("aria-haspopup")).toBe("menu");
    fireEvent.click(button());
    expect(button().getAttribute("aria-expanded")).toBe("true");
    const items = screen.getAllByRole("menuitem");
    await waitFor(() => expect(document.activeElement).toBe(items[0]));
    fireEvent.keyDown(items[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[2]);
    fireEvent.keyDown(items[2], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(items[0], { key: "End" });
    expect(document.activeElement).toBe(items[2]);
    expect(act).not.toHaveBeenCalled();
  });

  it("does the chosen item once, closes, and gives focus back to the button", () => {
    const act = vi.fn();
    render(<MenuButton label="Přesunout do složky" items={ITEMS} onSelect={act} />);
    fireEvent.click(button());
    fireEvent.click(screen.getByRole("menuitem", { name: "Archiv" }));
    expect(act).toHaveBeenCalledTimes(1);
    expect(act).toHaveBeenCalledWith("f3");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(button());
  });

  it("closes on Esc and on a press outside, doing nothing", () => {
    const act = vi.fn();
    render(
      <>
        <MenuButton label="Přesunout do složky" items={ITEMS} onSelect={act} />
        <p>venku</p>
      </>,
    );
    fireEvent.click(button());
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(button());
    fireEvent.click(button());
    fireEvent.pointerDown(screen.getByText("venku"));
    expect(screen.queryByRole("menu")).toBeNull();
    expect(act).not.toHaveBeenCalled();
  });

  it("opens from the keyboard with ↓ on the first item and ↑ on the last", async () => {
    render(<MenuButton label="Přesunout do složky" items={ITEMS} onSelect={() => {}} />);
    fireEvent.keyDown(button(), { key: "ArrowUp" });
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Archiv" })));
  });

  it("says when it has nothing to offer", () => {
    render(<MenuButton label="Přidat štítek" items={[]} onSelect={() => {}} empty="Žádné štítky" />);
    fireEvent.click(screen.getByRole("button", { name: "Přidat štítek" }));
    expect(screen.getByText("Žádné štítky")).toBeTruthy();
  });
});
