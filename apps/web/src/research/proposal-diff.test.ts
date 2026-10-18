import { describe, expect, it } from "vitest";

import { diffLists, proposalDiff, questionnaireReplacement } from "./proposal-diff";

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

describe("questionnaireReplacement (PC6)", () => {
  const own = { id: "s1", type: "questions", questions: [{ id: "q1", text: "Jak často pijete kávu?" }, { id: "q2", text: "Kde kávu kupujete?" }] };
  const battery = { id: "s2", type: "object_battery", objects: ["Káva", "Čaj"] };
  const library = { id: "lib", type: "questions", metadata: { instrument_id: "nps" }, questions: [{ id: "n1", text: "Doporučil byste nás?" }] };
  const intro = { id: "intro", type: "intro" };

  it("names the own questions and items that go, what is new and what is kept; library and other sections stay", () => {
    const proposed = { sections: [library, intro, { id: "ai_section_1", type: "questions", questions: [{ id: "ai_q_1_1", text: "jak často pijete  kávu?" }, { id: "ai_q_1_2", text: "Kolik šálků denně?" }] }] };
    const r = questionnaireReplacement({ sections: [own, battery, library, intro] }, proposed);
    expect(r).toEqual({ replaced: 2, preserved: 2, removed: ["Kde kávu kupujete?", "Káva", "Čaj"], added: ["Kolik šálků denně?"], kept: 1 });
  });

  it("says a questionnaire with no own blocks loses nothing", () => {
    const r = questionnaireReplacement({ sections: [library] }, { sections: [library, own] });
    expect(r).toEqual({ replaced: 0, preserved: 1, removed: [], added: ["Jak často pijete kávu?", "Kde kávu kupujete?"], kept: 0 });
  });
});
