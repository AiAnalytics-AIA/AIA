import { describe, expect, it } from "vitest";

import type { Readiness } from "./api";
import { outlookSummary, personaSourcesOf, sourceChosenOnRun, supportForecastOf } from "./sample-view";

const readiness = (over: Partial<Readiness>): Readiness => ({
  design_revision_id: "r1", rules: "aia-readiness-1", ready: true, checks: [], questions: 3, batteries: 0, objects: 0, n: 200,
  fieldwork_source: "ai_runtime", cost_ceiling_usd: null, cost_ceiling_unknown: null, fieldwork_requests: 0, analysis_calls: 0,
  spend_confirm_usd: null, confirmation_required: false, ...over,
});

describe("supportForecastOf", () => {
  it("reads the server's forecast check for the fictional roster", () => {
    const r = readiness({ persona_source: "fictional_roster", checks: [{ id: "support_forecast", status: "PASS", message: "Běh bude mít 67 různých dárců na 200 respondentů: opora stačí." }] });
    expect(supportForecastOf(r)).toEqual({ known: true, status: "PASS", message: "Běh bude mít 67 různých dárců na 200 respondentů: opora stačí." });
  });

  it("reads a panel run's forecast as unknown, never good, keeping the server's words", () => {
    const r = readiness({ persona_source: "panel", checks: [{ id: "support_forecast", status: "WARN", message: "Kolik různých dárců běh bude mít, se ukáže až při výběru." }] });
    expect(supportForecastOf(r)).toEqual({ known: false, message: "Kolik různých dárců běh bude mít, se ukáže až při výběru." });
  });

  it("reads a readiness without the check as unknown", () => {
    expect(supportForecastOf(readiness({ checks: [{ id: "sample_size", status: "PASS", message: "n 200" }] }))).toEqual({ known: false, message: null });
  });
});

describe("outlookSummary", () => {
  it("counts every verdict, zero when none", () => {
    const item = (verdict: "ANSWERABLE" | "AT_RISK") => ({ question_id: verdict, text: "", section_id: "s", battery_id: null, verdict, reasons: [] });
    expect(outlookSummary(readiness({ question_outlook: [item("ANSWERABLE"), item("ANSWERABLE"), item("AT_RISK")] }))).toEqual({ UNANSWERABLE: 0, AT_RISK: 1, UNKNOWN: 0, ANSWERABLE: 2 });
  });

  it("is null when the API sent no outlook, never all answered", () => {
    expect(outlookSummary(readiness({}))).toBeNull();
    expect(outlookSummary(readiness({ question_outlook: [] }))).toBeNull();
  });
});

describe("personaSourcesOf", () => {
  it("lists the server's sources as sent", () => {
    const sources = [
      { source: "fictional_roster", offered: true, reason: null, default: true },
      { source: "panel", offered: false, reason: "panel_personas_disabled", default: false },
    ];
    expect(personaSourcesOf(readiness({ persona_sources: sources }))).toEqual(sources);
  });

  it("is null when the API sent none, never a default", () => {
    expect(personaSourcesOf(readiness({}))).toBeNull();
    expect(personaSourcesOf(readiness({ persona_sources: [] }))).toBeNull();
  });
});

describe("sourceChosenOnRun", () => {
  const sources = [{ source: "fictional_roster", offered: true, reason: null, default: true }];

  it("is true only for an AI-answered run with sources, as Spuštění offers the choice", () => {
    expect(sourceChosenOnRun(readiness({ persona_sources: sources }))).toBe(true);
    expect(sourceChosenOnRun(readiness({ fieldwork_source: "synthetic_fixture", persona_sources: sources }))).toBe(false);
    expect(sourceChosenOnRun(readiness({}))).toBe(false);
  });
});
