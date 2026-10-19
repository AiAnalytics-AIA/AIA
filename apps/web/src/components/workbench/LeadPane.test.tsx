// @vitest-environment jsdom
// The Research Lead's pane (ADR 0026): the researcher hatches their own Lead, reads the session,
// writes to it, and approves a prepared job only through the card; nothing is done for them.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LeadState, LeadTurn, ResearcherLead } from "@/lib/lead";
import { LeadPane } from "./LeadPane";

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
function api() {
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    if (u === "/config") return new Response(JSON.stringify({ apiBase: "", aiRuntime: null }));
    if (u === "/api/v1/lead" && init?.method === "POST") {
      me = hatched;
      return new Response(JSON.stringify(me), { status: 201 });
    }
    if (u === "/api/v1/lead") return new Response(JSON.stringify(me));
    if (u.endsWith("/lead/turns")) {
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
  me = hatched;
  state = { available: true, unavailable_reason: null, busy: false, turns: [] };
  api();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const pane = (over: Partial<Parameters<typeof LeadPane>[0]> = {}) => (
  <LeadPane studyId="STU-1" stage="brief" canEdit focus={null} picking={false} onPick={vi.fn()} onClearFocus={vi.fn()} onView={vi.fn()} onRequest={vi.fn(async () => {})} onTurns={vi.fn()} onFocusMode={vi.fn()} mode="split" epoch={0} {...over} />
);

describe("LeadPane", () => {
  it("offers hatching to a researcher without a Lead, and hatches it on their click", async () => {
    me = { hatched: false, lead: null };
    render(pane());
    fireEvent.click(await screen.findByRole("button", { name: "Vylíhnout mého Vedoucího" }));
    expect(await screen.findByText("Bára")).toBeTruthy();
  });

  it("greets once on opening, and sends a message with the stage it was written on", async () => {
    render(pane());
    await waitFor(() => expect(posts).toEqual([{ kind: "greeting", stage: "brief" }]));
    fireEvent.change(screen.getByLabelText("Napište Vedoucímu výzkumu"), { target: { value: "Je cíl dost konkrétní?" } });
    fireEvent.keyDown(screen.getByLabelText("Napište Vedoucímu výzkumu"), { key: "Enter" });
    await waitFor(() => expect(posts[1]).toEqual({ kind: "message", text: "Je cíl dost konkrétní?", stage: "brief", focus: null }));
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

  it("says why the Lead is not answering, instead of answering for it", async () => {
    state = { available: false, unavailable_reason: "research_lead_unavailable", busy: false, turns: [turn({ status: "WAITING", reason: "research_lead_unconfigured" })] };
    render(pane());
    expect(await screen.findByText("Vedoucí výzkumu není v tomto prostředí zapnutý.")).toBeTruthy();
    expect(screen.getByText(/model AI není pro pracovníka nastavený/)).toBeTruthy();
    expect((screen.getByLabelText("Napište Vedoucímu výzkumu") as HTMLTextAreaElement).disabled).toBe(true);
  });
});
