"use client";
// Analýza §3 "Blokované nároky" (artifact-analysis ANL4): every analysis module the evidence gate stored
// BLOCKED, what it refused in words, and the way out the server says it has. Reads the stored outcomes and
// the retryable list; judges nothing again.
import Link from "next/link";
import { t } from "@/i18n/t";
import type { ResearchAnalysis, ResearchRun } from "@/lib/api";
import { blockedModules, wayOut, type BlockedReason, type WayOut } from "@/lib/analysis-blocked";
import { codeWords } from "@/lib/reason-words";
import { stepLabel } from "@/lib/research-execution";
import { CodedWords } from "./CodedWords";
import { useFrame } from "./frame-hook";

const WAY_OUT: Record<WayOut, string> = {
  retry: "Nové kolo nad stejnými daty ji může opravit; spouští se u běhu na stránce Průběh.",
  same_data_fails: "Nové kolo nad stejnými daty ji neopraví: kontrola ji odmítla dřív, než se zeptala modelu, a stejná data odmítne znovu.",
  run_unfinished: "Běh ještě neskončil; o novém kole lze rozhodnout, až doběhne.",
  unknown: "Zjišťuje se, zda ji nové kolo nad stejnými daty může opravit.",
};

/** A blocked module's refusals: each reason once, in words, with each subject and its detail under the fold. */
export function ViolationList({ reasons }: { reasons: BlockedReason[] }) {
  if (!reasons.length) return <p className="text-sm text-ink-muted">Kontrola neuvedla důvod. Proč ji část nesplnila, nelze říct.</p>;
  return (
    <ul className="flex flex-col gap-2 text-sm">
      {reasons.map((r) => (
        <li key={r.code} data-violation={r.code}>
          <CodedWords inline coded={codeWords("research.exec.violation", r.code)} />
          {r.items.length > 1 ? <span className="text-ink-muted"> ({r.items.length}×)</span> : null}
          <details className="mt-1 text-xs text-ink-muted"><summary className="cursor-pointer">Technické podrobnosti</summary>
            <ul className="mt-1 list-disc pl-5">{r.items.map((i) => <li key={`${i.subject}\u0000${i.detail}`} className="break-words"><code>{i.subject}</code>{i.detail ? `: ${i.detail}` : ""}</li>)}</ul>
          </details>
        </li>
      ))}
    </ul>
  );
}

export function AnalysisBlocked({ analysis, run, retryable, progressHref }: {
  analysis: ResearchAnalysis | null;
  run: ResearchRun;
  /** The server's retryable modules for this run; null while unread. */
  retryable: readonly string[] | null;
  progressHref: string | null;
}) {
  const frame = useFrame();
  const rows = blockedModules(analysis);
  if (!rows.length) return null;
  // Where the round is not this person's to ask (a read-only frame, no Průběh), no way out is offered.
  const canAct = frame.canEdit && !!progressHref;
  return (
    <section aria-labelledby="analysis-blocked-title" data-analysis-blocked className="rounded-md border border-status-fault/40 bg-status-fault-wash p-4">
      <h3 id="analysis-blocked-title" className="text-base font-semibold">Blokované nároky</h3>
      <p className="mt-1 text-sm leading-6">Text těchto částí se nesmí číst jako zjištění a do zprávy nevstoupí.</p>
      <ul className="mt-3 flex flex-col gap-3">
        {rows.map(({ module, reasons }) => {
          const way = wayOut(module, run.is_terminal, retryable);
          return (
            <li key={module} data-blocked-module={module} data-way-out={canAct ? way : undefined} className="rounded-md border border-border bg-surface-raised p-3">
              <p className="mb-2 text-sm font-semibold">{stepLabel(`analysis_${module}`)} <span className="font-normal text-status-fault">· {t("research.exec.stepStatus.ANALYSIS_BLOCKED")}</span></p>
              <ViolationList reasons={reasons} />
              {canAct ? <p className="mt-2 text-sm">{WAY_OUT[way]}</p> : null}
            </li>
          );
        })}
      </ul>
      {canAct && progressHref ? <Link className="mt-3 inline-block text-sm underline" href={progressHref}>{t("research.exec.results.reportSeeProgress")}</Link> : null}
    </section>
  );
}
