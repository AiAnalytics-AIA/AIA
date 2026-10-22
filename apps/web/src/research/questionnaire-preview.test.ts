// The respondent preview numbers its items as Dotazník's editor does (artifact-questionnaire QF-14):
// questions and sets each on their own, a set being every section that is not questions.
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { respondentPreview } from "./questionnaire";

const set = (title: string) => ({ type: "object_battery", title, objects: ["A", "B", "C", "D"] });
const question = (id: string) => ({ id, text: `Otázka ${id}?`, typ: "otevrena" });

describe("the respondent preview's numbers", () => {
  it("count questions and sets each on their own, as the editor and its outline do", () => {
    const p = {
      sections: [{ title: "Bez typu", questions: [question("Q0")] }, set("První"), { type: "questions", questions: [question("Q1"), question("Q2")] }, set("Druhá")],
    } as unknown as ResearchProject;
    const items = respondentPreview(p);
    // The untyped section is drawn as a set by the editor (Sada 1), so the first set read is Sada 2.
    expect(items.map((it) => [it.kind, it.number])).toEqual([
      ["battery", 2],
      ["question", 1],
      ["question", 2],
      ["battery", 3],
    ]);
    // 18.6.6's running index is kept beside them, as the parity test reads it.
    expect(items.map((it) => it.index)).toEqual([1, 2, 3, 4]);
  });
});
