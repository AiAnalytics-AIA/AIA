// @vitest-environment jsdom
// The Research Lead's pane (ADR 0026): the researcher hatches their own Lead, reads the session,
// writes to it, and approves a prepared job only through the card; nothing is done for them.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LeadState, LeadTurn, ResearcherLead } from "@/lib/lead";
import { LeadPane, type LeadCardsContext } from "./LeadPane";

const hatched: ResearcherLead = {
  hatched: true,
  lead: { lead_id: "LEAD-1", name: "Bára", hatched_at: "2026-10-19T08:00:00Z", updated_at: "2026-10-19T08:00:00Z", files: { soul: "", user: "" }, memories: [] },
};
const turn = (over: Partial<LeadTurn>): LeadTurn => ({
  turn_id: "LDT-1", sequence_no: 1, actor: "lead", kind: "message", stage: "brief", text: null, focus: null,
  status: "COMPLETED", reason: null, output: null, run_id: "RUN-1", workspace_revision: 3, created_at: "2026-10-19T08:00:00Z", created_by: "USR-1",
  ...over,
});

let me: ResearcherLead;
let state: LeadState;
let posts: unknown[];
let failPosts = 0;
let selfUpdates: unknown[];
let staleAnswer: string[];
function api() {
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    if (u.endsWith("/self-update")) {
      selfUpdates.push(JSON.parse(String(init?.body)));
      state = { ...state, turns: state.turns.map((t) => ({ ...t, self_update_pending: false, self_update_decision: { status: "accepted" as const } })) };
      return new Response(JSON.stringify({ status: "accepted", changes: { remembered: ["LMM-1"] }, stale: staleAnswer }));
    }
    if (u === "/config") return new Response(JSON.stringify({ apiBase: "", aiRuntime: null }));
    if (u === "/api/v1/lead" && init?.method === "POST") {
      me = hatched;
      return new Response(JSON.stringify(me), { status: 201 });
    }
    if (u === "/api/v1/lead") return new Response(JSON.stringify(me));
    if (u.endsWith("/lead/turns")) {
      if (failPosts > 0) {
        failPosts -= 1;
        return new Response(JSON.stringify({ code: "service_unavailable" }), { status: 503 });
      }
      posts.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify({ turns: [] }), { status: 201 });
    }
    if (u.endsWith("/lead")) return new Response(JSON.stringify(state));
    return new Response(JSON.stringify({ code: "not_found" }), { status: 404 });
  }));
}

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
  posts = [];
  selfUpdates = [];
  staleAnswer = [];
  failPosts = 0;
  me = hatched;
  state = { available: true, unavailable_reason: null, busy: false, turns: [] };
  api();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

const pane = (over: Partial<Parameters<typeof LeadPane>[0]> = {}) => (
  <LeadPane studyId="STU-1" stage="brief" canEdit focus={null} picking={false} onPick={vi.fn()} onClearFocus={vi.fn()} onView={vi.fn()} onRequest={vi.fn(async () => {})} onTurns={vi.fn()} onFocusMode={vi.fn()} mode="split" epoch={0} {...over} />
);

const cards = (over: Partial<LeadCardsContext> = {}): LeadCardsContext => ({
  runs: [], stepHref: (s) => `/s/${s}`, onStage: vi.fn(), prepareRun: vi.fn(), startRun: vi.fn(async () => null), runOfTurn: new Map(), onRunStarted: vi.fn(), ...over,
});

describe("LeadPane", () => {
  it("offers hatching to a researcher without a Lead, and hatches it on their click", async () => {
    me = { hatched: false, lead: null };
    render(pane());
    const hatch = await screen.findByRole("button", { name: "Vylíhnout mého Vedoucího" });
    // The shut composer says why in its own field, not "Napište Vedoucímu výzkumu…" (audit).
    const composer = screen.getByLabelText("Napište Vedoucímu výzkumu") as HTMLTextAreaElement;
    expect(composer.disabled).toBe(true);
    expect(composer.placeholder).toMatch(/vylíhněte/);
    fireEvent.click(hatch);
    expect(await screen.findByText("Bára")).toBeTruthy();
  });

  it("greets once on opening, and sends a message with the stage it was written on", async () => {
    render(pane());
    await waitFor(() => expect(posts).toEqual([{ kind: "greeting", stage: "brief" }]));
    fireEvent.change(screen.getByLabelText("Napište Vedoucímu výzkumu"), { target: { value: "Je cíl dost konkrétní?" } });
    fireEvent.keyDown(screen.getByLabelText("Napište Vedoucímu výzkumu"), { key: "Enter" });
    await waitFor(() => expect(posts[1]).toEqual({ kind: "message", text: "Je cíl dost konkrétní?", stage: "brief", focus: null }));
  });

  it("saves the working copy's waiting change before a message goes, so the Lead reads it", async () => {
    const order: string[] = [];
    const beforeMessage = vi.fn(async () => {
      order.push(`flush with ${posts.length} posts`);
    });
    render(pane({ beforeMessage }));
    await waitFor(() => expect(posts).toEqual([{ kind: "greeting", stage: "brief" }]));
    fireEvent.change(screen.getByLabelText("Napište Vedoucímu výzkumu"), { target: { value: "Je cíl dost konkrétní?" } });
    fireEvent.keyDown(screen.getByLabelText("Napište Vedoucímu výzkumu"), { key: "Enter" });
    await waitFor(() => expect(posts).toHaveLength(2));
    // Once, for the message, and before it was sent: the greeting does not save.
    expect(order).toEqual(["flush with 1 posts"]);
  });

  it("reads a Lead's reply, its edits and its request, which starts nothing until approved", async () => {
    state.turns = [
      turn({ turn_id: "LDT-0", actor: "person", text: "Pomoz mi", run_id: null }),
      turn({ output: { reply: "Cíl je obecný.\n\n- Zúžit na mladé klienty", edits: [{ op: "set_text", field: "goal", value: "Nový cíl", why: "konkrétnější" }], request: { kind: "agent_job", action: "build_questionnaire", why: "Dotazník chybí." }, follow: ["A co rozpočet?"] } }),
    ];
    const onRequest = vi.fn(async () => {});
    render(pane({ onRequest }));
    expect(await screen.findByText("Cíl je obecný.")).toBeTruthy();
    expect(screen.getByText("Zúžit na mladé klienty")).toBeTruthy();
    expect(screen.getByText("1 návrh změny v artefaktu")).toBeTruthy();
    expect(onRequest).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Spustit úlohu" }));
    await waitFor(() => expect(onRequest).toHaveBeenCalledWith(expect.objectContaining({ turn_id: "LDT-1" }), expect.objectContaining({ kind: "agent_job" })));
    expect(await screen.findByText("Rozhodnuto")).toBeTruthy();
  });

  it("keeps what the Lead wants for all of the researcher's work only on their yes", async () => {
    // Codex P1 on #484: a personal note or a file change reaches every client's studies.
    state.turns = [turn({
      output: { reply: "Zapamatuji si to.", self_update: { user: "Chce tabulky.", remember: [{ scope: "personal", text: "Preferuje tabulky." }, { scope: "client", text: "Klient chce grafy." }], forget: ["LMM-p", "LMM-c"] } },
      changes: { remembered: ["LMM-n"], forgotten: ["LMM-c"] },
      self_update_pending: true, self_update_decision: null,
      self_update_waiting: { name: null, soul: null, user: "Chce tabulky.", remember: ["Preferuje tabulky."], forget: [{ memory_id: "LMM-p", text: "Píše stručně." }] },
    })];
    render(pane());
    expect(await screen.findByText("Poznámka: Preferuje tabulky.")).toBeTruthy();
    expect(screen.getByText("USER: Chce tabulky.")).toBeTruthy();
    // Forgetting a personal note waits too, named by its text.
    expect(screen.getByText("Zapomenout: Píše stručně.")).toBeTruthy();
    // What stays inside this study's client was applied with the turn, and says so.
    expect(screen.getByText(/zapamatováno u klienta: Klient chce grafy\./)).toBeTruthy();
    expect(screen.getByText(/zapomenuto u klienta 1×/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Zahodit" })).toBeTruthy();
    expect(selfUpdates).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: "Pamatovat si" }));
    await waitFor(() => expect(selfUpdates).toEqual([{ decision: "accept" }]));
    expect(await screen.findByText("Zapamatováno pro všechnu vaši práci")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Pamatovat si" })).toBeNull();
  });

  it("reads the files an accept left from its 200, and says to ask the Lead again", async () => {
    // The review of baac33d5: an older SOUL change is not put back over a newer one.
    staleAnswer = ["soul"];
    state.turns = [turn({
      output: { reply: "Upravím se.", self_update: { soul: "# Starší" } },
      self_update_pending: true, self_update_decision: null,
      self_update_waiting: { name: null, soul: "# Starší", user: null, remember: [], forget: [] },
    })];
    render(pane());
    fireEvent.click(await screen.findByRole("button", { name: "Pamatovat si" }));
    await waitFor(() => expect(selfUpdates).toEqual([{ decision: "accept" }]));
    expect(await screen.findByText("SOUL: Soubor se mezitím změnil, požádejte Vedoucího znovu.")).toBeTruthy();
  });

  it("keeps saying a file changed after a reload, from the turn's decision", async () => {
    state.turns = [turn({
      output: { reply: "Upravím se.", self_update: { soul: "# Starší" } },
      self_update_pending: false, self_update_decision: { status: "accepted", stale: ["soul"] },
      self_update_waiting: { name: null, soul: "# Starší", user: null, remember: [], forget: [] },
    })];
    render(pane());
    expect(await screen.findByText("SOUL: Soubor se mezitím změnil, požádejte Vedoucího znovu.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Pamatovat si" })).toBeNull();
  });

  it("says why the Lead is not answering, instead of answering for it", async () => {
    state = { available: false, unavailable_reason: "research_lead_unavailable", busy: false, turns: [turn({ status: "WAITING", reason: "research_lead_unconfigured" })] };
    render(pane());
    expect(await screen.findByText("Vedoucí výzkumu není v tomto prostředí zapnutý.")).toBeTruthy();
    expect(screen.getByText(/model AI není pro pracovníka nastavený/)).toBeTruthy();
    expect((screen.getByLabelText("Napište Vedoucímu výzkumu") as HTMLTextAreaElement).disabled).toBe(true);
  });

  it("shows design jobs in the conversation, under the card that started one, with the way to review it", async () => {
    const job = { run_id: "RUN-J", design_revision_id: "REV-1", action: "build_questionnaire" as const, status: "COMPLETED", is_terminal: true, needs_attention: false, context_sha256: "x", harness_version: "3", created_at: "2026-10-19T08:01:00Z", steps: [], actual_cost_usd: 0.012 };
    const other = { ...job, run_id: "RUN-K", action: "critique_design" as const, status: "RUNNING", is_terminal: false, created_at: "2026-10-19T07:00:00Z" };
    state.turns = [turn({ output: { reply: "Navrhuji dotazník.", request: { kind: "agent_job", action: "build_questionnaire", why: "Chybí." } }, request_decision: { status: "approved", run_id: "RUN-J" } })];
    const onOpenJob = vi.fn();
    render(pane({ jobs: [other, job], onOpenJob }));
    expect(await screen.findByText("Navrhuji dotazník.")).toBeTruthy();
    expect(screen.getByText("Rozhodnuto")).toBeTruthy();
    expect(screen.getByText("Kontrola návrhu")).toBeTruthy();
    expect(screen.getByText("běží")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zkontrolovat návrh" }));
    expect(onOpenJob).toHaveBeenCalledWith(expect.objectContaining({ run_id: "RUN-J" }));
  });

  it("shows a running job's card with its orb and live activity, then the way to what it changed", async () => {
    const running = { run_id: "RUN-J", design_revision_id: "REV-1", action: "optimize_questionnaire" as const, status: "RUNNING", is_terminal: false, needs_attention: false, context_sha256: "x", harness_version: "3", created_at: "2026-10-19T08:01:00Z",
      steps: [{ step_id: "STEP-J", node_key: "agent", kind: "research_agent", stage_type: "x", status: "RUNNING", waiting_reason: null, attempts_recorded: 1, max_attempts: 3, started_at: "2026-10-19T08:01:00Z", finished_at: null, failure_class: null, error_message: null, artifact_id: null, data_origin: null }],
      actual_cost_usd: null };
    const onStage = vi.fn();
    const { rerender, container } = render(pane({ jobs: [running], onOpenJob: vi.fn(), cards: cards({ onStage }) }));
    await screen.findByText("Úprava dotazníku");
    const card = container.querySelector('[data-card="worker"]')!;
    expect(card.getAttribute("data-card-state")).toBe("running");
    expect(card.querySelector("[data-orb]")?.getAttribute("data-orb")).toBe("solving");
    expect(card.querySelector("[data-step-activity]")).not.toBeNull();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    const done = { ...running, status: "COMPLETED", is_terminal: true, proposal_state: "pending" as const, actual_cost_usd: 0.02, steps: [{ ...running.steps[0]!, status: "SUCCEEDED" }] };
    rerender(pane({ jobs: [done], onOpenJob: vi.fn(), cards: cards({ onStage }) }));
    await waitFor(() => expect(container.querySelector('[data-card="worker"]')?.getAttribute("data-card-state")).toBe("completed"));
    expect(container.querySelector('[data-card="worker"] [data-orb]')).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Otevřít Dotazník" }));
    expect(onStage).toHaveBeenCalledWith("questionnaire");
    expect(screen.getByRole("button", { name: "Zkontrolovat návrh" })).toBeTruthy();
  });

  it("shows every research run as a card with Průběh, and Výsledky once its data exists", async () => {
    const run = { run_id: "RUN-R", study_id: "STU-1", design_revision_id: "REV-1", design_revision: 4, status: "COMPLETED", phase: "COMPLETED" as const, needs_attention: false, is_terminal: true, retryable: false, cancel_requested: false, fieldwork_source: "ai_runtime", retry_of: null, created: true, created_at: "2026-10-19T09:00:00Z", started_at: null, finished_at: null,
      steps: [{ step_id: "S-a", node_key: "aggregate", kind: "research_aggregate", stage_type: "x", status: "SUCCEEDED", waiting_reason: null, attempts_recorded: 1, max_attempts: 3, started_at: null, finished_at: null, failure_class: null, error_message: null, artifact_id: "ART-1", data_origin: null }],
      artifact_ids: [], actual_cost_usd: 1.5 };
    render(pane({ cards: cards({ runs: [run] }) }));
    expect(await screen.findByText("Výzkumný běh")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Průběh" }).getAttribute("href")).toBe("/s/progress?run=RUN-R");
    expect(screen.getByRole("link", { name: "Výsledky" }).getAttribute("href")).toBe("/s/results?run=RUN-R#data");
  });

  it("starts the Lead's prepared research run only on the person's click, through Spuštění's route", async () => {
    state.turns = [turn({ output: { reply: "Můžeme spustit.", request: { kind: "research_run", why: "Návrh je hotový." } } })];
    const readiness = { design_revision_id: "REV-9", rules: "r", ready: true, checks: [], questions: 3, batteries: 0, objects: 0, n: 300, fieldwork_source: "ai_runtime", cost_ceiling_usd: 4.2, cost_ceiling_unknown: null, fieldwork_requests: 300, analysis_calls: 8, spend_confirm_usd: null, confirmation_required: false, persona_source: "fictional_roster" };
    const started = { run_id: "RUN-N", design_revision_id: "REV-9" };
    const prepareRun = vi.fn(async () => ({ readiness, runs: [] }));
    const startRun = vi.fn(async () => started as never);
    const onRunStarted = vi.fn();
    render(pane({ cards: cards({ prepareRun, startRun, onRunStarted }) }));
    fireEvent.click(await screen.findByRole("button", { name: "Zkontrolovat spuštění" }));
    expect(prepareRun).toHaveBeenCalledTimes(1);
    expect(startRun).not.toHaveBeenCalled();
    // The ceiling is the card's key fact, labelled; the state pill says it is ready.
    const key = await screen.findByText("4,2 USD");
    expect(key.className).toContain("card__key");
    expect(key.closest("dd")?.previousElementSibling?.textContent).toBe("Cena nejvýše");
    expect(screen.getByText("Připraveno")).toBeTruthy();
    expect(screen.getByText("Rozpočet studie")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Jiný zdroj nebo populaci zvolíte na Spuštění" }).getAttribute("href")).toBe("/s/run");
    fireEvent.click(screen.getByRole("button", { name: "Spustit výzkum" }));
    await waitFor(() => expect(startRun).toHaveBeenCalledWith(readiness, null));
    // The working copy is checked again at the click, before anything starts.
    expect(prepareRun).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(onRunStarted).toHaveBeenCalledWith("LDT-1", started));
    expect(screen.getByText("Spuštěno")).toBeTruthy();
  });

  it("never starts a design that changed since the card checked it: it checks it again and shows it", async () => {
    state.turns = [turn({ output: { reply: "Můžeme spustit.", request: { kind: "research_run", why: "Návrh je hotový." } } })];
    const readiness = { design_revision_id: "REV-9", rules: "r", ready: true, checks: [], questions: 3, batteries: 0, objects: 0, n: 300, fieldwork_source: "ai_runtime", cost_ceiling_usd: 4.2, cost_ceiling_unknown: null, fieldwork_requests: 300, analysis_calls: 8, spend_confirm_usd: null, confirmation_required: false, persona_source: "fictional_roster" };
    const edited = { ...readiness, design_revision_id: "REV-10", cost_ceiling_usd: 6.5 };
    const prepareRun = vi.fn().mockResolvedValueOnce({ readiness, runs: [] }).mockResolvedValue({ readiness: edited, runs: [] });
    const startRun = vi.fn(async () => null);
    render(pane({ cards: cards({ prepareRun, startRun }) }));
    fireEvent.click(await screen.findByRole("button", { name: "Zkontrolovat spuštění" }));
    await screen.findByText("4,2 USD");
    fireEvent.click(screen.getByRole("button", { name: "Spustit výzkum" }));
    expect(await screen.findByText(/Návrh se od kontroly změnil/)).toBeTruthy();
    expect(screen.getByText("6,5 USD")).toBeTruthy();
    expect(startRun).not.toHaveBeenCalled();
    // A second click starts the design now shown.
    fireEvent.click(screen.getByRole("button", { name: "Spustit výzkum" }));
    await waitFor(() => expect(startRun).toHaveBeenCalledWith(edited, null));
  });

  it("says a run's ceiling is unknown rather than zero, and sends the person to Spuštění", async () => {
    state.turns = [turn({ output: { reply: "Můžeme spustit.", request: { kind: "research_run", why: "Návrh je hotový." } } })];
    const readiness = { design_revision_id: "REV-9", rules: "r", ready: true, checks: [], questions: 3, batteries: 0, objects: 0, n: 300, fieldwork_source: "ai_runtime", cost_ceiling_usd: null, cost_ceiling_unknown: "no_reservation", fieldwork_requests: 300, analysis_calls: 8, spend_confirm_usd: 2, confirmation_required: true, persona_source: "fictional_roster" };
    render(pane({ cards: cards({ prepareRun: vi.fn(async () => ({ readiness, runs: [] })) }) }));
    fireEvent.click(await screen.findByRole("button", { name: "Zkontrolovat spuštění" }));
    expect(await screen.findByText("Blokuje: neznámá cena")).toBeTruthy();
    expect(screen.getByText(/Neznámá/)).toBeTruthy();
    expect(screen.queryByText(/^0 USD/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Spustit výzkum" })).toBeNull();
    expect(screen.getByRole("link", { name: "Otevřít Kontrolu a spuštění" })).toBeTruthy();
  });

  it("sends a message written while the Lead works with the stage and element it was written about", async () => {
    state = { ...state, busy: true, turns: [turn({ status: "RUNNING", output: null })] };
    const focus = { id: "question:Q_1", label: "Otázka Q_1" };
    const { rerender } = render(pane({ focus }));
    await screen.findByLabelText("Napište Vedoucímu výzkumu");
    fireEvent.change(screen.getByLabelText("Napište Vedoucímu výzkumu"), { target: { value: "Zkrať ji" } });
    fireEvent.keyDown(screen.getByLabelText("Napište Vedoucímu výzkumu"), { key: "Enter" });
    expect(await screen.findByText("Zkrať ji")).toBeTruthy();
    rerender(pane({ focus: null, stage: "design" }));
    state = { ...state, busy: false, turns: [turn({ output: { reply: "Hotovo." } })] };
    await waitFor(() => expect(posts.at(-1)).toEqual({ kind: "message", text: "Zkrať ji", stage: "brief", focus }));
  });

  it("keeps a message the server did not take, held until the researcher tries again", async () => {
    state = { ...state, turns: [turn({ output: { reply: "Dobrý den." } })] };
    render(pane());
    await waitFor(() => expect(posts).toEqual([{ kind: "greeting", stage: "brief" }]));
    failPosts = 1;
    fireEvent.change(screen.getByLabelText("Napište Vedoucímu výzkumu"), { target: { value: "Je cíl dost konkrétní?" } });
    fireEvent.keyDown(screen.getByLabelText("Napište Vedoucímu výzkumu"), { key: "Enter" });
    expect(await screen.findByText("Je cíl dost konkrétní?")).toBeTruthy();
    expect(screen.getByText(/Zprávu se nepodařilo odeslat/)).toBeTruthy();
    expect(posts).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Zkusit znovu" }));
    await waitFor(() => expect(posts[1]).toEqual({ kind: "message", text: "Je cíl dost konkrétní?", stage: "brief", focus: null }));
  });

  // F-BRF-2 (lead_journey.mjs, "Tab stays inside the open conversation"): Tab onto "Na nejnovější" just
  // as the log's scroll from the previous Tab reaches the bottom unmounted the button under the
  // keyboard, and the focus fell to the page.
  it("keeps Na nejnovější while it has the focus, and gives the focus to the log once it has jumped", async () => {
    state = { ...state, turns: [turn({ output: { reply: "Dobrý den." } })] };
    vi.spyOn(document, "hasFocus").mockReturnValue(true); // jsdom's window never has the focus
    render(pane());
    const log = await screen.findByRole("log");
    let top = 0;
    Object.defineProperty(log, "scrollHeight", { configurable: true, get: () => 1000 });
    Object.defineProperty(log, "clientHeight", { configurable: true, get: () => 200 });
    Object.defineProperty(log, "scrollTop", { configurable: true, get: () => top, set: (v: number) => { top = v; } });
    top = 100;
    fireEvent.scroll(log);
    const latest = await screen.findByRole("button", { name: "Na nejnovější" });
    act(() => latest.focus());
    top = 790; // the previous Tab's scroll lands at the bottom after the button took the focus
    fireEvent.scroll(log);
    expect(screen.getByRole("button", { name: "Na nejnovější" })).toBe(latest);
    expect(document.activeElement).toBe(latest);
    fireEvent.click(latest);
    expect(screen.queryByRole("button", { name: "Na nejnovější" })).toBeNull();
    expect(document.activeElement).toBe(log);
    expect(top).toBe(1000);
  });
});
