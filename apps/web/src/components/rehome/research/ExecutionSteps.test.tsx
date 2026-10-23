// @vitest-environment jsdom
// Run, Progress and Results (ADR 0016) against a fake AIA API. What they must do:
// submit the design the person sees as a Design Revision, say what AIA's checks
// say, start one run over that revision, explain a run waiting for the AI
// runtime, hide a suppressed cell's numbers, label fictional data every time, and
// keep the internal Sociomap internal.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { t, tv } from "@/i18n/t";
import { runState } from "@/lib/run-state";
import type { ResearchRun } from "@/lib/api";
import signedOffFixture from "@/lib/fixtures/object-map-signed-off.json";
import sociomappingFixture from "@/lib/fixtures/sociomapping.json";
import { AnalysisInspect } from "./AnalysisInspect";
import { ItemInspectorContext } from "@/components/workbench/item-inspector-context";
import { measureAnchor } from "@/lib/result-reading";
import { parseAiaId } from "@/lib/workbench-artifacts";
import { CONFLICT_MESSAGE } from "@/research/store";
import { RunResults, fixStep } from "./ExecutionSteps";
import { REPORT_APPROVED, type ReportApproved } from "./ReportDocumentView";
import { StudyFrameProvider } from "./frame";
import { ResearchScreen, ResearchSession } from "./ResearchScreen";
import { CONTENT_PATH, workspaceFixture } from "./test-workspace";
import { TEST_FRAME, stagePath } from "./test-frame";

// The workbench's layout, where a test asks for it: the Lead owns the AI starts there, and the
// Sociomapa stage is the map (artifact-sociomap SOC9). Null: the layout's own answer.
const layout = vi.hoisted(() => ({ workbench: null as boolean | null }));
vi.mock("./AskLead", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./AskLead")>();
  return { ...actual, useLeadOwnsAiStarts: () => layout.workbench ?? actual.useLeadOwnsAiStarts() };
});

/** Approval asks first, naming the version (input-interactions B22); answer yes. */
async function confirmApproval(version?: string): Promise<void> {
  const dialog = await screen.findByRole("dialog");
  if (version) expect(dialog.textContent).toContain(`uloženou verzi ${version} (`);
  fireEvent.click(within(dialog).getByRole("button", { name: t("research.exec.report.approveAsk.yes") }));
}

/** An approval made in the document pane's doc bar (RPT3a), as the pane announces it. */
function approvedInPane(d: Partial<ReportApproved> & Pick<ReportApproved, "kind" | "artifactId">): void {
  const detail: ReportApproved = { runId: "RUN-1", reviewState: "APPROVED_INTERNAL", approvedOn: null, stamped: null, ...d };
  window.dispatchEvent(new CustomEvent(REPORT_APPROVED, { detail }));
}

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
  question_outlook: [] as unknown[],
};
const step = (node: string, status: string, extra: Record<string, unknown> = {}) => ({
  step_id: `STEP-${node}`, node_key: node, kind: `research_${node}`, stage_type: "BRIEF", status, waiting_reason: null, attempts_recorded: 1, max_attempts: 3,
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
// What the API gives: the Study's list carries each run's steps without their attempt history
// (no start time, no error); the run itself is read in full.
const listed = (...runs: ReturnType<typeof run>[]) => {
  const routes: Record<string, () => unknown> = {
    "GET /api/v1/studies/STU-1/research/runs": () => ({
      items: runs.map((r) => ({ ...r, steps: (r.steps as ReturnType<typeof step>[]).map((s) => ({ ...s, started_at: null, error_message: null })), actual_cost_usd: null })),
    }),
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
        // PROJECT is not what defaultsMerge makes of it: the stage saves its completed copy
        // before submitting it as a design (ADR 0026 decision 5), as AIA stores it.
        "PUT /api/v1/studies/STU-1/workspace/content": () => ({ study_id: "STU-1", state: "NATIVE", revision: 4, revision_id: "REV-4", deduplicated: false }),
        "POST /api/v1/studies/STU-1/design/revisions": () => ({ revision_id: "REV-a1", study_id: "STU-1", revision: 3, content_sha256: "x", parent_revision: 2, source_stage: "run", created_by: "USR-1", created_at: "2026-09-25T08:00:00Z", created: true }),
        "GET /api/v1/studies/STU-1/design/revisions": () => ({ items: [{ revision_id: "REV-old", revision: 2 }] }),
        "GET /api/v1/studies/STU-1/research/readiness": () => READY,
        "GET /api/v1/studies/STU-1/research/runs": () => ({ items: [] }),
        "GET /api/v1/studies/STU-1/deep-research/runs": () => [],
        "POST /api/v1/studies/STU-1/research/runs": () => run({ created: true, phase: "QUEUED" }),
        ...overrides,
      };
      // A route may answer later (a promise), to hold a read while the test looks at the screen.
      const answer = (await routes[`${method} ${u.split("?")[0]}`]?.(body)) ?? {};
      return answer instanceof Response ? answer : new Response(JSON.stringify(answer), { status: 200 });
    }),
  );
}
/** A measure's card on Data, by its anchor: a question without stored wording has no id in its name. */
const findMeasure = (id: string) => waitFor(() => {
  const card = document.getElementById(measureAnchor(id));
  if (!card) throw new Error(`no measure ${id}`);
  return card;
});
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

describe("fixStep", () => {
  it("sends each readiness check to the stage where it is fixed", () => {
    // The ids the domain's readiness emits (research_design.assess_readiness, support_forecast,
    // research_trace), a prefixed one standing for its kind; n and its support live on Dimenze,
    // the audience on its own stage.
    const where = {
      sample_size: "persona", support_forecast: "persona", sociomap_support: "persona", dimensions: "persona",
      audience: "audience",
      questionnaire: "questionnaire", conditional_questions: "questionnaire", battery_familiarity: "questionnaire",
      sociomap_input: "questionnaire", research_question_coverage: "questionnaire", "compile:invalid_scale:q1": "questionnaire", "battery_size:b1": "questionnaire",
    };
    for (const [id, step] of Object.entries(where)) expect([id, fixStep(id)]).toEqual([id, step]);
    // An id that names an Object.prototype member is an unknown check, never a function.
    expect(fixStep("constructor")).toBe("questionnaire");
  });
});

describe("Run", () => {
  it("names each check's status in words, and gives a status it does not know no good tone (6b)", async () => {
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...READY, checks: [...READY.checks, { id: "novel", status: "SOMETHING_NEW", message: "Nová kontrola." }] }) });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const novel = (await screen.findByText("Nová kontrola.")).closest("li") as HTMLElement;
    expect(within(novel).getByText("AIA k tomuto záznamu zatím nemá popis.").closest("[data-tone]")?.getAttribute("data-tone")).toBe("neutral");
    // The status it does not know stays visible beside the words, never dropped.
    expect(within(novel).getByText("SOMETHING_NEW").tagName).toBe("CODE");
    expect(screen.getAllByText("Upozornění").length).toBeGreaterThan(0);
    expect(screen.queryByText("WARN")).toBeNull();
    expect(screen.queryByText("PASS")).toBeNull();
  });

  it("lists each earlier run in the state every screen reads, and opens results only once they are ready (6a)", async () => {
    const analysis = (outcome: string) => step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", analysis_outcome: outcome });
    const blocked = run({ ...COMPLETED, run_id: "RUN-2", steps: [...COMPLETED.steps, analysis("BLOCKED")] });
    const ready = run({ ...COMPLETED, run_id: "RUN-1", steps: [...COMPLETED.steps, analysis("COMPLETED")] });
    api(listed(blocked, ready));
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByText("Potřebuje opravu")).toBeTruthy();
    expect(screen.getByText("Výsledky jsou hotové")).toBeTruthy();
    expect(screen.queryByText("Dokončeno")).toBeNull();
    const links = screen.getAllByRole("link", { name: /Zobrazit (průběh|výsledky)/ }).map((a) => [a.textContent, a.getAttribute("href")?.split("?run=")[1]]);
    expect(links).toEqual([["Zobrazit průběh", "RUN-2"], ["Zobrazit výsledky", "RUN-1"]]);
  });

  it("submits the design the person sees as a revision, shows AIA's checks, and starts one run over it", async () => {
    api();
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByText("Revize návrhu 3")).toBeTruthy();
    const [submitted] = called("POST", "/api/v1/studies/STU-1/design/revisions");
    expect(submitted.body).toMatchObject({ source_stage: "run", content: { title: "Ranní nápoj", n: 450 } });
    // No client, org or unit id; the working revision the design is (ADR 0026), and nothing else.
    expect(Object.keys(submitted.body as object).sort()).toEqual(["content", "source_stage", "workspace_revision"]);
    expect((submitted.body as { workspace_revision: unknown }).workspace_revision).toEqual(expect.any(Number));
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

  it("lets the person choose who answers, reads the checks again under it, and starts with it (run-recovery-and-truth 5a)", async () => {
    const READINESS = "/api/v1/studies/STU-1/research/readiness";
    const sources = [
      { source: "fictional_roster", offered: true, reason: null, default: true },
      { source: "panel", offered: true, reason: null, default: false },
    ];
    api({
      [`GET ${READINESS}`]: () => {
        const asked = new URL(called("GET", READINESS).at(-1)!.url, "http://x").searchParams.get("persona_source");
        const source = asked ?? "fictional_roster";
        const audience = source === "panel" ? { id: "audience", status: "PASS", message: "Filtry se uplatní při výběru respondentů z populace." } : READY.checks[1];
        return { ...READY, checks: [READY.checks[0], audience], persona_source: source, persona_sources: sources };
      },
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const card = (await screen.findByRole("heading", { name: t("research.exec.respondents.title") })).closest("section") as HTMLElement;
    const roster = within(card).getByRole("radio", { name: new RegExp(t("research.exec.respondents.fictional_roster")) }) as HTMLInputElement;
    const panel = within(card).getByRole("radio", { name: new RegExp(t("research.exec.respondents.panel")) }) as HTMLInputElement;
    expect(roster.checked).toBe(true);
    fireEvent.click(panel);
    // While the checks are read again under the new choice, Start cannot send the old one
    // (review, Codex on #439).
    expect((screen.getByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement).disabled).toBe(true);
    await screen.findByText("Filtry se uplatní při výběru respondentů z populace.");
    await waitFor(() => expect((screen.getByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement).disabled).toBe(false));
    expect(called("GET", READINESS).at(-1)!.url).toContain("persona_source=panel");
    expect((within(card).getByRole("radio", { name: new RegExp(t("research.exec.respondents.panel")) }) as HTMLInputElement).checked).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: t("research.exec.start") }));
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("progress")));
    expect(called("POST", "/api/v1/studies/STU-1/research/runs")[0].body).toEqual({ design_revision_id: "REV-a1", persona_source: "panel" });
  });

  it("shows a source the deployment does not offer, with its reason, and never selectable", async () => {
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () => ({
        ...READY,
        persona_source: "fictional_roster",
        persona_sources: [
          { source: "fictional_roster", offered: true, reason: null, default: true },
          { source: "panel", offered: false, reason: "panel_personas_disabled", default: false },
        ],
      }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const card = (await screen.findByRole("heading", { name: t("research.exec.respondents.title") })).closest("section") as HTMLElement;
    expect((within(card).getByRole("radio", { name: new RegExp(t("research.exec.respondents.panel")) }) as HTMLInputElement).disabled).toBe(true);
    expect(within(card).getByText(t("research.exec.respondents.reason.panel_personas_disabled"))).toBeTruthy();
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
    let refuse = true;
    api({
      "GET /api/v1/studies/STU-1/workspace/content": () => served,
      "PUT /api/v1/studies/STU-1/workspace/content": () => refuse
        ? new Response(JSON.stringify({ code: "stale_revision", message: "The working content changed.", details: { current_revision: 4 } }), { status: 409 })
        : { study_id: "STU-1", state: "NATIVE", revision: 5, revision_id: "REV-5", deduplicated: false },
    });
    const at = (step: "brief" | "run") => (
      <ResearchSession studyId="STU-1">
        <ResearchScreen step={step} frame={TEST_FRAME} />
      </ResearchSession>
    );
    const { rerender } = render(at("brief"));
    fireEvent.change(await screen.findByLabelText(t("research.brief.goalLabel")), { target: { value: "Změna, kterou AIA odmítla" } });
    // The debounced save meets the newer revision while the person is still on the brief.
    expect(await screen.findByText(t("research.saveConflict"))).toBeTruthy();
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
    refuse = false;
    fireEvent.click(screen.getByRole("button", { name: t("research.saveReload") }));
    expect(await screen.findByText("Revize návrhu 3")).toBeTruthy();
    const [submitted] = called("POST", "/api/v1/studies/STU-1/design/revisions");
    expect((submitted.body as { content: { goal: string } }).content.goal).toBe("Cíl, který uložil kolega");
    expect(called("GET", CONTENT_PATH)).toHaveLength(2);
    // The refused save, then the reloaded copy saved as the template completed it, from
    // revision 4, so the design names a stored revision (ADR 0026 decision 5).
    const puts = called("PUT", CONTENT_PATH);
    expect(puts).toHaveLength(2);
    expect((puts[1].body as { base_revision: number }).base_revision).toBe(4);
    expect((submitted.body as { workspace_revision: number }).workspace_revision).toBe(5);
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

describe("Run: which questions the run will answer (run-recovery-and-truth 2b)", () => {
  const item = (id: string, text: string, verdict: string, reasons: string[]) => ({ question_id: id, text, section_id: "s1", battery_id: null, verdict, reasons });
  const OUTLOOK = {
    ...READY,
    question_outlook: [
      item("q1", "Jak často pijete kávu?", "ANSWERABLE", []),
      item("q2", "Kolik Kč byste maximálně zaplatili?", "UNANSWERABLE", ["fidelity_refused"]),
      item("q3", "Co vás ráno probudí?", "AT_RISK", ["open_ended"]),
    ],
  };

  it("lists what the run will not answer first, by its wording, with the reason and where to fix it", async () => {
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => OUTLOOK });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const card = await screen.findByRole("region", { name: t("research.exec.outlook.title") });
    expect(within(card).getByText("1 bez odpovědi · 1 s rizikem · 0 neznámo · 1 zodpoví")).toBeTruthy();
    const flagged = within(card).getByRole("list", { name: t("research.exec.outlook.title") });
    const rows = within(flagged).getAllByRole("listitem").filter((li) => li.parentElement === flagged);
    expect(rows.map((r) => r.querySelector("p")?.textContent)).toEqual(["Kolik Kč byste maximálně zaplatili?", "Co vás ráno probudí?"]);
    expect(within(rows[0]).getByText(t("research.exec.outlook.reason.fidelity_refused"))).toBeTruthy();
    expect(within(rows[0]).getByRole("link", { name: t("research.exec.fix") })).toBeTruthy();
    // What it will answer is there, folded away.
    expect(within(card).getByText(tv("research.exec.outlook.answerable", { count: 1 }))).toBeTruthy();
  });

  it("traces each research question to its measures, and says when nothing measures one", async () => {
    const traced = {
      ...OUTLOOK,
      research_trace: {
        linked: true,
        dangling: [{ question_id: "q1", research_question: "Stará otázka?" }],
        questions: [
          { text: "Jak často lidé pijí kávu?", measures: ["q1"], verdict: "ANSWERABLE", reasons: [] },
          { text: "Co lidé snídají?", measures: [], verdict: "UNANSWERABLE", reasons: ["unmeasured"] },
          { text: "Liší se segmenty?", measures: ["q1"], verdict: "UNANSWERABLE", reasons: ["segments_unavailable"], comparison: "compare_segments" },
        ],
      },
    };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => traced });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const card = await screen.findByRole("region", { name: t("research.exec.trace.title") });
    const rows = within(card).getAllByRole("listitem").filter((li) => li.parentElement?.tagName === "OL");
    expect(within(rows[0]).getByText("Jak často pijete kávu?")).toBeTruthy(); // its measure, by its wording
    expect(within(rows[0]).queryByRole("link")).toBeNull();
    expect(within(rows[1]).getByText(t("research.exec.trace.reason.unmeasured"))).toBeTruthy();
    expect(within(rows[1]).getByRole("link", { name: t("research.exec.fix") })).toBeTruthy();
    expect(within(card).getByText(/Stará otázka\?/)).toBeTruthy();
    // The comparison the plan declares, and why the run cannot carry it.
    expect(within(rows[2]).getByText(tv("research.exec.trace.comparison", { kind: t("research.questionnaire.comparisons.kind.compare_segments") }))).toBeTruthy();
    expect(within(rows[2]).getByText(t("research.exec.trace.reason.segments_unavailable"))).toBeTruthy();
  });

  it("sends each gap to where it is fixed, and the trace card sends its research question to the same place", async () => {
    // research-integrity-report 14 (D1): one link to Dotazník's root for every gap did not say where.
    const gaps = {
      rules: "aia-answerability-1", capable: false, digest: "e".repeat(64), acknowledgement_required: false,
      gaps: [
        { kind: "not_answerable", research_question: "Co lidé snídají?", verdict: "UNANSWERABLE", reasons: ["unmeasured"], measures: [] },
        { kind: "not_answerable", research_question: "Liší se segmenty?", verdict: "UNANSWERABLE", reasons: ["segments_unavailable"], measures: ["q1"] },
        { kind: "not_answerable", research_question: "Kolik by zaplatili?", verdict: "UNANSWERABLE", reasons: ["measures_unanswerable"], measures: ["q2"] },
      ],
    };
    const traced = {
      ...OUTLOOK,
      answerability: gaps,
      research_trace: {
        linked: true,
        dangling: [],
        questions: [
          { text: "Jak často lidé pijí kávu?", measures: ["q1"], verdict: "ANSWERABLE", reasons: [] },
          { text: "Co lidé snídají?", measures: [], verdict: "UNANSWERABLE", reasons: ["unmeasured"] },
          { text: "Liší se segmenty?", measures: ["q1"], verdict: "UNANSWERABLE", reasons: ["segments_unavailable"], comparison: "compare_segments" },
          { text: "Kolik by zaplatili?", measures: ["q2"], verdict: "UNANSWERABLE", reasons: [] },
        ],
      },
    };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => traced });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    const gapRows = within(gate).getAllByRole("listitem");
    const places = gapRows.map((li) => within(li).getAllByRole("link").map((a) => a.getAttribute("href")));
    const questionnaire = stagePath("questionnaire");
    expect(places).toEqual([[`${questionnaire}#q-editor`], [`${questionnaire}#q-comparisons`], [`${questionnaire}#qedit_q2`]]);
    expect(within(gapRows[0]).getByRole("link").textContent).toBe(t("research.exec.answerability.fixTo.links"));
    // Dotazník itself stays below the gaps.
    expect(within(gate).getByRole("link", { name: t("research.exec.answerability.fix") }).getAttribute("href")).toBe(questionnaire);
    const card = screen.getByRole("region", { name: t("research.exec.trace.title") });
    const traceRows = within(card).getAllByRole("listitem").filter((li) => li.parentElement?.tagName === "OL");
    const fixes = traceRows.slice(1).map((li) => within(li).getByRole("link", { name: t("research.exec.fix") }).getAttribute("href"));
    expect(fixes).toEqual(places.map((p) => p[0]));
  });

  it("offers no linking in Dotazník for a design that states no research question", async () => {
    // Review web#12: under "the design states no research question" the gate still offered to link
    // items to research questions, where there is none to link to; Návrh is where it is fixed.
    const none = {
      rules: "aia-answerability-1", capable: false, digest: "d".repeat(64), acknowledgement_required: false,
      gaps: [{ kind: "no_research_questions", research_question: null, verdict: "UNANSWERABLE", reasons: [], measures: [] }],
    };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...OUTLOOK, answerability: none }) });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    expect(within(gate).getAllByRole("link").map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      [t("research.exec.answerability.fixTo.plan"), `${stagePath("plan")}#plan-understanding`],
    ]);
  });

  it("shows what Design Research found per research question, a gap, and every rejection's reason", async () => {
    const traced = {
      ...OUTLOOK,
      research_trace: {
        linked: true,
        dangling: [],
        questions: [
          { text: "Jak často lidé pijí kávu?", measures: ["q1"], verdict: "ANSWERABLE", reasons: [] },
          { text: "Co lidé snídají?", measures: ["q1"], verdict: "ANSWERABLE", reasons: [] },
          { text: "Nová otázka?", measures: ["q1"], verdict: "ANSWERABLE", reasons: [] },
        ],
      },
    };
    const DR = "/api/v1/studies/STU-1/deep-research/runs";
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () => traced,
      [`GET ${DR}`]: () => [{ run_id: "DR-1", purpose: "DESIGN_RESEARCH", phase: "COMPLETED", steps: [] }],
      [`GET ${DR}/DR-1/design-proposal`]: () => ({
        run_id: "DR-1", admissible: true, refusal: null,
        items: [
          { item_id: "DRP-1", kind: "EVIDENCE", subject_key: "q-aaaaaaaaaaaa", subject_kind: "QUESTION", subject_text: "Jak často lidé pijí kávu?", subject_origin: "o", findings: [{ evidence_id: "EV-1", claim: "Kávu pije denně většina dospělých.", quote: "denně pije kávu 6 z 10", source_title: "Fiktivní zdroj", source: "https://example.org", source_class: "B", confidence: 0.8 }] },
          { item_id: "DRP-2", kind: "GAP", subject_key: "q-bbbbbbbbbbbb", subject_kind: "QUESTION", subject_text: "Co lidé snídají?", subject_origin: "o", findings: [] },
        ],
      }),
      [`GET ${DR}/DR-1/bundle`]: () => ({
        quality_status: "OK", fictional_client: true, client_facing: false, accepted: [], snapshots: [], counts: {}, sha256: "x",
        subjects: [{ key: "q-aaaaaaaaaaaa", kind: "QUESTION", text: "Jak často lidé pijí kávu?", origin: "o" }, { key: "q-bbbbbbbbbbbb", kind: "QUESTION", text: "Co lidé snídají?", origin: "o" }],
        tracks: [{ track_id: "T-2", subject_key: "q-bbbbbbbbbbbb" }],
        quarantined: [{ reason: "low_source_quality", track_id: "T-2" }],
      }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const card = await screen.findByRole("region", { name: t("research.exec.trace.title") });
    const rows = () => within(card).getAllByRole("listitem").filter((li) => li.parentElement?.tagName === "OL");
    await waitFor(() => expect(within(rows()[0]).getByText(tv("research.exec.trace.evidence.found", { count: 1 }))).toBeTruthy());
    expect(within(rows()[0]).getByText("Kávu pije denně většina dospělých.")).toBeTruthy();
    expect(within(rows()[1]).getByText(t("research.exec.trace.evidence.gap"))).toBeTruthy();
    expect(within(rows()[1]).getByText(tv("research.exec.trace.evidence.rejected", { list: `1× ${t("research.exec.trace.quarantine.low_source_quality")}` }))).toBeTruthy();
    expect(within(rows()[2]).getByText(t("research.exec.trace.evidence.notStudied"))).toBeTruthy();
    // Asked for the server's widest page, so newer runs never hide the design run.
    expect(calls.filter((c) => c.method === "GET" && c.url.startsWith(DR) && !c.url.slice(DR.length).startsWith("/")).map((c) => c.url)).toEqual([`${DR}?limit=100`]);
  });

  it("keeps the card for stale links when the plan states no research question", async () => {
    const stale = { ...OUTLOOK, research_trace: { linked: true, questions: [], dangling: [{ question_id: "q1", research_question: "Stará otázka?" }] } };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => stale });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const card = await screen.findByRole("region", { name: t("research.exec.trace.title") });
    expect(within(card).getByText(/Stará otázka\?/)).toBeTruthy();
  });

  it("shows no card for a design with no items", async () => {
    api();
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.ready"))).toBeTruthy();
    expect(screen.queryByRole("region", { name: t("research.exec.outlook.title") })).toBeNull();
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
    // Each amount says USD once (it read "400.00 USD USD").
    expect(await within(cost).findByText("Z rozpočtu studie zbývá 400.00 USD (rozpočet 500.00 USD).")).toBeTruthy();
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
    // Beside the question, what remains of the study's budget, read as it asks (6d).
    expect(within(dialog).getByText("Tento běh může stát až 225.00 USD (práh potvrzení studie je 100.00 USD). Spustit? Z rozpočtu studie zbývá 400.00 USD. I při nejvyšší ceně by zbylo 175.00 USD, bez částek, které právě drží běžící kroky.")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: t("dialog.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(called("POST", RUNS)).toHaveLength(0); // no yes, no run

    fireEvent.click(screen.getByRole("button", { name: t("research.exec.start") }));
    fireEvent.click(await screen.findByRole("button", { name: "OK" }));
    await waitFor(() => expect(called("POST", RUNS)).toHaveLength(1));
    expect(called("POST", RUNS)[0].body).toEqual({ design_revision_id: "REV-a1", confirm_cost_usd: 225 });
  });

  it("starts a run that cannot answer its research questions only once the person acknowledges it", async () => {
    // research-integrity-report 1: the Fio pattern -- ready, but no question linked to any research question.
    const digest = "d".repeat(64);
    const answerability = {
      rules: "aia-answerability-1",
      capable: false,
      digest,
      acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    const reason = "Ověřujeme jen postup na fiktivních datech.";
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...READY, answerability }),
      // The new run records the acknowledgement it was started with.
      "POST /api/v1/studies/STU-1/research/runs": () =>
        run({ phase: "QUEUED", answerability: { ...answerability, acknowledgement: { reason, by: "USR-1" } } }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    expect(within(gate).getByText("Jak klienti důvěřují účtu?")).toBeTruthy();
    const start = screen.getByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement;
    expect(start.disabled).toBe(true); // runnable, not answerable: not started on a click
    fireEvent.click(within(gate).getByRole("checkbox", { name: t("research.exec.answerability.choice"), description: t("research.exec.answerability.choiceHelp") }));
    // Chosen for these gaps: the same button now says it starts with limitations.
    expect(screen.getByRole("button", { name: t("research.exec.answerability.startLimited") })).toBe(start);
    fireEvent.change(within(gate).getByRole("textbox"), { target: { value: reason } });
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    await waitFor(() => expect(called("POST", RUNS)).toHaveLength(1));
    expect(called("POST", RUNS)[0].body).toEqual({
      design_revision_id: "REV-a1",
      acknowledge_research_questions: { digest, reason },
    });
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("progress")));
  });

  it("says Spustit s omezeními only while Pokračovat s omezeními is chosen for the gaps on screen", async () => {
    // research-integrity-report 14 (D1): the choice is named, and the start says what it does. The
    // gaps read again under another respondent source have another digest: the choice made for
    // the first ones covers nothing, so the button says Spustit výzkum again and waits.
    const READINESS = "/api/v1/studies/STU-1/research/readiness";
    const sources = [
      { source: "fictional_roster", offered: true, reason: null, default: true },
      { source: "panel", offered: true, reason: null, default: false },
    ];
    api({
      [`GET ${READINESS}`]: () => {
        const source = new URL(called("GET", READINESS).at(-1)!.url, "http://x").searchParams.get("persona_source") ?? "fictional_roster";
        const answerability = {
          rules: "aia-answerability-1", capable: false, digest: (source === "panel" ? "b" : "a").repeat(64), acknowledgement_required: true,
          gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
        };
        return { ...READY, persona_source: source, persona_sources: sources, answerability };
      },
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    const start = screen.getByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement;
    expect(screen.getByText(t("research.exec.answerability.dock"))).toBeTruthy();
    const choice = within(gate).getByRole("checkbox", { name: t("research.exec.answerability.choice") }) as HTMLInputElement;
    fireEvent.click(choice);
    // Named at once; started only with a reason (10-1000 characters, unchanged).
    expect(start.textContent).toBe(t("research.exec.answerability.startLimited"));
    expect(start.disabled).toBe(true);
    fireEvent.change(within(gate).getByRole("textbox", { name: t("research.exec.answerability.why") }), { target: { value: "Ověřujeme jen postup na fiktivních datech." } });
    await waitFor(() => expect(start.disabled).toBe(false));
    const card = (await screen.findByRole("heading", { name: t("research.exec.respondents.title") })).closest("section") as HTMLElement;
    fireEvent.click(within(card).getByRole("radio", { name: new RegExp(t("research.exec.respondents.panel")) }));
    await waitFor(() => expect((within(card).getByRole("radio", { name: new RegExp(t("research.exec.respondents.panel")) }) as HTMLInputElement).checked).toBe(true));
    await waitFor(() => expect(choice.checked).toBe(false));
    expect(screen.getByRole("button", { name: t("research.exec.start") })).toBe(start);
    expect(start.disabled).toBe(true);
    expect(screen.queryByRole("button", { name: t("research.exec.answerability.startLimited") })).toBeNull();
    expect(called("POST", RUNS)).toHaveLength(0);
  });

  it("says nothing new started when the revision already had a run, and keeps the person here", async () => {
    // Review, 2026-10-16: the start returns the revision's existing run, which records nothing of
    // the acknowledgement just given; the page used to move on as if it had.
    const digest = "d".repeat(64);
    const answerability = {
      rules: "aia-answerability-1", capable: false, digest, acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...READY, answerability }),
      "POST /api/v1/studies/STU-1/research/runs": () =>
        run({ run_id: "RUN-old", created: false, phase: "CANCELLED", answerability: { ...answerability, acknowledgement: null, enforced: false } }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    fireEvent.click(within(gate).getByRole("checkbox", { name: t("research.exec.answerability.choice") }));
    fireEvent.change(within(gate).getByRole("textbox"), { target: { value: "Ověřujeme jen postup na fiktivních datech." } });
    const start = screen.getByRole("button", { name: t("research.exec.answerability.startLimited") }) as HTMLButtonElement;
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    const said = await screen.findByText((_, el) => el?.getAttribute("role") === "alert" && !!el.textContent?.includes(t("research.exec.answerability.existing")));
    expect(within(said).getByRole("link").getAttribute("href")).toBe(`${stagePath("progress")}?run=RUN-old`);
    expect(push).not.toHaveBeenCalled();
    // Review 2: the page stayed on "Spouštím…" with every control disabled until it was left.
    await waitFor(() => expect(start.textContent).toBe(t("research.exec.answerability.startLimited")));
    expect((within(gate).getByRole("checkbox", { name: t("research.exec.answerability.choice") }) as HTMLInputElement).disabled).toBe(false);
  });

  it("follows a run the start created, whatever it recorded", async () => {
    // Review 2: "nothing new started" was read from the acknowledgement, so a new run that is
    // capable at start (it records none) kept the person here as if nothing had started.
    const digest = "d".repeat(64);
    const answerability = {
      rules: "aia-answerability-1", capable: false, digest, acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...READY, answerability }),
      "POST /api/v1/studies/STU-1/research/runs": () => run({ created: true, phase: "QUEUED", answerability: { ...answerability, capable: true, gaps: [], acknowledgement: null } }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    fireEvent.click(within(gate).getByRole("checkbox", { name: t("research.exec.answerability.choice") }));
    fireEvent.change(within(gate).getByRole("textbox"), { target: { value: "Ověřujeme jen postup na fiktivních datech." } });
    const start = screen.getByRole("button", { name: t("research.exec.answerability.startLimited") }) as HTMLButtonElement;
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("progress")));
  });

  it("opens a run the start found instead of starting one, and says nothing new started (PC13)", async () => {
    api({ "POST /api/v1/studies/STU-1/research/runs": () => run({ created: false, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true }) });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const start = await screen.findByRole("button", { name: t("research.exec.start") });
    await waitFor(() => expect((start as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(start);
    await waitFor(() => expect(push).toHaveBeenCalledWith(`${stagePath("progress")}?run=RUN-1&found=1`));
  });

  it("says on Průběh that the run was found, not started, only for the run the start found", async () => {
    window.history.replaceState(null, "", "/?run=RUN-1&found=1");
    api(listed(COMPLETED));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.foundByStart"))).toBeTruthy();
    cleanup();
    window.history.replaceState(null, "", "/?run=RUN-1");
    api(listed(COMPLETED));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect((await screen.findAllByText(tv("research.exec.revision", { revision: COMPLETED.design_revision }))).length).toBeGreaterThan(0);
    expect(screen.queryByText(t("research.exec.foundByStart"))).toBeNull();
  });

  it("follows a found run that already holds this very acknowledgement", async () => {
    // Review 3: a start whose answer was lost, asked again with the same reason, finds the run that
    // recorded it; the page said the confirmation was saved nowhere.
    const digest = "d".repeat(64);
    const reason = "Ověřujeme jen postup na fiktivních datech.";
    const answerability = {
      rules: "aia-answerability-1", capable: false, digest, acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...READY, answerability }),
      "POST /api/v1/studies/STU-1/research/runs": () =>
        run({ created: false, phase: "QUEUED", answerability: { ...answerability, acknowledgement: { reason, by: "USR-1" } } }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    fireEvent.click(within(gate).getByRole("checkbox", { name: t("research.exec.answerability.choice") }));
    fireEvent.change(within(gate).getByRole("textbox"), { target: { value: reason } });
    const start = screen.getByRole("button", { name: t("research.exec.answerability.startLimited") }) as HTMLButtonElement;
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    await waitFor(() => expect(push).toHaveBeenCalledWith(stagePath("progress")));
    expect(screen.queryByText((_, el) => !!el?.textContent?.includes(t("research.exec.answerability.existing")) && el?.getAttribute("role") === "alert")).toBeNull();
  });

  it("shows the gaps the server refused even when reading readiness again fails", async () => {
    // Review 3: a failed re-read left the old reading on screen under a message calling it the
    // server's current one.
    const answerability = {
      rules: "aia-answerability-1", capable: false, digest: "d".repeat(64), acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Co klienty odrazuje?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    let reads = 0;
    api({
      "GET /api/v1/studies/STU-1/research/readiness": () =>
        reads++ === 0
          ? { ...READY, answerability: { rules: "aia-answerability-1", capable: true, digest: "e".repeat(64), acknowledgement_required: false, gaps: [] } }
          : new Response(JSON.stringify({ code: "internal_error", message: "Chyba.", details: {} }), { status: 500 }),
      "POST /api/v1/studies/STU-1/research/runs": () =>
        new Response(JSON.stringify({ code: "research_questions_unanswerable", message: "…", details: answerability }), { status: 409 }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const start = await screen.findByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement;
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    expect(await screen.findByText(t("research.exec.answerability.refused"))).toBeTruthy();
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    expect(within(gate).getByText("Co klienty odrazuje?")).toBeTruthy();
  });

  it("says a start refused for its research questions in Czech, beside the gaps read again", async () => {
    const digest = "d".repeat(64);
    const answerability = {
      rules: "aia-answerability-1", capable: false, digest, acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    let reads = 0;
    api({
      // Read first without the requirement (the gate was off), then as the server refuses.
      "GET /api/v1/studies/STU-1/research/readiness": () => (reads++ === 0 ? { ...READY, answerability: { ...answerability, acknowledgement_required: false } } : { ...READY, answerability }),
      "POST /api/v1/studies/STU-1/research/runs": () =>
        new Response(JSON.stringify({ code: "research_questions_unanswerable", message: "The run cannot answer every research question.", details: answerability }), { status: 409 }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const start = await screen.findByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement;
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    const said = await screen.findByText(t("research.exec.answerability.refused"));
    expect(said.getAttribute("role")).toBe("alert");
    expect(screen.queryByText(/cannot answer/)).toBeNull();
    expect(await screen.findByRole("checkbox", { name: t("research.exec.answerability.choice") })).toBeTruthy();
  });

  it("calls the gate runnable only where readiness lets the design run", async () => {
    const answerability = {
      rules: "aia-answerability-1", capable: false, digest: "e".repeat(64), acknowledgement_required: false,
      gaps: [{ kind: "not_answerable", research_question: "Co je odrazuje?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...READY, ready: false, answerability }) });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByRole("region", { name: t("research.exec.answerability.titleNotReady") })).toBeTruthy();
    expect(screen.queryByRole("region", { name: t("research.exec.answerability.title") })).toBeNull();
  });

  it("shows the gaps without asking where the deployment does not require an acknowledgement", async () => {
    // The switch off (the default): the researcher still sees what the run cannot answer, and
    // starting sends no acknowledgement the server did not ask for.
    const answerability = {
      rules: "aia-answerability-1", capable: false, digest: "e".repeat(64), acknowledgement_required: false,
      gaps: [{ kind: "not_answerable", research_question: "Co je odrazuje?", verdict: "UNANSWERABLE", reasons: ["measures_unanswerable"], measures: ["q2"] }],
      pending: ["Jak často platí kartou?"],
    };
    api({ "GET /api/v1/studies/STU-1/research/readiness": () => ({ ...READY, answerability }) });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    expect(within(gate).getByText("Co je odrazuje?")).toBeTruthy();
    expect(within(gate).getByText(/Běh na ni neodpoví/)).toBeTruthy();
    expect(within(gate).getByText(/Jak často platí kartou\?/)).toBeTruthy();
    expect(within(gate).queryByRole("checkbox")).toBeNull();
    expect(within(gate).getByText(t("research.exec.answerability.notRequired"))).toBeTruthy();
    // Under the gap, the way to the question that measures it (research-integrity-report 14).
    expect(within(gate).getByRole("link", { name: t("research.exec.answerability.fixTo.measure") }).getAttribute("href")).toBe(`${stagePath("questionnaire")}#qedit_q2`);
    const start = screen.getByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement;
    await waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);
    await waitFor(() => expect(called("POST", RUNS)).toHaveLength(1));
    expect(called("POST", RUNS)[0].body).toEqual({ design_revision_id: "REV-a1" });
  });

  it("offers the client's materialized children, and a run started over one names it", async () => {
    const child = (id: string, client: string, achieved: number) => ({
      version_id: id, label: `v_5+${id}`, content_sha256: "c".repeat(64), row_count: 6, column_count: 5,
      parent_version_id: "DSV-v_5", status: "REGISTERED", runtime_eligible: false, companions_attached: false,
      imported_at: "2026-10-12T09:00:00Z", imported_by: "USR-1", provenance: "materialized", owner_client_id: client,
      extension_sha256: "e".repeat(64),
      materialized: { dimension_id: id, kind: "scale_1_10", definition_sha256: "d".repeat(64), method: "m@1", target: 2.0, achieved, target_met: Math.abs(achieved - 2.0) <= 0.01, usable_predictors: ["vek"] },
    });
    api({
      "GET /api/v1/population": () => ({ dataset_id: "d", contract_id: "c", populations: [], history: [],
        versions: [child("ochota", "CLI-1", 2.68), child("cizi", "CLI-other", 2.0)] }),
    });
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    const choice = await screen.findByRole("group", { name: t("research.exec.population.text") });
    // Only this client's child is offered, with its unmet target said so; LIVE is the default.
    expect(within(choice).queryByText("cizi")).toBeNull();
    expect(within(choice).getByText("cíl 2,00, dosaženo 2,68")).toBeTruthy();
    expect(within(choice).getByText(t("aia.intelligence.population.children.verdict.unmet"))).toBeTruthy();
    expect((within(choice).getByRole("radio", { name: t("research.exec.population.live") }) as HTMLInputElement).checked).toBe(true);

    fireEvent.click(within(choice).getAllByRole("radio")[1]);
    // The checks are read again over the child, so readiness and the start forecast one population.
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1/research/readiness").at(-1)!.url).toContain("population_version_id=ochota"));
    await waitFor(() => expect((screen.getByRole("button", { name: t("research.exec.start") }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: t("research.exec.start") }));
    await waitFor(() => expect(called("POST", RUNS)).toHaveLength(1));
    expect(called("POST", RUNS)[0].body).toEqual({ design_revision_id: "REV-a1", population_version_id: "ochota" });
  });

  it("offers no choice when the client has no child, and a run names no population", async () => {
    api();
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.start") }));
    await waitFor(() => expect(called("POST", RUNS)).toHaveLength(1));
    expect(called("POST", RUNS)[0].body).toEqual({ design_revision_id: "REV-a1" });
    expect(screen.queryByRole("group", { name: t("research.exec.population.text") })).toBeNull();
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
      // The retry's run, as the API then serves it (the page follows and reads it).
      "GET /api/v1/studies/STU-1/research/runs/RUN-2": () => run({ run_id: "RUN-2", retry_of: "RUN-1", phase: "QUEUED" }),
      "GET /api/v1/studies/STU-1": () => STUDY,
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.retry") }));
    const dialog = await screen.findByRole("dialog");
    // Beside the question, what remains of the study's budget, read as it asks (6d).
    expect(within(dialog).getByText("Tento běh může stát až 225.00 USD (práh potvrzení studie je 100.00 USD). Spustit? Z rozpočtu studie zbývá 400.00 USD. I při nejvyšší ceně by zbylo 175.00 USD, bez částek, které právě drží běžící kroky.")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "OK" }));
    expect(await screen.findByText("Opakování běhu RUN-1")).toBeTruthy();
    expect(asked).toBe(1);
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/retry").map((c) => c.body)).toEqual([null, { confirm_cost_usd: 225 }]);
  });

  it("asks for the research questions on a retry the server refused, retries with the answer, and then asks no more", async () => {
    // research-integrity-report 1: a run started before the gate has no acknowledgement to inherit.
    const cancelled = { ...PARKED, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true };
    const digest = "f".repeat(64);
    const refusal = {
      rules: "aia-answerability-1", capable: false, digest, acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    api({
      ...listed(cancelled),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/retry": (b) =>
        (b as { acknowledge_research_questions?: unknown } | null)?.acknowledge_research_questions
          ? run({ run_id: "RUN-2", retry_of: "RUN-1", phase: "QUEUED" })
          : new Response(JSON.stringify({ code: "research_questions_unanswerable", message: "…", details: refusal }), { status: 409 }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-2": () => run({ run_id: "RUN-2", retry_of: "RUN-1", phase: "QUEUED" }),
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.retry") }));
    const gate = await screen.findByRole("region", { name: t("research.exec.answerability.title") });
    // A retry reruns the original's Design Revision: no edit closes its gaps, so no link offers
    // one; a fix applies to a new run, started from Kontrola a spuštění (review web#8).
    expect(within(gate).getAllByRole("link").map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      [tv("research.exec.answerability.retryOpen", { stage: t("aia.stages.run") }), stagePath("run")],
    ]);
    expect(within(gate).getByText(tv("research.exec.answerability.retryFixes", { stage: t("aia.stages.run") }))).toBeTruthy();
    expect(within(gate).getByText(t("research.exec.answerability.helpRetry"))).toBeTruthy();
    expect(within(gate).queryByText(t("research.exec.answerability.help"))).toBeNull();
    const again = screen.getByRole("button", { name: t("research.exec.answerability.retryAction") }) as HTMLButtonElement;
    expect(again.disabled).toBe(true);
    fireEvent.click(within(gate).getByRole("checkbox", { name: t("research.exec.answerability.choice") }));
    fireEvent.change(within(gate).getByRole("textbox"), { target: { value: "Opakujeme jen ověření postupu." } });
    await waitFor(() => expect(again.disabled).toBe(false));
    fireEvent.click(again);
    expect(await screen.findByText("Opakování běhu RUN-1")).toBeTruthy();
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/retry").map((c) => c.body)).toEqual([
      null,
      { acknowledge_research_questions: { digest, reason: "Opakujeme jen ověření postupu." } },
    ]);
    // Retried: the gaps were the old run's, so nothing about them is asked any more.
    await waitFor(() => expect(screen.queryByRole("region", { name: t("research.exec.answerability.title") })).toBeNull());
  });

  it("refuses a retry of an old-method run and starts a new run on aia-sociomap-5 from its revision", async () => {
    const cancelled = { ...PARKED, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true };
    const revision = (cancelled as { design_revision_id: string }).design_revision_id;
    const refusal = {
      code: "run_on_retired_method",
      message: "Běh byl spočten starší metodou Sociomapy a znovu se nespouští.",
      details: {
        methods: ["aia-sociomap-1", "aia-sociomap-3"],
        design_revision_id: revision,
        new_run: { method: "POST", href: "/api/v1/studies/STU-1/research/runs", body: { design_revision_id: revision, persona_source: "panel", population_version_id: "VER-child", acknowledge_research_questions: { digest: "d".repeat(64), reason: "Pokračujeme s omezeními." } } },
      },
    };
    api({
      ...listed(cancelled),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/retry": () => new Response(JSON.stringify(refusal), { status: 409 }),
      "POST /api/v1/studies/STU-1/research/runs": () => run({ run_id: "RUN-2", phase: "QUEUED" }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-2": () => run({ run_id: "RUN-2", phase: "QUEUED" }),
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.retry") }));
    const note = await waitFor(() => {
      const found = document.querySelector("[data-retired-method]");
      if (!found) throw new Error("no refusal shown");
      return found as HTMLElement;
    });
    expect(within(note).getByText(t("research.exec.retiredMethod.text"))).toBeTruthy();
    const starts = () => calls.filter((c) => c.method === "POST" && c.url === "/api/v1/studies/STU-1/research/runs");
    expect(starts()).toHaveLength(0); // the refusal started nothing
    fireEvent.click(within(note).getByRole("button", { name: t("research.exec.retiredMethod.action") }));
    await waitFor(() => expect(starts()).toHaveLength(1));
    // The new run starts as the refused one did: its respondents, population and decision.
    expect(starts()[0].body).toEqual({
      design_revision_id: revision, persona_source: "panel", population_version_id: "VER-child",
      acknowledge_research_questions: { digest: "d".repeat(64), reason: "Pokračujeme s omezeními." },
    });
    await waitFor(() => expect(document.querySelector("[data-retired-method]")).toBeNull());
  });

  it("asks for the research questions when the offered new run is refused for them, and starts it with the answer", async () => {
    const cancelled = { ...PARKED, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true };
    const digest = "e".repeat(64);
    const gaps = {
      rules: "aia-answerability-1", capable: false, digest, acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    const refusal = {
      code: "run_on_retired_method", message: "…",
      details: { methods: ["aia-sociomap-1"], design_revision_id: "REV-a1",
        new_run: { method: "POST", href: "/api/v1/studies/STU-1/research/runs", body: { design_revision_id: "REV-a1", persona_source: "fictional_roster" } } },
    };
    api({
      ...listed(cancelled),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/retry": () => new Response(JSON.stringify(refusal), { status: 409 }),
      "POST /api/v1/studies/STU-1/research/runs": (b) =>
        (b as { acknowledge_research_questions?: unknown } | null)?.acknowledge_research_questions
          ? run({ run_id: "RUN-2", phase: "QUEUED" })
          : new Response(JSON.stringify({ code: "research_questions_unanswerable", message: "…", details: gaps }), { status: 409 }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-2": () => run({ run_id: "RUN-2", phase: "QUEUED" }),
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.retry") }));
    const note = await waitFor(() => {
      const found = document.querySelector("[data-retired-method]");
      if (!found) throw new Error("no refusal shown");
      return found as HTMLElement;
    });
    fireEvent.click(within(note).getByRole("button", { name: t("research.exec.retiredMethod.action") }));
    const gate = await within(note).findByRole("region", { name: t("research.exec.answerability.title") });
    const again = within(note).getByRole("button", { name: t("research.exec.retiredMethod.action") }) as HTMLButtonElement;
    expect(again.disabled).toBe(true);
    fireEvent.click(within(gate).getByRole("checkbox", { name: t("research.exec.answerability.choice") }));
    fireEvent.change(within(gate).getByRole("textbox"), { target: { value: "Spouštíme nový běh s omezeními." } });
    await waitFor(() => expect(again.disabled).toBe(false));
    fireEvent.click(again);
    const starts = () => calls.filter((c) => c.method === "POST" && c.url === "/api/v1/studies/STU-1/research/runs");
    await waitFor(() => expect(starts()).toHaveLength(2));
    expect(starts()[1].body).toEqual({
      design_revision_id: "REV-a1", persona_source: "fictional_roster",
      acknowledge_research_questions: { digest, reason: "Spouštíme nový běh s omezeními." },
    });
    // The new run is followed: the refusal belonged to the old one and is gone.
    await waitFor(() => expect(document.querySelector("[data-retired-method]")).toBeNull());
  });

  it("keeps a refused retry's gaps only while their run can still be retried", async () => {
    // Review 2: the gate stayed after the run moved on, and its button retried whatever run was shown.
    let shown: Record<string, unknown> = { ...PARKED, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true };
    const refusal = {
      rules: "aia-answerability-1", capable: false, digest: "f".repeat(64), acknowledgement_required: true,
      gaps: [{ kind: "not_answerable", research_question: "Jak klienti důvěřují účtu?", verdict: "UNKNOWN", reasons: ["unlinked_design"], measures: [] }],
    };
    api({
      ...listed(shown as ReturnType<typeof run>),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1": () => shown,
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/retry": () =>
        new Response(JSON.stringify({ code: "research_questions_unanswerable", message: "…", details: refusal }), { status: 409 }),
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.retry") }));
    expect(await screen.findByRole("region", { name: t("research.exec.answerability.title") })).toBeTruthy();
    // Someone retried it meanwhile: read again, it is no longer retryable, and nothing is asked.
    shown = { ...shown, retryable: false };
    fireEvent.click(screen.getByRole("button", { name: t("research.exec.refresh") }));
    await waitFor(() => expect(screen.queryByRole("region", { name: t("research.exec.answerability.title") })).toBeNull());
    expect(screen.queryByRole("button", { name: t("research.exec.answerability.retryAction") })).toBeNull();
  });
});

describe("Progress", () => {
  it("never calls a run with a blocked module done: its state, its reason, and a bar that does not count it (6a)", async () => {
    const blocked = run({
      ...COMPLETED,
      steps: [...COMPLETED.steps, step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", analysis_outcome: "BLOCKED" }), step("analysis_objects", "SUCCEEDED", { kind: "research_analysis", analysis_outcome: "COMPLETED" })],
    });
    api({ ...listed(blocked), "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis/retryable": () => ({ run_id: "RUN-1", modules: ["executive"] }) });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect(await screen.findByText("1 z 2 částí analýzy potřebuje opravu.")).toBeTruthy();
    expect(screen.getAllByText("Potřebuje opravu").length).toBeGreaterThanOrEqual(2); // the run, and its blocked module
    expect(screen.queryByText("Dokončeno")).toBeNull();
    expect(screen.getByText("6 z 7 kroků hotovo")).toBeTruthy();
  });

  it("says an analysis retry of an old-method run was refused, and starts the new run it names", async () => {
    const blocked = run({
      ...COMPLETED,
      steps: [...COMPLETED.steps, step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", analysis_outcome: "BLOCKED" })],
    });
    const refusal = {
      code: "run_on_retired_method", message: "…",
      details: { methods: ["aia-sociomap-1", "aia-sociomap-3"], design_revision_id: "REV-a1",
        new_run: { method: "POST", href: "/api/v1/studies/STU-1/research/runs", body: { design_revision_id: "REV-a1", persona_source: "fictional_roster" } } },
    };
    api({
      ...listed(blocked),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis/retryable": () => ({ run_id: "RUN-1", modules: ["executive"] }),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/analysis/retry": () => new Response(JSON.stringify(refusal), { status: 409 }),
      "POST /api/v1/studies/STU-1/research/runs": () => run({ run_id: "RUN-2", phase: "QUEUED" }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-2": () => run({ run_id: "RUN-2", phase: "QUEUED" }),
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const card = (await screen.findByRole("region", { name: t("research.exec.analysisRetry.title") })) as HTMLElement;
    fireEvent.click(within(card).getByRole("button", { name: t("research.exec.analysisRetry.action") }));
    const note = await waitFor(() => {
      const found = card.querySelector("[data-retired-method]");
      if (!found) throw new Error("no refusal shown");
      return found as HTMLElement;
    });
    const starts = () => calls.filter((c) => c.method === "POST" && c.url === "/api/v1/studies/STU-1/research/runs");
    expect(starts()).toHaveLength(0);
    fireEvent.click(within(note).getByRole("button", { name: t("research.exec.retiredMethod.action") }));
    await waitFor(() => expect(starts()).toHaveLength(1));
    expect(starts()[0].body).toEqual({ design_revision_id: "REV-a1", persona_source: "fictional_roster" });
  });

  it("offers to repair a run whose modules an earlier version of AIA completed, and says that is why (PC3)", async () => {
    const MODULES = ["executive", "objects"];
    const stale = run({
      ...COMPLETED,
      steps: [...COMPLETED.steps, ...MODULES.map((m) => step(`analysis_${m}`, "SUCCEEDED", { kind: "research_analysis", analysis_outcome: "COMPLETED" }))],
    });
    api({ ...listed(stale), "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis/retryable": () => ({ run_id: "RUN-1", modules: MODULES, stale: MODULES }) });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const card = (await screen.findByRole("region", { name: t("research.exec.analysisRetry.title") })) as HTMLElement;
    expect(within(card).getByText(tv("research.exec.analysisRetry.stale", { n: 2 }))).toBeTruthy();
    // Not a model's failure: the words for one are not used.
    expect(within(card).queryByText(/model nedokázal/)).toBeNull();
    expect(within(card).getByRole("button", { name: t("research.exec.analysisRetry.action") })).toBeTruthy();
  });

  it("says who answered, the population, and which selected dimensions and filters were applied (run-recovery-and-truth 5b)", async () => {
    const answered = run({
      ...COMPLETED,
      persona_source: "fictional_roster",
      population: { population_id: "cz", version_id: "v17_4_0", version_label: "v17_4_0", read_by_fieldwork: false },
      selection: {
        dimensions: ["region"], dimensions_unmatched: ["region"], dimensions_applied: false, dimensions_reason: "dimensions_need_population_draw",
        audience_filters: { vek: { min: 30 } }, filters_applied: false, filters_reason: "filters_need_population_draw",
      },
    });
    api(listed(answered));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const R = "research.exec.respondents.receipt";
    const card = (await screen.findByRole("heading", { name: t(`${R}.title`) })).closest("section") as HTMLElement;
    const value = (label: string) => within(card).getByText(label).nextElementSibling?.textContent;
    expect(value(t(`${R}.source`))).toBe(`${t("research.exec.respondents.fictional_roster")} · ${t(`${R}.observed.SIMULATED`)}`);
    expect(value(t(`${R}.population`))).toContain("v17_4_0");
    expect(value(t(`${R}.dimensions`))).toContain(t(`${R}.reason.dimensions_need_population_draw`));
    // A selected id that is no persona topic is named: it never reaches a respondent (Codex on #447).
    expect(value(t(`${R}.dimensions`))).toContain(tv(`${R}.unmatched`, { list: "region" }));
    expect(value(t(`${R}.filters`))).toBe(`vek · ${t(`${R}.reason.filters_need_population_draw`)}`);
    expect(within(card).queryByRole("alert")).toBeNull();
  });

  it("names data that does not match the source the run chose, and a run that recorded no selection", async () => {
    api(listed(run({ ...COMPLETED, persona_source: "panel" })));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const R = "research.exec.respondents.receipt";
    const card = (await screen.findByRole("heading", { name: t(`${R}.title`) })).closest("section") as HTMLElement;
    expect(within(card).getByRole("alert").textContent).toBe(t(`${R}.mismatch`));
    expect(within(card).getByText(t(`${R}.unrecorded`))).toBeTruthy();
  });

  it("keeps both sides of a mismatch in view, the stored origin code beside the pinned source, pointable by the Lead (artifact-fieldwork FLD7)", async () => {
    api(listed(run({ ...COMPLETED, persona_source: "panel" })));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const R = "research.exec.respondents.receipt";
    const card = (await screen.findByRole("heading", { name: t(`${R}.title`) })).closest("section") as HTMLElement;
    const value = (label: string) => within(card).getByText(label).nextElementSibling?.textContent;
    // Named, never resolved: the pinned panel, what the data say, and the code as stored.
    expect(value(t(`${R}.source`))).toBe(`${t("research.exec.respondents.panel")} · ${t(`${R}.observed.SIMULATED`)}`);
    expect(value(t(`${R}.origin`))).toBe("SYNTHETIC_FIXTURE");
    // Pointable by the Lead: the mark parses as the fieldwork stage's receipt (#618).
    const mark = card.closest("[data-aia]")?.getAttribute("data-aia");
    expect(mark).toBe("receipt:respondents");
    expect(parseAiaId(mark!)).toEqual({ kind: "receipt", id: "respondents", stage: "fieldwork" });
  });

  it("says the data's origin is not yet stored while fieldwork has not stored it", async () => {
    api(listed(PARKED));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const R = "research.exec.respondents.receipt";
    const card = (await screen.findByRole("heading", { name: t(`${R}.title`) })).closest("section") as HTMLElement;
    expect(within(card).getByText(t(`${R}.origin`)).nextElementSibling?.textContent).toBe(t(`${R}.pending`));
    expect(card.querySelector("[data-origin-code]")).toBeNull();
  });

  it("tags each step AI or deterministic and makes it pointable by the Lead (artifact-fieldwork FLD2)", async () => {
    api(listed(PARKED));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const list = await screen.findByRole("list", { name: t("aia.stages.progress") });
    const work = (key: string) => list.querySelector(`[data-aia="step:${key}"] [data-step-work]`)?.textContent;
    // AI respondents answer this run's fieldwork: a model step.
    expect(work("run")).toBe(t("research.exec.stepWork.ai"));
    expect(work("compile")).toBe(t("research.exec.stepWork.running"));
    expect(work("aggregate")).toBe(t("research.exec.stepWork.running"));
  });

  it("tags fictional fixture fieldwork as code, never as AI", async () => {
    api(listed(COMPLETED));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const list = await screen.findByRole("list", { name: t("aia.stages.progress") });
    expect(list.querySelector('[data-aia="step:run"] [data-step-work]')?.textContent).toBe(t("research.exec.stepWork.running"));
  });

  it("tags no fieldwork step when the run recorded no source: unknown is never stamped as code", async () => {
    api(listed(run({ ...COMPLETED, fieldwork_source: "" })));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const list = await screen.findByRole("list", { name: t("aia.stages.progress") });
    expect(list.querySelector('[data-aia="step:run"]')).toBeTruthy();
    expect(list.querySelector('[data-aia="step:run"] [data-step-work]')).toBeNull();
    expect(list.querySelector('[data-aia="step:aggregate"] [data-step-work]')?.textContent).toBe(t("research.exec.stepWork.running"));
  });

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
      expect.stringContaining("Sociomapa"),
    ]);
    expect(within(steps[3]).getByText("Čeká na předchozí krok")).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("research.exec.retry") })).toBeNull();
    expect(screen.queryByRole("note")).toBeNull(); // not fictional: no fiction banner
  });

  it("says a modelled run is modelled on its banner and its steps, never fictional or fieldwork (ADR 0024 §7)", async () => {
    const modelled = run({
      status: "RUNNING", phase: "RUNNING",
      steps: [
        step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
        step("run", "SUCCEEDED", { artifact_id: "ART-3", data_origin: "MODELLED_AI_PANEL", data_origin_kind: "MODELLED" }),
        step("aggregate", "SUCCEEDED", { artifact_id: "ART-4", data_origin: "MODELLED_AI_PANEL" }),
      ],
    });
    api(listed(modelled));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const banner = await screen.findByText(/^Modelováno: AI respondenti z populace\. Odpovědi vytvořil model/);
    expect(banner.getAttribute("data-origin")).toBe("modelled");
    expect(screen.queryByText(t("research.exec.syntheticNotice"))).toBeNull();
    const steps = within(screen.getByRole("list", { name: t("aia.stages.progress") })).getAllByRole("listitem");
    const kinds = steps.flatMap((li) => [...li.querySelectorAll("[data-origin-kind]")].map((e) => e.getAttribute("data-origin-kind")));
    expect(kinds).toEqual(["MODELLED", "MODELLED"]);
    expect(within(steps[1]).getByText("Modelovaná data")).toBeTruthy();
    expect(within(steps[1]).queryByText("MODELLED_AI_PANEL")).toBeNull(); // the raw value is a title, not a fault chip
  });

  it("says an origin it has no word for is unknown, never real", async () => {
    api(listed(run({ status: "RUNNING", phase: "RUNNING", steps: [step("run", "SUCCEEDED", { artifact_id: "ART-3", data_origin: "PANEL" })] })));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect((await screen.findByText(t("research.exec.unknownOriginNotice"))).getAttribute("data-origin")).toBe("unknown");
  });

  it("shows an orb beside every running step, as AI where a model thinks and as work where code runs", async () => {
    api(listed(run({
      steps: [
        step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
        step("preflight", "RUNNING"),
        step("run", "RUNNING"),
        step("aggregate", "BLOCKED", { attempts_recorded: 0, started_at: null }),
        step("analysis_executive", "RUNNABLE", { attempts_recorded: 0, started_at: null }),
      ],
    })));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const list = await screen.findByRole("list", { name: t("aia.stages.progress") });
    const orbs = [...list.querySelectorAll("li")].map((li) => {
      const orb = li.querySelector<HTMLElement>("[data-orb]");
      return [li.dataset.step, orb ? `${orb.dataset.orb}/${orb.dataset.orbInk}` : null];
    });
    // Preflight is code at work; AI fieldwork thinks; a queued or blocked step shows nothing.
    expect(orbs).toEqual([["compile", null], ["preflight", "solving/running"], ["run", "listening/ai"], ["aggregate", null], ["analysis_executive", null]]);
    for (const orb of list.querySelectorAll("[data-orb]")) expect(orb.getAttribute("aria-hidden")).toBe("true");
  });

  it("opens a running step's space with a large orb and what its events said, and no other", async () => {
    const running = run({
      steps: [
        step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
        step("run", "RUNNING", { started_at: new Date(Date.now() - 65_000).toISOString() }),
        step("aggregate", "BLOCKED", { attempts_recorded: 0, started_at: null }),
      ],
    });
    const feed = (id: number, step_id: string | null, event_type: string, message: string, payload: Record<string, unknown> = {}) => ({
      event_id: id, step_id, attempt_id: "ATT-1", event_type, level: "INFO", message, payload, created_at: "2026-09-25T08:01:00Z",
    });
    api({
      ...listed(running),
      [`GET /api/v1/studies/STU-1/research/runs/${running.run_id}/events`]: () => [
        feed(1, null, "RUN_CREATED", "created"),
        feed(2, "STEP-compile", "STEP_SUCCEEDED", "compile completed"),
        feed(3, "STEP-run", "ATTEMPT_CLAIMED", "run claimed by worker-1"),
        feed(4, "STEP-run", "STEP_PROGRESS", "AI respondenti odpověděli", { respondents: 40, of: 300 }),
        feed(5, "STEP-run", "STEP_PROGRESS", "ai_request_answered", { input_tokens: 1200, output_tokens: 380, cost_usd: 0.004, latency_ms: 3200 }),
      ],
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const list = await screen.findByRole("list", { name: t("aia.stages.progress") });
    const li = (key: string) => list.querySelector<HTMLElement>(`li[data-step="${key}"]`)!;
    // The finished and the waiting step keep their row; only the running one opens.
    expect(li("compile").querySelector("[data-step-activity]")).toBeNull();
    expect(li("aggregate").querySelector("[data-step-activity]")).toBeNull();
    const panel = li("run").querySelector<HTMLElement>("[data-step-activity]")!;
    expect(panel.dataset.stepActivity).toBe("open");
    expect(panel.querySelector<HTMLElement>("[data-orb]")?.style.width).toBe("64px");
    const log = await within(panel).findByRole("log");
    // The log's times are the time alone, so its first entry of a day is headed by that day.
    const items = within(log).getAllByRole("listitem");
    expect(items[0].hasAttribute("data-day")).toBe(true);
    expect(items[0].textContent).toBe("25. září 2026");
    expect(items.filter((l) => !l.hasAttribute("data-day")).map((l) => l.textContent?.replace(/^[\d:]+/, ""))).toEqual([
      "Worker krok převzal",
      "AI respondenti odpověděli · 40 z 300 respondentů",
      "Model odpověděl · 1200 → 380 tokenů · $0.004 · 3.2 s",
    ]);
    // Its counts as the step reported them, and how long it has run: never a percentage.
    expect(panel.textContent).toContain("40 z 300 respondentů");
    expect(panel.textContent).toContain("1 odpovědí modelu · 1580 tokenů · $0.004");
    expect(panel.textContent).toMatch(/Běží 1 min 0[56] s/);
    expect(panel.textContent).not.toMatch(/%/);
  });

  it("keeps parked fieldwork's last reported count beside the step, from its events (FLD3)", async () => {
    api({
      ...listed(PARKED),
      [`GET /api/v1/studies/STU-1/research/runs/${PARKED.run_id}/events`]: () => [
        { event_id: 7, step_id: "STEP-run", attempt_id: "ATT-1", event_type: "STEP_PROGRESS", level: "INFO", message: "fieldwork_progress",
          payload: { version: "aia-fieldwork-events-1", respondents: 40, of: 300, sent: 70, replayed: 50 }, created_at: "2026-09-25T08:01:00Z" },
      ],
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const list = await screen.findByRole("list", { name: t("aia.stages.progress") });
    const row = list.querySelector<HTMLElement>('li[data-step="run"]')!;
    await waitFor(() => expect(row.querySelector("[data-last-reported]")?.textContent).toBe(
      `${tv("research.exec.activity.lastReported", { done: 40, of: 300 })} · ${tv("research.exec.activity.fieldworkReplayed", { replayed: 50 })}`,
    ));
    expect(row.querySelector("[data-step-activity]")).toBeNull();
    expect(list.querySelectorAll("[data-last-reported]")).toHaveLength(1);
  });

  it("shows a panel run's quota cells filled by the respondents fieldwork reported (RQC7b)", async () => {
    const feed = (id: number, message: string, payload: Record<string, unknown>) => ({
      event_id: id, step_id: "STEP-run", attempt_id: "ATT-1", event_type: "STEP_PROGRESS", level: "INFO", message,
      payload: { version: "aia-fieldwork-events-2", ...payload }, created_at: "2026-09-25T08:01:00Z",
    });
    api({
      ...listed(PARKED),
      [`GET /api/v1/studies/STU-1/research/runs/${PARKED.run_id}/events`]: () => [
        feed(1, "fieldwork_sample", { quota_fields: ["pohlavi", "vek"], cells: [
          { key: "zena/18-29", values: ["žena", "18-29"], n: 1 },
          { key: "muz/30-44", values: ["muž", "30-44"], n: 2 },
        ] }),
        feed(2, "fieldwork_respondent", { respondent: 1, cell: "zena/18-29", sent: 1, replayed: 0 }),
        feed(3, "fieldwork_respondent", { respondent: 2, cell: "muz/30-44", sent: 1, replayed: 0 }),
      ],
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const list = await screen.findByRole("list", { name: t("aia.stages.progress") });
    const row = list.querySelector<HTMLElement>('li[data-step="run"]')!;
    const fill = await waitFor(() => {
      const el = row.querySelector<HTMLElement>("[data-quota-fill]");
      expect(el).not.toBeNull();
      return el!;
    });
    expect(within(fill).getByText(tv("research.exec.activity.quotaTitle", { full: 1, cells: 2 }))).toBeTruthy();
    const cells = [...fill.querySelectorAll<HTMLElement>("tr[data-cell]")].map((tr) => tr.textContent);
    expect(cells).toEqual(["žena · 18-29" + tv("research.exec.activity.quotaOf", { answered: 1, n: 1 }), "muž · 30-44" + tv("research.exec.activity.quotaOf", { answered: 1, n: 2 })]);
    expect(fill.textContent).toContain(t("research.exec.activity.quotaNote"));
    // A full-size touch target on a phone, with the shared focus ring (Codex on #836).
    expect(fill.querySelector("summary")?.className).toMatch(/min-h-11/);
    expect(fill.querySelector("summary")?.className).toMatch(/focus-visible/);
    expect(list.querySelectorAll("[data-quota-fill]")).toHaveLength(1);
  });

  it("shows no orb while fieldwork waits for the AI runtime", async () => {
    api(listed(PARKED));
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    const list = await screen.findByRole("list", { name: t("aia.stages.progress") });
    expect(list.querySelector("[data-orb]")).toBeNull();
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

  it("lets a run parked for the AI runtime go on, and says it will not by itself (PC4)", async () => {
    const parked = () => parkedWith([
      step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
      step("preflight", "SUCCEEDED", { artifact_id: "ART-2" }),
      step("run", "WAITING_PROVIDER", { waiting_reason: "ai_runtime_unavailable", failure_class: "RUNTIME_UNAVAILABLE" }),
    ]);
    const resumed = run({ steps: [step("compile", "SUCCEEDED"), step("preflight", "SUCCEEDED"), step("run", "RUNNABLE")] });
    let going = false;
    const RESUME = "/api/v1/studies/STU-1/research/runs/RUN-1/resume";
    api({
      ...listed(parked()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1": () => (going ? resumed : parked()),
      [`POST ${RESUME}`]: () => { going = true; return resumed; },
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.parkedResume"))).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: t("research.exec.resume") }));
    await waitFor(() => expect(called("POST", RESUME)).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText(t("research.exec.parkedResume"))).toBeNull());
    // Nothing new was started: the same run, no start and no retry.
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/retry")).toHaveLength(0);
    expect(calls.filter((c) => c.method === "POST" && c.url === "/api/v1/studies/STU-1/research/runs")).toHaveLength(0);
  });

  it("offers no way on for a run parked on a study that may not change", async () => {
    api(listed(parkedWith([step("run", "WAITING_PROVIDER", { waiting_reason: "ai_runtime_unavailable" })])));
    render(<ResearchScreen step="progress" frame={{ ...TEST_FRAME, canEdit: false, canReview: true }} />);
    expect(await screen.findByText(t("research.exec.parkedResume"))).toBeTruthy();
    expect(screen.queryByRole("button", { name: t("research.exec.resume") })).toBeNull();
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
    // The run's lift (CR-3): one path for the run, never one per step.
    const BUDGET_PATH = "/api/v1/studies/STU-1/research/runs/RUN-1/budget";
    const waiting = () => parkedWith([
      step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
      step("analysis_executive", "AWAITING_BUDGET", { kind: "research_analysis", waiting_reason: "budget_exceeded" }),
    ]);

    it("offers one lift for the run when eight analysis steps wait, and one post releases them all (CR-3)", async () => {
      const modules = ["executive", "segments", "drivers", "attitudes", "brand", "price", "risks", "recommendations"];
      const many = parkedWith([
        step("compile", "SUCCEEDED", { artifact_id: "ART-1" }),
        ...modules.map((m) => step(`analysis_${m}`, "AWAITING_BUDGET", { kind: "research_analysis", waiting_reason: "budget_exceeded" })),
      ]);
      const resumed = run({ steps: [step("compile", "SUCCEEDED"), ...modules.map((m) => step(`analysis_${m}`, "RUNNABLE"))] });
      let lifted = false;
      api({
        ...listed(many),
        "GET /api/v1/studies/STU-1/research/runs/RUN-1": () => (lifted ? resumed : many),
        "GET /api/v1/studies/STU-1": () => STUDY,
        [`POST ${BUDGET_PATH}`]: () => { lifted = true; return resumed; },
      });
      render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
      const section = await screen.findByRole("status", { name: t("research.exec.budget.runTitle") });
      expect(within(section).getByText(/Čekající kroky \(8\)/)).toBeTruthy();
      // One form on the page, whatever the number of waiting steps.
      await waitFor(() => expect(screen.getAllByRole("form", { name: t("research.exec.budget.title") })).toHaveLength(1));
      const form = screen.getByRole("form", { name: t("research.exec.budget.title") });
      await within(form).findByText(/10\.00/);
      // The remainder leaves out open holds, and says so.
      expect(within(form).getByText(t("research.exec.budgetLine.holdsNotCounted"))).toBeTruthy();
      fireEvent.change(within(form).getByLabelText(t("research.exec.budget.amount")), { target: { value: "30" } });
      fireEvent.click(within(form).getByRole("button", { name: t("research.exec.budget.lift") }));
      await waitFor(() => expect(called("POST", BUDGET_PATH)).toHaveLength(1));
      expect(called("POST", BUDGET_PATH)[0].body).toEqual({ budget_usd: 30, note: "" });
      expect(calls.filter((c) => c.method === "POST" && /\/steps\/.+\/budget$/.test(c.url))).toEqual([]);
      await waitFor(() => expect(screen.queryByRole("form", { name: t("research.exec.budget.title") })).toBeNull());
    });

    it("offers to raise the budget, showing what is spent, and posts the new total for the run", async () => {
      const resumed = run({ steps: [step("compile", "SUCCEEDED"), step("analysis_executive", "RUNNABLE")] });
      // As the API does: once lifted, the run reads resumed (the page reads it again after an action).
      let lifted = false;
      api({
        ...listed(waiting()),
        "GET /api/v1/studies/STU-1/research/runs/RUN-1": () => (lifted ? resumed : waiting()),
        "GET /api/v1/studies/STU-1": () => STUDY,
        [`POST ${BUDGET_PATH}`]: () => { lifted = true; return resumed; },
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

    it("says what remains beside the budget, and never reads a spend the API did not report as zero (6d)", async () => {
      api({ ...listed(waiting()), "GET /api/v1/studies/STU-1": () => STUDY });
      render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
      const form = await screen.findByRole("form", { name: t("research.exec.budget.title") });
      expect(await within(form).findByText("Rozpočet 10.00 USD, vyčerpáno 9.50 USD. Z rozpočtu studie zbývá 0.50 USD.")).toBeTruthy();
      cleanup();
      api({ ...listed(waiting()), "GET /api/v1/studies/STU-1": () => ({ ...STUDY, spent_usd: null, remaining_usd: null }) });
      render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
      const unread = await screen.findByRole("form", { name: t("research.exec.budget.title") });
      expect(await within(unread).findByText("Rozpočet 10.00 USD; kolik je vyčerpáno, AIA nyní neví. Kolik z rozpočtu studie zbývá, AIA nyní neví.")).toBeTruthy();
      expect(within(unread).queryByText(/vyčerpáno 0\.00/)).toBeNull();
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

  it("follows the run a retry starts and keeps reading it, so its steps move on screen", async () => {
    // The bug: the retry's run replaced the page's run, but the poll had stopped with the old,
    // finished run, so the new run's first step read "running" until the page was reloaded --
    // and a reload went back to the old run, which ?run= still named.
    window.history.replaceState(null, "", "/progress?run=RUN-1");
    const failed = run({ status: "FAILED", phase: "FAILED", is_terminal: true, retryable: true,
      steps: [step("compile", "SUCCEEDED"), step("run", "FAILED", { error_message: "boom" })] });
    let reads = 0;
    const retried = (phase: string, compile: string) => run({ run_id: "RUN-2", retry_of: "RUN-1", phase, status: phase, is_terminal: phase === "COMPLETED", steps: [step("compile", compile)] });
    api({
      ...listed(failed),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/retry": () => retried("RUNNING", "RUNNING"),
      "GET /api/v1/studies/STU-1/research/runs/RUN-2": () => (++reads < 2 ? retried("RUNNING", "RUNNING") : retried("COMPLETED", "SUCCEEDED")),
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.retry") }));
    expect(await screen.findByText("Opakování běhu RUN-1")).toBeTruthy();
    // The page is now about the new run, a reload included.
    expect(window.location.search).toBe("?run=RUN-2");
    // And it keeps reading it: the first step finishes on screen without a reload.
    await waitFor(() => expect(document.querySelector('[data-step="compile"]')?.getAttribute("data-status")).toBe("SUCCEEDED"));
    expect(reads).toBeGreaterThanOrEqual(2);
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1").filter((c) => !c.url.includes("/runs/RUN-1/"))).toHaveLength(1);
  }, 10000);

  it("cancels only after the person confirms, and retries a failed run as a new run", async () => {
    let cancelled = false;
    api({
      ...listed(PARKED),
      // As the API does: a cancelled run reads cancelled, and the retry's run is served.
      "GET /api/v1/studies/STU-1/research/runs/RUN-1": () => (cancelled ? { ...PARKED, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true } : PARKED),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/cancel": () => { cancelled = true; return { ...PARKED, phase: "CANCELLED", status: "CANCELLED", is_terminal: true, retryable: true }; },
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/retry": () => run({ run_id: "RUN-2", retry_of: "RUN-1", phase: "QUEUED" }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-2": () => run({ run_id: "RUN-2", retry_of: "RUN-1", phase: "QUEUED" }),
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
  it("shows who answered without the receipt's Lead mark: Výsledky's row names measures alone (#618)", async () => {
    api({ ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const card = (await screen.findByRole("heading", { name: t("research.exec.respondents.receipt.title") })).closest("section") as HTMLElement;
    expect(card.closest("[data-aia]")).toBeNull();
    expect(document.querySelector('[data-aia^="receipt:"]')).toBeNull();
  });

  it("explains a failed run load and retries instead of leaving Results loading forever", async () => {
    let failed = true;
    api({ ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs": () => failed
        ? new Response(JSON.stringify({ code: "service_unavailable", message: "Výsledky se nepodařilo načíst." }), { status: 503 })
        : { items: [COMPLETED] },
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Výsledky se nepodařilo načíst.")).toBeTruthy();
    failed = false;
    fireEvent.click(screen.getByRole("button", { name: t("research.retry") }));
    expect(await screen.findByRole("tab", { name: "Přehled" })).toBeTruthy();
  });

  it("clears a failed load when the retry finds no run (404)", async () => {
    let failed = true;
    api({ ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs": () => failed
        ? new Response(JSON.stringify({ code: "service_unavailable", message: "Výsledky se nepodařilo načíst." }), { status: 503 })
        : new Response(JSON.stringify({ code: "not_found", message: "Nenalezeno." }), { status: 404 }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByText("Výsledky se nepodařilo načíst.")).toBeTruthy();
    failed = false;
    fireEvent.click(screen.getByRole("button", { name: t("research.retry") }));
    expect(await screen.findByText(t("research.exec.noResults"))).toBeTruthy();
    expect(screen.queryByText("Výsledky se nepodařilo načíst.")).toBeNull();
    // With no run, the stage that starts one (workbench audit F-R8).
    expect(screen.getByRole("link", { name: tv("research.exec.answerability.retryOpen", { stage: t("aia.stages.run") }) }).getAttribute("href")).toBe(TEST_FRAME.stepHref("run"));
    // No run, so no word about "this run's" report (workbench audit, 2026-10-22).
    expect(screen.queryByText(t("research.exec.results.reportNotInAia"))).toBeNull();
  });

  it("keeps the neutral analysis note while no module has stored an outcome, never 'unknown origin'", async () => {
    const pending = run({
      status: "WAITING_PROVIDER", phase: "WAITING", fieldwork_source: "ai_runtime",
      steps: [
        step("aggregate", "SUCCEEDED", { artifact_id: "ART-4", data_origin: "MODELLED_AI_PANEL" }),
        step("analysis_executive", "WAITING_PROVIDER", { kind: "research_analysis" }),
      ],
    });
    api({
      ...listed(pending),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({
        run_id: "RUN-1", complete: false, internal_only: true, synthetic: false, modelled: false,
        data_origin_kind: null, pending: { executive: "WAITING_PROVIDER" }, modules: {},
      }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    expect(await screen.findByText(t("research.exec.results.analysisInternal"))).toBeTruthy();
    expect(screen.queryByText(t("research.exec.results.analysisUnknownOrigin"))).toBeNull();
  });

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
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    expect(await screen.findByText("Ověřené shrnutí.")).toBeTruthy();
    expect(screen.getByText(/C1 → q1.mean/)).toBeTruthy();
    expect(screen.getByText(/Interní analýza fiktivních respondentů/)).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "AI analýza" }));
    fireEvent.click(screen.getByRole("button", { name: /Omezení.*Čeká/ }));
    expect(screen.getByText("Stav kroku: Čeká")).toBeTruthy();
    expect(document.querySelector("[data-aggregate-deviation]")).toBeNull(); // the unit's port
  });

  it("shows artifact outcomes rather than workflow completion and hides validation codes in details", async () => {
    const partial = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-6" }),
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-7" }),
    ] });
    api({ ...listed(partial),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, synthetic: true, pending: {}, modules: {
        executive: { outcome: "COMPLETED", summary: "Přijaté shrnutí.", research_question_answers: [], key_findings: [], claims: [], violations: [] },
        research_questions: { outcome: "BLOCKED", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [{ code: "SCHEMA_INVALID", subject: "research_question_answers", detail: "Input should be a valid array" }] },
      } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    expect(await screen.findByText("1 z 8 částí analýzy dokončeno · k opravě: 1")).toBeTruthy();
    const blocked = screen.getByRole("button", { name: /Výzkumné otázky.*Potřebuje opravu/ });
    fireEvent.click(blocked);
    expect(screen.getByText(/Výstup této části neprošel kontrolou/)).toBeTruthy();
    // The refusal in words on the surface; its code, subject and detail only in a closed fold.
    const pane = screen.getByRole("region", { name: "Výzkumné otázky" });
    expect(within(pane).getByText(/odpověď modelu neodpovídala předepsanému tvaru/)).toBeTruthy();
    const diagnostic = within(pane).getByText("Technické podrobnosti").closest("details");
    expect(diagnostic?.open).toBe(false);
    expect(diagnostic?.textContent).toContain("research_question_answers: Input should be a valid array");
    expect(pane.textContent?.replace(diagnostic?.textContent ?? "", "")).not.toContain("SCHEMA_INVALID");
  });

  it("says an analysis an earlier version of AIA built cannot be shown, and where it is repaired, not 'try again' (PC3)", async () => {
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-6", analysis_outcome: "COMPLETED" }),
    ] });
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => new Response(JSON.stringify({
        code: "fingerprint_mismatch", message: "the evidence, policy, method status or harness no longer match this outcome", details: {},
      }), { status: 409 }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    expect(await screen.findByText(t("research.exec.results.analysisStale"))).toBeTruthy();
    const repair = screen.getByRole("link", { name: t("research.exec.results.analysisStaleRepair") });
    expect(repair.getAttribute("href")).toContain("?run=RUN-1");
    expect(screen.queryByText(/harness no longer match/)).toBeNull();
  });

  it("marks an answer to a research question the run recorded as a gap, as the report does (PC2)", async () => {
    const words = "běh na ni odpovědět nemohl (měří ji jen otázky, na které běh neodpoví)";
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-6", analysis_outcome: "COMPLETED" }),
    ] });
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, synthetic: true, pending: {}, modules: {
        executive: { outcome: "COMPLETED", summary: null, key_findings: [], claims: [], violations: [], research_question_answers: [
          { question: "Kdo pije kávu?", answer: "Hlavně ráno.", claim_ids: [], gap: words },
          { question: "Co lidé pijí?", answer: "Čaj a kávu.", claim_ids: [], gap: null },
        ] },
      } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const marked = await screen.findByText(tv("research.exec.results.answerGap", { words }));
    expect(marked.closest("div")?.textContent).toContain("Kdo pije kávu?");
    expect(document.querySelectorAll("[data-answer-gap]")).toHaveLength(1);
  });

  it("covers every research question of the frozen design: its answer, the findings on the same measures, what is missing (ANL2)", async () => {
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-7", analysis_outcome: "COMPLETED" }),
    ], answerability: { ready: true, gaps: [{ kind: "not_answerable", research_question: "Proč  měníte banku?", verdict: "UNANSWERABLE", reasons: [], measures: [] }] } as unknown as ResearchRun["answerability"] });
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/design/revisions/REV-a1": () => ({ revision_id: "REV-a1", content: { research_plan: { research_questions: ["Co lidé pijí?", "Proč měníte banku?", "Kdo pije čaj?"] } } }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, synthetic: true, pending: {}, modules: {
        research_questions: { outcome: "COMPLETED", summary: null, violations: [],
          research_question_answers: [{ question: "Co lidé pijí?", answer: "Čaj.", claim_ids: ["C1"] }, { question: "Proč měníte banku?", answer: "Nevíme.", claim_ids: [] }, { question: "Kdo pije čaj?", answer: "Mnozí.", claim_ids: [] }],
          key_findings: [{ text: "Čaj vede.", claim_ids: ["C1"] }],
          claims: [{ claim_id: "C1", evidence_ref: "q2.pct.2", value: 38.4, indicative: false, data_origin: null }] },
      } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const table = await screen.findByRole("region", { name: "Pokrytí výzkumných otázek" });
    await waitFor(() => expect(table.querySelectorAll("tr[data-rq]")).toHaveLength(3));
    const rows = [...table.querySelectorAll("tr[data-rq]")];
    expect(rows.map((r) => [r.getAttribute("data-rq"), r.getAttribute("data-state")])).toEqual([["0", "answered"], ["1", "gap"], ["2", "unsupported"]]);
    // The Lead points at the module (rq:<id> waits for stable research-question ids, WCE1).
    expect(table.getAttribute("data-aia")).toBe("module:research_questions");
    // The recorded gap reads "bez doložené odpovědi", with what the run recorded; never "ano".
    expect(rows[1].textContent).toContain("bez doložené odpovědi");
    expect(rows[1].textContent).toContain("Při spuštění běh zaznamenal");
    // A finding on the same measure is linked to where it is shown, and carries its Lead target.
    expect(rows[0].querySelector("[data-finding-chip]")?.getAttribute("data-finding-chip")).toBe("research_questions:0");
    expect(document.getElementById("analysis-finding-research_questions-0")?.getAttribute("data-aia")).toBe("finding:research_questions:0");
    expect(rows[2].textContent).toContain("Odpověď necituje žádné připuštěné číslo.");
    // The run's fieldwork step ("run") succeeded: Sběr dokončen, never "čeká" (ANL8 audit, F1).
    const milestones = [...document.querySelectorAll("[data-analysis-milestones] li")];
    expect(milestones[0].textContent).toContain("Sběr dokončen");
    expect(milestones[0].getAttribute("data-done")).toBe("true");
    // A finding chip brings the finding into view without a hash: a hash naming no view sends the
    // workspace back to Přehled (ANL8 audit, F4).
    const before = window.location.hash;
    const finding = document.getElementById("analysis-finding-research_questions-0") as HTMLElement;
    finding.scrollIntoView = () => {};
    fireEvent.click(within(rows[0] as HTMLElement).getByRole("button", { name: /1$/ }));
    expect(window.location.hash).toBe(before);
    expect(document.activeElement).toBe(finding);
  });

  it("opens a finding and a cited number in the workbench's inspector, from the coverage, the finding and its chip (ANL3)", async () => {
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-7", analysis_outcome: "COMPLETED" }),
    ] });
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/design/revisions/REV-a1": () => ({ revision_id: "REV-a1", content: { research_plan: { research_questions: ["Co lidé pijí?"] } } }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, synthetic: true, pending: {}, modules: {
        research_questions: { outcome: "COMPLETED", summary: null, violations: [],
          research_question_answers: [{ question: "Co lidé pijí?", answer: "Čaj.", claim_ids: ["C1"] }],
          key_findings: [{ text: "Čaj vede.", claim_ids: ["C1"] }],
          claims: [{ claim_id: "C1", evidence_ref: "q2.pct.2", value: 38.4, indicative: false, data_origin: null }] },
      } }),
    });
    const opened: string[] = [];
    const inspector = { open: (entry: { id: string }) => { opened.push(entry.id); return true; }, closeWhere: () => {} };
    render(<ItemInspectorContext.Provider value={inspector}><ResearchScreen step="results" frame={TEST_FRAME} /></ItemInspectorContext.Provider>);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const table = await screen.findByRole("region", { name: "Pokrytí výzkumných otázek" });
    const chip = await within(table).findByRole("button", { name: /1$/ });
    const before = document.activeElement;
    fireEvent.click(chip);
    // The drawer takes it: the page neither scrolls nor moves focus to the finding.
    expect(document.activeElement).toBe(before);
    const keyFindings = screen.getByRole("region", { name: "Hlavní zjištění" });
    fireEvent.click(within(keyFindings).getByRole("button", { name: /^Otevřít .*zjištění 1 v inspektoru$/ }));
    const number = keyFindings.querySelector("[data-inspect-claim]") as HTMLElement;
    expect(number.tagName).toBe("BUTTON");
    fireEvent.click(number);
    expect(opened).toEqual(["finding:research_questions:0", "finding:research_questions:0", "claim:research_questions:C1"]);
    // The Lead's targets stay where they were: one element each.
    expect(document.querySelectorAll('[data-aia="claim:research_questions:C1"]')).toHaveLength(1);
    expect(document.querySelectorAll('[data-aia="finding:research_questions:0"]')).toHaveLength(1);
    // A run that pinned no Design Research shows no register (ANL5).
    expect(screen.queryByRole("region", { name: "Externí kontext" })).toBeNull();
  });

  it("lists the Design Research the modules were shown as Externí kontext, with its sources and no claim chip (ANL5)", async () => {
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-6", analysis_outcome: "COMPLETED" }),
    ] });
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, synthetic: true, pending: {},
        external_context: { deep_research_run_id: "DR-1", items: [
          { evidence_id: "EV-1", claim: "Spotřeba rostlinných nápojů vzrostla o 12,5 %.", source: "https://www.stat.example/napoje" },
          { evidence_id: "EV-2", claim: "Ze znalostí klienta.", source: "javascript:alert(1)" },
        ] },
        modules: { executive: { outcome: "COMPLETED", summary: null, violations: [], research_question_answers: [], key_findings: [{ text: "Čaj vede.", claim_ids: [] }], claims: [] } } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const register = await screen.findByRole("region", { name: "Externí kontext" });
    const items = register.querySelectorAll("[data-external-item]");
    expect(items).toHaveLength(2);
    expect(items[0].textContent).toContain("Spotřeba rostlinných nápojů vzrostla o 12,5 %.");
    expect(within(items[0] as HTMLElement).getByText("Externí kontext")).toBeTruthy();
    // A source links only as an http(s) address; anything else stays text.
    const link = within(items[0] as HTMLElement).getByRole("link", { name: "stat.example" });
    expect(link.getAttribute("href")).toBe("https://www.stat.example/napoje");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
    expect(within(items[1] as HTMLElement).queryByRole("link")).toBeNull();
    // Context is never evidence: no claim chip and no Lead target in the register.
    expect(register.querySelector("[data-cited-number], [data-aia]")).toBeNull();
  });

  it("says the research questions are unknown when the frozen design cannot be read, never that it has none (ANL2)", async () => {
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-7", analysis_outcome: "BLOCKED" }),
    ] });
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/design/revisions/REV-a1": () => { throw new Error("neznámá revize"); },
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, synthetic: true, pending: {}, modules: {
        research_questions: { outcome: "BLOCKED", summary: null, violations: [{ code: "x", subject: "y", detail: "z" }], research_question_answers: [], key_findings: [], claims: [] },
      } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const section = await screen.findByRole("region", { name: "Pokrytí výzkumných otázek" });
    await waitFor(() => expect(section.querySelector("[data-coverage-read]")?.getAttribute("data-coverage-read")).toBe("failed"));
    expect(section.textContent).toContain("Výzkumné otázky běhu jsou neznámé");
    expect(section.textContent).not.toContain("neuvádí výzkumné otázky");
    expect(section.querySelectorAll("tr[data-rq]")).toHaveLength(0);
  });

  it("reads a failed retryable read as unknown, and words a suppression by every cause it has (ANL4)", async () => {
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_audience", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-8", analysis_outcome: "BLOCKED" }),
    ] });
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, synthetic: true, pending: {}, modules: {
        // Every row removed because its question was refused for fidelity, not for thin support.
        audience: { outcome: "BLOCKED", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [
          { code: "SUPPORT_SUPPRESSED", subject: "preflight", detail: "no citable evidence: all 4 rows were removed (thin support, a refused question, or an estimate without its interval)" },
        ] },
      } }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis/retryable": () => { throw new Error("409 conflict"); },
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const blocked = await screen.findByRole("region", { name: "Blokované nároky" });
    const audience = blocked.querySelector('[data-blocked-module="audience"]') as HTMLElement;
    // A list that could not be read promises nothing: never "the same data would refuse it again".
    await waitFor(() => expect(audience.getAttribute("data-way-out")).toBe("unknown"));
    expect(audience.textContent).not.toContain("neopraví");
    // The words name every cause the preflight groups under one code, not "too few respondents" alone.
    expect(audience.textContent).toContain("odmítnutá otázka");
    expect(audience.textContent).not.toContain("příliš málo respondentů");
  });

  it("names each blocked module's refusals in words with the way out the server gives, and never reads it as done (ANL4)", async () => {
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-6", analysis_outcome: "COMPLETED" }),
      step("analysis_audience", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-8", analysis_outcome: "BLOCKED" }),
      step("analysis_hypotheses", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-9", analysis_outcome: "BLOCKED" }),
    ] });
    const blockedAnalysis = () => ({ complete: false, synthetic: true, pending: {}, modules: {
      executive: { outcome: "COMPLETED", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [] },
      // Refused by the preflight before any model turn: the server does not list it as retryable.
      audience: { outcome: "BLOCKED", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [
        { code: "JOINT_CERTIFICATE_DEGRADED", subject: "core", detail: "certificate degraded" },
      ] },
      hypotheses: { outcome: "BLOCKED", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [
        { code: "EVIDENCE_REF_UNKNOWN", subject: "c1", detail: "q9.mean" },
        { code: "EVIDENCE_REF_UNKNOWN", subject: "c2", detail: "q7.mean" },
        { code: "NOT_A_KNOWN_CODE", subject: "summary", detail: "x" },
      ] },
    } });
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": blockedAnalysis,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis/retryable": () => ({ run_id: "RUN-1", modules: ["hypotheses"] }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const blocked = await screen.findByRole("region", { name: "Blokované nároky" });
    const hypotheses = blocked.querySelector('[data-blocked-module="hypotheses"]') as HTMLElement;
    expect(hypotheses.textContent).toContain("Potřebuje opravu");
    // Each reason once, in words, counted; each subject beside its own detail; a code without words keeps its code.
    expect(hypotheses.querySelectorAll("[data-violation]")).toHaveLength(2);
    expect(within(hypotheses).getByText(/cituje číslo, které v datech běhu není/)).toBeTruthy();
    expect(hypotheses.textContent).toContain("(2×)");
    expect([...hypotheses.querySelectorAll('[data-violation="EVIDENCE_REF_UNKNOWN"] details li')].map((li) => li.textContent)).toEqual(["c1: q9.mean", "c2: q7.mean"]);
    expect(hypotheses.textContent).toContain("NOT_A_KNOWN_CODE");
    expect(blocked.querySelector('[data-blocked-module="executive"]')).toBeNull();
    // The way out is the server's: a retry only for what it lists; the preflight's refusal is said not to pass again.
    await waitFor(() => expect(hypotheses.getAttribute("data-way-out")).toBe("retry"));
    expect(blocked.querySelector('[data-blocked-module="audience"]')?.getAttribute("data-way-out")).toBe("same_data_fails");
    expect(within(blocked).getByRole("link", { name: "Zobrazit průběh běhu" })).toBeTruthy();
    // The module list never says it is done, and its pane words the refusals the same way.
    const entry = screen.getByRole("button", { name: /Hypotézy/ });
    expect(entry.textContent).toContain("Potřebuje opravu");
    expect(entry.textContent).not.toMatch(/Dokončeno|Hotovo/);
    fireEvent.click(entry);
    const pane = screen.getByRole("region", { name: "Hypotézy" });
    expect(within(pane).getByText(/cituje číslo, které v datech běhu není/)).toBeTruthy();
    expect(pane.textContent).not.toMatch(/EVIDENCE_REF_UNKNOWN:/);
    cleanup();
    // On a frame that may not edit, nothing offers a round the reader cannot ask for.
    render(<ResearchScreen step="results" frame={{ ...TEST_FRAME, canEdit: false }} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const readOnly = await screen.findByRole("region", { name: "Blokované nároky" });
    expect(readOnly.querySelector("[data-way-out]")).toBeNull();
    expect(within(readOnly).queryByRole("link")).toBeNull();
  });

  it("puts every module's key findings first, each with the numbers it cites, and keeps every word formatted", async () => {
    const analysed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-6" }),
      step("analysis_objects", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-8" }),
      step("analysis_audience", "WAITING_PROVIDER", { kind: "research_analysis" }),
    ] });
    const specification = { ...AGGREGATE, artifact_id: "ART-1", artifact_type: "research_specification",
      payload: { specification: { n: 200, questions: [{ id: "q2", text: "Který nápoj byste si vybrali?", typ: "vyber", options: ["Kávu", "Čaj"] }], batteries: [] } } };
    api({ ...listed(analysed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-1": () => specification,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, synthetic: true, pending: { audience: "WAITING_PROVIDER" }, modules: {
        executive: { outcome: "COMPLETED", summary: "Úvodní odstavec.\n\n- první bod\n- druhý bod", research_question_answers: [{ question: "Co lidé pijí?", answer: "Hlavně čaj a kávu.", claim_ids: ["C2"] }],
          key_findings: [{ text: "Čaj a káva jsou **vyrovnané**.", claim_ids: ["C1", "C2", "C9", "C3"] }],
          claims: [{ claim_id: "C1", evidence_ref: "q2.pct.2", value: 38.4, indicative: false, data_origin: null }, { claim_id: "C2", evidence_ref: "q2.pct.1", value: 34.8, indicative: true, data_origin: null }, { claim_id: "C3", evidence_ref: "x9.median", value: 4, indicative: false, data_origin: null }], violations: [] },
        objects: { outcome: "COMPLETED", summary: null, research_question_answers: [], key_findings: [{ text: "Bez čísel.", claim_ids: [] }, { text: "Jen neuložená čísla.", claim_ids: ["C7"] }], claims: [], violations: [] },
      } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "AI analýza" }));
    const keyFindings = await screen.findByRole("region", { name: "Hlavní zjištění" });
    // Both modules' findings, under their module, before the module-by-module view.
    expect(within(keyFindings).getByText("Shrnutí analýzy")).toBeTruthy();
    expect(within(keyFindings).getByText("Srovnání objektů")).toBeTruthy();
    expect(within(keyFindings).getByText("Bez čísel.")).toBeTruthy();
    expect(within(keyFindings).getByText("vyrovnané").tagName).toBe("STRONG");
    // Each cited number: value, what, which question, a link to its card; C9 is not a claim and is left out.
    const cited = within(keyFindings).getAllByRole("link");
    expect(cited.map((a) => a.textContent)).toEqual([
      "38,4 % podíl odpovědi „Čaj“ · Který nápoj byste si vybrali?",
      "34,8 % podíl odpovědi „Kávu“ · Který nápoj byste si vybrali?",
    ]);
    expect(cited[0].getAttribute("href")).toBe("#measure-q2");
    // Each cited number and the module view carry the Lead's targets (ANL1).
    expect(keyFindings.querySelector('[data-aia="claim:executive:C1"]')).toBeTruthy();
    expect(keyFindings.querySelector('[data-aia="finding:executive:0"]')).toBeTruthy();
    // Every module is a Lead target whichever is selected (Codex P1 on #605), and every target names
    // exactly one element: research_questions is the coverage table, each claim its first chip.
    for (const m of ["executive", "research_questions", "objects", "audience", "segments", "hypotheses", "implications", "limitations"]) {
      expect(document.querySelectorAll(`[data-aia="module:${m}"]`)).toHaveLength(1);
    }
    for (const c of ["C1", "C2", "C3"]) expect(document.querySelectorAll(`[data-aia="claim:executive:${c}"]`)).toHaveLength(1);
    expect(keyFindings.querySelector('[data-aia="claim:executive:C2"]')).toBeTruthy();
    // The inspector reads this very analysis, published by the page (ANL3), and adds no target of
    // its own: with the drawer open, every target still names exactly one element.
    const drawer = render(<AnalysisInspect target={{ kind: "finding", id: "executive:0" }} />);
    expect(within(drawer.container).getAllByRole("link")[0].getAttribute("href")).toBe("#measure-q2");
    expect(drawer.container.querySelector("[data-aia]")).toBeNull();
    for (const c of ["C1", "C2", "C3"]) expect(document.querySelectorAll(`[data-aia="claim:executive:${c}"]`)).toHaveLength(1);
    drawer.unmount();
    // A finding that cites no admitted number is never said to rest on one (review of #692).
    // Neither does one that cites only ids the module did not store.
    for (const id of ["objects:0", "objects:1"]) {
      const bare = render(<AnalysisInspect target={{ kind: "finding", id }} />);
      expect(bare.container.textContent).not.toContain("z připuštěných čísel");
      expect(bare.container.textContent).toContain("neopírá se o žádné připuštěné číslo");
      bare.unmount();
    }
    // A number whose question AIA cannot find says so in words; its reference stays as a code (6c).
    expect(within(keyFindings).getByText(/číslo, k němuž AIA nedohledala otázku/)).toBeTruthy();
    expect(within(keyFindings).getByText("x9.median").tagName).toBe("CODE");
    expect(within(keyFindings).getByText(/· orientační/)).toBeTruthy();
    expect(keyFindings.compareDocumentPosition(screen.getByText("Analýza po částech")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The module's own text, formatted: its summary's list, its answer with the number it cites.
    const items = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toContain("první bod");
    expect(items).toContain("druhý bod");
    const answer = screen.getByText("Co lidé pijí?").parentElement as HTMLElement;
    expect(within(answer).getByText("Hlavně čaj a kávu.")).toBeTruthy();
    expect(within(answer).getByRole("link").textContent).toBe("34,8 % podíl odpovědi „Kávu“ · Který nápoj byste si vybrali?");
    // A pending module keeps its reason, in words (6b), never the stored status.
    fireEvent.click(screen.getByRole("button", { name: /Cílová skupina.*Čeká/ }));
    expect(screen.getByText("Stav kroku: Čeká")).toBeTruthy();
    expect(screen.queryByText(/WAITING_PROVIDER/)).toBeNull();
  });

  it("says on the analysis when the aggregate it read is no longer 18.6.6's port (G3c)", async () => {
    const partial = run({
      status: "WAITING_PROVIDER", phase: "WAITING", fieldwork_source: "synthetic_fixture",
      steps: [
        step("aggregate", "SUCCEEDED", { artifact_id: "ART-4", data_origin: "SYNTHETIC_FIXTURE" }),
        step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-6" }),
      ],
    });
    api({
      ...listed(partial),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({
        run_id: "RUN-1", complete: false, internal_only: true, synthetic: true, pending: {},
        aggregation_deviation: {
          from: "aia-aggregate-1", methodology_version: "aia-aggregate-1+e1",
          changed: [{ path: "top_box", unit: 2, used: 1 }], replaced_formulas: ["agg.kish"], note_cs: "…",
        },
        modules: { executive: { outcome: "COMPLETED", artifact_id: "ART-6",
          summary: "Ověřené shrnutí.", research_question_answers: [], key_findings: [], claims: [], violations: [] } },
      }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    await screen.findByText("Ověřené shrnutí.");
    const note = await waitFor(() => {
      const found = document.querySelector("[data-aggregate-deviation]");
      if (!found) throw new Error("the deviation note is not shown yet");
      return found as HTMLElement;
    });
    expect(within(note).getByText("Odchylka od 18.6.6")).toBeTruthy();
    expect(within(note).getByText("top_box: 2 v 18.6.6, zde 1")).toBeTruthy();
    expect(within(note).getByText("Nahrazený vzorec: agg.kish")).toBeTruthy();
  });

  it("says beside a number the analysis and report never cite that they do not, from the rating the aggregate stored (PC2)", async () => {
    const reason = "Absolutní WTP/velikost trhu není validovaný claim.";
    const rated = { ...AGGREGATE, payload: { aggregate: { ...AGGREGATE.payload.aggregate, questions: {
      q2: { ...AGGREGATE.payload.aggregate.questions.q2, evidence: { rating: "RED", mode: "REFUSE", question_type: "absolute_value", reason } },
      t1: { ...AGGREGATE.payload.aggregate.questions.t1, evidence: { rating: "AMBER", mode: "JUST_SHOW", question_type: "rating_scale", reason: "Bez holdoutu." } },
    } } } };
    api({ ...listed(COMPLETED), "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => rated });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    const q2 = await findMeasure("q2");
    expect(within(q2).getByText(tv("research.exec.results.fidelityRefused", { reason }))).toBeTruthy();
    const t1 = await findMeasure("t1");
    expect(t1.querySelector("[data-fidelity-refused]")).toBeNull();
  });

  it("says why a run has no Sociomap, from the note it stored, and explains no map that is not there (PC17)", async () => {
    const note = "Návrh nemá sledovanou sadu; Sociomapa nevznikla.";
    const none = { ...SOCIOMAP, payload: { sociomap: { methodology_status: "INTERNAL_ONLY", batteries: [], note } } };
    api({
      ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => none,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Sociomapy" }));
    expect(await screen.findByText(note)).toBeTruthy();
    expect(screen.queryByText(t("research.exec.results.mapToolNotInAia"))).toBeNull();
    expect(screen.queryByText(t("research.exec.results.mapsByMethod"))).toBeNull();
  });

  it("draws a new run's aia-sociomap-5 map with no reference comparison beside it", async () => {
    const battery = signedOffFixture.batteries[0];
    const methodId = Object.keys(battery.maps)[0];
    const signedOff = { ...SOCIOMAP, payload: { sociomap: {
      methodology_status: "CLIENT_FACING", data_origin: "SYNTHETIC_FIXTURE",
      methods: [{ method_id: methodId, spec_fingerprint: (battery.maps as Record<string, { spec_fingerprint: string }>)[methodId].spec_fingerprint }],
      batteries: [{ ...battery, methodology_status: "CLIENT_FACING" }],
    } } };
    api({
      ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => signedOff,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Sociomapy" }));
    const [map] = await screen.findAllByRole("region", { name: battery.title });
    expect(map.querySelector(`[data-testid="object-map-${battery.battery_id}"]`)).not.toBeNull();
    expect(within(map).queryByText(t("research.exec.results.olderMethod"))).toBeNull();
    // No reference map was computed, so no comparison with one is offered.
    expect(within(map).queryByText(t("research.exec.objectMap.comparison"))).toBeNull();
  });

  describe("the workbench's Sociomapa stage (artifact-sociomap SOC9-SOC11)", () => {
    const battery = signedOffFixture.batteries[0];
    const methodId = Object.keys(battery.maps)[0];
    const signedOff = { ...SOCIOMAP, payload: { sociomap: {
      methodology_status: "CLIENT_FACING", data_origin: "SYNTHETIC_FIXTURE",
      methods: [{ method_id: methodId, spec_fingerprint: (battery.maps as Record<string, { spec_fingerprint: string }>)[methodId].spec_fingerprint }],
      batteries: [battery],
    } } };
    // A run that also made the experimental Sociomapping (its own step and artifact).
    const MAPPED = run({ ...COMPLETED, steps: [...(COMPLETED.steps as ReturnType<typeof step>[]), step("sociomapping", "SUCCEEDED", { artifact_id: "ART-6", data_origin: "SYNTHETIC_FIXTURE" })] });
    const SOCIOMAPPING = { ...SOCIOMAP, artifact_id: "ART-6", artifact_type: "research_sociomapping", payload: sociomappingFixture };
    const open = (artifact: unknown, workbench: boolean, hash = "#maps", runs = COMPLETED) => {
      layout.workbench = workbench;
      window.history.replaceState(null, "", `${window.location.pathname}${hash}`);
      onTestFinished(() => { layout.workbench = null; window.history.replaceState(null, "", window.location.pathname); });
      api({
        ...listed(runs),
        "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
        "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => artifact,
        "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-6": () => SOCIOMAPPING,
      });
      return render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    };

    it("is the map: no results tabs, no guide, no other card, the map before what explains it", async () => {
      open(signedOff, true);
      const stage = await screen.findByTestId("sociomap-stage");
      await waitFor(() => expect(within(stage).getByTestId("object-map-stage")).toBeTruthy());
      expect(screen.queryByRole("tablist", { name: "Oddíly výsledků" })).toBeNull();
      expect(screen.queryByText("Jak používat mapu a AI pomoc")).toBeNull();
      expect(screen.queryByText(t("research.exec.results.mapsByMethod"))).toBeNull();
      expect(screen.queryByText(t("research.exec.results.mapToolNotInAia"))).toBeNull();
      expect(document.getElementById("res-sociomap")).toBeNull();
      // The run's origin is still said above it: fictional data is labelled every time.
      expect(screen.getByText(/Fiktivní data\. Tento běh používá smyšlené respondenty/)).toBeTruthy();
      // The map first, then the sections in their order, the method folded last.
      const map = within(stage).getByTestId("object-map-stage");
      const explained = within(stage).getByTestId("map-explained");
      expect(map.compareDocumentPosition(explained) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect([...explained.querySelectorAll("[data-map-section]")].map((n) => n.getAttribute("data-map-section")))
        .toEqual(["what", "rel", "obj", "resp", "rely", "how"].map((k) => `${battery.battery_id}-${k}`));
      expect((explained.querySelector("details.fx-how") as HTMLDetailsElement).open).toBe(false);
    });

    it("says it in plain words: no artifact, run or method id outside Technické údaje", async () => {
      open(signedOff, true);
      const stage = await screen.findByTestId("sociomap-stage");
      await within(stage).findByTestId("map-explained");
      const tech = within(stage).getByTestId("map-tech");
      const outside = stage.cloneNode(true) as HTMLElement;
      outside.querySelector('[data-testid="map-tech"]')!.remove();
      for (const code of ["ART-5", "RUN-1", SOCIOMAP.sha256, methodId, "baseline_corrected_pearson", "soft_rank_spearman_coulomb"]) {
        expect(outside.textContent).not.toContain(code);
      }
      expect(tech.textContent).toContain("ART-5");
      expect(tech.textContent).toContain(methodId);
      expect(within(stage).getByText("Co mapa ukazuje")).toBeTruthy();
      expect(within(stage).getByText("Jak spolehlivá je mapa")).toBeTruthy();
    });

    it("says a set stored under an older method draws no map, with no map hint above the notice", async () => {
      open(SOCIOMAP, true);
      const stage = await screen.findByTestId("sociomap-stage");
      const notice = await within(stage).findByText(t("research.exec.results.olderMethod"));
      expect(notice.textContent).toBe("Mapa ze starší metody; spusťte nový běh");
      expect(within(stage).queryByTestId("object-map-stage")).toBeNull();
      expect(within(stage).queryByTestId("map-explained")).toBeNull();
      // Nothing about using a map is said above a notice that no map is drawn.
      expect(within(stage).queryByText(t("research.exec.objectMap.hint"))).toBeNull();
      expect(screen.queryByText(t("research.exec.results.mapToolNotInAia"))).toBeNull();
      expect(screen.queryByText("Jak používat mapu a AI pomoc")).toBeNull();
    });

    it("shows the run's experimental Sociomapping under the map, its old anchor opening the stage", async () => {
      open(signedOff, true, "#res-sociomapping", MAPPED);
      const stage = await screen.findByTestId("sociomap-stage");
      await within(stage).findByText(t("research.exec.sociomapping.experimental"));
      const card = document.getElementById("res-sociomapping")!;
      expect(stage.contains(card)).toBe(true);
      // Under the maps and what explains them, and with no amber frame on the stage (SOC12).
      const explained = await within(stage).findByTestId("map-explained");
      expect(explained.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(card.className).not.toContain("status-you");
    });

    it("keeps Výsledky when its Sociomapy tab is chosen, after any later render: a tab is not a stage", async () => {
      const { rerender } = open(signedOff, true, "#data");
      fireEvent.click(await screen.findByRole("tab", { name: "Sociomapy" }));
      expect(window.location.hash).toBe("#maps");
      rerender(<ResearchScreen step="results" frame={TEST_FRAME} />);
      await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
      expect(screen.getByRole("tablist", { name: "Oddíly výsledků" })).toBeTruthy();
      expect(screen.queryByTestId("sociomap-stage")).toBeNull();
      // Navigation to the stage (the workbench sets the hash: hashchange) opens it.
      act(() => { window.location.hash = "#data"; });
      act(() => { window.location.hash = "#maps"; });
      expect(await screen.findByTestId("sociomap-stage")).toBeTruthy();
    });

    it("keeps Sociomapy a tab of Výsledky in the classic layout", async () => {
      open(signedOff, false);
      expect(await screen.findByRole("tab", { name: "Sociomapy" })).toBeTruthy();
      expect(screen.queryByTestId("sociomap-stage")).toBeNull();
    });
  });

  it("shows a fictional run's aggregates labelled as fiction, hides a suppressed cell, keeps the Sociomap internal", async () => {
    api({
      ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    expect(await screen.findByText(/Fiktivní data\. Tento běh používá smyšlené respondenty/)).toBeTruthy();
    // A question with no stored wording says so, never its id; its card is found by its anchor (6c).
    const q2 = await findMeasure("q2");
    expect(q2.getAttribute("aria-label")).toBe("Otázka bez uloženého znění");
    fireEvent.click(within(q2).getByText("Odpovědi, intervaly a původ otázky"));
    expect(within(q2).getByText("34,8 %")).toBeTruthy();
    expect(within(q2).getByText("30,1–39,9")).toBeTruthy();
    const t1 = await findMeasure("t1");
    expect(within(t1).getByText(/Potlačeno: jen 19 unikátních dárců/)).toBeTruthy();
    expect(within(t1).queryByText("3,73")).toBeNull();
    expect(within(t1).queryByText(/3,25/)).toBeNull();
    expect(await screen.findByText(t("research.exec.results.mapsByMethod"))).toBeTruthy();
    // What 18.6.6's map tool did and AIA does not is said where the map is.
    expect(screen.getByText(t("research.exec.results.mapToolNotInAia"))).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Sociomapy" }));
    // A run stored under the old default (the reference map, no aia-sociomap-5 map): its data
    // stays, its map panel says why nothing is drawn, and draws nothing.
    const map = screen.getByRole("region", { name: "Nápoje" });
    expect(within(map).getByText(t("research.exec.results.olderMethod"))).toBeTruthy();
    expect(t("research.exec.results.olderMethod")).toBe("Mapa ze starší metody; spusťte nový běh");
    expect(within(map).queryByText("Káva")).toBeNull();
    expect(within(map).queryByText("6,14")).toBeNull();
    expect(screen.getAllByText(/Artefakt ART-4/).length).toBe(1);
    // No hand-off to 18.6.6: the report AIA does not have yet is said, not linked (ADR 0018).
    expect(screen.queryByRole("link", { name: /18\.6\.6/ })).toBeNull();
    expect(screen.getByText(t("research.exec.results.reportNotInAia"))).toBeTruthy();
    // 18.6.6's own aggregation: no deviation is claimed.
    expect(document.querySelector("[data-aggregate-deviation]")).toBeNull();
  });

  it("says above the numbers when the aggregate is no longer 18.6.6's port, and what changed", async () => {
    const deviating = {
      ...AGGREGATE,
      payload: {
        aggregate: {
          ...AGGREGATE.payload.aggregate,
          questions: {
            t2: { typ: "skala", ...support("REPORTABLE", 140), prumer: 3.9, prumer_interval_95: { low: 3.5, high: 4.2 }, top2box_pct: 41.0, top2box_interval_95: { low: 35, high: 47 } },
          },
          deviation: {
            from: "aia-aggregate-1",
            methodology_version: "aia-aggregate-1+e2",
            changed: [{ path: "top_box", unit: 2, used: 3 }],
            replaced_formulas: ["agg.mean"],
            note_cs: "…",
          },
        },
      },
    };
    api({
      ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => deviating,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    // Wait until the aggregate has loaded: querySelector's null does not throw, so it is thrown.
    const note = await waitFor(() => {
      const found = document.querySelector("[data-aggregate-deviation]");
      if (!found) throw new Error("the deviation note is not shown yet");
      return found as HTMLElement;
    });
    expect(within(note).getByText("Odchylka od 18.6.6")).toBeTruthy();
    expect(within(note).getByText(/upravené metodiky aia-aggregate-1\+e2/)).toBeTruthy();
    expect(within(note).getByText("top_box: 2 v 18.6.6, zde 3")).toBeTruthy();
    expect(within(note).getByText("Nahrazený vzorec: agg.mean")).toBeTruthy();
    // The top box is named by the width this aggregate used, not the unit's two.
    const t2 = await findMeasure("t2");
    fireEvent.click(within(t2).getByText("Odpovědi, intervaly a původ otázky"));
    expect(within(t2).getByText("Horní body (3)")).toBeTruthy();
    expect(within(t2).queryByText("Horní dva body")).toBeNull();
  });

  it("opens data with pinned question wording, evidence counts and searchable measures", async () => {
    const specification = {
      ...AGGREGATE,
      artifact_id: "ART-1",
      artifact_type: "research_specification",
      // An identical compiled specification may be reused from an earlier revision.
      payload: { design_revision_id: "REV-older", specification: { n: 200, questions: [{ id: "t1", text: "Jak hodnotíte nabídku?", typ: "skala", scale: [1, 5] }, { id: "q2", text: "Který nápoj byste si vybrali?", typ: "vyber", options: ["Kávu", "Čaj"] }] } },
    };
    api({
      ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-1": () => specification,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    const question = await screen.findByRole("region", { name: "Který nápoj byste si vybrali?" });
    // Čaj leads only by its estimate: the intervals overlap, so no winner is named.
    expect(within(question).getByText("Nejvíce odpovědí: Čaj (38,4 %) a Kávu (34,8 %); pořadí mezi nimi nelze potvrdit, 95% intervaly se překrývají.")).toBeTruthy();
    expect(within(question).queryByText(/Nejčastější odpověď/)).toBeNull();
    const explorer = document.querySelector("[data-aggregate-explorer]") as HTMLElement;
    // The questionnaire's order, not the aggregate's: t1 is asked first.
    expect(within(explorer).getAllByRole("region").map((r) => r.getAttribute("aria-label")).filter((l) => l !== "Jak číst tato data"))
      .toEqual(["Jak hodnotíte nabídku?", "Který nápoj byste si vybrali?"]);
    expect(within(explorer).getByRole("region", { name: "Jak hodnotíte nabídku?" }).textContent).toMatch(/Číselný výsledek je skrytý: podpora dat nestačí\./);
    expect(within(explorer).getByText("Plánovaný vzorek: 200")).toBeTruthy();
    expect(within(explorer).getAllByText("Podložené v rámci běhu").length).toBeGreaterThan(0);
    fireEvent.change(within(explorer).getByRole("searchbox", { name: "Najít otázku nebo objekt" }), { target: { value: "nabídku" } });
    expect(within(explorer).queryByRole("region", { name: "Který nápoj byste si vybrali?" })).toBeNull();
    expect(within(explorer).getByRole("region", { name: "Jak hodnotíte nabídku?" })).toBeTruthy();
    fireEvent.change(within(explorer).getByRole("searchbox", { name: "Najít otázku nebo objekt" }), { target: { value: "" } });
    fireEvent.change(within(explorer).getByRole("combobox", { name: "Podpora dat" }), { target: { value: "SUPPRESS" } });
    expect(within(explorer).queryByRole("region", { name: "Který nápoj byste si vybrali?" })).toBeNull();
    expect(within(explorer).getByRole("region", { name: "Jak hodnotíte nabídku?" })).toBeTruthy();
  });

  it("compares a set's objects in words and on one scale, and opens a card from its link", async () => {
    const rating = (mean: number, low: number, high: number, status = "REPORTABLE") => ({ typ: "skala", ...support(status as "REPORTABLE", 140), effective_n_kish: 401.8, prumer: mean, prumer_interval_95: { low, high }, top2box_pct: 40, top2box_interval_95: { low: 30, high: 50 } });
    const aggregate = { ...AGGREGATE, payload: { aggregate: { ...AGGREGATE.payload.aggregate, batteries: { napoje: { title: "Nápoje", objects: {
      kava: { label: "Káva", ...rating(4.2, 4.0, 4.4) }, caj: { label: "Čaj", ...rating(3.0, 2.7, 3.3) }, voda: { label: "Voda", ...rating(2.9, 2.6, 3.2) },
      mleko: { label: "Mléko", ...rating(3.5, 2.0, 5.0, "SUPPRESS") },
    } } } } } };
    const specification = { ...AGGREGATE, artifact_id: "ART-1", artifact_type: "research_specification",
      payload: { specification: { n: 200, questions: [], batteries: [{ id: "napoje", title: "Nápoje", scale: [1, 5], objects: [{ id: "kava", label: "Káva" }, { id: "caj", label: "Čaj" }, { id: "voda", label: "Voda" }, { id: "mleko", label: "Mléko" }] }] } } };
    api({ ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-1": () => specification,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => aggregate,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    const comparison = await screen.findByRole("region", { name: "Srovnání: Nápoje" });
    expect(within(comparison).getByText("Průměr na škále 1–5 · 95% interval · Kish n")).toBeTruthy();
    expect(within(comparison).getByText(/Spolehlivě nejvýše hodnocený: Káva\. Nejníže hodnocené: Čaj a Voda; pořadí mezi nimi nelze potvrdit\./)).toBeTruthy();
    expect(within(comparison).getByText("Pořadí platí jen tam, kde se intervaly rozcházejí.")).toBeTruthy();
    // Highest mean first, then the suppressed object in a row of its own.
    expect(within(comparison).getAllByRole("link").map((a) => a.textContent)).toEqual(["Káva", "Čaj", "Voda", "Mléko"]);
    const kava = comparison.querySelector('[data-object="kava"]') as HTMLElement;
    expect(within(kava).getByText("[4,00; 4,40]")).toBeTruthy();
    expect(kava.textContent).toMatch(/z 5/);
    // Kish n is the aggregate's effective_n_kish (401.8), not the donor-adjusted effective_n (30).
    expect(kava.querySelector("td:last-child")?.textContent).toBe("401");
    // A suppressed object keeps its row and says why; its mean and interval are not shown.
    const mleko = comparison.querySelector('[data-object="mleko"]') as HTMLElement;
    expect(mleko.getAttribute("data-withheld")).toBe("suppressed");
    expect(mleko.textContent).toMatch(/^MlékoPotlačeno · podpora dat nestačí \(\d+ unikátních dárců\)/);
    expect(within(comparison).queryByText("3,50")).toBeNull();
    expect(comparison.textContent).not.toMatch(/2,00|5,00/);
    // The Lead names a measure's card and nothing else on Výsledky: no set: or object: (those
    // kinds are the design's and the map's), and every id names exactly one element.
    expect(comparison.hasAttribute("data-aia")).toBe(false);
    expect(comparison.querySelector("[data-aia]")).toBeNull();
    const marks = [...document.querySelectorAll("[data-aggregate-explorer] [data-aia]")].map((el) => el.getAttribute("data-aia")!);
    expect(marks).toEqual(expect.arrayContaining(["measure:napoje/kava", "measure:napoje/caj", "measure:napoje/voda", "measure:napoje/mleko"]));
    expect(marks.every((m) => m.startsWith("measure:"))).toBe(true);
    for (const m of marks) expect(document.querySelectorAll(`[data-aia="${m}"]`)).toHaveLength(1);
    // No rounding block: 18.6.6's two places, as each card prints them.
    expect(within(comparison).getByText("4,20")).toBeTruthy();
    // A link to a card clears the filters that hide it and opens its detail.
    const explorer = document.querySelector("[data-aggregate-explorer]") as HTMLElement;
    fireEvent.change(within(explorer).getByRole("searchbox", { name: "Najít otázku nebo objekt" }), { target: { value: "káva" } });
    expect(within(explorer).queryByRole("region", { name: "Čaj" })).toBeNull();
    window.location.hash = "measure-napoje-caj";
    fireEvent(window, new HashChangeEvent("hashchange"));
    const card = await within(explorer).findByRole("region", { name: "Čaj" });
    expect(card.getAttribute("data-focused")).toBe("true");
    expect(card.getAttribute("data-aia")).toBe("measure:napoje/caj");
    expect((card.querySelector("details") as HTMLDetailsElement).open).toBe(true);
    expect((within(explorer).getByRole("searchbox", { name: "Najít otázku nebo objekt" }) as HTMLInputElement).value).toBe("");
    window.location.hash = "";
  });

  it("says above the numbers when the study's design moved past the run's revision", async () => {
    api({ ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/design/revisions": () => ({ items: [{ revision_id: "REV-b", revision: 4 }, { revision_id: "REV-a1", revision: 3 }] }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    await waitFor(() => expect(document.querySelector("[data-revision-moved]")?.textContent).toBe(
      "Výsledky běhu z revize 3; studie je na revizi 4Čísla platí pro revizi 3; změny z revize 4 v nich nejsou."));
  });

  it("says nothing of revisions while the run is on the study's newest", async () => {
    api({ ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/design/revisions": () => ({ items: [{ revision_id: "REV-a1", revision: 3 }] }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1/design/revisions").length).toBeGreaterThan(0));
    // Let the answer render before saying nothing showed.
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
    expect(document.querySelector("[data-revision-moved]")).toBeNull();
  });

  it("shows at most five raw answers to an open question, outside the details, labelled as data", async () => {
    const answers = ["Lepší aplikace", "Nižší poplatky", "Doporučení", "Pobočka blízko", "Rychlá podpora", "Šesté", "Sedmé"];
    const aggregate = { ...AGGREGATE, payload: { aggregate: { ...AGGREGATE.payload.aggregate, questions: {
      q9: { typ: "otevrena", ...support("REPORTABLE", 140), verbatimy: answers },
      q10: { typ: "otevrena", ...support("SUPPRESS", 12), verbatimy: ["Skryté"] },
    } } } };
    const specification = { ...AGGREGATE, artifact_id: "ART-1", artifact_type: "research_specification",
      payload: { specification: { n: 200, questions: [{ id: "q9", text: "Proč zvažujete změnu?", typ: "otevrena" }, { id: "q10", text: "Co dalšího?", typ: "otevrena" }] } } };
    api({ ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-1": () => specification,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => aggregate,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    const card = await screen.findByRole("region", { name: "Proč zvažujete změnu?" });
    expect(within(card).getByText("Otevřená otázka: 120 odpovědí, nekódováno.")).toBeTruthy();
    const list = within(card).getByRole("list", { name: "Ukázky odpovědí" });
    expect(within(list).getAllByRole("listitem").map((li) => li.textContent)).toEqual(answers.slice(0, 5).map((a) => `„${a}“`));
    expect(list.closest("details")).toBeNull();
    expect(card.textContent).not.toMatch(/Šesté|Sedmé/);
    expect(within(card).getByText(/^Otevřené odpovědi jsou data, ne připuštěná evidence; nejsou kódované\./)).toBeTruthy();
    // A suppressed open question shows no answer.
    const hidden = screen.getByRole("region", { name: "Co dalšího?" });
    expect(within(hidden).queryByRole("list", { name: "Ukázky odpovědí" })).toBeNull();
    expect(hidden.textContent).not.toMatch(/Skryté/);
  });

  it("ranks a set's means at the places the run stored them, as its cards print them", async () => {
    const rating = (mean: number, low: number, high: number) => ({ typ: "skala", ...support("REPORTABLE", 140), prumer: mean, prumer_interval_95: { low, high }, top2box_pct: 40, top2box_interval_95: { low: 30, high: 50 } });
    const aggregate = { ...AGGREGATE, payload: { aggregate: { ...AGGREGATE.payload.aggregate, rounding: { share_decimals: 0, mean_decimals: 1 }, batteries: { napoje: { title: "Nápoje", objects: {
      kava: { label: "Káva", ...rating(4.2, 4.0, 4.4) }, caj: { label: "Čaj", ...rating(3.0, 2.7, 3.3) },
    } } } } } };
    api({ ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => aggregate,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    const comparison = await screen.findByRole("region", { name: "Srovnání: Nápoje" });
    expect(within(comparison).getByText("4,2")).toBeTruthy();
    expect(within(comparison).getByText("3,0")).toBeTruthy();
    expect(within(comparison).queryByText("4,20")).toBeNull();
  });

  it("says why a run without results has none, in its state's words, and links to its progress", async () => {
    api(listed(run()));
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByText(`${t("research.exec.noResultsYet")} ${runState(run() as ResearchRun).label}.`)).toBeTruthy();
    expect(screen.getByRole("link", { name: t("research.exec.results.reportSeeProgress") }).getAttribute("href")).toContain("run=RUN-1");
    expect(screen.queryByRole("link", { name: tv("research.exec.answerability.retryOpen", { stage: t("aia.stages.run") }) })).toBeNull();
  });

  it("never says a failed run is still going", async () => {
    const failed = run({ phase: "FAILED", status: "FAILED", is_terminal: true, steps: [step("fieldwork", "FAILED", { kind: "research_fieldwork" })] });
    api(listed(failed));
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const state = runState(failed as ResearchRun);
    expect(state.state).not.toBe("RUNNING");
    expect(state.reason).toBeTruthy();
    // The whole sentence: one period, the reason's own (a doubled ".." was the stand-in review's P2).
    expect(await screen.findByText(`${t("research.exec.noResultsYet")} ${state.label}: ${state.reason}`)).toBeTruthy();
  });

  it("says there are no results while the run waits at fieldwork", async () => {
    api(listed(PARKED));
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.noResultsParked"))).toBeTruthy();
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/artifacts")).toHaveLength(0);
  });

  // The report card at the top of Výsledky (CompleteReport) is the one place a report is
  // downloaded and approved; the report panel below keeps its status and provenance.
  const reportRun = () => run({
    ...COMPLETED,
    steps: [...COMPLETED.steps, step("report", "SUCCEEDED", {
      kind: "research_report", stage_type: "REPORT", artifact_id: "ART-report",
    })],
  });
  const reportStatus = (extra: Record<string, unknown> = {}) => ({
    run_id: "RUN-1", state: "READY", internal_only: true, review_state: "DRAFT_UNAPPROVED",
    artifact_id: "ART-report", sha256: "abcdef0123456789", size_bytes: 10, synthetic: true, ...extra,
  });
  const stubDownloads = () => {
    const createObjectURL = vi.fn(() => "blob:report");
    const real = { create: URL.createObjectURL, revoke: URL.revokeObjectURL, click: HTMLAnchorElement.prototype.click };
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = vi.fn();
    HTMLAnchorElement.prototype.click = vi.fn();
    onTestFinished(() => {
      URL.createObjectURL = real.create;
      URL.revokeObjectURL = real.revoke;
      HTMLAnchorElement.prototype.click = real.click;
    });
    return createObjectURL;
  };
  const card = async () => {
    await screen.findByRole("heading", { name: "Kompletní zpráva studie" });
    return within(document.querySelector("[data-complete-report]") as HTMLElement);
  };
  // An option of the card once the report's status has been read and offers it: until then it is
  // drawn but disabled, and a click on it does nothing (the race this waits out).
  const offered = async (report: Awaited<ReturnType<typeof card>>, name: string) => {
    const option = await report.findByRole("radio", { name });
    await waitFor(() => expect(option.getAttribute("aria-disabled")).toBeNull());
    return option;
  };

  it("downloads one variant with its chosen review as DOCX and PDF of the same stored draft, and leaves its approval to the doc bar", async () => {
    // research-integrity-report 3: the Fio split -- a 40-page DOCX with literature, a 33-page base PDF.
    const createObjectURL = stubDownloads();
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: "2026-10-16T10:00:00Z", actual_cost_usd: 0.1, steps: [] };
    let prepared = false;
    let approvedNow = false;
    // D2: approved, the server says when and that the version's footers say so; its PDF is the
    // approved rendering the approval asked for. A draft whose own PDF was rendered here: the
    // server says approving gives the approved version one too.
    const variantStatus = () => prepared
      ? { run_id: "RUN-1", deep_research_run_id: "RUN-deep", state: "READY", artifact_id: "ART-context", sha256: "c", internal_only: true, stamped: true,
          ...(approvedNow
            ? { review_state: "APPROVED_INTERNAL", approved_on: "2026-10-18", approval_renders_pdf: false, pdf: { state: "RENDERING", artifact_id: null, size_bytes: null, reason: null } }
            : { review_state: "DRAFT_UNAPPROVED", approved_on: null, approval_renders_pdf: true, pdf: { state: "READY", artifact_id: "ART-context-pdf", size_bytes: 9, reason: null } }) }
      : { run_id: "RUN-1", deep_research_run_id: "RUN-deep", state: "NOT_PREPARED", internal_only: true };
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus({ pdf: { state: "READY", artifact_id: "ART-base-pdf", size_bytes: 9 } }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/context": () => variantStatus(),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/report/context": () => { prepared = true; return variantStatus(); },
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/context/download": () =>
        new Response(new Blob(["docx bytes"]), { headers: { "X-AIA-Artifact-Id": "ART-context", "X-AIA-Review-State": "DRAFT_UNAPPROVED" } }),
      // The PDF names the DOCX draft it renders: the same document in both formats.
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/context/pdf/download": () =>
        new Response(new Blob(["%PDF"]), { headers: { "X-AIA-Artifact-Id": "ART-context", "X-AIA-Review-State": "DRAFT_UNAPPROVED" } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    // The base report says it has no literature; nothing reads as "waiting" for a review it lacks.
    expect(report.getByText("není součástí")).toBeTruthy();
    const variant = await report.findByRole("combobox", { name: "Varianta zprávy" });
    await waitFor(() => expect(within(variant).getAllByRole("option")).toHaveLength(2));
    fireEvent.change(variant, { target: { value: "RUN-deep" } });
    const prepare = await report.findByRole("button", { name: /Připravit zprávu s rešerší/ });
    // A PDF is promised only where one will be made (review 2, F35), never as "DOCX i PDF".
    expect(report.getByText(/PDF se stejným obsahem vznikne, pokud ho toto prostředí a stav studie dovolí/)).toBeTruthy();
    expect(report.queryByText(/DOCX i PDF/)).toBeNull();
    fireEvent.click(prepare);
    await waitFor(() => expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context")).toHaveLength(1));
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context")[0].url).toContain("deep_research_run_id=RUN-deep");
    expect(await report.findByText("kapitola s rešerší a zdroji")).toBeTruthy();
    // The stored draft says it is a draft in its footers, and what approving it will change (D2).
    expect(report.getByText(tv("research.exec.report.review.draft", { version: "ART-context" }))).toBeTruthy();
    fireEvent.click(await report.findByRole("button", { name: /Stáhnout zprávu/ }));
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context/download")).toHaveLength(1));
    fireEvent.click(await offered(report, "PDF"));
    fireEvent.click(report.getByRole("button", { name: /Stáhnout zprávu/ }));
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context/pdf/download")).toHaveLength(1));
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context/pdf/download")[0].url).toContain("deep_research_run_id=RUN-deep");
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/pdf/download")).toHaveLength(0); // never the base PDF
    expect(createObjectURL).toHaveBeenCalledTimes(2);
    // Approved on the document being read, in the pane's doc bar (RPT3a): the card offers no
    // approval, says where it is, and follows the pane's answer by reading the variant again.
    expect(report.queryByRole("button", { name: t("research.exec.results.reportApprove") })).toBeNull();
    expect(report.getByText(t("research.exec.results.reportApproveWhere"))).toBeTruthy();
    // Another review's approval is not this card's: nothing read for it, nothing changed here.
    act(() => approvedInPane({ kind: "with_review", artifactId: "ART-elsewhere", review: "RUN-other" }));
    expect(calls.filter((c) => c.url.includes("deep_research_run_id=RUN-other"))).toHaveLength(0);
    approvedNow = true;
    act(() => approvedInPane({ kind: "with_review", artifactId: "ART-context", review: "RUN-deep" }));
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/approve")).toHaveLength(0);
    // The version is named before and after; what it is now is read again, never patched here
    // (was: the card patched review_state locally and kept the draft's PDF state).
    expect(report.getByText("ART-context")).toBeTruthy();
    expect(await report.findByText("schváleno 18. 10. 2026")).toBeTruthy();
    // Its approved PDF is being made: the line names the DOCX alone until that PDF exists (was:
    // "DOCX i PDF … to nesou", said of a PDF that could still fail; review 4).
    expect(report.getByText("Stav: Schváleno 18. 10. 2026 · verze ART-context — DOCX této verze to nese v zápatí")).toBeTruthy();
    expect(report.getByText(/PDF schválené verze se právě vytváří/)).toBeTruthy();
  });

  it("keeps a report with a review prepared under an earlier composition, says so, and prepares it anew", async () => {
    // Review 3: hiding an earlier contract's draft lost a prepared, possibly approved, report
    // whenever composing it again is refused. Changed on purpose (cross-review interactions#5):
    // this draft was approved here, and preparing an approved version anew displaced it; an
    // approved one is no longer offered to be prepared anew (the next test), so this one is a draft.
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: "2026-10-16T10:00:00Z", actual_cost_usd: 0.1, steps: [] };
    const earlier = { run_id: "RUN-1", deep_research_run_id: "RUN-deep", state: "READY", artifact_id: "ART-old", sha256: "c",
      review_state: "DRAFT_UNAPPROVED", internal_only: true, contract: "aia-contextual-report-3", contract_current: false,
      pdf: { state: "NOT_REQUESTED", artifact_id: null, size_bytes: null, reason: null, askable: true } };
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus(),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/context": () => earlier,
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/report/context": () =>
        new Response(JSON.stringify({ code: "context_report_refused", message: "the evidence, policy, method status or harness no longer match this outcome", details: { reason: "fingerprint_mismatch" } }), { status: 409 }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    const variant = await report.findByRole("combobox", { name: "Varianta zprávy" });
    await waitFor(() => expect(within(variant).getAllByRole("option")).toHaveLength(2));
    fireEvent.change(variant, { target: { value: "RUN-deep" } });
    expect(await report.findByText(/podle dřívější skladby zprávy \(aia-contextual-report-3\)/)).toBeTruthy();
    expect(report.getByRole("button", { name: /Stáhnout zprávu/ })).toBeTruthy();
    expect(report.getByText("neschváleno")).toBeTruthy();
    fireEvent.click(report.getByRole("button", { name: "Připravit znovu podle současné skladby" }));
    await waitFor(() => expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context")).toHaveLength(1));
    // Refused: the earlier report is still the one offered, and why is said in words (PC17).
    expect((await report.findByRole("alert")).textContent).toBe(t("research.exec.results.analysisStale"));
    expect(report.getByRole("button", { name: /Stáhnout zprávu/ })).toBeTruthy();
  });

  it("keeps an approved report with a review of an earlier composition the report, and offers no new one", async () => {
    // Cross-review interactions#5 / web#6: preparing an approved earlier version anew stored a
    // new draft that became the variant, and the approved one could no longer be downloaded.
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: "2026-10-16T10:00:00Z", actual_cost_usd: 0.1, steps: [] };
    const approved = { run_id: "RUN-1", deep_research_run_id: "RUN-deep", state: "READY", artifact_id: "ART-old", sha256: "c",
      review_state: "APPROVED_INTERNAL", internal_only: true, contract: "aia-contextual-report-3", contract_current: false,
      pdf: { state: "READY", artifact_id: "ART-old-pdf", size_bytes: 9, reason: null, askable: false } };
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus(),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/context": () => approved,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    const variant = await report.findByRole("combobox", { name: "Varianta zprávy" });
    await waitFor(() => expect(within(variant).getAllByRole("option")).toHaveLength(2));
    fireEvent.change(variant, { target: { value: "RUN-deep" } });
    expect(await report.findByText(/a je schválená: zůstává zprávou této varianty/)).toBeTruthy();
    expect(report.getByText("schváleno v AIA")).toBeTruthy();
    expect(report.queryByRole("button", { name: "Připravit znovu podle současné skladby" })).toBeNull();
    expect(report.queryByText(/připravená znovu bude nový koncept/)).toBeNull();
    expect(report.getByRole("button", { name: /Stáhnout zprávu/ })).toBeTruthy();
  });

  it("says why there is no PDF as text on the card, once on the page", async () => {
    // Review 3: removing the panel's stale line left the reason only in a disabled option's tooltip.
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () =>
        reportStatus({ pdf: { state: "FAILED", reason: "pdf_disabled", askable: false } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    const why = "PDF se nevytvořilo, protože toto nasazení PDF tehdy nevytvářelo; zpráva je k dispozici jako DOCX.";
    expect(await report.findByText(why)).toBeTruthy();
    // Not offered again: in this deployment asking only fails again (cross-review web#2).
    expect(report.queryByRole("button", { name: /Vytvořit PDF/ })).toBeNull();
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    await screen.findByText(t("research.exec.results.reportDraft"));
    expect(screen.getAllByText(why)).toHaveLength(1);
  });

  it("says an approved version's PDF was not asked for because its draft's was refused, and offers none", async () => {
    // The server keeps the draft's pdf_disabled for an approved version never asked for; without
    // it the card offered "Vytvořit PDF" for a job that could only fail again.
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () =>
        reportStatus({
          review_state: "APPROVED_INTERNAL",
          approved_on: "2026-10-18",
          stamped: true,
          pdf: { state: "NOT_REQUESTED", reason: "pdf_disabled", askable: false },
        }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    expect(await report.findByText(t("research.exec.report.review.pdfNotRequestedDisabled"))).toBeTruthy();
    expect(report.queryByText(/Můžete ho nechat vytvořit/)).toBeNull();
    expect(report.queryByRole("button", { name: /Vytvořit PDF/ })).toBeNull();
  });

  it("shows the internal draft from the completed report step and downloads it from the report card", async () => {
    const createObjectURL = stubDownloads();
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus(),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/download": () =>
        new Response(new Blob(["docx bytes"]), { status: 200, headers: { "X-AIA-Artifact-Id": "ART-report", "X-AIA-Review-State": "DRAFT_UNAPPROVED" } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    expect(await screen.findByText(t("research.exec.results.reportDraft"))).toBeTruthy();
    expect(screen.getByText(t("research.exec.results.reportSynthetic"))).toBeTruthy();
    expect(screen.getByText(/Artefakt ART-report/)).toBeTruthy();
    // The card lives on Přehled and Rešerše a zpráva; on Data it is hidden, kept mounted.
    expect(screen.queryByRole("heading", { name: "Kompletní zpráva studie" })).toBeNull();
    expect((document.querySelector("[data-results-lead]") as HTMLElement).hidden).toBe(true);
    fireEvent.click(screen.getByRole("tab", { name: "Rešerše a zpráva" }));
    const report = await card();
    expect(report.getByText("Stav: Koncept čeká na schválení.")).toBeTruthy();
    fireEvent.click(report.getByRole("button", { name: /Stáhnout zprávu/ }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/download")).toHaveLength(1);
    // Fictional data has no client version, and says why.
    expect(report.getByRole("radio", { name: "Pro klienta" }).getAttribute("aria-disabled")).toBe("true");
    expect(report.getByText(/Klientská zpráva vzniká jen z běhu s AI respondenty z populace/)).toBeTruthy();
  });

  it("still downloads the report of a delivered study, which starts no new work, and leaves its approval to the doc bar", async () => {
    // productization-coherence PC1: one flag gated both editing and the report, so closing a
    // study for edits would have taken its deliverable away with them.
    const createObjectURL = stubDownloads();
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus(),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/download": () =>
        new Response(new Blob(["docx bytes"]), { status: 200, headers: { "X-AIA-Artifact-Id": "ART-report", "X-AIA-Review-State": "DRAFT_UNAPPROVED" } }),
    });
    const delivered = { ...TEST_FRAME, canEdit: false, canReview: true, closed: { status: "DELIVERED", deliveredAt: null } };
    render(<ResearchScreen step="results" frame={delivered} />);
    expect(await screen.findByText(t("aia.study.closed.DELIVERED"))).toBeTruthy();
    const report = await card();
    expect(await report.findByText("Stav: Koncept čeká na schválení.")).toBeTruthy();
    fireEvent.click(report.getByRole("button", { name: /Stáhnout zprávu/ }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
    // Approved on the document being read, in the pane's doc bar (RPT3a), never here.
    expect(report.queryByRole("button", { name: /Schválit/ })).toBeNull();
    // Nothing on the page starts work: no analysis, retry or literature run is offered.
    expect(screen.queryByRole("button", { name: /Spustit rešerši výsledků/ })?.hasAttribute("disabled") ?? true).toBe(true);
  });

  it("asks for the run's own report's PDF when its step made none", async () => {
    // Review, 2026-10-16: a report whose step rendered no PDF had no way to get one.
    stubDownloads();
    let asked = false;
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () =>
        reportStatus({ pdf: asked ? { state: "RENDERING", askable: false } : { state: "NOT_REQUESTED", reason: null, askable: true } }),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/report/pdf": () => {
        asked = true;
        return reportStatus({ pdf: { state: "RENDERING", askable: false } });
      },
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    // Never asked for: made the first time, not "again" (was "Vytvořit PDF znovu", review 4 of D2).
    const ask = await report.findByRole("button", { name: "Vytvořit PDF" });
    expect(report.getByRole("radio", { name: "PDF" }).getAttribute("title")).toBe("PDF zatím nebylo vyžádáno. Můžete ho nechat vytvořit.");
    fireEvent.click(ask);
    await waitFor(() => expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/pdf")).toHaveLength(1));
    await waitFor(() => expect(report.queryByRole("button", { name: "Vytvořit PDF" })).toBeNull());
    expect(report.getByRole("radio", { name: "PDF" }).getAttribute("title")).toContain("vytváří");
  });

  it("prepares the report with a review although the run's own report failed", async () => {
    // Review, 2026-10-16: the card's one action waited on the base report being ready, which the
    // report with a review does not need (the prepare is refused by name when it cannot be made).
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: "2026-10-16T10:00:00Z", actual_cost_usd: 0.1, steps: [] };
    api({
      ...listed(run({ ...COMPLETED, steps: [...COMPLETED.steps, step("report", "FAILED", { kind: "research_report", stage_type: "REPORT" })] })),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => ({ run_id: "RUN-1", state: "FAILED", internal_only: true, reason: "pdf_conversion_failed" }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/context": () => ({ run_id: "RUN-1", deep_research_run_id: "RUN-deep", state: "NOT_PREPARED", internal_only: true }),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/report/context": () => ({ run_id: "RUN-1", deep_research_run_id: "RUN-deep", state: "NOT_PREPARED", internal_only: true }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    const variant = await report.findByRole("combobox", { name: "Varianta zprávy" });
    await waitFor(() => expect(within(variant).getAllByRole("option")).toHaveLength(2));
    fireEvent.change(variant, { target: { value: "RUN-deep" } });
    const prepare = await report.findByRole("button", { name: /Připravit zprávu s rešerší/ }) as HTMLButtonElement;
    expect(prepare.disabled).toBe(false);
    fireEvent.click(prepare);
    await waitFor(() => expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context")).toHaveLength(1));
  });

  it("never hands over a file that is not the draft the card shows and approves", async () => {
    // A newer draft stored since the card read the status: its bytes are not what an approval here names.
    const createObjectURL = stubDownloads();
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus(),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/download": () =>
        new Response(new Blob(["newer bytes"]), { headers: { "X-AIA-Artifact-Id": "ART-newer", "X-AIA-Review-State": "DRAFT_UNAPPROVED" } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    expect(await report.findByText("ART-report")).toBeTruthy(); // the draft named before download
    fireEvent.click(report.getByRole("button", { name: /Stáhnout zprávu/ }));
    expect(await report.findByRole("alert")).toBeTruthy();
    expect(report.getByRole("alert").textContent).toContain("není verze, kterou karta ukazuje");
    expect(createObjectURL).not.toHaveBeenCalled();
  });

  it("offers the client report only for modelled data, says why when refused, and leaves its approval to the doc bar", async () => {
    stubDownloads();
    let refuse = true;
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () =>
        reportStatus({ synthetic: false, modelled: true, data_origin_kind: "MODELLED" }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/client/download": () => refuse
        ? new Response('{"code":"client_report_refused","message":"Žádné číslo tohoto běhu nesplnilo pravidla pro klienta."}', { status: 409 })
        : new Response(new Blob(["client docx"]), { status: 200, headers: { "X-AIA-Artifact-Id": "ART-client", "X-AIA-Review-State": "DRAFT_UNAPPROVED" } }),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/report/approve": () =>
        ({ run_id: "RUN-1", artifact_id: "ART-client", review_state: "APPROVED_INTERNAL", report_kind: "client", internal_only: false }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    // The client option is there from the first render but disabled until the run's report
    // status says its data is modelled: click it only once that has loaded.
    await waitFor(() => expect(report.getByRole("radio", { name: "Pro klienta" }).getAttribute("aria-disabled")).not.toBe("true"));
    fireEvent.click(report.getByRole("radio", { name: "Pro klienta" }));
    expect(await report.findByText(t("research.exec.results.reportClientHint"))).toBeTruthy();
    // Not downloaded yet: whether it is a draft is not known here, and not said.
    expect(report.queryByText(new RegExp(t("research.exec.results.reportClientHintDraft")))).toBeNull();
    // The client version is DOCX only.
    expect(report.getByRole("radio", { name: "PDF" }).getAttribute("aria-disabled")).toBe("true");
    fireEvent.click(report.getByRole("button", { name: t("research.exec.results.reportDownloadClient") }));
    expect(await report.findByText(/nesplnilo pravidla pro klienta/)).toBeTruthy();
    refuse = false;
    fireEvent.click(report.getByRole("button", { name: t("research.exec.results.reportDownloadClient") }));
    // The client report is approved on the document being read (RPT3a): the card offers no approval,
    // neither as "for the client" nor as "for internal use".
    await report.findByText(new RegExp(t("research.exec.results.reportClientHintDraft")));
    expect(report.queryByRole("button", { name: t("research.exec.results.reportApproveClient") })).toBeNull();
    expect(report.queryByRole("button", { name: t("research.exec.results.reportApprove") })).toBeNull();
    // The downloaded draft is said to be one, and to need approving before it is handed over.
    expect(report.getByText(new RegExp(t("research.exec.results.reportClientHintDraft")))).toBeTruthy();
    // Approved in the pane's doc bar: the card says the review alone, as the server answered it.
    act(() => approvedInPane({ kind: "client", artifactId: "ART-client", stamped: null }));
    expect(await report.findByText(`Stav: ${t("research.exec.report.review.clientApproved")}`)).toBeTruthy();
    expect(report.queryByText(/interní použití/)).toBeNull();
    // Approved: never "Je to koncept" two lines from "Schváleno" (cross-review web#4).
    expect(report.queryByText(new RegExp(t("research.exec.results.reportClientHintDraft")))).toBeNull();
    // The card itself approved nothing.
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/approve")).toHaveLength(0);
  });

  it("says what approving the client report does to the file the client receives", async () => {
    stubDownloads();
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () =>
        reportStatus({ synthetic: false, modelled: true, data_origin_kind: "MODELLED" }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/client/download": () =>
        new Response(new Blob(["client docx"]), { status: 200, headers: { "X-AIA-Artifact-Id": "ART-client", "X-AIA-Review-State": "DRAFT_UNAPPROVED" } }),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/report/approve": () =>
        ({ run_id: "RUN-1", artifact_id: "ART-client", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-18", stamped: true, internal_only: true }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    await waitFor(() => expect(report.getByRole("radio", { name: "Pro klienta" }).getAttribute("aria-disabled")).not.toBe("true"));
    fireEvent.click(report.getByRole("radio", { name: "Pro klienta" }));
    fireEvent.click(report.getByRole("button", { name: t("research.exec.results.reportDownloadClient") }));
    expect(await report.findByText(`Stav: ${t("research.exec.report.review.clientDraft")}`)).toBeTruthy();
    act(() => approvedInPane({ kind: "client", artifactId: "ART-client", approvedOn: "2026-10-18", stamped: true }));
    // Its DOCX, the one the client receives, says SCHVÁLENO with the date and the version.
    expect(await report.findByText("Stav: Schváleno 18. 10. 2026 · verze ART-client — DOCX této verze to nese v zápatí")).toBeTruthy();
    expect(report.queryByText(/interní použití/)).toBeNull();
  });

  it("hears an approval of another run as nothing (RPT3a)", async () => {
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () =>
        reportStatus({ synthetic: false, modelled: true, data_origin_kind: "MODELLED" }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    await waitFor(() => expect(report.getByRole("radio", { name: "Pro klienta" }).getAttribute("aria-disabled")).not.toBe("true"));
    fireEvent.click(report.getByRole("radio", { name: "Pro klienta" }));
    act(() => approvedInPane({ runId: "RUN-other", kind: "client", artifactId: "ART-elsewhere" }));
    expect(report.queryByText(`Stav: ${t("research.exec.report.review.clientApproved")}`)).toBeNull();
    expect(report.queryByText(/ART-elsewhere/)).toBeNull();
  });

  it("offers the report's PDF when the run stored one, and says why when it could not", async () => {
    stubDownloads();
    let pdf: unknown = { state: "READY", artifact_id: "ART-pdf", size_bytes: 9 };
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus({ pdf }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/pdf/download": () =>
        new Response(new Blob(["%PDF-1.7"], { type: "application/pdf" }), { status: 200, headers: { "X-AIA-Artifact-Id": "ART-report" } }),
    });
    const { unmount } = render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    let report = await card();
    fireEvent.click(await offered(report, "PDF"));
    fireEvent.click(report.getByRole("button", { name: /Stáhnout zprávu/ }));
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/pdf/download")).toHaveLength(1));
    unmount();

    pdf = { state: "FAILED", reason: "pdf_conversion_failed" };
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    report = await card();
    const option = await report.findByRole("radio", { name: "PDF" });
    await waitFor(() => expect(option.getAttribute("title")).toBe(t("research.exec.results.reportPdfFailed")));
    expect(option.getAttribute("aria-disabled")).toBe("true");
  });

  it("says the internal draft approved in the doc bar once the pane answers, approving nothing itself (RPT3a)", async () => {
    let approvedNow = false;
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      // The card reads the report again on the pane's word (D2): the server's state, not a patch.
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus(approvedNow ? { review_state: "APPROVED_INTERNAL" } : {}),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    expect(await report.findByText("Stav: Koncept čeká na schválení.")).toBeTruthy();
    expect(report.queryByRole("button", { name: t("research.exec.results.reportApprove") })).toBeNull();
    // It says where the draft is approved, so it never looks unapprovable.
    expect(report.getByText(t("research.exec.results.reportApproveWhere"))).toBeTruthy();
    approvedNow = true;
    act(() => approvedInPane({ kind: "internal", artifactId: "ART-report" }));
    expect(await report.findByText("Stav: Schváleno pouze pro interní použití.")).toBeTruthy();
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/approve")).toHaveLength(0);
    expect(report.queryByText(t("research.exec.results.reportApproveWhere"))).toBeNull();
  });

  it("reads the report again after an approval in the doc bar and waits for the approved version's PDF", async () => {
    // D2: approving freezes the version and asks for its approved PDF. The approval's answer has
    // no date; the line below has one only because the card read the report again.
    const createObjectURL = stubDownloads();
    let approvedNow = false;
    const named = 'attachment; filename="AIA-STU-1-RUN-1-zakladni-ART-report-schvaleno.docx"';
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => approvedNow
        ? reportStatus({ review_state: "APPROVED_INTERNAL", approved_on: "2026-10-18", stamped: true, approval_renders_pdf: false, pdf: { state: "RENDERING", askable: false } })
        : reportStatus({ approved_on: null, stamped: true, approval_renders_pdf: true, pdf: { state: "READY", artifact_id: "ART-pdf", size_bytes: 9 } }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/download": () =>
        new Response(new Blob(["stamped docx"]), { headers: {
          "X-AIA-Artifact-Id": "ART-report", "X-AIA-Review-State": "APPROVED_INTERNAL", "Content-Disposition": named,
        } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    expect(await report.findByText(tv("research.exec.report.review.draft", { version: "ART-report" }))).toBeTruthy();
    const reads = called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report").filter((c) => c.url.endsWith("/report")).length;
    // Approved in the pane's doc bar (RPT3a): the card hears it and reads the report again.
    approvedNow = true;
    act(() => approvedInPane({ kind: "internal", artifactId: "ART-report" }));
    // The approved PDF is not made yet: the DOCX alone is said to carry it (review 4).
    expect(await report.findByText("Stav: Schváleno 18. 10. 2026 · verze ART-report — DOCX této verze to nese v zápatí")).toBeTruthy();
    // The state line is a live region: the approval a screen reader user made is announced
    // (cross-review web#11: the focused button vanished and nothing was said).
    expect(report.getByRole("status").textContent).toBe("Stav: Schváleno 18. 10. 2026 · verze ART-report — DOCX této verze to nese v zápatí");
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report").filter((c) => c.url.endsWith("/report")).length).toBeGreaterThan(reads);
    // The draft's PDF is not the approved version's: the approved one is being made.
    const pdf = report.getByRole("radio", { name: "PDF" });
    expect(pdf.getAttribute("aria-disabled")).toBe("true");
    expect(report.getByText(/PDF schválené verze se právě vytváří/)).toBeTruthy();
    expect(report.queryByText(t("research.exec.report.review.older"))).toBeNull();
    // The approved DOCX is saved under the name the server gives it: the version, approved.
    fireEvent.click(report.getByRole("button", { name: /Stáhnout zprávu/ }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
    const clicked = vi.mocked(HTMLAnchorElement.prototype.click).mock.contexts[0] as HTMLAnchorElement;
    expect(clicked.download).toBe("AIA-STU-1-RUN-1-zakladni-ART-report-schvaleno.docx");
  });

  it("never hands over a file whose review is not the card's", async () => {
    // Approved since the card read it: the file says SCHVÁLENO, the card still says Koncept.
    const createObjectURL = stubDownloads();
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus({ stamped: true }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/download": () =>
        new Response(new Blob(["stamped"]), { headers: { "X-AIA-Artifact-Id": "ART-report", "X-AIA-Review-State": "APPROVED_INTERNAL" } }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    expect(await report.findByText("ART-report")).toBeTruthy();
    fireEvent.click(report.getByRole("button", { name: /Stáhnout zprávu/ }));
    expect(await report.findByRole("alert")).toBeTruthy();
    expect(report.getByRole("alert").textContent).toContain("jiný stav schválení");
    expect(createObjectURL).not.toHaveBeenCalled();
  });

  it("says an older approved version keeps its draft footer, as it is served", async () => {
    // A version stored before its status moved to the footers is served as stored (D2).
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () =>
        reportStatus({ review_state: "APPROVED_INTERNAL", approved_on: "2026-10-01", stamped: false }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    expect(await report.findByText("Stav: Schváleno pouze pro interní použití.")).toBeTruthy();
    // Approved already: said as done, never as an approval still to come (was `older`, review 4).
    expect(report.getByText(t("research.exec.report.review.olderApproved"))).toBeTruthy();
    expect(report.queryByText(t("research.exec.report.review.older"))).toBeNull();
    expect(report.getByText("schváleno 1. 10. 2026")).toBeTruthy();
    expect(report.queryByText(/to nesou v zápatí/)).toBeNull();
  });

  it.each([
    // Its draft PDF ready, but a delivered study starts no work: approving asks for none. The PDF
    // gives no reason, so the card read "a PDF will be made" (review 4 of D2).
    ["a closed study whose draft PDF is ready", { approval_renders_pdf: false, pdf: { state: "READY", artifact_id: "ART-pdf", size_bytes: 9, askable: false } }],
    // A deployment that rendered no PDF (the code default): nothing says one ever will be.
    ["a deployment that made no PDF", { pdf: { state: "NOT_REQUESTED", reason: null, askable: true } }],
  ])("promises the approved version's DOCX alone for %s", async (_case, extra) => {
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus({ stamped: true, ...extra }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    expect(await report.findByText(tv("research.exec.report.review.draftDocx", { version: "ART-report" }))).toBeTruthy();
    expect(report.queryByText(/DOCX i PDF/)).toBeNull();
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
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    // One rule, one wording, on the card and the panel (6e).
    expect((await screen.findAllByText(t("research.exec.report.status.REFUSED"), { exact: false })).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByRole("button", { name: t("research.exec.results.reportDownload") })).toBeNull();
  });

  it("names the module that holds the report back, why, and the way to Progress", async () => {
    const reportRun = run({
      ...COMPLETED,
      status: "WAITING", phase: "WAITING",
      steps: [...COMPLETED.steps,
        step("analysis_executive", "SUCCEEDED", { kind: "research_analysis", stage_type: "ANALYSIS", artifact_id: "ART-a" }),
        step("analysis_audience", "WAITING_PROVIDER", { kind: "research_analysis", stage_type: "ANALYSIS",
          waiting_reason: "analysis_unconfigured", error_message: "AI analýza není pro tento běh zapnuta." }),
        step("report", "PENDING", { kind: "research_report", stage_type: "REPORT" })],
    });
    api({
      ...listed(reportRun),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ run_id: "RUN-1", internal_only: true, synthetic: true, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => ({ run_id: "RUN-1", state: "PENDING", internal_only: true, reason: null }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    expect(await screen.findByText(t("research.exec.results.reportHeldBy"))).toBeTruthy();
    const hold = document.querySelector('[data-hold="analysis_audience"]');
    expect(hold?.textContent).toContain("Cílová skupina");
    expect(hold?.textContent).toContain("AI analýza není pro tento běh zapnuta.");
    expect(document.querySelector('[data-hold="analysis_executive"]')).toBeNull();
    expect(document.querySelector('[data-hold="report"]')).toBeNull();
    const link = screen.getByRole("link", { name: t("research.exec.results.reportSeeProgress") });
    expect(link.getAttribute("href")).toContain("?run=RUN-1");
  });

  it("leaves the Sociomap out for a person the API refuses it to", async () => {
    api({
      ...listed(COMPLETED),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () =>
        new Response('{"code":"insufficient_role","message":"Not permitted."}', { status: 403 }),
    });
    render(<ResearchScreen step="results" frame={{ ...TEST_FRAME, canEdit: false }} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    expect(await findMeasure("q2")).toBeTruthy();
    await waitFor(() => expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5")).toHaveLength(1));
    expect(screen.queryByText(t("research.exec.results.mapsByMethod"))).toBeNull();
  });
});


describe("A run's results outside a study session (project memory M2a)", () => {
  it("draws a run from the frame alone, read-only: every label, no download, no interpretation research, only reads", async () => {
    const reportRun = run({
      ...COMPLETED,
      steps: [...COMPLETED.steps,
        step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", stage_type: "ANALYSIS", artifact_id: "ART-a" }),
        step("report", "SUCCEEDED", { kind: "research_report", stage_type: "REPORT", artifact_id: "ART-report" })],
    });
    api({
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ run_id: "RUN-1", internal_only: true, synthetic: true, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => ({
        run_id: "RUN-1", state: "READY", internal_only: true, review_state: "DRAFT_UNAPPROVED",
        artifact_id: "ART-report", sha256: "abcdef0123456789", size_bytes: 10, synthetic: true,
      }),
    });
    render(
      <StudyFrameProvider frame={{ ...TEST_FRAME, canEdit: false }}>
        <RunResults run={reportRun as unknown as ResearchRun} progressHref={null} />
      </StudyFrameProvider>,
    );
    expect(await screen.findByText(/Fiktivní data\. Tento běh používá smyšlené respondenty/)).toBeTruthy();
    expect(await screen.findByText(t("research.exec.results.reportDraft"))).toBeTruthy();
    expect(await screen.findByText(t("research.exec.results.mapsByMethod"))).toBeTruthy();
    // Read-only: no report card, and the report panel offers no download or approval.
    expect(document.querySelector("[data-complete-report]")).toBeNull();
    expect(screen.queryByRole("button", { name: /Stáhnout/, hidden: true })).toBeNull();
    expect(screen.queryByRole("button", { name: t("research.exec.results.reportApprove"), hidden: true })).toBeNull();
    expect(screen.queryByRole("link", { name: /Průběh tohoto běhu/ })).toBeNull();
    expect(called("GET", "/api/v1/studies/STU-1/deep-research")).toHaveLength(0);
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
  });
});

describe("Interpretation research", () => {
  it("does not interpret a research-questions module stored BLOCKED: it is no result yet (6a)", async () => {
    const blocked = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-questions", analysis_outcome: "BLOCKED" })] });
    api({ ...listed(blocked),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [],
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    expect(await screen.findByText("Nejprve je potřeba dokončit analýzu výzkumných otázek.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Spustit rešerši výsledků" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows a completed search with no accepted findings and blocks an incomplete report", async () => {
    const completed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-questions" })] });
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: null, actual_cost_usd: 0.8, steps: [] };
    api({ ...listed(completed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: false, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "GET /api/v1/studies/STU-1/deep-research/runs/RUN-deep/bundle": () => ({ quality_status: "NO_EVIDENCE", accepted: [], snapshots: [{ snapshot_id: "SRC-1", title: "Zachycený zdroj", url: "https://example.org", retrieval_mode: "LIVE" }], quarantined: [], sha256: "bundle-1" }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    expect(await screen.findByText("Bez ověřených zjištění")).toBeTruthy();
    expect(screen.getByText(/žádné externí tvrzení neprošlo ověřením/)).toBeTruthy();
    expect(await screen.findByText(/Analýza běhu není úplná/)).toBeTruthy();
    // An incomplete analysis is no report: the review cannot be put into one yet.
    const use = screen.getByRole("button", { name: "Použít ve zprávě" }) as HTMLButtonElement;
    expect(use.disabled).toBe(true);
    fireEvent.click(use);
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context")).toHaveLength(0);
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context/download")).toHaveLength(0);
  });
  it("shows every word of the review, formatted: findings, sources, gaps and rejections with their reasons, the draft by section", async () => {
    const completed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-questions" })] });
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: null, actual_cost_usd: 0.8, steps: [] };
    const bundle = { quality_status: "PARTIAL", sha256: "b-2", counts: { tracks: 3, new_metric: 2 },
      accepted: [
        { evidence: { evidence_id: "EV-1", claim: "Spotřeba čaje roste.\n- hlavně u mladých\n- ve městech", quote: "Čaj roste o 4 %.", source_ref: "SRC-1" }, score: { score: 0.8, source_class: "OFFICIAL_STATISTICS" } },
        { evidence: { evidence_id: "EV-2", claim: "Káva je stabilní.", quote: "", source_ref: "SRC-2" }, score: { score: 0.6, source_class: "C" } },
      ],
      snapshots: [{ snapshot_id: "SRC-1", title: "Zpráva o trhu", url: "https://example.org/a", retrieval_mode: "LIVE" }, { snapshot_id: "SRC-2", title: "", url: "https://example.org/b", retrieval_mode: "LIVE" }],
      quarantined: [{ reason: "QUOTE_NOT_FOUND", detail: "citace není ve zdroji", claim: "Čaj pijí hlavně senioři." }],
      synthesis: {
        check: { status: "PARTIAL", summary: "Trh se posouvá.\n\nDruhý odstavec.", summary_withheld: "shrnutí cituje číslo mimo podklady", excluded: [{ subject_key: "s3", text: "Káva brzy zmizí z trhu.", reason: "number_not_in_cited_evidence", detail: "číslo není v citaci" }], findings: [{ subject_key: "s1", text: "Čaj roste rychleji než káva.", evidence_ids: ["EV-2", "EV-1"] }, { subject_key: "s2", text: "Bez opory.", evidence_ids: ["EV-x"] }], gaps: ["Chybí data za rok 2025."], limitations: ["Jen veřejné zdroje."] },
        brief: { gaps: [{ need: "Benchmark spokojenosti", reason: "žádný zdroj ho neuvádí" }] },
      } };
    api({ ...listed(completed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: true, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "GET /api/v1/studies/STU-1/deep-research/runs/RUN-deep/bundle": () => bundle,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    const accepted = await screen.findByRole("list", { name: "Přijatá zjištění" });
    const first = within(accepted).getAllByRole("listitem")[0];
    expect(within(first).getByText("Zjištění č. 1")).toBeTruthy();
    expect(within(first).getByText("Spotřeba čaje roste.")).toBeTruthy();
    expect(within(first).getByText("hlavně u mladých").parentElement?.tagName).toBe("LI"); // a list inside the finding
    // A source's class in words; one this client does not know keeps its code beside them.
    expect(within(first).getByText(/typ zdroje podle domény: oficiální statistika/)).toBeTruthy();
    expect(within(first).queryByText(/OFFICIAL_STATISTICS/)).toBeNull();
    const second = accepted.querySelectorAll("[data-accepted-finding]")[1] as HTMLElement;
    expect(within(second).getByText(/typ zdroje podle domény: jiný typ/)).toBeTruthy();
    expect(within(second).getByText("C").tagName).toBe("CODE");
    expect(within(first).getByText("Čaj roste o 4 %.")).toBeTruthy();
    expect(screen.getByText("Zachycené zdroje (2)")).toBeTruthy();
    expect(screen.getAllByText("https://example.org/b")).toHaveLength(2); // the finding's source and the source list
    // Gaps and rejections keep their reasons.
    expect(screen.getByText("Benchmark spokojenosti")).toBeTruthy();
    expect(screen.getByText("· žádný zdroj ho neuvádí")).toBeTruthy();
    // A count key a newer engine added keeps its code; a known one reads in words.
    expect(screen.getByText("Počty: stopy 3 · jiný počet (technický kód: new_metric) 2")).toBeTruthy();
    // A reason this client has no words for says so; its code stays under technical details.
    expect(screen.getByText("AIA k tomuto záznamu zatím nemá popis.")).toBeTruthy();
    expect(screen.getByText("QUOTE_NOT_FOUND").closest("details")).toBeTruthy();
    expect(screen.getByText("· citace není ve zdroji")).toBeTruthy();
    // The draft stays closed and labelled, but reads by section, each finding naming what it rests on.
    const draft = document.querySelector("[data-synthesis-draft]") as HTMLDetailsElement;
    expect(draft.open).toBe(false);
    expect(within(draft).getByText("Trh se posouvá.")).toBeTruthy();
    expect(within(draft).getByText("Druhý odstavec.")).toBeTruthy();
    expect(within(draft).getByText("Opírá se o přijatá zjištění č. 2, 1")).toBeTruthy();
    expect(within(draft).getByText("Neopírá se o žádné přijaté zjištění · odkazy mimo přijatá zjištění: 1")).toBeTruthy();
    expect(within(draft).getByText("Chybí data za rok 2025.")).toBeTruthy();
    expect(within(draft).getByText("Jen veřejné zdroje.")).toBeTruthy();
    expect(within(draft).getByText("Stav kontroly: část byla vyřazena nebo zadržena, důvody jsou níže")).toBeTruthy();
    // The rejected claim and the prose the checker refused stay readable, with their reasons.
    expect(screen.getByText("Čaj pijí hlavně senioři.")).toBeTruthy();
    const rejected = within(draft).getByText("Odmítnuto kontrolou").parentElement as HTMLElement;
    expect(within(rejected).getByText("Káva brzy zmizí z trhu.")).toBeTruthy();
    expect(within(rejected).getByText("číslo není v citovaném podkladu · číslo není v citaci")).toBeTruthy();
    expect(within(rejected).getByText("· shrnutí cituje číslo mimo podklady")).toBeTruthy();
  });

  it("says an older review predates today's acceptance rules its report applies, and nothing of a newer one (review web#5)", async () => {
    // The screen listed an older review's findings as plain accepted ones while its report with
    // literature labelled those today's rules would not accept.
    const completed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-questions" })] });
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: null, actual_cost_usd: 0.4, steps: [] };
    let merge = "aia-merge-1";
    api({ ...listed(completed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: true, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "GET /api/v1/studies/STU-1/deep-research/runs/RUN-deep/bundle": () => ({
        quality_status: "OK", sha256: "b-3", counts: {}, quarantined: [], versions: { harness: "aia-deep-research-harness-1", merge },
        accepted: [{ evidence: { evidence_id: "EV-1", claim: "Fiktivní zjištění o běžném účtu.", quote: "Fiktivní citace.", source_ref: "SRC-1" }, score: { score: 0.7, source_class: "ACADEMIC_INSTITUTION" } }],
        snapshots: [{ snapshot_id: "SRC-1", title: "Fiktivní práce", url: "https://example.org/prace.pdf", retrieval_mode: "LIVE" }],
      }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    const note = await screen.findByRole("note", { name: t("research.deep.olderRules.title") });
    expect(note.textContent).toContain("vznikla před zavedením kontroly tématu a pravidel typů dokumentů");
    expect(note.textContent).toContain("v ní označí s důvodem");
    // Never unconditionally: today's topic check needs the review's stored plan to verify.
    expect(note.textContent).toContain("Kontrolu tématu přitom lze použít, jen když se podaří ověřit uložený plán rešerše");
    // The findings stay listed as the review accepted them.
    expect(within(await screen.findByRole("list", { name: "Přijatá zjištění" })).getByText("Fiktivní zjištění o běžném účtu.")).toBeTruthy();
    // A review merged under today's rules: nothing to say of them.
    cleanup();
    merge = "aia-merge-3/aia-works-1/aia-dr-topicality-1/aia-dr-filters-1/aia-dr-concepts-1/aia-document-types-1";
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    expect(within(await screen.findByRole("list", { name: "Přijatá zjištění" })).getByText("Fiktivní zjištění o běžném účtu.")).toBeTruthy();
    expect(screen.queryByRole("note", { name: t("research.deep.olderRules.title") })).toBeNull();
  });

  it.each([
    ["no query left", 0, true],
    ["queries left and nothing passed", 5, false],
  ])("an interpretation review with no finding says one thing: %s (review, Codex on #479)", async (_, sent, nothingSent) => {
    const completed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-questions" })] });
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: null, actual_cost_usd: 0, steps: [] };
    api({ ...listed(completed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: true, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "GET /api/v1/studies/STU-1/deep-research/runs/RUN-deep/bundle": () => ({ quality_status: "INSUFFICIENT", accepted: [], snapshots: [], quarantined: [] }),
      "GET /api/v1/studies/STU-1/deep-research/runs/RUN-deep/coverage": () => ({ tracks: 4, blocked_tracks: sent ? 0 : 4, queries_proposed: 6,
        queries_sent: sent, queries_refused: 0, hits: 0, sources_captured: 0, findings_accepted: 0, findings_quarantined: 0 }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    await screen.findByText("Přijatá zjištění");
    const searchedEmpty = /Rešerše dokončila hledání, ale žádné externí tvrzení neprošlo ověřením/;
    if (nothingSent) {
      // A run that sent no query never also reads as one that searched and found nothing.
      expect((await screen.findByText(tv("research.deep.searchedNothing", { blocked: 4, tracks: 4 }), { exact: false })).closest("[data-searched-nothing]")).toBeTruthy();
      expect(screen.queryByText(searchedEmpty)).toBeNull();
    } else {
      expect(await screen.findByText(searchedEmpty)).toBeTruthy();
      expect(document.querySelector("[data-searched-nothing]")).toBeNull();
    }
  });

  it("requires confirmation before cancelling an active interpretation review", async () => {
    const completed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-questions" })] });
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "RUNNING", phase: "RUNNING", is_terminal: false, retryable: false,
      created_at: null, actual_cost_usd: null, steps: [] };
    api({ ...listed(completed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: true, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "POST /api/v1/studies/STU-1/deep-research/runs/RUN-deep/cancel": () => review,
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    fireEvent.click(await screen.findByRole("button", { name: "Zrušit rešerši" }));
    expect(await screen.findByRole("dialog")).toBeTruthy();
    expect(called("POST", "/api/v1/studies/STU-1/deep-research/runs/RUN-deep/cancel")).toHaveLength(0);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "OK" }));
    await waitFor(() => expect(called("POST", "/api/v1/studies/STU-1/deep-research/runs/RUN-deep/cancel")).toHaveLength(1));
  });

  it("asks for the retry ceiling and sends the confirmed amount without changing the study budget", async () => {
    const completed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-questions" })] });
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" },
      preset: "QUICK", status: "FAILED", phase: "FAILED", is_terminal: true, retryable: true,
      created_at: null, actual_cost_usd: 0.1, steps: [] };
    api({ ...listed(completed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => [review],
      "POST /api/v1/studies/STU-1/deep-research/runs/RUN-deep/retry": b => (b as { confirm_cost_usd?: number } | null)?.confirm_cost_usd === 5 ? review :
        new Response(JSON.stringify({ code: "cost_confirmation_required", message: "confirm", details: { ceiling_usd: 5 } }), { status: 409 }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    fireEvent.click(await screen.findByRole("button", { name: "Zkusit znovu" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Opakování rešerše může stát nejvýše 5.00 USD/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "OK" }));
    await waitFor(() => expect(called("POST", "/api/v1/studies/STU-1/deep-research/runs/RUN-deep/retry")).toHaveLength(2));
    expect(called("POST", "/api/v1/studies/STU-1/deep-research/runs/RUN-deep/retry").map(c => c.body)).toEqual([null, { confirm_cost_usd: 5 }]);
    expect(called("PATCH", "/api/v1/studies/STU-1")).toHaveLength(0);
  });
  it("starts over the pinned analysis and puts the explicitly selected review into the report", async () => {
    const completed = run({ ...COMPLETED, steps: [...COMPLETED.steps,
      step("analysis_research_questions", "SUCCEEDED", { kind: "research_analysis", artifact_id: "ART-questions" })] });
    const review = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { kind: "ANALYSIS_MODULE", research_run_id: "RUN-1" },
      preset: "QUICK", status: "COMPLETED", phase: "COMPLETED", is_terminal: true, retryable: false,
      created_at: null, actual_cost_usd: 0.1, steps: [] };
    const bundle = { quality_status: "PARTIAL", accepted: [{ evidence: {
      evidence_id: "EV-library", claim: "Studie popisuje hodnocení knihovních služeb.", source_ref: "SRC-library",
    } }], snapshots: [], quarantined: [],
      synthesis: { check: { summary: "Sociomapping není aplikovatelný na hodnocení služeb.", findings: [], gaps: ["Chybí srovnatelný benchmark."], limitations: [] } } };
    let started = false;
    api({ ...listed(completed),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/analysis": () => ({ complete: true, modules: {}, pending: {} }),
      "GET /api/v1/studies/STU-1/deep-research/runs": () => started ? [review] : [{ ...review, run_id: "RUN-other", target: { research_run_id: "RUN-other" } }],
      "POST /api/v1/studies/STU-1/deep-research/runs/interpretation": () => { started = true; return review; },
      "GET /api/v1/studies/STU-1/deep-research/runs/RUN-deep/bundle": () => bundle,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/context/download": () => new Response("document bytes",
        { headers: { "X-AIA-Artifact-Id": "ART-context", "X-AIA-Review-State": "DRAFT_UNAPPROVED" } }),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/report/approve": () => ({ artifact_id: "ART-context", review_state: "APPROVED_INTERNAL" }),
    });
    const createUrl = vi.fn(() => "blob:test-report");
    const revokeUrl = vi.fn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: revokeUrl }));
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Rešerše a zpráva" }));
    const start = await screen.findByRole("button", { name: "Spustit rešerši výsledků" });
    expect(screen.queryByRole("button", { name: "Použít ve zprávě" })).toBeNull();
    fireEvent.click(start);
    expect(await screen.findByText("Studie popisuje hodnocení knihovních služeb.", { exact: true })).toBeTruthy();
    const unapproved = screen.getByText("Sociomapping není aplikovatelný na hodnocení služeb.");
    const draft = unapproved.closest("details");
    expect(draft?.open).toBe(false);
    expect(within(draft!).getByText("Generovaný návrh syntézy · věcně neschválený")).toBeTruthy();
    expect(called("POST", "/api/v1/studies/STU-1/deep-research/runs/interpretation")[0].body).toMatchObject({
      target: { kind: "ANALYSIS_MODULE", research_run_id: "RUN-1", analysis_artifact_id: "ART-questions", module_id: "research_questions" }, preset_name: "QUICK",
    });
    // One choice of review, read by the report card: the panel never downloads a second variant.
    const use = screen.getByRole("button", { name: "Použít ve zprávě" }) as HTMLButtonElement;
    await waitFor(() => expect(use.disabled).toBe(false));
    fireEvent.click(use);
    const note = await screen.findByText(/Kompletní zpráva studie nahoře je teď varianta s touto rešerší/);
    expect(note.textContent).not.toContain("DOCX i PDF");
    expect(note.textContent).toContain("kde ho toto prostředí a stav studie dovolí");
    const variant = screen.getByRole("combobox", { name: "Varianta zprávy" }) as HTMLSelectElement;
    await waitFor(() => expect(variant.value).toBe("RUN-deep"));
    expect(called("POST", "/api/v1/studies/STU-1/research/runs")).toHaveLength(0);
    expect(createUrl).not.toHaveBeenCalled();
    expect(revokeUrl).not.toHaveBeenCalled();
  });
});

describe("Náklady on Průběh (artifact-fieldwork FLD4b)", () => {
  const STUDY = { study_id: "STU-1", name: "Starbucks", budget_usd: 50, spent_usd: 10, remaining_usd: 40, spend_confirm_usd: null };
  const rowsOf = async () => {
    const card = await screen.findByText(t("research.exec.spend.title"));
    const dl = await waitFor(() => {
      const found = card.closest("section, div")!.parentElement!.querySelector("[data-run-spend]");
      if (!found) throw new Error("no spend yet");
      return found;
    });
    return [...dl.querySelectorAll("[data-spend]")].map((r) => [r.getAttribute("data-spend"), r.querySelector("dd")!.textContent]);
  };

  it("reads the run's spent, held and unpriced calls beside the study's remainder", async () => {
    const spent = { ...COMPLETED, spend: { spent_usd: 0.4, reserved_usd: 0, uncertain_calls: 1 }, cost_ceiling: { usd: 2.5, unknown: null } };
    api({ ...listed(spent), "GET /api/v1/studies/STU-1": () => STUDY });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    await waitFor(async () =>
      expect(await rowsOf()).toEqual([
        ["spent", "0,40 USD"],
        ["held", "0,00 USD"],
        ["ceiling", `2,50 USD · ${t("research.exec.spend.ceilingNote")}`],
        ["unpriced", `${tv("research.exec.spend.unpricedCalls", { count: 1 })} · ${t("research.exec.spend.unpricedEnded")}`],
        ["remaining", `40,00 USD · ${t("research.exec.spend.remainingNote")}`],
      ]),
    );
  });

  it("says the spend is unknown when the API gave none, never 0,00 USD", async () => {
    api({ ...listed(COMPLETED), "GET /api/v1/studies/STU-1": () => STUDY });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.exec.spend.unknown"))).toBeTruthy();
    expect(document.querySelector("[data-run-spend]")).toBeNull();
  });

  it("carries the run's spend over an action's answer, which has none, until the next read replaces it", async () => {
    const parked = { ...PARKED, spend: { spent_usd: 1.5, reserved_usd: 0.25, uncertain_calls: 0 } };
    // The action's answer: no spend. The read after it: the run's spend as it now is.
    const answer = run({ steps: [step("compile", "SUCCEEDED"), step("preflight", "SUCCEEDED"), step("run", "RUNNABLE")] });
    const reread = { ...answer, spend: { spent_usd: 1.75, reserved_usd: 0.25, uncertain_calls: 0 } };
    let going = false;
    let held: (() => void) | null = null;
    const RESUME = "/api/v1/studies/STU-1/research/runs/RUN-1/resume";
    api({
      ...listed(parked),
      // The read after the answer waits, so what the answer alone leaves on screen can be seen.
      "GET /api/v1/studies/STU-1/research/runs/RUN-1": () => (going ? new Promise((resolve) => { held = () => resolve(reread); }) : parked),
      [`POST ${RESUME}`]: () => { going = true; return answer; },
      "GET /api/v1/studies/STU-1": () => STUDY,
    });
    render(<ResearchScreen step="progress" frame={TEST_FRAME} />);
    await waitFor(async () => expect((await rowsOf())[0]).toEqual(["spent", "1,50 USD"]));
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.resume") }));
    await waitFor(() => expect(called("POST", RESUME)).toHaveLength(1));
    await waitFor(() => expect(screen.queryByText(t("research.exec.parkedResume"))).toBeNull());
    expect((await rowsOf())[0]).toEqual(["spent", "1,50 USD"]);
    expect(screen.queryByText(t("research.exec.spend.unknown"))).toBeNull();
    await waitFor(() => expect(held).not.toBeNull());
    act(() => held!());
    await waitFor(async () => expect((await rowsOf())[0]).toEqual(["spent", "1,75 USD"]));
  });
});
