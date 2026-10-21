import { describe, expect, it } from "vitest";

import type { ResearchRun } from "@/lib/api";
import { resultOriginKind, runOriginKinds, type OriginKind } from "@/lib/research-execution";

import { originWords, reportParts } from "./CompleteReport";

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

describe("the report card's origin (CR-5)", () => {
  const ORIGIN_PART = "Omezení, původ dat a příloha evidence";
  const done = [step("report", "research_report", "SUCCEEDED")];
  const detail = (origins: ReadonlySet<OriginKind>) => reportParts({ steps: done }, "pending", false, origins).find((p) => p.label === ORIGIN_PART)?.detail;
  // A run as the card reads it: its source and each step's stamped origin.
  const run = (fieldwork_source: string, origins: (string | null)[]) =>
    ({ fieldwork_source, steps: origins.map((data_origin) => ({ data_origin, data_origin_kind: null })) }) as unknown as ResearchRun;

  it("says a fictional run's data is fictional, never modelled", () => {
    expect(detail(runOriginKinds(run("ai_runtime", ["SYNTHETIC_AI_FICTIONAL"])))).toBe("Fiktivní data, otisky artefaktů");
    expect(detail(runOriginKinds(run("synthetic_fixture", [null])))).toBe("Fiktivní data, otisky artefaktů");
    expect(detail(new Set(["SIMULATED"]))).not.toContain("Modelovaná");
  });

  it("says a modelled run's data is modelled", () => {
    expect(detail(runOriginKinds(run("ai_runtime", ["MODELLED_AI_PANEL"])))).toBe("Modelovaná data, otisky artefaktů");
    expect(detail(new Set([resultOriginKind({ data_origin_kind: "MODELLED" }) as OriginKind]))).toBe("Modelovaná data, otisky artefaktů");
  });

  it("says an unknown origin as unknown, and nothing stated yet as unknown too, never presumed", () => {
    expect(detail(runOriginKinds(run("ai_runtime", ["SOMETHING_NEW"])))).toBe("Neznámý původ dat, otisky artefaktů");
    expect(detail(runOriginKinds(run("ai_runtime", [null])))).toBe("Neznámý původ dat, otisky artefaktů");
    expect(detail(new Set())).toBe("Neznámý původ dat, otisky artefaktů");
    expect(reportParts({ steps: done }).find((p) => p.label === ORIGIN_PART)?.detail).not.toContain("Modelovaná");
  });

  it("names every kind of a mixed run, in one order", () => {
    expect(originWords(new Set<OriginKind>(["MODELLED", "SIMULATED"]))).toBe("Fiktivní data + Modelovaná data");
  });
});
