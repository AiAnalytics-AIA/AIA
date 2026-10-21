// @vitest-environment jsdom
// Analýza's inspector body (artifact-analysis ANL3).
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ResearchAnalysis } from "@/lib/api";
import { AnalysisInspect, setShownAnalysis } from "./AnalysisInspect";

type Module = ResearchAnalysis["modules"][string];
const mod = (over: Partial<Module> = {}): Module => ({
  outcome: "COMPLETED", artifact_id: "ART", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [], ...over,
});
const ANALYSIS: ResearchAnalysis = {
  run_id: "RUN-1", complete: true, internal_only: true, synthetic: true, pending: {},
  modules: {
    executive: mod({
      key_findings: [{ text: "Čaj **vede**.", claim_ids: ["C1"] }],
      claims: [{ claim_id: "C1", evidence_ref: "q2.pct.2", value: 38.4, indicative: false, data_origin: null }],
    }),
  },
};
const SPEC = { questions: [{ id: "q2", text: "Který nápoj byste si vybrali?", typ: "vyber", options: ["Kávu", "Čaj"] }], batteries: [] };

afterEach(() => { cleanup(); setShownAnalysis(null); });

describe("AnalysisInspect", () => {
  it("waits for the page's analysis, then opens a finding down to its measure on Výsledky", () => {
    render(<AnalysisInspect target={{ kind: "finding", id: "executive:0" }} />);
    expect(screen.getByText("Analýza běhu se načítá.")).toBeTruthy();
    act(() => setShownAnalysis({ runId: "RUN-1", analysis: ANALYSIS, spec: SPEC }));
    expect(screen.getByText("vede").tagName).toBe("STRONG");
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("#measure-q2");
    expect(link.textContent).toBe("38,4 % podíl odpovědi „Čaj“ · Který nápoj byste si vybrali?");
    // The drawer names no target: the page's chip is claim:executive:C1's one element.
    expect(document.querySelector("[data-aia]")).toBeNull();
  });

  it("opens a claim with the sentences that cite it", () => {
    setShownAnalysis({ runId: "RUN-1", analysis: ANALYSIS, spec: SPEC });
    render(<AnalysisInspect target={{ kind: "claim", id: "executive:C1" }} />);
    expect(document.querySelector('[data-inspect="claim"]')).toBeTruthy();
    expect(screen.getByText("Zjištění 1")).toBeTruthy();
    expect(screen.getByText("vede").tagName).toBe("STRONG");
  });

  it("says what is missing, and refuses a target that is not Analýza's", () => {
    setShownAnalysis({ runId: "RUN-1", analysis: ANALYSIS, spec: SPEC });
    render(<AnalysisInspect target={{ kind: "finding", id: "executive:4" }} />);
    expect(screen.getByText("Toto zjištění v uloženém běhu není.")).toBeTruthy();
    cleanup();
    render(<AnalysisInspect target={{ kind: "finding", id: "nonsense" }} />);
    expect(screen.getByText("Tuto položku Analýza nezná.")).toBeTruthy();
  });
});
