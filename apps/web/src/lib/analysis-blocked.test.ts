// Analýza's blocked claims (artifact-analysis ANL4).
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { cs } from "@/i18n/cs";
import type { ResearchAnalysis } from "@/lib/api";
import { blockedModules, wayOut } from "./analysis-blocked";

type Module = ResearchAnalysis["modules"][string];
const mod = (over: Partial<Module> = {}): Module => ({
  outcome: "COMPLETED", artifact_id: "ART", summary: null, research_question_answers: [], key_findings: [], claims: [], violations: [], ...over,
});
const analysis = (modules: Record<string, Module>): ResearchAnalysis => ({ run_id: "RUN-1", complete: false, internal_only: true, synthetic: true, pending: {}, modules });

describe("wayOut", () => {
  it("offers a same-data round only for what the server lists, after the run ended, and promises nothing unread", () => {
    expect(wayOut("hypotheses", true, ["hypotheses"])).toBe("retry");
    expect(wayOut("audience", true, ["hypotheses"])).toBe("same_data_fails");
    expect(wayOut("hypotheses", true, [])).toBe("same_data_fails");
    expect(wayOut("hypotheses", true, null)).toBe("unknown");
    expect(wayOut("hypotheses", false, ["hypotheses"])).toBe("run_unfinished");
  });
});

describe("blockedModules", () => {
  it("lists only modules stored BLOCKED, in module order, each reason once with every subject it named", () => {
    const rows = blockedModules(analysis({
      limitations: mod({ outcome: "BLOCKED", violations: [{ code: "SCHEMA_INVALID", subject: "summary", detail: "missing" }] }),
      executive: mod(),
      hypotheses: mod({ outcome: "BLOCKED", violations: [
        { code: "EVIDENCE_REF_UNKNOWN", subject: "c1", detail: "q9.mean" },
        { code: "EVIDENCE_REF_UNKNOWN", subject: "c2", detail: "q9.mean" },
        { code: "UNCITED_NUMBER", subject: "summary", detail: "42" },
      ] }),
    }));
    expect(rows.map((r) => r.module)).toEqual(["hypotheses", "limitations"]);
    expect(rows[0].reasons).toEqual([
      { code: "EVIDENCE_REF_UNKNOWN", items: [{ subject: "c1", detail: "q9.mean" }, { subject: "c2", detail: "q9.mean" }] },
      { code: "UNCITED_NUMBER", items: [{ subject: "summary", detail: "42" }] },
    ]);
    expect(blockedModules(null)).toEqual([]);
    expect(blockedModules(analysis({}))).toEqual([]);
  });

  it("has words for every reason the evidence gate can give", () => {
    // Held to the domain's one definition (domain/evidence/gate.py ViolationCode), read as written.
    const gate = readFileSync(new URL("../../../../packages/aia_core/src/aia_core/domain/evidence/gate.py", import.meta.url), "utf8");
    const enumBody = gate.slice(gate.indexOf("class ViolationCode"), gate.indexOf("@dataclass"));
    const codes = [...enumBody.matchAll(/^ {4}([A-Z_]+) = "/gm)].map((m) => m[1]);
    expect(codes.length).toBeGreaterThan(30);
    const words = (cs as unknown as { research: { exec: { violation: Record<string, string> } } }).research.exec.violation;
    expect(codes.filter((c) => !words[c])).toEqual([]);
    expect(Object.keys(words).filter((k) => !codes.includes(k))).toEqual([]);
  });
});
