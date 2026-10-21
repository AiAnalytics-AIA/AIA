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

type AnalysisModules = Readonly<Record<string, {
  outcome: string;
  key_findings: readonly { claim_ids: readonly string[] }[];
  research_question_answers: readonly { claim_ids: readonly string[] }[];
}>>;

/** Where a cited-number chip is drawn on Analýza: in a key finding of the cross-module list, or in
 *  the selected module's own answers or findings. */
export type ChipPlace = { list: "key" | "answer" | "finding"; module: string; index: number };

export const chipKey = (place: ChipPlace, claimId: string): string => `${place.list}:${place.module}:${place.index}:${claimId}`;

/**
 * Which chips carry their claim's target: the first one in the page's order, so a target names one
 * element whatever cites it twice (the cross-module list first, then the selected module's answers,
 * then its findings, which repeat the list's). A completed module only; a blocked one shows no chips.
 */
export function claimMarks(modules: AnalysisModules, selected: AnalysisModuleKind): Set<string> {
  const marked = new Set<string>();
  const seen = new Set<string>();
  const visit = (place: ChipPlace, ids: readonly string[]) => {
    for (const id of ids) {
      const target = `${place.module}:${id}`;
      if (seen.has(target)) continue;
      seen.add(target);
      marked.add(chipKey(place, id));
    }
  };
  for (const kind of ANALYSIS_ORDER) {
    const outcome = modules[kind];
    if (outcome?.outcome !== "COMPLETED") continue;
    outcome.key_findings.forEach((f, index) => visit({ list: "key", module: kind, index }, f.claim_ids));
  }
  const own = modules[selected];
  if (own?.outcome === "COMPLETED") {
    own.research_question_answers.forEach((a, index) => visit({ list: "answer", module: selected, index }, a.claim_ids));
    own.key_findings.forEach((f, index) => visit({ list: "finding", module: selected, index }, f.claim_ids));
  }
  return marked;
}
