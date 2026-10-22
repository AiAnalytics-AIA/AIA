"use client";
// Externí kontext on Analýza (artifact-analysis ANL5): the Design Research findings the run pinned and
// every module was shown, each labelled as context, with its source; never a claim chip, never a number
// of this run (evidence-integrity 7).
import type { ResearchAnalysis } from "@/lib/api";
import { sourceChip } from "@/lib/analysis-external";

export function AnalysisExternal({ context }: { context: ResearchAnalysis["external_context"] }) {
  if (!context?.items.length) return null;
  return (
    <section aria-labelledby="external-context-title" data-external-context className="rounded-md border border-border bg-surface-raised p-4">
      <h3 id="external-context-title" className="text-base font-semibold">Externí kontext</h3>
      <p className="mt-1 text-sm leading-6 text-ink-muted">Zjištění z hloubkového výzkumu (Design Research), která analýza četla vedle dat tohoto běhu. Jsou to citace zdrojů, ne čísla tohoto běhu, a zjištění se o ně nemůže opírat.</p>
      <ul className="mt-3 flex flex-col gap-3">
        {context.items.map((item) => {
          const chip = sourceChip(item.source);
          return (
            <li key={item.evidence_id} data-external-item={item.evidence_id} className="border-l-2 border-border pl-3 text-sm">
              <span className="mr-2 rounded-control border border-border px-1.5 text-xs text-ink-muted">Externí kontext</span>
              {item.claim}
              <span className="mt-1 flex flex-wrap gap-1 text-xs">
                {chip.href
                  ? <a href={chip.href} target="_blank" rel="noopener noreferrer" data-source-chip className="rounded-control border border-border bg-surface-sunken px-1.5 no-underline hover:underline">{chip.label}</a>
                  : <span data-source-chip className="rounded-control border border-border bg-surface-sunken px-1.5">{chip.label}</span>}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
