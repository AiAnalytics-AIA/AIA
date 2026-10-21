"use client";
// Analýza's inspector body (artifact-analysis ANL3): a finding or a claim opened in the drawer,
// down to the measure on Výsledky. The frame draws the drawer, its title and its back stack and
// passes the target alone; the analysis it reads is the one the page shows, published by
// AnalysisResults (shownAnalysis), so the drawer can never open another run's item. Display only.
import { useSyncExternalStore, type ReactNode } from "react";
import { t } from "@/i18n/t";
import type { ResearchAnalysis } from "@/lib/api";
import { inspectView, numberWords, type CitedNumber } from "@/lib/analysis-inspect";
import { readAnalysisTarget } from "@/lib/artifacts/analysis";
import type { CompiledSpecification } from "@/lib/result-reading";
import { CodedWords } from "./CodedWords";
import { FormattedText } from "./FormattedText";

type Shown = { runId: string; analysis: ResearchAnalysis; spec: CompiledSpecification | null } | null;

let shown: Shown = null;
const listeners = new Set<() => void>();

/** The analysis the page shows now; AnalysisResults sets it when it reads one and clears it when it leaves. */
export function setShownAnalysis(next: Shown): void {
  if (next === shown) return;
  shown = next;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function CitedLine({ n }: { n: CitedNumber }) {
  const words = numberWords(n);
  return (
    <li data-aia={n.target ?? undefined} className="rounded-control border border-border bg-surface-sunken px-2.5 py-1 text-xs leading-5">
      {n.href && n.measure
        ? <a href={n.href} className="no-underline hover:underline"><span className="font-semibold tabular-nums">{words}</span> · {n.measure.title}</a>
        : <span><span className="font-semibold tabular-nums">{words}</span> <CodedWords inline coded={{ words: t("research.exec.untitled.cited"), code: n.claim.evidence_ref }} /></span>}
      {n.claim.indicative ? <span className="text-status-you-ink"> · orientační</span> : null}
    </li>
  );
}

export function AnalysisInspect({ target }: { target: { kind: "module" | "finding" | "claim"; id: string } }): ReactNode {
  const current = useSyncExternalStore(subscribe, () => shown, () => null);
  const read = readAnalysisTarget(`${target.kind}:${target.id}`);
  if (!read) return <p className="text-sm text-ink-muted">Tuto položku Analýza nezná.</p>;
  if (!current) return <p className="text-sm text-ink-muted">Analýza běhu se načítá.</p>;
  const view = inspectView(read, current.analysis, current.spec);
  if (view.kind === "missing") return <p data-inspect="missing" className="text-sm text-ink-muted">{view.why}</p>;
  if (view.kind === "finding") {
    return (
      <div data-inspect="finding" className="flex flex-col gap-3 text-sm">
        <FormattedText text={view.text} />
        <p className="text-xs text-ink-muted">Zjištění napsala AI analýza z připuštěných čísel tohoto běhu; čeká na posouzení výzkumníkem.</p>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Čísla, o která se opírá</h4>
        {view.numbers.length ? <ul className="flex flex-col gap-2">{view.numbers.map((n) => <CitedLine key={n.claim.claim_id} n={n} />)}</ul> : <p className="text-ink-muted">Necituje žádné připuštěné číslo.</p>}
        {view.unresolved.length ? <p className="text-xs text-ink-muted">Odkazuje i na čísla, která modul neuložil: {view.unresolved.map((id) => <code key={id} className="mr-1">{id}</code>)}</p> : null}
      </div>
    );
  }
  return (
    <div data-inspect="claim" className="flex flex-col gap-3 text-sm">
      <ul><CitedLine n={view.number} /></ul>
      <p className="text-xs text-ink-muted">Připuštěné číslo běhu {current.runId}. Odkaz: <code>{view.number.claim.evidence_ref}</code></p>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Kde ho analýza cituje</h4>
      {view.citedBy.length ? (
        <ul className="flex flex-col gap-2">
          {view.citedBy.map((c, i) => (
            <li key={i} data-aia={c.kind === "finding" ? c.target ?? undefined : undefined} className="border-l-2 border-signal pl-3">
              {c.kind === "answer" ? <p className="text-xs font-medium">{c.question}</p> : <p className="text-xs font-medium">Zjištění {c.index + 1}</p>}
              <FormattedText text={c.text} />
            </li>
          ))}
        </ul>
      ) : <p className="text-ink-muted">Žádná věta modulu ho necituje.</p>}
    </div>
  );
}
