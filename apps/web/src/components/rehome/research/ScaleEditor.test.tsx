// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ScaleEditor, ScaleUndoProvider, type ScaleValue } from "./ScaleEditor";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const TEN = Array.from({ length: 10 }, (_, i) => `bod ${i + 1}`);

// The editor over a working copy of its own: every change is kept, as the study store keeps it.
const writes: ScaleValue[] = [];
function Host({ scale, labels, perPoint, rangeFixed }: { scale: unknown[]; labels: string[]; perPoint?: boolean; rangeFixed?: boolean }) {
  const [value, setValue] = useState<{ scale: unknown[]; labels: string[] }>({ scale, labels });
  return (
    <ScaleUndoProvider>
      <ScaleEditor
        name="Q1"
        scale={value.scale}
        labels={value.labels}
        perPoint={perPoint}
        rangeFixed={rangeFixed}
        onChange={(next) => {
          writes.push(next);
          setValue({ scale: [...next.scale], labels: next.labels });
        }}
      />
    </ScaleUndoProvider>
  );
}
const last = () => writes[writes.length - 1];
const range = () => screen.getByRole("radiogroup", { name: "Rozsah škály Q1" });
const chip = (name: string) => within(range()).getByRole("radio", { name });
const modes = () => screen.getByRole("radiogroup", { name: "Popisky škály Q1" });
const edit = (label: string, value: string) => {
  fireEvent.click(screen.getByRole("button", { name: new RegExp(`^Upravit: ${label}`) }));
  const field = screen.getByRole("textbox", { name: label });
  fireEvent.change(field, { target: { value } });
  fireEvent.keyDown(field, { key: "Enter" });
};

describe("ScaleEditor: the range (audit A9, Q32 a)", () => {
  it("offers the owner's presets and Vlastní, the stored range chosen", () => {
    writes.length = 0;
    render(<Host scale={[1, 10]} labels={["vůbec", "zcela"]} />);
    const names = within(range()).getAllByRole("radio").map((r) => r.textContent);
    expect(names).toEqual(["1–5", "1–7", "0–10", "1–10", "Vlastní"]);
    expect(chip("1–10").getAttribute("aria-checked")).toBe("true");
    expect(screen.queryByRole("spinbutton")).toBeNull();
    fireEvent.click(chip("0–10"));
    expect(last()).toEqual({ scale: [0, 10], labels: ["vůbec", "zcela"] });
  });

  it("moves through the presets with the arrows, one Tab stop (I11)", () => {
    writes.length = 0;
    render(<Host scale={[1, 5]} labels={["ne", "ano"]} />);
    const tabbable = within(range()).getAllByRole("radio").filter((r) => r.tabIndex === 0);
    expect(tabbable.map((r) => r.textContent)).toEqual(["1–5"]);
    fireEvent.keyDown(chip("1–5"), { key: "ArrowRight" });
    expect(last().scale).toEqual([1, 7]);
    expect(document.activeElement?.textContent).toBe("1–7");
  });

  it("opens two steppers for Vlastní, each bounded by the other, a decimal refused at the field", () => {
    writes.length = 0;
    render(<Host scale={[1, 10]} labels={["vůbec", "zcela"]} />);
    fireEvent.click(chip("Vlastní"));
    const low = screen.getByRole("spinbutton", { name: "Minimum" });
    const high = screen.getByRole("spinbutton", { name: "Maximum" });
    expect(low.getAttribute("aria-valuemin")).toBe("0");
    expect(low.getAttribute("aria-valuemax")).toBe("9");
    expect(high.getAttribute("aria-valuemin")).toBe("2");
    expect(high.getAttribute("aria-valuemax")).toBe("100");
    // The server's invalid_scale: a non-integer end is refused here, never truncated (IA-2).
    fireEvent.change(low, { target: { value: "2,5" } });
    fireEvent.blur(low);
    expect(writes).toHaveLength(0);
    expect(screen.getByRole("alert").textContent).toBe("Jen celé číslo; neuloženo.");
    // An end that would meet the other is refused too: never min >= max.
    fireEvent.change(low, { target: { value: "10" } });
    fireEvent.blur(low);
    expect(writes).toHaveLength(0);
    fireEvent.change(low, { target: { value: "2" } });
    fireEvent.blur(low);
    expect(last()).toEqual({ scale: [2, 10], labels: ["vůbec", "zcela"] });
    fireEvent.keyDown(high, { key: "ArrowUp" });
    expect(last().scale).toEqual([2, 11]);
    // The range is no preset now: Vlastní stays chosen with its steppers.
    expect(chip("Vlastní").getAttribute("aria-checked")).toBe("true");
  });

  it("says a stored range it cannot use and edits no label until one is chosen", () => {
    writes.length = 0;
    render(<Host scale={[8, 3]} labels={["vůbec", "zcela"]} />);
    expect(screen.getByRole("note").textContent).toContain("Uložený rozsah [8,3] nelze použít");
    expect(within(range()).getAllByRole("radio").some((r) => r.getAttribute("aria-checked") === "true")).toBe(false);
    expect((screen.getByRole("button", { name: /^Upravit: Levý popisek/ }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(chip("1–7"));
    expect(last()).toEqual({ scale: [1, 7], labels: ["vůbec", "zcela"] });
  });

  it("shows a set's range without editing it, and offers only its two ends", () => {
    writes.length = 0;
    render(<Host scale={[1, 10]} labels={["vůbec", "velmi"]} rangeFixed perPoint={false} />);
    expect(screen.queryByRole("radiogroup", { name: "Rozsah škály Q1" })).toBeNull();
    expect(screen.queryByRole("radiogroup", { name: "Popisky škály Q1" })).toBeNull();
    expect(screen.getByText("Škála 1–10")).toBeTruthy();
    edit("Pravý popisek", "hodně");
    expect(last()).toEqual({ scale: [1, 10], labels: ["vůbec", "hodně"] });
  });
});

describe("ScaleEditor: a label on every point (audit A10, the owner's note to Q32)", () => {
  it("turns the two ends into every point, prefilled, each point edited in place", () => {
    writes.length = 0;
    render(<Host scale={[1, 10]} labels={["vůbec", "zcela"]} />);
    fireEvent.click(within(modes()).getByRole("radio", { name: "Každý bod" }));
    expect(last().labels).toEqual(["vůbec", "", "", "", "", "", "", "", "", "zcela"]);
    // Until every point is described the labels would be left out, as the server's WARN says.
    expect(document.querySelector("[data-scale-labels-left-out]")?.textContent).toContain("nesmí být prázdný");
    for (let n = 2; n <= 9; n++) edit(`Popisek bodu ${n}`, `bod ${n}`);
    expect(last().labels).toEqual(["vůbec", "bod 2", "bod 3", "bod 4", "bod 5", "bod 6", "bod 7", "bod 8", "bod 9", "zcela"]);
    expect(document.querySelector("[data-scale-labels-left-out]")).toBeNull();
  });

  it("reaches every point's label by Tab, in order", () => {
    render(<Host scale={[1, 5]} labels={["a", "b", "c", "d", "e"]} />);
    const buttons = [1, 2, 3, 4, 5].map((n) => screen.getByRole("button", { name: new RegExp(`^Upravit: Popisek bodu ${n}`) }));
    // Each is a button in document order, no tabindex of its own: Tab moves from one to the next.
    expect(buttons.every((b) => b.tabIndex === 0)).toBe(true);
    for (let i = 1; i < buttons.length; i++) {
      expect(buttons[i - 1].compareDocumentPosition(buttons[i]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
  });

  it("refuses a repeated or over-long label at its field", () => {
    writes.length = 0;
    render(<Host scale={[1, 5]} labels={["a", "b", "c", "d", "e"]} />);
    edit("Popisek bodu 3", "B");
    expect(writes).toHaveLength(0);
    expect(screen.getByText("Dva body škály nesmí mít stejný popisek.")).toBeTruthy();
    const field = screen.getByRole("textbox", { name: "Popisek bodu 3" });
    fireEvent.change(field, { target: { value: "x".repeat(61) } });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(writes).toHaveLength(0);
    expect(screen.getByText("Nejvýš 60 znaků; neuloženo.")).toBeTruthy();
  });

  it("says stored labels of another length are left out, as readiness warns", () => {
    render(<Host scale={[1, 10]} labels={["a", "b", "c"]} />);
    expect(document.querySelector("[data-scale-labels-left-out]")?.textContent).toBe(
      "Popisky se nepoužijí, dokud je neopravíte: Škála má 10 bodů: popište oba konce, nebo každý bod.",
    );
    // Writing an end puts the list right: exactly two ends.
    writes.length = 0;
    edit("Levý popisek", "vůbec");
    expect(last().labels).toEqual(["vůbec", "c"]);
  });

  it("offers every point only up to 11 points", () => {
    render(<Host scale={[0, 20]} labels={["vůbec", "zcela"]} />);
    expect((within(modes()).getByRole("radio", { name: "Každý bod" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/nejvýš o 11 bodech/)).toBeTruthy();
  });
});

describe("ScaleEditor: the range-change rule and its undo (plan § Scales)", () => {
  it("keeps every label when the number of points is unchanged", () => {
    writes.length = 0;
    render(<Host scale={[0, 4]} labels={["a", "b", "c", "d", "e"]} />);
    fireEvent.click(chip("1–5"));
    expect(last()).toEqual({ scale: [1, 5], labels: ["a", "b", "c", "d", "e"] });
    expect(screen.queryByRole("button", { name: "Vrátit" })).toBeNull();
  });

  it("keeps the end labels, clears the inner ones, counts them, and Vrátit restores range and labels", () => {
    writes.length = 0;
    render(<Host scale={[1, 10]} labels={TEN} />);
    fireEvent.click(chip("1–5"));
    expect(last()).toEqual({ scale: [1, 5], labels: ["bod 1", "bod 10"] });
    expect(screen.getByRole("status").textContent).toContain("Odstraněno 8 popisků bodů");
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    expect(last()).toEqual({ scale: [1, 10], labels: TEN });
    expect(chip("1–10").getAttribute("aria-checked")).toBe("true");
    expect(screen.getByRole("button", { name: /^Upravit: Popisek bodu 10/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Vrátit" })).toBeNull();
  });

  it("restores the first state when the arrows pass over several presets", () => {
    writes.length = 0;
    render(<Host scale={[1, 7]} labels={["a", "b", "c", "d", "e", "f", "g"]} />);
    fireEvent.keyDown(chip("1–7"), { key: "ArrowLeft" }); // to 1-5: five inner labels cleared
    expect(screen.getByRole("status").textContent).toContain("Odstraněno 5 popisků bodů");
    fireEvent.keyDown(chip("1–5"), { key: "ArrowLeft" }); // wraps to Vlastní: nothing more lost
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    expect(last()).toEqual({ scale: [1, 7], labels: ["a", "b", "c", "d", "e", "f", "g"] });
  });

  it("clears the inner labels on Oba konce, with the same undo", () => {
    writes.length = 0;
    render(<Host scale={[1, 5]} labels={["a", "b", "c", "", "e"]} />);
    fireEvent.click(within(modes()).getByRole("radio", { name: "Oba konce" }));
    expect(last().labels).toEqual(["a", "e"]);
    expect(screen.getByRole("status").textContent).toContain("Odstraněny 2 popisky bodů");
    fireEvent.click(screen.getByRole("button", { name: "Vrátit" }));
    expect(last().labels).toEqual(["a", "b", "c", "", "e"]);
  });

  it("takes the toast down after 8 s, the change standing", () => {
    vi.useFakeTimers();
    writes.length = 0;
    render(<Host scale={[1, 10]} labels={TEN} />);
    fireEvent.click(chip("1–7"));
    act(() => vi.advanceTimersByTime(8000));
    expect(screen.queryByRole("button", { name: "Vrátit" })).toBeNull();
    expect(last()).toEqual({ scale: [1, 7], labels: ["bod 1", "bod 10"] });
  });
});
