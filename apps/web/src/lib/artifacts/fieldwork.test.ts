// Sběr dat's contract as data (artifact-fieldwork FLD1).
import { describe, expect, it } from "vitest";

import { FIELDWORK, RECEIPT_TARGET, readFieldworkTarget, stepTarget } from "./fieldwork";

describe("Sběr dat's row", () => {
  it("is a frozen run the Lead may open, focus and inspect, naming its steps and receipt", () => {
    expect(FIELDWORK.artifact).toBe("run");
    expect(FIELDWORK.edits).toBe(false);
    expect(FIELDWORK.view_ops).toEqual(["open_stage", "focus", "inspect"]);
    expect(FIELDWORK.targets).toEqual(["step", "receipt"]);
    expect(FIELDWORK.starts).toEqual(["research_run"]);
  });
});

describe("stepTarget / RECEIPT_TARGET / readFieldworkTarget", () => {
  it("names a step by its node key and the receipt, and reads both back", () => {
    for (const key of ["run", "analysis_executive", "investigate/track-1"]) {
      expect(readFieldworkTarget(stepTarget(key)!)).toEqual({ kind: "step", nodeKey: key });
    }
    expect(RECEIPT_TARGET).toBe("receipt:respondents");
    expect(readFieldworkTarget(RECEIPT_TARGET)).toEqual({ kind: "receipt" });
  });

  it("leaves a key outside the grammar unnamed instead of throwing", () => {
    expect(stepTarget("a key with spaces")).toBeNull();
    expect(stepTarget("x".repeat(81))).toBeNull();
  });

  it("reads nothing another stage names, nor a receipt it does not have", () => {
    for (const value of ["measure:q1", "receipt:other", "module:executive", "nonsense"]) {
      expect(readFieldworkTarget(value)).toBeNull();
    }
  });
});
