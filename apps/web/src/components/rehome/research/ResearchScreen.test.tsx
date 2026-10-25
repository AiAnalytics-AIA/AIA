// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t, tv } from "@/i18n/t";
import { defaultsMerge, type Template } from "@/research/model";
import { REBUILT_STEPS, STEP_KEYS } from "@/research/steps";
import { ResearchScreen, ResearchSession, aiHelpFor } from "./ResearchScreen";
import { STEP_SCREENS } from "./steps";
import { TEST_FRAME, stagePath } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ replace }) }));

const GOAL_LABEL = t("research.brief.goalLabel");

type Call = { method: string; url: string; body: Record<string, unknown> | null };
let calls: Call[] = [];

/** AIA, answering the study's working content with `load` (and any save with `save`); `routes`
 * ("METHOD /path") answer anything else a test needs before the defaults. */
function api(load: () => unknown, save: (b: Record<string, unknown>) => unknown = () => ({ state: "NATIVE", revision: 1, revision_id: "REV-1", deduplicated: false }), routes: Record<string, () => unknown> = {}) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url).split("?")[0];
      const method = init?.method ?? "GET";
      const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;
      calls.push({ method, url: u, body });
      const route = routes[`${method} ${u}`];
      const answer =
        route ? route()
        : u === "/config" ? { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost" }
        : u === CONTENT_PATH && method === "GET" ? load()
        : u === CONTENT_PATH && method === "PUT" ? save(body ?? {})
        : u.endsWith("/research/readiness") ? { design_revision_id: "REV-3", revision: 3, ready: false, checks: [], questions: 0, batteries: 0, objects: 0, n: 0, rules: "test" }
        : u.endsWith("/research/runs") ? { items: [] }
        : u.endsWith("/design/revisions") && method === "POST" ? { revision_id: "REV-3", revision: 3 }
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
  // Every test here also proves the screen reached nothing of the 18.6.6 unit (ADR 0018).
  expect(calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config").map((c) => c.url)).toEqual([]);
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
    // Průběh is a stage of its own on the track (research-lane-redesign).
    expect(steps.map((a) => a.getAttribute("href"))).toEqual(
      (["brief", "plan", "questionnaire", "audience", "persona", "run", "progress", "results"] as const).map((s) => stagePath(s)),
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
    await vi.waitFor(() => expect(saves()).toHaveLength(1), { timeout: 10_000 });
    expect(saves()[0].body).toMatchObject({ base_revision: null, content: { goal: "Znovu od začátku" } });
  });

  it("says a recovered study's content is its last submitted design, and edits it as any other", async () => {
    api(() => content({ state: "RECOVERED", revision: 1, revision_id: "REV-1", lineage: { outcome: "recovered", design_revision: 4 } }));
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    const notice = await screen.findByText(tv("research.recoveredFrom", { revision: 4 }));
    expect(notice.getAttribute("role")).toBe("status");
    fireEvent.change(await screen.findByLabelText(GOAL_LABEL), { target: { value: "Pokračujeme" } });
    await vi.waitFor(() => expect(saves()).toHaveLength(1), { timeout: 10_000 });
    expect(saves()[0].body).toMatchObject({ base_revision: 1, content: { goal: "Pokračujeme" } });
  });

  it("does not offer a reader to start a lost study again", async () => {
    api(() => content({ state: "UNRECOVERABLE", revision: null, revision_id: null, content: null, can_edit: false }));
    render(<ResearchScreen step="brief" frame={{ ...TEST_FRAME, canEdit: false }} />);
    expect(await screen.findByText(t("research.unrecoverableReadOnly"))).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("research.startAgain") })).toBeNull();
  });

  it("says a delivered study is closed, keeps its design read-only and saves nothing", async () => {
    api(() => content({ can_edit: false }));
    const closed = { ...TEST_FRAME, canEdit: false, canReview: true, closed: { status: "DELIVERED", deliveredAt: "2026-10-17T09:00:00Z" } };
    render(<ResearchScreen step="brief" frame={closed} />);
    const goal = (await screen.findByLabelText(GOAL_LABEL)) as HTMLTextAreaElement;
    // Said once, on the stage: what it is and what still works.
    expect(screen.getByText(tv("aia.study.closed.DELIVERED_on", { when: new Date("2026-10-17T09:00:00Z").toLocaleDateString("cs-CZ") }))).toBeTruthy();
    expect(screen.getByText(t("aia.study.closed.help"))).toBeTruthy();
    // Settings no longer changes a study's status (F7): the notice never sends a person there.
    expect(document.querySelector('[data-study-closed] a[href*="settings"]')).toBeNull();
    expect(t("aia.study.closed.reopen")).not.toMatch(/Nastavení/);
    // Every control of the design is disabled as one, and nothing is sent.
    expect(goal.closest("fieldset")?.disabled).toBe(true);
    expect(goal.closest("fieldset")?.getAttribute("role")).toBe("none"); // disables, announces no group
    // So are the stage's own actions in the column beside it (the brief's AI proposal).
    const inspector = document.querySelector("[data-inspector]");
    const actions = [...(inspector?.querySelectorAll("fieldset button") ?? [])] as HTMLButtonElement[];
    expect(actions.length).toBeGreaterThan(0);
    expect(actions.every((b) => b.closest("fieldset")?.disabled)).toBe(true);
    expect(screen.getByText(t("research.saveReadOnly"))).toBeTruthy();
    fireEvent.change(goal, { target: { value: "Nový cíl" } });
    await new Promise((r) => setTimeout(r, 2100));
    expect(saves()).toHaveLength(0);
    expect(screen.queryByText(t("research.saveFailed"))).toBeNull();
  });

  it("changes the study's status on the study, and reopens a closed one in place (F7)", async () => {
    let status = "DELIVERED";
    const refreshed: string[] = [];
    api(() => content({ can_edit: false }), undefined, {
      "PUT /api/v1/studies/STU-1/status": () => { status = String(calls.at(-1)?.body?.status); return { study_id: "STU-1", status }; },
    });
    const frame = {
      ...TEST_FRAME, canEdit: false, canReview: true, status, closed: { status, deliveredAt: null },
      refreshStudy: async () => { refreshed.push(status); },
    };
    render(<ResearchScreen step="brief" frame={frame} />);
    await screen.findByLabelText(GOAL_LABEL);
    // The header's control names the status and offers every other one.
    fireEvent.click(await screen.findByRole("button", { name: "Stav: Předáno" }));
    expect(within(screen.getByRole("menu", { name: "Stav: Předáno" })).getAllByRole("menuitem").map((i) => i.textContent))
      .toEqual(["Rozpracováno", "Aktivní", "V kontrole", "Archivováno", "Zrušeno"]);
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
    // The notice reopens it where it stands, to a status that accepts work.
    const notice = document.querySelector("[data-study-closed]") as HTMLElement;
    fireEvent.click(within(notice).getByRole("button", { name: t("aia.study.closed.reopen") }));
    fireEvent.click(within(screen.getByRole("menu", { name: t("aia.study.closed.reopen") })).getByRole("menuitem", { name: "Aktivní" }));
    await vi.waitFor(() => expect(refreshed).toEqual(["ACTIVE"]));
    expect(calls.filter((c) => c.method === "PUT" && c.url === "/api/v1/studies/STU-1/status").map((c) => c.body)).toEqual([{ status: "ACTIVE" }]);
  });

  it("says the API's refusal of a status change as given", async () => {
    api(() => content(), undefined, {
      "PUT /api/v1/studies/STU-1/status": () => new Response(JSON.stringify({ code: "forbidden", message: "Delivery needs sign-off" }), { status: 403 }),
    });
    render(<ResearchScreen step="brief" frame={{ ...TEST_FRAME, status: "ACTIVE", refreshStudy: async () => {} }} />);
    await screen.findByLabelText(GOAL_LABEL);
    fireEvent.click(await screen.findByRole("button", { name: "Stav: Aktivní" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Předáno" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Delivery needs sign-off");
  });

  it("reads an AI proposal on a closed study's run stage and closes it, never applies it (review, Codex on #479)", async () => {
    const job = { run_id: "RUN-J1", design_revision_id: "REV-2", action: "build_questionnaire", status: "COMPLETED", is_terminal: true,
      needs_attention: false, context_sha256: "x", harness_version: "3", created_at: "2026-10-17T09:00:00Z", steps: [], actual_cost_usd: 0.1,
      proposal_state: "pending" };
    const proposed = { title: "Alfa", sections: [{ id: "ai_section_1", type: "questions", title: "Zvyky", questions: [{ id: "ai_q_1_1", text: "Jak často pijete kávu?", typ: "skala" }] }] };
    api(() => content({ can_edit: false }), undefined, {
      "GET /api/v1/studies/STU-1/research/agent-jobs": () => [job],
      // The revision the job was asked over is the working copy as loaded: a proposal, not advice.
      "GET /api/v1/studies/STU-1/design/revisions/REV-2": () => ({ revision_id: "REV-2", revision: 2,
        content: defaultsMerge({ title: "Alfa" }, { empty_project: EMPTY_PROJECT } as unknown as Template) }),
      "GET /api/v1/studies/STU-1/research/agent-jobs/RUN-J1/result": () => ({
        result: { project: proposed, proposal: { message: "Návrh", sections: proposed.sections, warnings: [], comparisons: [] } },
        provenance: { agent_id: "aia.research.build_questionnaire", design_revision_id: "REV-2", context_sha256: "x", status: "COMPLETED" },
      }),
    });
    const closed = { ...TEST_FRAME, canEdit: false, canReview: true, closed: { status: "DELIVERED", deliveredAt: "2026-10-17T09:00:00Z" } };
    render(<ResearchScreen step="results" frame={closed} />);
    const saved = (await screen.findByRole("heading", { name: t("research.aiSaved") })).parentElement as HTMLElement;
    fireEvent.click(within(saved).getByRole("button"));
    const review = (await screen.findByRole("button", { name: "Použít návrh" })).closest("[data-proposal-review]") as HTMLElement;
    // Read, with the reason it cannot be applied; closing it writes nothing and stays possible.
    expect(within(review).getByText(t("research.proposalClosed"))).toBeTruthy();
    expect((within(review).getByRole("button", { name: "Použít návrh" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(review).getByRole("button", { name: "Ponechat současný návrh" }));
    await new Promise((r) => setTimeout(r, 50));
    expect(document.querySelector("[data-proposal-review]")).toBeNull();
    expect(calls.filter((c) => c.method === "POST" && c.url.endsWith("/accept"))).toEqual([]);
  });

  it("wraps an editable stage in nothing: the read-only fieldset exists only on a closed study", async () => {
    api(() => content());
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    await screen.findByLabelText(GOAL_LABEL);
    // No unnamed group round the stage or its column, nothing for a selector to match (journey review).
    expect(document.querySelector('fieldset[role="none"]')).toBeNull();
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
    await screen.findByRole("list", { name: t("research.exec.steps.preflight") });
    rerender(page("results"));
    expect(await screen.findByRole("heading", { level: 1, name: "Výsledky" })).toBeTruthy();
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
    // Inside a study the global navigation is icons only: the four AIA destinations, each named
    // for assistive technology (research-lane-redesign); the client is in the breadcrumbs.
    const global = within(screen.getByRole("navigation", { name: "Hlavní navigace" })).getAllByRole("link").map((a) => a.getAttribute("aria-label"));
    expect(global).toEqual(["AI Analytics", "Klienti", "Společenská inteligence", "Projektová paměť", "Nastavení"]);
    expect(screen.getByRole("link", { name: /Zpět na klienta/ }).getAttribute("href")).toBe("/app/clients/CLI-1");
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
    await vi.waitFor(() => expect(saves()).toHaveLength(1), { timeout: 10_000 });
    expect(saves()[0].body).toMatchObject({ base_revision: null, reason: "autosave", content: { title: "Nový výzkum", goal: "Zjistit zájem o službu" } });
    expect(Object.keys(saves()[0].body ?? {}).sort()).toEqual(["analysis", "base_revision", "content", "reason"]); // no project, unit or client id
    fireEvent.change(screen.getByLabelText(GOAL_LABEL), { target: { value: "Zjistit zájem o novou službu" } });
    await vi.waitFor(() => expect(saves()).toHaveLength(2), { timeout: 10_000 });
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
    expect(await screen.findByText(t("research.saveConflict"))).toBeTruthy();
    expect(saves()).toHaveLength(1);
    // A further edit is not saved over the newer revision.
    fireEvent.change(screen.getByLabelText(GOAL_LABEL), { target: { value: "Moje verze 2" } });
    await new Promise((r) => setTimeout(r, 2100));
    expect(saves()).toHaveLength(1);
    served = content({ revision: 3, content: { title: "Alfa", goal: "Jejich verze" } });
    fireEvent.click(screen.getByRole("button", { name: t("research.saveReload") }));
    // The field is there before the reload lands; wait for its value, not for the field.
    await vi.waitFor(() => expect((screen.getByLabelText(GOAL_LABEL) as HTMLTextAreaElement).value).toBe("Jejich verze"), { timeout: 10_000 });
  });

  it("lists as rebuilt exactly the steps that have a screen", () => {
    for (const k of STEP_KEYS) expect(REBUILT_STEPS.has(k), k).toBe(k in STEP_SCREENS);
  });

  describe("an AI job stopped at the study's budget (CR-2)", () => {
  const JOBS = "/api/v1/studies/STU-1/research/agent-jobs";
  const job = (status: string, stepStatus: string) => ({ run_id: "RUN-J1", design_revision_id: "REV-3", action: "propose_audience", status,
    is_terminal: status === "COMPLETED", needs_attention: status === "AWAITING_BUDGET", context_sha256: "x", harness_version: "2",
    created_at: "2026-10-20T09:00:00Z", actual_cost_usd: null, proposal_state: status === "COMPLETED" ? "pending" : null,
    steps: [{ step_id: "STEP-agent", node_key: "agent", status: stepStatus, waiting_reason: stepStatus === "AWAITING_BUDGET" ? "budget_exceeded" : null, error_message: null }] });
  const AUDIENCE = { content: { title: "Alfa", audience: { strategy: "filters" }, ui_state: { audience_entry: "analytics", analytics_choice: "cz18" } } };
  /** The study's AI job, waiting for budget until lifted; `listed` puts it in the screen's list of jobs too. */
  /** `runningPolls`: how many reads of the job after the lift still find it running (a slow job). */
  const waitingJob = (listed: boolean, runningPolls = 0) => {
    const state = { lifted: false, polls: 0 };
    const now = () => {
      if (!state.lifted) return job("AWAITING_BUDGET", "AWAITING_BUDGET");
      return state.polls <= runningPolls ? job("RUNNING", "RUNNING") : job("COMPLETED", "SUCCEEDED");
    };
    api(() => content(AUDIENCE), undefined, {
      [`POST ${JOBS}`]: () => job("AWAITING_BUDGET", "AWAITING_BUDGET"),
      [`GET ${JOBS}`]: () => (listed ? [now()] : []),
      [`GET ${JOBS}/RUN-J1`]: () => { if (state.lifted) state.polls += 1; return now(); },
      [`POST ${JOBS}/RUN-J1/budget`]: () => { state.lifted = true; return job("RUNNING", "RUNNABLE"); },
      [`GET ${JOBS}/RUN-J1/result`]: () => ({
        result: { project: { title: "Alfa" }, proposal: { message: "Návrh audience" } },
        provenance: { agent_id: "aia.research.propose_audience", design_revision_id: "REV-3", context_sha256: "x", status: "COMPLETED" },
      }),
      "GET /api/v1/studies/STU-1/design/revisions/REV-3": () => ({ revision_id: "REV-3", revision: 3,
        content: defaultsMerge({ title: "Alfa" }, { empty_project: EMPTY_PROJECT } as unknown as Template) }),
      "GET /api/v1/studies/STU-1": () => ({ study_id: "STU-1", name: "Alfa", budget_usd: 5, spent_usd: 4.8, remaining_usd: 0.2 }),
      "GET /api/v1/population/audience-catalogue": () => new Response('{"code":"not_found","message":"No such resource."}', { status: 404 }),
    });
    return state;
  };
  const lift = async (form: HTMLElement, total: string) => {
    await within(form).findByText(/5\.00/);
    fireEvent.change(within(form).getByLabelText(t("research.exec.budget.amount")), { target: { value: total } });
    fireEvent.click(within(form).getByRole("button", { name: t("research.exec.budget.lift") }));
  };

  it("offers one lift for a wait the stage shows in place, never a second in the job list, and opens the proposal from it (Codex on #533)", async () => {
    waitingJob(true);
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByPlaceholderText(t("research.audience.describePlaceholder")), { target: { value: "Ženy 30-45 let" } });
    fireEvent.click(screen.getByRole("button", { name: t("research.audience.propose") }));
    await screen.findByRole("status", { name: t("research.aiBudget.waitingTitle") });
    // The list was read again with the job in it (the start refreshes it), and still one form.
    await vi.waitFor(() => expect(calls.filter((c) => c.method === "GET" && c.url === JOBS).length).toBeGreaterThanOrEqual(2));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getAllByRole("form", { name: t("research.exec.budget.title") })).toHaveLength(1);
    expect(screen.queryByRole("heading", { name: t("research.aiBudget.title") })).toBeNull();
    await lift(screen.getByRole("form", { name: t("research.exec.budget.title") }), "8");
    expect(await screen.findByRole("button", { name: "Použít návrh" }, { timeout: 5000 })).toBeTruthy();
  });

  it("offers no second lift while a lifted job still runs, though the list was last read while it waited (review P2-1)", async () => {
    const state = waitingJob(true, 2);
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByPlaceholderText(t("research.audience.describePlaceholder")), { target: { value: "Ženy 30-45 let" } });
    fireEvent.click(screen.getByRole("button", { name: t("research.audience.propose") }));
    await screen.findByRole("status", { name: t("research.aiBudget.waitingTitle") });
    await vi.waitFor(() => expect(calls.filter((c) => c.method === "GET" && c.url === JOBS).length).toBeGreaterThanOrEqual(2));
    await lift(screen.getByRole("form", { name: t("research.exec.budget.title") }), "8");
    // The job reads RUNNING on its first two polls after the lift: no lift form anywhere then.
    await vi.waitFor(() => expect(state.polls).toBeGreaterThanOrEqual(1), { timeout: 5000 });
    expect(screen.queryAllByRole("form")).toHaveLength(0);
    expect(screen.queryByRole("heading", { name: t("research.aiBudget.title") })).toBeNull();
    await vi.waitFor(() => expect(state.polls).toBeGreaterThanOrEqual(2), { timeout: 5000 });
    expect(screen.queryAllByRole("form")).toHaveLength(0);
    expect(await screen.findByRole("button", { name: "Použít návrh" }, { timeout: 8000 })).toBeTruthy();
    expect(screen.queryAllByRole("form")).toHaveLength(0);
    expect(calls.filter((c) => c.method === "POST" && c.url === `${JOBS}/RUN-J1/budget`)).toHaveLength(1);
  });

  it("opens the proposal of a job lifted from the screen's list of waiting jobs, which no stage shows in place", async () => {
    waitingJob(true);
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    const list = (await screen.findByRole("heading", { name: t("research.aiBudget.title") }, { timeout: 5000 })).parentElement as HTMLElement;
    expect(screen.getAllByRole("form")).toHaveLength(1);
    await lift(within(list).getByRole("form"), "8");
    expect(await screen.findByRole("button", { name: "Použít návrh" }, { timeout: 5000 })).toBeTruthy();
    expect(calls.filter((c) => c.method === "POST" && c.url === JOBS)).toEqual([]); // nothing started
  });

  it("shows a stage's AI job stopped at the budget as waiting, lifts it in place and goes on with the same job (CR-2)", async () => {
    waitingJob(false);
    render(<ResearchScreen step="audience" frame={TEST_FRAME} />);
    fireEvent.change(await screen.findByPlaceholderText(t("research.audience.describePlaceholder")), { target: { value: "Ženy 30-45 let" } });
    fireEvent.click(screen.getByRole("button", { name: t("research.audience.propose") }));

    // Waiting in words, with the study's budget lift where the failure was: no retry, no fault.
    const card = await screen.findByRole("status", { name: t("research.aiBudget.waitingTitle") });
    expect(within(card).getByText(t("research.aiBudget.waitingHelp"))).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("research.retry") })).toBeNull();
    expect(screen.queryByText(t("research.audience.failedTitle"))).toBeNull();
    const form = within(card).getByRole("form", { name: t("research.exec.budget.title") });
    await within(form).findByText(/5\.00/);
    expect(within(form).getByText(t("research.exec.budgetLine.holdsNotCounted"))).toBeTruthy();
    fireEvent.change(within(form).getByLabelText(t("research.exec.budget.amount")), { target: { value: "8" } });
    fireEvent.click(within(form).getByRole("button", { name: t("research.exec.budget.lift") }));

    await vi.waitFor(() => expect(calls.filter((c) => c.method === "GET" && c.url === `${JOBS}/RUN-J1/result`)).toHaveLength(1));
    expect(calls.filter((c) => c.method === "POST" && c.url === `${JOBS}/RUN-J1/budget`).map((c) => c.body)).toEqual([{ budget_usd: 8, note: "" }]);
    // The same job went on: one start, never a second job for the waiting one.
    expect(calls.filter((c) => c.method === "POST" && c.url === JOBS)).toHaveLength(1);
    await vi.waitFor(() => expect(screen.queryByRole("status", { name: t("research.aiBudget.waitingTitle") })).toBeNull());
  });
  });
});

describe("AI pomoc (Studio v3)", () => {
  const offered = (step: Parameters<typeof aiHelpFor>[0]) => aiHelpFor(step).map((a) => a.action);

  it("offers each AI action only on the steps it helps", () => {
    expect(offered("brief")).toEqual(["answer_memory"]);
    for (const step of ["plan", "questionnaire", "audience", "persona"] as const) {
      expect(offered(step), step).toEqual(["critique_design", "design_copilot", "answer_memory"]);
    }
    expect(offered("run")).toEqual(["critique_design", "answer_memory"]);
    expect(offered("progress")).toEqual(offered("run"));
    expect(offered("results")).toEqual(["answer_memory"]);
    expect(offered("verify")).toEqual(["answer_memory"]);
  });

  it("places the same AI actions in the column beside the stage, with a prefill-only suggestion", async () => {
    api(() => content());
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    await screen.findByText("Uloženo");
    const bar = screen.getByRole("region", { name: t("research.aiHelpLabel") });
    // Beside the work, in the inspector, not in the page header (research-lane-redesign).
    expect(bar.closest("[data-inspector]")).not.toBeNull();
    const buttons = within(bar).getAllByRole("button").filter((b) => b.hasAttribute("data-ai-action"));
    expect(buttons.map((b) => b.textContent)).toEqual([t("research.aiCritique"), t("research.aiCopilot"), t("research.aiMemory")]);
    for (const b of buttons) {
      expect(b.getAttribute("data-ai-action")).toBe("true");
      expect(b.getAttribute("title")).toBe(t("research.aiActionTitle"));
    }
    fireEvent.click(within(bar).getByRole("button", { name: /Které výzkumné otázky/ }));
    expect((screen.getByRole("textbox", { name: "Co chcete zjistit?" }) as HTMLTextAreaElement).value).toBe("Které výzkumné otázky potřebují zpřesnit, aby podpořily rozhodnutí?");
    expect(screen.getByRole("complementary", { name: "Pomoc s návrhem" })).toBeTruthy();
  });
});
