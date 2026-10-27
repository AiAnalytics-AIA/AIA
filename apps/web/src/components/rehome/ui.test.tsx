// @vitest-environment jsdom
// The interface primitives that carry a rule of their own.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AiButton, FaultNote } from "./ui";

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
