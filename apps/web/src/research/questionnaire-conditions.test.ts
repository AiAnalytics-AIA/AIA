// The web's half of a question's display condition (working-copy-edit-ops WCE13): the rule cases
// are the shared edit case file's (edit-ops.cases.test.ts); this holds what that file cannot carry.
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { conditionRefusal } from "./questionnaire";

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
});
