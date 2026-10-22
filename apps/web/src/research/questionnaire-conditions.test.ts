// The web's half of a question's display condition (working-copy-edit-ops WCE13): the rule cases
// are the shared edit case file's (edit-ops.cases.test.ts); this holds what that file cannot carry.
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { conditionOf, conditionRefusal } from "./questionnaire";

const project = (sections: unknown[]) => ({ sections }) as unknown as ResearchProject;
const Q1 = { id: "Q1", text: "Pijete kávu?", typ: "vyber", kategorie: ["Ano", "Ne"] };
const Q2 = { id: "Q2", text: "Proč?", typ: "otevrena" };

describe("a question's display condition", () => {
  it("reads past what is no section or no question, never throwing on it", () => {
    const malformed = project([null, "x", { type: "questions", questions: [null, 7, Q1, Q2] }, { type: "questions", questions: "Q3" }]);
    expect(conditionRefusal(malformed, "Q2", { question_id: "Q1", options: ["Ano"] })).toBeNull();
    // A category list that is no list names no answer.
    const odd = project([{ type: "questions", questions: [{ ...Q1, kategorie: "Ano" }, Q2] }]);
    expect(conditionRefusal(odd, "Q2", { question_id: "Q1", options: ["Ano"] })).toBe("condition_unknown_option");
  });

  it("collapses whitespace as the server does, \\x85 included and \\ufeff not", () => {
    const spaced = project([{ type: "questions", questions: [{ ...Q1, kategorie: ["Ano\x85", "Ne"] }, Q2] }]);
    expect(conditionRefusal(spaced, "Q2", { question_id: "Q1", options: ["Ano"] })).toBeNull();
    const bom = project([{ type: "questions", questions: [{ ...Q1, kategorie: ["Ano﻿", "Ne"] }, Q2] }]);
    expect(conditionRefusal(bom, "Q2", { question_id: "Q1", options: ["Ano"] })).toBe("condition_unknown_option");
  });

  it("offers only the earlier choice questions a condition may stand on, numbered as Dotazník numbers them", () => {
    const Q3 = { id: "Q3", text: "Kolik?", typ: "multi", kategorie: ["1", "2"], povolit_nevim: true };
    const twin = { id: "Q4", text: "A?", typ: "vyber", kategorie: ["A", "B"] };
    const untyped = { id: "Q6", text: "Bez typu oddílu", typ: "vyber", kategorie: ["X", "Y"] };
    const Q5 = { id: "Q5", text: "Proč?", typ: "otevrena" };
    const p = project([{ questions: [untyped] }, { type: "questions", questions: [Q1, Q2, twin] }, { type: "object_battery" }, { type: "questions", questions: [Q3, twin, Q5] }]);
    // Q2 is open, Q4 is stored twice (a condition on it is refused), Q6 sits in a section Dotazník
    // does not number as questions; Q5 is the question itself.
    expect(conditionOf(p, 3, 2).sources).toEqual([
      { id: "Q1", number: 1, text: "Pijete kávu?", options: ["Ano", "Ne"] },
      { id: "Q3", number: 4, text: "Kolik?", options: ["1", "2", "Nevím / neodpovím"] },
    ]);
    for (const s of conditionOf(p, 3, 2).sources) expect(conditionRefusal(p, "Q5", { question_id: s.id, options: [s.options[0]!] })).toBeNull();
    expect(conditionOf(p, 1, 0).sources).toEqual([]);
    // A question whose own id is not its alone is offered nothing: route_set names it by id.
    expect(conditionOf(p, 3, 1).sources).toEqual([]);
  });

  it("reads a stored condition by the question's place: set, refused by name, or shown as stored", () => {
    const at = (filtr: unknown, q2: Record<string, unknown> = Q2) => conditionOf(project([{ type: "questions", questions: [Q1, { ...q2, filtr }] }]), 0, 1).state;
    expect(at(undefined)).toEqual({ kind: "none" });
    expect(at("  ")).toEqual({ kind: "none" });
    expect(at({ question_id: " Q1", options: ["Ano ", "Ano"] })).toEqual({ kind: "set", source: { id: "Q1", number: 1, text: "Pijete kávu?", options: ["Ano", "Ne"] }, options: ["Ano"] });
    expect(at({ question_id: "Q1", options: ["Možná"] })).toEqual({ kind: "refused", reason: "condition_unknown_option" });
    // A question without an id cannot be named by route_set, so its condition is refused as such.
    expect(at({ question_id: "Q1", options: ["Ano"] }, { text: "Bez id", typ: "otevrena" })).toEqual({ kind: "refused", reason: "unknown_question" });
    expect(at("Q1 == 'Ano'")).toEqual({ kind: "unread", stored: "Q1 == 'Ano'" });
    expect(at({ question_id: "Q1", options: ["Ano"], negate: true })).toEqual({ kind: "unread", stored: '{"question_id":"Q1","options":["Ano"],"negate":true}' });
    expect(at({ question_id: "Q1", options: [1] }).kind).toBe("unread");
  });
});
