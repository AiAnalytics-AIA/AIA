// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InlineCreateRow } from "./InlineCreateRow";

afterEach(cleanup);

const row = () => screen.getByRole("textbox", { name: "Nová složka" }) as HTMLInputElement;
const openRow = () => fireEvent.click(screen.getByRole("button", { name: "Nová složka" }));

describe("InlineCreateRow (I5): created in the list, no dialog", () => {
  it("opens a focused row in place of the button; Enter creates and opens the next empty row", async () => {
    const create = vi.fn(async () => undefined);
    render(<InlineCreateRow label="Nová složka" onCreate={create} />);
    openRow();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(row());
    fireEvent.change(row(), { target: { value: " Konkurence   2026 " } });
    fireEvent.keyDown(row(), { key: "Enter" });
    await waitFor(() => expect(create).toHaveBeenCalledWith("Konkurence 2026"));
    await waitFor(() => expect(row().value).toBe(""));
    fireEvent.change(row(), { target: { value: "Smlouvy" } });
    fireEvent.keyDown(row(), { key: "Enter" });
    await waitFor(() => expect(create).toHaveBeenLastCalledWith("Smlouvy"));
  });

  it("closes after one creation when asked", async () => {
    render(<InlineCreateRow label="Nová složka" next={false} onCreate={() => true} />);
    openRow();
    fireEvent.change(row(), { target: { value: "A" } });
    fireEvent.keyDown(row(), { key: "Enter" });
    await waitFor(() => expect(screen.getByRole("button", { name: "Nová složka" })).toBeTruthy());
  });

  it("says a taken or too long name at the row as it is typed, and sends nothing", () => {
    const create = vi.fn();
    render(<InlineCreateRow label="Nová složka" existing={["Smlouvy"]} maxLength={10} onCreate={create} />);
    openRow();
    fireEvent.change(row(), { target: { value: "smlouvy" } });
    expect(screen.getByRole("alert").textContent).toBe("„Smlouvy“ už existuje.");
    expect(row().getAttribute("aria-invalid")).toBe("true");
    fireEvent.keyDown(row(), { key: "Enter" });
    fireEvent.change(row(), { target: { value: "příliš dlouhý název" } });
    expect(screen.getByRole("alert").textContent).toBe("Nejvýš 10 znaků.");
    fireEvent.keyDown(row(), { key: "Enter" });
    expect(create).not.toHaveBeenCalled();
  });

  it("says an empty row only once Enter was pressed on it", () => {
    render(<InlineCreateRow label="Nová složka" onCreate={vi.fn()} />);
    openRow();
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.keyDown(row(), { key: "Enter" });
    expect(screen.getByRole("alert").textContent).toBe("Napište název.");
  });

  it("says the server's refusal at the row and keeps the name", async () => {
    render(<InlineCreateRow label="Nová složka" onCreate={async () => "Takový název už u tohoto klienta je."} />);
    openRow();
    fireEvent.change(row(), { target: { value: "Archiv" } });
    fireEvent.keyDown(row(), { key: "Enter" });
    expect((await screen.findByRole("alert")).textContent).toBe("Takový název už u tohoto klienta je.");
    expect(row().value).toBe("Archiv");
    // Typing again clears the refusal.
    fireEvent.change(row(), { target: { value: "Archiv 2" } });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("says a failure that has no words of its own", async () => {
    render(<InlineCreateRow label="Nová složka" onCreate={() => Promise.reject(new Error("network"))} />);
    openRow();
    fireEvent.change(row(), { target: { value: "Archiv" } });
    fireEvent.keyDown(row(), { key: "Enter" });
    expect((await screen.findByRole("alert")).textContent).toBe("Nevytvořeno. Zkuste to znovu.");
  });

  it("cancels on Esc, and on leaving it empty; a typed name survives a blur", () => {
    render(<InlineCreateRow label="Nová složka" onCreate={vi.fn()} />);
    openRow();
    fireEvent.keyDown(row(), { key: "Escape" });
    expect(screen.getByRole("button", { name: "Nová složka" })).toBeTruthy();
    openRow();
    fireEvent.blur(row());
    expect(screen.getByRole("button", { name: "Nová složka" })).toBeTruthy();
    openRow();
    fireEvent.change(row(), { target: { value: "Rozepsané" } });
    fireEvent.blur(row());
    expect(row().value).toBe("Rozepsané");
  });
});
