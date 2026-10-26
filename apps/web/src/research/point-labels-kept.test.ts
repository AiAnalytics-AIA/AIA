// A scale's labels on every point survive every rewrite of the questionnaire, and the respondent
// preview shows its true ends (#559 review). The server keeps them by the same rule
// (research_design.keep_point_labels, test_point_labels_kept.py).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { type ResearchProject, type Template, defaultsMerge } from "./model";
import { applyOptimized, previewBattery, previewQuestion } from "./questionnaire";
import { keepPointLabels } from "./scale-labels";

const POINTS = ["vůbec", "spíše ne", "nevím", "spíše ano", "zcela"];
const TEXT = "Jak moc vás produkt zaujal?";
const scale = (id: string, text: string, popisky_skaly: string[], skala = [1, 5]) => ({ id, text, typ: "skala", skala, popisky_skaly });
const sections = (...questions: object[]) => [{ id: "s1", type: "questions", title: "A", questions }];
const labelsOf = (xs: unknown[]) => ((xs[0] as { questions: { popisky_skaly?: string[] }[] }).questions[0]).popisky_skaly;
const STORED = sections(scale("Q1", TEXT, POINTS));

describe("keepPointLabels", () => {
  it("keeps the stored labels by id, by wording, then by the two ends", () => {
    expect(labelsOf(keepPointLabels(sections(scale("Q1", "Jiné?", ["a", "b"])), STORED))).toEqual(POINTS);
    expect(labelsOf(keepPointLabels(sections(scale("ai_q", `  ${TEXT.toUpperCase()} `, ["a", "b"])), STORED))).toEqual(POINTS);
    expect(labelsOf(keepPointLabels(sections(scale("ai_q", "Jiné?", ["Vůbec", "ZCELA"])), STORED))).toEqual(POINTS);
    expect(labelsOf(STORED)).toEqual(POINTS);
  });

  it("leaves a rewrite as written when no single stored scale of the same range matches", () => {
    const otherRange = sections(scale("Q1", TEXT, ["a", "b"], [1, 7]));
    expect(keepPointLabels(otherRange, STORED)).toEqual(otherRange);
    const unmatched = sections(scale("ai_q", "Jiné?", ["nízké", "vysoké"]));
    expect(keepPointLabels(unmatched, STORED)).toEqual(unmatched);
    const twice = [...STORED, { id: "s2", type: "questions", questions: [scale("Q9", TEXT, [...POINTS].reverse())] }];
    const byText = sections(scale("ai_q", TEXT, ["a", "b"]));
    expect(keepPointLabels(byText, twice)).toEqual(byText);
    const invalid = sections(scale("Q1", TEXT, ["a", "", "c", "d", "e"]));
    const rewrite = sections(scale("Q1", TEXT, ["a", "b"]));
    expect(keepPointLabels(rewrite, invalid)).toEqual(rewrite);
  });
});

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const TEMPLATE: Template = { empty_project: EMPTY };
const before: ResearchProject = defaultsMerge({ goal: "Test", sections: STORED }, TEMPLATE);
const rewritten = { project: { goal: "Test", sections: sections(scale("Q1", TEXT, ["vůbec", "zcela"])) } };

describe("the classic rewrites keep labels on every point", () => {
  it("Optimalizovat: the optimiser's two ends do not replace them", () => {
    expect(labelsOf(applyOptimized(rewritten, null, TEMPLATE, before).project.sections)).toEqual(POINTS);
    // Without the copy it rewrote, as the parity port reads it: as written.
    expect(labelsOf(applyOptimized(rewritten, null, TEMPLATE).project.sections)).toEqual(["vůbec", "zcela"]);
  });
});

describe("the respondent preview", () => {
  it("shows a scale labelled on every point by its first and last label", () => {
    const item = previewQuestion(scale("Q1", TEXT, POINTS), 1);
    expect(item.kind === "question" && item.scale).toEqual(["vůbec", "zcela"]);
    const ends = previewQuestion(scale("Q1", TEXT, ["nízké", "vysoké"]), 1);
    expect(ends.kind === "question" && ends.scale).toEqual(["nízké", "vysoké"]);
  });
  it("shows a set labelled on every point by its first and last label", () => {
    const set = previewBattery({ type: "object_battery", objects: ["A"], scale_labels: ["a", "b", "c", "d"] }, 1);
    expect(set.kind === "battery" && [set.low, set.high]).toEqual(["a", "d"]);
  });
});
