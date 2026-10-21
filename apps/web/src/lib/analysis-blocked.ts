// Analýza §3 "Blokované nároky" (artifact-analysis ANL4): every analysis module the evidence gate
// stored BLOCKED, with what it refused grouped by reason, in module order. Pure: it reads the stored
// outcomes and judges nothing again; a module not yet stored is pending, never blocked.
import type { ResearchAnalysis } from "@/lib/api";
import { ANALYSIS_ORDER } from "@/lib/research-execution";

/** One reason the gate refused, with every subject it named (a field, a claim, a question) and its details. */
export type BlockedReason = { code: string; subjects: string[]; details: string[] };
export type BlockedModule = { module: (typeof ANALYSIS_ORDER)[number]; reasons: BlockedReason[] };

export function blockedModules(analysis: ResearchAnalysis | null): BlockedModule[] {
  if (!analysis) return [];
  return ANALYSIS_ORDER.flatMap((module) => {
    const outcome = analysis.modules[module];
    if (outcome?.outcome !== "BLOCKED") return [];
    const reasons: BlockedReason[] = [];
    for (const v of outcome.violations) {
      let reason = reasons.find((r) => r.code === v.code);
      if (!reason) reasons.push((reason = { code: v.code, subjects: [], details: [] }));
      if (v.subject && !reason.subjects.includes(v.subject)) reason.subjects.push(v.subject);
      if (v.detail && !reason.details.includes(v.detail)) reason.details.push(v.detail);
    }
    return [{ module, reasons }];
  });
}
