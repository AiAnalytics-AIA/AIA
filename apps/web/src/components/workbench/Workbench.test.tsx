// @vitest-environment jsdom
// The workbench's automatic text edits (plan inline-decisions chunk 2): off by default; on, a turn
// that finishes has its wording edits accepted through the server's gate, marked automatic, shown
// as "Přijato automaticky" with Vrátit, while its structural edits wait as change blocks. The copy
// is read again in place, asynchronously; a change the person makes meanwhile is never dropped, and
// the bar lives in the study's page memory, so a stage change keeps it.
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
/** What the working copy's GET answers: the server's own write after an accept. */
let held: { project: ResearchProject; revision: number };
let contentReads: number;
/** Held open until released: the gate's answer, the working copy's read. */
let editsGate: Promise<void> | null;
let contentGate: Promise<void> | null;
/** Run while the gate is answering: the person typing meanwhile. */
let duringEdits: (() => void) | null;
/** The gate's refusal, as the server words it. */
let editsRefusal: { status: number; code: string; details?: Record<string, unknown> } | null;

function deferred(): { promise: Promise<void>; release: () => void } {
  let release = () => {};
  const promise = new Promise<void>((r) => {
    release = r;
  });
  return { promise, release };
}

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
  held = { project: project("Znáte?"), revision: 3 };
  contentReads = 0;
  editsGate = null;
  contentGate = null;
  duringEdits = null;
  editsRefusal = null;
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
    if (u.endsWith("/workspace/content")) {
      contentReads += 1;
      if (contentGate) await contentGate;
      return new Response(JSON.stringify({
        study_id: "STU-1", state: "NATIVE", revision: held.revision, revision_id: `REV-${held.revision}`, content: held.project, analysis: null,
        template: EMPTY_PROJECT, saved_at: null, saved_by: null, can_edit: true, lineage: {},
      }));
    }
    if (u.endsWith("/lead/turns/LDT-1/edits")) {
      const body = JSON.parse(String(init?.body)) as { indices: number[]; auto?: boolean };
      decided.push(body);
      duringEdits?.();
      if (editsGate) await editsGate;
      if (editsRefusal) return new Response(JSON.stringify({ code: editsRefusal.code, message: editsRefusal.code, details: editsRefusal.details ?? {} }), { status: editsRefusal.status });
      revision += 1;
      // The server wrote the accepted wording into the working copy.
      if (body.indices.includes(0)) held = { project: project("Znáte značku?"), revision };
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

type Bench = { store?: ResearchStore; memory?: Map<string, unknown>; step?: "questionnaire" | "brief" };
function bench({ store, memory = new Map(), step = "questionnaire" }: Bench = {}) {
  const s = store ?? new ResearchStore({ revision: 3, project: project("Znáte?"), analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1");
  // The stage's reload after a click; an automatic accept reads the copy in place instead.
  const reload = vi.fn();
  const view = render(
    <Workbench frame={TEST_FRAME} step={step} store={s} memory={memory} save={null} inspector={null} reload={reload} confirm={vi.fn(async () => true)}
      onAgentStarted={vi.fn()} jobs={[]} onOpenJob={vi.fn()} onRefreshJobs={vi.fn(async () => [])}>
      <div>Dotazník</div>
    </Workbench>,
  );
  return { store: s, reload, memory, unmount: view.unmount };
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
    // Nothing was waiting to be saved: no save first, the accept names the copy's own revision.
    expect(decided).toEqual([{ decision: "accept", indices: [0], base_revision: 3, auto: true }]);
    expect(saves).toEqual([]);
    expect(reload).not.toHaveBeenCalled();
    await waitFor(() => expect(store.get().revision).toBe(4));
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
    await waitFor(() => expect(saves).toHaveLength(1), { timeout: 4000 });
    expect(saves[0]).toMatchObject({ base_revision: 4 });
  });

  it("offers Vrátit only once the copy holds what the accept wrote: the read is asynchronous", async () => {
    auto = true;
    const read = deferred();
    contentGate = read.promise;
    const { store } = bench();
    const applied = await screen.findByRole("region", { name: "Přijato automaticky" }, { timeout: 4000 });
    await waitFor(() => expect(contentReads).toBe(1));
    // The server has written revision 4; this copy is still revision 3 with the old wording.
    const back = within(applied).getByRole("button", { name: "Vrátit" }) as HTMLButtonElement;
    expect(back.disabled).toBe(true);
    fireEvent.click(back);
    expect(questionText(store)).toBe("Znáte?");
    expect(screen.queryByText(/Text se mezitím změnil/)).toBeNull();

    read.release();
    await waitFor(() => expect(store.get().revision).toBe(4));
    expect(back.disabled).toBe(false);
    fireEvent.click(back);
    expect(questionText(store)).toBe("Znáte?");
    expect(screen.queryByRole("region", { name: "Přijato automaticky" })).toBeNull();
    await waitFor(() => expect(saves).toHaveLength(1), { timeout: 4000 });
  });

  it("keeps what the person typed while the gate answered: no reload over it, nothing saved on the old base, and says so", async () => {
    auto = true;
    const gate = deferred();
    editsGate = gate.promise;
    const { store } = bench();
    duringEdits = () => store.update(() => ({ project: project("Píšu vlastní znění") }));
    await waitFor(() => expect(decided).toHaveLength(1), { timeout: 4000 });
    gate.release();
    await screen.findByText(/Vedoucí přijal textové úpravy, zatímco jste psali/, {}, { timeout: 4000 });
    expect(questionText(store)).toBe("Píšu vlastní znění");
    expect(store.get().save).toEqual({ kind: "conflict", current: 4 });
    // The copy is not the accepted revision: Vrátit waits, and no save went out over revision 4.
    const applied = screen.getByRole("region", { name: "Přijato automaticky" });
    expect((within(applied).getByRole("button", { name: "Vrátit" }) as HTMLButtonElement).disabled).toBe(true);
    await new Promise((r) => setTimeout(r, 2000));
    expect(saves).toEqual([]);
  });

  it("accepts nothing over a copy with changes still waiting to be saved: every edit waits for a click", async () => {
    auto = true;
    // A save that has not answered: the person's change is in flight when the turn finishes.
    const store = new ResearchStore({ revision: 3, project: project("Znáte?"), analysis: null, save: { kind: "saved" }, checkEpoch: 0 }, "STU-1", {
      save: () => new Promise(() => {}),
    });
    store.update(() => ({ project: project("Znáte to?") }));
    bench({ store });
    const blocks = await screen.findByRole("region", { name: "Návrhy Vedoucího" }, { timeout: 4000 });
    expect(within(blocks).getAllByRole("button", { name: "Přijmout" })).toHaveLength(2);
    await screen.findByText(/čekají k přijetí: v pracovní kopii máte neuložené změny/);
    expect(decided).toEqual([]);
    expect(questionText(store)).toBe("Znáte to?");
  });

  it("leaves a turn the person saved over for their click when the server says stale_turn", async () => {
    auto = true;
    editsRefusal = { status: 409, code: "stale_turn", details: { current_revision: 4 } };
    const { store } = bench();
    await screen.findByText(/textové úpravy Vedoucího proto čekají k přijetí/, {}, { timeout: 4000 });
    expect(decided).toEqual([{ decision: "accept", indices: [0], base_revision: 3, auto: true }]);
    const blocks = await screen.findByRole("region", { name: "Návrhy Vedoucího" });
    expect(within(blocks).getAllByRole("button", { name: "Přijmout" })).toHaveLength(2);
    expect(screen.queryByRole("region", { name: "Přijato automaticky" })).toBeNull();
    expect(contentReads).toBe(0);
    expect(questionText(store)).toBe("Znáte?");
  });

  it("keeps the bar across a stage change, even one made before the gate answered", async () => {
    auto = true;
    const gate = deferred();
    editsGate = gate.promise;
    const first = bench();
    await waitFor(() => expect(decided).toHaveLength(1), { timeout: 4000 });
    // The Lead's open_stage moves the person to Zadání: this screen goes, the study's memory stays.
    first.unmount();
    gate.release();
    await waitFor(() => expect(first.store.get().revision).toBe(4));
    const brief = bench({ store: first.store, memory: first.memory, step: "brief" });
    expect(screen.queryByRole("region", { name: "Přijato automaticky" })).toBeNull();
    brief.unmount();
    bench({ store: first.store, memory: first.memory });
    const applied = await screen.findByRole("region", { name: "Přijato automaticky" });
    fireEvent.click(within(applied).getByRole("button", { name: "Vrátit" }));
    expect(questionText(first.store)).toBe("Znáte?");
    await waitFor(() => expect(saves).toHaveLength(1), { timeout: 4000 });
  });
});
