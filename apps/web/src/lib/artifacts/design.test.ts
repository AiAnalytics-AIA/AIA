// Návrh's part of the Lead contract (artifact-design DSN1).
import { describe, expect, it } from "vitest";

import { ARTIFACTS, parseAiaId } from "@/lib/workbench-artifacts";
import { DESIGN_LABELS, PLAN_PARTS, type DesignKind, type PlanPart, designAllows, designLabel, designTarget, planTarget, sectionElement, sectionTargetOf } from "./design";

const KINDS = Object.keys(DESIGN_LABELS) as DesignKind[];

describe("Návrh's targets", () => {
  it("emits only kinds the design row lists, and every kind it lists", () => {
    expect([...KINDS].sort()).toEqual([...ARTIFACTS.design.targets].sort());
  });

  it("builds `<kind>:<id>` ids that read back as Návrh's", () => {
    for (const kind of KINDS.filter((k) => k !== "plan")) {
      const id = designTarget(kind, "abc-1");
      expect(id).toBe(`${kind}:abc-1`);
      expect(parseAiaId(id)).toEqual({ kind, id: "abc-1", stage: "design" });
    }
  });

  it("refuses a kind the row does not list, a section Návrh does not draw and an id outside the grammar", () => {
    expect(() => designTarget("question" as DesignKind, "q1")).toThrow(/not a Návrh target/);
    expect(() => designTarget("plan", "coverage")).toThrow(/not a section/);
    expect(() => designTarget("rq", "a b")).toThrow(/not an identifier/);
  });
});

describe("Návrh's section anchors", () => {
  it("open on the element PlanStep draws, and read back from it", () => {
    for (const part of Object.keys(PLAN_PARTS) as PlanPart[]) {
      const target = planTarget(part);
      expect(sectionElement(target)).toBe(PLAN_PARTS[part]);
      expect(sectionTargetOf(PLAN_PARTS[part])).toBe(target);
    }
  });

  it("open nothing for another stage's target, an unknown part or an unparsable value, never a guess", () => {
    expect(sectionElement("question:q1")).toBeNull();
    expect(sectionElement("plan:coverage")).toBeNull();
    expect(sectionElement("plan:toString")).toBeNull();
    expect(sectionElement("nonsense")).toBeNull();
    expect(sectionTargetOf("q-editor")).toBeNull();
  });
});

describe("Návrh in words", () => {
  it("names a section and an item; anything not Návrh's reads null", () => {
    expect(designLabel("plan:sets")).toBe("Návrh: sledované sady");
    expect(designLabel("rq:RQ-7")).toBe("Výzkumná otázka");
    expect(designLabel("plan:nowhere")).toBeNull();
    expect(designLabel("section:s1")).toBeNull();
  });
});

describe("Návrh's view operations", () => {
  it("allows the row's operations and refuses the rest", () => {
    expect(designAllows("open_stage")).toBe(true);
    expect(designAllows("focus")).toBe(true);
    expect(designAllows("show_diff")).toBe(true);
    // V2's "Celý řetěz" is inspect on an rq:<id> target (the coordinator's ruling), never its own name.
    expect(designAllows("inspect")).toBe(true);
    expect(designAllows("filter")).toBe(false);
    expect(designAllows("expand_chain")).toBe(false);
  });
});
