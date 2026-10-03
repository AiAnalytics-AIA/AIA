// The switches native AI activities are turned on by, in the worker's environment
// (apps/executors/src/aia_executors/ai_runtime.py). Compose hands the web the same
// raw values; the settings document names which activity needs which.
export const AI_SWITCHES = ["AIA_AI_RUNTIME_ENABLED", "AIA_AI_RESEARCH_AGENTS_ENABLED", "AIA_AI_ANALYSIS_ENABLED"] as const;

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
  build: { sha: string | null; built_at: string | null };
};

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
