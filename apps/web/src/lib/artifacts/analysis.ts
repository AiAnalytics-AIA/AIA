// Analýza's contract as data (artifact-analysis ANL1): its row of the Lead's registry
// (workbench-artifacts.ts), and the ids its screen puts on what the Lead may name. A module is
// `module:<kind>`, a finding `finding:<module>:<n>` (its place in the module's key findings, fixed
// because a run's modules are frozen) and a claim `claim:<module>:<claim_id>` (a claim id is unique
// only within its module). No research question is named here: `rq:<id>` belongs to the design row
// and waits for stable ids (WCE1). Pure.
import { aiaId, ARTIFACTS, parseAiaId, type ArtifactContract } from "@/lib/workbench-artifacts";
import { ANALYSIS_ORDER } from "@/lib/research-execution";

export const ANALYSIS: ArtifactContract = ARTIFACTS.analysis;

export type AnalysisModuleKind = (typeof ANALYSIS_ORDER)[number];

export type AnalysisTarget =
  | { kind: "module"; module: AnalysisModuleKind }
  | { kind: "finding"; module: AnalysisModuleKind; index: number }
  | { kind: "claim"; module: AnalysisModuleKind; claimId: string };

const isModule = (value: string): value is AnalysisModuleKind => (ANALYSIS_ORDER as readonly string[]).includes(value);

/** The `data-aia` id of a target, or null when its parts fall outside the id grammar (a stored
 *  claim id this grammar cannot carry is left unnamed, never rewritten into another id). */
export function analysisTarget(target: AnalysisTarget): string | null {
  const id = target.kind === "module" ? target.module
    : target.kind === "finding" ? `${target.module}:${target.index}`
    : `${target.module}:${target.claimId}`;
  try {
    return aiaId(target.kind, id);
  } catch {
    return null;
  }
}

/** A `data-aia` id read back as an Analýza target; null for anything else, or a module this run
 *  does not have. */
export function readAnalysisTarget(value: string): AnalysisTarget | null {
  const parsed = parseAiaId(value);
  if (!parsed || parsed.stage !== "analysis") return null;
  const [module, ...rest] = parsed.id.split(":");
  if (!isModule(module)) return null;
  if (parsed.kind === "module") return rest.length ? null : { kind: "module", module };
  if (parsed.kind === "finding") {
    return rest.length === 1 && /^(0|[1-9]\d*)$/.test(rest[0]) ? { kind: "finding", module, index: Number(rest[0]) } : null;
  }
  if (parsed.kind === "claim") return rest.length ? { kind: "claim", module, claimId: rest.join(":") } : null;
  return null;
}

/** The targets the inspector opens (V2's `C.visual.inspect`): a finding or a claim, never a module. */
export const inspectable = (target: AnalysisTarget): boolean => target.kind !== "module";
