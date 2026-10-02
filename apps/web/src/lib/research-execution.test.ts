// How a research run and its results read (ADR 0016): the rules the three
// execution stages share, without React.
import { describe, expect, it } from "vitest";

import type { ResearchRun, ResearchStep } from "@/lib/api";
import { isSynthetic, parkedForRuntime, phaseTone, resultTable, shouldPoll, stepLabel, supportNote, waitingDetail } from "./research-execution";

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
    expect(shown.rows).toEqual([{ label: "A", value: "55,2 %", interval: "40,0–70,0" }]);
    expect(supportNote(shown)).toMatch(/Indikativní/);
  });

  it("labels AI respondents on fictional personas as synthetic, like the fixture", () => {
    const step = (origin: string | null) => ({ node_key: "run", data_origin: origin }) as ResearchRun["steps"][number];
    expect(isSynthetic(run({ fieldwork_source: "synthetic_fixture" }))).toBe(true);
    expect(isSynthetic(run({ steps: [step("SYNTHETIC_AI_FICTIONAL")] }))).toBe(true);
    expect(isSynthetic(run({ steps: [step(null)] }))).toBe(false);
    expect(isSynthetic(run({ steps: [step("SOMETHING_ELSE")] }))).toBe(false);
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
