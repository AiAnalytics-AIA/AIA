// @vitest-environment jsdom
// In the workbench the Research Lead owns every AI start (plan research-lead-workbench D15, chunk
// 23): no AI pomoc, no stage "Navrhnout", no job dialog; each stage says to ask the Lead instead.
// Spuštění's own Start is not a worker start and stays. A file of its own: the workbench switch,
// once read, is kept for the page, so it would leak into the classic layout's tests.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { ResearchScreen } from "./ResearchScreen";
import { TEST_FRAME } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/persona", useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

const urls: string[] = [];
function api() {
  urls.length = 0;
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("min-width: 1100px"), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    urls.push(`${method} ${u}`);
    const answer =
      u === "/config" ? { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", workbench: true }
      : u === CONTENT_PATH && method === "GET" ? { study_id: "STU-1", state: "NATIVE", revision: 2, revision_id: "REV-2", content: { title: "Alfa", goal: "Zjistit, co lidé chtějí od nové služby." }, analysis: null, template: EMPTY_PROJECT, saved_at: null, saved_by: null, can_edit: true, lineage: {} }
      : u === CONTENT_PATH ? { state: "NATIVE", revision: 3, revision_id: "REV-3", deduplicated: false }
      : u.endsWith("/research/readiness") ? { design_revision_id: "REV-3", revision: 3, ready: false, checks: [], questions: 0, batteries: 0, objects: 0, n: 0, rules: "test", fieldwork_source: "ai_runtime" }
      : u.endsWith("/research/runs") ? { items: [] }
      : u.endsWith("/design/revisions") && method === "POST" ? { revision_id: "REV-3", revision: 3 }
      : u.endsWith("/research/agent-jobs") ? []
      : u === "/api/v1/lead" ? { hatched: true, lead: { lead_id: "L", name: "Bára", hatched_at: "", updated_at: "", files: { soul: "", user: "" }, memories: [] } }
      : u.endsWith("/lead") ? { available: true, unavailable_reason: null, busy: false, turns: [] }
      : null;
    return answer === null
      ? new Response(JSON.stringify({ code: "not_found", message: "not here" }), { status: 404 })
      : new Response(JSON.stringify(answer), { status: 200 });
  }));
}

beforeEach(() => {
  signedIn();
  api();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const aiStarts = () => Array.from(document.querySelectorAll("#artbody [data-ai-action]"));

describe("the workbench: the Lead owns the AI starts", () => {
  for (const step of ["brief", "questionnaire", "audience", "persona"] as const) {
    it(`draws ${step} with no AI start of its own and no AI pomoc`, async () => {
      render(<ResearchScreen step={step} frame={TEST_FRAME} />);
      await screen.findByText("Bára");
      expect(document.querySelector("[data-workbench]")).not.toBeNull();
      expect(screen.queryByRole("region", { name: t("research.aiHelpLabel") })).toBeNull();
      expect(aiStarts()).toEqual([]);
      expect(urls.some((u) => u.startsWith("POST") && u.includes("/agent-jobs"))).toBe(false);
    });
  }

  it("says on Dimenze where the dimensions' proposal is asked for now", async () => {
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    expect(await screen.findByText(/Návrh dimenzí připraví Vedoucí výzkumu/)).toBeTruthy();
  });

  it("keeps Spuštění's own Start: a research run is not a worker start", async () => {
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByRole("button", { name: t("research.exec.start") })).toBeTruthy();
  });
});
