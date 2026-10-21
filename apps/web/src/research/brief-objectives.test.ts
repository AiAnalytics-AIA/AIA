import { describe, expect, it } from "vitest";
import { addObjective, objectivesEditable, objectivesOf, removeObjective, restoreObjective, setObjective, withObjectives } from "./brief-objectives";
import { listIds, withItemIds } from "./item-ids";
import { addSet } from "./plan";
import { proposalAnalysis } from "./plan-edit";
import type { ResearchProject } from "./model";
import type { Analysis } from "./store";

const design = (plan: Record<string, unknown>, analysis: Analysis | null = null) => ({
  project: { title: "S", goal: "G", research_plan: plan, ui_state: {} } as unknown as ResearchProject,
  analysis,
});

describe("Cíle on the Brief", () => {
  it("has none until objectives are stated: never the goal in their place", () => {
    expect(objectivesOf(design({}))).toEqual([]);
    expect(objectivesOf(design({ objectives: [] }))).toEqual([]);
  });

  it("reads the analysis when the stage has one, else the plan, each with item_ids' id", () => {
    const d = design({ objectives: ["Z plánu"] }, { objectives: ["Změřit zájem", "Porovnat značky"] });
    const read = objectivesOf(d);
    expect(read.map((o) => o.text)).toEqual(["Změřit zájem", "Porovnat značky"]);
    const [, analysis] = withItemIds(d.project as never, d.analysis);
    expect(read.map((o) => o.id)).toEqual(listIds(analysis, "objectives", "objective_ids"));
    expect(read[0]!.id).toMatch(/^obj_/);
    expect(objectivesOf(design({ objectives: ["Z plánu"] })).map((o) => o.text)).toEqual(["Z plánu"]);
  });

  it("keeps a stored id", () => {
    const d = design({ objectives: ["A"], objective_ids: [{ id: "obj_kept", bound: "x" }] });
    expect(objectivesOf(d)).toEqual([{ id: "obj_kept", text: "A" }]);
  });

  it("writes the plan and the analysis together, and marks the plan changed by hand", () => {
    const d = withObjectives(design({ objectives: ["A"], research_questions: ["Q"] }, { objectives: ["A"] }), ["B"]);
    expect(d.project.research_plan.objectives).toEqual(["B"]);
    expect(d.project.research_plan.research_questions).toEqual(["Q"]);
    expect(d.analysis?.objectives).toEqual(["B"]);
    expect(d.project.ui_state.plan_manual_changed).toBe(true);
    // Where the stage had none, the analysis Návrh already reads (the plan) is stored with them...
    const made = withObjectives(design({ research_questions: ["Q"] }), ["B"]);
    expect(made.analysis).toEqual(proposalAnalysis({ project: made.project, analysis: null } as never));
    expect(made.analysis?.objectives).toEqual(["B"]);
    // ...and none when the plan then states nothing.
    expect(withObjectives(design({}), []).analysis).toBeNull();
  });

  it("keeps objectives typed before any analysis when Návrh then adds a set (stand-in review, #609)", () => {
    const typed = addObjective(design({}), "Najít bariéry");
    const after = addSet({ project: typed.project, analysis: typed.analysis } as never, "Značky", "A, B, C, D");
    expect(after?.objectives).toEqual(["Najít bariéry"]);
    expect(objectivesOf({ project: typed.project, analysis: after }).map((o) => o.text)).toEqual(["Najít bariéry"]);
    // Before the fix the set's new analysis put the goal in their place.
    expect(after?.objectives).not.toContain("G");
  });

  it("rewords, adds, removes and puts back in place", () => {
    let d = design({ objectives: ["A", "B", "C"] });
    d = setObjective(d, 1, "B2");
    d = addObjective(d, "D");
    expect(d.project.research_plan.objectives).toEqual(["A", "B2", "C", "D"]);
    const { design: less, removed } = removeObjective(d, 1);
    expect(removed).toBe("B2");
    expect(less.project.research_plan.objectives).toEqual(["A", "C", "D"]);
    expect(restoreObjective(less, 1, "B2").project.research_plan.objectives).toEqual(["A", "B2", "C", "D"]);
    expect(restoreObjective(design({ objectives: [] }), 5, "X").project.research_plan.objectives).toEqual(["X"]);
    expect(removeObjective(d, 9)).toEqual({ design: d, removed: null });
  });

  it("changes nothing in a list it cannot read, never dropping an entry", () => {
    const d = design({ objectives: ["A", 3] });
    expect(objectivesEditable(d)).toBe(false);
    expect(objectivesOf(d)).toEqual([]);
    expect(addObjective(d, "B")).toBe(d);
    expect(setObjective(d, 0, "B")).toBe(d);
    expect(removeObjective(d, 0).removed).toBeNull();
    expect(objectivesEditable(design({}))).toBe(true);
  });
});
