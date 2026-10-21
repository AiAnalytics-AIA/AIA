// What Analýza's inspector shows for a finding or a claim (artifact-analysis ANL3): a finding with
// every number it cites, each resolved to its measure on Výsledky, and a claim with the measure it
// is and every sentence of its module that cites it. Pure: it reads the run's stored analysis and
// specification, and a target this run does not hold reads as missing, never as something else.
import type { ResearchAnalysis } from "@/lib/api";
import { analysisTarget, type AnalysisModuleKind, type AnalysisTarget } from "@/lib/artifacts/analysis";
import { stepLabel } from "@/lib/research-execution";
import { citedMeasure, measureAnchor, type CitedMeasure, type CompiledSpecification } from "@/lib/result-reading";

type Module = ResearchAnalysis["modules"][string];
type Claim = Module["claims"][number];

/** One number a sentence cites: the stored claim, its target, and its measure (null: the reference
 *  names no measure of this run's specification; its code is then shown as written). */
export type CitedNumber = { claim: Claim; target: string | null; measure: CitedMeasure | null; href: string | null };

/** A sentence of the module that cites a claim: a key finding or an answer to a research question. */
export type Citation = { kind: "finding"; index: number; text: string; target: string | null } | { kind: "answer"; question: string; text: string };

export type InspectView =
  | { kind: "finding"; title: string; module: string; text: string; numbers: CitedNumber[]; unresolved: string[] }
  | { kind: "claim"; title: string; module: string; number: CitedNumber; citedBy: Citation[] }
  | { kind: "missing"; title: string; why: string };

function cited(claim: Claim, module: AnalysisModuleKind, spec: CompiledSpecification | null): CitedNumber {
  const measure = citedMeasure(claim.evidence_ref, spec);
  return {
    claim,
    target: analysisTarget({ kind: "claim", module, claimId: claim.claim_id }),
    measure,
    href: measure ? `#${measureAnchor(measure.measureId)}` : null,
  };
}

/** A claim's value as printed: with its measure's unit when known, else the bare number. */
export function numberWords(n: CitedNumber): string {
  return n.measure ? `${n.measure.format(n.claim.value, n.claim.decimals)} ${n.measure.what}` : n.claim.value.toLocaleString("cs-CZ");
}

/** What the inspector shows for `target` in `analysis` (a module target is not inspected). */
export function inspectView(target: AnalysisTarget, analysis: ResearchAnalysis | null, spec: CompiledSpecification | null): InspectView {
  const label = stepLabel(`analysis_${target.module}`);
  const outcome = analysis?.modules[target.module];
  if (target.kind === "module") return { kind: "missing", title: label, why: "Modul se otevírá na stránce, ne v inspektoru." };
  if (!outcome) return { kind: "missing", title: label, why: "Tato část analýzy zatím není uložená." };
  if (outcome.outcome === "BLOCKED") return { kind: "missing", title: label, why: "Tato část analýzy neprošla kontrolou; její výstup se nesmí číst ani použít ve zprávě." };
  if (target.kind === "finding") {
    const finding = outcome.key_findings[target.index];
    if (!finding) return { kind: "missing", title: label, why: "Toto zjištění v uloženém běhu není." };
    const byId = new Map(outcome.claims.map((c) => [c.claim_id, c]));
    return {
      kind: "finding",
      title: `${label} · zjištění ${target.index + 1}`,
      module: target.module,
      text: finding.text,
      numbers: finding.claim_ids.flatMap((id) => (byId.has(id) ? [cited(byId.get(id) as Claim, target.module, spec)] : [])),
      unresolved: finding.claim_ids.filter((id) => !byId.has(id)),
    };
  }
  const claim = outcome.claims.find((c) => c.claim_id === target.claimId);
  if (!claim) return { kind: "missing", title: label, why: "Toto číslo v uloženém běhu není." };
  const citedBy: Citation[] = [
    ...outcome.key_findings.flatMap((f, index) => (f.claim_ids.includes(claim.claim_id)
      ? [{ kind: "finding" as const, index, text: f.text, target: analysisTarget({ kind: "finding", module: target.module, index }) }] : [])),
    ...outcome.research_question_answers.flatMap((a) => (a.claim_ids.includes(claim.claim_id)
      ? [{ kind: "answer" as const, question: a.question, text: a.answer }] : [])),
  ];
  const number = cited(claim, target.module, spec);
  return { kind: "claim", title: `${label} · ${numberWords(number)}`, module: target.module, number, citedBy };
}
