// What Design Research found for each research question (run-recovery-and-truth 3d).
import { describe, expect, it } from "vitest";

import type { DeepResearchBundle, DeepResearchRun, DesignProposal } from "@/lib/api";
import { latestDesignRun, questionEvidence, isDesignRun } from "./design-evidence";

const RQ = "Jak často lidé pijí kávu?";
const finding = (id: string) => ({ evidence_id: id, claim: `Tvrzení ${id}`, quote: "citace", source_title: "Zdroj", source: "https://example.org", source_class: "B", confidence: 0.7 });
const proposal: DesignProposal = {
  run_id: "DR-1", admissible: true, refusal: null,
  items: [
    { item_id: "DRP-1", kind: "EVIDENCE", subject_key: "q-aaaaaaaaaaaa", subject_kind: "QUESTION", subject_text: RQ, subject_origin: "research_plan.research_questions[0]", findings: [finding("EV-1"), finding("EV-2")] },
    { item_id: "DRP-2", kind: "GAP", subject_key: "q-bbbbbbbbbbbb", subject_kind: "QUESTION", subject_text: "Jiná?", subject_origin: "research_plan.research_questions[1]", findings: [] },
  ],
};
const bundle = {
  subjects: [
    { key: "q-aaaaaaaaaaaa", kind: "QUESTION", text: RQ, origin: "research_plan.research_questions[0]" },
    { key: "q-bbbbbbbbbbbb", kind: "QUESTION", text: "Jiná?", origin: "research_plan.research_questions[1]" },
    { key: "x-cccccccccccc", kind: "CROSS", text: "x", origin: "cross", question_key: "q-aaaaaaaaaaaa" },
  ],
  tracks: [{ track_id: "T-1", subject_key: "q-aaaaaaaaaaaa" }, { track_id: "T-2", subject_key: "q-bbbbbbbbbbbb" }],
  quarantined: [
    { reason: "low_source_quality", track_id: "T-1" },
    { reason: "low_source_quality", evidence: { subject_key: "x-cccccccccccc" } },
    { reason: "ungrounded_excerpt", track_id: "T-1" },
    { reason: "unverified", track_id: "T-2" },
    { reason: "unverified" },
  ],
} as unknown as DeepResearchBundle;

describe("Design Research evidence per research question", () => {
  it("joins the research question's findings and every rejection on it or its crosses", () => {
    const e = questionEvidence(`  ${RQ} `, proposal, bundle);
    expect(e.studied).toBe(true);
    expect(e.findings.map((f) => f.evidence_id)).toEqual(["EV-1", "EV-2"]);
    expect(e.rejected).toEqual([{ reason: "low_source_quality", count: 2 }, { reason: "ungrounded_excerpt", count: 1 }]);
  });

  it("tells a gap apart from a research question the run never studied", () => {
    expect(questionEvidence("Jiná?", proposal, bundle)).toEqual({ studied: true, findings: [], rejected: [{ reason: "unverified", count: 1 }] });
    expect(questionEvidence("Nová otázka?", proposal, bundle)).toEqual({ studied: false, findings: [], rejected: [] });
  });

  it("takes the newest finished Design Research run, never an interpretation run", () => {
    const run = (run_id: string, purpose: string, phase: string) => ({ run_id, purpose, phase }) as DeepResearchRun;
    expect(latestDesignRun([run("A", "INTERPRETATION_RESEARCH", "COMPLETED"), run("B", "DESIGN_RESEARCH", "RUNNING"), run("C", "DESIGN_RESEARCH", "COMPLETED"), run("D", "DESIGN_RESEARCH", "COMPLETED")])?.run_id).toBe("C");
    expect(latestDesignRun([])).toBeNull();
  });
});

describe("isDesignRun (PC18)", () => {
  it("is a Design Research run, or one made before purposes were recorded; never an interpretation", () => {
    expect(isDesignRun({ purpose: "DESIGN_RESEARCH" })).toBe(true);
    expect(isDesignRun({ purpose: null })).toBe(true);
    expect(isDesignRun({})).toBe(true);
    expect(isDesignRun({ purpose: "INTERPRETATION_RESEARCH" })).toBe(false);
  });
});
