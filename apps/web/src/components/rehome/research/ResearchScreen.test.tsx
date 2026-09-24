// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resetBootCache } from "@/unit/boot";
import { REBUILT_STEPS, STEP_KEYS } from "@/unit/research/steps";
import { ResearchScreen } from "./ResearchScreen";
import { STEP_SCREENS } from "./steps";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/research/PRJ-1/questionnaire", useRouter: () => ({ replace }) }));

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));

function unitStub(load: () => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) => {
      const u = String(url);
      const body =
        u === "/api/bootstrap" ? { empty_project: EMPTY, ai_provider: "claude_code_subscription", panel: { version: "v17.1.2" }, edition: { version: "18.6.6" }, joint_core: { status: "JOINT_UNVALIDATED" } }
        : u === "/api/projects/load" ? load()
        : u.startsWith("/api/providers/claude-code/status") ? { ok: true }
        : {};
      return body instanceof Response ? body : new Response(JSON.stringify(body), { status: 200 });
    }),
  );
}

beforeEach(() => resetBootCache());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("ResearchScreen", () => {
  it("draws the step in the shell with the project's steps, and hands a step not yet rebuilt to the classic interface", async () => {
    unitStub(() => ({ project_id: "PRJ-1", revision: 2, project_type: "research", project: { title: "Alfa" }, analysis: null }));
    render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    expect(await screen.findByRole("link", { name: /Otevřít krok v klasickém rozhraní/ })).toHaveProperty("href", "http://localhost:3000/#aia:open=PRJ-1@questionnaire");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("3. Dotazník");
    expect(screen.getByText(/VÝZKUM · KROK 3 \/ 7/)).toBeTruthy();
    const steps = screen.getAllByRole("link").filter((a) => a.getAttribute("href")?.startsWith("/app/research/PRJ-1/"));
    expect(steps.map((a) => a.getAttribute("href"))).toEqual(
      ["brief", "plan", "questionnaire", "audience", "persona", "run", "results"].map((s) => `/app/research/PRJ-1/${s}`),
    );
    expect(within(steps[2]).getByText("Dotazník").closest("a")?.getAttribute("aria-current")).toBe("step");
    expect(screen.getByText("Uloženo")).toBeTruthy();
  });

  it("does not open a DEMO or a simulation here", async () => {
    unitStub(() => ({ is_demo: true }));
    render(<ResearchScreen projectId="PRJ-DEMO-1" step="brief" />);
    expect(await screen.findByText(/Toto je DEMO projekt/)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Otevřít v klasickém rozhraní/ }).getAttribute("href")).toBe("/#aia:open=PRJ-DEMO-1");
  });

  it("says why a project could not be loaded, and retries", async () => {
    let fail = true;
    unitStub(() => (fail ? new Response('{"error":"Projekt neexistuje."}', { status: 404 }) : { project_id: "PRJ-1", project_type: "research", project: {} }));
    render(<ResearchScreen projectId="PRJ-1" step="plan" />);
    expect(await screen.findByText("Projekt neexistuje.")).toBeTruthy();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Zkusit znovu" }));
    expect(await screen.findByText(/Tento krok zatím běží v klasickém rozhraní/)).toBeTruthy();
  });

  it("says a project with no saved version has nowhere to hand off to yet", async () => {
    unitStub(() => ({}));
    render(<ResearchScreen projectId={null} step="questionnaire" />);
    const note = await screen.findByText(/Projekt ještě nemá uloženou verzi/);
    expect(note).toBeTruthy();
  });

  it("loads a project once, however often the screen re-renders", async () => {
    unitStub(() => ({ project_id: "PRJ-1", revision: 2, project_type: "research", project: {}, analysis: null }));
    const { rerender } = render(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    await screen.findByText("Uloženo");
    rerender(<ResearchScreen projectId="PRJ-1" step="audience" />);
    rerender(<ResearchScreen projectId="PRJ-1" step="questionnaire" />);
    await screen.findByText("Uloženo");
    const loads = (fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls.filter((c) => String(c[0]) === "/api/projects/load");
    expect(loads.length).toBe(1);
  });

  it("lists as rebuilt exactly the steps that have a screen", () => {
    for (const k of STEP_KEYS) expect(REBUILT_STEPS.has(k), k).toBe(k in STEP_SCREENS);
  });
});
