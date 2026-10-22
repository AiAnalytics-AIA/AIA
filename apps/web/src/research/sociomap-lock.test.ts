import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { declaresSociomapInputs, restoreLocked } from "./sociomap-lock";

type Q = { [k: string]: unknown; id: string; text?: string; skala?: number[]; sociomap_rating?: boolean };
type Sec = { [k: string]: unknown; id: string; objects?: string[]; context_objects?: string[]; questions: Q[] };
type Doc = { title: string; sections: Sec[] };
const doc = (p: ResearchProject) => p as unknown as Doc;

const battery = { id: "set_a", type: "object_battery", objects: ["A", "B"], context_objects: ["B"] };
const rating = { id: "q1", text: "Jak moc?", typ: "skala", skala: [1, 5], sociomap_rating: true };
const plain = { id: "q2", text: "Kde?", typ: "vyber", kategorie: ["X", "Y"] };
const saved = { title: "Fiktivní", sections: [battery, { id: "s1", type: "questions", questions: [rating, plain] }] } as unknown as ResearchProject;
const edit = (f: (p: Doc) => void): ResearchProject => {
  const p = structuredClone(saved);
  f(doc(p));
  return p;
};

describe("restoreLocked", () => {
  it("puts a locked set and rating question back as saved and keeps every other change", () => {
    const edited = edit((p) => {
      p.title = "Nový";
      p.sections[0].objects = ["A", "B", "C"];
      p.sections[1].questions[0].skala = [1, 7];
      p.sections[1].questions[1].text = "Kde jinde?";
    });
    const restored = doc(restoreLocked(saved, edited));
    expect(restored.title).toBe("Nový");
    expect(restored.sections[0]).toEqual(battery);
    expect(restored.sections[1].questions).toEqual([rating, { ...plain, text: "Kde jinde?" }]);
  });

  it("puts a removed locked item back where it stood", () => {
    const edited = edit((p) => {
      p.sections.splice(0, 1);
      p.sections[0].questions.splice(0, 1);
    });
    const restored = doc(restoreLocked(saved, edited));
    expect(restored.sections.map((s) => s.id)).toEqual(["set_a", "s1"]);
    expect(restored.sections[1].questions.map((q) => q.id)).toEqual(["q1", "q2"]);
  });

  it("returns the same copy when nothing locked changed, or nothing is declared", () => {
    const edited = edit((p) => { p.sections[1].questions[1].text = "Kde jinde?"; });
    expect(restoreLocked(saved, edited)).toBe(edited);
    const undeclared = edit((p) => { delete p.sections[0].context_objects; delete p.sections[1].questions[0].sociomap_rating; });
    expect(declaresSociomapInputs(undeclared)).toBe(false);
    const changed = edit((p) => { p.sections[0].objects = ["Z"]; });
    expect(restoreLocked(undeclared, changed)).toBe(changed);
  });
});
