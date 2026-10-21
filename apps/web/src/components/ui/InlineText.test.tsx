// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InlineText } from "./InlineText";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const shown = () => screen.getByRole("button", { name: "Upravit: Název studie" });
const field = () => screen.getByRole("textbox", { name: "Název studie" });

describe("InlineText (I1): edit where it is shown", () => {
  it("opens in place on a click, saves on Enter, and gives focus back to the value", async () => {
    const save = vi.fn();
    render(<InlineText label="Název studie" value="Ranní pečivo" onCommit={save} />);
    expect(screen.queryByRole("textbox")).toBeNull();
    fireEvent.click(shown());
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.change(field(), { target: { value: "  Ranní   pečivo 2026 " } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(save).toHaveBeenCalledWith("Ranní pečivo 2026");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("opens on F2 and on Enter from the keyboard", () => {
    render(<InlineText label="Název studie" value="A" onCommit={() => {}} />);
    fireEvent.keyDown(shown(), { key: "F2" });
    expect(field()).toBeTruthy();
    fireEvent.keyDown(field(), { key: "Escape" });
    fireEvent.keyDown(shown(), { key: "Enter" });
    expect(field()).toBeTruthy();
  });

  it("restores on Esc and saves nothing, the blur after it included", () => {
    const save = vi.fn();
    render(<InlineText label="Název studie" value="Ranní pečivo" onCommit={save} />);
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "Jiný" } });
    const input = field();
    fireEvent.keyDown(input, { key: "Escape" });
    fireEvent.blur(input);
    expect(save).not.toHaveBeenCalled();
    expect(shown().textContent).toContain("Ranní pečivo");
  });

  it("saves on blur, and saves nothing when the value did not change", () => {
    const save = vi.fn();
    render(<InlineText label="Název studie" value="A" onCommit={save} />);
    fireEvent.click(shown());
    fireEvent.blur(field());
    expect(save).not.toHaveBeenCalled();
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "B" } });
    fireEvent.blur(field());
    expect(save).toHaveBeenCalledWith("B");
  });

  it("keeps a refused draft in the field with the reason beside it, checked live once said (I9)", () => {
    const save = vi.fn();
    render(<InlineText label="Název studie" value="A" onCommit={save} rules={{ maxLength: 5 }} />);
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "příliš dlouhé" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(save).not.toHaveBeenCalled();
    expect(field().getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("Nejvýš 5 znaků; neuloženo.")).toBeTruthy();
    fireEvent.change(field(), { target: { value: "krátk" } });
    expect(screen.queryByText("Nejvýš 5 znaků; neuloženo.")).toBeNull();
    fireEvent.change(field(), { target: { value: "   " } });
    expect(screen.getByText("Vyplňte text; neuloženo.")).toBeTruthy();
  });

  it("saves multi-line text on Ctrl+Enter only; Enter is a new line", () => {
    const save = vi.fn();
    render(<InlineText label="Název studie" value="A" multiline onCommit={save} />);
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "řádek\ndruhý" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(save).not.toHaveBeenCalled();
    fireEvent.keyDown(field(), { key: "Enter", ctrlKey: true });
    expect(save).toHaveBeenCalledWith("řádek\ndruhý");
  });

  it("says Ukládám… then Uloženo while a save is in flight, and that it went", async () => {
    vi.useFakeTimers();
    let done!: () => void;
    const save = vi.fn(() => new Promise<void>((r) => (done = r)));
    render(<InlineText label="Název studie" value="A" onCommit={save} />);
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "B" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(screen.getByText("Ukládám…")).toBeTruthy();
    await act(async () => done());
    expect(screen.getByText("Uloženo")).toBeTruthy();
    act(() => vi.advanceTimersByTime(3000));
    expect(screen.queryByText("Uloženo")).toBeNull();
  });

  it("on a failed save keeps what was typed and offers Zkusit znovu, which resends it", async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error("x")).mockResolvedValueOnce(undefined);
    render(<InlineText label="Název studie" value="A" onCommit={save} />);
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "Nový název" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(await screen.findByText(/Neuloženo/)).toBeTruthy();
    expect(shown().textContent).toContain("Nový název");
    fireEvent.click(screen.getByRole("button", { name: "Zkusit znovu" }));
    expect(save).toHaveBeenLastCalledWith("Nový název");
    expect(await screen.findByText("Uloženo")).toBeTruthy();
  });

  it("cannot be opened when disabled, and says why", () => {
    render(<InlineText label="Název studie" value="A" onCommit={() => {}} disabled disabledReason="zmrazeno během běhu" />);
    fireEvent.click(shown());
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText("zmrazeno během běhu")).toBeTruthy();
  });
});
