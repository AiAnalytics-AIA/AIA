// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { REBUILT_STEPS, STEP_KEYS } from "@/research/steps";
import { ResearchScreen, ResearchSession } from "./ResearchScreen";
import { STEP_SCREENS } from "./steps";
import { TEST_FRAME, stagePath } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ replace }) }));

const GOAL_LABEL = t("research.brief.goalLabel");

type Call = { method: string; url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];

/** AIA, answering the study's working content with `load` (and any save with `save`). */
function api(load: () => unknown, save: (b: Record<string, unknown>) => unknown = () => ({ state: "NATIVE", revision: 1, revision_id: "REV-1", deduplicated: false })) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url).split("?")[0];
      const method = init?.method ?? "GET";
      const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;
      calls.push({ method, url: u, body });
      const answer =
        u === "/config" ? { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" }
        : u === CONTENT_PATH && method === "GET" ? load()
        : u === CONTENT_PATH && method === "PUT" ? save(body ?? {})
        : u.endsWith("/research/agent-jobs") ? []
        : {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const content = (over: Record<string, unknown> = {}) => ({
  study_id: "STU-1", state: "NATIVE", revision: 2, revision_id: "REV-2", content: { title: "Alfa" }, analysis: null,
  template: EMPTY_PROJECT, saved_at: null, saved_by: null, can_edit: true, lineage: {}, ...over,
});
const loads = () => calls.filter((c) => c.method === "GET" && c.url === CONTENT_PATH);
const saves = () => calls.filter((c) => c.method === "PUT" && c.url === CONTENT_PATH);

beforeEach(() => signedIn());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("ResearchScreen", () => {
  it("draws the step in the shell with the study's steps, and says a step AIA has not rebuilt is not in AIA", async () => {
    api(() => content());
    // Verification is not rebuilt, and there is no 18.6.6 interface to hand off to (ADR 0018).
    render(<ResearchScreen step="verify" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.notInAia"))).toBeTruthy();
    expect(screen.queryByRole("link", { name: /klasick/i })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("8. Ověření & kontext");
    expect(screen.getByText(t("aia.kind.RESEARCH"))).toBeTruthy(); // not a rail step: no step counter
    const rail = screen.getByRole("navigation", { name: "Fáze výzkumu" });
    const steps = within(rail).getAllByRole("link");
    expect(steps.map((a) => a.getAttribute("href"))).toEqual(
      (["brief", "plan", "questionnaire", "audience", "persona", "run", "results"] as const).map((s) => stagePath(s)),
    );
    expect(steps[4].getAttribute("href")).toBe("/app/clients/CLI-1/research/STU-1/dimensions");
    expect(steps.some((a) => a.getAttribute("aria-current") === "step")).toBe(false);
    expect(screen.getByText("Uloženo")).toBeTruthy();
    // Nothing reached the 18.6.6 unit's paths.
    expect(calls.filter((c) => c.url.startsWith("/api/") && !c.url.startsWith("/api/v1/"))).toEqual([]);
  });

  it("says a study whose content still waits in 18.6.6 cannot be opened yet, and never saves over it", async () => {
    api(() => content({ state: "AWAITING_MIGRATION", revision: null, revision_id: null, content: null, can_edit: false }));
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.awaitingMigration"))).toBeTruthy();
    expect(screen.queryByLabelText(GOAL_LABEL)).toBeNull();
    expect(saves()).toEqual([]);
  });

  it("says a study's 18.6.6 content was lost, and lets an editor start again from the template", async () => {
    api(() => content({ state: "UNRECOVERABLE", revision: null, revision_id: null, content: null, lineage: { outcome: "unit project missing" } }));
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.unrecoverable"))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t("research.startAgain") }));
    fireEvent.change(await screen.findByLabelText(GOAL_LABEL), { target: { value: "Znovu od začátku" } });
    await vi.waitFor(() => expect(saves()).toHaveLength(1), { timeout: 4000 });
    expect(saves()[0].body).toMatchObject({ base_revision: null, content: { goal: "Znovu od začátku" } });
  });

  it("does not offer a reader to start a lost study again", async () => {
    api(() => content({ state: "UNRECOVERABLE", revision: null, revision_id: null, content: null, can_edit: false }));
    render(<ResearchScreen step="brief" frame={{ ...TEST_FRAME, canEdit: false }} />);
    expect(await screen.findByText(t("research.unrecoverableReadOnly"))).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("research.startAgain") })).toBeNull();
  });

  it("says why the content could not be loaded, and retries", async () => {
    let fail = true;
    api(() => (fail ? new Response('{"code":"not_found","message":"No such resource."}', { status: 404 }) : content()));
    render(<ResearchScreen step="verify" frame={TEST_FRAME} />);
    expect(await screen.findByText("No such resource.")).toBeTruthy();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Zkusit znovu" }));
    expect(await screen.findByText(t("research.notInAia"))).toBeTruthy();
  });

  it("loads the content once, however often the screen re-renders", async () => {
    api(() => content());
    const { rerender } = render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByText("Uloženo");
    rerender(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    rerender(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByText("Uloženo");
    expect(loads()).toHaveLength(1);
  });

  it("keeps one study session while each step's page mounts afresh, as Next mounts them", async () => {
    api(() => content());
    const page = (step: "run" | "results") => (
      <ResearchSession studyId="STU-1">
        <ResearchScreen key={step} step={step} frame={TEST_FRAME} />
      </ResearchSession>
    );
    const { rerender } = render(page("run"));
    await screen.findByText("Uloženo");
    rerender(page("results"));
    expect(await screen.findByRole("heading", { name: "7. Výsledky" })).toBeTruthy();
    expect(loads()).toHaveLength(1);
  });

  it("says in the breadcrumbs which client, which study and which stage", async () => {
    api(() => content());
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByText("Uloženo");
    const crumbs = within(screen.getByRole("navigation", { name: "Kde jste" })).getAllByRole("listitem");
    expect(crumbs.map((c) => c.textContent?.replace("/", "").trim())).toEqual(["Klienti", "Klient A", "Výzkumy", "Výzkum A", "Dotazník"]);
    expect(within(crumbs[1]).getByRole("link").getAttribute("href")).toBe("/app/clients/CLI-1");
    expect(within(crumbs[3]).getByRole("link").getAttribute("href")).toBe(stagePath("brief"));
    // The stage rail is the study's own; the global navigation stays the four AIA destinations.
    const global = within(screen.getByRole("navigation", { name: "Hlavní navigace" })).getAllByRole("link").map((a) => a.textContent);
    expect(global).toEqual(["AI Analytics", "Klienti", "Společenská inteligence", "Projektová paměť", "Nastavení"]);
  });

  it("saves a new study's first change as revision one, and the next one from it", async () => {
    let revision = 0;
    api(
      () => content({ state: "EMPTY", revision: null, revision_id: null, content: null }),
      () => ({ state: "NATIVE", revision: ++revision, revision_id: `REV-${revision}`, deduplicated: false }),
    );
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.saveNew"))).toBeTruthy();
    fireEvent.change(await screen.findByLabelText(GOAL_LABEL), { target: { value: "Zjistit zájem o službu" } });
    await vi.waitFor(() => expect(saves()).toHaveLength(1), { timeout: 4000 });
    expect(saves()[0].body).toMatchObject({ base_revision: null, reason: "autosave", content: { title: "Nový výzkum", goal: "Zjistit zájem o službu" } });
    expect(Object.keys(saves()[0].body ?? {}).sort()).toEqual(["analysis", "base_revision", "content", "reason"]); // no project, unit or client id
    fireEvent.change(screen.getByLabelText(GOAL_LABEL), { target: { value: "Zjistit zájem o novou službu" } });
    await vi.waitFor(() => expect(saves()).toHaveLength(2), { timeout: 4000 });
    expect(saves()[1].body).toMatchObject({ base_revision: 1 });
  });

  it("says when someone else saved first, keeps their version, and reloads it on request", async () => {
    let served = content({ revision: 2 });
    api(
      () => served,
      () => new Response('{"code":"stale_revision","message":"saved elsewhere","details":{"current_revision":3}}', { status: 409 }),
    );
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByLabelText(GOAL_LABEL), { target: { value: "Moje verze" } });
    expect(await screen.findByText(t("research.saveConflict"), {}, { timeout: 4000 })).toBeTruthy();
    expect(saves()).toHaveLength(1);
    // A further edit is not saved over the newer revision.
    fireEvent.change(screen.getByLabelText(GOAL_LABEL), { target: { value: "Moje verze 2" } });
    await new Promise((r) => setTimeout(r, 2100));
    expect(saves()).toHaveLength(1);
    served = content({ revision: 3, content: { title: "Alfa", goal: "Jejich verze" } });
    fireEvent.click(screen.getByRole("button", { name: t("research.saveReload") }));
    expect(((await screen.findByLabelText(GOAL_LABEL)) as HTMLTextAreaElement).value).toBe("Jejich verze");
  });

  it("lists as rebuilt exactly the steps that have a screen", () => {
    for (const k of STEP_KEYS) expect(REBUILT_STEPS.has(k), k).toBe(k in STEP_SCREENS);
  });
});
