// @vitest-environment jsdom
// The interface primitives that carry a rule of their own.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { AiButton, FaultNote, StaleMark, StatusPill, type StatusTone, Value } from "./ui";
import { usdWords } from "@/lib/spend";

afterEach(cleanup);

describe("FaultNote", () => {
  it("is the one alert box: announced, in the fault wash, its spacing the caller's", () => {
    render(<FaultNote className="mb-4" data-lost-edit>Uložení selhalo.</FaultNote>);
    const note = screen.getByRole("alert");
    expect(note.textContent).toBe("Uložení selhalo.");
    expect(note.className).toContain("bg-status-fault-wash");
    expect(note.className).toContain("mb-4");
    expect(note.hasAttribute("data-lost-edit")).toBe(true);
  });
});

describe("AiButton", () => {
  it("is marked by the spark edge and the sparkle, never by a colour of its own", () => {
    render(<><AiButton>Navrhni dotazník</AiButton><AiButton variant="primary">Spustit úlohu</AiButton></>);
    const [secondary, primary] = screen.getAllByRole("button");
    expect(secondary.className).toContain("ai-spark");
    expect(primary.className).toContain("ai-spark--solid");
    for (const b of [secondary, primary]) {
      expect(b.className).not.toMatch(/\bbg-ai\b|text-ai-ink|border-ai-edge/);
      expect(b.querySelector("svg.ai-sparkle")).toBeTruthy();
    }
  });
});

describe("StatusPill", () => {
  it("says every state with its word and its shape, never by colour alone", () => {
    const tones: StatusTone[] = ["running", "you", "world", "fault", "done", "cancelled", "inert"];
    render(<>{tones.map((t) => <StatusPill key={t} tone={t}>{t}</StatusPill>)}<StatusPill tone="neutral">bez stavu</StatusPill></>);
    for (const t of tones) {
      const pill = screen.getByText(t).closest("[data-status-pill]") as HTMLElement;
      expect(pill.dataset.tone).toBe(t);
      expect(pill.querySelector(`svg.glyph[data-tone="${t}"]`)).toBeTruthy();
    }
    // Neutral states no status: a word, no shape that could be read as one.
    expect((screen.getByText("bez stavu").closest("[data-status-pill]") as HTMLElement).querySelector("svg")).toBeNull();
  });
});

describe("Value", () => {
  it("never shows an unknown figure as zero or a dash, and never a suppressed number", () => {
    const { container } = render(<>
      <Value of={null} /><Value of={Number.NaN} usd /><Value of={0} usd /><Value of={0.003} usd /><Value of={12} />
      <Value suppressed="podpora dat nestačí" />
    </>);
    const states = [...container.querySelectorAll("[data-value]")].map((n) => [n.getAttribute("data-value"), n.textContent]);
    expect(states).toEqual([
      ["unknown", "neznámé"], ["unknown", "neznámé"],
      ["known", usdWords(0)], ["known", usdWords(0.003)], ["known", "12"],
      ["suppressed", "Potlačeno · podpora dat nestačí"],
    ]);
    // Known zero is a real figure; a sub-cent amount is never rounded to it.
    expect(usdWords(0.003).replace(/\s/g, " ")).toBe("< 0,01 USD");
    expect(usdWords(0.0042, 3).replace(/\s/g, " ")).toBe("0,004 USD");
  });
});

describe("StaleMark", () => {
  it("marks what is older than the copy as waiting on a person, never as a failure", () => {
    render(<><StaleMark alert data-proposal-stale>Návrh nejde použít.</StaleMark><StaleMark title="Výsledky běhu z revize 3">Čísla platí pro revizi 3.</StaleMark></>);
    const [alert, note] = [screen.getByRole("alert"), screen.getByRole("note")];
    for (const box of [alert, note]) {
      expect(box.className).toContain("bg-status-you-wash");
      expect(box.className).not.toContain("status-fault");
      expect(box.querySelector('svg.glyph[data-tone="reopened"]')).toBeTruthy();
    }
    expect(alert.hasAttribute("data-proposal-stale")).toBe(true);
    expect(note.textContent).toBe("Výsledky běhu z revize 3Čísla platí pro revizi 3.");
  });
});
