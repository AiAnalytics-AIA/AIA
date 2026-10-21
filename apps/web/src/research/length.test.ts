// The questionnaire's length by Metodika's rule (artifact-questionnaire QST7).
import { describe, expect, it } from "vitest";

import { questionnaireLength, readRule } from "./length";
import type { ResearchProject } from "./model";

const RULE = { version: "readiness-1+e2", seconds: { vyber: 10, multi: 15, skala: 8, otevrena: 40, set_object: 6 }, max_seconds: null };
const project = (sections: unknown[]): ResearchProject => ({ sections }) as unknown as ResearchProject;
const SECTIONS = [
  { type: "questions", questions: [{ text: "A?", typ: "vyber" }, { text: "B?", typ: "multi" }, { text: "C?", typ: "otevrena" }] },
  { type: "object_battery", title: "Nápoje", objects: ["Káva", "Čaj", "Káva", " ", "Voda"] },
  { type: "intro", questions: [{ text: "Skryto?", typ: "vyber" }] },
];

describe("the questionnaire's length", () => {
  it("says the rule is unset rather than assume a number", () => {
    expect(questionnaireLength(project(SECTIONS), null)).toEqual({ kind: "unset" });
  });

  it("prices each question by its type and each distinct set object, to the half minute", () => {
    // 10 + 15 + 40 + 3 objects x 6 = 83 s, 1.5 min.
    expect(questionnaireLength(project(SECTIONS), readRule(RULE))).toEqual({ kind: "estimate", seconds: 83, minutes: 1.5, limit: "unset", rule: RULE });
  });

  it("measures the estimate against the study type's limit: within, over, or none set", () => {
    const at = (max: number | null) => questionnaireLength(project(SECTIONS), readRule({ ...RULE, max_seconds: max }));
    expect(at(83)).toMatchObject({ limit: "within" });
    expect(at(82)).toMatchObject({ limit: "over" });
    expect(at(null)).toMatchObject({ limit: "unset" });
    expect(questionnaireLength(project(SECTIONS), readRule({ version: RULE.version, seconds: RULE.seconds }))).toMatchObject({ limit: "unset" });
  });

  it("leaves the length unknown, never zero, when an item's type has no price", () => {
    const p = project([{ type: "questions", questions: [{ text: "A?", typ: "vyber" }, { text: "C?", typ: "matice" }, { text: "D?", typ: "set_object" }] }]);
    expect(questionnaireLength(p, readRule(RULE))).toEqual({ kind: "unknown", unpriced: 2 });
  });

  it("prices a question without a type as single choice, as the compiler reads it", () => {
    const p = project([{ type: "questions", questions: [{ text: "A?" }, { text: "B?", typ: "" }, { text: "C?", typ: " skala " }] }]);
    expect(questionnaireLength(p, readRule(RULE))).toMatchObject({ kind: "estimate", seconds: 28 });
  });

  it("reads a rule only when every price is a finite number of seconds", () => {
    expect(readRule(undefined)).toBeNull();
    expect(readRule(null)).toBeNull();
    expect(readRule({ ...RULE, version: 3 })).toBeNull();
    expect(readRule({ ...RULE, seconds: { ...RULE.seconds, skala: undefined } })).toBeNull();
    expect(readRule({ ...RULE, seconds: { ...RULE.seconds, skala: -1 } })).toBeNull();
    expect(readRule({ ...RULE, seconds: { ...RULE.seconds, skala: Number.NaN } })).toBeNull();
    expect(readRule({ ...RULE, seconds: { ...RULE.seconds, skala: 0 } })?.seconds.skala).toBe(0);
    expect(readRule({ ...RULE, max_seconds: -1 })).toBeNull();
    expect(readRule({ ...RULE, max_seconds: "600" })).toBeNull();
    expect(readRule({ ...RULE, max_seconds: 600 })?.max_seconds).toBe(600);
  });
});
