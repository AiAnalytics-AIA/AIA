// The settings page's reading of the AI runtime: switches from /config against the
// activities the settings document describes. The page may say "on in
// configuration", "off, because", "invalid" or "unknown" -- never more.
import { describe, expect, it } from "vitest";

import { activityState, approvedClasses } from "./ai-runtime";
import type { NativeRuntime } from "./api";

const RUNTIME: NativeRuntime = {
  providers: [{ id: "aws_bedrock", label: "Amazon Bedrock", paid: true, use: "NATIVE" }],
  credential: "INSTANCE_ROLE",
  switch: "AIA_AI_RUNTIME_ENABLED",
  activities: [
    { key: "respondent_fieldwork", step_kind: "research_fieldwork", capabilities: ["SIMULATION"], versions: [], switches: ["AIA_AI_RUNTIME_ENABLED"], actions: [] },
    { key: "design_agents", step_kind: "research_agent", capabilities: ["RESEARCH_REASONING", "CRITIC"], versions: [], switches: ["AIA_AI_RUNTIME_ENABLED", "AIA_AI_RESEARCH_AGENTS_ENABLED"], actions: [] },
  ],
  unused_capabilities: ["FAST_EXTRACTION", "REPORT_WRITING", "EMBEDDING"],
};
const [FIELDWORK, DESIGN] = RUNTIME.activities;
const both = (switches: Record<string, boolean | null> | null) =>
  [activityState(RUNTIME, FIELDWORK, switches), activityState(RUNTIME, DESIGN, switches)];

describe("the AI runtime, as Settings may state it", () => {
  it("fieldwork on and design off: one configured, one off because of its own switch", () => {
    expect(both({ AIA_AI_RUNTIME_ENABLED: true, AIA_AI_RESEARCH_AGENTS_ENABLED: false })).toEqual([
      { kind: "configured", switch: null },
      { kind: "off", switch: "AIA_AI_RESEARCH_AGENTS_ENABLED" },
    ]);
  });

  it("both on: configured, which is not verified -- no state says so", () => {
    const states = both({ AIA_AI_RUNTIME_ENABLED: true, AIA_AI_RESEARCH_AGENTS_ENABLED: true });
    expect(states.map((s) => s.kind)).toEqual(["configured", "configured"]);
    expect(JSON.stringify(states)).not.toMatch(/verified|healthy|connected/i);
  });

  it("the runtime off: everything off because of the runtime, whatever the design switch says", () => {
    for (const design of [true, false, null]) {
      expect(both({ AIA_AI_RUNTIME_ENABLED: false, AIA_AI_RESEARCH_AGENTS_ENABLED: design })).toEqual([
        { kind: "off", switch: "AIA_AI_RUNTIME_ENABLED" },
        { kind: "off", switch: "AIA_AI_RUNTIME_ENABLED" },
      ]);
    }
  });

  it("a refused runtime switch: nothing starts", () => {
    expect(both({ AIA_AI_RUNTIME_ENABLED: null, AIA_AI_RESEARCH_AGENTS_ENABLED: true }).map((s) => s.kind)).toEqual(["invalid", "invalid"]);
  });

  it("a refused design switch with the runtime on stops the whole worker, fieldwork included", () => {
    expect(both({ AIA_AI_RUNTIME_ENABLED: true, AIA_AI_RESEARCH_AGENTS_ENABLED: null })).toEqual([
      { kind: "invalid", switch: "AIA_AI_RESEARCH_AGENTS_ENABLED" },
      { kind: "invalid", switch: "AIA_AI_RESEARCH_AGENTS_ENABLED" },
    ]);
  });

  it("no configuration, or a switch the page cannot see: unknown, never off or on", () => {
    expect(both(null).map((s) => s.kind)).toEqual(["unknown", "unknown"]);
    expect(both({}).map((s) => s.kind)).toEqual(["unknown", "unknown"]);
    expect(both({ AIA_AI_RUNTIME_ENABLED: true })).toEqual([
      { kind: "configured", switch: null },
      { kind: "unknown", switch: "AIA_AI_RESEARCH_AGENTS_ENABLED" },
    ]);
  });

  it("marks a data class the vocabulary does not know, instead of dropping it", () => {
    expect(approvedClasses(["CLASS_C_INTERNAL", "CLASS_Z"], ["CLASS_A_CLIENT_CONFIDENTIAL", "CLASS_C_INTERNAL"])).toEqual([
      { id: "CLASS_C_INTERNAL", known: true },
      { id: "CLASS_Z", known: false },
    ]);
    expect(approvedClasses([], ["CLASS_C_INTERNAL"])).toEqual([]);
  });
});
