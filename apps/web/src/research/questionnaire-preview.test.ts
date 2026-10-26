// The respondent preview numbers its items as Dotazník's editor does (artifact-questionnaire QF-14):
// questions and sets each on their own, a set being every section that is not questions.
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { previewLeftOut, respondentPreview } from "./questionnaire";

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

// QST11: the preview draws a scale at its stored range and says what it leaves out; 18.6.6 drew every
// scale 1-10 and cut lists without a word.
describe("the respondent preview's range and cuts", () => {
  const scale = (skala: unknown) => ({ id: "Q1", text: "Jak moc?", typ: "skala", skala });
  it("a 1–7 scale previews at 1–7; a range the editor would not read previews at none", () => {
    const at = (skala: unknown) => {
      const [it] = respondentPreview({ sections: [{ type: "questions", questions: [scale(skala)] }] } as unknown as ResearchProject);
      return it.kind === "question" ? it.range : "not a question";
    };
    expect(at([1, 7])).toEqual([1, 7]);
    expect(at(undefined)).toEqual([1, 10]);
    expect(at([7, 1])).toBeNull();
    expect(at([1.5, 7])).toBeNull();
  });

  it("a cut list says how many it left out: options past eight, set objects, items past fourteen", () => {
    const options = Array.from({ length: 11 }, (_, i) => `M${i}`);
    const questions = Array.from({ length: 15 }, (_, i) => ({ id: `Q${i}`, text: `Otázka ${i}?`, typ: "vyber", kategorie: options, ...(i === 1 ? { filtr: { question_id: "Q0", options: ["M0"] } } : {}) }));
    const p = { sections: [{ type: "questions", questions }, { type: "object_battery", title: "Značky", objects: ["A", "B", "C", "D", "E"] }] } as unknown as ResearchProject;
    const items = respondentPreview(p);
    expect(items).toHaveLength(14);
    expect(items[0].kind === "question" && [items[0].moreOptions, items[0].conditional]).toEqual([3, false]);
    expect(items[1].kind === "question" && items[1].conditional).toBe(true);
    // Fifteen questions and one set: two left out of the fourteen shown.
    expect(previewLeftOut(p, items.length)).toBe(2);
    const [set] = respondentPreview({ sections: [p.sections[1]] } as unknown as ResearchProject);
    expect(set.kind === "battery" && set.objects).toBe(5);
  });
});
