// The Lead's availability (research-lead-workbench chunk 27a): read from GET /lead alone,
// unknown never on, a switched-off Lead off, a parked turn waiting.
import { describe, expect, it } from "vitest";

import type { LeadTurn } from "./lead";
import { type LeadStateWithWorker, availabilityLabel, availabilityWords, isLeadOn, leadAvailability, leadReasonWords } from "./lead-availability";

const turn = (over: Partial<LeadTurn>): LeadTurn => ({
  turn_id: `t${over.sequence_no ?? 1}`,
  sequence_no: 1,
  actor: "lead",
  kind: "message",
  stage: "brief",
  text: null,
  focus: null,
  status: "COMPLETED",
  reason: null,
  output: null,
  run_id: null,
  workspace_revision: null,
  created_at: "2026-10-21T12:00:00Z",
  created_by: null,
  ...over,
} as LeadTurn);

const state = (over: Partial<LeadStateWithWorker>): LeadStateWithWorker => ({ available: true, unavailable_reason: null, busy: false, turns: [], worker_ready: true, ...over });

describe("leadAvailability", () => {
  it("never reads an unread, unreadable or out-of-shape answer as on", () => {
    expect(leadAvailability(null)).toEqual({ kind: "UNKNOWN", reason: null });
    expect(leadAvailability(undefined)).toEqual({ kind: "UNKNOWN", reason: null });
    expect(leadAvailability(state({}), true)).toEqual({ kind: "UNKNOWN", reason: null });
    const odd = { ...state({}), available: "yes" } as unknown as LeadStateWithWorker;
    expect(leadAvailability(odd).kind).toBe("UNKNOWN");
    const missing = { busy: false, turns: [] } as unknown as LeadStateWithWorker;
    expect(leadAvailability(missing).kind).toBe("UNKNOWN");
    for (const s of [null, undefined, odd, missing]) expect(isLeadOn(leadAvailability(s))).toBe(false);
  });

  it("reads research_lead_disabled as off, whatever the turns say", () => {
    const a = leadAvailability(state({ available: false, unavailable_reason: "research_lead_disabled", turns: [turn({ status: "COMPLETED" })] }));
    expect(a).toEqual({ kind: "OFF", reason: "research_lead_disabled" });
    expect(isLeadOn(a)).toBe(false);
    expect(availabilityLabel(a)).toBe("Vedoucí vypnutý");
    expect(availabilityWords(a)).toBe("Vedoucí výzkumu není v tomto prostředí zapnutý.");
  });

  it("reads an off answer without a reason as off, never on", () => {
    expect(leadAvailability(state({ available: false, unavailable_reason: null }))).toEqual({ kind: "OFF", reason: "research_lead_unavailable" });
  });

  it("reads a newest Lead turn the worker parked as waiting, with its reason", () => {
    for (const reason of ["research_lead_unconfigured", "ai_runtime_unavailable", "egress_no_approved_route", "budget_exceeded", "reservation_exhausted"]) {
      const a = leadAvailability(state({ turns: [turn({ sequence_no: 1 }), turn({ sequence_no: 2, status: "WAITING", reason })] }));
      expect(a).toEqual({ kind: "WAITING", reason });
      expect(isLeadOn(a)).toBe(false);
      expect(availabilityLabel(a)).toBe("Vedoucí čeká");
      expect(availabilityWords(a)).toBe(leadReasonWords(reason));
    }
  });

  it("reads the newest Lead turn by sequence, not by its place in the list", () => {
    const turns = [turn({ sequence_no: 3, status: "COMPLETED" }), turn({ sequence_no: 2, status: "WAITING", reason: "research_lead_unconfigured" })];
    expect(leadAvailability(state({ turns })).kind).toBe("ON");
  });

  it("ignores the person's own turns", () => {
    const turns = [turn({ sequence_no: 1, status: "WAITING", reason: "research_lead_unconfigured" }), turn({ sequence_no: 2, actor: "person", status: "COMPLETED" })];
    expect(leadAvailability(state({ turns })).kind).toBe("WAITING");
  });

  it("reads on with no turns, a finished turn or a turn in progress", () => {
    expect(leadAvailability(state({}))).toEqual({ kind: "ON" });
    expect(leadAvailability(state({ turns: [turn({ status: "RUNNING" })] }))).toEqual({ kind: "ON" });
    expect(leadAvailability(state({ busy: true, turns: [turn({ status: "QUEUED" })] }))).toEqual({ kind: "ON" });
    expect(availabilityLabel({ kind: "ON" })).toBe("Vedoucí");
  });

  it("says unknown as unavailable, never as on", () => {
    const a = leadAvailability(null);
    expect(availabilityLabel(a)).toBe("Vedoucí nedostupný");
    expect(availabilityWords(a)).toBe("Nelze zjistit, zda Vedoucí výzkumu odpovídá.");
  });
});

describe("the worker's readiness", () => {
  it("reads available: true without a worker-ready signal as unknown, never on", () => {
    // Today's GET /lead: the API's switch on, nothing said about the worker (routers/lead.py:356-359).
    const today = { available: true, unavailable_reason: null, busy: false, turns: [] } as LeadStateWithWorker;
    expect(leadAvailability(today)).toEqual({ kind: "UNKNOWN", reason: null });
    expect(leadAvailability(state({ worker_ready: null }))).toEqual({ kind: "UNKNOWN", reason: null });
    expect(isLeadOn(leadAvailability(today))).toBe(false);
  });

  it("reads a worker that says it is not ready as waiting, with its reason", () => {
    expect(leadAvailability(state({ worker_ready: false, worker_reason: "research_lead_unconfigured" }))).toEqual({ kind: "WAITING", reason: "research_lead_unconfigured" });
    expect(leadAvailability(state({ worker_ready: false }))).toEqual({ kind: "WAITING", reason: null });
  });

  it("still reads a parked newest turn as waiting when readiness is not reported", () => {
    const turns = [turn({ status: "WAITING", reason: "research_lead_unconfigured" })];
    expect(leadAvailability(state({ worker_ready: undefined, turns }))).toEqual({ kind: "WAITING", reason: "research_lead_unconfigured" });
  });

  it("reads the API's switch off as off whatever the worker says", () => {
    expect(leadAvailability(state({ available: false, unavailable_reason: "research_lead_disabled", worker_ready: true })).kind).toBe("OFF");
  });
});

describe("leadReasonWords", () => {
  it("has words for the codes a budget park really carries, not the status name", () => {
    expect(leadReasonWords("budget_exceeded")).toMatch(/rozpočet studie/);
    expect(leadReasonWords("reservation_exhausted")).toMatch(/rozpočet studie/);
    expect(leadReasonWords("AWAITING_BUDGET")).toBe("Vedoucí se zastavil (AWAITING_BUDGET).");
  });

  it("keeps a code it has no words for, never guessing", () => {
    expect(leadReasonWords("something_new")).toBe("Vedoucí se zastavil (something_new).");
    expect(leadReasonWords(null)).toBe("Vedoucí se zastavil.");
  });
});
