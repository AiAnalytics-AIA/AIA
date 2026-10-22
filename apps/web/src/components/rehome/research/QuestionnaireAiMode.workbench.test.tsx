// @vitest-environment jsdom
// "Sestavit s AI" on a questionnaire that already has items (artifact-questionnaire QF-4): the AI
// does not build it anew, so the choice says so and, in the workbench, asks the Lead in one click.
// A file of its own: the workbench switch, once read, is kept for the page.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchScreen } from "./ResearchScreen";
import { TEST_FRAME } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

const urls: string[] = [];
const bodies: { url: string; body: Record<string, unknown> }[] = [];
let stored: Record<string, unknown> = {};
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
      : u === "/api/v1/lead" ? { hatched: true, lead: { lead_id: "L", name: "Bára", hatched_at: "", updated_at: "", files: { soul: "", user: "" }, memories: [] } }
      : u.endsWith("/lead/turns") && method === "POST" ? { turns: [] }
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

const SECTIONS = [{ id: "sec_a", type: "questions", title: "Hlavní otázky", questions: [{ id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] }] }];

beforeEach(() => {
  signedIn();
  api({ title: "Alfa", goal: "Zjistit zájem.", sections: SECTIONS, ui_state: { questionnaire_path: "manual" } });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("Sestavit s AI on a questionnaire with items, in the workbench", () => {
  it("says the AI will not build it anew and asks the Lead for changes in words", async () => {
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByText("Bára");
    expect(screen.queryByText(/takže ho AI znovu nesestaví/)).toBeNull();
    fireEvent.click(await screen.findByRole("radio", { name: "Sestavit s AI" }));
    expect(await screen.findByText(/úpravy těch, které tu jsou, navrhne Vedoucí výzkumu/)).toBeTruthy();
    // The questionnaire stays as it was, in the editor.
    expect(screen.getByDisplayValue("Jak často?")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Požádat Vedoucího" }));
    await waitFor(() => expect(bodies.some((b) => b.url.endsWith("/lead/turns") && b.body.text === "Navrhni úpravy dotazníku.")).toBe(true));
    expect(urls.some((u) => u.startsWith("POST") && (u.includes("/agent-jobs") || u.endsWith("/request")))).toBe(false);
  });
});
