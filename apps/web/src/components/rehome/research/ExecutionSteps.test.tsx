// @vitest-environment jsdom
// Run, Progress and Results (ADR 0016) against a fake AIA API. What they must do:
// submit the design the person sees as a Design Revision, say what AIA's checks
// say, start one run over that revision, explain a run waiting for the AI
// runtime, hide a suppressed cell's numbers, label fictional data every time, and
// keep the internal Sociomap internal.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";

import { t, tv } from "@/i18n/t";
import type { ResearchRun } from "@/lib/api";
import { measureAnchor } from "@/lib/result-reading";
import { CONFLICT_MESSAGE } from "@/research/store";
import { RunResults } from "./ExecutionSteps";
import { StudyFrameProvider } from "./frame";
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
        "POST /api/v1/studies/STU-1/design/revisions": () => ({ revision_id: "REV-a1", study_id: "STU-1", revision: 3, content_sha256: "x", parent_revision: 2, source_stage: "run", created_by: "USR-1", created_at: "2026-09-25T08:00:00Z", created: true }),
        "GET /api/v1/studies/STU-1/design/revisions": () => ({ items: [{ revision_id: "REV-old", revision: 2 }] }),
        "GET /api/v1/studies/STU-1/research/readiness": () => READY,
        "GET /api/v1/studies/STU-1/research/runs": () => ({ items: [] }),
        "GET /api/v1/studies/STU-1/deep-research/runs": () => [],
        "POST /api/v1/studies/STU-1/research/runs": () => run({ created: true, phase: "QUEUED" }),
        ...overrides,
      };
      const answer = routes[`${method} ${u.split("?")[0]}`]?.(body) ?? {};
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
    expect(within(dialog).getByText("Tento běh může stát až 225.00 USD (limit studie je 100.00 USD). Spustit? Z rozpočtu studie zbývá 400.00 USD. Poté zbude nejméně 175.00 USD.")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: t("dialog.cancel") }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(called("POST", RUNS)).toHaveLength(0); // no yes, no run

    fireEvent.click(screen.getByRole("button", { name: t("research.exec.start") }));
    fireEvent.click(await screen.findByRole("button", { name: "OK" }));
    await waitFor(() => expect(called("POST", RUNS)).toHaveLength(1));
    expect(called("POST", RUNS)[0].body).toEqual({ design_revision_id: "REV-a1", confirm_cost_usd: 225 });
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
    fireEvent.click(await screen.findByRole("button", { name: t("research.exec.start") }));
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
    expect(within(dialog).getByText("Tento běh může stát až 225.00 USD (limit studie je 100.00 USD). Spustit? Z rozpočtu studie zbývá 400.00 USD. Poté zbude nejméně 175.00 USD.")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: "OK" }));
    expect(await screen.findByText("Opakování běhu RUN-1")).toBeTruthy();
    expect(asked).toBe(1);
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/retry").map((c) => c.body)).toEqual([null, { confirm_cost_usd: 225 }]);
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
    expect(within(log).getAllByRole("listitem").map((l) => l.textContent?.replace(/^[\d:]+/, ""))).toEqual([
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
    await waitFor(() => expect(document.querySelector('[data-step="compile"]')?.getAttribute("data-status")).toBe("SUCCEEDED"), { timeout: 6000 });
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
    const diagnostic = screen.getByText("Technické důvody odmítnutí").closest("details");
    expect(diagnostic?.open).toBe(false);
    expect(within(diagnostic!).getByText(/SCHEMA_INVALID: Input should be a valid array/)).toBeTruthy();
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
        objects: { outcome: "COMPLETED", summary: null, research_question_answers: [], key_findings: [{ text: "Bez čísel.", claim_ids: [] }], claims: [], violations: [] },
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
    const map = screen.getByRole("region", { name: "Nápoje" });
    expect(within(map).getByText("Káva")).toBeTruthy();
    expect(within(map).getByText("6,14")).toBeTruthy();
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
    const rating = (mean: number, low: number, high: number, status = "REPORTABLE") => ({ typ: "skala", ...support(status as "REPORTABLE", 140), prumer: mean, prumer_interval_95: { low, high }, top2box_pct: 40, top2box_interval_95: { low: 30, high: 50 } });
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
    expect(within(comparison).getByText("Průměr na škále 1–5 · 95% interval")).toBeTruthy();
    expect(within(comparison).getByText("Spolehlivě nejvýše hodnocený: Káva.")).toBeTruthy();
    expect(within(comparison).getByText("Nejníže hodnocené: Čaj a Voda; pořadí mezi nimi nelze potvrdit.")).toBeTruthy();
    expect(within(comparison).getAllByRole("link").map((a) => a.textContent)).toEqual(["Káva", "Čaj", "Voda"]);
    // A suppressed object is not drawn and has no number, but is named.
    expect(within(comparison).getByText("Bez čísla (potlačeno nebo bez průměru): Mléko.")).toBeTruthy();
    expect(within(comparison).queryByText("3,50")).toBeNull();
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
    expect((card.querySelector("details") as HTMLDetailsElement).open).toBe(true);
    expect((within(explorer).getByRole("searchbox", { name: "Najít otázku nebo objekt" }) as HTMLInputElement).value).toBe("");
    window.location.hash = "";
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

  it("shows the internal draft from the completed report step and downloads it from the report card", async () => {
    const createObjectURL = stubDownloads();
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus(),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report/download": () =>
        new Response(new Blob(["docx bytes"]), { status: 200 }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Data" }));
    expect(await screen.findByText(t("research.exec.results.reportDraft"))).toBeTruthy();
    expect(screen.getByText(t("research.exec.results.reportSynthetic"))).toBeTruthy();
    expect(screen.getByText(/Artefakt ART-report/)).toBeTruthy();
    const report = await card();
    expect(report.getByText("Stav: Koncept čeká na schválení.")).toBeTruthy();
    fireEvent.click(report.getByRole("button", { name: /Stáhnout zprávu/ }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/download")).toHaveLength(1);
    // Fictional data has no client version, and says why.
    expect(report.getByRole("radio", { name: "Pro klienta" }).getAttribute("aria-disabled")).toBe("true");
    expect(report.getByText(/Klientská zpráva vzniká jen z běhu s AI respondenty z populace/)).toBeTruthy();
  });

  it("offers the client report only for modelled data, approves the draft it downloaded, and says why when refused", async () => {
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
        ({ run_id: "RUN-1", artifact_id: "ART-client", review_state: "APPROVED_INTERNAL", internal_only: true }),
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    // The client option is there from the first render but disabled until the run's report
    // status says its data is modelled: click it only once that has loaded.
    await waitFor(() => expect(report.getByRole("radio", { name: "Pro klienta" }).getAttribute("aria-disabled")).not.toBe("true"));
    fireEvent.click(report.getByRole("radio", { name: "Pro klienta" }));
    expect(await report.findByText(t("research.exec.results.reportClientHint"))).toBeTruthy();
    // The client version is DOCX only.
    expect(report.getByRole("radio", { name: "PDF" }).getAttribute("aria-disabled")).toBe("true");
    fireEvent.click(report.getByRole("button", { name: t("research.exec.results.reportDownloadClient") }));
    expect(await report.findByText(/nesplnilo pravidla pro klienta/)).toBeTruthy();
    refuse = false;
    fireEvent.click(report.getByRole("button", { name: t("research.exec.results.reportDownloadClient") }));
    const approve = await report.findByRole("button", { name: t("research.exec.results.reportApprove") });
    fireEvent.click(approve);
    expect(await report.findByText("Stav: Schváleno pouze pro interní použití.")).toBeTruthy();
    const posted = called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/approve");
    expect(posted).toHaveLength(1);
    expect(posted[0].body).toEqual({ artifact_id: "ART-client", note: "" });
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
        new Response(new Blob(["%PDF-1.7"], { type: "application/pdf" }), { status: 200 }),
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

  it("approves the stored internal draft, and says so when its producer may not", async () => {
    let refuse = true;
    api({
      ...listed(reportRun()),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-5": () => SOCIOMAP,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => reportStatus(),
      "POST /api/v1/studies/STU-1/research/runs/RUN-1/report/approve": () => refuse
        ? new Response('{"code":"separation_of_duties","message":"independent review required"}', { status: 403 })
        : { run_id: "RUN-1", artifact_id: "ART-report", review_state: "APPROVED_INTERNAL", internal_only: true },
    });
    render(<ResearchScreen step="results" frame={TEST_FRAME} />);
    const report = await card();
    fireEvent.click(await report.findByRole("button", { name: t("research.exec.results.reportApprove") }));
    expect(await report.findByText(t("research.exec.results.reportApproveIndependent"))).toBeTruthy();
    refuse = false;
    fireEvent.click(report.getByRole("button", { name: t("research.exec.results.reportApprove") }));
    expect(await report.findByText("Stav: Schváleno pouze pro interní použití.")).toBeTruthy();
    expect(report.queryByRole("button", { name: t("research.exec.results.reportApprove") })).toBeNull();
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/approve")[1].body)
      .toEqual({ artifact_id: "ART-report", note: "" });
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
    const downloadReport = screen.getByRole("button", { name: "Stáhnout AIA zprávu s rešerší" }) as HTMLButtonElement;
    expect(downloadReport.disabled).toBe(true);
    fireEvent.click(downloadReport);
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
        { evidence: { evidence_id: "EV-1", claim: "Spotřeba čaje roste.\n- hlavně u mladých\n- ve městech", quote: "Čaj roste o 4 %.", source_ref: "SRC-1" }, score: { score: 0.8, source_class: "B" } },
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
    expect(within(first).getByText(/třída zdroje B/)).toBeTruthy();
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
  it("starts over the pinned analysis and downloads the report with the explicitly selected review", async () => {
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
    expect(screen.queryByRole("button", { name: "Stáhnout AIA zprávu s rešerší" })).toBeNull();
    fireEvent.click(start);
    expect(await screen.findByText("Studie popisuje hodnocení knihovních služeb.", { exact: true })).toBeTruthy();
    const unapproved = screen.getByText("Sociomapping není aplikovatelný na hodnocení služeb.");
    const draft = unapproved.closest("details");
    expect(draft?.open).toBe(false);
    expect(within(draft!).getByText("Generovaný návrh syntézy · věcně neschválený")).toBeTruthy();
    expect(called("POST", "/api/v1/studies/STU-1/deep-research/runs/interpretation")[0].body).toMatchObject({
      target: { kind: "ANALYSIS_MODULE", research_run_id: "RUN-1", analysis_artifact_id: "ART-questions", module_id: "research_questions" }, preset_name: "QUICK",
    });
    const downloadReport = screen.getByRole("button", { name: "Stáhnout AIA zprávu s rešerší" }) as HTMLButtonElement;
    await waitFor(() => expect(downloadReport.disabled).toBe(false));
    fireEvent.click(downloadReport);
    await waitFor(() => expect(createUrl).toHaveBeenCalled());
    expect(called("GET", "/api/v1/studies/STU-1/research/runs/RUN-1/report/context/download")[0].url).toContain("deep_research_run_id=RUN-deep");
    expect(called("POST", "/api/v1/studies/STU-1/research/runs")).toHaveLength(0);
    // The downloaded draft is the one approved: its artifact id, from the download's header.
    expect(await screen.findByText("Stažený dokument je koncept: schvalujete právě ten, který jste stáhli.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Schválit pro interní použití" }));
    expect(await screen.findByText("Stažený dokument je schválen pro interní použití.")).toBeTruthy();
    expect(called("POST", "/api/v1/studies/STU-1/research/runs/RUN-1/report/approve")[0].body).toEqual({ artifact_id: "ART-context", note: "" });
    expect(screen.queryByRole("button", { name: "Schválit pro interní použití" })).toBeNull();
  });
});
