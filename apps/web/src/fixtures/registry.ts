/**
 * Every capability the web client still renders from development fixtures.
 *
 * Machine-readable on purpose: `FIXTURE_CAPABILITIES.length` is the number the
 * product-surface status reports, and a fixture that is not listed here is a
 * defect. Remove an entry in the same change that wires the real endpoint.
 */

export type FixtureCapability = {
  id: string;
  /** What the screen shows from fixture data. */
  capability: string;
  /** Why it is still a fixture. */
  reason: "not-wired-yet" | "no-http-route" | "no-contract";
  /** Who must provide the missing route or contract, when it is not the web client. */
  owner: "product-surface" | "platform-runtime" | "integration-architecture" | "analysis-governance";
  /** Register entry, when one exists. */
  register?: string;
};

export const FIXTURE_CAPABILITIES: readonly FixtureCapability[] = [
  { id: "portfolio-studies", capability: "Portfolio: studies across clients", reason: "not-wired-yet", owner: "product-surface" },
  { id: "study-projects", capability: "Study: its projects", reason: "not-wired-yet", owner: "product-surface" },
  { id: "project-stages", capability: "Project: 13 stages and their status", reason: "not-wired-yet", owner: "product-surface" },
  { id: "stage-artifacts", capability: "Stage: artifact list and upload", reason: "no-http-route", owner: "platform-runtime" },
  { id: "report-draft", capability: "Report stage: draft editor and assistant proposals", reason: "no-http-route", owner: "platform-runtime" },
] as const;
