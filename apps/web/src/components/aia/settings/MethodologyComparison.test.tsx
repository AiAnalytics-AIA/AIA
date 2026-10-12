// @vitest-environment jsdom
// The support draft check as the Metodika tab shows it (plan G1d): every fictional cell the edit
// newly shows or newly suppresses is named with its surface, what does not move says so, and
// every cell is listed with both statuses on both surfaces, folded away until asked for.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { MethodCompare, MethodSupportCell } from "@/lib/api";
import { MethodologyComparison } from "./MethodologyComparison";

afterEach(cleanup);

const cell = (id: string, label: string, results: [string, string], analysis: [string, string], changes: MethodSupportCell["changes"] = {}): MethodSupportCell => ({
  cell: id, label_cs: label, n: 60, effective_n: 23, donors: 23, results, analysis, changes,
});

const result = (support: MethodCompare["support"]): MethodCompare => ({
  valid: true, problems: {}, in_force: "aia-support-1", panels: [], support,
});

describe("the support draft check", () => {
  it("names every cell newly shown and lists every cell with both statuses", () => {
    render(
      <MethodologyComparison
        result={result({
          draft: "aia-support-1+e1",
          cells: [
            cell("maly.q1", "Malý panel (fiktivní) · otázka 1", ["SUPPRESS", "INDICATIVE"], ["SUPPRESS", "SUPPRESS"], { results: "reported" }),
            cell("velky.q1", "Velký panel (fiktivní) · otázka 1", ["REPORTABLE", "REPORTABLE"], ["REPORTABLE", "REPORTABLE"]),
          ],
          newly_reported: [["maly.q1", "results"]],
          newly_suppressed: [],
        })}
      />,
    );
    expect(screen.getByText("Co úprava změní oproti aia-support-1")).toBeTruthy();
    expect(screen.getByText("Malý panel (fiktivní) · otázka 1 · Výsledky")).toBeTruthy();
    expect(screen.getByText("Úprava žádnou buňku nově nepotlačí.")).toBeTruthy();
    const moved = document.querySelector('[data-support-cell="maly.q1"]') as HTMLElement;
    expect(within(moved).getByText("indikativní").tagName).toBe("STRONG");
    const still = document.querySelector('[data-support-cell="velky.q1"]') as HTMLElement;
    expect(within(still).getAllByText("reportovatelné")).toHaveLength(2);
    // What moved is in view; the full list of cells waits behind its summary.
    const all = document.querySelector("[data-compare-support] details") as HTMLDetailsElement;
    expect(all.open).toBe(false);
    expect(within(all).getByText("Všechny buňky (2)")).toBeTruthy();
    expect(document.querySelector("[data-compare-panel]")).toBeNull();
  });

  it("says plainly when nothing moves", () => {
    render(
      <MethodologyComparison
        result={result({
          draft: "aia-support-1+e1",
          cells: [cell("maly.q1", "Malý panel (fiktivní) · otázka 1", ["SUPPRESS", "SUPPRESS"], ["SUPPRESS", "SUPPRESS"])],
          newly_reported: [],
          newly_suppressed: [],
        })}
      />,
    );
    expect(screen.getByText("Úprava žádnou buňku nově neukáže.")).toBeTruthy();
    expect(screen.getByText("Úprava žádnou buňku nově nepotlačí.")).toBeTruthy();
  });
});
