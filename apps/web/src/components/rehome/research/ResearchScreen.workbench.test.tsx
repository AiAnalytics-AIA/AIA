// @vitest-environment jsdom
// In the workbench the Research Lead owns every AI start (plan research-lead-workbench D15, chunk
// 23): no AI pomoc, no stage "Navrhnout", no job dialog; each stage says to ask the Lead instead.
// Spuštění's own Start is not a worker start and stays. A file of its own: the workbench switch,
// once read, is kept for the page, so it would leak into the classic layout's tests.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { ResearchScreen } from "./ResearchScreen";
import { TEST_FRAME } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/persona", useRouter: () => ({ replace: vi.fn(), push }) }));

const urls: string[] = [];
const bodies: { url: string; body: Record<string, unknown> }[] = [];
let stored: Record<string, unknown> = {};
let runs: Record<string, unknown>[] = [];
function api(content: Record<string, unknown> = { title: "Alfa", goal: "Zjistit, co lidé chtějí od nové služby." }, analysis: Record<string, unknown> | null = null, designRuns: Record<string, unknown>[] = []) {
  urls.length = 0;
  runs = designRuns;
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
      : u.endsWith("/deep-research/runs") ? runs
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

  it("goes on from Zadání to Návrh through the frame, so Návrh's heading takes the focus (Codex stand-in on #714)", async () => {
    push.mockClear();
    render(<ResearchScreen step="brief" frame={TEST_FRAME} />);
    await screen.findByText("Bára");
    fireEvent.click(screen.getByRole("button", { name: /Připravenost a pomoc/ }));
    // A button the frame answers, not a bare link: a link would skip the frame's heading focus.
    fireEvent.click(await screen.findByRole("button", { name: "Pokračovat na Návrh" }));
    await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
    expect(push.mock.calls[0][0]).toMatch(/\/plan$/);
  });

  it("says on Dimenze where the dimensions' proposal is asked for now", async () => {
    render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    const hint = await screen.findByText(/Návrh dimenzí připraví Vedoucí výzkumu/);
    // Right at every width: below 1100 px the conversation is a drawer or a sheet, not "vlevo".
    expect(hint.textContent).not.toMatch(/vlevo/);
  });

  it("saves Návrh's comments for the Lead, with no AI call, and asks the Lead in words on a click", async () => {
    api({ title: "Alfa", goal: "Zjistit, co lidé chtějí od nové služby.", ui_state: { plan_comments26: [{ quote: "cíl", comment: "zúžit na Prahu" }] } }, { problem_summary: "Jde o test.", objectives: ["Změřit zájem"], hypotheses: [], research_questions: [], tracked_sets: [] });
    render(<ResearchScreen step="plan" frame={TEST_FRAME} />);
    await screen.findByText("Bára");
    expect(screen.queryByRole("button", { name: t("research.plan.commentsProcess") })).toBeNull();
    fireEvent.click(await screen.findByRole("button", { name: "Uložit komentáře" }));
    expect(await screen.findByText(/Komentáře jsou uložené; návrh podle nich aktualizuje Vedoucí výzkumu/)).toBeTruthy();
    await waitFor(() => {
      const saved = bodies.filter((b) => b.url === `PUT ${CONTENT_PATH}`).at(-1)?.body.content as { briefing?: { review_comments?: string }; ui_state?: { plan_changed26?: boolean } } | undefined;
      expect(saved?.briefing?.review_comments).toBe("1. K textu „cíl“: zúžit na Prahu");
      expect(saved?.ui_state?.plan_changed26).toBe(true);
    });
    fireEvent.click(screen.getByRole("button", { name: "Požádat Vedoucího" }));
    await waitFor(() => expect(bodies.some((b) => b.url.endsWith("/lead/turns") && b.body.text === "Aktualizuj návrh podle mých komentářů.")).toBe(true));
    // The Lead answers with its card; nothing paid starts from the stage.
    expect(urls.some((u) => u.startsWith("POST") && (u.includes("/agent-jobs") || u.endsWith("/request")))).toBe(false);
  });

  it("leaves Design Research to the Lead on Dotazník: no start or retry of its own, the runs still read (QF-13)", async () => {
    const failed = { run_id: "DR-1", purpose: "DESIGN_RESEARCH", phase: "FAILED", status: "FAILED", is_terminal: true, retryable: true, steps: [], created_at: null };
    api({ title: "Alfa", sections: [{ id: "s", type: "questions", title: "Blok", questions: [{ id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně"] }] }], ui_state: { questionnaire_path: "manual" } }, null, [failed]);
    render(<ResearchScreen step="questionnaire" frame={TEST_FRAME} />);
    await screen.findByText(/^Rešerši připraví Vedoucí výzkumu/);
    // The run is read, with its state: only its start and retry are the Lead's.
    await screen.findByRole("button", { name: "Nový běh" });
    expect(screen.getByText(/^Stav: /)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Spustit veřejný výzkum" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Opakovat běh" })).toBeNull();
  });

  it("keeps Spuštění's own Start: a research run is not a worker start", async () => {
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByRole("button", { name: t("research.exec.start") })).toBeTruthy();
  });
});
