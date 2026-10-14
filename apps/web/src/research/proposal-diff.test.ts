import { describe, expect, it } from "vitest";

import { diffLists, proposalDiff } from "./proposal-diff";

describe("diffLists", () => {
  it("names what was added and removed, ignoring case and spacing", () => {
    expect(diffLists(["Důvěra v banku", "Cena"], ["důvěra  v banku", "Modernost"])).toEqual({ added: ["Modernost"], removed: ["Cena"], kept: 1 });
  });
});

describe("proposalDiff", () => {
  const current = {
    problem_summary: "Jak nás vnímají.",
    research_questions: ["Jak nás vnímají?"],
    objectives: ["Profil značky"],
    tracked_sets: [{ title: "Banky", objects: ["Horizont", "ČSOB", "Fio", "Air Bank"] }],
  };

  it("lists each change against the plan the person has now", () => {
    const d = proposalDiff(current, {
      problem_summary: "Jak nás vnímají lidé 25–55.",
      research_questions: ["Jak nás vnímají?", "Které sdělení zabírá?"],
      tracked_sets: [{ title: "Banky", objects: ["Horizont", "ČSOB", "Fio", "Air Bank", "Revolut"] }, { title: "Sdělení", objects: ["A", "B", "C", "D"] }],
    });
    expect(d.summary).toEqual({ before: "Jak nás vnímají.", after: "Jak nás vnímají lidé 25–55." });
    expect(d.lists).toEqual([{ key: "research_questions", label: "Výzkumné otázky", added: ["Které sdělení zabírá?"], removed: [], kept: 1 }]);
    expect(d.sets).toEqual([
      { title: "Banky", status: "changed", added: ["Revolut"], removed: [], size: 5 },
      { title: "Sdělení", status: "new", added: ["A", "B", "C", "D"], removed: [], size: 4 },
    ]);
    expect(d.changes).toBe(4);
  });

  it("does not count a field the proposal does not carry, and names a set it drops", () => {
    const d = proposalDiff(current, { tracked_sets: [] });
    expect(d.lists).toEqual([]);
    expect(d.summary).toBeNull();
    expect(d.sets).toEqual([{ title: "Banky", status: "removed", added: [], removed: ["Horizont", "ČSOB", "Fio", "Air Bank"], size: 0 }]);
  });

  it("treats everything as new when there is no plan yet", () => {
    expect(proposalDiff(null, { objectives: ["A"] }).lists[0]).toMatchObject({ added: ["A"], kept: 0 });
  });
});
