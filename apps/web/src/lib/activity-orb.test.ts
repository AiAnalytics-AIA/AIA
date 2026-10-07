// An orb shows only while the API reports a step RUNNING; a model's step is tinted
// as AI, a step that is code as work in progress.
import { describe, expect, it } from "vitest";

import { AGENT_ORB, agentJobOrb, deepResearchRunOrb, deepResearchStepOrb, researchStepOrb } from "./activity-orb";
import type { ResearchAgentAction } from "./api";

const step = (node_key: string, status: string) => ({ node_key, status }) as never;
const NOT_RUNNING = ["RUNNABLE", "BLOCKED", "SUCCEEDED", "FAILED", "CANCELLED", "WAITING_PROVIDER", "WAITING_CAPACITY", "AWAITING_BUDGET", "AWAITING_GATE", "RECOVERY_REQUIRED"];

describe("a research agent job", () => {
  it("shows its action's AI orb while its step runs", () => {
    expect(agentJobOrb({ action: "build_questionnaire", steps: [step("agent", "RUNNING")] })).toEqual({ state: "composing", ink: "ai" });
  });

  it.each(NOT_RUNNING)("shows none while its step is %s", (status) => {
    expect(agentJobOrb({ action: "build_questionnaire", steps: [step("agent", status)] })).toBeNull();
  });

  it("shows none before it has a step", () => {
    expect(agentJobOrb({ action: "analyze_brief", steps: [] })).toBeNull();
  });

  it("names a state for every action", () => {
    const actions: ResearchAgentAction[] = ["analyze_brief", "build_questionnaire", "optimize_questionnaire", "propose_audience", "suggest_dimensions", "critique_design", "design_copilot", "answer_memory"];
    expect(Object.keys(AGENT_ORB).sort()).toEqual([...actions].sort());
  });
});

describe("a research run's step", () => {
  const ai = { fieldwork_source: "ai_runtime" };
  const fixture = { fieldwork_source: "synthetic_fixture" };

  it("AI fieldwork thinks; fictional fixture fieldwork works as code", () => {
    expect(researchStepOrb(ai, step("run", "RUNNING"))).toEqual({ state: "listening", ink: "ai" });
    expect(researchStepOrb(fixture, step("run", "RUNNING"))).toEqual({ state: "listening", ink: "running" });
  });

  it("an analysis module thinks", () => {
    expect(researchStepOrb(fixture, step("analysis_executive", "RUNNING"))).toEqual({ state: "working", ink: "ai" });
  });

  it.each(["compile", "preflight", "aggregate", "sociomap", "sociomapping", "sociomapping_report", "report", "a_step_added_later"])("%s works as code", (key) => {
    expect(researchStepOrb(ai, step(key, "RUNNING"))?.ink).toBe("running");
  });

  it.each(NOT_RUNNING)("a step %s shows none", (status) => {
    expect(researchStepOrb(ai, step("run", status))).toBeNull();
    expect(researchStepOrb(ai, step("aggregate", status))).toBeNull();
  });
});

describe("a Deep Research step", () => {
  it.each([
    ["plan", "shaping", "ai"],
    ["investigate", "searching", "ai"],
    ["investigate/track-1", "searching", "ai"],
    ["merge", "weaving", "running"],
    ["verify", "solving", "ai"],
    ["synthesize", "composing", "ai"],
    ["publish", "composing", "running"],
  ])("%s runs as %s, %s", (key, state, ink) => {
    expect(deepResearchStepOrb(step(key, "RUNNING"))).toEqual({ state, ink });
  });

  it("a run shows the step thinking before one working, and none when nothing runs", () => {
    expect(deepResearchRunOrb([step("merge", "RUNNING"), step("investigate/a", "RUNNING")])).toEqual({ state: "searching", ink: "ai" });
    expect(deepResearchRunOrb([step("plan", "SUCCEEDED"), step("merge", "RUNNING")])).toEqual({ state: "weaving", ink: "running" });
    expect(deepResearchRunOrb([step("verify", "WAITING_PROVIDER")])).toBeNull();
  });
});
