// The workbench's eleven stages over today's routes (research-lead-workbench D2): every stage
// reaches a route, every route shows a stage, and a stage's tone is the lane's.
import { describe, expect, it } from "vitest";

import { PHASES, STAGES, STAGE_ORDER, stageHref, stageOf, stageState } from "./workbench-stages";
import type { StepKey } from "@/research/steps";

const href = (step: StepKey) => `/s/${step}`;

describe("workbench stages", () => {
  it("are the prototype's eleven, each in one of the six phases", () => {
    expect(STAGE_ORDER).toHaveLength(11);
    const phases = new Set(PHASES.map((p) => p.id));
    for (const s of STAGE_ORDER) expect(phases.has(STAGES[s].phase)).toBe(true);
  });

  it("each open a route, and the route shows the same stage back", () => {
    for (const s of STAGE_ORDER) {
      const url = stageHref(s, href);
      const [path, hash = ""] = url.split("#");
      const step = path!.split("/").pop() as StepKey;
      expect(stageOf(step, hash ? `#${hash}` : ""), s).toBe(s);
    }
  });

  it("put the result views on Výsledky by the hash ResultsWorkspace reads, old anchors included", () => {
    expect(stageHref("sociomap", href)).toBe("/s/results#maps");
    expect(stageOf("results", "#measure-q3")).toBe("results");
    expect(stageOf("results", "#res-sociomap")).toBe("sociomap");
    expect(stageOf("results", "#res-literature")).toBe("report");
    expect(stageOf("results", "")).toBe("results");
    expect(stageOf("progress", "")).toBe("fieldwork");
  });

  it("read their state from the lane and say nothing for a stage the lane does not know", () => {
    const lane = {
      persona: { tone: "done" as const, line: "2 dimenze · N=600" },
      run: { tone: "done" as const, line: "Spuštěno 1×" },
      progress: { tone: "running" as const, line: "Běh 1: běží" },
      results: { tone: "idle" as const, line: "Zatím nic" },
    };
    expect(stageState("sample", lane)).toEqual({ tone: "done", line: "2 dimenze · N=600" });
    expect(stageState("fieldwork", lane)).toEqual({ tone: "running", line: "Běh 1: běží" });
    expect(stageState("analysis", lane)).toEqual({ tone: "inert", line: "Zatím nic" });
    expect(stageState("brief", lane)).toEqual({ tone: "inert", line: "" });
  });
});
