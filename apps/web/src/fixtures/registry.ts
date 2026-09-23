/**
 * What the web client does NOT get from the API, in two machine-readable lists.
 *
 * `FIXTURE_CAPABILITIES` — screens still rendered from development fixtures.
 * `UNAVAILABLE_CAPABILITIES` — capabilities the slice shows as explicitly
 * unavailable, because the backend has no route or contract for them yet. They
 * are never filled with look-alike data.
 *
 * `.length` of each is the number the product-surface status reports. A fixture
 * or an "unavailable" panel that is not listed here is a defect, and
 * `registry.test.ts` fails on one. Remove an entry in the same change that wires
 * the real endpoint.
 */

export type Owner = "product-surface" | "platform-runtime" | "integration-architecture" | "analysis-governance";

export type FixtureCapability = {
  id: string;
  /** What the screen shows from fixture data. */
  capability: string;
  /** Why it is still a fixture. */
  reason: "not-wired-yet" | "no-http-route" | "no-contract";
  /** Who must provide the missing route or contract, when it is not the web client. */
  owner: Owner;
  /** Register entry, when one exists. */
  register?: string;
};

export const FIXTURE_CAPABILITIES: readonly FixtureCapability[] = [
  { id: "stage-artifacts", capability: "Stage: artifact list and upload", reason: "no-http-route", owner: "platform-runtime" },
  { id: "report-draft", capability: "Report stage: draft editor and assistant proposals", reason: "no-http-route", owner: "platform-runtime" },
] as const;

export type UnavailableCapability = {
  id: string;
  capability: string;
  /** `degraded`: shown, but through a stated temporary substitute. */
  reason: "no-http-route" | "no-contract" | "degraded";
  owner: Owner;
  register?: string;
};

export const UNAVAILABLE_CAPABILITIES: readonly UnavailableCapability[] = [
  { id: "needs-me", capability: "Portfolio: what is waiting on this viewer", reason: "no-contract", owner: "integration-architecture", register: "OI-11" },
  { id: "workflow-runs", capability: "Project: workflow runs, steps and attempts", reason: "no-http-route", owner: "platform-runtime", register: "OI-26" },
  { id: "approvals", capability: "Project: gates and approvals awaiting a decision", reason: "no-http-route", owner: "platform-runtime", register: "OI-26" },
  { id: "budget-reservations", capability: "Study: cost reservations and the usage ledger", reason: "no-http-route", owner: "platform-runtime", register: "OI-26" },
  { id: "impact-estimate", capability: "Impact preview: cost and duration of recomputation", reason: "no-contract", owner: "integration-architecture", register: "OI-10" },
  { id: "client-accent", capability: "Scope chrome: persisted client accent slot", reason: "degraded", owner: "integration-architecture", register: "OI-12" },
  { id: "sign-in", capability: "Authenticated web session (the client uses a development identity)", reason: "no-contract", owner: "product-surface", register: "OI-25" },
] as const;

export function unavailable(id: string): UnavailableCapability | undefined {
  return UNAVAILABLE_CAPABILITIES.find((c) => c.id === id);
}
