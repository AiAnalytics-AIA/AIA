// What Analýza's inspector shows for a finding or a claim (artifact-analysis ANL3).
import { describe, expect, it } from "vitest";

import type { ResearchAnalysis } from "@/lib/api";
import { inspectView } from "./analysis-inspect";

type Module = ResearchAnalysis["modules"][string];

const SPEC = { questions: [{ id: "q2", text: "Který nápoj byste si vybrali?", typ: "vyber", options: ["Kávu", "Čaj"] }], batteries: [] };
const mod = (over: Partial<Module> = {}): Module => ({
  outcome: "COMPLETED", artifact_id: "ART", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [], ...over,
});
const analysis = (modules: Record<string, Module>): ResearchAnalysis => ({ run_id: "RUN-1", complete: true, internal_only: true, synthetic: true, pending: {}, modules });

const A = analysis({
  executive: mod({
    key_findings: [{ text: "Čaj vede.", claim_ids: ["C1", "C9", "C3"] }],
    research_question_answers: [{ question: "Co lidé pijí?", answer: "Hlavně čaj.", claim_ids: ["C1"] }],
    claims: [
      { claim_id: "C1", evidence_ref: "q2.pct.2", value: 38.4, indicative: false, data_origin: null },
      { claim_id: "C3", evidence_ref: "x9.median", value: 4, indicative: true, data_origin: null },
    ],
  }),
  objects: mod({ outcome: "BLOCKED" }),
});

describe("inspectView", () => {
  it("opens a finding with every number it cites, resolved to its measure on Výsledky", () => {
    const view = inspectView({ kind: "finding", module: "executive", index: 0 }, A, SPEC);
    if (view.kind !== "finding") throw new Error(view.kind);
    expect(view.text).toBe("Čaj vede.");
    expect(view.numbers.map((n) => [n.target, n.href, n.measure?.what ?? null])).toEqual([
      ["claim:executive:C1", "#measure-q2", "podíl odpovědi „Čaj“"],
      ["claim:executive:C3", null, null],
    ]);
    // A claim id the module does not hold is named as a code, never dropped silently.
    expect(view.unresolved).toEqual(["C9"]);
  });

  it("opens a claim with its measure and every sentence of its module that cites it", () => {
    const view = inspectView({ kind: "claim", module: "executive", claimId: "C1" }, A, SPEC);
    if (view.kind !== "claim") throw new Error(view.kind);
    expect(view.title).toContain("38,4");
    expect(view.number.measure?.title).toBe("Který nápoj byste si vybrali?");
    expect(view.citedBy).toEqual([
      { kind: "finding", index: 0, text: "Čaj vede.", target: "finding:executive:0" },
      { kind: "answer", question: "Co lidé pijí?", text: "Hlavně čaj." },
    ]);
  });

  it("reads a target this run does not hold as missing, with why, never as another item", () => {
    expect(inspectView({ kind: "finding", module: "executive", index: 5 }, A, SPEC).kind).toBe("missing");
    expect(inspectView({ kind: "claim", module: "executive", claimId: "C7" }, A, SPEC).kind).toBe("missing");
    expect(inspectView({ kind: "finding", module: "audience", index: 0 }, A, SPEC).kind).toBe("missing");
    const blocked = inspectView({ kind: "finding", module: "objects", index: 0 }, A, SPEC);
    expect(blocked.kind === "missing" && blocked.why).toContain("neprošla kontrolou");
    expect(inspectView({ kind: "finding", module: "executive", index: 0 }, null, SPEC).kind).toBe("missing");
  });
});
