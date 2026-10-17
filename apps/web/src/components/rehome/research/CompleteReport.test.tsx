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

  it("claims the question tables, the design and the questionnaire once the report step composed them", () => {
    const parts = reportParts({ steps: [step("report", "research_report", "SUCCEEDED"), step("sociomap", "sociomap", "SUCCEEDED")] });
    const states = Object.fromEntries(parts.map((p) => [p.label, p.state]));
    expect(states["Tabulky všech otázek"]).toBe("in");
    expect(states["Návrh studie a dotazník v příloze"]).toBe("in");
    expect(states["Respondenti a výpočet"]).toBe("in");
    // Literature waits on a chosen review; nothing claims it.
    expect(states["Literatura (Deep Research)"]).toBe("pending");
  });

  it("claims the run-derived parts of a prepared variant whatever the run's own report step did", () => {
    // Review 2: a failed report step left a ready report-with-review listed as "čeká na přípravu".
    const steps = [step("report", "research_report", "FAILED"), step("sociomap", "sociomap", "SUCCEEDED")];
    const states = Object.fromEntries(reportParts({ steps }, "in", true).map((p) => [p.label, p.state]));
    expect(states["Shrnutí a dopady pro rozhodnutí"]).toBe("in");
    expect(states["Tabulky všech otázek"]).toBe("in");
    expect(states["Sociomapy"]).toBe("in");
    expect(states["Literatura (Deep Research)"]).toBe("in");
    expect(state(steps)["Shrnutí a dopady pro rozhodnutí"]).toBe("pending");
  });
});
