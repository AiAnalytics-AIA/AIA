// What reads each questionnaire item downstream (artifact-questionnaire QST8).
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { questionnaireReaders, readBy } from "./readers";

const SET = { id: "sec_drinks", type: "object_battery", title: "Nápoje", object_family: "nápoje", objects: ["Káva", "Čaj", "Kakao", "Voda"] };

const project = (sections: unknown[]): ResearchProject => ({ sections }) as unknown as ResearchProject;

describe("what reads each questionnaire item", () => {
  it("lists Sociomapa for a tracked set", () => {
    const [set] = questionnaireReaders(project([SET]));
    expect(set).toMatchObject({ kind: "set", id: "sec_drinks", label: "Sada 1", text: "Nápoje", held: null });
    expect(set.readers).toEqual(["fieldwork", "results", "sociomap", "analysis", "report"]);
  });

  it("keeps a set outside 3-40 distinct objects from every stage, as the compiler does", () => {
    // battery_size: the compiler's hard range, TRACKED_SET_LIMITS[0]; 4-15 is a readiness warning.
    const sized = (objects: string[]) => questionnaireReaders(project([{ ...SET, objects }]))[0];
    expect(sized(["Káva", "Káva", "Čaj"])).toMatchObject({ held: "set_size", readers: [] });
    expect(sized(["Káva", "Káva", "Čaj", "Kakao"]).held).toBeNull();
    expect(sized(Array.from({ length: 40 }, (_, i) => `O${i}`)).held).toBeNull();
    expect(sized(Array.from({ length: 41 }, (_, i) => `O${i}`))).toMatchObject({ held: "set_size", readers: [] });
    // The compiler checks the limits in force: a stored maximum of 30 holds a set of 31.
    const stored = { min: 3, max: 30, recommended_min: 5, recommended_max: 12 };
    expect(questionnaireReaders(project([{ ...SET, objects: Array.from({ length: 31 }, (_, i) => `O${i}`) }]), stored)[0].held).toBe("set_size");
  });

  it("holds a set with familiarity required, which the run refuses, and keeps it from the Sociomap", () => {
    const [set] = questionnaireReaders(project([{ ...SET, familiarity_required: true }]));
    expect(set).toMatchObject({ held: "familiarity", readers: [] });
    const q = { id: "q_mood", text: "Jak se dnes cítíte?", typ: "skala", sociomap_rating: true };
    const items = questionnaireReaders(project([{ type: "questions", questions: [q] }, { ...SET, familiarity_required: true }]));
    expect(items[0].readers).not.toContain("sociomap");
    for (const off of [false, 0, "", [], {}, null]) expect(questionnaireReaders(project([{ ...SET, familiarity_required: off }]))[0].held).toBeNull();
  });

  it("names a set's declared context objects", () => {
    const [set] = questionnaireReaders(project([{ ...SET, context_objects: ["Voda", " "] }]));
    expect(set.context).toEqual(["Voda"]);
  });

  it("puts a declared rating question into the Sociomap only beside a set", () => {
    const q = { id: "q_mood", text: "Jak se dnes cítíte?", typ: "skala", sociomap_rating: true };
    const alone = questionnaireReaders(project([{ type: "questions", questions: [q] }]));
    expect(alone[0].rating).toBe(true);
    expect(alone[0].readers).not.toContain("sociomap");
    const beside = questionnaireReaders(project([{ type: "questions", questions: [q] }, SET]));
    expect(beside[0].readers).toContain("sociomap");
    expect(readBy(beside, "sociomap").map((i) => i.label)).toEqual(["Q1", "Sada 1"]);
  });

  it("never reads an undeclared scale question into the Sociomap", () => {
    const items = questionnaireReaders(project([{ type: "questions", questions: [{ text: "Kolik?", typ: "skala" }] }, SET]));
    expect(items[0].readers).toEqual(["fieldwork", "results", "analysis", "report"]);
  });

  it("shows an open question's answers in Results and keeps them out of the analysis", () => {
    const [q] = questionnaireReaders(project([{ type: "questions", questions: [{ text: "Proč?", typ: "otevrena" }] }]));
    expect(q).toMatchObject({ open: true, readers: ["fieldwork", "results"], id: null });
  });

  it("holds a question without wording or with a condition", () => {
    const items = questionnaireReaders(project([{ type: "questions", questions: [{ text: "  ", typ: "vyber" }, { text: "Komu?", typ: "vyber", filtr: "Q1 = Ano" }, { text: "Komu?", typ: "vyber", filtr: " " }] }]));
    expect(items.map((i) => i.held)).toEqual(["no_text", "condition", null]);
    expect(items[0].readers).toEqual([]);
    expect(items[1].readers).toEqual([]);
  });

  it("numbers questions across blocks and skips sections the study does not include", () => {
    const items = questionnaireReaders(project([
      { questions: [{ text: "A?", typ: "vyber" }] },
      { type: "intro", questions: [{ text: "Skryto?", typ: "vyber" }] },
      { type: "questions", questions: [{ text: "B?", typ: "vyber" }] },
      SET,
    ]));
    expect(items.map((i) => i.label)).toEqual(["Q1", "Q2", "Sada 1"]);
  });
});
