import { describe, expect, it, vi } from "vitest";

import { effective } from "../testing/legacy";
import { activeProvider, claudeCodeEnabled, notReadyMessage, providerReady } from "./provider";

const answer = (body: unknown, status = 200) =>
  vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
const on = { raw: { edition: { claude_code_enabled: true } } };

describe("the provider an AI step runs on", () => {
  it("is activeProvider1790's order: preferred, run policy, the unit's default", () => {
    expect(effective("activeProvider1790")).toContain(
      "PROJECT_META_1790?.preferred_provider||PROJECT?.run_policy?.provider||BOOT?.ai_provider||'claude_code_subscription'",
    );
    expect(activeProvider("anthropic", "claude_code_subscription", { ai_provider: "x" })).toBe("anthropic");
    expect(activeProvider(null, "anthropic", { ai_provider: "x" })).toBe("anthropic");
    expect(activeProvider(null, undefined, { ai_provider: "openai" })).toBe("openai");
    expect(activeProvider(null, "", {})).toBe("claude_code_subscription");
  });

  it("says it is not ready in the classic words", () => {
    expect(effective("ensureClaudeReady1776")).toContain("alert(providerLabel1790(p)+' není připravený. Projekt zůstává uložený.')");
    expect(notReadyMessage("anthropic")).toBe("Claude API není připravený. Projekt zůstává uložený.");
  });
});

describe("providerReady", () => {
  it("Claude Code: the edition must enable it before the status is asked", async () => {
    const f = answer({ ok: true });
    expect(claudeCodeEnabled({ raw: {} })).toBe(false);
    await expect(providerReady("claude_code_subscription", { boot: { raw: {} }, fetchImpl: f })).resolves.toBe(false);
    expect(f).not.toHaveBeenCalled();
    await expect(providerReady("claude_code_subscription", { boot: on, fetchImpl: f })).resolves.toBe(true);
    expect(f.mock.calls[0][0]).toBe("/api/providers/claude-code/status");
  });

  it("Claude Code: not ok, or no answer, is not ready", async () => {
    await expect(providerReady("claude_code_subscription", { boot: on, fetchImpl: answer({ ok: false }) })).resolves.toBe(false);
    await expect(providerReady("claude_code_subscription", { boot: on, fetchImpl: answer({ error: "x" }, 500) })).resolves.toBe(false);
  });

  it("Claude API: the settings check with the project's model", async () => {
    const f = answer({ ok: true });
    await expect(providerReady("anthropic", { boot: on, model: "opus", fetchImpl: f })).resolves.toBe(true);
    expect(f.mock.calls[0][0]).toBe("/api/settings/ai_check");
    expect((f.mock.calls[0][1] as RequestInit).body).toBe('{"provider":"anthropic","anthropic_model":"opus"}');
    await expect(providerReady("anthropic", { boot: on, fetchImpl: answer({ ok: false }) })).resolves.toBe(false);
  });
});
