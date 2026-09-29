import { describe, expect, it } from "vitest";

import { legacyContext, statement } from "@/testing/legacy";
import { type JobRead, fmtTime, jobMeta, jobMetaLine, usualRange } from "./jobs";

// The meta-line statement inside the original job body, evaluated verbatim. The
// job panel of AIA's research agent jobs prints it (lib/research-agent-jobs.ts);
// the unit's own job runner it came from is gone (ADR 0018).
const legacy = legacyContext({
  prelude: [
    "var aiProviderLabel=function(){return 'AI partner'};",
    `var __meta=function(t,payload,elapsed){let pm={textContent:''};${statement("let hb=t.heartbeat_age_seconds==null?'—':fmtTime(t.heartbeat_age_seconds)", "+' · '+cost;")}return pm.textContent};`,
  ],
  functions: ["fmtTime", "usualRange"],
});

describe("time formats are the classic ones", () => {
  it.each([0, 0.4, 1, 59.4, 59.6, 60, 61, 119.5, 3599, 3600, 3661, 7322, -5, null, "12"])("fmtTime(%j)", (x) => {
    expect(fmtTime(x)).toBe(legacy.run("fmtTime(__x)", { __x: x }));
  });
  it.each([[[10, 90]], [[1]], [null], ["x"], [[3600, 7200]]])("usualRange(%j)", (x) => {
    expect(usualRange(x)).toBe(legacy.run("usualRange(__x)", { __x: x }));
  });
});

describe("the meta line is the classic one", () => {
  const telemetries = [
    {},
    { elapsed_seconds: 75, usual_seconds: [30, 90], hard_seconds: 900, provider_stage: "print", heartbeat_age_seconds: 3, provider: "claude_code_subscription", model: "sonnet" },
    { provider: "anthropic", actual_cost_usd: 0.01234 },
    { provider: "anthropic", estimated_cost_usd: 0.5, heartbeat_age_seconds: 0 },
    { provider: "strict_claude_x" },
  ];
  it.each(telemetries.map((t, i) => [i, t] as const))("telemetry %i", (_, t) => {
    // The classic job computes `elapsed` first: Number(t.elapsed_seconds ?? <wall clock>).
    const expected = legacy.run("__meta(__t,__payload,Number(__t.elapsed_seconds??42))", { __t: t, __payload: { model: "opus" } });
    expect(jobMetaLine(jobMeta({ telemetry: t } as JobRead, { model: "opus", elapsed: 42 }))).toBe(expected);
  });
});
