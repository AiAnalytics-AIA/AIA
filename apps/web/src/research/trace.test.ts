// Which research question each questionnaire item measures (run-recovery-and-truth 3b).
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import type { Section } from "./questionnaire";
import { comparisonOf, danglingLinks, linksOf, researchQuestionsOf, setComparison, toggleQuestionLink, toggleSectionLink } from "./trace";

const RQ1 = "Jak často lidé pijí kávu?";
const RQ2 = "Jak lidé vnímají ranní nápoje?";

const project = (extra: Partial<ResearchProject> = {}): ResearchProject =>
  ({
    research_plan: { research_questions: [RQ1, RQ2] },
    sections: [
      { type: "questions", questions: [{ id: "q1", text: "Jak často pijete kávu?", typ: "skala" }] },
      { type: "object_battery", title: "Nápoje", objects: ["Káva", "Čaj", "Kakao"] },
    ],
    ...extra,
  }) as unknown as ResearchProject;

const sections = (p: ResearchProject) => p.sections as Section[];

describe("research questions an item measures", () => {
  it("reads the research questions as the analysis reads them", () => {
    expect(researchQuestionsOf(project())).toEqual([RQ1, RQ2]);
    expect(researchQuestionsOf(project({ research_plan: { research_questions: [" A? ", "A?", 1, ""], objectives: ["O"] } as never }))).toEqual(["A?"]);
    expect(researchQuestionsOf(project({ research_plan: { objectives: ["O"] } as never, goal: "G" }))).toEqual(["O"]);
    expect(researchQuestionsOf(project({ research_plan: {} as never, goal: " G " }))).toEqual(["G"]);
    expect(researchQuestionsOf(project({ research_plan: { research_questions: Array.from({ length: 12 }, (_, i) => `Q${i}?`) } as never }))).toHaveLength(8);
  });

  it("links a question and unlinks it, leaving no empty declaration behind", () => {
    const on = toggleQuestionLink(project(), 0, 0, RQ1);
    expect(linksOf(sections(on)[0].questions![0])).toEqual([RQ1]);
    const off = toggleQuestionLink(on, 0, 0, `  ${RQ1}`); // compared as the server compares
    expect(sections(off)[0].questions![0]).not.toHaveProperty("research_questions");
    expect(sections(project())[0].questions![0]).not.toHaveProperty("research_questions"); // the input is untouched
  });

  it("links a tracked set as a whole", () => {
    const p = toggleSectionLink(toggleSectionLink(project(), 1, RQ2), 1, RQ1);
    expect(linksOf(sections(p)[1])).toEqual([RQ2, RQ1]);
  });

  it("names a link whose research question the plan no longer states, and can drop it", () => {
    const linked = toggleQuestionLink(project(), 0, 0, "Stará otázka?");
    const q = sections(linked)[0].questions![0];
    expect(danglingLinks(q, researchQuestionsOf(linked))).toEqual(["Stará otázka?"]);
    const dropped = toggleQuestionLink(linked, 0, 0, "Stará otázka?");
    expect(danglingLinks(sections(dropped)[0].questions![0], [RQ1])).toEqual([]);
  });
});

describe("how a research question is answered (run-recovery-and-truth 3c)", () => {
  it("declares a comparison by the question's text, replaces it and clears it", () => {
    const ranked = setComparison(project(), RQ2, "rank_objects");
    expect(comparisonOf(ranked, RQ2)).toBe("rank_objects");
    expect(comparisonOf(ranked, `  ${RQ2} `)).toBe("rank_objects");
    expect(comparisonOf(ranked, RQ1)).toBeNull();
    const ab = setComparison(ranked, ` ${RQ2}`, "ab_test");
    expect(Object.keys(ab.research_plan.research_question_comparisons as object)).toEqual([` ${RQ2}`]);
    const cleared = setComparison(ab, RQ2, null);
    expect(cleared.research_plan).not.toHaveProperty("research_question_comparisons");
    expect(cleared.research_plan.research_questions).toEqual([RQ1, RQ2]);
  });

  it("reads a kind AIA does not know as none declared here; the server names it", () => {
    const odd = project({ research_plan: { research_questions: [RQ1], research_question_comparisons: { [RQ1]: "guess" } } as never });
    expect(comparisonOf(odd, RQ1)).toBeNull();
  });
});
