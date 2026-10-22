import { describe, expect, it } from "vitest";
import { defaultsMerge } from "./model";
import { applyNarrative, applyPlanSets, proposalAnalysis, validMeasurement } from "./plan-edit";

describe("working proposal edits", () => {
  const project = defaultsMerge({ research_plan: { objectives: ["Stored objective"], method_reason: "Keep method" }, sections: [{ title: "Existing instrument" }], ui_state: { kept: true } }, { empty_project: {} });
  it("reads a native stored plan and preserves unrelated content and analysis provenance on edits", () => {
    const state = { project, analysis: null };
    expect(proposalAnalysis(state)?.objectives).toEqual(["Stored objective"]);
    const edited = applyNarrative(state, { problem_summary: "Revised", research_questions: ["Why?"], objectives: ["New objective"], hypotheses: [] });
    expect(edited.project.sections).toEqual(project.sections);
    expect(edited.project.research_plan.method_reason).toBe("Keep method");
    expect(edited.project.ui_state).toMatchObject({ kept: true, plan_manual_changed: true });
    expect(project.research_plan.objectives).toEqual(["Stored objective"]);
    const result = applyPlanSets({ ...edited, analysis: { ...edited.analysis, _brief_signature: "unchanged-brief" } }, [{ title: "A", objects: ["1", "2", "3", "4"] }]);
    expect(result.analysis?._brief_signature).toBe("unchanged-brief");
    expect(result.analysis?.tracked_sets).toEqual(result.project.research_plan.tracked_sets);
  });
  it("refuses ambiguous or incomplete measurement edits", () => {
    const set = { title: "Concepts", purpose: "Compare concepts", objects: ["A", "B", "C", "D"], object_question: "Rate {object}", scale_labels: ["Never", "Always"] };
    expect(validMeasurement(set)).toBe(true);
    expect(validMeasurement({ ...set, objects: ["A", "a", "C", "D"] })).toBe(false);
    expect(validMeasurement({ ...set, objects: ["A", "B", "C"] })).toBe(false);
    // Above the recommended 15 is allowed (Q75 (a)); past the server's 40 is not.
    expect(validMeasurement({ ...set, objects: Array.from({ length: 16 }, (_, i) => String(i)) })).toBe(true);
    expect(validMeasurement({ ...set, objects: Array.from({ length: 41 }, (_, i) => String(i)) })).toBe(false);
    expect(validMeasurement({ ...set, scale_labels: ["", "Always"] })).toBe(false);
    expect(validMeasurement({ ...set, object_question: "Rate the concept" })).toBe(false);
  });
});
