// How a research run and its results read (ADR 0016): the rules the three
// execution stages share, without React.
import { describe, expect, it } from "vitest";

import type { ResearchRun, ResearchStep } from "@/lib/api";
import { aggregateDeviation, hasUnknownOrigin, isModelled, isSynthetic, mayRetryAnalysis, MODELLED_DISCLOSURE, needsRepair, originKind, resultOriginKind, stepOriginKind, parkedForRuntime, phaseTone, populationNote, resultTable, shouldPoll, stepLabel, stepStatusLabel, stepTone, supportNote, topBoxWidth, waitingDetail } from "./research-execution";

const run = (extra: Partial<ResearchRun>): ResearchRun =>
  ({ phase: "RUNNING", is_terminal: false, steps: [], fieldwork_source: "ai_runtime", ...extra }) as ResearchRun;

describe("research execution", () => {
  it("keeps reading only while something can change on its own", () => {
    expect(shouldPoll(run({ phase: "QUEUED" }))).toBe(true);
    expect(shouldPoll(run({ phase: "RUNNING" }))).toBe(true);
    expect(shouldPoll(run({ phase: "WAITING" }))).toBe(false); // a parked run does not move by itself
    expect(shouldPoll(run({ phase: "COMPLETED", is_terminal: true }))).toBe(false);
  });

  it("finds the step waiting for the AI runtime, and nothing else", () => {
    const parked = run({ steps: [{ node_key: "run", waiting_reason: "ai_runtime_unavailable" } as ResearchRun["steps"][number]] });
    expect(parkedForRuntime(parked)?.node_key).toBe("run");
    expect(parkedForRuntime(run({ steps: [{ node_key: "run", waiting_reason: "provider_quota_exhausted" } as ResearchRun["steps"][number]] }))).toBeNull();
  });

  it("gives every phase a tone, so colour is never the only cue", () => {
    expect(phaseTone("WAITING")).toBe("you");
    expect(phaseTone("FAILED")).toBe("fault");
    expect(phaseTone("COMPLETED")).toBe("done");
    expect(stepLabel("sociomap")).toBe("Sociomapa (interní)");
    expect(stepLabel("something_new")).toBe("something_new");
  });

  it("shows no number for a suppressed cell, and says why", () => {
    const base = { n_platnych: 60, effective_n: 12, n_unique_layer_donors: 19 };
    const hidden = resultTable("t1", { typ: "vyber", support_status: "SUPPRESS", ...base, celkem_pct: { A: 55.2 }, intervaly_95: { A: { low: 40, high: 70 } } });
    expect(hidden.suppressed).toBe(true);
    expect(hidden.rows).toEqual([{ label: "A", value: null, interval: null }]);
    expect(supportNote(hidden)).toMatch(/Potlačeno: jen 19/);
    const shown = resultTable("t1", { typ: "multi", support_status: "INDICATIVE", ...base, n_unique_layer_donors: 40, celkem_pct: { A: 55.2 }, intervaly_95: { A: { low: 40, high: 70 } } });
    // A shown share carries its bar (Studio v3); the suppressed one above has none.
    expect(shown.rows).toEqual([{ label: "A", value: "55,2 %", interval: "40,0–70,0", bar: { value: 55.2, low: 40, high: 70 } }]);
    expect(supportNote(shown)).toMatch(/Indikativní/);
  });

  it("labels AI respondents on fictional personas as synthetic, like the fixture", () => {
    const step = (origin: string | null) => ({ node_key: "run", data_origin: origin }) as ResearchRun["steps"][number];
    expect(isSynthetic(run({ fieldwork_source: "synthetic_fixture" }))).toBe(true);
    expect(isSynthetic(run({ steps: [step("SYNTHETIC_AI_FICTIONAL")] }))).toBe(true);
    expect(isSynthetic(run({ steps: [step(null)] }))).toBe(false);
    expect(isSynthetic(run({ steps: [step("SOMETHING_ELSE")] }))).toBe(false);
  });

  it("reads every origin as simulated, modelled or unknown, the API's way (plan chunk 4d)", () => {
    expect(originKind("SYNTHETIC_FIXTURE")).toBe("SIMULATED");
    expect(originKind("SYNTHETIC_AI_FICTIONAL")).toBe("SIMULATED");
    expect(originKind("MODELLED_AI_PANEL")).toBe("MODELLED");
    for (const odd of [null, undefined, "", "PANEL", "SYNTHETIC_SOMETHING"]) expect(originKind(odd)).toBe("UNKNOWN");
    expect(MODELLED_DISCLOSURE).toBe("modelováno: AI respondenti z populace");
  });

  it("says a modelled run and an unknown origin, and never reads either as fieldwork", () => {
    const step = (origin: string | null, kind?: string) => ({ node_key: "run", data_origin: origin, data_origin_kind: kind }) as ResearchRun["steps"][number];
    const modelled = run({ fieldwork_source: "ai_runtime", steps: [step("MODELLED_AI_PANEL")] });
    expect([isModelled(modelled), isSynthetic(modelled), hasUnknownOrigin(modelled)]).toEqual([true, false, false]);
    const odd = run({ fieldwork_source: "ai_runtime", steps: [step("PANEL")] });
    expect([isModelled(odd), isSynthetic(odd), hasUnknownOrigin(odd)]).toEqual([false, false, true]);
    expect(stepOriginKind(step(null))).toBeNull();
    // The API's stated kind wins over the page's own reading: an origin added later is not unknown.
    expect(stepOriginKind(step("MODELLED_AI_PANEL_V2", "MODELLED"))).toBe("MODELLED");
    expect(stepOriginKind(step("PANEL", "MEASURED"))).toBe("UNKNOWN");
  });

  it("reads an analysis or a report by its stated kind, an older API by its synthetic flag", () => {
    expect(resultOriginKind({ synthetic: false, data_origin_kind: "MODELLED" })).toBe("MODELLED");
    expect(resultOriginKind({ synthetic: true })).toBe("SIMULATED");
    expect(resultOriginKind({ synthetic: false })).toBe("UNKNOWN");
    expect(resultOriginKind({})).toBe("UNKNOWN");
    // The API states no kind while nothing with an origin exists (analysis pending): neutral.
    expect(resultOriginKind({ synthetic: false, data_origin_kind: null })).toBeNull();
    expect(resultOriginKind({ synthetic: true, data_origin_kind: null })).toBe("SIMULATED");
    expect(resultOriginKind({ data_origin_kind: "MEASURED" })).toBe("UNKNOWN");
  });
});


describe("waitingDetail", () => {
  const base = { node_key: "run", kind: "k", stage_type: "FIELDWORK", status: "WAITING_PROVIDER", waiting_reason: null, attempts_recorded: 1,
    max_attempts: 3, started_at: null, finished_at: null, failure_class: null, error_message: null, artifact_id: null, data_origin: null } as ResearchStep;

  it("prefers what the step recorded over a generic line", () => {
    expect(waitingDetail({ ...base, waiting_reason: "budget_exceeded", error_message: "Přesný důvod." })).toBe("Přesný důvod.");
  });

  it("tells budget, quota and decisions apart", () => {
    expect(waitingDetail({ ...base, status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded" })).toMatch(/rozpočet/);
    expect(waitingDetail({ ...base, waiting_reason: "provider_quota_exhausted" })).toMatch(/kvótu/);
    expect(waitingDetail({ ...base, status: "AWAITING_GATE", waiting_reason: "gate:design" })).toMatch(/rozhodnutí/);
  });

  it("says nothing for a step that is not waiting, and guesses nothing for a reason it does not know", () => {
    expect(waitingDetail({ ...base, status: "SUCCEEDED", error_message: "stará chyba" })).toBeNull();
    expect(waitingDetail({ ...base, status: "FAILED", error_message: "x" })).toBeNull();
    expect(waitingDetail({ ...base, waiting_reason: "something_new" })).toBeNull();
  });
});

describe("populationNote (population-operations P3)", () => {
  const recorded = { population_id: "CZ_LIVE", version_id: "DSV-x", version_label: "v17_4_0", read_by_fieldwork: false };

  it("says nothing for a run that recorded no population", () => {
    expect(populationNote({ population: null })).toBeNull();
    expect(populationNote({})).toBeNull();
  });

  it("names the recorded version and says the respondents did not come from it", () => {
    const note = populationNote({ population: recorded });
    expect(note).toContain("v17_4_0");
    expect(note).toContain("CZ_LIVE");
    expect(note).toMatch(/fiktivní/);
  });

  it("drops the fictional caveat only when fieldwork read the population", () => {
    const note = populationNote({ population: { ...recorded, read_by_fieldwork: true } });
    expect(note).toContain("v17_4_0");
    expect(note).not.toMatch(/fiktivní/);
  });
});


describe("aggregateDeviation (methodology-tab G2c)", () => {
  it("is null for 18.6.6's port and reads what a deviation names", () => {
    expect(aggregateDeviation({ questions: {} })).toBeNull();
    expect(aggregateDeviation(null)).toBeNull();
    const d = aggregateDeviation({
      deviation: { methodology_version: "aia-aggregate-1+e1", changed: [{ path: "top_box", unit: 2, used: 1 }], replaced_formulas: ["agg.share"] },
    });
    expect(d).toEqual({ version: "aia-aggregate-1+e1", changed: [{ path: "top_box", unit: 2, used: 1 }], formulas: ["agg.share"] });
    expect(topBoxWidth(d)).toBe(1);
    expect(topBoxWidth(null)).toBe(2);
  });

  it("never passes an unreadable deviation as the port", () => {
    expect(aggregateDeviation({ deviation: "garbled" })).toEqual({ version: null, changed: [], formulas: [] });
    expect(aggregateDeviation({ deviation: { changed: [{ nope: 1 }, "x"], replaced_formulas: [3] } })).toEqual({ version: null, changed: [], formulas: [] });
    expect(topBoxWidth({ version: null, changed: [{ path: "top_box", unit: 2, used: "three" }], formulas: [] })).toBe(2);
  });

  it("names the top box by its width", () => {
    const base = { support_status: "REPORTABLE" as const, n_platnych: 100, n_unique_layer_donors: 60, effective_n: 50 };
    const scale = { typ: "skala", ...base, prumer: 3.1, top2box_pct: 40 };
    expect(resultTable("t", scale).rows[1].label).toBe("Horní dva body");
    expect(resultTable("t", scale, 3).rows[1].label).toBe("Horní body (3)");
  });
});

describe("an analysis module a model could not complete", () => {
  const analysisStep = (extra: Partial<ResearchStep>) =>
    ({ node_key: "analysis_objects", kind: "research_analysis", status: "SUCCEEDED", analysis_outcome: "COMPLETED", ...extra }) as ResearchStep;

  it("is not \"Hotovo\": its step succeeded, its module needs repair", () => {
    const blocked = analysisStep({ analysis_outcome: "BLOCKED" });
    expect(needsRepair(blocked)).toBe(true);
    expect(stepStatusLabel(blocked)).toBe("Potřebuje opravu");
    expect(stepTone(blocked)).toBe("fault");
    expect(stepStatusLabel(analysisStep({}))).toBe("Hotovo");
    expect(stepTone(analysisStep({}))).toBe("done");
    expect(needsRepair(analysisStep({ status: "RUNNING", analysis_outcome: null }))).toBe(false);
  });

  it("makes a finished run worth asking about a retry, and only a finished one", () => {
    const blocked = analysisStep({ analysis_outcome: "BLOCKED" });
    expect(mayRetryAnalysis(run({ is_terminal: true, steps: [blocked] }))).toBe(true);
    expect(mayRetryAnalysis(run({ is_terminal: false, steps: [blocked] }))).toBe(false);
    expect(mayRetryAnalysis(run({ is_terminal: true, steps: [analysisStep({ status: "FAILED", analysis_outcome: null })] }))).toBe(true);
    expect(mayRetryAnalysis(run({ is_terminal: true, steps: [analysisStep({})] }))).toBe(false);
  });
});
