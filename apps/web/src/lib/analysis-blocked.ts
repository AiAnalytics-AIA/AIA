// Analýza §3 "Blokované nároky" (artifact-analysis ANL4): every analysis module the evidence gate stored
// BLOCKED, with what it refused grouped by reason, in module order, and the way out each one has. Pure: it
// reads the stored outcomes and the server's retryable list, and judges nothing again; a module not yet
// stored is pending, never blocked.
import type { ResearchAnalysis } from "@/lib/api";
import { ANALYSIS_ORDER } from "@/lib/research-execution";

/** One reason the gate refused, with each subject it named (a claim, a field, a question) beside its detail. */
export type BlockedReason = { code: string; items: { subject: string; detail: string }[] };
export type BlockedModule = { module: (typeof ANALYSIS_ORDER)[number]; reasons: BlockedReason[] };

export function blockedModules(analysis: ResearchAnalysis | null): BlockedModule[] {
  if (!analysis) return [];
  return ANALYSIS_ORDER.flatMap((module) => {
    const outcome = analysis.modules[module];
    if (outcome?.outcome !== "BLOCKED") return [];
    const reasons: BlockedReason[] = [];
    for (const v of outcome.violations) {
      let reason = reasons.find((r) => r.code === v.code);
      if (!reason) reasons.push((reason = { code: v.code, items: [] }));
      if (!reason.items.some((i) => i.subject === v.subject && i.detail === v.detail)) reason.items.push({ subject: v.subject, detail: v.detail });
    }
    return [{ module, reasons }];
  });
}

/**
 * What a blocked module's way out is, as the server decides it (`GET …/analysis/retryable`):
 * - `retry`: a new round over the same data may pass (a model's drafts were refused);
 * - `same_data_fails`: the preflight refused it before any model turn, so the same data would refuse it again;
 * - `run_unfinished`: the run has not ended, so no round can be asked yet;
 * - `unknown`: the retryable list is unread or its read failed (never a promise either way).
 */
export type WayOut = "retry" | "same_data_fails" | "run_unfinished" | "unknown";

export function wayOut(module: string, runEnded: boolean, retryable: readonly string[] | null): WayOut {
  if (!runEnded) return "run_unfinished";
  if (retryable === null) return "unknown";
  return retryable.includes(module) ? "retry" : "same_data_fails";
}

/** A completed module that states no supported finding, as the server diagnosed it (evidence-integrity 9a). */
export type Unsupported = { module: (typeof ANALYSIS_ORDER)[number]; reason: "no_supported_finding" | "context_missing"; resolutions: string[] };

/** Every module the server diagnosed as stating nothing, in module order; a reason this client does not know is left out. */
export function unsupportedModules(analysis: ResearchAnalysis | null): Unsupported[] {
  if (!analysis) return [];
  return ANALYSIS_ORDER.flatMap((module) => {
    const d = analysis.modules[module]?.diagnostic;
    return d && (d.reason === "no_supported_finding" || d.reason === "context_missing")
      ? [{ module, reason: d.reason, resolutions: d.resolutions }]
      : [];
  });
}
