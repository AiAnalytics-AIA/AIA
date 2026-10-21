// Whether the study's Research Lead answers, said once and honestly (research-lead-workbench
// chunk 27a, D20). Read from GET /studies/{id}/lead alone: its `available` and
// `unavailable_reason` are the API's own switch (apps/api/src/aia_api/routers/lead.py:350-362 @
// 095a3e68), and the newest Lead turn says whether the worker parked it. /config's copy of
// AIA_AI_RESEARCH_LEAD_ENABLED is the web container's and never read for this.
//
// ON: the API takes messages and the newest turn did not park. WAITING: on, but the newest turn
// waits (the worker's model is not configured, no route, a budget). OFF: the API says the Lead is
// switched off. UNKNOWN: not read yet, unreadable, or an answer out of shape -- never on.

import type { LeadState, LeadTurn } from "./lead";

export type LeadAvailability =
  | { kind: "ON" }
  | { kind: "WAITING"; reason: string | null }
  | { kind: "OFF"; reason: string }
  | { kind: "UNKNOWN"; reason: string | null };

/** The stored codes in words. The pane's own map (LeadPane.tsx:36-50) moves here when 26c wires it. */
export const LEAD_REASON_WORDS: Readonly<Record<string, string>> = {
  research_lead_unavailable: "Vedoucí výzkumu není v tomto prostředí zapnutý.",
  research_lead_disabled: "Vedoucí výzkumu není v tomto prostředí zapnutý.",
  egress_unclassified_material: "Tuto zprávu zatím nelze poslat modelu: materiál studie není klasifikovaný. Rozhoduje o tom správce AIA.",
  egress_no_approved_route: "Vedoucí výzkumu čeká: pro model AI není schválená trasa.",
  egress_route_not_approved_for_class: "Tuto studii nelze poslat modelu: trasa AI není schválena pro třídu jejích dat.",
  research_lead_unconfigured: "Vedoucí výzkumu čeká: model AI není pro pracovníka nastavený.",
  ai_runtime_unavailable: "Vedoucí výzkumu čeká: AI v tomto prostředí neběží.",
  licence_undetermined: "Tuto studii nelze poslat modelu: licence dat panelu to neumožňuje.",
  lead_context_too_large: "Studie je pro jednu odpověď příliš velká. Zkuste se zeptat na konkrétní část.",
  lead_busy: "Vedoucí ještě odpovídá na předchozí zprávu.",
  lead_not_hatched: "Nejdřív si vylíhněte vlastního Vedoucího výzkumu.",
  AWAITING_BUDGET: "Vedoucí čeká na rozpočet studie.",
};

/** A code in words; a code with no words keeps the code, never a guess at what it means. */
export function leadReasonWords(code: string | null | undefined): string {
  if (!code) return "Vedoucí se zastavil.";
  return LEAD_REASON_WORDS[code] ?? `Vedoucí se zastavil (${code}).`;
}

/** The newest turn the Lead answered or was asked to answer, by sequence; none: null. */
function newestLeadTurn(turns: readonly LeadTurn[]): LeadTurn | null {
  let newest: LeadTurn | null = null;
  for (const t of turns) if (t.actor === "lead" && (newest === null || t.sequence_no > newest.sequence_no)) newest = t;
  return newest;
}

/**
 * The Lead's availability from what GET /lead answered. `failed`: the read failed (a network
 * error, a 404 from an API without the Lead, any refusal); `state` null: not read yet.
 */
export function leadAvailability(state: LeadState | null | undefined, failed = false): LeadAvailability {
  if (failed) return { kind: "UNKNOWN", reason: null };
  if (!state) return { kind: "UNKNOWN", reason: null };
  if (state.available === false) return { kind: "OFF", reason: state.unavailable_reason || "research_lead_unavailable" };
  if (state.available !== true) return { kind: "UNKNOWN", reason: state.unavailable_reason ?? null };
  const newest = newestLeadTurn(Array.isArray(state.turns) ? state.turns : []);
  if (newest?.status === "WAITING") return { kind: "WAITING", reason: newest.reason };
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
