// @vitest-environment jsdom
// Dotazník in the workbench: one editor, one way in (the product owner, 2026-10-26). Whatever path a
// study stored, the stage draws the editor; a file or a draft comes from the Lead, and the stage
// starts no AI of its own. A file of its own: the workbench switch, once read, is kept for the page.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchScreen } from "./ResearchScreen";
import { TEST_FRAME } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/questionnaire", useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

const urls: string[] = [];
let stored: Record<string, unknown> = {};
function api(content: Record<string, unknown>) {
  urls.length = 0;
  stored = content;
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("min-width: 1100px"), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    urls.push(`${method} ${u}`);
    const answer =
      u === "/config" ? { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", workbench: true }
      : u === CONTENT_PATH && method === "GET" ? { study_id: "STU-1", state: "NATIVE", revision: 2, revision_id: "REV-2", content: stored, analysis: null, template: EMPTY_PROJECT, saved_at: null, saved_by: null, can_edit: true, lineage: {} }
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
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const SECTIONS = [{ id: "sec_a", type: "questions", title: "Hlavní otázky", questions: [{ id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] }] }];

describe("Dotazník in the workbench", () => {
  for (const path of ["choose", "upload", "ai"]) {
    it(`draws the editor for a study stored at "${path}", with no path, file or build of its own`, async () => {
      api({ title: "Alfa", goal: "Zjistit zájem.", sections: SECTIONS, ui_state: { questionnaire_path: path } });
      render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
      await screen.findByText("Bára");
      expect(await screen.findByDisplayValue("Jak často?")).toBeTruthy();
      for (const gone of ["Nahrát Excel", "Sestavit ručně", "Sestavit s AI", "Optimalizovat dotazník s AI"]) expect(screen.queryByText(gone)).toBeNull();
      expect(screen.queryByLabelText("Vyplněný XLSX / CSV")).toBeNull();
      expect(urls.some((u) => u.startsWith("POST") && (u.includes("/agent-jobs") || u.includes("questionnaire-import")))).toBe(false);
    });
  }
});
