import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, runtimeSwitch } from "./route";

afterEach(() => vi.unstubAllEnvs());

describe("public AI configuration", () => {
  it("reports the runtime switch and pinned route without credentials or a provider call", async () => {
    vi.stubEnv("AIA_AI_RUNTIME_ENABLED", "true");
    vi.stubEnv("AIA_BEDROCK_REGION", "eu-central-1");
    vi.stubEnv("AIA_BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0");
    vi.stubEnv("AIA_AI_ROUTE_APPROVED_FOR", "CLASS_C_INTERNAL");
    vi.stubEnv("ANTHROPIC_API_KEY", "secret-not-for-browser");
    vi.stubEnv("AWS_SECRET_ACCESS_KEY", "role-secret-not-for-browser");
    const response = GET();
    const config = await response.json();
    expect(config.aiRuntime).toEqual({
      enabled: true, researchAgentsEnabled: false, provider: "aws_bedrock", region: "eu-central-1",
      model: "eu.anthropic.claude-sonnet-4-5-20250929-v1:0", approvedFor: "CLASS_C_INTERNAL",
    });
    expect(JSON.stringify(config)).not.toContain("secret-not-for-browser");
    expect(response.headers.get("Cache-Control")).toBe("no-store");
  });
  it("does not announce activation when the switch is absent or false", async () => {
    vi.stubEnv("AIA_AI_RUNTIME_ENABLED", undefined);
    vi.stubEnv("AIA_AI_RESEARCH_AGENTS_ENABLED", "true");
    expect((await GET().json()).aiRuntime.enabled).toBe(false);
    expect((await GET().json()).aiRuntime.researchAgentsEnabled).toBe(false);
    vi.stubEnv("AIA_AI_RUNTIME_ENABLED", "false");
    expect((await GET().json()).aiRuntime.enabled).toBe(false);
    vi.stubEnv("AIA_AI_RUNTIME_ENABLED", "true");
    expect((await GET().json()).aiRuntime.researchAgentsEnabled).toBe(true);
  });
  it("reads the switch with the worker's vocabulary, so the page never says off while calls run", async () => {
    for (const on of ["1", "true", "yes", "on", " TRUE ", "On"]) {
      vi.stubEnv("AIA_AI_RUNTIME_ENABLED", on);
      vi.stubEnv("AIA_AI_RESEARCH_AGENTS_ENABLED", on);
      expect((await GET().json()).aiRuntime.enabled, on).toBe(true);
      expect((await GET().json()).aiRuntime.researchAgentsEnabled, on).toBe(true);
    }
    for (const off of ["0", "false", "no", "off", "", "  "]) {
      vi.stubEnv("AIA_AI_RUNTIME_ENABLED", off);
      expect((await GET().json()).aiRuntime.enabled, JSON.stringify(off)).toBe(false);
    }
  });
  it("reports a value the worker refuses as unknown, not as off", async () => {
    expect(runtimeSwitch("enabled")).toBeNull();
    expect(runtimeSwitch("2")).toBeNull();
    vi.stubEnv("AIA_AI_RUNTIME_ENABLED", "ture");
    expect((await GET().json()).aiRuntime.enabled).toBeNull();
    expect((await GET().json()).aiRuntime.researchAgentsEnabled).toBeNull();
    vi.stubEnv("AIA_AI_RUNTIME_ENABLED", "true");
    vi.stubEnv("AIA_AI_RESEARCH_AGENTS_ENABLED", "ture");
    expect((await GET().json()).aiRuntime.researchAgentsEnabled).toBeNull();
  });
});
