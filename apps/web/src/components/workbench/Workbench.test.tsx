// @vitest-environment jsdom
// The workbench's automatic text edits (plan inline-decisions chunk 2): off by default; on, a turn
// that finishes has its wording edits accepted through the server's gate, marked automatic, shown
// as "Přijato automaticky" with Vrátit, while its structural edits wait as change blocks.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LeadState, LeadTurn, ResearcherLead } from "@/lib/lead";
import type { ResearchProject } from "@/research/model";
import { ResearchStore } from "@/research/store";
import { TEST_FRAME } from "../rehome/research/test-frame";
import { EMPTY_PROJECT } from "../rehome/research/test-workspace";
import { Workbench } from "./Workbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/app" }));

const project = (text: string): ResearchProject =>
  ({ ...EMPTY_PROJECT, sections: [{ id: "s1", type: "questions", title: "Hlavní", purpose: "", questions: [{ id: "q1", text, typ: "otevrena" }] }] }) as unknown as ResearchProject;

const WHY = "Srozumitelnější.";
const EDITS = [
  { op: "question_edit" as const, question_id: "q1", text: "Znáte značku?", options: null, why: WHY },
  { op: "question_add" as const, section_id: null, text: "Kolik?", qtype: "otevrena" as const, options: [], why: WHY },
];
const leadTurn = (over: Partial<LeadTurn>): LeadTurn => ({
  turn_id: "LDT-1", sequence_no: 2, actor: "lead", kind: "message", stage: "questionnaire", text: null, focus: null,
  status: "RUNNING", reason: null, output: null, run_id: "RUN-1", workspace_revision: 3, created_at: "2026-10-19T08:00:00Z", created_by: "USR-1",
  ...over,
});

let auto: boolean;
let reads: number;
let state: LeadState;
let decided: unknown[];
let saves: unknown[];

function me(): ResearcherLead {
  return {
    hatched: true,
    lead: {
      lead_id: "LEAD-1", name: "Bára", hatched_at: "2026-10-19T08:00:00Z", updated_at: "2026-10-19T08:00:00Z",
      files: { soul: "", user: "" }, memories: [], ...(auto ? { preferences: { auto_accept_text_edits: true } } : {}),
    },
  };
}

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
  auto = false;
  reads = 0;
  decided = [];
  saves = [];
  let revision = 3;
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url).split("?")[0]!;
    const method = init?.method ?? "GET";
    if (u === "/config") return new Response(JSON.stringify({ apiBase: "", aiRuntime: null }));
    if (u === "/api/v1/lead") return new Response(JSON.stringify(me()));
    if (u.endsWith("/workspace/content") && method === "PUT") {
      saves.push(JSON.parse(String(init?.body)));
      revision += 1;
      return new Response(JSON.stringify({ study_id: "STU-1", state: "NATIVE", revision, revision_id: `REV-${revision}`, deduplicated: false }));
    }
    if (u.endsWith("/lead/turns/LDT-1/edits")) {
      const body = JSON.parse(String(init?.body)) as { indices: number[]; auto?: boolean };
      decided.push(body);
      revision += 1;
      // The server's gate: only wording is taken automatically; the rest stays undecided.
      const results = body.indices.map((i) => (body.auto && i !== 0 ? { index: i, status: "refused", reason: "not_a_text_edit" } : { index: i, status: "accepted", reason: null }));
      const accepted = Object.fromEntries(results.filter((r) => r.status === "accepted").map((r) => [String(r.index), { status: "accepted" as const, reason: null, auto: !!body.auto }]));
      state = { ...state, turns: state.turns.map((t) => ({ ...t, edit_decisions: { ...(t.edit_decisions ?? {}), ...accepted } })) };
      return new Response(JSON.stringify({ workspace_revision: revision, results }));
    }
    if (u.endsWith("/lead/turns")) return new Response(JSON.stringify({ turns: [] }));
    if (u.endsWith("/lead")) {
      reads += 1;
      // The turn is running when the screen first reads the conversation, and finishes after.
      if (reads > 1) state = { ...state, busy: false, turns: state.turns.map((t) => ({ ...t, status: "COMPLETED", output: { reply: "Upravil bych otázky.", edits: EDITS } })) };
      return new Response(JSON.stringify(state));
    }
    if (u.endsWith("/research/runs")) return new Response(JSON.stringify([]));
    if (u === "/api/v1/studies/STU-1") return new Response(JSON.stringify({ study_id: "STU-1", budget_usd: null, spent_usd: null }));
    return new Response(JSON.stringify({ code: "not_found" }), { status: 404 });
  }));
  state = { available: true, unavailable_reason: null, busy: true, turns: [leadTurn({})] };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function bench() {
  const store = new ResearchStore({ revision: 3, project: project("Znáte?"), analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
  // The stage's reload reads the working copy the server wrote.
  const reload = vi.fn(() => store.replace({ project: project("Znáte značku?") }));
  render(
    <Workbench frame={TEST_FRAME} step="questionnaire" store={store} save={null} inspector={null} reload={reload} confirm={vi.fn(async () => true)}
      onAgentStarted={vi.fn()} jobs={[]} onOpenJob={vi.fn()} onRefreshJobs={vi.fn(async () => [])}>
      <div>Dotazník</div>
    </Workbench>,
  );
  return { store, reload };
}

const questionText = (s: ResearchStore) => (s.get().project as unknown as { sections: { questions: { text: string }[] }[] }).sections[0]!.questions[0]!.text;

describe("automatic text edits", () => {
  it("are off by default: every edit waits as a change block and nothing is accepted", async () => {
    bench();
    const blocks = await screen.findByRole("region", { name: "Návrhy Vedoucího" }, { timeout: 4000 });
    expect(within(blocks).getAllByRole("button", { name: "Přijmout" })).toHaveLength(2);
    expect(decided).toEqual([]);
    expect(screen.queryByRole("region", { name: "Přijato automaticky" })).toBeNull();
  });

  it("on, accept only the wording through the gate as automatic; structure stays a block, and Vrátit puts the wording back", async () => {
    auto = true;
    const { store, reload } = bench();
    const applied = await screen.findByRole("region", { name: "Přijato automaticky" }, { timeout: 4000 });
    expect(decided).toEqual([{ decision: "accept", indices: [0], base_revision: 4, auto: true }]);
    expect(reload).toHaveBeenCalled();
    expect(within(applied).getByText(/Dotazník · upravit otázku · Přijato automaticky \(vaše nastavení\)/)).toBeTruthy();
    expect(within(applied).getByText("Znáte?")).toBeTruthy();
    // The question added is structure: it waits for the researcher's click.
    const blocks = await screen.findByRole("region", { name: "Návrhy Vedoucího" });
    expect(within(blocks).getAllByRole("button", { name: "Přijmout" })).toHaveLength(1);
    expect(within(blocks).getByText("Kolik?")).toBeTruthy();

    expect(questionText(store)).toBe("Znáte značku?");
    fireEvent.click(within(applied).getByRole("button", { name: "Vrátit" }));
    expect(questionText(store)).toBe("Znáte?");
    expect(screen.queryByRole("region", { name: "Přijato automaticky" })).toBeNull();
    // The revert is the person's own edit, saved through the normal revision-checked save.
    await waitFor(() => expect(saves.length).toBeGreaterThan(1), { timeout: 4000 });
  });
});
