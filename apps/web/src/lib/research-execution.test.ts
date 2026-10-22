// How a research run and its results read (ADR 0016): the rules the three
// execution stages share, without React.
import { t } from "@/i18n/t";
import { describe, expect, it } from "vitest";

import type { QuestionOutlook, ResearchRun, ResearchStep } from "@/lib/api";
import { aggregateDeviation, fidelityRefusal, hasUnknownOrigin, isModelled, isSynthetic, mayRetryAnalysis, MODELLED_DISCLOSURE, needsRepair, originKind, outlookByVerdict, traceMeasures, outlookCounts, outlookFixStep, outlookReason, resultOriginKind, stepOriginKind, parkedForRuntime, phaseTone, populationNote, reportHolds, respondentReceipt, resultTable, pollMs, shouldPoll, storedPlaces, UNIT_PLACES, stepLabel, stepStatusLabel, stepTone, supportNote, topBoxWidth, verdictTone, waitingDetail } from "./research-execution";

const run = (extra: Partial<ResearchRun>): ResearchRun =>
  ({ phase: "RUNNING", is_terminal: false, steps: [], fieldwork_source: "ai_runtime", ...extra }) as ResearchRun;

describe("research execution", () => {
  it("keeps reading only while something can change on its own", () => {
    expect(shouldPoll(run({ phase: "QUEUED" }))).toBe(true);
    expect(shouldPoll(run({ phase: "RUNNING" }))).toBe(true);
    // A run that waits for a person (a gate, the budget, recovery) does not move by itself...
    expect(shouldPoll(run({ phase: "WAITING", needs_attention: true }))).toBe(false);
    // ...and an older payload that does not say is not read as moving either.
    expect(shouldPoll(run({ phase: "WAITING" }))).toBe(false);
    // A provider's quota or capacity clears on its own: the run then finishes, and the page must see it.
    expect(shouldPoll(run({ phase: "WAITING", status: "WAITING_PROVIDER", needs_attention: false }))).toBe(true);
    // A park for a runtime that is not deployed never resumes by itself: it waits until a person acts.
    const parked = { node_key: "run", status: "WAITING_PROVIDER", waiting_reason: "ai_runtime_unavailable" } as ResearchRun["steps"][number];
    expect(shouldPoll(run({ phase: "WAITING", status: "WAITING_PROVIDER", needs_attention: false, steps: [parked] }))).toBe(false);
    // ...but a run whose other steps still move on their own is read (review 3: a map step running
    // beside parked analysis modules went unseen until a reload).
    const step = (status: string, waiting_reason: string | null = null) => ({ node_key: status, status, waiting_reason }) as ResearchRun["steps"][number];
    const waiting = (steps: ResearchRun["steps"]) => run({ phase: "WAITING", status: "WAITING_PROVIDER", needs_attention: false, steps });
    expect(shouldPoll(waiting([parked, step("RUNNING")]))).toBe(true);
    expect(shouldPoll(waiting([parked, step("RUNNABLE")]))).toBe(true);
    expect(shouldPoll(waiting([parked, step("WAITING_CAPACITY", "capacity")]))).toBe(true);
    expect(shouldPoll(waiting([parked, step("SUCCEEDED"), step("BLOCKED")]))).toBe(false);
    // A run that waits for a person while another of its steps still runs is read (PC14): the
    // map beside a module stopped at the budget finishes, and the page shows it.
    const attention = (steps: ResearchRun["steps"]) => run({ phase: "WAITING", status: "AWAITING_BUDGET", needs_attention: true, steps });
    expect(shouldPoll(attention([step("AWAITING_BUDGET", "budget_exceeded"), step("RUNNING")]))).toBe(true);
    expect(shouldPoll(attention([step("RECOVERY_REQUIRED"), step("RUNNABLE")]))).toBe(true);
    expect(shouldPoll(attention([step("AWAITING_BUDGET", "budget_exceeded"), step("SUCCEEDED")]))).toBe(false);
    expect(pollMs(run({ phase: "WAITING", needs_attention: false }))).toBeGreaterThan(pollMs(run({ phase: "RUNNING" })));
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
    expect(stepLabel("sociomap")).toBe("Sociomapa");
    expect(stepLabel("something_new")).toBe("something_new");
  });

  it("lists a choice question's answers in the order it asked them, not the stored name order", () => {
    // The aggregate is canonical JSON, its answers sorted by name (artifact_repository.py sort_keys).
    const stored = { typ: "vyber", n_platnych: 300, effective_n: 250, n_unique_layer_donors: 200, support_status: "REPORTABLE" as const, celkem_pct: { "Jeden až dva dny": 30, "Každý den": 28, "Méně často": 20, Jinak: 2 }, intervaly_95: {} };
    const table = resultTable("q", stored, 2, UNIT_PLACES, ["Každý den", "Jeden až dva dny", "Méně často"]);
    expect(table.rows.map((r) => r.label)).toEqual(["Každý den", "Jeden až dva dny", "Méně často", "Jinak"]);
    expect(resultTable("q", stored).rows.map((r) => r.label)).toEqual(["Jeden až dva dny", "Každý den", "Méně často", "Jinak"]);
  });

  it("shows each number at the places the aggregate stored it, never rounded again (V1b)", () => {
    expect(storedPlaces({ questions: {} })).toEqual(UNIT_PLACES);
    expect(storedPlaces({ rounding: { share_decimals: 0, mean_decimals: 3 } })).toEqual({ share: 0, mean: 3 });
    expect(storedPlaces({ rounding: { share_decimals: 9, mean_decimals: "2" } })).toEqual(UNIT_PLACES);
    const base = { n_platnych: 300, effective_n: 250, n_unique_layer_donors: 200, support_status: "REPORTABLE" as const };
    const share = resultTable("q", { typ: "vyber", ...base, celkem_pct: { Kávu: 38 }, intervaly_95: { Kávu: { low: 34, high: 43 } } }, 2, { share: 0, mean: 3 });
    expect(share.rows[0]).toMatchObject({ value: "38 %", interval: "34–43" });
    const scale = resultTable("q", { typ: "skala", ...base, prumer: 7.432, prumer_interval_95: { low: 7.209, high: 7.651 }, top2box_pct: 61.804, top2box_interval_95: { low: 55.1, high: 68.25 } }, 2, { share: 3, mean: 3 });
    expect(scale.rows[0]).toMatchObject({ value: "7,432", interval: "7,209–7,651" });
    expect(scale.rows[1].value).toBe("61,804 %");
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

  it("says who fixes a refusal of the AI route on Progress, after what the step recorded (LO12a)", () => {
    const parked = waitingDetail({ ...base, waiting_reason: "ai_runtime_unavailable", error_message: "Běh čeká u sběru dat.", error_reason: "egress_residency_violation" });
    expect(parked).toMatch(/^Běh čeká u sběru dat\. Opraví to provozovatel AIA/);
    expect(parked).toContain("aia_ai_route_eu_processing_approved");
    expect(waitingDetail({ ...base, error_message: "Běh čeká u sběru dat.", error_reason: "licence_undetermined" })).toBe("Běh čeká u sběru dat.");
  });

  it("tells budget, quota and decisions apart", () => {
    expect(waitingDetail({ ...base, status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded" })).toMatch(/rozpočet/);
    expect(waitingDetail({ ...base, waiting_reason: "provider_quota_exhausted" })).toMatch(/kvótu/);
    expect(waitingDetail({ ...base, status: "AWAITING_GATE", waiting_reason: "gate:design" })).toMatch(/rozhodnutí/);
  });

  it("says why a step stopped for recovery, a paid call of unknown outcome first (PC14)", () => {
    const stopped = { ...base, status: "RECOVERY_REQUIRED" };
    expect(waitingDetail({ ...stopped, recovery_reason: "paid_call_uncertain", error_message: "timeout" })).toBe(t("research.exec.wait.paid_call_uncertain"));
    expect(waitingDetail({ ...stopped, recovery_reason: "attempts_exhausted", error_message: "Poslední chyba." })).toBe("Poslední chyba.");
    expect(waitingDetail({ ...stopped, recovery_reason: "attempts_exhausted" })).toBe(t("research.exec.wait.attempts_exhausted"));
    // Not read (a listing): unknown, said as such, never guessed to be either.
    expect(waitingDetail({ ...stopped, recovery_reason: null })).toBe(t("research.exec.wait.recovery_required"));
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

  it("says a step that had not started when its run ended will not run, never ready (PC14)", () => {
    for (const status of ["PENDING", "RUNNABLE", "BLOCKED"]) {
      const untouched = analysisStep({ status, analysis_outcome: null });
      expect(stepStatusLabel(untouched, true)).toBe(t("research.exec.stepStatus.WILL_NOT_RUN"));
      expect(stepTone(untouched, true)).toBe("neutral");
      expect(stepStatusLabel(untouched, false)).not.toBe(t("research.exec.stepStatus.WILL_NOT_RUN"));
    }
    // What ran is said as it ran, ended run or not.
    expect(stepStatusLabel(analysisStep({ status: "RUNNING", analysis_outcome: null }), true)).toBe("Běží");
    expect(stepStatusLabel(analysisStep({}), true)).toBe("Hotovo");
  });

  it("makes a finished run with analysis worth asking about a retry, and only a finished one", () => {
    const blocked = analysisStep({ analysis_outcome: "BLOCKED" });
    expect(mayRetryAnalysis(run({ is_terminal: true, steps: [blocked] }))).toBe(true);
    expect(mayRetryAnalysis(run({ is_terminal: false, steps: [blocked] }))).toBe(false);
    expect(mayRetryAnalysis(run({ is_terminal: true, steps: [analysisStep({ status: "FAILED", analysis_outcome: null })] }))).toBe(true);
    // A completed module may have been completed under an earlier harness: only the API knows (PC3).
    expect(mayRetryAnalysis(run({ is_terminal: true, steps: [analysisStep({})] }))).toBe(true);
    expect(mayRetryAnalysis(run({ is_terminal: true, steps: [] }))).toBe(false);
  });
});

describe("reportHolds (run-gate-visibility chunk 2)", () => {
  const step = (node_key: string, kind: string, status: string, extra: Partial<ResearchStep> = {}) =>
    ({ step_id: `S-${node_key}`, node_key, kind, stage_type: "ANALYSIS", status, waiting_reason: null, attempts_recorded: 1, max_attempts: 3,
      started_at: null, finished_at: null, failure_class: null, error_message: null, artifact_id: null, data_origin: null, ...extra }) as ResearchStep;
  const runOf = (steps: ResearchStep[]) => ({ steps }) as unknown as ResearchRun;

  it("names each analysis module that has not succeeded, with what it recorded, in the run's order", () => {
    const held = reportHolds(runOf([
      step("aggregate", "research_aggregate", "SUCCEEDED"),
      step("analysis_executive", "research_analysis", "SUCCEEDED"),
      step("analysis_audience", "research_analysis", "WAITING_PROVIDER", { waiting_reason: "analysis_unconfigured", error_message: "AI analýza není zapnuta." }),
      step("analysis_segments", "research_analysis", "AWAITING_BUDGET", { waiting_reason: "budget_exceeded" }),
      step("analysis_hypotheses", "research_analysis", "FAILED", { error_message: "Model odpověděl mimo schéma." }),
      step("analysis_limitations", "research_analysis", "PENDING"),
      step("report", "research_report", "PENDING"),
    ]));
    expect(held.map((h) => h.step.node_key)).toEqual(["analysis_audience", "analysis_segments", "analysis_hypotheses", "analysis_limitations"]);
    expect(held[0].detail).toBe("AI analýza není zapnuta.");
    expect(held[1].detail).toMatch(/rozpočet/);
    expect(held[2].detail).toBe("Model odpověděl mimo schéma.");
    // Not started yet: unknown, never an invented reason; and a report merely not started holds nothing itself.
    expect(held[3].detail).toBeNull();
  });

  it("names the report step itself when it failed or waits, with its message", () => {
    const held = reportHolds(runOf([
      step("analysis_executive", "research_analysis", "SUCCEEDED"),
      step("report", "research_report", "FAILED", { error_message: "audience: no admitted result" }),
    ]));
    expect(held).toEqual([{ step: expect.objectContaining({ node_key: "report" }), detail: "audience: no admitted result" }]);
    expect(reportHolds(runOf([step("report", "research_report", "SUCCEEDED")]))).toEqual([]);
  });

  it("names a module stored BLOCKED, whose step succeeded, as holding the report", () => {
    const held = reportHolds(runOf([
      step("analysis_executive", "research_analysis", "SUCCEEDED", { analysis_outcome: "COMPLETED" }),
      step("analysis_objects", "research_analysis", "SUCCEEDED", { analysis_outcome: "BLOCKED" }),
    ]));
    expect(held.map((h) => h.step.node_key)).toEqual(["analysis_objects"]);
    expect(held[0].detail).toMatch(/zopakovat/);
  });
});

describe("which questions a run will answer (run-recovery-and-truth 2b)", () => {
  const item = (id: string, verdict: QuestionOutlook["verdict"], reasons: string[] = []): QuestionOutlook => ({ question_id: id, text: id, section_id: "s", battery_id: null, verdict, reasons });

  it("reads worst first and keeps questionnaire order within a verdict", () => {
    const items = [item("a", "ANSWERABLE"), item("b", "AT_RISK"), item("c", "UNANSWERABLE"), item("d", "UNKNOWN"), item("e", "UNANSWERABLE")];
    expect(outlookByVerdict(items).map((i) => i.question_id)).toEqual(["c", "e", "b", "d", "a"]);
    expect(outlookCounts(items)).toEqual({ UNANSWERABLE: 2, AT_RISK: 1, UNKNOWN: 1, ANSWERABLE: 1 });
    expect(outlookCounts([])).toEqual({ UNANSWERABLE: 0, AT_RISK: 0, UNKNOWN: 0, ANSWERABLE: 0 });
  });

  it("never gives unknown the tone of an answer", () => {
    expect(verdictTone("UNKNOWN")).toBe("neutral");
    expect(verdictTone("ANSWERABLE")).toBe("done");
    expect(verdictTone("AT_RISK")).toBe("you");
    expect(verdictTone("UNANSWERABLE")).toBe("fault");
  });

  it("sends a question's own fault to the questionnaire and a support fault to the sample", () => {
    expect(outlookFixStep(["fidelity_refused", "support_suppressed"])).toBe("questionnaire");
    expect(outlookFixStep(["support_suppressed"])).toBe("persona");
    expect(outlookFixStep(["support_indicative"])).toBe("persona");
    expect(outlookFixStep(["support_analysis_excluded"])).toBe("persona");
    expect(outlookFixStep(["support_unknown"])).toBeNull();
    expect(outlookFixStep([])).toBeNull();
  });

  it("words every reason, and names one it does not know", () => {
    for (const code of ["conditional", "familiarity", "fidelity_refused", "open_ended", "support_suppressed", "support_analysis_excluded", "support_indicative", "support_unknown"]) {
      expect(outlookReason(code)).not.toContain(code);
    }
    expect(outlookReason("new_rule")).toContain("new_rule");
  });
});

describe("a research question's measures in words (run-recovery-and-truth 3b)", () => {
  const item = (id: string, text: string, verdict: QuestionOutlook["verdict"], battery_id: string | null = null): QuestionOutlook => ({ question_id: id, text, section_id: battery_id ?? "s", battery_id, verdict, reasons: [] });
  const outlook = [
    item("q1", "Jak často pijete kávu?", "ANSWERABLE"),
    item("set_obj_a", "Jak hodnotíte Káva?", "AT_RISK", "set"),
    item("set_obj_b", "Jak hodnotíte Čaj?", "ANSWERABLE", "set"),
  ];

  it("names a question by its wording and a tracked set once, with its best verdict", () => {
    const measures = traceMeasures({ text: "RQ", measures: ["q1", "set_obj_a", "set_obj_b"], verdict: "ANSWERABLE", reasons: [] }, outlook);
    expect(measures.map((m) => [m.text, m.verdict])).toEqual([
      ["Jak často pijete kávu?", "ANSWERABLE"],
      ["Jak hodnotíte Káva? a další položky sady (2 celkem)", "ANSWERABLE"],
    ]);
  });

  it("reads a measure the outlook does not list as unknown, never answerable, by words with its id kept aside (6c)", () => {
    expect(traceMeasures({ text: "RQ", measures: ["gone"], verdict: "UNKNOWN", reasons: [] }, outlook)).toEqual([
      { key: "gone", text: "Otázka bez uloženého znění", verdict: "UNKNOWN", code: "gone" },
    ]);
  });
});

describe("respondentReceipt (run-recovery-and-truth 5b)", () => {
  const fieldwork = (data_origin: string | null, data_origin_kind?: string | null) => ({ node_key: "run", data_origin, data_origin_kind }) as never;
  it("puts the pinned source beside the origin the fieldwork data reports", () => {
    expect(respondentReceipt({ persona_source: "fictional_roster", steps: [fieldwork("SYNTHETIC_AI_FICTIONAL", "SIMULATED")] })).toEqual({ pinned: "fictional_roster", observed: "SIMULATED", origin: "SYNTHETIC_AI_FICTIONAL", mismatch: false });
    expect(respondentReceipt({ persona_source: "panel", steps: [fieldwork("MODELLED_AI_PANEL")] })).toEqual({ pinned: "panel", observed: "MODELLED", origin: "MODELLED_AI_PANEL", mismatch: false });
  });
  it("says nothing was observed before fieldwork stores its data, and reads an older run as the roster", () => {
    expect(respondentReceipt({ steps: [fieldwork(null, null)] })).toEqual({ pinned: "fictional_roster", observed: null, origin: null, mismatch: false });
    expect(respondentReceipt({ persona_source: "panel", steps: [] }).observed).toBeNull();
  });
  it("names a mismatch, and an unknown origin is never a match", () => {
    expect(respondentReceipt({ persona_source: "panel", steps: [fieldwork("SYNTHETIC_AI_FICTIONAL")] }).mismatch).toBe(true);
    expect(respondentReceipt({ persona_source: "fictional_roster", steps: [fieldwork("SOMETHING_NEW")] })).toEqual({ pinned: "fictional_roster", observed: "UNKNOWN", origin: "SOMETHING_NEW", mismatch: true });
  });
});

describe("fidelityRefusal (PC2)", () => {
  const q = (evidence: unknown) => ({ typ: "vyber", support_status: "REPORTABLE", n_platnych: 1, n_unique_layer_donors: 1, effective_n: 1, evidence }) as unknown as Parameters<typeof fidelityRefusal>[0];
  it("reads the rating the aggregate stored: REFUSE with its reason, nothing for any other or none", () => {
    expect(fidelityRefusal(q({ mode: "REFUSE", rating: "RED", reason: "Absolutní WTP." }))).toBe("Absolutní WTP.");
    expect(fidelityRefusal(q({ mode: "REFUSE" }))).toBe("");
    expect(fidelityRefusal(q({ mode: "JUST_SHOW", reason: "x" }))).toBeNull();
    expect(fidelityRefusal(q(undefined))).toBeNull();
    expect(fidelityRefusal(q("REFUSE"))).toBeNull();
  });
});
