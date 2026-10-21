"use client";
// Analýza §3 "Blokované nároky" (artifact-analysis ANL4): every analysis module the evidence gate stored
// BLOCKED, what it refused in words with the subjects it named, and the way out. A blocked module's
// output is never read or used in the report; the screen says why and where it is repaired. Reads the
// stored outcomes; judges nothing again.
import Link from "next/link";
import { t } from "@/i18n/t";
import type { ResearchAnalysis } from "@/lib/api";
import { blockedModules } from "@/lib/analysis-blocked";
import { codeWords } from "@/lib/reason-words";
import { stepLabel } from "@/lib/research-execution";
import { AskLead, useLeadOwnsAiStarts } from "./AskLead";
import { CodedWords } from "./CodedWords";

export function AnalysisBlocked({ analysis, progressHref }: { analysis: ResearchAnalysis | null; progressHref: string | null }) {
  const leadOwnsAiStarts = useLeadOwnsAiStarts();
  const rows = blockedModules(analysis);
  if (!rows.length) return null;
  return (
    <section aria-labelledby="analysis-blocked-title" data-analysis-blocked className="rounded-md border border-status-fault/40 bg-status-fault-wash p-4">
      <h3 id="analysis-blocked-title" className="text-base font-semibold">Blokované nároky</h3>
      <p className="mt-1 text-sm leading-6">
        Tyto části analýzy neprošly kontrolou evidence. Jejich text se nesmí číst jako zjištění a do zprávy nevstoupí; zpráva vznikne, až budou všechny části v pořádku.
      </p>
      <ul className="mt-3 flex flex-col gap-3">
        {rows.map(({ module, reasons }) => (
          <li key={module} data-blocked-module={module} className="rounded-md border border-border bg-surface-raised p-3">
            <p className="text-sm font-semibold">{stepLabel(`analysis_${module}`)} <span className="font-normal text-status-fault">· {t("research.exec.stepStatus.ANALYSIS_BLOCKED")}</span></p>
            {reasons.length ? (
              <ul className="mt-2 flex flex-col gap-2 text-sm">
                {reasons.map((r) => (
                  <li key={r.code} data-violation={r.code}>
                    <CodedWords inline coded={codeWords("research.exec.violation", r.code)} />
                    {r.subjects.length ? <span className="text-ink-muted"> · týká se: {r.subjects.map((s) => <code key={s} className="mr-1 text-xs">{s}</code>)}</span> : null}
                    {r.details.length ? (
                      <details className="mt-1 text-xs text-ink-muted"><summary className="cursor-pointer">Technické podrobnosti</summary>
                        <ul className="mt-1 list-disc pl-5">{r.details.map((d) => <li key={d} className="break-words">{d}</li>)}</ul>
                      </details>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : <p className="mt-2 text-sm text-ink-muted">Kontrola neuvedla důvod. Proč ji část nesplnila, nelze říct.</p>}
          </li>
        ))}
      </ul>
      <div className="mt-3 text-sm">
        <p className="font-medium">Jak dál</p>
        {leadOwnsAiStarts
          ? <AskLead what="Nové kolo analýzy nad stejnými daty" className="mt-1" />
          : <p className="mt-1 text-ink-muted">Nové kolo nad stejnými daty se spouští u běhu na stránce Průběh; části, které kontrolu splnily, se nepočítají znovu.</p>}
        {progressHref ? <Link className="mt-1 inline-block underline" href={progressHref}>{t("research.exec.results.reportSeeProgress")}</Link> : null}
      </div>
    </section>
  );
}
