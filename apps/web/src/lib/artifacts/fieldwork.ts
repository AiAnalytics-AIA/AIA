// Sběr dat's contract as data (artifact-fieldwork FLD1): its row of the Lead's registry
// (workbench-artifacts.ts), and the ids its screen puts on what the Lead may name. A run's step is
// `step:<node_key>` (the key survives a retry; the step id does not), the respondents receipt
// `receipt:respondents`. Pure.
import { aiaId, ARTIFACTS, parseAiaId, type ArtifactContract } from "@/lib/workbench-artifacts";

export const FIELDWORK: ArtifactContract = ARTIFACTS.fieldwork;

export type FieldworkTarget = { kind: "step"; nodeKey: string } | { kind: "receipt" };

/** "Kdo odpovídal", the receipt the report's method chapter reads. */
export const RECEIPT_TARGET = aiaId("receipt", "respondents");

/** A step's `data-aia` id, or null when its key falls outside the id grammar: the step is left
 *  unnamed, never rewritten into another id and never a render error. */
export function stepTarget(nodeKey: string): string | null {
  try {
    return aiaId("step", nodeKey);
  } catch {
    return null;
  }
}

/** A `data-aia` id read back as a Sběr dat target; null for anything else. */
export function readFieldworkTarget(value: string): FieldworkTarget | null {
  const parsed = parseAiaId(value);
  if (!parsed || parsed.stage !== "fieldwork") return null;
  if (parsed.kind === "step") return { kind: "step", nodeKey: parsed.id };
  return parsed.kind === "receipt" && parsed.id === "respondents" ? { kind: "receipt" } : null;
}
