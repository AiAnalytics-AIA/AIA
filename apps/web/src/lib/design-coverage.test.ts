// Návrh's research questions with their coverage (artifact-design DSN2).
import { describe, expect, it } from "vitest";

import type { QuestionOutlook, ResearchTrace } from "@/lib/api";
import { coverageInputs, coverageInputsChanged, coverageStatus, rqCoverage } from "./design-coverage";

const outlook: QuestionOutlook[] = [
  { question_id: "q1", text: "Jak často pijete kávu?", section_id: "s1", battery_id: null, verdict: "ANSWERABLE", reasons: [] },
  { question_id: "o1", text: "Značka A", section_id: "sada", battery_id: "sada", verdict: "AT_RISK", reasons: ["support_indicative"] },
  { question_id: "o2", text: "Značka B", section_id: "sada", battery_id: "sada", verdict: "ANSWERABLE", reasons: [] },
];

const trace: ResearchTrace = {
  linked: true,
  dangling: [],
  questions: [
    { text: "Jak často lidé pijí kávu?", measures: ["q1"], verdict: "ANSWERABLE", reasons: [], comparison: "describe" },
    { text: "Které značky  vedou?", measures: ["o1", "o2"], verdict: "AT_RISK", reasons: ["support_indicative"], comparison: "rank_objects" },
    { text: "Proč lidé značku mění?", measures: [], verdict: "UNANSWERABLE", reasons: ["unmeasured"] },
    { text: "Kdo rozhoduje?", measures: [], verdict: "UNKNOWN", reasons: ["unlinked_design"] },
  ],
};

describe("coverageStatus", () => {
  it("reads the trace's verdict in V2's words, unknown never covered", () => {
    expect(coverageStatus("ANSWERABLE")).toBe("covered");
    expect(coverageStatus("AT_RISK")).toBe("partial");
    expect(coverageStatus("UNANSWERABLE")).toBe("gap");
    expect(coverageStatus("UNKNOWN")).toBe("unknown");
    expect(coverageStatus("SOMETHING_NEW")).toBe("unknown");
  });
});

describe("rqCoverage", () => {
  const working = ["Jak často lidé pijí kávu?", "Které značky vedou?", "Proč lidé značku mění?", "Kdo rozhoduje?", "Nová otázka po revizi?"];
  const rows = rqCoverage(working, trace, outlook);

  it("keeps the working copy's order and matches by text as the server compares a link", () => {
    expect(rows.map((r) => r.text)).toEqual(working);
    expect(rows[1].checked).toBe(true); // whitespace collapsed, as linkKey does
  });

  it("gives each question the trace's status, an unmeasured one a gap", () => {
    expect(rows.map((r) => r.status)).toEqual(["covered", "partial", "gap", "unknown", "unknown"]);
    expect(rows[2].reasons).toEqual(["unmeasured"]);
  });

  it("reads a question the revision does not hold as not checked, never covered", () => {
    expect(rows[4]).toMatchObject({ checked: false, status: "unknown", measures: [], comparison: null });
  });

  it("names each measure's place in Dotazník: a question by its card, a tracked set once", () => {
    expect(rows[0].measures).toEqual([expect.objectContaining({ key: "q1", anchor: "qedit_q1", verdict: "ANSWERABLE" })]);
    expect(rows[1].measures).toHaveLength(1);
    expect(rows[1].measures[0]).toMatchObject({ key: "sada", anchor: "qset_sada" });
    expect(rows[1].comparison).toBe("rank_objects");
  });

  it("leaves out a trace question the copy no longer states, and reads nothing without a trace", () => {
    expect(rqCoverage(["Jak často lidé pijí kávu?"], trace, outlook)).toHaveLength(1);
    expect(rqCoverage(["Jak často lidé pijí kávu?"], null, [])[0]).toMatchObject({ checked: false, status: "unknown" });
  });

  it("keeps a measure the outlook does not list as unknown, by its id", () => {
    const t: ResearchTrace = { linked: true, dangling: [], questions: [{ text: "X?", measures: ["gone"], verdict: "UNKNOWN", reasons: [] }] };
    expect(rqCoverage(["X?"], t, outlook)[0].measures[0]).toMatchObject({ key: "gone", code: "gone", verdict: "UNKNOWN", anchor: "qedit_gone" });
  });
});

describe("coverageInputs", () => {
  const sections = [{ id: "s1", questions: [] }];
  const project = (over: Record<string, unknown> = {}) => ({ goal: "G", sections, research_plan: { research_questions: ["Kdo?"], ...over } }) as never;

  it("changes with the research questions, their comparisons or the questionnaire, and nothing else", () => {
    const base = coverageInputs(project());
    expect(coverageInputsChanged(base, coverageInputs(project()))).toBe(false);
    expect(coverageInputsChanged(base, coverageInputs(project({ hypotheses: ["H"] })))).toBe(false);
    expect(coverageInputsChanged(base, coverageInputs(project({ research_questions: ["Kdo nakupuje?"] })))).toBe(true);
    expect(coverageInputsChanged(base, coverageInputs(project({ research_question_comparisons: [{}] })))).toBe(true);
    expect(coverageInputsChanged(base, coverageInputs({ ...(project() as object), sections: [...sections] } as never))).toBe(true);
  });
});
