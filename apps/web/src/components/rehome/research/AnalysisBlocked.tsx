"use client";
// Analýza §3 "Blokované nároky" (artifact-analysis ANL4): every analysis module the evidence gate stored
// BLOCKED, what it refused in words, and the way out the server says it has. Reads the stored outcomes and
// the retryable list; judges nothing again.
import Link from "next/link";
import { useEffect, useState } from "react";
import { t } from "@/i18n/t";
import { lead, type ResearchAnalysis, type ResearchRun } from "@/lib/api";
import { blockedModules, unsupportedModules, wayOut, type BlockedReason, type Unsupported, type WayOut } from "@/lib/analysis-blocked";
import { codeWords } from "@/lib/reason-words";
import { stepLabel } from "@/lib/research-execution";
import { Button } from "../ui";
import { useAskLead, useLeadOwnsAiStarts } from "./AskLead";
import { CodedWords } from "./CodedWords";
import { useFrame } from "./frame-hook";

/** The person's typed retry (domain/lead_commands.py ANALYSIS_RETRY): the Lead answers it with their own card. */
const RETRY_COMMAND = "Zopakuj analýzu";

/** In the workbench a same-data round is asked of the Lead, never started from Průběh (ANL4, spec szz A5). */
const RETRY_WITH_LEAD = "Nové kolo nad stejnými daty ji může opravit: zopakování připraví Vedoucí výzkumu na vaší kartě.";

const UNSUPPORTED: Record<Unsupported["reason"], string> = {
  no_supported_finding: "Měla z čeho vyvodit zjištění, ale žádné doložené připuštěným číslem neuvádí. Zpráva na ni čeká.",
  context_missing: "Běh pro ni neměl podklady, proto nic neuvádí. Zprávu nedrží.",
};


const WAY_OUT: Record<WayOut, string> = {
  retry: "Nové kolo nad stejnými daty ji může opravit; spouští se u běhu na stránce Průběh.",
  same_data_fails: "Nové kolo nad stejnými daty ji neopraví: kontrola ji odmítla dřív, než se zeptala modelu, a stejná data odmítne znovu.",
  run_unfinished: "Běh ještě neskončil; o novém kole lze rozhodnout, až doběhne.",
  unknown: "Zda ji nové kolo nad stejnými daty může opravit, nelze zatím říct.",
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
  const ask = useAskLead();
  const leadOwns = useLeadOwnsAiStarts();
  const rows = blockedModules(analysis);
  const unsupported = unsupportedModules(analysis);
  // The typed "Zopakuj analýzu" retries the study's newest analysed run (lead_chat_start.py), so the Lead is
  // asked only on that run; on any other, the round is asked where the run is followed, on Průběh.
  const [newest, setNewest] = useState<{ key: string; runId: string | null } | null>(null);
  const withAsk = frame.canEdit && leadOwns && !!ask && (rows.length > 0 || unsupported.length > 0);
  useEffect(() => {
    if (!withAsk) return;
    let live = true;
    lead.state(frame.studyId).then(
      (state) => { if (live) setNewest({ key: frame.studyId, runId: state.analysis_retry_run?.run_id ?? null }); },
      () => { if (live) setNewest({ key: frame.studyId, runId: null }); },
    );
    return () => { live = false; };
  }, [withAsk, frame.studyId]);
  if (!rows.length && !unsupported.length) return null;
  // Where the round is not this person's to ask (a read-only frame, no Průběh), no way out is offered.
  const canAct = frame.canEdit && !!progressHref;
  // In the workbench, on the run the typed command retries, the round is the Lead's to prepare: one button.
  const withLead = withAsk && newest?.key === frame.studyId && newest.runId === run.run_id;
  const ways = rows.map(({ module }) => wayOut(module, run.is_terminal, retryable));
  // A same-data round is offered only where the server would take it: an ended run that lists the module.
  const sameData = (module: string) => run.is_terminal && !!retryable?.includes(module);
  const shown = (u: Unsupported) => u.resolutions.filter((r) => r !== "same_data_retry" || sameData(u.module));
  const retry = withLead && (ways.includes("retry") || unsupported.some((u) => u.resolutions.includes("same_data_retry") && sameData(u.module)));
  // Průběh stays the way whenever the Lead's button does not cover every round asked for.
  const progressLink = canAct && progressHref && (!retry || ways.includes("run_unfinished"))
    ? <Link className="mt-3 inline-block text-sm underline" href={progressHref}>{t("research.exec.results.reportSeeProgress")}</Link>
    : null;
  return (
    <div data-analysis-ways-out className="flex flex-col gap-3">
      {rows.length ? (
        <section aria-labelledby="analysis-blocked-title" data-analysis-blocked className="rounded-md border border-status-fault/40 bg-status-fault-wash p-4">
          <h3 id="analysis-blocked-title" className="text-base font-semibold">Blokované nároky</h3>
          <p className="mt-1 text-sm leading-6">Text těchto částí se nesmí číst jako zjištění a do zprávy nevstoupí.</p>
          <ul className="mt-3 flex flex-col gap-3">
            {rows.map(({ module, reasons }, i) => (
              <li key={module} data-blocked-module={module} data-way-out={canAct || withLead ? ways[i] : undefined} className="rounded-md border border-border bg-surface-raised p-3">
                <p className="mb-2 text-sm font-semibold">{stepLabel(`analysis_${module}`)} <span className="font-normal text-status-fault">· {t("research.exec.stepStatus.ANALYSIS_BLOCKED")}</span></p>
                <ViolationList reasons={reasons} />
                {canAct || withLead ? <p className="mt-2 text-sm">{withLead && ways[i] === "retry" ? RETRY_WITH_LEAD : WAY_OUT[ways[i]]}</p> : null}
              </li>
            ))}
          </ul>
          {progressLink}
        </section>
      ) : null}
      {unsupported.length ? (
        <section aria-labelledby="analysis-unsupported-title" data-analysis-unsupported className="rounded-md border border-border bg-surface-raised p-4">
          <h3 id="analysis-unsupported-title" className="text-base font-semibold">Bez doloženého zjištění</h3>
          <ul className="mt-2 flex flex-col gap-3">
            {unsupported.map((u) => (
              <li key={u.module} data-unsupported-module={u.module} data-reason={u.reason} className="text-sm">
                <p className="font-semibold">{stepLabel(`analysis_${u.module}`)}</p>
                <p className="mt-0.5 leading-6">{UNSUPPORTED[u.reason]}</p>
                {frame.canEdit && shown(u).length ? <p className="mt-0.5 text-ink-muted">Co s tím: {shown(u).map((r, i) => <span key={r}>{i ? ", nebo " : ""}<CodedWords inline coded={codeWords("research.exec.resolution", r)} /></span>)}.</p> : null}
              </li>
            ))}
          </ul>
          {rows.length ? null : progressLink}
        </section>
      ) : null}
      {retry ? <div><Button onClick={() => ask?.(RETRY_COMMAND)}>Opakovat analýzu</Button></div> : null}
    </div>
  );
}
