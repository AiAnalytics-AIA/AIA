// Dotazník's inline adds (input-interactions chunk 3, audit A5, A8, A21).
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { type IdSource, type Section, addNamedSection, addNamedTrackedSet, addQuestionTo, addTrackedSet } from "./questionnaire";

const ids: IdSource = { now: () => 1, random: () => 0.5 };
const project = (sections: Section[] = []): ResearchProject => ({ sections }) as unknown as ResearchProject;
const xs = (p: ResearchProject) => p.sections as Section[];

describe("Dotazník's inline adds", () => {
  it("names a new block as typed, and refuses an empty name", () => {
    const made = addNamedSection(project(), "  Úvod  ", ids)!;
    expect(xs(made.project)).toEqual([{ id: made.sectionId, type: "questions", title: "Úvod", purpose: "", questions: [] }]);
    expect(addNamedSection(project(), "   ", ids)).toBeNull();
  });

  it("adds a question with its wording into the block's own list, a single choice of Ano / Ne", () => {
    const p = project([{ id: "sec_a", type: "questions", questions: [{ id: "Q1", text: "A?" }] }, { id: "sec_b", type: "object_battery", objects: [] }]);
    const made = addQuestionTo(p, 0, " Jak často? ", ids)!;
    expect(xs(made.project)[0].questions!.at(-1)).toEqual({ id: made.questionId, text: "Jak často?", typ: "vyber", kategorie: ["Ano", "Ne"], povolit_nevim: false });
    expect(addQuestionTo(p, 1, "Do sady?", ids)).toBeNull();
    expect(addQuestionTo(p, 0, " ", ids)).toBeNull();
    expect(xs(p)[0].questions).toHaveLength(1);
  });

  it("makes the same tracked set as the classic add, with its objects still to be added", () => {
    const named = addNamedTrackedSet(project(), " média ", ids)!;
    const classic = addTrackedSet(project(), "média", "TV, Rádio, Web, Tisk", ids) as { project: ResearchProject };
    expect(xs(named.project)[0]).toEqual({ ...xs(classic.project)[0], objects: [] });
    expect(addNamedTrackedSet(project(), "", ids)).toBeNull();
  });
});
