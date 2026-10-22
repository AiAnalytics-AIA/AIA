"use client";
// Analýza's inspector body (artifact-analysis ANL3): a finding or a claim opened in the drawer,
// down to the measure on Výsledky. The frame draws the drawer, its title and its back stack and
// passes the target alone; the analysis it reads is the one the page shows, published by
// AnalysisResults (shownAnalysis), so the drawer can never open another run's item. Display only, and
// it carries no Lead target: each target names one element, which is on the page (claimMarks).
import { useMemo, useSyncExternalStore, type ReactNode } from "react";
import { useItemInspector } from "@/components/workbench/item-inspector-context";
import { t } from "@/i18n/t";
import type { ResearchAnalysis } from "@/lib/api";
import { inspectView, numberWords, type CitedNumber } from "@/lib/analysis-inspect";
import { readAnalysisTarget } from "@/lib/artifacts/analysis";
import { stepLabel } from "@/lib/research-execution";
import { Icon } from "../icons";
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

/** Opens an Analýza finding or claim, by its target id, in the workbench's item inspector; true
 *  when it opened (an id outside the grammar opens nothing). Null outside the workbench, where
 *  there is no drawer and the page keeps its own behaviour. */
export type OpenAnalysisItem = (id: string | null, title: string) => boolean;

export function useOpenAnalysisItem(): OpenAnalysisItem | null {
  const inspector = useItemInspector();
  return useMemo(
    () => (inspector ? (id, title) => id !== null && inspector.open({ id, title, sub: "Analýza" }) : null),
    [inspector],
  );
}

/** A key finding as the inspector opens it: its target id (null outside the grammar) and its title.
 *  One builder for the coverage chip and the finding's own button. */
export function findingItem(module: string, index: number): { id: string | null; title: string } {
  const id = `finding:${module}:${index}`;
  return { id: readAnalysisTarget(id) ? id : null, title: `${stepLabel(`analysis_${module}`)} · zjištění ${index + 1}` };
}

/** A key finding's own way into the inspector; nothing where there is none, or its id is outside the grammar. */
export function FindingInspectButton({ open, module, index }: { open: OpenAnalysisItem | null; module: string; index: number }) {
  const { id, title } = findingItem(module, index);
  if (!open || !id) return null;
  return (
    <button type="button" data-inspect-finding aria-label={`Otevřít ${title} v inspektoru`} onClick={() => open(id, title)}
      className="shrink-0 rounded-control p-1 text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring">
      <Icon name="inspector" size={14} />
    </button>
  );
}

function CitedLine({ n }: { n: CitedNumber }) {
  const words = numberWords(n);
  return (
    <li className="rounded-control border border-border bg-surface-sunken px-2.5 py-1 text-xs leading-5">
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
        {/* Only a finding that cites an admitted number is said to rest on one (review of #692). */}
        <p className="text-xs text-ink-muted">{view.numbers.length
          ? "Zjištění napsala AI analýza z připuštěných čísel tohoto běhu; čeká na posouzení výzkumníkem."
          : "Zjištění napsala AI analýza a neopírá se o žádné připuštěné číslo tohoto běhu; čeká na posouzení výzkumníkem."}</p>
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
            <li key={i} className="border-l-2 border-signal pl-3">
              {c.kind === "answer" ? <p className="text-xs font-medium">{c.question}</p> : <p className="text-xs font-medium">Zjištění {c.index + 1}</p>}
              <FormattedText text={c.text} />
            </li>
          ))}
        </ul>
      ) : <p className="text-ink-muted">Žádná věta modulu ho necituje.</p>}
    </div>
  );
}
