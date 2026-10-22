// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MenuButton, menuSide } from "./MenuButton";

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

  it("as a row's ⋯ shows its icon alone, named by what it acts on, and the menu carries that name (chunk 2)", () => {
    render(<MenuButton hideLabel align="end" label="Akce složky Archiv" items={ITEMS} onSelect={() => {}} />);
    const more = screen.getByRole("button", { name: "Akce složky Archiv" });
    expect(more.textContent).toBe("");
    fireEvent.click(more);
    const menu = screen.getByRole("menu", { name: "Akce složky Archiv" });
    // Opened from the row's end: leftwards from the button's right edge.
    expect(menu.className).toContain("right-0");
    expect(menu.className).not.toContain("left-0");
  });
});

describe("menuSide: a menu stays inside the viewport", () => {
  it("opens the side asked for when it fits, else the other side", () => {
    expect(menuSide("start", { left: 20, right: 120 }, 1440)).toBe("start");
    // A button wrapped to the right of a bar at 390 px: rightwards would run off the page.
    expect(menuSide("start", { left: 300, right: 380 }, 390)).toBe("end");
    expect(menuSide("end", { left: 300, right: 380 }, 390)).toBe("end");
    // At a row's end near the left edge, leftwards would run off: it opens rightwards.
    expect(menuSide("end", { left: 10, right: 40 }, 390)).toBe("start");
    // Neither fits (a viewport narrower than the menu): the side asked for.
    expect(menuSide("start", { left: 50, right: 100 }, 150)).toBe("start");
    expect(menuSide("end", { left: 50, right: 100 }, 150)).toBe("end");
  });
});
