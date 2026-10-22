// The switches native AI activities are turned on by, in the worker's environment
// (apps/executors/src/aia_executors/ai_runtime.py). Compose hands the web the same
// raw values; the settings document names which activity needs which.
export const AI_SWITCHES = [
  "AIA_AI_RUNTIME_ENABLED",
  "AIA_AI_RESEARCH_AGENTS_ENABLED",
  "AIA_AI_ANALYSIS_ENABLED",
  "AIA_AI_RESEARCH_LEAD_ENABLED",
  "AIA_DEEP_RESEARCH_ENABLED",
  "AIA_DEEP_RESEARCH_AGENT_DIRECTED",
  "AIA_DEEP_RESEARCH_LEAD",
] as const;

export type PublicConfig = {
  cognitoDomain: string | null;
  cognitoClientId: string | null;
  publicOrigin: string | null;
  apiBase: string;
  // A display of the deployment's AI configuration, never a health check: nothing
  // here says the worker accepted it or that Bedrock answered.
  aiRuntime: {
    // null means a flag value the worker rejects.
    enabled: boolean | null;
    researchAgentsEnabled: boolean | null;
    provider: "aws_bedrock";
    region: string | null;
    model: string | null;
    // AIA_AI_ROUTE_APPROVED_FOR as given; approvedClasses is the same, split as the worker splits it.
    approvedFor: string | null;
    approvedClasses: string[];
    // Each switch by its variable name, read with the worker's vocabulary.
    switches: Record<(typeof AI_SWITCHES)[number], boolean | null>;
  };
  // The research workbench (ADR 0026): the study screen as conversation beside artifact.
  // AIA_WEB_RESEARCH_WORKBENCH; unset or not a switch value, off.
  workbench: boolean;
  // Stable item ids (working-copy-edit-ops WCE1): the study's store writes each plan item's,
  // option's and object's id beside it and follows a reworded research question's links.
  // AIA_WEB_STABLE_ITEM_IDS; unset or not a switch value, off (the server keys by ids either way).
  stableItemIds: boolean;
  // Display conditions (working-copy-edit-ops WCE13): Dotazník sets one at its question only
  // under AIA_ROUTING_ENABLED, one key for the API and the web alike (the API's readiness reads it
  // in WCE13 (d)), so a deployment sets it on both; off until fieldwork routes by it (RQC11).
  // Unset or not a switch value, off: a stored condition is still shown, and can be removed.
  routing: boolean;
  build: { sha: string | null; built_at: string | null };
  // Where the browser reports an error it could not handle (GlitchTip; lib/error-tracking.ts).
  // A DSN's key is public by design: it can only send events. null: nothing is loaded.
  errorTracking: { dsn: string | null; environment: string | null; release: string | null };
};

// A DSN as GlitchTip and Sentry write one: http(s)://<key>@<host>[:port]/<project id>. The
// API and the worker refuse a malformed one at start (aia_core error_tracking); /config cannot
// refuse to answer, so it reports none and says why in the server's log.
const DSN_SHAPE = /^https?:\/\/[A-Za-z0-9]+@[A-Za-z0-9.-]+(:\d+)?\/\d+$/;

export function errorTrackingDsn(raw: string | undefined): string | null {
  const value = (raw ?? "").trim();
  if (!value) return null;
  if (!DSN_SHAPE.test(value)) {
    console.error("AIA_WEB_ERROR_TRACKING_DSN is not a DSN; browser error tracking is off");
    return null;
  }
  return value;
}

// The worker's vocabulary for AIA_AI_RUNTIME_ENABLED (apps/executors/src/aia_executors/
// ai_runtime.py, _TRUE/_FALSE). Compose hands both services the same raw value, so the
// page must read it the same way or it reports "off" while respondent calls run.
const TRUE = new Set(["1", "true", "yes", "on"]);
const FALSE = new Set(["0", "false", "no", "off", ""]);

export function runtimeSwitch(raw: string | undefined): boolean | null {
  if (raw === undefined) return false;
  const value = raw.trim().toLowerCase();
  if (TRUE.has(value)) return true;
  if (FALSE.has(value)) return false;
  return null;
}

/** AIA_AI_ROUTE_APPROVED_FOR as the worker reads it: comma-separated, blanks dropped. */
export function approvedClasses(raw: string | undefined): string[] {
  return (raw ?? "").split(",").map((c) => c.trim()).filter(Boolean);
}

