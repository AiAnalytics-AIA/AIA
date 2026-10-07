// The settings page's reading of the AI runtime: switches from /config against the
// activities the settings document describes. The page may say "on in
// configuration", "off, because", "invalid" or "unknown" -- never more.
import { describe, expect, it } from "vitest";

import { activityState, approvedClasses, needsOf } from "./ai-runtime";
import type { NativeRuntime } from "./api";

const RUNTIME: NativeRuntime = {
  providers: [{ id: "aws_bedrock", label: "Amazon Bedrock", paid: true, use: "NATIVE" }],
  credential: "INSTANCE_ROLE",
  switch: "AIA_AI_RUNTIME_ENABLED",
  strict_switches: [],
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

// Deep Research's switches, as the worker reads them (aia_executors/deep_research_runtime.py,
// held there by apps/executors/tests/test_settings_presentation.py).
const DR = "AIA_DEEP_RESEARCH_ENABLED";
const DIRECTED = "AIA_DEEP_RESEARCH_AGENT_DIRECTED";
const LEAD = "AIA_DEEP_RESEARCH_LEAD";
const WITH_DR: NativeRuntime = {
  ...RUNTIME,
  strict_switches: [DR, DIRECTED, LEAD],
  activities: [
    ...RUNTIME.activities,
    { key: "deep_research", step_kind: "deep_research_plan", capabilities: ["RESEARCH_REASONING", "CRITIC"], versions: [], switches: ["AIA_AI_RUNTIME_ENABLED", "AIA_AI_RESEARCH_AGENTS_ENABLED", DR], actions: [] },
    { key: "deep_research_lead", step_kind: "deep_research_plan", capabilities: ["RESEARCH_LEAD"], versions: [], switches: ["AIA_AI_RUNTIME_ENABLED", "AIA_AI_RESEARCH_AGENTS_ENABLED", DR, DIRECTED, LEAD], actions: [] },
  ],
};
const [, , RESEARCH, LEADING] = WITH_DR.activities;
const ALL_ON = { AIA_AI_RUNTIME_ENABLED: true, AIA_AI_RESEARCH_AGENTS_ENABLED: true, [DR]: true, [DIRECTED]: true, [LEAD]: true };

describe("Deep Research's strict switches", () => {
  it("names what each one needs: every switch before it, in any activity that lists it", () => {
    expect(needsOf(WITH_DR, DR)).toEqual(["AIA_AI_RUNTIME_ENABLED", "AIA_AI_RESEARCH_AGENTS_ENABLED"]);
    expect(needsOf(WITH_DR, LEAD)).toEqual(["AIA_AI_RUNTIME_ENABLED", "AIA_AI_RESEARCH_AGENTS_ENABLED", DR, DIRECTED]);
  });

  it("everything on: both configured; the lead off: research configured, the lead off by its switch", () => {
    expect([activityState(WITH_DR, RESEARCH, ALL_ON), activityState(WITH_DR, LEADING, ALL_ON)].map((s) => s.kind)).toEqual(["configured", "configured"]);
    expect(activityState(WITH_DR, LEADING, { ...ALL_ON, [LEAD]: false })).toEqual({ kind: "off", switch: LEAD });
    expect(activityState(WITH_DR, RESEARCH, { ...ALL_ON, [LEAD]: false })).toEqual({ kind: "configured", switch: null });
  });

  it("on with the runtime off is not 'off': the worker does not start, so nothing runs", () => {
    const states = WITH_DR.activities.map((a) => activityState(WITH_DR, a, { ...ALL_ON, AIA_AI_RUNTIME_ENABLED: false }));
    expect(states).toEqual(WITH_DR.activities.map(() => ({ kind: "invalid", switch: DR, needs: "AIA_AI_RUNTIME_ENABLED" })));
  });

  it("the lead on without agent-directed research stops the worker, fieldwork included", () => {
    expect(activityState(WITH_DR, FIELDWORK, { ...ALL_ON, [DIRECTED]: false })).toEqual({ kind: "invalid", switch: LEAD, needs: DIRECTED });
  });

  it("a refused value stops the worker even with the runtime off", () => {
    expect(activityState(WITH_DR, FIELDWORK, { AIA_AI_RUNTIME_ENABLED: false, [DR]: null })).toEqual({ kind: "invalid", switch: DR });
  });

  it("all off with the runtime off: off because of the runtime, as before", () => {
    const off = { AIA_AI_RUNTIME_ENABLED: false, AIA_AI_RESEARCH_AGENTS_ENABLED: false, [DR]: false, [DIRECTED]: false, [LEAD]: false };
    expect(activityState(WITH_DR, RESEARCH, off)).toEqual({ kind: "off", switch: "AIA_AI_RUNTIME_ENABLED" });
  });

  it("a need the page cannot see is not a refusal: it says unknown instead", () => {
    expect(activityState(WITH_DR, RESEARCH, { AIA_AI_RUNTIME_ENABLED: true, [DR]: true })).toEqual({ kind: "unknown", switch: "AIA_AI_RESEARCH_AGENTS_ENABLED" });
  });
});
