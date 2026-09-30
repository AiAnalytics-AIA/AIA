import { NextResponse } from "next/server";

import { buildIdentity } from "@/lib/build";

// Runtime configuration for the browser. Read from the server's environment at
// request time, so one image serves any environment: NEXT_PUBLIC_* values would
// be baked in at `next build` and make the SHA-tagged image environment-specific.
// Nothing here is a secret: the Cognito app client is public (PKCE) by design.
export const dynamic = "force-dynamic";

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

export function GET() {
  const switches = Object.fromEntries(AI_SWITCHES.map((name) => [name, runtimeSwitch(process.env[name])])) as PublicConfig["aiRuntime"]["switches"];
  const runtime = switches.AIA_AI_RUNTIME_ENABLED;
  const config: PublicConfig = {
    cognitoDomain: process.env.AIA_COGNITO_DOMAIN?.trim() || null,
    cognitoClientId: process.env.AIA_COGNITO_CLIENT_ID?.trim() || null,
    publicOrigin: process.env.AIA_PUBLIC_ORIGIN?.trim() || null,
    apiBase: process.env.AIA_API_BASE?.trim() || "",
    aiRuntime: {
      enabled: runtime,
      researchAgentsEnabled: runtime === false ? false : runtime === null ? null : switches.AIA_AI_RESEARCH_AGENTS_ENABLED,
      provider: "aws_bedrock",
      region: process.env.AIA_BEDROCK_REGION?.trim() || null,
      model: process.env.AIA_BEDROCK_MODEL_ID?.trim() || null,
      approvedFor: process.env.AIA_AI_ROUTE_APPROVED_FOR?.trim() || null,
      approvedClasses: approvedClasses(process.env.AIA_AI_ROUTE_APPROVED_FOR),
      switches,
    },
    build: buildIdentity(),
  };
  return NextResponse.json(config, { headers: { "Cache-Control": "no-store" } });
}
