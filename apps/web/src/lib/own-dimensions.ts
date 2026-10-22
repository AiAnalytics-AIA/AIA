// Vlastní dimenze klienta on Dimenze (artifact-dimensions DIM4): a study's materialize runs read in
// words. A child's outcome is read only when the run recorded one; otherwise it is unknown, never
// read as met.

import { t, tv } from "@/i18n/t";
import type { Materialization } from "@/lib/api";
import { type TargetVerdict, outcomeValue } from "@/lib/population";
import { type Coded, codeWords, known } from "@/lib/reason-words";

export type OwnDimension = {
  name: string;
  status: Coded;
  /** Why it waits or why it failed; null when nothing was recorded. */
  reason: Coded | null;
  /** The target beside what was achieved, and the verdict; null while the step has not succeeded. */
  outcome: { words: string; verdict: TargetVerdict } | null;
};

const RUN_ENDED = new Set(["COMPLETED", "FAILED", "CANCELLED"]);
const STEP_ENDED = new Set(["SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED"]);

/** A reason the materialize step records, in words: its own first, then a step's waiting reasons. */
function reasonWords(code: string): Coded {
  const own = known(`research.persona.own.reason.${code}`);
  return own === null ? codeWords("research.exec.wait", code) : { words: own, code: null };
}

export function ownDimension(m: Materialization): OwnDimension {
  // A step that had not finished when its run ended will not run (the run list's WILL_NOT_RUN).
  const step = m.step_status && RUN_ENDED.has(m.status) && !STEP_ENDED.has(m.step_status) ? "WILL_NOT_RUN" : (m.step_status ?? m.status);
  const code = m.waiting_reason ?? m.refusal_reason;
  const outcome =
    m.child && m.kind
      ? {
          words: tv("aia.intelligence.population.children.outcome", { target: outcomeValue(m.kind, m.child.target), achieved: outcomeValue(m.kind, m.child.achieved) }),
          verdict: m.child.target_met ? ("met" as const) : ("unmet" as const),
        }
      : step === "SUCCEEDED"
        ? { words: t("research.persona.own.noOutcome"), verdict: "unknown" as const }
        : null;
  return {
    name: m.dimension_id ?? m.child?.label ?? m.run_id,
    status: codeWords("research.exec.stepStatus", step),
    reason: code ? reasonWords(code) : null,
    outcome,
  };
}
