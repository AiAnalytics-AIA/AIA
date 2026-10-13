// @vitest-environment jsdom
// A past research, read-only (plans/project-memory-reuse.md M2d): its revisions and what each says,
// the runs of the chosen one with their labels, a run's results; every request a read. A study of
// another client in the URL, or a simulation, is not here; a study with no revision shows its
// working draft, said to be a draft.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t, tv } from "@/i18n/t";
import { ClientValue } from "./clients/ClientContext";
import { MemoryStudy } from "./MemoryStudy";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-a/memory/STU-1", useRouter: () => ({ push, replace: vi.fn() }) }));

const S = "aia.memory.study";
const CLIENT = { client_id: "CLI-a", name: "Klient A", slug: "a", status: "ACTIVE", your_role: "RESEARCHER", permissions: [] };
const study = (over: Record<string, unknown> = {}) => ({
  study: {
    study_id: "STU-1", client_id: "CLI-a", name: "Ranní káva", slug: "ranni-kava", kind: "RESEARCH", status: "ACTIVE",
    accepts_work: true, last_stage: "results", has_working_content: true, content_state: "SAVED", created_at: null, modified_at: null, ...over,
  },
  client_name: "Klient A", your_role: "RESEARCHER", can_edit: true, content_state: "SAVED",
});
const revision = (n: number) => ({
  revision_id: `REV-${n}`, study_id: "STU-1", revision: n, content_sha256: "x", parent_revision: n > 1 ? n - 1 : null,
  source_stage: "run", created_by: "USR-1", created_at: "2026-10-0" + n + "T08:00:00Z",
});
const DESIGN = {
  title: "Ranní káva", goal: "Zjistit, zda nový nápoj dává smysl dojíždějícím.",
  research_plan: { research_questions: ["Kdo pije kávu ráno?"] },
  sections: [{ title: "Návyky" }],
  persona_dimensions: { approved: ["zdravi", "KNI-1"] },
};
const step = (node: string, kind: string, extra: Record<string, unknown> = {}) => ({
  node_key: node, kind, stage_type: "BRIEF", status: "SUCCEEDED", waiting_reason: null, attempts_recorded: 1, max_attempts: 3,
  started_at: null, finished_at: null, failure_class: null, error_message: null, artifact_id: null, data_origin: null, ...extra,
});
const RUN = {
  run_id: "RUN-1", study_id: "STU-1", design_revision_id: "REV-2", design_revision: 2, status: "COMPLETED", phase: "COMPLETED",
  needs_attention: false, is_terminal: true, retryable: false, cancel_requested: false, fieldwork_source: "ai_runtime",
  retry_of: null, created: null, created_at: "2026-10-02T09:00:00Z", started_at: null, finished_at: null, actual_cost_usd: null, population: null,
  steps: [
    step("run", "research_fieldwork", { artifact_id: "ART-3", data_origin: "SYNTHETIC_AI_FICTIONAL" }),
    step("aggregate", "research_aggregate", { artifact_id: "ART-4", data_origin: "SYNTHETIC_AI_FICTIONAL" }),
    step("report", "research_report", { artifact_id: "ART-r" }),
  ],
  artifact_ids: ["ART-3", "ART-4", "ART-r"],
};
const AGGREGATE = {
  artifact_id: "ART-4", artifact_type: "research_aggregate", stage_type: "AGGREGATION", revision: 2, content_type: "application/json",
  sha256: "abcdef0123456789", size_bytes: 10, status: "VALID", runtime_version: "x", produced_by_job_id: null, created_at: null,
  payload: { aggregate: { data_origin: "SYNTHETIC_AI_FICTIONAL", questions: {}, batteries: {} } },
};

type Call = { method: string; url: string; body: unknown };
let calls: Call[] = [];
function api(routes: Record<string, (body: unknown) => unknown>) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ method, url: u, body });
      const all: Record<string, (body: unknown) => unknown> = {
        "GET /config": () => ({ apiBase: "", aiRuntime: null }),
        "GET /api/v1/workspace/me": () => ({ user_id: "USR-1", email: "a@example.test", organization_role: "MEMBER", may_administer: false }),
        "GET /api/v1/workspace/clients": () => [],
        "GET /api/v1/clients/CLI-a/knowledge": () => [{ item_id: "KNI-1", kind: "DIMENSION", title: "Ranní rituály", summary: "", content: {}, revision: 1, modified_at: null }],
        ...routes,
      };
      const answer = all[`${method} ${u.split("?")[0]}`];
      if (!answer) return new Response(JSON.stringify({ code: "not_found" }), { status: 404 });
      const value = answer(body);
      return value instanceof Response ? value : new Response(JSON.stringify(value), { status: 200 });
    }),
  );
}

beforeEach(() => {
  push.mockReset();
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const page = () =>
  render(
    <ClientValue client={CLIENT}>
      <MemoryStudy studyId="STU-1" />
    </ClientValue>,
  );

describe("a past research in project memory", () => {
  it("shows what the newest revision says, its run's labels and results, and only reads", async () => {
    api({
      "GET /api/v1/studies/STU-1/workspace": () => study(),
      "GET /api/v1/studies/STU-1/design/revisions": () => ({ items: [revision(2), revision(1)] }),
      "GET /api/v1/studies/STU-1/design/revisions/REV-2": () => ({ ...revision(2), content: DESIGN }),
      "GET /api/v1/studies/STU-1/design/revisions/REV-1": () => ({ ...revision(1), content: { title: "Starší" } }),
      "GET /api/v1/studies/STU-1/research/runs": () => ({ items: [{ ...RUN, steps: [], artifact_ids: [] }] }),
      "GET /api/v1/studies/STU-1/research/runs/RUN-1": () => RUN,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/artifacts/ART-4": () => AGGREGATE,
      "GET /api/v1/studies/STU-1/research/runs/RUN-1/report": () => ({
        run_id: "RUN-1", state: "READY", internal_only: true, review_state: "DRAFT_UNAPPROVED", artifact_id: "ART-r", sha256: "abc", size_bytes: 1, synthetic: true,
      }),
    });
    page();
    expect(await screen.findByText("Kdo pije kávu ráno?")).toBeTruthy();
    expect(screen.getByText("Zdraví")).toBeTruthy();
    expect(screen.getByText("Ranní rituály")).toBeTruthy();
    const labels = await screen.findByRole("region", { name: t(`${S}.labels`) });
    expect(within(labels).getByText(t(`${S}.data.synthetic`))).toBeTruthy();
    expect(await within(labels).findByText(t(`${S}.report.draft`))).toBeTruthy();
    expect(within(labels).getByText(t(`${S}.internal`))).toBeTruthy();
    expect(await screen.findByText(/Fiktivní data\. Tento běh používá smyšlené respondenty/)).toBeTruthy();
    // Read-only: the report is neither downloaded nor approved from project memory.
    for (const name of [t("research.exec.results.reportDownload"), "Stáhnout zprávu", t("research.exec.results.reportApprove")]) {
      expect(screen.queryByRole("button", { name, hidden: true })).toBeNull();
    }

    // The older revision: what it said, and that it was never run.
    fireEvent.click(screen.getByRole("button", { name: new RegExp(tv(`${S}.revision`, { revision: 1 })) }));
    expect(await screen.findByText("Starší")).toBeTruthy();
    expect(await screen.findByText(t(`${S}.noRuns`))).toBeTruthy();

    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
    expect(calls.some((c) => c.url.includes("/workspace/content"))).toBe(false);
  });

  it("says a study without a revision has only a working draft, never a design", async () => {
    api({
      "GET /api/v1/studies/STU-1/workspace": () => study(),
      "GET /api/v1/studies/STU-1/design/revisions": () => ({ items: [] }),
      "GET /api/v1/studies/STU-1/workspace/content": () => ({ study_id: "STU-1", state: "SAVED", content: DESIGN, can_edit: true }),
    });
    page();
    expect(await screen.findByText(t(`${S}.draft`))).toBeTruthy();
    expect(screen.getByText("Kdo pije kávu ráno?")).toBeTruthy();
    expect(screen.queryByText(t(`${S}.runs`))).toBeNull();
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
  });

  it("is not here for a study of another client, or a simulation", async () => {
    for (const over of [{ client_id: "CLI-b" }, { kind: "SIMULATION" }]) {
      api({ "GET /api/v1/studies/STU-1/workspace": () => study(over) });
      page();
      expect(await screen.findByText(t("aia.notFoundTitle"))).toBeTruthy();
      expect(calls.some((c) => c.url.includes("/design/revisions") || c.url.includes("/research/runs"))).toBe(false);
      cleanup();
    }
  });
});

describe("using a past design (M3e)", () => {
  const routes = (reuse: (body: unknown) => unknown) => ({
    "GET /api/v1/studies/STU-1/workspace": () => study(),
    "GET /api/v1/studies/STU-1/design/revisions": () => ({ items: [revision(2)] }),
    "GET /api/v1/studies/STU-1/design/revisions/REV-2": () => ({ ...revision(2), content: DESIGN }),
    "GET /api/v1/studies/STU-1/research/runs": () => ({ items: [] }),
    "GET /api/v1/clients/CLI-a/studies": () => [
      { ...study().study, study_id: "STU-9", name: "Prázdný", has_working_content: false, content_state: "EMPTY" },
      { ...study().study, study_id: "STU-8", name: "Rozepsaný", has_working_content: true, content_state: "NATIVE" },
    ],
    "POST /api/v1/clients/CLI-a/memory/reuse": reuse,
  });

  it("starts a new study from the chosen revision and opens it", async () => {
    api(routes(() => ({ study_id: "STU-NEW", created_study: true })));
    page();
    const name = await screen.findByLabelText(t(`${S}.reuse.name`));
    fireEvent.change(name, { target: { value: "Ranní káva 2" } });
    fireEvent.click(screen.getByRole("button", { name: t(`${S}.reuse.start`) }));
    await vi.waitFor(() => expect(push).toHaveBeenCalledWith("/app/clients/CLI-a/research/STU-NEW"));
    const posted = calls.filter((c) => c.method === "POST");
    expect(posted.map((c) => c.body)).toEqual([{ source_study_id: "STU-1", source_revision_id: "REV-2", new_study_name: "Ranní káva 2" }]);
  });

  it("offers only the client's empty studies, and says why the server refused one", async () => {
    api(routes(() => new Response(JSON.stringify({ code: "target_not_empty", message: "x" }), { status: 409 })));
    page();
    fireEvent.click(await screen.findByLabelText(t(`${S}.reuse.intoEmpty`)));
    const select = (await screen.findByLabelText(t(`${S}.reuse.empty`))) as HTMLSelectElement;
    expect([...select.options].map((o) => o.textContent)).toEqual(["—", "Prázdný"]);
    fireEvent.change(select, { target: { value: "STU-9" } });
    fireEvent.click(screen.getByRole("button", { name: t(`${S}.reuse.start`) }));
    expect(await screen.findByText(t(`${S}.reuse.refused.target_not_empty`))).toBeTruthy();
    expect(push).not.toHaveBeenCalled();
    expect(calls.filter((c) => c.method === "POST").map((c) => c.body)).toEqual([{ source_study_id: "STU-1", source_revision_id: "REV-2", target_study_id: "STU-9" }]);
  });
});
