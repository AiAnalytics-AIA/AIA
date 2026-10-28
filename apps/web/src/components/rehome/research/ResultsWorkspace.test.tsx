// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useState } from "react";
import type { ResearchRun } from "@/lib/api";
import { t, tv } from "@/i18n/t";
import { usePanelShown } from "./panel-shown";
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
  expect(screen.getByText(t("research.exec.spend.unknown"))).toBeTruthy();
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

it("shows the study's report card on Přehled and Rešerše a zpráva only, kept mounted with its state", () => {
  render(<ResultsWorkspace run={run} panels={[...panels, { id: "analysis", label: "AI analýza", description: "Analýza", content: <p>Moduly</p> }]} progressHref={null} notice={null} lead={<Camera />} />);
  const card = () => document.querySelector("[data-results-lead]") as HTMLElement;
  expect(card().hidden).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Úhel 0" }));
  for (const [tab, hidden] of [["Data", true], ["Sociomapy", true], ["AI analýza", true], ["Rešerše a zpráva", false], ["Přehled", false]] as const) {
    fireEvent.click(screen.getByRole("tab", { name: tab }));
    expect(card().hidden, tab).toBe(hidden);
  }
  expect(screen.getAllByRole("button", { name: "Úhel 15" })).toHaveLength(1);
});

it("opens a view named by the address scrolled to its tabs, and the overview where it is", async () => {
  const scrolled = vi.fn();
  const real = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = scrolled;
  try {
    view();
    await new Promise((r) => requestAnimationFrame(r));
    expect(scrolled).not.toHaveBeenCalled();
    cleanup();
    window.history.replaceState(null, "", "/results#maps");
    view();
    await new Promise((r) => requestAnimationFrame(r));
    expect(screen.getByRole("tab", { name: "Sociomapy" }).getAttribute("aria-selected")).toBe("true");
    expect(scrolled.mock.contexts).toEqual([screen.getByRole("tablist")]);
  } finally {
    Element.prototype.scrollIntoView = real;
  }
});

const spentLine = (r: Partial<ResearchRun>) => {
  render(<ResultsWorkspace run={{ ...run, ...r } as ResearchRun} panels={panels} progressHref={null} notice={null} />);
  return document.querySelector("[data-run-spent] dd")?.textContent;
};

it("reads what the run spent from its spend, never the attempts' sum", () => {
  expect(spentLine({ actual_cost_usd: 0, is_terminal: true, spend: { spent_usd: 0.42, reserved_usd: 0.3, uncertain_calls: 0 } })).toBe("0,42 USD");
});

it("names a call the run could not price beside the sum, never a bare zero", () => {
  // The attempts' sum reads 0 for a paid call that came back without a price; the run's spend counts it.
  const unpriced = `${t("research.exec.spend.unpriced")}: ${tv("research.exec.spend.unpricedCalls", { count: 1 })}`;
  expect(spentLine({ actual_cost_usd: 0, is_terminal: true, spend: { spent_usd: 0, reserved_usd: 0, uncertain_calls: 1 } }))
    .toBe(`0,00 USD · ${unpriced} (${t("research.exec.spend.unpricedEnded")})`);
  cleanup();
  // While the run goes on, the call may still be in flight: said so, never called a failure.
  expect(spentLine({ actual_cost_usd: 0, is_terminal: false, spend: { spent_usd: 0, reserved_usd: 0.1, uncertain_calls: 1 } }))
    .toBe(`0,00 USD · ${unpriced} (${t("research.exec.spend.unpricedRunning")})`);
});

it("says the cost cannot be told when the run carries no spend, whatever its attempts sum to", () => {
  expect(spentLine({ actual_cost_usd: 0, spend: null })).toBe(t("research.exec.spend.unknown"));
});

// RES9 (spec sber/V1): in the workbench each view is a stage of its own, named by the hash.
const stage = (hash: string) => {
  window.history.replaceState(null, "", `/results${hash}`);
  return render(<ResultsWorkspace tabs={false} run={run} panels={panels} progressHref="/progress?run=RUN-frozen"
    notice={<p>Fiktivní data</p>} lead={<p>Karta zprávy</p>} />);
};

it("shows only the view the stage's hash names in the workbench, with no tabs and no overview", () => {
  stage("#data");
  expect(screen.queryByRole("tablist")).toBeNull();
  expect(screen.queryByRole("tab")).toBeNull();
  expect(screen.queryByText("Co chcete prozkoumat?")).toBeNull();
  expect(screen.queryByText("Od výsledků k souvislostem a zprávě")).toBeNull();
  expect(screen.getByText("Výsledná tabulka").closest("[hidden]")).toBeNull();
  expect(screen.getByText("Zvolená rešerše").closest("[hidden]")).not.toBeNull();
  // The fictional-data notice is said on every view.
  expect(screen.getByText("Fiktivní data")).toBeTruthy();
});

it("opens Výsledky's data where the stage names no view, never an overview", () => {
  stage("");
  expect(screen.getByText("Výsledná tabulka").closest("[hidden]")).toBeNull();
  cleanup();
  stage("#overview");
  expect(screen.getByText("Výsledná tabulka").closest("[hidden]")).toBeNull();
});

it("keeps the report card with Zpráva and a hidden view's own state across stages in the workbench", () => {
  stage("#maps");
  expect(screen.getByText("Karta zprávy").closest("[hidden]")).not.toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Úhel 0" }));
  window.history.replaceState(null, "", "/results#report");
  fireEvent(window, new HashChangeEvent("hashchange"));
  expect(screen.getByText("Karta zprávy").closest("[hidden]")).toBeNull();
  window.history.replaceState(null, "", "/results#maps");
  fireEvent(window, new HashChangeEvent("hashchange"));
  expect(screen.getByRole("button", { name: "Úhel 15" })).toBeTruthy();
});

it("keeps the run's record under Technické údaje in the workbench, closed", () => {
  stage("#data");
  const details = screen.getByText("Technické údaje").closest("details");
  expect(details).not.toBeNull();
  expect(details?.open).toBe(false);
  expect(details?.textContent).toContain("RUN-frozen");
  expect(details?.textContent).toContain(t("research.exec.spend.spent"));
});

it("keeps its tabs and overview in the classic layout", () => {
  view();
  expect(screen.getByRole("tablist")).toBeTruthy();
  expect(screen.getByText("Co chcete prozkoumat?")).toBeTruthy();
  expect(screen.queryByText("Technické údaje")).toBeNull();
});

it("says a stage's view is not in this run, never the data under its name", () => {
  stage("#analysis");
  // Absent or withheld from this person (a 403 hides an artifact): said without claiming which.
  expect(screen.getByRole("note").textContent).toBe("Tuto část výsledků tu nelze zobrazit: běh ji nemá, nebo vám není přístupná.");
  expect(screen.getByText("Výsledná tabulka").closest("[hidden]")).not.toBeNull();
});

it("keeps each view's description and the run's progress link in the workbench", () => {
  stage("#maps");
  expect(screen.getByText("Uložené mapy").closest("[hidden]")).toBeNull();
  expect(screen.getByRole("link", { name: "Průběh tohoto běhu →" }).getAttribute("href")).toBe("/progress?run=RUN-frozen");
});

it("puts the report card with Zpráva's view in the workbench, inside what opens scrolled to", () => {
  stage("#report");
  const card = screen.getByText("Karta zprávy");
  const view = screen.getByText("Zvolená rešerše").closest("section");
  expect(card.closest("[data-results-stage]")).not.toBeNull();
  expect(card.closest("[data-results-stage]")).toBe(view?.closest("[data-results-stage]"));
  expect(card.compareDocumentPosition(view!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("tells each panel's content whether it is the one on screen, so a hidden one opens nothing (#964)", () => {
  function Shown({ name }: { name: string }) {
    return <p data-shown={name}>{String(usePanelShown())}</p>;
  }
  const watched = panels.map((p) => ({ ...p, content: <Shown name={p.id} /> }));
  render(<ResultsWorkspace run={run} panels={watched} progressHref={null} notice={null} />);
  const shown = () => Object.fromEntries([...document.querySelectorAll("[data-shown]")].map((e) => [e.getAttribute("data-shown"), e.textContent]));
  // On mount, the overview: every panel is mounted, none is on screen.
  expect(shown()).toEqual({ data: "false", maps: "false", report: "false" });
  fireEvent.click(screen.getByRole("tab", { name: "Rešerše a zpráva" }));
  expect(shown()).toEqual({ data: "false", maps: "false", report: "true" });
  fireEvent.click(screen.getByRole("tab", { name: "Data" }));
  expect(shown()).toEqual({ data: "true", maps: "false", report: "false" });
});

it("tells only the stage's own view it is on screen in the workbench, so a hidden one opens nothing (#964)", () => {
  function Shown({ name }: { name: string }) {
    return <p data-shown={name}>{String(usePanelShown())}</p>;
  }
  window.history.replaceState(null, "", "/results#report");
  render(<ResultsWorkspace tabs={false} run={run} panels={panels.map((p) => ({ ...p, content: <Shown name={p.id} /> }))} progressHref={null} notice={null} />);
  const shown = () => Object.fromEntries([...document.querySelectorAll("[data-shown]")].map((e) => [e.getAttribute("data-shown"), e.textContent]));
  expect(shown()).toEqual({ data: "false", maps: "false", report: "true" });
});

it("keeps the comparability caveat on the numbers in sight in the workbench, not under Technické údaje", () => {
  const edited = { ...run, methodology: {
    sociomap: { name: "aia-sociomap-5", stored: false }, support: { name: "aia-support-1", stored: false },
    aggregation: { name: "aia-aggregate-1", stored: false }, response: { name: "aia-response-1+e1", stored: true },
    response_deviates: true,
  } } as ResearchRun;
  window.history.replaceState(null, "", "/results#data");
  render(<ResultsWorkspace tabs={false} run={edited} panels={panels} progressHref={null} notice={null} />);
  const notes = document.querySelectorAll("[data-response-deviation]");
  expect(notes).toHaveLength(1);
  expect(notes[0].closest("details")).toBeNull();
  expect(notes[0].textContent).toContain("je nelze přímo srovnávat s výsledky 18.6.6");
});
