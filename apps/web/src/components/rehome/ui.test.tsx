// @vitest-environment jsdom
// The interface primitives that carry a rule of their own.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AiButton, FaultNote, StaleMark, StatusPill, type StatusTone, Value } from "./ui";
import { usdWords } from "@/lib/spend";
import { AiJobCard } from "./AiJobCard";
import { ItemReview } from "./ItemReview";

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

describe("AiJobCard", () => {
  it("is one card for an AI job and a run: the AI's edge turns only while a model works, a run is drawn in ink", () => {
    const { container } = render(<>
      <AiJobCard kind="ai" title="Analýza zadání" state={{ word: "Běží", tone: "running" }} working facts={[{ label: "Cena nejvýše", value: "0,40 USD", key: true }]} />
      <AiJobCard kind="ai" title="Návrh dotazníku" state={{ word: "Návrh čeká na vás", tone: "you" }} />
      <AiJobCard kind="run" title="Běh 2" state={{ word: "Běží", tone: "running" }} working />
    </>);
    const [busy, waiting, run] = [...container.querySelectorAll<HTMLElement>("[data-job-card]")];
    expect(busy.className).toContain("ai-spark--working");
    expect(busy.getAttribute("aria-busy")).toBe("true");
    expect(waiting.className).toContain("ai-spark");
    expect(waiting.className).not.toContain("ai-spark--working");
    expect(run.className).not.toContain("ai-spark");
    for (const card of [busy, waiting, run]) {
      expect(card.className).toContain("rounded-panel");
      expect(card.querySelector("[data-status-pill]")).toBeTruthy();
    }
    expect(screen.getByText("0,40 USD").hasAttribute("data-fact-key")).toBe(true);
  });
});

describe("ItemReview", () => {
  const items = [
    { id: "a", where: "Dotazník · upravit otázku", before: "Znáte?", after: "Znáte značku?", why: "Jasnější" },
    { id: "b", where: "Dotazník · přidat otázku", after: "Kolik?" },
    { id: "c", where: "Návrh · cíl", after: "Hotovo", decided: "Přijato" },
  ];

  it("decides each item, or all still open, and never offers a decided one again", () => {
    const onAccept = vi.fn(); const onDismiss = vi.fn();
    render(<ItemReview mode="each" label="Návrhy Vedoucího" head="Vedoucí navrhuje 3 změny" canEdit items={items} onAccept={onAccept} onDismiss={onDismiss} />);
    const region = screen.getByRole("region", { name: "Návrhy Vedoucího" });
    expect(within(region).getAllByRole("button", { name: "Přijmout" })).toHaveLength(2);
    expect(within(region).getByText("Znáte?").hasAttribute("data-review-before")).toBe(true);
    expect(within(region).getByText("Proč: Jasnější")).toBeTruthy();
    fireEvent.click(within(region).getByRole("button", { name: "Přijmout vše" }));
    expect(onAccept).toHaveBeenCalledWith(["a", "b"]);
    fireEvent.click(within(region).getAllByRole("button", { name: "Zahodit" })[1]!);
    expect(onDismiss).toHaveBeenCalledWith(["b"]);
  });

  it("ticks only what may be taken, and keeps a decided item ticked and closed", () => {
    const onToggle = vi.fn();
    render(<ItemReview mode="select" label="Položky" canEdit selected={new Set(["a"])} onToggle={onToggle} footer={<p>pata</p>}
      items={[{ ...items[0]!, selectable: true }, { ...items[1]!, selectable: false }, { ...items[2]!, selectable: true }, { id: "gap", where: "Mezera" }]} />);
    const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(boxes.map((b) => [b.checked, b.disabled])).toEqual([[true, false], [false, true], [true, true]]);
    fireEvent.click(boxes[0]!);
    expect(onToggle).toHaveBeenCalledWith("a");
    expect(screen.getByText("pata")).toBeTruthy();
  });
});
