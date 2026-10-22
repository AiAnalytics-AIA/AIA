// Whether the study's Research Lead answers, said once and honestly (research-lead-workbench
// chunk 27a, D20). Read from GET /studies/{id}/lead alone: its `available` and
// `unavailable_reason` are the API's own switch (apps/api/src/aia_api/routers/lead.py:350-362 @
// 095a3e68), and the newest Lead turn says whether the worker parked it. /config's copy of
// AIA_AI_RESEARCH_LEAD_ENABLED is the web container's and never read for this.
//
// ON: the API takes messages, the worker says it is ready and the newest turn did not park.
// WAITING: on, but the worker is not ready or the newest turn waits (no model configured, no route,
// a budget). OFF: the API says the Lead is switched off. UNKNOWN: not read yet, unreadable, an
// answer out of shape, or the worker's readiness not reported -- never on.
//
// The API's switch alone is not availability: with it on and the worker's switch or model keys off,
// a fresh study answers available: true while every turn parks. GET /lead is to carry the worker's
// readiness from the worker composition record (lead-orchestration LO12b, research-lead-workbench
// 27b); until it does, `worker_ready` is absent and available: true reads as UNKNOWN.

import { leadReasonWords, type LeadState, type LeadTurn } from "./lead";

/**
 * GET /lead with the worker's readiness (27b, from LO12b's composition record). `worker_ready`
 * true: the worker can answer a turn; false: it cannot, `worker_reason` saying why; absent or
 * null: not reported, which is unknown, never ready.
 */
export type LeadStateWithWorker = LeadState & { worker_ready?: boolean | null; worker_reason?: string | null };

export type LeadAvailability =
  | { kind: "ON" }
  | { kind: "WAITING"; reason: string | null }
  | { kind: "OFF"; reason: string }
  | { kind: "UNKNOWN"; reason: string | null };

/** The stored codes in words: the Lead pane's own, one table (./lead). */
export { leadReasonWords };

/** The newest turn the Lead answered or was asked to answer, by sequence; none: null. */
function newestLeadTurn(turns: readonly LeadTurn[]): LeadTurn | null {
  let newest: LeadTurn | null = null;
  for (const t of turns) if (t.actor === "lead" && (newest === null || t.sequence_no > newest.sequence_no)) newest = t;
  return newest;
}

/**
 * The Lead's availability from what GET /lead answered: ON only with an explicit worker-ready signal. `failed`: the read failed (a network
 * error, a 404 from an API without the Lead, any refusal); `state` null: not read yet.
 */
export function leadAvailability(state: LeadStateWithWorker | null | undefined, failed = false): LeadAvailability {
  if (failed) return { kind: "UNKNOWN", reason: null };
  if (!state) return { kind: "UNKNOWN", reason: null };
  if (state.available === false) return { kind: "OFF", reason: state.unavailable_reason || "research_lead_unavailable" };
  if (state.available !== true) return { kind: "UNKNOWN", reason: state.unavailable_reason ?? null };
  const newest = newestLeadTurn(Array.isArray(state.turns) ? state.turns : []);
  if (newest?.status === "WAITING") return { kind: "WAITING", reason: newest.reason };
  if (state.worker_ready === false) return { kind: "WAITING", reason: state.worker_reason ?? null };
  if (state.worker_ready !== true) return { kind: "UNKNOWN", reason: null };
  return { kind: "ON" };
}

/** Only ON is on: waiting, off and unknown are not. */
export const isLeadOn = (a: LeadAvailability): boolean => a.kind === "ON";

/** The launcher's short label (26c): one word on the Lead's state, unknown said as unavailable. */
export function availabilityLabel(a: LeadAvailability): string {
  switch (a.kind) {
    case "ON":
      return "Vedoucí";
    case "WAITING":
      return "Vedoucí čeká";
    case "OFF":
      return "Vedoucí vypnutý";
    case "UNKNOWN":
      return "Vedoucí nedostupný";
  }
}

/** The sentence beside it: the reason in words, or why the state is not known. */
export function availabilityWords(a: LeadAvailability): string {
  switch (a.kind) {
    case "ON":
      return "Vedoucí výzkumu odpovídá.";
    case "WAITING":
      return a.reason ? leadReasonWords(a.reason) : "Vedoucí výzkumu čeká.";
    case "OFF":
      return leadReasonWords(a.reason);
    case "UNKNOWN":
      return "Nelze zjistit, zda Vedoucí výzkumu odpovídá.";
  }
}
