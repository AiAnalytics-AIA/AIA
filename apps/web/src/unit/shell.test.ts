import { describe, expect, it } from "vitest";

import { parseBootstrap, parseClaudeCode } from "./shell";

describe("the rail's status", () => {
  it("prints the joint core status the unit reports, never a stamped VALID", () => {
    expect(parseBootstrap({ edition: { version: "18.6.6" }, joint_core: { status: "JOINT_UNVALIDATED" } })).toEqual({
      release: "18.6.6",
      jointCore: "JOINT_UNVALIDATED",
    });
  });
  it("prints nothing it was not told", () => {
    expect(parseBootstrap({ edition: {}, joint_core: null })).toEqual({ release: null, jointCore: null });
    expect(() => parseBootstrap([])).toThrow();
  });
  it("is READY only on an explicit ok", () => {
    expect(parseClaudeCode({ ok: true })).toBe("READY");
    expect(parseClaudeCode({ ok: "yes" })).toBe("CHECK");
    expect(parseClaudeCode({ ok: false, kind: "ERROR" })).toBe("CHECK");
    expect(parseClaudeCode(null)).toBeNull();
  });
});
