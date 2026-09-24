// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectsScreen } from "./ProjectsScreen";

vi.mock("next/navigation", () => ({ usePathname: () => "/app/projects" }));

// jsdom has no <dialog> modality; the component only needs open/close.
beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  window.localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ROWS = [
  { project_id: "PRJ-1", title: "Alfa výzkum", project_type: "research", status: "WAITING_USER", current_stage: "QUESTIONNAIRE", modified_at: "2026-09-01T10:00:00", revision: 3, job_summary: { waiting_user: 1 } },
  { project_id: "PRJ-2", title: "Beta simulace", project_type: "simulation", status: "IN_PROGRESS", modified_at: "2026-09-02T10:00:00", pinned: true },
  { project_id: "PRJ-DEMO-1", title: "Ukázka", project_type: "research", status: "COMPLETED", is_demo: true, study_result: "Varianta B vede." },
];
const COUNTS = { counts: { all: 2, research: 1, simulation: 1, waiting_user: 1, running: 1, pinned: 1, demo: 1 } };

function unitStub(overrides: Record<string, (body: unknown) => unknown> = {}) {
  const calls: { path: string; body: unknown }[] = [];
  const fetchStub = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url);
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ path, body });
    const answer =
      overrides[path]?.(body) ??
      (path === "/api/projects" ? ROWS : path === "/api/projects/dashboard" ? COUNTS : { ok: true });
    return new Response(JSON.stringify(answer), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchStub);
  return calls;
}

describe("ProjectsScreen", () => {
  it("draws every project with the classic texts, and the view counts", async () => {
    unitStub();
    render(<ProjectsScreen />);
    expect(screen.getByText("Načítám portfolio…")).toBeTruthy();
    expect(await screen.findByText("Alfa výzkum")).toBeTruthy();
    expect(screen.getByText("Beta simulace")).toBeTruthy();
    expect(screen.getByText("Ukázka")).toBeTruthy();
    expect(screen.getByText("3 projektů")).toBeTruthy();
    // Waiting on you and running are different families, each with its label.
    expect(screen.getByText("Čeká na vás", { selector: "[data-tone] *, [data-tone]" }).closest("[data-tone]")?.getAttribute("data-tone")).toBe("you");
    expect(screen.getByText("Probíhá", { selector: "[data-tone]" }).getAttribute("data-tone")).toBe("running");
    const views = screen.getByRole("group", { name: "Pohledy" });
    expect(within(views).getByRole("button", { name: /Čeká na mě/ }).textContent).toContain("1");
  });

  it("filters by view and by search, as pmFiltered1810 does", async () => {
    unitStub();
    render(<ProjectsScreen />);
    await screen.findByText("Alfa výzkum");
    fireEvent.click(within(screen.getByRole("group", { name: "Pohledy" })).getByRole("button", { name: /^DEMO/ }));
    expect(screen.getByText("1 projektů")).toBeTruthy();
    expect(screen.queryByText("Alfa výzkum")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Vyčistit filtry" }));
    fireEvent.change(screen.getByPlaceholderText("název, téma, klient, populace, štítek…"), { target: { value: "beta" } });
    expect(screen.getByText("1 projektů")).toBeTruthy();
    expect(screen.getByText("Beta simulace")).toBeTruthy();
  });

  it("links a card into the classic interface with a hand-off", async () => {
    unitStub();
    render(<ProjectsScreen />);
    await screen.findByText("Ukázka");
    const demo = screen.getByText("Ukázka").closest("article")!;
    expect(within(demo).getByRole("link", { name: /Otevřít DEMO/ }).getAttribute("href")).toBe("/#aia:open=PRJ-DEMO-1");
    expect(screen.getByRole("link", { name: /Nový výzkum/ }).getAttribute("href")).toBe("/#aia:start=research");
  });

  it("asks the classic question before moving to the trash, and sends the classic body", async () => {
    const calls = unitStub();
    render(<ProjectsScreen />);
    await screen.findByText("Alfa výzkum");
    const card = screen.getByText("Alfa výzkum").closest("article")!;
    fireEvent.click(within(card).getByRole("button", { name: "Do koše" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Opravdu chcete tento výzkum přesunout do koše?")).toBeTruthy();
    await act(async () => {
      fireEvent.click(within(dialog).getByRole("button", { name: "OK" }));
    });
    expect(calls).toContainEqual({ path: "/api/projects/history-action", body: { project_id: "PRJ-1", action: "trash" } });
    expect(await screen.findByText("Projekt přesunut do koše")).toBeTruthy();
  });

  it("sends nothing when the question is cancelled", async () => {
    const calls = unitStub();
    render(<ProjectsScreen />);
    await screen.findByText("Alfa výzkum");
    fireEvent.click(within(screen.getByText("Alfa výzkum").closest("article")!).getByRole("button", { name: "Archivovat" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Zrušit" }));
    expect(calls.some((c) => c.path === "/api/projects/history-action")).toBe(false);
  });

  it("sends the tags a person types, split as the classic screen splits them", async () => {
    const calls = unitStub();
    render(<ProjectsScreen />);
    await screen.findByText("Alfa výzkum");
    fireEvent.click(within(screen.getByText("Alfa výzkum").closest("article")!).getByRole("button", { name: "Štítky" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: " cena, , Q3 " } });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole("button", { name: "OK" }));
    });
    expect(calls).toContainEqual({ path: "/api/projects/history-action", body: { project_id: "PRJ-1", action: "tags", tags: ["cena", "Q3"] } });
  });

  it("says why the screen could not load, in the unit's words", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response('{"error":"Backend bootstrap selhal."}', { status: 500 })));
    render(<ProjectsScreen />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Správce projektů se nepodařilo načíst")).toBeTruthy();
    expect(screen.getByText("Backend bootstrap selhal.")).toBeTruthy();
  });
});
