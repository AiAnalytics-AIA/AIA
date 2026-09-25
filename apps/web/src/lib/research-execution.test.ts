// How a research run and its results read (ADR 0016): the rules the three
// execution stages share, without React.
import { describe, expect, it } from "vitest";

import type { ResearchRun } from "@/lib/api";
import { parkedForRuntime, phaseTone, resultTable, shouldPoll, stepLabel, supportNote } from "./research-execution";

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
});
