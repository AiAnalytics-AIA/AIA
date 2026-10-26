// Analýza's research-question coverage (artifact-analysis ANL2).
import { describe, expect, it } from "vitest";

import type { AnswerabilityGap, ResearchAnalysis } from "@/lib/api";
import { analysisHeader, coverage, findingId, findingsOf } from "./analysis-coverage";

type Module = ResearchAnalysis["modules"][string];

const RQ1 = "Jak lidé hodnotí banku?";
const RQ2 = "Proč zvažují změnu?";

const mod = (over: Partial<Module> = {}): Module => ({
  outcome: "COMPLETED", artifact_id: "ART", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [], ...over,
});
const claim = (claim_id: string, evidence_ref: string) => ({ claim_id, evidence_ref, value: 1, indicative: false, data_origin: null });
const analysis = (modules: Record<string, Module>): ResearchAnalysis => ({
  run_id: "RUN-1", complete: true, internal_only: true, synthetic: true, pending: {}, modules,
});
const gap = (research_question: string): AnswerabilityGap => ({ kind: "not_answerable", research_question, verdict: "UNANSWERABLE", reasons: ["no_measure"], measures: [] });

describe("coverage", () => {
  const answered = analysis({
    research_questions: mod({
      research_question_answers: [{ question: RQ1, answer: "Průměr 6,8.", claim_ids: ["c1"] }, { question: RQ2, answer: "Nevíme.", claim_ids: [] }],
      key_findings: [{ text: "Hodnocení 6,8.", claim_ids: ["c1"] }],
      claims: [claim("c1", "Q1.mean")],
    }),
    executive: mod({ key_findings: [{ text: "Jiné.", claim_ids: ["e1"] }, { text: "Stejná míra.", claim_ids: ["e2"] }], claims: [claim("e1", "Q2.mean"), claim("e2", "Q1.mean")] }),
  });

  it("answers each question of the design in its order, with the findings that cite the same measures", () => {
    const rows = coverage([RQ1, RQ2], answered, []);
    expect(rows.map((r) => [r.index, r.state])).toEqual([[0, "answered"], [1, "unsupported"]]);
    expect(rows[0].findings.map(findingId)).toEqual(["executive:1", "research_questions:0"]);
    expect(rows[1].findings).toEqual([]);
  });

  it("matches a question with its whitespace folded, as the server does", () => {
    expect(coverage(["Jak  lidé hodnotí\nbanku?"], answered, [])[0].state).toBe("answered");
  });

  it("reads a question recorded as a gap at start as a gap, with the recorded words, never as answered", () => {
    const withWords = analysis({ research_questions: mod({ research_question_answers: [{ question: RQ1, answer: "Průměr.", claim_ids: ["c1"], gap: "nelze zodpovědět (žádná otázka ji neměří)" }], claims: [claim("c1", "Q1.mean")] }) });
    const row = coverage([RQ1], withWords, [])[0];
    expect(row.state).toBe("gap");
    expect(row.gap).toEqual({ words: "nelze zodpovědět (žádná otázka ji neměří)" });
    // Only the run says so: the recorded gap itself, worded by the screen.
    const fromRun = coverage([RQ2], answered, [gap(RQ2)])[0];
    expect(fromRun.state).toBe("gap");
    expect(fromRun.gap).toEqual({ recorded: gap(RQ2) });
  });

  it("never reads a blocked or missing module as an answer", () => {
    const blocked = analysis({ research_questions: mod({ outcome: "BLOCKED", violations: [{ code: "x", subject: "y", detail: "z" }] }) });
    expect(coverage([RQ1], blocked, [])[0].state).toBe("blocked");
    expect(coverage([RQ1], analysis({}), [])[0].state).toBe("pending");
    expect(coverage([RQ1], null, [gap(RQ1)])[0].state).toBe("gap");
    expect(coverage([RQ1], null, [])[0].state).toBe("pending");
    expect(coverage(["Nikdo se neptal?"], answered, [])[0].state).toBe("unanswered");
  });

  it("says each row's state in one of the stage's words, never Odpovězeno for what is not known (ANL2b)", () => {
    const verdicts = (rows: ReturnType<typeof coverage>) => rows.map((r) => r.verdict);
    expect(verdicts(coverage([RQ1, RQ2], answered, []))).toEqual(["answered", "no_data"]);
    // A segment comparison the run could not make, answered with a number: Orientačně.
    const segments = { ...gap(RQ1), reasons: ["segments_unavailable"] };
    expect(verdicts(coverage([RQ1], answered, [segments]))).toEqual(["indicative"]);
    // The same gap answered in words alone, or any other gap: Bez dat.
    expect(verdicts(coverage([RQ2], answered, [{ ...gap(RQ2), reasons: ["segments_unavailable"] }]))).toEqual(["no_data"]);
    expect(verdicts(coverage([RQ1], answered, [gap(RQ1)]))).toEqual(["no_data"]);
    const blocked = analysis({ research_questions: mod({ outcome: "BLOCKED", violations: [{ code: "x", subject: "y", detail: "z" }] }) });
    expect(verdicts(coverage([RQ1], blocked, []))).toEqual(["unknown"]);
    expect(verdicts(coverage(["Nikdo se neptal?"], answered, []))).toEqual(["unknown"]);
    expect(verdicts(coverage([RQ1], null, []))).toEqual(["pending"]);
    // Before the module is stored, a recorded gap waits too, never a verdict the analysis may contradict.
    expect(verdicts(coverage([RQ1], null, [segments]))).toEqual(["pending"]);
    // A segment comparison that also has no citable measure has no data, whatever the module cites.
    expect(verdicts(coverage([RQ1], answered, [{ ...gap(RQ1), reasons: ["segments_unavailable", "no_citable_measure"] }]))).toEqual(["no_data"]);
  });

  it("lists only the design's questions: a question the module did not answer keeps its row", () => {
    expect(coverage([RQ1, "Nikdo se neptal?"], answered, []).map((r) => r.state)).toEqual(["answered", "unanswered"]);
    expect(coverage([], answered, [])).toEqual([]);
  });
});

describe("findingsOf", () => {
  it("lists completed modules' findings in module order and skips blocked ones", () => {
    const a = analysis({
      limitations: mod({ key_findings: [{ text: "L", claim_ids: [] }] }),
      executive: mod({ key_findings: [{ text: "E", claim_ids: [] }] }),
      objects: mod({ outcome: "BLOCKED", key_findings: [{ text: "O", claim_ids: [] }] }),
    });
    expect(findingsOf(a).map((f) => findingId(f.ref))).toEqual(["executive:0", "limitations:0"]);
  });
});

describe("analysisHeader", () => {
  it("names the run's day, that it is internal, and its origin (ANL10)", () => {
    // Built from local parts, so the day is the 21st in every time zone (review of #932).
    const at = (year: number) => new Date(year, 9, 21, 12).toISOString();
    const now = new Date(2026, 9, 26, 12);
    expect(analysisHeader(at(2026), "MODELLED", now)).toBe("Běh z 21. 10. · interní · modelováno");
    expect(analysisHeader(at(2026), "SIMULATED", now)).toBe("Běh z 21. 10. · interní · fiktivní respondenti");
    // A run from another year says which.
    expect(analysisHeader(at(2025), "MODELLED", now)).toBe("Běh z 21. 10. 2025 · interní · modelováno");
  });

  it("leaves out a date it cannot read and never reads an unread origin as known", () => {
    expect(analysisHeader(null, null)).toBe("Běh · interní · neznámý původ dat");
    expect(analysisHeader("not a date", "UNKNOWN")).toBe("Běh · interní · neznámý původ dat");
  });
});
