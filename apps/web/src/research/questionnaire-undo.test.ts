// Undoing a delete on Dotazník (input-interactions chunk 3, audit A17, A18).
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { type Section, removeQuestion, removeSection, restoreOption, restoreQuestion, restoreSection } from "./questionnaire";

const SECTIONS: Section[] = [
  { id: "sec_a", type: "questions", title: "A", questions: [{ id: "Q1", text: "Jedna?" }, { id: "Q2", text: "Dvě?" }, { id: "Q3", text: "Tři?" }] },
  { id: "sec_b", type: "object_battery", title: "Sada", objects: ["a", "b", "c", "d"] },
];
const project = (xs: Section[] = SECTIONS): ResearchProject => ({ sections: structuredClone(xs) }) as unknown as ResearchProject;
const ids = (p: ResearchProject) => (p.sections as Section[]).map((s) => [s.id, ...(s.questions || []).map((q) => q.id)]);

describe("undoing a delete on Dotazník", () => {
  it("puts a question back where it was", () => {
    const removed = removeQuestion(project(), 0, 1);
    expect(ids(restoreQuestion(removed, 0, "sec_a", 1, SECTIONS[0].questions![1]))).toEqual(ids(project()));
  });

  it("finds the question's section by its id after the sections moved", () => {
    const moved = restoreSection(removeSection(removeQuestion(project(), 0, 0), 0), 1, { ...SECTIONS[0], questions: SECTIONS[0].questions!.slice(1) });
    const back = restoreQuestion(moved, 0, "sec_a", 0, SECTIONS[0].questions![0]);
    expect(ids(back)).toEqual([["sec_b"], ["sec_a", "Q1", "Q2", "Q3"]]);
  });

  it("does nothing when the section is gone or the question is already back", () => {
    const gone = removeSection(removeQuestion(project(), 0, 1), 0);
    expect(restoreQuestion(gone, 0, "sec_a", 1, SECTIONS[0].questions![1])).toBe(gone);
    const p = project();
    expect(restoreQuestion(p, 0, "sec_a", 1, SECTIONS[0].questions![1])).toBe(p);
  });

  it("puts a block or set back at its place, or last, and only once", () => {
    const removed = removeSection(project(), 0);
    const back = restoreSection(removed, 0, SECTIONS[0]);
    expect(ids(back)).toEqual(ids(project()));
    expect(restoreSection(back, 0, SECTIONS[0])).toBe(back);
    expect(ids(restoreSection(project([]), 5, SECTIONS[1]))).toEqual([["sec_b"]]);
  });

  it("restores a copy, so a later edit of the copy leaves the undo's item alone", () => {
    const q = { id: "Q9", text: "Nová?" };
    const back = restoreQuestion(project(), 0, "sec_a", 0, q);
    (back.sections as Section[])[0].questions![0].text = "Změněno";
    expect(q.text).toBe("Nová?");
  });
});

describe("undoing an option's removal", () => {
  const withOptions = (typ?: string) => project([{ id: "sec_a", type: "questions", questions: [{ id: "Q1", text: "Jak?", ...(typ ? { typ } : {}), kategorie: ["Týdně", "Měsíčně"] }] }]);
  const options = (p: ResearchProject) => (p.sections as Section[])[0].questions![0].kategorie;

  it("puts the one option back in its place, keeping what was edited since", () => {
    const edited = withOptions("vyber");
    (edited.sections as Section[])[0].questions![0].kategorie = ["Každý týden", "Měsíčně"];
    expect(options(restoreOption(edited, 0, "sec_a", 0, "Q1", 0, "Denně"))).toEqual(["Denně", "Každý týden", "Měsíčně"]);
  });

  it("does nothing once the question is gone, another type, or the option back already", () => {
    const p = withOptions("skala");
    expect(restoreOption(p, 0, "sec_a", 0, "Q1", 0, "Denně")).toBe(p);
    const q = withOptions(undefined);
    expect(options(restoreOption(q, 0, "sec_a", 0, "Q1", 9, "Denně"))).toEqual(["Týdně", "Měsíčně", "Denně"]);
    expect(restoreOption(q, 0, "sec_a", 0, "Q9", 0, "Denně")).toBe(q);
    expect(restoreOption(q, 0, "sec_a", 0, "Q1", 0, "Týdně")).toBe(q);
  });
});
