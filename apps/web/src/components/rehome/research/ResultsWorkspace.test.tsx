// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { useState } from "react";
import type { ResearchRun } from "@/lib/api";
import { ResultsWorkspace } from "./ResultsWorkspace";

const run = { run_id: "RUN-frozen", design_revision_id: "REV-frozen", design_revision: 4, phase: "COMPLETED", actual_cost_usd: null } as ResearchRun;
function Camera() {
  const [angle, setAngle] = useState(0);
  return <button onClick={() => setAngle(a => a + 15)}>Úhel {angle}</button>;
}
const panels = [
  { id: "data", label: "Data", description: "Uložená data", content: <p>Výsledná tabulka</p> },
  { id: "maps", label: "Sociomapy", description: "Uložené mapy", content: <Camera /> },
  { id: "report", label: "Rešerše a zpráva", description: "Zpráva", content: <p>Zvolená rešerše</p> },
];
const view = () => render(<ResultsWorkspace run={run} panels={panels} progressHref="/progress?run=RUN-frozen" notice={<p>Fiktivní data</p>} />);
afterEach(() => { cleanup(); window.history.replaceState(null, "", "/"); });

it("opens an overview without inventing zero cost and exposes only the selected panel", () => {
  view();
  expect(screen.getByRole("tab", { name: "Přehled" }).getAttribute("aria-selected")).toBe("true");
  expect(screen.getAllByRole("tabpanel")).toHaveLength(1);
  expect(screen.getByText("Zatím nejsou vykázané")).toBeTruthy();
  expect(screen.getByText("Fiktivní data")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Průběh tohoto běhu →" }).getAttribute("href")).toBe("/progress?run=RUN-frozen");
});

it("keeps the map camera and frozen run query while changing views", () => {
  window.history.replaceState(null, "", "/results?run=RUN-frozen");
  view();
  fireEvent.click(screen.getByRole("tab", { name: "Sociomapy" }));
  fireEvent.click(screen.getByRole("button", { name: "Úhel 0" }));
  fireEvent.click(screen.getByRole("tab", { name: "Data" }));
  expect(screen.queryByRole("button", { name: "Úhel 15" })).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "Sociomapy" }));
  expect(screen.getByRole("button", { name: "Úhel 15" })).toBeTruthy();
  expect(window.location.search).toBe("?run=RUN-frozen");
  expect(window.location.hash).toBe("#maps");
});

it("opens old literature anchors and follows browser history without selecting an unavailable section", () => {
  window.history.replaceState(null, "", "/results#res-literature");
  view();
  expect(screen.getByRole("tab", { name: "Rešerše a zpráva" }).getAttribute("aria-selected")).toBe("true");
  window.history.replaceState(null, "", "/results#unknown");
  fireEvent(window, new PopStateEvent("popstate"));
  expect(screen.getByRole("tab", { name: "Přehled" }).getAttribute("aria-selected")).toBe("true");
});

it("supports arrow, Home and End keys with matching selection, focus and panel names", () => {
  view();
  const first = screen.getByRole("tab", { name: "Přehled" });
  first.focus(); fireEvent.keyDown(first, { key: "ArrowRight" });
  expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Data" }));
  expect(screen.getByRole("tabpanel", { name: "Data" })).toBeTruthy();
  fireEvent.keyDown(document.activeElement!, { key: "End" });
  expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Rešerše a zpráva" }));
  fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
  expect(document.activeElement).toBe(first);
  fireEvent.keyDown(first, { key: "ArrowLeft" });
  expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Rešerše a zpráva" }));
  fireEvent.keyDown(document.activeElement!, { key: "Home" });
  expect(document.activeElement).toBe(first);
});

it("names the methods the run computed under, stored version or code preset", () => {
  const pinned = {
    ...run,
    methodology: {
      sociomap: { name: "aia-sociomap-3", stored: false },
      support: { name: "aia-support-1+e2", stored: true },
      aggregation: { name: "aia-aggregate-1+e1", stored: true },
    },
  } as ResearchRun;
  render(<ResultsWorkspace run={pinned} panels={panels} progressHref={null} notice={null} />);
  const row = document.querySelector("[data-run-methodology]") as HTMLElement;
  expect(row.textContent).toContain("Podpora aia-support-1+e2 (uložená verze)");
  expect(row.textContent).toContain("Agregace aia-aggregate-1+e1 (uložená verze)");
  expect(row.textContent).toContain("Sociomapa aia-sociomap-3 (z kódu)");
});

it("says nothing about methods an older API did not report", () => {
  view();
  expect(document.querySelector("[data-run-methodology]")).toBeNull();
});

it("says a pin it cannot read is unreadable, never a preset's name", () => {
  const unreadable = {
    ...run,
    methodology: {
      sociomap: { name: null, stored: false },
      support: { name: "aia-support-1", stored: false },
      aggregation: { name: "aia-aggregate-1", stored: false },
    },
  } as ResearchRun;
  render(<ResultsWorkspace run={unreadable} panels={panels} progressHref={null} notice={null} />);
  const row = document.querySelector("[data-run-methodology]") as HTMLElement;
  expect(row.textContent).toContain("Sociomapa záznam nelze přečíst");
  expect(row.textContent).not.toContain("aia-sociomap");
});

it("names the response process and says when it is not 18.6.6's (R1d)", () => {
  const edited = {
    ...run,
    methodology: {
      sociomap: { name: "aia-sociomap-3", stored: false },
      support: { name: "aia-support-1", stored: false },
      aggregation: { name: "aia-aggregate-1", stored: false },
      response: { name: "aia-response-1+e1", stored: true },
      response_deviates: true,
    },
  } as ResearchRun;
  render(<ResultsWorkspace run={edited} panels={panels} progressHref={null} notice={null} />);
  const row = document.querySelector("[data-run-methodology]") as HTMLElement;
  expect(row.textContent).toContain("Odpověď aia-response-1+e1 (uložená verze)");
  const note = document.querySelector("[data-response-deviation]") as HTMLElement;
  expect(note.textContent).toContain("jiným procesem odpovědi než v 18.6.6");
  expect(note.textContent).toContain("aia-response-1+e1");
});

it("says nothing about a deviation when the response process is 18.6.6's", () => {
  const unit = {
    ...run,
    methodology: {
      sociomap: { name: "aia-sociomap-3", stored: false },
      support: { name: "aia-support-1", stored: false },
      aggregation: { name: "aia-aggregate-1", stored: false },
      response: { name: "aia-response-1", stored: false },
      response_deviates: false,
    },
  } as ResearchRun;
  render(<ResultsWorkspace run={unit} panels={panels} progressHref={null} notice={null} />);
  expect((document.querySelector("[data-run-methodology]") as HTMLElement).textContent).toContain("Odpověď aia-response-1 (z kódu)");
  expect(document.querySelector("[data-response-deviation]")).toBeNull();
});

it("says a response process it cannot read is unreadable, and that it cannot tell", () => {
  const unreadable = {
    ...run,
    methodology: {
      sociomap: { name: "aia-sociomap-3", stored: false },
      support: { name: "aia-support-1", stored: false },
      aggregation: { name: "aia-aggregate-1", stored: false },
      response: { name: null, stored: false },
      response_deviates: null,
    },
  } as ResearchRun;
  render(<ResultsWorkspace run={unreadable} panels={panels} progressHref={null} notice={null} />);
  expect((document.querySelector("[data-run-methodology]") as HTMLElement).textContent).toContain("Odpověď záznam nelze přečíst");
  expect((document.querySelector("[data-response-deviation]") as HTMLElement).textContent).toContain("nelze říct");
});
