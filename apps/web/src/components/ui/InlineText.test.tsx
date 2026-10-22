// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InlineText, SELECT_SETTLE_MS } from "./InlineText";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const shown = () => screen.getByRole("button", { name: /^Upravit: Název studie/ });
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

  it("gives focus back to the value only if the person has not moved it before the next frame", async () => {
    render(
      <>
        <InlineText label="Název studie" value="A" onCommit={() => {}} />
        <button type="button">Jinde</button>
      </>,
    );
    fireEvent.click(shown());
    fireEvent.keyDown(field(), { key: "Enter" });
    // The person moves on within the same frame, before the field's refocus runs.
    const elsewhere = screen.getByRole("button", { name: "Jinde" });
    elsewhere.focus();
    await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
    expect(document.activeElement).toBe(elsewhere);

    // Left alone, focus still comes back to the value (I11).
    fireEvent.click(shown());
    fireEvent.keyDown(field(), { key: "Enter" });
    await waitFor(() => expect(document.activeElement).toBe(shown()));
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

  it("ignores an older save that answers after a newer one (Codex #532)", async () => {
    // Each call returns its own promise, settled by hand in the order the test chooses.
    const pending: { resolve: () => void; reject: (e: Error) => void }[] = [];
    const save = vi.fn(() => new Promise<void>((resolve, reject) => pending.push({ resolve, reject })));
    const edit = (text: string) => {
      fireEvent.click(shown());
      fireEvent.change(field(), { target: { value: text } });
      fireEvent.keyDown(field(), { key: "Enter" });
    };

    // A pending, B fails, then A resolves: the failure of B stands, and the retry resends B.
    const { unmount } = render(<InlineText label="Název studie" value="původní" onCommit={save} />);
    edit("A");
    edit("B");
    await act(async () => pending[1].reject(new Error("x")));
    await act(async () => pending[0].resolve());
    expect(screen.getByText(/Neuloženo/)).toBeTruthy();
    expect(screen.queryByText("Uloženo")).toBeNull();
    expect(shown().textContent).toContain("B");
    fireEvent.click(screen.getByRole("button", { name: "Zkusit znovu" }));
    expect(save).toHaveBeenLastCalledWith("B");
    unmount();

    // A pending, B succeeds, then A rejects: B is saved, and no retry is offered.
    pending.length = 0;
    render(<InlineText label="Název studie" value="původní" onCommit={save} />);
    edit("A");
    edit("B");
    await act(async () => pending[1].resolve());
    await act(async () => pending[0].reject(new Error("x")));
    expect(screen.getByText("Uloženo")).toBeTruthy();
    expect(screen.queryByText(/Neuloženo/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Zkusit znovu" })).toBeNull();
  });

  it("names the button by its action and the value it shows (review of #532)", () => {
    render(<InlineText label="Název studie" value="Ranní pečivo" onCommit={() => {}} />);
    expect(screen.getByRole("button", { name: "Upravit: Název studie Ranní pečivo" })).toBeTruthy();
  });

  it("shows, reopens and compares against the value in flight, so a revert typed meanwhile is sent (review of #532, P2-1)", async () => {
    const answers: (() => void)[] = [];
    const save = vi.fn(() => new Promise<void>((resolve) => answers.push(resolve)));
    render(<InlineText label="Název studie" value="A" onCommit={save} />);
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "B" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    // B is in flight: shown, and the field reopens on it.
    expect(shown().textContent).toContain("B");
    fireEvent.click(shown());
    expect((field() as HTMLInputElement).value).toBe("B");
    // Back to the stored A: that is a new save, not "nothing changed".
    fireEvent.change(field(), { target: { value: "A" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(save).toHaveBeenLastCalledWith("A");
    expect(save).toHaveBeenCalledTimes(2);
    // B's late answer does not count; A's does.
    await act(async () => answers[0]());
    expect(screen.getByText("Ukládám…")).toBeTruthy();
    await act(async () => answers[1]());
    expect(screen.getByText("Uloženo")).toBeTruthy();
  });

  it("forgets a failed save when the value is set back to the stored one (review of #532, P2-2)", async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error("x"));
    render(<InlineText label="Název studie" value="A" onCommit={save} />);
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "B" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(await screen.findByText(/Neuloženo/)).toBeTruthy();
    fireEvent.click(shown());
    expect((field() as HTMLInputElement).value).toBe("B");
    fireEvent.change(field(), { target: { value: "A" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(save).toHaveBeenCalledTimes(1);
    expect(shown().textContent).toContain("A");
    expect(screen.queryByText(/Neuloženo/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Zkusit znovu" })).toBeNull();
  });

  it("waits for any thenable, not only a native Promise (review of #532)", async () => {
    let done!: () => void;
    const thenable = { then: (ok: () => void) => void (done = ok) };
    render(<InlineText label="Název studie" value="A" onCommit={() => thenable as unknown as PromiseLike<void>} />);
    fireEvent.click(shown());
    fireEvent.change(field(), { target: { value: "B" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(screen.getByText("Ukládám…")).toBeTruthy();
    await act(async () => done());
    expect(screen.getByText("Uloženo")).toBeTruthy();
  });

  it("cannot be opened when disabled, and says why", () => {
    render(<InlineText label="Název studie" value="A" onCommit={() => {}} disabled disabledReason="zmrazeno během běhu" />);
    fireEvent.click(shown());
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText("zmrazeno během běhu")).toBeTruthy();
  });
});

describe("InlineText opened from elsewhere (input-interactions chunk 2: a row's rename)", () => {
  it("opens as it mounts with autoOpen, focused, and is settled by Esc without saving", () => {
    const save = vi.fn();
    const settled = vi.fn();
    render(<InlineText autoOpen label="Název studie" value="A" onCommit={save} onSettled={settled} />);
    expect(document.activeElement).toBe(field());
    expect((field() as HTMLInputElement).value).toBe("A");
    expect(settled).not.toHaveBeenCalled();
    fireEvent.keyDown(field(), { key: "Escape" });
    expect(save).not.toHaveBeenCalled();
    expect(settled).toHaveBeenCalledTimes(1);
  });

  it("settles once its save has answered, not while it is in flight", async () => {
    let done = () => {};
    const save = vi.fn(() => new Promise<void>((resolve) => (done = resolve)));
    const settled = vi.fn();
    render(<InlineText autoOpen label="Název studie" value="A" onCommit={save} onSettled={settled} />);
    fireEvent.change(field(), { target: { value: "B" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(screen.getByText("Ukládám…")).toBeTruthy();
    expect(settled).not.toHaveBeenCalled();
    await act(async () => done());
    expect(settled).toHaveBeenCalledTimes(1);
  });

  it("does not settle on a failed save, so Neuloženo – Zkusit znovu stays; it settles when the retry goes", async () => {
    const save = vi.fn().mockRejectedValueOnce(new Error("x")).mockResolvedValueOnce(undefined);
    const settled = vi.fn();
    render(<InlineText autoOpen label="Název studie" value="A" onCommit={save} onSettled={settled} />);
    fireEvent.change(field(), { target: { value: "B" } });
    fireEvent.keyDown(field(), { key: "Enter" });
    expect(await screen.findByText(/Neuloženo/)).toBeTruthy();
    expect(settled).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Zkusit znovu" }));
    expect(await screen.findByText("Uloženo")).toBeTruthy();
    // onSettled runs in an effect after the commit that shows "Uloženo" (InlineText.tsx:77-81),
    // so under load the assertion can run first: wait for it rather than read it at once.
    await waitFor(() => expect(settled).toHaveBeenCalledTimes(1));
  });

  it("never settles without having been opened, and does not open when disabled", () => {
    const settled = vi.fn();
    render(<InlineText label="Název studie" value="A" onCommit={() => {}} onSettled={settled} />);
    render(<InlineText autoOpen disabled label="Jiný název" value="B" onCommit={() => {}} onSettled={settled} />);
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(settled).not.toHaveBeenCalled();
  });
});

describe("InlineText selectable (Q68): its words can be selected and still edited in place", () => {
  const select = (node: Node, from: number, to: number) => {
    const range = document.createRange();
    range.setStart(node, from);
    range.setEnd(node, to);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
  };
  afterEach(() => window.getSelection()?.removeAllRanges());

  it("is a focusable role=button span, not a <button>, so a browser lets its words be selected", () => {
    render(<InlineText selectable label="Název studie" value="Ranní pečivo" onCommit={() => {}} />);
    expect(shown().tagName).toBe("SPAN");
    expect(shown().getAttribute("tabindex")).toBe("0");
  });

  const settle = () => act(() => new Promise((r) => setTimeout(r, SELECT_SETTLE_MS + 50)));

  it("does not open on the click that ends a selection of its words, and opens on a plain click once it settles", async () => {
    render(<InlineText selectable label="Název studie" value="Ranní pečivo" onCommit={() => {}} />);
    select(screen.getByText("Ranní pečivo").firstChild!, 0, 5);
    fireEvent.click(shown(), { detail: 1 });
    await settle();
    expect(screen.queryByRole("textbox")).toBeNull();
    window.getSelection()!.removeAllRanges();
    fireEvent.click(shown(), { detail: 1 });
    expect(await screen.findByRole("textbox", { name: "Název studie" })).toBeTruthy();
  });

  it("does not open on a double-click, which selects a word instead", async () => {
    render(<InlineText selectable label="Název studie" value="Ranní pečivo" onCommit={() => {}} />);
    fireEvent.click(shown(), { detail: 1 });
    fireEvent.click(shown(), { detail: 2 });
    await settle();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("opened by a key right after a click, keeps what is typed when the click's wait runs out", async () => {
    render(<InlineText selectable label="Název studie" value="A" onCommit={() => {}} />);
    fireEvent.click(shown(), { detail: 1 });
    fireEvent.keyDown(shown(), { key: "Enter" });
    fireEvent.change(field(), { target: { value: "Rozepsáno" } });
    await settle();
    expect((field() as HTMLTextAreaElement | HTMLInputElement).value).toBe("Rozepsáno");
  });

  it("opens on Enter, F2 and Space at once; disabled, it is its words alone, taking no focus", () => {
    const { unmount } = render(<InlineText selectable label="Název studie" value="A" onCommit={() => {}} />);
    for (const key of ["Enter", "F2", " "]) {
      fireEvent.keyDown(shown(), { key });
      expect(field()).toBeTruthy();
      fireEvent.keyDown(field(), { key: "Escape" });
    }
    unmount();
    render(<InlineText selectable disabled label="Název studie" value="Slova" onCommit={() => {}} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Slova").closest("[tabindex]")).toBeNull();
  });
});
