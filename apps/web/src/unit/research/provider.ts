// Is the AI provider ready before an AI step starts? (ADR 0014, area A4)
// ensureClaudeReady1776's effective binding, ported: for Claude Code, the
// edition must enable it and GET /api/providers/claude-code/status must say ok;
// for the Claude API, POST /api/settings/ai_check must. The classic interface
// then jumps to Nastavení and alerts; a rebuilt step shows the notice where the
// person is and links to the settings instead (research-flow-rehome.md).

import { unit } from "../client";
import type { BootInfo } from "../boot";

/** providerLabel1790's effective binding (the reassignment @_providerLabel1850). */
export function providerLabel(p: string): string {
  return p === "openai" ? "OpenAI API" : p === "anthropic" ? "Claude API" : "Claude Code";
}

/** activeProvider1790: the project's preferred provider, its run policy's, the unit's default. */
export function activeProvider(preferred: string | null, runPolicyProvider: unknown, boot: Pick<BootInfo, "ai_provider">): string {
  return preferred || (typeof runPolicyProvider === "string" && runPolicyProvider) || boot.ai_provider || "claude_code_subscription";
}

/** Legacy design jobs have not been migrated to the governed Bedrock runtime. */
export function notReadyMessage(): string {
  return "AI návrh výzkumu zatím není dostupný. Amazon Bedrock nyní zajišťuje odpovědi respondentů. Projekt zůstává uložený.";
}

const isRecord = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

/** BOOT.edition.claude_code_enabled: the edition's own switch for Claude Code. */
export function claudeCodeEnabled(boot: Pick<BootInfo, "raw">): boolean {
  const edition = boot.raw.edition;
  return isRecord(edition) && Boolean(edition.claude_code_enabled);
}

/** True when an AI step may start with `provider`; any failure to ask is "not ready". */
export async function providerReady(
  provider: string,
  { boot, model, fetchImpl }: { boot: Pick<BootInfo, "raw">; model?: string; fetchImpl?: typeof fetch },
): Promise<boolean> {
  try {
    if (provider === "claude_code_subscription") {
      if (!claudeCodeEnabled(boot)) return false;
      const r = await unit("claudeCodeStatus", { fetchImpl });
      return isRecord(r) && Boolean(r.ok);
    }
    const r = await unit("settingsAiCheck", {
      body: { provider: "anthropic", anthropic_model: model || "sonnet" },
      timeoutMs: 120_000,
      fetchImpl,
    });
    return isRecord(r) && Boolean(r.ok);
  } catch {
    return false;
  }
}
