// @vitest-environment jsdom
// AIA's questionnaire template on Dotazník in the workbench, for a table given to the Lead (LO18b):
// downloaded through the study, a refusal said in Czech by its code. A file of its own: the
// workbench switch, once read, is kept for the page.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchScreen } from "./ResearchScreen";
import { TEST_FRAME } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

const saved: string[] = [];
vi.mock("@/lib/download", () => ({ saveBlob: (_blob: Blob, name: string) => { saved.push(name); } }));
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

const urls: string[] = [];
const bodies: { url: string; body: Record<string, unknown> }[] = [];
let stored: Record<string, unknown> = {};
let templateRefused = false;
function api(content: Record<string, unknown> = { title: "Alfa", goal: "Zjistit, co lidé chtějí od nové služby." }, analysis: Record<string, unknown> | null = null) {
  urls.length = 0;
  bodies.length = 0;
  stored = content;
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("min-width: 1100px"), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    urls.push(`${method} ${u}`);
    if (init?.body) bodies.push({ url: `${method} ${u}`, body: JSON.parse(String(init.body)) as Record<string, unknown> });
    const answer =
      u === "/config" ? { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", workbench: true }
      : u === CONTENT_PATH && method === "GET" ? { study_id: "STU-1", state: "NATIVE", revision: 2, revision_id: "REV-2", content: stored, analysis, template: EMPTY_PROJECT, saved_at: null, saved_by: null, can_edit: true, lineage: {} }
      : u === CONTENT_PATH ? { state: "NATIVE", revision: 3, revision_id: "REV-3", deduplicated: false }
      : u.endsWith("/research/readiness") ? { design_revision_id: "REV-3", revision: 3, ready: false, checks: [], questions: 0, batteries: 0, objects: 0, n: 0, rules: "test", fieldwork_source: "ai_runtime" }
      : u.endsWith("/research/runs") ? { items: [] }
      : u.endsWith("/design/revisions") && method === "POST" ? { revision_id: "REV-3", revision: 3 }
      : u.endsWith("/research/agent-jobs") ? []
      : u.endsWith("/workspace/questionnaire-template") ? (templateRefused ? null : "PK")
      : u === "/api/v1/lead" ? { hatched: true, lead: { lead_id: "L", name: "Bára", hatched_at: "", updated_at: "", files: { soul: "", user: "" }, memories: [] } }
      : u.endsWith("/lead/turns") && method === "POST" ? { turns: [] }
      : u.endsWith("/lead") ? { available: true, unavailable_reason: null, busy: false, turns: [] }
      : null;
    if (answer === null) return new Response(JSON.stringify({ code: "not_found", message: "not here" }), { status: 404 });
    return typeof answer === "string" ? new Response(answer, { status: 200 }) : new Response(JSON.stringify(answer), { status: 200 });
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

describe("the questionnaire template, in the workbench", () => {
  it("downloads AIA's template through the study and says what to do with it", async () => {
    templateRefused = false;
    saved.length = 0;
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Stáhnout šablonu XLSX/ }));
    await waitFor(() => expect(saved).toEqual(["AIA_dotaznik_sablona.xlsx"]));
    expect(urls).toContain("GET /api/v1/studies/STU-1/workspace/questionnaire-template");
    expect(screen.getByText(/přiložte ke zprávě Vedoucímu výzkumu/)).toBeTruthy();
  });

  it("says a template the API would not give in Czech, by its code", async () => {
    templateRefused = true;
    saved.length = 0;
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    fireEvent.click(await screen.findByRole("button", { name: /Stáhnout šablonu XLSX/ }));
    expect(await screen.findByText("Šablonu se nepodařilo stáhnout (kód not_found)")).toBeTruthy();
    expect(saved).toEqual([]);
  });
});
