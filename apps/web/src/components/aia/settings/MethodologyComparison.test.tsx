// @vitest-environment jsdom
// The support draft check as the Metodika tab shows it (plan G1d): every fictional cell the edit
// newly shows or newly suppresses is named with its surface, what does not move says so, and
// every cell is listed with both statuses on both surfaces, folded away until asked for.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { MethodAggregationPanel, MethodCompare, MethodSupportCell } from "@/lib/api";
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

describe("the aggregation draft check (plan G3b)", () => {
  const panel = (id: string, label: string, moved: boolean) => ({
    panel: id, label_cs: label, respondents: 240,
    rows: [
      { question: "spokojenost", measure: "prumer", moved: false, in_force: [3.9, 3.7, 4.1], draft: [3.9, 3.7, 4.1] },
      { question: "spokojenost", measure: "top2box", moved, in_force: [45.4, 38.3, 53.2], draft: moved ? [3.6, 1.0, 7.0] : [45.4, 38.3, 53.2] },
      { question: "volba", measure: "share:Alfa", moved: false, in_force: [50.1, 44.0, 56.0], draft: [50.1, 44.0, 56.0] },
    ] as MethodAggregationPanel["rows"],
    status_changes: moved ? [{ question: "spokojenost", in_force: "SUPPRESS", draft: "REPORTABLE" }] : [],
    effective_n: { spokojenost: [30.8, moved ? 40 : 30.8] as [number, number] },
  });

  it("names each estimate the draft moves, with its interval, and the statuses it changes", () => {
    render(
      <MethodologyComparison
        result={{
          valid: true, problems: {}, in_force: "aia-aggregate-1", panels: [],
          aggregation: { draft: "aia-aggregate-1+e1", panels: [panel("vazeny", "Silně vážený panel (fiktivní)", true), panel("velky", "Velký panel (fiktivní)", false)] },
        }}
      />,
    );
    const moved = document.querySelector('[data-compare-aggregation-panel="vazeny"]') as HTMLElement;
    expect((moved.querySelector("details") as HTMLDetailsElement).open).toBe(true); // the first panel is open
    expect(within(moved).getByText(/1 z 3 odhadů se mění/)).toBeTruthy();
    const line = within(moved).getByText(/top box/).closest("li") as HTMLElement;
    expect(line.textContent).toContain("45,4 (38,3–53,2)");
    expect(within(line).getByText("3,6 (1–7)").tagName).toBe("STRONG");
    expect(within(moved).getByText("reportovatelné").tagName).toBe("STRONG");
    expect(within(moved).getByText(/30,8 → 40/)).toBeTruthy();

    const still = document.querySelector('[data-compare-aggregation-panel="velky"]') as HTMLElement;
    expect((still.querySelector("details") as HTMLDetailsElement).open).toBe(false);
    expect(within(still).getByText("Žádný odhad se nemění.")).toBeTruthy();
    expect(within(still).getByText("Žádné otázce se stav podpory nemění.")).toBeTruthy();
    expect(document.querySelector("[data-compare-support]")).toBeNull();
  });
});

describe("the response-process draft check", () => {
  it("shows each option's share under the model, in force and drafted, and each respondent's shift", () => {
    render(
      <MethodologyComparison
        result={{
          valid: true, problems: {}, in_force: "aia-response-1", panels: [],
          response: {
            draft: "aia-response-1+e1", respondents: 80, described_in_force: 77, described_draft: 40,
            questions: [{
              question: "skala7", label_cs: "Škála 1-7 bez „nevím“, nic deklarovaného",
              labels: ["1", "2", "3"], model: [25, 50, 25], in_force: [25.5, 49, 25.5], draft: [30, 40, 30],
              moved_pp: 9, shift_in_force: 3.49, shift_draft: 9.78,
            }],
          },
        }}
      />,
    );
    const box = document.querySelector("[data-compare-response]") as HTMLElement;
    expect(within(box).getByText(/Model se nevolá/)).toBeTruthy();
    expect(within(box).getByText("Profily se stylem slovy: 77 → 40 z 80")).toBeTruthy();
    expect(within(box).getByText(/největší změna podílu 9 p\. b\. · posun respondenta 3,49 → 9,78 p\. b\./)).toBeTruthy();
    const table = within(box).getByRole("table", { name: "Škála 1-7 bez „nevím“, nic deklarovaného" });
    const two = within(table).getByRole("rowheader", { name: "2" }).closest("tr") as HTMLElement;
    expect(two.textContent).toBe("250 %49 %40 %");
    expect(within(two).getByText("40 %").className).toContain("font-semibold");
  });
});
