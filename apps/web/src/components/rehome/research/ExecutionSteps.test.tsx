// @vitest-environment jsdom
// Run, Progress and Results (ADR 0016) against a fake AIA API. What they must do:
// submit the design the person sees as a Design Revision, say what AIA's checks
// say, start one run over that revision, explain a run waiting for the AI
// runtime, hide a suppressed cell's numbers, label fictional data every time, and
// keep the internal Sociomap internal.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { t } from "@/i18n/t";
import { CONFLICT_MESSAGE } from "@/research/store";
import { ResearchScreen, ResearchSession } from "./ResearchScreen";
import { CONTENT_PATH, workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

const push = vi.fn();
const replace = vi.fn();
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/run", useRouter: () => ({ push, replace }) }));

const PROJECT = { title: "Ranní nápoj", n: 450, sections: [{ type: "questions", questions: [{ id: "q1", text: "Jak často?", typ: "skala", skala: [1, 5] }] }] };

const READY = {
  design_revision_id: "REV-a1", rules: "aia-structural-readiness-1", ready: true, questions: 1, batteries: 1, objects: 5, n: 450,
  fieldwork_source: "ai_runtime",
  checks: [
    { id: "sample_size", status: "PASS", message: "n = 450." },
    { id: "audience", status: "WARN", message: "AIA zatím nepoužije filtry." },
  ],
};
const step = (node: string, status: string, extra: Record<string, unknown> = {}) => ({
  node_key: node, kind: `research_${node}`, stage_type: "BRIEF", status, waiting_reason: null, attempts_recorded: 1, max_attempts: 3,
  started_at: "2026-09-25T08:00:00Z", finished_at: null, failure_class: null, error_message: null, artifact_id: null, data_origin: null, ...extra,
});
const run = (extra: Record<string, unknown> = {}) => ({
  run_id: "RUN-1", study_id: "STU-1", design_revision_id: "REV-a1", design_revision: 3, status: "RUNNING", phase: "RUNNING",
  needs_attention: false, is_terminal: false, retryable: false, cancel_requested: false, fieldwork_source: "ai_runtime",
  retry_of: null, created: null, created_at: "2026-09-25T08:00:00Z", started_at: "2026-09-25T08:00:00Z", finished_at: null,
  steps: [], artifact_ids: [], actual_cost_usd: null, ...extra,
});
const PARKED = run({
  status: "WAITING_PROVIDER", phase: "WAITING",
  steps: [
    step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
    step("preflight", "SUCCEEDED", { artifact_id: "ART-2" }),
    step("run", "WAITING_PROVIDER", { waiting_reason: "ai_runtime_unavailable", failure_class: "RUNTIME_UNAVAILABLE" }),
    step("aggregate", "BLOCKED", { attempts_recorded: 0, started_at: null }),
    step("sociomap", "BLOCKED", { attempts_recorded: 0, started_at: null }),
  ],
});
const parkedWith = (steps: ReturnType<typeof step>[]) => run({ status: "WAITING_PROVIDER", phase: "WAITING", steps });
const COMPLETED = run({
  status: "COMPLETED", phase: "COMPLETED", is_terminal: true, fieldwork_source: "synthetic_fixture", finished_at: "2026-09-25T08:05:00Z",
  steps: [
    step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
    step("preflight", "SUCCEEDED", { artifact_id: "ART-2" }),
    step("run", "SUCCEEDED", { artifact_id: "ART-3", data_origin: "SYNTHETIC_FIXTURE" }),
    step("aggregate", "SUCCEEDED", { artifact_id: "ART-4", data_origin: "SYNTHETIC_FIXTURE" }),
    step("sociomap", "SUCCEEDED", { artifact_id: "ART-5", data_origin: "SYNTHETIC_FIXTURE" }),
  ],
});
// What the API gives: the Study's list is a summary (no steps, no artifacts); the run itself is read in full.
const listed = (...runs: ReturnType<typeof run>[]) => {
  const routes: Record<string, () => unknown> = {
    "GET /api/v1/studies/STU-1/research/runs": () => ({ items: runs.map((r) => ({ ...r, steps: [], artifact_ids: [] })) }),
  };
  for (const r of runs) routes[`GET /api/v1/studies/STU-1/research/runs/${r.run_id}`] = () => r;
  return routes;
};
const support = (status: string, donors: number) => ({ support_status: status, n_platnych: 120, n_unique_layer_donors: donors, effective_n: 30 });
const AGGREGATE = {
  artifact_id: "ART-4", artifact_type: "research_aggregate", stage_type: "AGGREGATION", revision: 3, content_type: "application/json",
  sha256: "abcdef0123456789", size_bytes: 10, status: "VALID", runtime_version: "a15be65", produced_by_job_id: null, created_at: null,
  payload: {
    aggregate: {
      data_origin: "SYNTHETIC_FIXTURE",
      questions: {
        q2: { typ: "vyber", ...support("REPORTABLE", 140), celkem_pct: { Kávu: 34.8, Čaj: 38.4 }, intervaly_95: { Kávu: { low: 30.1, high: 39.9 }, Čaj: { low: 33.0, high: 43.2 } } },
        t1: { typ: "skala", ...support("SUPPRESS", 19), prumer: 3.73, prumer_interval_95: { low: 3.25, high: 4.28 }, top2box_pct: 22.1, top2box_interval_95: { low: 10, high: 30 } },
      },
      batteries: {},
    },
  },
};
const SOCIOMAP = {
  ...AGGREGATE, artifact_id: "ART-5", artifact_type: "research_sociomap",
  payload: {
    sociomap: {
      methodology_status: "INTERNAL_ONLY",
      batteries: [{
        battery_id: "napoje", title: "Nápoje", methodology_status: "INTERNAL_ONLY",
        objects: [{ id: "kava", label: "Káva" }, { id: "caj", label: "Čaj" }, { id: "voda", label: "Voda" }],
        relation: { scores: [6.14, 6.47, 5.89] },
        sociomap: { object_ids: ["kava", "caj", "voda"], layout: { object_xy: [[1.5, -2], [0, 3], [-4, 1]] } },
      }],
    },
  },
};

type Call = { method: string; url: string; body: unknown };
let calls: Call[] = [];
function api(overrides: Record<string, (body: unknown) => unknown> = {}) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ method, url: u, body });
      const routes: Record<string, (b: unknown) => unknown> = {
        "GET /config": () => ({ cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", apiBase: "", build: { sha: null } }),
        "GET /api/v1/studies/STU-1/workspace/content": () => workspaceFixture(PROJECT).answer(CONTENT_PATH, "GET", null),
        "POST /api/v1/studies/STU-1/design/revisions": () => ({ revision_id: "REV-a1", study_id: "STU-1", revision: 3, content_sha256: "x", parent_revision: 2, source_stage: "run", created_by: "USR-1", created_at: "2026-09-25T08:00:00Z", created: true }),
        "GET /api/v1/studies/STU-1/design/revisions": () => ({ items: [{ revision_id: "REV-old", revision: 2 }] }),
        "GET /api/v1/studies/STU-1/research/readiness": () => READY,
        "GET /api/v1/studies/STU-1/research/runs": () => ({ items: [] }),
        "POST /api/v1/studies/STU-1/research/runs": () => run({ created: true, phase: "QUEUED" }),
        ...overrides,
      };
      const answer = routes[`${method} ${u.split("?")[0]}`]?.(body) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
const called = (method: string, prefix: string) => calls.filter((c) => c.method === method && c.url.startsWith(prefix));

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
  };
  push.mockReset();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test", subject: "s" }));
  window.history.replaceState(null, "", "/");
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  // Every test here also proves the screen reached nothing of the 18.6.6 unit (ADR 0018).
  expect(calls.filter((c) => !c.url.startsWith("/api/v1/") && c.url !== "/config").map((c) => c.url)).toEqual([]);
  sessionStorage.clear();
});

describe("Run", () => {
  it("submits the design the person sees as a revision, shows AIA's checks, and starts one run over it", async () => {
    api();
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByText("Revize návrhu 3")).toBeTruthy();
    const [submitted] = called("POST", "/api/v1/studies/STU-1/design/revisions");
    expect(submitted.body).toMatchObject({ source_stage: "run", content: { title: "Ranní nápoj", n: 450 } });
    expect(Object.keys(submitted.body as object).sort()).toEqual(["content", "source_stage"]); // no client, org or unit id
    expect(called("GET", "/api/v1/studies/STU-1/research/readiness")[0].url).toContain("design_revision_id=REV-a1");
    expect(screen.getByText("n = 450.")).toBeTruthy();
    expect(screen.getByText(/AIA zatím nepoužije filtry/)).toBeTruthy();
    expect(screen.getByText(/Sběr dat pomocí AI respondentů je dostupný jen pro schválené studie/)).toBeTruthy();
    // Studio v3: "Co spustíte" names each step with a way back to it, and a check that does
    // not pass links to the step that fixes it (the audience warning, to Audience).
    expect(screen.getByText("Co spustíte")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Upravit" }).map((a) => a.getAttribute("href"))).toEqual(
      (["brief", "plan", "questionnaire", "audience", "persona"] as const).map((s) => stagePath(s)),
    );
    expect(screen.getByRole("link", { name: "Opravit →" }).getAttribute("href")).toBe(stagePath("audience"));
    expect(screen.getByRole("button", { name: t("research.exec.start") }).getAttribute("data-ai-action")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: t("research.exec.start") }));
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("progress")));
    expect(called("POST", "/api/v1/studies/STU-1/research/runs")[0].body).toEqual({ design_revision_id: "REV-a1" });
  });

  it("saves a change not yet saved before the design becomes a revision", async () => {
    const workspace = workspaceFixture(PROJECT);
    api({ "PUT /api/v1/studies/STU-1/workspace/content": (b) => workspace.answer(CONTENT_PATH, "PUT", b) });
    const at = (step: "brief" | "run") => (
      <ResearchSession studyId="STU-1">
        <ResearchScreen step={step} frame={TEST_FRAME} />
      </ResearchSession>
    );
    const { rerender } = render(at("brief"));
    fireEvent.change(await screen.findByLabelText(t("research.brief.goalLabel")), { target: { value: "Nový cíl" } });
    rerender(at("run")); // before the 1.8 s autosave
    expect(await screen.findByText("Revize návrhu 3")).toBeTruthy();
    const put = calls.findIndex((c) => c.method === "PUT" && c.url === CONTENT_PATH);
    const post = calls.findIndex((c) => c.method === "POST" && c.url === "/api/v1/studies/STU-1/design/revisions");
    expect(put).toBeGreaterThanOrEqual(0);
    expect(put).toBeLessThan(post);
    expect((calls[post].body as { content: { goal: string } }).content.goal).toBe("Nový cíl");
    expect(calls[post].body).toMatchObject({ content: workspace.saves[0].content });
  });

  it("never submits a copy whose save AIA refused because someone saved a newer one", async () => {
    api({
      "PUT /api/v1/studies/STU-1/workspace/content": () =>
        new Response(JSON.stringify({ code: "stale_revision", message: "The working content changed.", details: { current_revision: 4 } }), { status: 409 }),
    });
    const at = (step: "brief" | "run") => (
      <ResearchSession studyId="STU-1">
        <ResearchScreen step={step} frame={TEST_FRAME} />
      </ResearchSession>
    );
    const { rerender } = render(at("brief"));
    fireEvent.change(await screen.findByLabelText(t("research.brief.goalLabel")), { target: { value: "Změna, kterou AIA odmítla" } });
    rerender(at("run"));
    expect(await screen.findByText(t("research.exec.readinessFailed"))).toBeTruthy();
    expect(screen.getAllByText(CONFLICT_MESSAGE).length).toBeGreaterThan(0);
    expect(called("PUT", CONTENT_PATH)).toHaveLength(1);
    expect(called("POST", "/api/v1/studies/STU-1/design/revisions")).toHaveLength(0);
    expect(called("POST", "/api/v1/studies/STU-1/research/runs")).toHaveLength(0);
  });

  it("submits nothing while an earlier save's conflict stands, and prepares the version AIA holds once it is reloaded", async () => {
    let served = workspaceFixture(PROJECT).answer(CONTENT_PATH, "GET", null) as Record<string, unknown>;
    api({
      "GET /api/v1/studies/STU-1/workspace/content": () => served,
      "PUT /api/v1/studies/STU-1/workspace/content": () =>
        new Response(JSON.stringify({ code: "stale_revision", message: "The working content changed.", details: { current_revision: 4 } }), { status: 409 }),
    });
    const at = (step: "brief" | "run") => (
      <ResearchSession studyId="STU-1">
        <ResearchScreen step={step} frame={TEST_FRAME} />
      </ResearchSession>
    );
    const { rerender } = render(at("brief"));
    fireEvent.change(await screen.findByLabelText(t("research.brief.goalLabel")), { target: { value: "Změna, kterou AIA odmítla" } });
    // The debounced save meets the newer revision while the person is still on the brief.
    expect(await screen.findByText(t("research.saveConflict"), {}, { timeout: 4000 })).toBeTruthy();
    rerender(at("run"));
    expect(await screen.findByText(t("research.exec.readinessFailed"))).toBeTruthy();
    expect(screen.getAllByText(CONFLICT_MESSAGE).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: t("research.exec.start") })).toBeNull();
    // The refused copy is not saved again, not made a revision, not run.
    expect(called("PUT", CONTENT_PATH)).toHaveLength(1);
    expect(called("POST", "/api/v1/studies/STU-1/design/revisions")).toHaveLength(0);
    expect(called("POST", "/api/v1/studies/STU-1/research/runs")).toHaveLength(0);

    // What the person can do: load the version AIA holds; Run then prepares that one.
    served = { ...served, revision: 4, revision_id: "REV-4", content: { ...PROJECT, goal: "Cíl, který uložil kolega" } };
    fireEvent.click(screen.getByRole("button", { name: t("research.saveReload") }));
    expect(await screen.findByText("Revize návrhu 3")).toBeTruthy();
    const [submitted] = called("POST", "/api/v1/studies/STU-1/design/revisions");
    expect((submitted.body as { content: { goal: string } }).content.goal).toBe("Cíl, který uložil kolega");
    expect(called("GET", CONTENT_PATH)).toHaveLength(2);
    expect(called("PUT", CONTENT_PATH)).toHaveLength(1);
    expect(called("POST", "/api/v1/studies/STU-1/research/runs")).toHaveLength(0);
  }, 15_000);

  it("submits nothing when the save before it fails, and says why", async () => {
    api({
      "PUT /api/v1/studies/STU-1/workspace/content": () =>
        new Response(JSON.stringify({ code: "internal_error", message: "Obsah se teď nepodařilo uložit.", details: {} }), { status: 500 }),
    });
    const at = (step: "brief" | "run") => (
      <ResearchSession studyId="STU-1">
        <ResearchScreen step={step} frame={TEST_FRAME} />
      </ResearchSession>
    );
    const { rerender } = render(at("brief"));
    fireEvent.change(await screen.findByLabelText(t("research.brief.goalLabel")), { target: { value: "Změna, kterou AIA neuložila" } });
    rerender(at("run")); // before the 1.8 s autosave
    expect(await screen.findByText(t("research.exec.readinessFailed"))).toBeTruthy();
    expect(screen.getAllByText("Obsah se teď nepodařilo uložit.").length).toBeGreaterThan(0);
    expect(screen.getByText(t("research.saveFailed"))).toBeTruthy();
    expect(screen.getByRole("button", { name: t("research.saveRetry") })).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("research.exec.start") })).toBeNull();
    expect(called("PUT", CONTENT_PATH)).toHaveLength(1);
    expect(called("POST", "/api/v1/studies/STU-1/design/revisions")).toHaveLength(0);
    expect(called("POST", "/api/v1/studies/STU-1/research/runs")).toHaveLength(0);
  });

  it("cannot start a design that fails a check", async () => {
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () => ({
        ...READY, ready: false,
        checks: [{ id: "conditional_questions", status: "FAIL", message: "Podmíněné otázky AIA zatím neumí." }],
      }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.notReady"))).toBeTruthy();
    expect((screen.getByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("lets a reader see the latest revision's checks, but not write a revision or start", async () => {
    api();
    render(<ResearchScreen step="run" frame={{ ...TEST_FRAME, canEdit: false }} />);
    expect(await screen.findByText("Revize návrhu 2")).toBeTruthy();
    expect(called("POST", "/api/v1/studies/STU-1/design/revisions")).toHaveLength(0);
    expect(called("GET", "/api/v1/studies/STU-1/research/readiness")[0].url).toContain("design_revision_id=REV-old");
    expect((screen.getByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(t("research.exec.readOnly"))).toBeTruthy();
  });
});

describe("Run: what a run can cost (5b.2)", () => {
  const STUDY = { study_id: "STU-1", name: "Starbucks", budget_usd: 500, spent_usd: 100, remaining_usd: 400, spend_confirm_usd: null };
  const PRICED = { ...READY, cost_ceiling_usd: 225, cost_ceiling_unknown: null, fieldwork_requests: 450, analysis_calls: 0, spend_confirm_usd: null, confirmation_required: false };
  const RUNS = "/api/v1/studies/STU-1/research/runs";

  it("shows the ceiling as an upper bound beside what is left of the budget", async () => {
    api({ "GET /api/v1/research/readiness": () => PRICED, "GET /api/v1/studies/STU-1/research/readiness": () => PRICED, "GET /api/v1/studies/STU-1": () => STUDY });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const cost = await screen.findByRole("region", { name: t("research.exec.cost.title") });
    expect(await within(cost).findByText(/225\.00 USD/)).toBeTruthy();
    expect(within(cost).getByText(/450 dotazů/)).toBeTruthy();
    expect(await within(cost).findByText(/400\.00 USD/)).toBeTruthy();
    expect(within(cost).getByText(t("research.exec.cost.bound"))).toBeTruthy();
  });

  it("says a ceiling it cannot work out is unknown, never zero", async () => {
    const unknown = { ...PRICED, cost_ceiling_usd: null, cost_ceiling_unknown: "fieldwork_reservation_missing" };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => unknown, "GET /api/v1/studies/STU-1": () => STUDY });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const cost = await screen.findByRole("region", { name: t("research.exec.cost.title") });
    expect(await within(cost).findByText(t("research.exec.cost.unknown.fieldwork_reservation_missing"))).toBeTruthy();
    expect(within(cost).queryByText(/Běh může stát nejvýše/)).toBeNull(); // no figure at all, so no zero
  });

  it("asks before starting a run whose ceiling reaches the study's limit, and sends the yes", async () => {
    const asks = { ...PRICED, spend_confirm_usd: 100, confirmation_required: true };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => asks, "GET /api/v1/studies/STU-1": () => ({ ...STUDY, spend_confirm_usd: 100 }) });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.start") }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/225\.00 USD/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: t("dialog.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(called("POST", RUNS)).toHaveLength(0); // no yes, no run

    fireEvent.click(screen.getByRole("button", { name: t("research.exec.start") }));
    fireEvent.click(await screen.findByRole("button", { name: "OK" }));
    await waitFor(() => expect(called("POST", RUNS)).toHaveLength(1));
    expect(called("POST", RUNS)[0].body).toEqual({ design_revision_id: "REV-a1", confirm_cost_usd: 225 });
  });

  it("does not offer to start when a limit is set and the ceiling is unknown, and says why", async () => {
    const blocked = { ...PRICED, cost_ceiling_usd: null, cost_ceiling_unknown: "fieldwork_reservation_missing", spend_confirm_usd: 100 };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => blocked, "GET /api/v1/studies/STU-1": () => STUDY });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const startButton = (await screen.findByRole("button", { name: t("research.exec.start") })) as HTMLButtonElement;
    expect(startButton.disabled).toBe(true);
    expect(screen.getByText(t("research.exec.cost.unknownBlocks"))).toBeTruthy();
  });

  it("sets the study's limit, clears it, and reads the checks again", async () => {
    let limit: number | null = null;
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...PRICED, spend_confirm_usd: limit, confirmation_required: limit !== null && 225 >= limit }),
      "GET /api/v1/studies/STU-1": () => ({ ...STUDY, spend_confirm_usd: limit }),
      "PUT /api/v1/studies/STU-1/spend-confirm": (b) => {
        limit = (b as { limit_usd: number | null }).limit_usd;
        return { ...STUDY, spend_confirm_usd: limit };
      },
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const form = await screen.findByRole("form", { name: t("research.exec.cost.limit") });
    // Studio v3: the limit is a switch with an amount, saved on Enter (or on leaving the field).
    const toggle = within(form).getByRole("switch", { name: t("research.exec.cost.switch") });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(toggle);
    fireEvent.change(within(form).getByLabelText(t("research.exec.cost.limitAmount")), { target: { value: "150" } });
    fireEvent.submit(form);
    await waitFor(() => expect(called("PUT", "/api/v1/studies/STU-1/spend-confirm")).toHaveLength(1));
    expect(called("PUT", "/api/v1/studies/STU-1/spend-confirm")[0].body).toEqual({ limit_usd: 150 });
    // The checks are read again, so the page now says Start will ask.
    expect(await screen.findByText(t("research.exec.cost.willAsk"))).toBeTruthy();
    // Switching it off clears the limit.
    fireEvent.click(within(form).getByRole("switch", { name: t("research.exec.cost.switch") }));
    await waitFor(() => expect(called("PUT", "/api/v1/studies/STU-1/spend-confirm")).toHaveLength(2));
    expect(called("PUT", "/api/v1/studies/STU-1/spend-confirm")[1].body).toEqual({ limit_usd: null });
  });

  it("keeps the switch on and the amount typed when they are set the moment the form appears", async () => {
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => PRICED, "GET /api/v1/studies/STU-1": () => STUDY });
    // A MutationObserver runs in the microtask right after React commits the form, before
    // React's passive effects run (a later task): the window in which a person's first click
    // was once overwritten by the mount's "no limit". The amount is typed in the same window.
    let acted = false;
    const observer = new MutationObserver(() => {
      const toggle = document.querySelector<HTMLElement>(`[role="switch"][aria-checked="false"]`);
      if (acted || !toggle) return;
      acted = true;
      fireEvent.click(toggle);
      const amount = screen.queryByLabelText(t("research.exec.cost.limitAmount"));
      if (amount) fireEvent.change(amount, { target: { value: "150" } });
    });
    observer.observe(document.body, { childList: true, subtree: true });
    onTestFinished(() => observer.disconnect());
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    await waitFor(() => expect(acted).toBe(true));
    const form = await screen.findByRole("form", { name: t("research.exec.cost.limit") });
    await screen.findByText(/Z rozpočtu studie zbývá/); // the study's budget arrived: the card's effects have run
    expect(within(form).getByRole("switch", { name: t("research.exec.cost.switch") }).getAttribute("aria-checked")).toBe("true");
    expect((within(form).getByLabelText(t("research.exec.cost.limitAmount")) as HTMLInputElement).value).toBe("150");
  });

  it("offers no limit control to a reader", async () => {
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => PRICED, "GET /api/v1/studies/STU-1": () => STUDY });
    render(<ResearchScreen step="run" frame={{ ...TEST_FRAME, canEdit: false }} />);
    await screen.findByRole("region", { name: t("research.exec.cost.title") });
    expect(screen.queryByRole("form", { name: t("research.exec.cost.limit") })).toBeNull();
  });

  it("asks again when a retry reaches the limit, and retries with the yes", async () => {
    const cancelled = { ...PARKED, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true };
    let asked = 0;
    api({
      ...listed(cancelled),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/retry": (b) => {
        if (!(b as { confirm_cost_usd?: number } | null)?.confirm_cost_usd) {
          asked += 1;
          return new Response(JSON.stringify({ code: "cost_confirmation_required", message: "confirm", details: { ceiling_usd: 225, limit_usd: 100 } }), { status: 409 });
        }
        return run({ run_id: "RUN-2", retry_of: "RUN-1", phase: "QUEUED" });
      },
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.retry") }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/225\.00 USD/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "OK" }));
    expect(await screen.findByText("Opakování běhu RUN-1")).toBeTruthy();
    expect(asked).toBe(1);
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/retry").map((c) => c.body)).toEqual([null, { confirm_cost_usd: 225 }]);
  });
});

describe("Progress", () => {
  it("explains a run waiting for the AI runtime, step by step, without offering a retry", async () => {
    api(listed(PARKED));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect(await screen.findByText(/Běh čeká u sběru dat: AI respondenti pro tuto studii nejsou dostupní nebo povolení/)).toBeTruthy();
    const steps = within(screen.getByRole("list", { name: t("aia.stages.progress") })).getAllByRole("listitem");
    expect(steps.map((li) => li.textContent)).toEqual([
      expect.stringContaining("Sestavení dotazníku z návrhu"),
      expect.stringContaining("Kontrola připravenosti"),
      expect.stringContaining("Sběr dat"),
      expect.stringContaining("Agregace"),
      expect.stringContaining("Sociomapa (interní)"),
    ]);
    expect(within(steps[3]).getByText("Čeká na předchozí krok")).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("research.exec.retry") })).toBeNull();
    expect(screen.queryByRole("note")).toBeNull(); // not fictional: no fiction banner
  });

  it("shows the gate that parked fieldwork, so the banner's advice to check the step can be followed", async () => {
    const message = "AI respondenti nejsou pro tento výzkum povoleni: licence_undetermined. Běh čeká u sběru dat.";
    api(listed(parkedWith([
      step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
      step("preflight", "SUCCEEDED", { artifact_id: "ART-2" }),
      step("run", "WAITING_PROVIDER", { waiting_reason: "ai_runtime_unavailable", failure_class: "RUNTIME_UNAVAILABLE", error_message: message }),
      step("aggregate", "BLOCKED", { attempts_recorded: 0, started_at: null }),
      step("sociomap", "BLOCKED", { attempts_recorded: 0, started_at: null }),
    ])));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect(await screen.findByText(/Běh čeká u sběru dat: AI respondenti/)).toBeTruthy();
    const steps = within(screen.getByRole("list", { name: t("aia.stages.progress") })).getAllByRole("listitem");
    expect(within(steps[2]).getByText(message)).toBeTruthy();
    expect(within(steps[0]).queryByText(message)).toBeNull();
  });

  it("names an analysis module as the parked step, not data collection", async () => {
    const message = "AI model není pro tento výzkum povolen: egress_no_approved_route.";
    api(listed(parkedWith([
      step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
      step("preflight", "SUCCEEDED", { artifact_id: "ART-2" }),
      step("run", "SUCCEEDED", { artifact_id: "ART-3", data_origin: "SYNTHETIC_AI_FICTIONAL" }),
      step("aggregate", "SUCCEEDED", { artifact_id: "ART-4" }),
      step("analysis_executive", "WAITING_PROVIDER", {
        kind: "research_analysis", waiting_reason: "ai_runtime_unavailable", failure_class: "RUNTIME_UNAVAILABLE", error_message: message,
      }),
    ])));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect(await screen.findByText(/Běh čeká u kroku „Shrnutí analýzy“/)).toBeTruthy();
    expect(screen.queryByText(/Běh čeká u sběru dat/)).toBeNull();
    expect(screen.getByText(message)).toBeTruthy();
  });

  it("says why a step waits for budget, provider quota or a decision when it recorded no message", async () => {
    for (const [reason, status, words] of [
      ["budget_exceeded", "AWAITING_BUDGET", /překročil rozpočet studie/],
      ["provider_quota_exhausted", "WAITING_PROVIDER", /vyčerpal kvótu/],
      ["gate:design", "AWAITING_GATE", /rozhodnutí člověka/],
    ] as const) {
      api(listed(parkedWith([step("run", status, { waiting_reason: reason })])));
      const { unmount } = render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
      expect(await screen.findByText(words)).toBeTruthy();
      expect(screen.queryByText(/Běh čeká u sběru dat/)).toBeNull(); // not a runtime park
      unmount();
    }
  });

  describe("a step waiting for budget", () => {
    const STUDY = { study_id: "STU-1", name: "Starbucks", budget_usd: 10, spent_usd: 9.5, remaining_usd: 0.5 };
    const BUDGET_PATH = "/api/v1/studies/STU-1/research/runs/RUN-1/steps/analysis_executive/budget";
    const waiting = () => parkedWith([
      step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
      step("analysis_executive", "AWAITING_BUDGET", { kind: "research_analysis", waiting_reason: "budget_exceeded" }),
    ]);

    it("offers to raise the budget, showing what is spent, and posts the new total for that step", async () => {
      const resumed = run({ steps: [step("compile", "SUCCEEDED"), step("analysis_executive", "RUNNABLE")] });
      api({
        ...listed(waiting()),
        "GET /api/v1/studies/STU-1": () => STUDY,
        [`POST ${BUDGET_PATH}`]: () => resumed,
      });
      render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
      const form = await screen.findByRole("form", { name: t("research.exec.budget.title") });
      expect(await within(form).findByText(/10\.00/)).toBeTruthy();
      const amount = within(form).getByLabelText(t("research.exec.budget.amount")) as HTMLInputElement;
      expect(amount.value).toBe("10");
      fireEvent.change(amount, { target: { value: "15" } });
      fireEvent.change(within(form).getByLabelText(t("research.exec.budget.note")), { target: { value: "Schváleno" } });
      fireEvent.click(within(form).getByRole("button", { name: t("research.exec.budget.lift") }));
      await waitFor(() => expect(called("POST", BUDGET_PATH)).toHaveLength(1));
      expect(called("POST", BUDGET_PATH)[0].body).toEqual({ budget_usd: 15, note: "Schváleno" });
      await waitFor(() => expect(screen.queryByRole("form", { name: t("research.exec.budget.title") })).toBeNull());
    });

    it("will not offer a total below the current budget", async () => {
      api({ ...listed(waiting()), "GET /api/v1/studies/STU-1": () => STUDY });
      render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
      const form = await screen.findByRole("form", { name: t("research.exec.budget.title") });
      await within(form).findByText(/10\.00/);
      fireEvent.change(within(form).getByLabelText(t("research.exec.budget.amount")), { target: { value: "4" } });
      expect((within(form).getByRole("button", { name: t("research.exec.budget.lift") }) as HTMLButtonElement).disabled).toBe(true);
      expect(called("POST", BUDGET_PATH)).toHaveLength(0);
    });

    it("says what the API refused instead of pretending the step went on", async () => {
      api({
        ...listed(waiting()),
        "GET /api/v1/studies/STU-1": () => STUDY,
        [`POST ${BUDGET_PATH}`]: () => new Response(JSON.stringify({ code: "not_waiting_for_budget", message: "Krok už na rozpočet nečeká." }), { status: 409 }),
      });
      render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
      const form = await screen.findByRole("form", { name: t("research.exec.budget.title") });
      await within(form).findByText(/10\.00/);
      fireEvent.click(within(form).getByRole("button", { name: t("research.exec.budget.lift") }));
      expect(await screen.findByText(/Krok už na rozpočet nečeká/)).toBeTruthy();
      expect(screen.getByRole("form", { name: t("research.exec.budget.title") })).toBeTruthy();
    });

    it("offers nothing to a reader, and nothing for a step waiting for something else", async () => {
      api({ ...listed(waiting()), "GET /api/v1/studies/STU-1": () => STUDY });
      const { unmount } = render(<ResearchScreen step="progress" frame={{ ...TEST_FRAME, canEdit: false }} />);
      await screen.findByText(/překročil rozpočet studie/);
      expect(screen.queryByRole("form", { name: t("research.exec.budget.title") })).toBeNull();
      unmount();
      api({ ...listed(parkedWith([step("run", "WAITING_PROVIDER", { waiting_reason: "provider_quota_exhausted" })])) });
      render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
      await screen.findByText(/vyčerpal kvótu/);
      expect(screen.queryByRole("form", { name: t("research.exec.budget.title") })).toBeNull();
    });
  });

  it("cancels only after the person confirms, and retries a failed run as a new run", async () => {
    api({
      ...listed(PARKED),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/cancel": () => ({ ...PARKED, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true }),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/retry": () => run({ run_id: "RUN-2", retry_of: "RUN-1", phase: "QUEUED" }),
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.cancel") }));
    fireEvent.click(await screen.findByRole("button", { name: "OK" }));
    expect(await screen.findByText("Zrušeno")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t("research.exec.retry") }));
    expect(await screen.findByText("Opakování běhu RUN-1")).toBeTruthy();
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/retry")).toHaveLength(1);
  });
});

describe("Results", () => {
  it("shows evidence-checked internal analysis while another module waits", async () => {
    const partial = run({
      status: "WAITING_PROVIDER", phase: "WAITING", fieldwork_source: "synthetic_fixture",
      steps: [
        step("aggregate", "SUCCEEDED", { artifact_id: "ART-4", data_origin: "SYNTHETIC_FIXTURE" }),
        step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-6" }),
        step("analysis_limitations", "WAITING_PROVIDER", { kind: "research_analysis" }),
      ],
    });
    api({
      ...listed(partial),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({
        run_id: "RUN-1", complete: false, internal_only: true, synthetic: true,
        pending: { limitations: "WAITING_PROVIDER" },
        modules: { executive: { outcome: "COMPLETED", artifact_id: "ART-6",
          summary: "Ověřené shrnutí.", research_question_answers: [], key_findings: [],
          claims: [{ claim_id: "C1", evidence_ref: "q1.mean", value: 3, indicative: false, data_origin: "SYNTHETIC_FIXTURE" }],
          violations: [] } },
      }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByText("Ověřené shrnutí.")).toBeTruthy();
    expect(screen.getByText(/C1 → q1.mean/)).toBeTruthy();
    expect(screen.getByText(/Interní analýza fiktivních respondentů/)).toBeTruthy();
    expect(screen.getByText(/Čeká: WAITING_PROVIDER/)).toBeTruthy();
  });

  it("shows a fictional run's aggregates labelled as fiction, hides a suppressed cell, keeps the Sociomap internal", async () => {
    api({
      ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByText(/Fiktivní data\. Tento běh používá smyšlené respondenty/)).toBeTruthy();
    const q2 = await screen.findByRole("region", { name: "q2" });
    expect(within(q2).getByText("34,8 %")).toBeTruthy();
    expect(within(q2).getByText("30,1–39,9")).toBeTruthy();
    const t1 = screen.getByRole("region", { name: "t1" });
    expect(within(t1).getByText(/Potlačeno: jen 19 unikátních dárců/)).toBeTruthy();
    expect(within(t1).queryByText("3,73")).toBeNull();
    expect(within(t1).queryByText(/3,25/)).toBeNull();
    expect(await screen.findByText(/Interní: metodika Sociomapy \(PROGRESS D6\) zatím není schválená/)).toBeTruthy();
    // What 18.6.6's map tool did and AIA does not is said where the map is.
    expect(screen.getByText(t("research.exec.results.mapToolNotInAia"))).toBeTruthy();
    const map = screen.getByRole("region", { name: "Nápoje" });
    expect(within(map).getByText("Káva")).toBeTruthy();
    expect(within(map).getByText("6,14")).toBeTruthy();
    expect(screen.getAllByText(/Artefakt ART-4/).length).toBe(1);
    // No hand-off to 18.6.6: the report AIA does not have yet is said, not linked (ADR 0018).
    expect(screen.queryByRole("link", { name: /18\.6\.6/ })).toBeNull();
    expect(screen.getByText(t("research.exec.results.reportNotInAia"))).toBeTruthy();
  });

  it("says there are no results while the run waits at fieldwork", async () => {
    api(listed(PARKED));
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.noResultsParked"))).toBeTruthy();
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/artifacts")).toHaveLength(0);
  });

  it("shows the internal draft from the completed report step and downloads it with authentication", async () => {
    const reportRun = run({
      ...COMPLETED,
      steps: [...COMPLETED.steps, step("report", "SUCCEEDED", {
        kind: "research_report", stage_type: "REPORT", artifact_id: "ART-report",
      })],
    });
    const documentBytes = new Blob(["docx bytes"], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
    const createObjectURL = vi.fn(() => "blob:report");
    const revokeObjectURL = vi.fn();
    const real = { create: URL.createObjectURL, revoke: URL.revokeObjectURL, click: HTMLAnchorElement.prototype.click };
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;
    const click = vi.fn();
    HTMLAnchorElement.prototype.click = click;
    onTestFinished(() => {
      URL.createObjectURL = real.create;
      URL.revokeObjectURL = real.revoke;
      HTMLAnchorElement.prototype.click = real.click;
    });
    api({
      ...listed(reportRun),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => ({
        run_id: "RUN-1", state: "READY", internal_only: true, review_state: "DRAFT_UNAPPROVED",
        artifact_id: "ART-report", sha256: "abcdef0123456789", size_bytes: 10, synthetic: true,
      }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/download": () =>
        new Response(documentBytes, { status: 200 }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.results.reportDraft"))).toBeTruthy();
    expect(screen.getByText(t("research.exec.results.reportSynthetic"))).toBeTruthy();
    expect(screen.getByText(/Artefakt ART-report/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t("research.exec.results.reportDownload") }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
    expect(click).toHaveBeenCalledOnce();
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/download")).toHaveLength(1);
  });

  it("explains why a report could not be made when analysis was refused", async () => {
    const reportRun = run({
      ...COMPLETED,
      status: "FAILED", phase: "FAILED",
      steps: [...COMPLETED.steps, step("report", "FAILED", { kind: "research_report", stage_type: "REPORT" })],
    });
    api({
      ...listed(reportRun),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => ({
        run_id: "RUN-1", state: "FAILED", internal_only: true, reason: "report_inputs_refused",
      }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.results.reportInputsRefused"))).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("research.exec.results.reportDownload") })).toBeNull();
  });

  it("leaves the Sociomap out for a person the API refuses it to", async () => {
    api({
      ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () =>
        new Response('{"code":"insufficient_role","message":"Not permitted."}', { status: 403 }),
    });
    render(<ResearchScreen step="results" frame={{ ...TEST_FRAME, canEdit: false }} />);
    expect(await screen.findByRole("region", { name: "q2" })).toBeTruthy();
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5")).toHaveLength(1));
    expect(screen.queryByText(/Interní: metodika Sociomapy/)).toBeNull();
  });
});
