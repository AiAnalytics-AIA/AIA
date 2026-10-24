// @vitest-environment jsdom
// The Research Lead's pane (ADR 0026): the researcher hatches their own Lead, reads the session,
// writes to it, and approves a prepared job only through the card; nothing is done for them.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LeadState, LeadTurn, ResearcherLead } from "@/lib/lead";
import type { PlanState } from "@/research/plan";
import { itemTargets } from "@/research/plan-narrative";
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

// A turn's manifest as the server reads it from the frozen context (LC2): fictional ids; the
// knowledge layer left 51 items out and lists the first fifty; Design Research was not recorded.
const MANIFEST = {
  turn_id: "LDT-1", recorded: true,
  manifest: { manifest_version: 1, total_bytes: 41_200, ceiling_bytes: 98_304, layers: [
    { layer: "knowledge", recorded: true, bytes: 21_000, ceiling_bytes: 20_480, bounded_bytes: 20_100, bound: "x", over_policy: "y", included: ["K-0"], included_count: 1,
      omitted: Array.from({ length: 50 }, (_, i) => ({ id: `K-${i + 1}`, reason: "over_budget" })), omitted_count: 51 },
    { layer: "external_context_not_evidence", recorded: false, ceiling_bytes: null, bound: "x", over_policy: "y", included: [], omitted: [] },
  ] },
};

let me: ResearcherLead;
let state: LeadState;
let posts: unknown[];
let failPosts = 0;
let selfUpdates: unknown[];
let staleAnswer: string[];
let drains = 0;
let failDrains = 0;
let withdrawn: string[] = [];
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
    if (u.endsWith("/lead/turns/queued")) {
      drains += 1;
      if (failDrains > 0) {
        failDrains -= 1;
        return new Response(JSON.stringify({ code: "service_unavailable" }), { status: 500 });
      }
      return new Response(JSON.stringify({ turns: [] }));
    }
    if (u.endsWith("/withdraw")) {
      withdrawn.push(u.split("/").at(-2)!);
      return new Response(JSON.stringify({ turns: [] }));
    }
    if (u.endsWith("/lead/turns")) {
      if (failPosts > 0) {
        failPosts -= 1;
        return new Response(JSON.stringify({ code: "service_unavailable" }), { status: 503 });
      }
      posts.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify({ turns: [] }), { status: 201 });
    }
    if (u.includes("/manifest/omitted")) {
      return new Response(JSON.stringify({ layer: "knowledge", after: 50, total: 51, omitted: [{ id: "K-51", reason: "over_budget" }] }));
    }
    if (u.endsWith("/manifest")) return new Response(JSON.stringify(MANIFEST));
    if (u.endsWith("/lead")) return new Response(JSON.stringify(state));
    return new Response(JSON.stringify({ code: "not_found" }), { status: 404 });
  }));
}

beforeEach(() => {
  sessionStorage.setItem("aia.session", JSON.stringify({ idToken: "tok", refreshToken: "r", expiresAt: Date.now() + 3_600_000, email: "a@example.test" }));
  posts = [];
  selfUpdates = [];
  staleAnswer = [];
  drains = 0;
  withdrawn = [];
  failPosts = 0;
  failDrains = 0;
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
  it("heads each local day of the conversation with its divider, before its first message", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 21, 10, 0));
    try {
      const at = (d: Date) => d.toISOString();
      state.turns = [
        turn({ turn_id: "LDT-0", actor: "person", text: "Včerejší otázka", run_id: null, created_at: at(new Date(2026, 9, 20, 23, 50)) }),
        turn({ turn_id: "LDT-1", output: { reply: "Půlnoční odpověď" }, created_at: at(new Date(2026, 9, 21, 0, 5)) }),
        turn({ turn_id: "LDT-2", actor: "person", text: "Ranní otázka", run_id: null, created_at: at(new Date(2026, 9, 21, 9, 0)) }),
      ];
      render(pane());
      expect(await screen.findByText("Ranní otázka")).toBeTruthy();
      const days = screen.getAllByRole("heading", { level: 3 }).filter((h) => h.classList.contains("conv__day"));
      expect(days.map((h) => h.textContent)).toEqual(["Včera", "Dnes"]);
      // Each divider stands before its day's first message, in the document's order.
      const before = (a: Node, b: Node) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
      expect(before(days[0], screen.getByText("Včerejší otázka"))).toBe(true);
      expect(before(screen.getByText("Včerejší otázka"), days[1])).toBe(true);
      expect(before(days[1], screen.getByText("Půlnoční odpověď"))).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows a turn parked on the budget in coral to whoever can raise it, and slate to a reader who cannot", async () => {
    state.turns = [turn({ turn_id: "LDT-B", status: "WAITING", reason: "budget_exceeded", output: null })];
    render(pane());
    const wait = await waitFor(() => { const n = document.querySelector('[data-lead-wait="budget_exceeded"]'); if (!n) throw new Error("no wait"); return n as HTMLElement; });
    expect(wait.querySelector(".glyph")?.getAttribute("data-tone")).toBe("you");
    expect(wait.textContent).toMatch(/Nastavte ho v Nastavení → Studie/);
    cleanup();
    state.turns = [turn({ turn_id: "LDT-B", status: "WAITING", reason: "budget_exceeded", output: null })];
    render(pane({ canEdit: false }));
    const read = await waitFor(() => { const n = document.querySelector('[data-lead-wait="budget_exceeded"]'); if (!n) throw new Error("no wait"); return n as HTMLElement; });
    expect(read.querySelector(".glyph")?.getAttribute("data-tone")).toBe("world");
  });

  it("opens what the last Lead turn could see from the Vidí chip, naming what it left out", async () => {
    state.turns = [turn({ output: { reply: "Hotovo." } })];
    render(pane());
    const chip = await screen.findByRole("button", { name: /Vidí: / });
    expect(chip.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(chip);
    expect(chip.getAttribute("aria-expanded")).toBe("true");
    const panel = await screen.findByRole("region", { name: "Co Vedoucí viděl v poslední odpovědi" });
    expect(await within(panel).findByText("Znalosti klienta")).toBeTruthy();
    const left = within(panel).getByRole("list", { name: "Vynecháno z vrstvy Znalosti klienta" });
    expect(within(left).getByText("K-1").closest("li")?.textContent).toBe("K-1 · nevešla se do limitu vrstvy");
    expect(within(panel).getByText("Nezaznamenáno: tato odpověď vrstvu neměla.")).toBeTruthy();
    fireEvent.click(within(panel).getByRole("button", { name: "Načíst další vynechané" }));
    expect(await within(left).findByText("K-51")).toBeTruthy();
    expect(within(panel).queryByRole("button", { name: "Načíst další vynechané" })).toBeNull();
  });

  it("opens the same panel in the compact drawer", async () => {
    state.turns = [turn({ output: { reply: "Hotovo." } })];
    render(pane({ onClose: vi.fn() }));
    fireEvent.click(await screen.findByRole("button", { name: /Vidí: / }));
    expect(await screen.findByRole("region", { name: "Co Vedoucí viděl v poslední odpovědi" })).toBeTruthy();
  });

  it("offers no chip before any Lead turn froze a context", async () => {
    render(pane());
    expect(await screen.findByText(/Vidí: /)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Vidí: / })).toBeNull();
  });

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

  it("follows a person's typed start with their own card, which starts it on their approval (LO5)", async () => {
    state.turns = [
      turn({ turn_id: "LDT-7", actor: "person", text: "Navrhni dotazník: krátce", command: "agent_job:build_questionnaire", run_id: null, output: null }),
      turn({ turn_id: "LDT-8", actor: "person", text: "Spusť výzkum", command: "research_run", run_id: null, output: null }),
    ];
    const onRequest = vi.fn(async () => {});
    render(pane({ onRequest, cards: cards() }));
    expect(await screen.findAllByText("Váš příkaz")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Spustit úlohu" }));
    await waitFor(() => expect(onRequest).toHaveBeenCalledWith(expect.objectContaining({ turn_id: "LDT-7" }), { kind: "agent_job", action: "build_questionnaire", why: "krátce" }));
    // The typed run starts from its card, not by opening Spuštění.
    fireEvent.click(screen.getByRole("button", { name: "Spustit výzkum" }));
    await waitFor(() => expect(onRequest).toHaveBeenCalledWith(expect.objectContaining({ turn_id: "LDT-8" }), expect.objectContaining({ kind: "research_run" })));
  });

  it("shows a typed analysis retry as the stage's retry, names the run it retries and starts it on that run", async () => {
    state = { ...state, wallet_enabled: false, analysis_retry_run: { run_id: "RUN-a1", created_at: "2026-10-22T09:30:00Z", phase: "succeeded" },
      turns: [turn({ turn_id: "LDT-10", actor: "person", text: "Zopakuj analýzu", command: "analysis_retry", run_id: null, output: null })] };
    const onRequest = vi.fn(async () => {});
    const { container } = render(pane({ onRequest, cards: cards() }));
    expect(await screen.findByText("Opakování analýzy")).toBeTruthy();
    const card = container.querySelector('[data-card="request"][data-typed]')!;
    expect(card.textContent).toContain("nová data se nesbírají");
    expect(card.textContent).toMatch(/Který běh.*Běh z /);
    // With the wallet off the card does not speak of it (the PM on #744).
    expect(card.textContent).not.toContain("Peněženk");
    fireEvent.click(screen.getByRole("button", { name: "Zopakovat analýzu" }));
    await waitFor(() => expect(onRequest).toHaveBeenCalledWith(expect.objectContaining({ turn_id: "LDT-10" }), { kind: "analysis_retry", why: "Spustí se až vaším potvrzením.", run_id: "RUN-a1" }));
  });

  it("says a typed start is not charged to the Peněženka only with the wallet on", async () => {
    state = { ...state, wallet_enabled: true, analysis_retry_run: null,
      turns: [turn({ turn_id: "LDT-11", actor: "person", text: "Zopakuj analýzu", command: "analysis_retry", run_id: null, output: null }),
        turn({ turn_id: "LDT-12", actor: "person", text: "Spusť výzkum", command: "research_run", run_id: null, output: null })] };
    const { container } = render(pane({ cards: cards() }));
    await screen.findByText("Opakování analýzy");
    const [retry, run] = Array.from(container.querySelectorAll('[data-card="request"][data-typed]'));
    expect(retry!.textContent).toContain("Opakování analýzy se nestrhává z Peněženky.");
    expect(retry!.textContent).toContain("Studie zatím nemá běh s AI analýzou");
    expect(run!.textContent).toContain("práh potvrzení a Peněženka se kontrolují");
  });

  it("says a typed start approved again found the job already done, and shows that job once", async () => {
    const job = { run_id: "RUN-J", design_revision_id: "REV-1", action: "critique_design" as const, status: "COMPLETED", is_terminal: true, needs_attention: false, context_sha256: "x", harness_version: "3", created_at: "2026-10-19T08:01:00Z", steps: [], actual_cost_usd: 0.012 };
    state.turns = [
      turn({ turn_id: "LDT-7", actor: "person", text: "Zkontroluj návrh", command: "agent_job:critique_design", run_id: null, output: null, request_decision: { status: "approved", run_id: "RUN-J", reused: false } }),
      turn({ turn_id: "LDT-9", actor: "person", text: "Zkontroluj návrh", command: "agent_job:critique_design", run_id: null, output: null, request_decision: { status: "approved", run_id: "RUN-J", reused: true } }),
    ];
    const { container } = render(pane({ jobs: [job], onOpenJob: vi.fn(), cards: cards() }));
    expect(await screen.findByText("Už proběhlo")).toBeTruthy();
    expect(screen.getByText("Tato úloha pro tento návrh už proběhla")).toBeTruthy();
    expect(container.querySelectorAll('[data-card="worker"]')).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Spustit úlohu" })).toBeNull();
    // A decided card no longer says it starts on the person's confirmation.
    expect(screen.queryByText("Spustí se až vaším potvrzením.")).toBeNull();
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

  it("sends a message written while the Lead works at once, with the stage and element it was written about", async () => {
    state = { ...state, busy: true, turns: [turn({ status: "RUNNING", output: null })] };
    const focus = { id: "question:Q_1", label: "Otázka Q_1" };
    render(pane({ focus }));
    await screen.findByLabelText("Napište Vedoucímu výzkumu");
    fireEvent.change(screen.getByLabelText("Napište Vedoucímu výzkumu"), { target: { value: "Zkrať ji" } });
    fireEvent.keyDown(screen.getByLabelText("Napište Vedoucímu výzkumu"), { key: "Enter" });
    // The server keeps it until the Lead is free (ADR 0041 decision 7): nothing waits in the page.
    await waitFor(() => expect(posts.at(-1)).toEqual({ kind: "message", text: "Zkrať ji", stage: "brief", focus }));
  });

  it("shows what waits on the server, withdraws it on request, and asks a free Lead to answer the rest", async () => {
    const waiting = (id: string, text: string) => turn({ turn_id: id, actor: "person", text, run_id: null, queued: true });
    state = { ...state, busy: true, turns: [turn({ status: "RUNNING", output: null }), waiting("LDT-8", "Z jiné karty"), waiting("LDT-9", "Zkrať ji")] };
    render(pane());
    const queue = await screen.findByLabelText("Čeká na Vedoucího");
    expect(within(queue).getByText("Z jiné karty")).toBeTruthy();
    // A waiting message is shown once, in the queue: not yet a turn of the conversation.
    expect(screen.getAllByText("Zkrať ji")).toHaveLength(1);
    expect(drains).toBe(0); // the Lead is still at work
    // The Lead finishes; the withdrawal's read finds it free with one message still waiting.
    state = { ...state, busy: false, turns: [turn({ output: { reply: "Hotovo." } }), waiting("LDT-8", "Z jiné karty")] };
    fireEvent.click(within(queue).getAllByRole("button", { name: "Odebrat z fronty" })[1]!);
    await waitFor(() => expect(withdrawn).toEqual(["LDT-9"]));
    await waitFor(() => expect(drains).toBe(1));
  });

  it("asks again for what waits once a turn parked on the budget is released and answered", async () => {
    const waiting = turn({ turn_id: "LDT-9", actor: "person", text: "Jsi tam?", run_id: null, queued: true });
    state = { ...state, busy: false, turns: [turn({ status: "WAITING", reason: "budget_exceeded", output: null }), waiting] };
    const { rerender } = render(pane());
    await waitFor(() => expect(drains).toBe(1)); // the server answers none: the turn waits on the budget
    // The budget is raised, the parked turn answered; the next read finds the message still waiting.
    state = { ...state, turns: [turn({ output: { reply: "Hotovo." } }), waiting] };
    rerender(pane({ epoch: 1 }));
    await waitFor(() => expect(drains).toBe(2));
  });

  it("says when asking the Lead to answer the queue failed, and asks again on Zkusit znovu", async () => {
    const waiting = turn({ turn_id: "LDT-9", actor: "person", text: "Jsi tam?", run_id: null, queued: true });
    state = { ...state, busy: false, turns: [turn({ output: { reply: "Hotovo." } }), waiting] };
    failDrains = 1;
    render(pane());
    expect(await screen.findByText(/Vedoucí zatím neodpovídá na zprávy ve frontě/)).toBeTruthy();
    expect(drains).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Zkusit znovu" }));
    await waitFor(() => expect(drains).toBe(2));
    await waitFor(() => expect(screen.queryByText(/Vedoucí zatím neodpovídá/)).toBeNull());
  });

  it("names a view chip's research question or hypothesis by its words in the working copy (F18)", async () => {
    const design = { project: { research_plan: { hypotheses: ["Mírnější varianta osloví širší publikum."] } }, analysis: null };
    const target = itemTargets(design as unknown as PlanState).hypotheses[0]!;
    state = { ...state, turns: [turn({ output: { reply: "Tady je.", view: [{ op: "inspect", target }, { op: "focus", target: "hypothesis:hyp_gone" }] } })] };
    const onView = vi.fn();
    render(pane({ design, onView }));
    fireEvent.click(await screen.findByRole("button", { name: "Detail: Hypotéza: Mírnější varianta osloví širší publikum." }));
    expect(onView).toHaveBeenCalledWith([{ op: "inspect", target }]);
    // One the copy no longer holds keeps its id rather than borrowing words.
    expect(screen.getByRole("button", { name: "Ukázat: Hypotéza hyp_gone" })).toBeTruthy();
  });

  it("names a show_diff chip by the stage whose changes it shows", async () => {
    state = { ...state, turns: [turn({ output: { reply: "Tady jsou.", view: [{ op: "show_diff", stage: "questionnaire" }] } })] };
    const onView = vi.fn();
    render(pane({ onView }));
    fireEvent.click(await screen.findByRole("button", { name: "Změny: Dotazník" }));
    expect(onView).toHaveBeenCalledWith([{ op: "show_diff", stage: "questionnaire" }]);
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
  describe("Na nejnovější under the keyboard", () => {
    // The log scrolled away from the bottom, its button shown and focused; jsdom's window never has
    // the focus, so the window's focus is the test's to set.
    const focusedLatest = async () => {
      state = { ...state, turns: [turn({ output: { reply: "Dobrý den." } })] };
      const windowFocus = vi.spyOn(document, "hasFocus").mockReturnValue(true);
      render(pane());
      const log = await screen.findByRole("log");
      let top = 100;
      Object.defineProperty(log, "scrollHeight", { configurable: true, get: () => 1000 });
      Object.defineProperty(log, "clientHeight", { configurable: true, get: () => 200 });
      Object.defineProperty(log, "scrollTop", { configurable: true, get: () => top, set: (v: number) => { top = v; } });
      fireEvent.scroll(log);
      const latest = await screen.findByRole("button", { name: "Na nejnovější" });
      act(() => latest.focus());
      const toBottom = () => { top = 790; fireEvent.scroll(log); };
      return { log, latest, windowFocus, toBottom, top: () => top };
    };
    const shown = () => screen.queryByRole("button", { name: "Na nejnovější" });

    it("stays while it has the focus, and gives the focus to the log once it has jumped", async () => {
      const { log, latest, toBottom, top } = await focusedLatest();
      toBottom(); // the previous Tab's scroll lands at the bottom after the button took the focus
      expect(shown()).toBe(latest);
      expect(document.activeElement).toBe(latest);
      fireEvent.click(latest);
      expect(shown()).toBeNull();
      expect(document.activeElement).toBe(log);
      expect(top()).toBe(1000);
    });

    it("stays when another window takes the focus, for the keyboard's return", async () => {
      const { latest, windowFocus, toBottom } = await focusedLatest();
      windowFocus.mockReturnValue(false);
      fireEvent.blur(latest);
      toBottom();
      expect(shown()).toBe(latest);
    });

    it("goes at the next scroll once the focus left it without the keyboard (the pane hidden)", async () => {
      const { log, windowFocus, toBottom } = await focusedLatest();
      windowFocus.mockReturnValue(false); // the blur is not counted, as when the pane is hidden
      act(() => log.focus());
      windowFocus.mockReturnValue(true);
      toBottom();
      expect(shown()).toBeNull();
    });
  });
});
