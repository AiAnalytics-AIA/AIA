import { describe, expect, it } from "vitest";
import { defaultsMerge } from "./model";
import { MAX_OBJECTS, SET_FULL } from "./plan";
import { applyNarrative, applyPlanSets, objectProblem, proposalAnalysis, setFieldProblem, withObject, withSetField } from "./plan-edit";

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
  it("refuses an empty field and a question without {object}, at the field", () => {
    expect(setFieldProblem("purpose", "  ")).toBe("Napište, co sada porovnává.");
    expect(setFieldProblem("scale_high", "")).toBe("Napište popisek pro 10.");
    expect(setFieldProblem("object_question", "Jak hodnotíte koncept?")).toBe("Otázka musí obsahovat {object}: tam se vloží název položky.");
    expect(setFieldProblem("object_question", "Jak hodnotíte {object}?")).toBeNull();
  });
  it("writes one field, keeping the rest of the set and the other end of the scale the person saw", () => {
    const set = { title: "Koncepty", purpose: "P", objects: ["A", "B", "C", "D"], extra: 1 };
    expect(withSetField(set, "purpose", "  Nový účel ")).toEqual({ ...set, purpose: "Nový účel" });
    expect(withSetField(set, "scale_high", "rozhodně")).toEqual({ ...set, scale_labels: ["vůbec", "rozhodně"] });
    expect(withSetField({ ...set, scale_labels: ["nikdy", "vždy"] }, "scale_low", "zřídka").scale_labels).toEqual(["zřídka", "vždy"]);
    // Stated ends stay as stored, as the preview shows them; a default fills only a set with none.
    expect(withSetField({ ...set, scale_labels: ["", "vždy"] }, "scale_high", "často").scale_labels).toEqual(["", "často"]);
  });
  it("refuses a repeated item (case aside) and one past the full set", () => {
    const set = { objects: ["Alfa", "Beta"] };
    expect(objectProblem(set, " ALFA ")).toBe("Tato položka už v sadě je.");
    expect(objectProblem(set, "Gama")).toBeNull();
    // The full set is addObject's own limit (MAX_OBJECTS, the server's hard maximum under Q75 (a)).
    const full = { objects: Array.from({ length: MAX_OBJECTS }, (_, i) => String(i)) };
    expect(objectProblem(full, "x")).toBe(SET_FULL);
    expect(objectProblem({ objects: full.objects.slice(1) }, "x")).toBeNull();
    // A rename is checked against the others only: its own wording, or a full set, is no refusal.
    expect(objectProblem(set, "alfa", 0)).toBeNull();
    expect(objectProblem(set, "alfa", 1)).toBe("Tato položka už v sadě je.");
    expect(objectProblem(full, "x", 3)).toBeNull();
  });
  it("rewords an item in its place, keeping the order", () => {
    expect(withObject({ objects: ["A", "B", "C"], extra: 1 }, 1, " Beta ")).toEqual({ objects: ["A", "Beta", "C"], extra: 1 });
  });
});
