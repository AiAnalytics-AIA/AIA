// @vitest-environment jsdom
// In the workbench the Research Lead owns every AI start (plan research-lead-workbench D15, chunk
// 23): no AI pomoc, no stage "Navrhnout", no job dialog; each stage says to ask the Lead instead.
// Spuštění's own Start is not a worker start and stays. A file of its own: the workbench switch,
// once read, is kept for the page, so it would leak into the classic layout's tests.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { t } from "@/i18n/t";
import { resetConfigCache } from "@/lib/auth";
import { ResearchScreen, ResearchSession, resetWorkbenchSwitch } from "./ResearchScreen";
import { TEST_FRAME } from "./test-frame";
import { CONTENT_PATH, EMPTY_PROJECT, signedIn } from "./test-workspace";

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ usePathname: () => "/app/clients/CLI-1/research/STU-1/persona", useRouter: () => ({ replace: vi.fn(), push }) }));

const urls: string[] = [];
const bodies: { url: string; body: Record<string, unknown> }[] = [];
let stored: Record<string, unknown> = {};
/** /config never answers: a proxy stall or a slow cold start. */
let configHangs = false;
/** The Lead's state, read in turn (the last one kept); null: no turns. */
let leadAnswers: object[] | null = null;
/** What GET …/agent-jobs?pending=true answers. */
let pendingAnswer: object[] = [];
function api(content: Record<string, unknown> = { title: "Alfa", goal: "Zjistit, co lidé chtějí od nové služby." }, analysis: Record<string, unknown> | null = null) {
  urls.length = 0;
  bodies.length = 0;
  stored = content;
  vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("min-width: 1100px"), media: q, addEventListener: () => {}, removeEventListener: () => {} }));
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0];
    const method = init?.method ?? "GET";
    if (u === "/config" && configHangs) return new Promise<Response>(() => {});
    urls.push(`${method} ${u}`);
    if (init?.body) bodies.push({ url: `${method} ${u}`, body: JSON.parse(String(init.body)) as Record<string, unknown> });
    const answer =
      u === "/config" ? { apiBase: "", cognitoDomain: "", cognitoClientId: "", publicOrigin: "http://localhost", workbench: true }
      : u === CONTENT_PATH && method === "GET" ? { study_id: "STU-1", state: "NATIVE", revision: 2, revision_id: "REV-2", content: stored, analysis, template: EMPTY_PROJECT, saved_at: null, saved_by: null, can_edit: true, lineage: {} }
      : u === CONTENT_PATH ? { state: "NATIVE", revision: 3, revision_id: "REV-3", deduplicated: false }
      : u.endsWith("/research/readiness") ? { design_revision_id: "REV-3", revision: 3, ready: false, checks: [], questions: 0, batteries: 0, objects: 0, n: 0, rules: "test", fieldwork_source: "ai_runtime" }
      : u.endsWith("/research/limits") ? { methodology_version: "aia-readiness-1", version: null, sample_size: { min: 20, max: 10000 } }
      : u.endsWith("/research/runs") ? { items: [] }
      : u.endsWith("/design/revisions") && method === "POST" ? { revision_id: "REV-3", revision: 3 }
      : u.endsWith("/research/agent-jobs") ? (String(url).includes("pending=true") ? pendingAnswer : [])
      : u.endsWith("/result") ? { result: { project: {}, proposal: {} }, provenance: { agent_id: "aia.research.optimize", design_revision_id: "REV-2", context_sha256: "0".repeat(64), status: "COMPLETED" } }
      : u === "/api/v1/lead" ? { hatched: true, lead: { lead_id: "L", name: "Bára", hatched_at: "", updated_at: "", files: { soul: "", user: "" }, memories: [] } }
      : u.endsWith("/lead/turns") && method === "POST" ? { turns: [] }
      : u.endsWith("/lead") ? (leadAnswers ? (leadAnswers.length > 1 ? leadAnswers.shift() : leadAnswers[0]) : { available: true, unavailable_reason: null, busy: false, turns: [] })
      : null;
    return answer === null
      ? new Response(JSON.stringify({ code: "not_found", message: "not here" }), { status: 404 })
      : new Response(JSON.stringify(answer), { status: 200 });
  }));
}

beforeEach(() => {
  // Each test is a fresh page: the switch and /config read anew, never left by an earlier test.
  resetWorkbenchSwitch();
  resetConfigCache();
  configHangs = false;
  leadAnswers = null;
  pendingAnswer = [];
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

  it("opens on its own stage a proposal the Lead's show_diff found older than the newest page (stand-in review on #809)", async () => {
    push.mockClear();
    const turn = (id: string, seq: number, view: object[] = []) => ({
      turn_id: id, sequence_no: seq, actor: "lead", kind: "message", stage: "brief", text: null, focus: null, status: "COMPLETED", reason: null,
      output: { reply: "Tady jsou změny.", view }, run_id: null, workspace_revision: 2, created_at: "2026-10-23T08:00:00Z", created_by: null,
    });
    const lead = (busy: boolean, turns: object[]) => ({ available: true, unavailable_reason: null, busy, turns });
    leadAnswers = [lead(true, [turn("T1", 1)]), lead(false, [turn("T1", 1), turn("T2", 2, [{ op: "show_diff", stage: "questionnaire" }])])];
    pendingAnswer = [{ run_id: "RUN-old", action: "optimize_questionnaire", proposal_state: "pending", created_at: "2026-10-01T09:00:00Z", status: "COMPLETED", is_terminal: true, steps: [] }];
    // The study's layout holds the session, as ResearchStudy does; the route change remounts the stage.
    const view = render(<ResearchSession studyId="STU-1"><ResearchScreen key="brief" step="brief" frame={TEST_FRAME} /></ResearchSession>);
    await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
    expect(String(push.mock.calls[0][0])).toContain("questionnaire");
    view.rerender(<ResearchSession studyId="STU-1"><ResearchScreen key="questionnaire" step="questionnaire" frame={TEST_FRAME} /></ResearchSession>);
    await waitFor(() => expect(urls).toContain("GET /api/v1/studies/STU-1/research/agent-jobs/RUN-old/result"));
  });

  it("mounts a stage once on a fresh page, not the classic layout first and then the workbench", async () => {
    const { container } = render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    await waitFor(() => expect(container.querySelector("[data-workbench]")).not.toBeNull());
    await new Promise((r) => setTimeout(r, 1500));
    // The stage's reads once: the classic layout, mounted while the switch was unknown, read them too.
    expect(urls.filter((u) => u.endsWith("/design/source"))).toHaveLength(1);
    expect(container.querySelector("[data-research-workspace]")).toBeNull();
  });

  it("is never blank while /config does not answer: the stage's chrome says it is loading, and no layout mounts", async () => {
    configHangs = true;
    const { container } = render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
    expect(await screen.findByText(t("research.loading"))).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Kde jste" })).toBeTruthy();
    await new Promise((r) => setTimeout(r, 1500));
    // Every read waits on /config (lib/api.ts), so nothing of either layout is read or mounted.
    expect(urls.filter((u) => u.endsWith("/design/source"))).toHaveLength(0);
    expect(container.querySelector("[data-workbench], [data-research-workspace]")).toBeNull();
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

  it("sets n on Vzorek, within the server's limits, and not on Dimenze (artifact-sample SMP7, artifact-dimensions DIM3b)", async () => {
    api({ title: "Alfa", goal: "Zjistit, co lidé chtějí od nové služby.", n: 350 });
    window.location.hash = "#sample";
    try {
      render(<ResearchScreen step="persona" frame={TEST_FRAME} />);
      const view = await screen.findByLabelText("Vzorek", { selector: "[data-sample-view]" });
      const field = () => within(view).getByRole("spinbutton", { name: "Počet respondentů" });
      await within(view).findByRole("spinbutton", { name: "Počet respondentů" });
      expect(field().closest("[data-aia='sample:n']")).not.toBeNull();
      expect(document.querySelectorAll("[data-aia='sample:n']")).toHaveLength(1);
      expect(within(view).queryByRole("button", { name: "Upravit v Dimenzích" })).toBeNull();
      fireEvent.click(within(view).getByRole("button", { name: "Zvýšit: Počet respondentů" }));
      await waitFor(() => expect((bodies.filter((b) => b.url === `PUT ${CONTENT_PATH}`).at(-1)?.body.content as { n?: unknown } | undefined)?.n).toBe(400), { timeout: 10_000 });
      // The Stepper remounts on the saved value; the field is read again.
      const puts = bodies.length;
      fireEvent.change(field(), { target: { value: "10001" } });
      fireEvent.blur(field());
      expect((await within(field().closest("[data-aia='sample:n']") as HTMLElement).findByRole("alert")).textContent).toMatch(/neuloženo/);
      await new Promise((r) => setTimeout(r, 2_100)); // past the store's 1.8 s save
      expect(bodies.slice(puts).filter((b) => b.url === `PUT ${CONTENT_PATH}` && (b.body.content as { n?: unknown }).n === 10001)).toEqual([]);
    } finally {
      window.location.hash = "";
    }
  }, 30_000);

  it("keeps Spuštění's own Start: a research run is not a worker start", async () => {
    render(<ResearchScreen step="run" frame={TEST_FRAME} />);
    expect(await screen.findByRole("button", { name: t("research.exec.start") })).toBeTruthy();
  });
});
