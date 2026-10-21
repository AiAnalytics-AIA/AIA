// Analýza's contract as data (artifact-analysis ANL1).
import { describe, expect, it } from "vitest";

import { ANALYSIS, analysisTarget, inspectable, readAnalysisTarget } from "./analysis";

describe("Analýza's row", () => {
  it("is a frozen run the Lead may open, focus and inspect, naming modules, findings and claims", () => {
    expect(ANALYSIS.artifact).toBe("run");
    expect(ANALYSIS.edits).toBe(false);
    expect(ANALYSIS.view_ops).toEqual(["open_stage", "focus", "inspect"]);
    expect(ANALYSIS.targets).toEqual(["module", "finding", "claim"]);
    expect(ANALYSIS.starts).toContain("analysis_retry");
    expect(ANALYSIS.hands_off.map((h) => h.to)).toEqual(["report"]);
  });
});

describe("analysisTarget / readAnalysisTarget", () => {
  it("names each kind in the agreed grammar and reads it back", () => {
    const cases = [
      [{ kind: "module", module: "research_questions" }, "module:research_questions"],
      [{ kind: "finding", module: "executive", index: 2 }, "finding:executive:2"],
      [{ kind: "claim", module: "objects", claimId: "C1" }, "claim:objects:C1"],
    ] as const;
    for (const [target, id] of cases) {
      expect(analysisTarget(target)).toBe(id);
      expect(readAnalysisTarget(id)).toEqual(target);
    }
  });

  it("leaves a claim id outside the grammar unnamed, never rewritten", () => {
    expect(analysisTarget({ kind: "claim", module: "objects", claimId: "C 1" })).toBeNull();
  });

  it("reads nothing another stage names, nor a module, index or shape this run cannot have", () => {
    for (const value of ["measure:q1", "module:unknown", "finding:executive", "finding:executive:01", "finding:executive:x", "module:executive:1", "claim:executive", "rq:0", "nonsense"]) {
      expect(readAnalysisTarget(value)).toBeNull();
    }
  });

  it("opens a finding or a claim in the inspector, never a module", () => {
    expect(inspectable({ kind: "finding", module: "executive", index: 0 })).toBe(true);
    expect(inspectable({ kind: "claim", module: "executive", claimId: "C1" })).toBe(true);
    expect(inspectable({ kind: "module", module: "executive" })).toBe(false);
  });
});
