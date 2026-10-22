// Návrh's narrative as items (artifact-design DSN3).
import { describe, expect, it } from "vitest";

import type { PlanState } from "./plan";
import { objectivesOf } from "./brief-objectives";
import { boundOf } from "./item-ids";
import { addItem, addProblem, itemProblem, itemTargets, narrativeOf, removeItem, setItem, setSummary } from "./plan-narrative";

const plan = { problem_summary: "Problém", research_questions: ["Kdo?", "Proč?"], objectives: ["Cíl A"], hypotheses: ["H1"], status: "approved" };
const state = (over: Record<string, unknown> = {}): PlanState =>
  ({ project: { goal: "Cíl studie", research_plan: { ...plan, ...over }, ui_state: {} }, analysis: null }) as unknown as PlanState;
const ok = (r: ReturnType<typeof setItem>) => {
  if ("refused" in r) throw new Error(r.refused);
  return r.state;
};

describe("narrativeOf", () => {
  it("reads the stored plan, the goal standing in for an empty summary", () => {
    expect(narrativeOf(state())).toEqual({ problem_summary: "Problém", research_questions: ["Kdo?", "Proč?"], objectives: ["Cíl A"], hypotheses: ["H1"] });
    expect(narrativeOf(state({ problem_summary: "" })).problem_summary).toBe("Cíl studie");
  });
});

describe("editing one item", () => {
  it("rewords an item in its place, in the project and the analysis together, keeping the plan's other fields", () => {
    const next = ok(setItem(state(), "research_questions", 1, "  Proč ne?  "));
    expect(next.project.research_plan).toMatchObject({ research_questions: ["Kdo?", "Proč ne?"], objectives: ["Cíl A"], status: "approved" });
    expect(next.analysis).toMatchObject({ research_questions: ["Kdo?", "Proč ne?"] });
    expect(next.project.ui_state).toMatchObject({ plan_manual_changed: true });
  });

  it("refuses an empty item, a repeat of another (case and spacing aside) and a place that is gone", () => {
    expect(setItem(state(), "research_questions", 0, "  ")).toEqual({ refused: "Prázdnou položku nelze uložit." });
    expect(setItem(state(), "research_questions", 0, "PROČ? ")).toEqual({ refused: "Tato položka už v seznamu je." });
    expect(setItem(state(), "hypotheses", 3, "x")).toHaveProperty("refused");
    // The item itself, reworded only in case, is not a repeat.
    expect(itemProblem(narrativeOf(state()), "research_questions", "kdo?", 0)).toBeNull();
  });

  it("rewords the summary and refuses an empty one", () => {
    expect(ok(setSummary(state(), "Nový problém")).project.research_plan).toMatchObject({ problem_summary: "Nový problém" });
    expect(setSummary(state(), " ")).toEqual({ refused: "Doplňte shrnutí výzkumného problému." });
  });
});

describe("adding and removing", () => {
  it("adds at the end, or back at its place for an undone removal", () => {
    expect(ok(addItem(state(), "hypotheses", "H2")).project.research_plan).toMatchObject({ hypotheses: ["H1", "H2"] });
    const removed = ok(removeItem(state(), "research_questions", 0));
    expect(removed.project.research_plan).toMatchObject({ research_questions: ["Proč?"] });
    expect(ok(addItem(removed, "research_questions", "Kdo?", 0)).project.research_plan).toMatchObject({ research_questions: ["Kdo?", "Proč?"] });
  });

  it("keeps the last objective and refuses a repeat", () => {
    expect(removeItem(state(), "objectives", 0)).toEqual({ refused: "Doplňte alespoň jeden cíl výzkumu." });
    expect(addItem(state(), "objectives", "cíl a")).toEqual({ refused: "Tato položka už v seznamu je." });
  });

  it("stops research questions at the eight the analysis reads", () => {
    const eight = state({ research_questions: Array.from({ length: 8 }, (_, i) => `Otázka ${i + 1}?`) });
    expect(addProblem(narrativeOf(eight), "research_questions")).toBe("Analýza čte nejvýše 8 výzkumných otázek.");
    expect(addItem(eight, "research_questions", "Devátá?")).toHaveProperty("refused");
    expect(addProblem(narrativeOf(eight), "hypotheses")).toBeNull();
  });
});

describe("each item's Lead target", () => {
  it("names an objective by the Brief's own id, so both screens point at one target", () => {
    const s = state();
    const brief = objectivesOf({ project: s.project, analysis: s.analysis }).map((o) => `objective:${o.id}`);
    expect(itemTargets(s).objectives).toEqual(brief);
  });

  it("names research questions and hypotheses by their stable ids, which follow the item when the list is reordered", () => {
    const before = itemTargets(state()).research_questions;
    expect(before.every((t) => t !== null && /^rq:/.test(t))).toBe(true);
    expect(new Set(before).size).toBe(2);
    expect(itemTargets(state()).hypotheses[0]).toMatch(/^hypothesis:/);
    // The same two questions in the other order: each keeps its own target, never its place's.
    const swapped = itemTargets(state({ research_questions: ["Proč?", "Kdo?"] })).research_questions;
    expect(swapped).toEqual([before[1], before[0]]);
  });

  it("uses a stored id over the wording's, so a question reworded under the stable ids keeps its target", () => {
    const stored = state({ research_questions: ["Kdo nakupuje?", "Proč?"], research_question_ids: [{ id: "rq_kept", bound: boundOf("Kdo?") }, { id: "rq_why", bound: boundOf("Proč?") }] });
    expect(itemTargets(stored).research_questions).toEqual(["rq:rq_kept", "rq:rq_why"]);
  });

  it("names nothing for an empty list", () => {
    expect(itemTargets(state({ hypotheses: [] })).hypotheses).toEqual([]);
  });
});
