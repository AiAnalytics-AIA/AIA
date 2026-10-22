import { describe, expect, it } from "vitest";

import type { Materialization } from "./api";
import { ownDimension } from "./own-dimensions";

const run = (over: Partial<Materialization>): Materialization => ({
  run_id: "RUN-1", status: "RUNNING", created_at: "2026-10-22T00:00:00Z", finished_at: null,
  dimension_id: "pije_kavu_rano", kind: "binary", step_status: "RUNNING", waiting_reason: null, refusal_reason: null, child: null, ...over,
});
const child = { version_id: "v17_4_0+c1", label: "Pije kávu ráno", target: 0.4, achieved: 0.396, target_met: true };

describe("a client's own dimension on Dimenze (artifact-dimensions DIM4)", () => {
  it("reads a finished child's target beside what it reached, in the kind's units", () => {
    const d = ownDimension(run({ status: "SUCCEEDED", step_status: "SUCCEEDED", child }));
    expect(d.name).toBe("pije_kavu_rano");
    expect(d.status).toEqual({ words: "Hotovo", code: null });
    expect(d.outcome).toEqual({ words: "cíl 40 %, dosaženo 39,6 %", verdict: "met" });
    expect(ownDimension(run({ kind: "scale_1_10", child: { ...child, target: 6.5, achieved: 6.2, target_met: false } })).outcome)
      .toEqual({ words: "cíl 6,50, dosaženo 6,20", verdict: "unmet" });
  });

  it("names a succeeded run without a readable outcome unknown, never met; a running one has none yet", () => {
    expect(ownDimension(run({ status: "COMPLETED", step_status: "SUCCEEDED", child: null })).outcome)
      .toEqual({ words: "Výsledek odvození není zaznamenaný.", verdict: "unknown" });
    expect(ownDimension(run({ child: null })).outcome).toBeNull();
  });

  it("a step its ended run never finished will not run, rather than reading as pending", () => {
    expect(ownDimension(run({ status: "CANCELLED", step_status: "RUNNABLE" })).status).toEqual({ words: "Nespustí se", code: null });
    expect(ownDimension(run({ status: "RUNNING", step_status: null })).status).toEqual({ words: "Běží", code: null });
  });

  it("says why a run waits or failed, keeping a code it has no words for", () => {
    expect(ownDimension(run({ step_status: "AWAITING_BUDGET", waiting_reason: "budget_exceeded" })).reason)
      .toEqual({ words: "Krok čeká, protože by překročil rozpočet studie.", code: null });
    const failed = ownDimension(run({ step_status: "FAILED", refusal_reason: "no_varying_predictor" }));
    expect(failed.status.words).toBe("Selhalo");
    expect(failed.reason).toEqual({ words: "Nepodařilo se: žádný z prediktorů se v populaci nemění, dimenzi nelze odvodit.", code: null });
    expect(ownDimension(run({ step_status: "FAILED", refusal_reason: "something_new" })).reason?.code).toBe("something_new");
  });
});
