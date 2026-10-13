import { describe, expect, it } from "vitest";

import { reportParts } from "./CompleteReport";

const step = (node_key: string, kind: string, status: string) => ({ node_key, kind, status });
const state = (steps: ReturnType<typeof step>[]) => Object.fromEntries(reportParts({ steps }).map((p) => [p.label, p.state]));

describe("reportParts", () => {
  it("claims a part only once the report step composed it", () => {
    expect(state([step("analysis_executive", "research_analysis", "SUCCEEDED"), step("report", "research_report", "RUNNING")])["Shrnutí a dopady pro rozhodnutí"]).toBe("pending");
    expect(state([step("report", "research_report", "SUCCEEDED")])["Shrnutí a dopady pro rozhodnutí"]).toBe("in");
  });

  it("puts the Sociomap in only when the run computed one", () => {
    expect(state([step("report", "research_report", "SUCCEEDED"), step("sociomap", "sociomap", "SUCCEEDED")])["Sociomapy"]).toBe("in");
    expect(state([step("report", "research_report", "SUCCEEDED")])["Sociomapy"]).toBe("later");
  });

  it("never says a part AIA does not compose yet is in the report", () => {
    const parts = reportParts({ steps: [step("report", "research_report", "SUCCEEDED"), step("sociomap", "sociomap", "SUCCEEDED")] });
    expect(parts.filter((p) => p.state === "later").map((p) => p.label)).toEqual(["Tabulky všech otázek", "Zadání, návrh a dotazník v příloze"]);
  });
});
