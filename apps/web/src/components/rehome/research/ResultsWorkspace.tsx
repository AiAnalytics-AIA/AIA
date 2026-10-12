"use client";

import { type KeyboardEvent, type ReactNode, useEffect, useId, useState } from "react";
import Link from "next/link";
import type { ResearchRun } from "@/lib/api";
import { phaseLabel } from "@/lib/research-execution";

export type ResultPanel = { id: string; label: string; description: string; content: ReactNode };

/** Views of the same frozen run. Hidden panels stay mounted so map cameras and review selections survive. */
export function ResultsWorkspace({ run, panels, progressHref, notice }: {
  /** The run's progress page; null where the page has none to link to (project memory). */
  run: ResearchRun; panels: ResultPanel[]; progressHref: string | null; notice: ReactNode;
}) {
  const [active, setActive] = useState("overview");
  const prefix = useId();
  const keys = ["overview", ...panels.map(p => p.id)];
  const panelKeys = panels.map(p => p.id).join(",");
  useEffect(() => {
    const read = () => {
      const id = window.location.hash.slice(1);
      // Old result anchors still open their containing view.
      const aliases: Record<string, string> = { "res-sociomap": "maps", "res-sociomapping": "maps", "res-aggregate": "data", "res-analysis": "analysis", "res-report": "report", "res-literature": "report" };
      const next = aliases[id] ?? id;
      setActive(next === "overview" || panelKeys.split(",").includes(next) ? next : "overview");
    };
    read();
    window.addEventListener("hashchange", read);
    window.addEventListener("popstate", read);
    return () => { window.removeEventListener("hashchange", read); window.removeEventListener("popstate", read); };
  }, [panelKeys]);
  const select = (id: string) => {
    setActive(id);
    window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}#${id}`);
  };
  const onKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next: number;
    if (event.key === "ArrowRight") next = (index + 1) % keys.length;
    else if (event.key === "ArrowLeft") next = (index + keys.length - 1) % keys.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = keys.length - 1;
    else return;
    event.preventDefault(); select(keys[next]);
    document.getElementById(`${prefix}-tab-${keys[next]}`)?.focus();
  };
  return <div className="flex min-w-0 max-w-6xl flex-col gap-5">
    <section aria-label="Vybraný běh výzkumu" className="rounded-md border border-border bg-surface-raised p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-signal">Výsledky studie</p>
          <h2 className="mt-1 text-xl font-semibold">Od výsledků k souvislostem a zprávě</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">Projděte data, prozkoumejte mapy a doplňte externí podklady. Zprávu stáhnete v oddílu Rešerše a zpráva.</p>
        </div>{progressHref ? <Link href={progressHref} className="rounded-control border border-border px-3 py-2 text-sm font-medium no-underline hover:bg-surface-sunken">Průběh tohoto běhu →</Link> : null}
      </div>
      <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 border-t border-border pt-3 text-sm">
        <div><dt className="text-xs text-ink-muted">Stav běhu</dt><dd className="font-semibold">{phaseLabel(run.phase)}</dd></div>
        <div><dt className="text-xs text-ink-muted">Revize návrhu</dt><dd className="font-semibold">{run.design_revision}</dd></div>
        <div><dt className="text-xs text-ink-muted">Skutečné náklady běhu</dt><dd className="font-semibold">{run.actual_cost_usd == null ? "Zatím nejsou vykázané" : `${run.actual_cost_usd.toFixed(2)} USD`}</dd></div>
        {run.methodology ? <div data-run-methodology><dt className="text-xs text-ink-muted">Metodika běhu</dt><dd className="flex flex-wrap gap-x-3 gap-y-1">
          {([["Sociomapa", run.methodology.sociomap], ["Podpora", run.methodology.support], ["Agregace", run.methodology.aggregation], ...(run.methodology.response ? [["Odpověď", run.methodology.response] as const] : [])] as const).map(([label, m]) =>
            m.name == null
              ? <span key={label}>{label} <span className="text-xs font-semibold">záznam nelze přečíst</span></span>
              : <span key={label}>{label} <span className="font-mono text-xs font-semibold">{m.name}</span> <span className="text-xs text-ink-muted">({m.stored ? "uložená verze" : "z kódu"})</span></span>)}
        </dd></div> : null}
      </dl>
      {run.methodology?.response_deviates === true ? (
        <p data-response-deviation className="mt-2 max-w-3xl text-xs text-ink-muted">Odpovědi AI respondentů vznikly jiným procesem odpovědi než v 18.6.6 (<span className="font-mono">{run.methodology.response?.name}</span>), takže je nelze přímo srovnávat s výsledky 18.6.6.</p>
      ) : run.methodology?.response_deviates === null ? (
        <p data-response-deviation className="mt-2 max-w-3xl text-xs text-ink-muted">Proces odpovědi tohoto běhu nelze přečíst; zda se liší od 18.6.6, nelze říct.</p>
      ) : null}
      <details className="mt-3 text-xs text-ink-muted"><summary className="cursor-pointer">Identifikace a původ běhu</summary><p className="mt-2 break-all">{run.run_id} · {run.design_revision_id}</p></details>
    </section>
    {notice}
    <div role="tablist" aria-label="Oddíly výsledků" className="flex gap-1 overflow-x-auto border-b border-border pb-1">
      {[{ id: "overview", label: "Přehled" }, ...panels].map((panel, index) => <button key={panel.id} type="button"
        id={`${prefix}-tab-${panel.id}`} role="tab" aria-selected={active === panel.id} aria-controls={`${prefix}-panel-${panel.id}`}
        tabIndex={active === panel.id ? 0 : -1} onKeyDown={event => onKey(event, index)} onClick={() => select(panel.id)}
        className={`shrink-0 rounded-control px-4 py-2.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-focus-ring ${active === panel.id ? "bg-signal-wash text-signal" : "text-ink-muted hover:bg-surface-sunken hover:text-ink"}`}>
        {panel.label}
      </button>)}
    </div>
    <section id={`${prefix}-panel-overview`} role="tabpanel" aria-labelledby={`${prefix}-tab-overview`} hidden={active !== "overview"} tabIndex={0}>
      <h2 className="mb-3 text-base font-semibold">Co chcete prozkoumat?</h2>
      <div className="grid gap-3 sm:grid-cols-2">{panels.map((panel, index) => <button key={panel.id} type="button" onClick={() => select(panel.id)}
        className="flex items-start gap-4 rounded-md border border-border bg-surface-raised p-5 text-left hover:border-signal focus-visible:outline-2 focus-visible:outline-focus-ring">
        <span aria-hidden="true" className="flex size-8 shrink-0 items-center justify-center rounded-control bg-signal-wash font-mono text-sm text-signal">{index + 1}</span>
        <span><span className="block font-semibold">{panel.label} →</span><span className="mt-1 block text-sm leading-6 text-ink-muted">{panel.description}</span></span>
      </button>)}</div>
      <p className="mt-4 text-sm leading-6 text-ink-muted">Každý oddíl patří ke stejnému běhu. Přepínání pohledů nemění výsledky ani nespouští nový výzkum. Kontrola a schválení výzkumníkem zůstávají samostatným krokem.</p>
    </section>
    {panels.map(panel => <section key={panel.id} id={`${prefix}-panel-${panel.id}`} role="tabpanel" aria-labelledby={`${prefix}-tab-${panel.id}`} hidden={active !== panel.id} tabIndex={0}>
      <p className="mb-4 text-sm leading-6 text-ink-muted">{panel.description}</p>
      <div className="space-y-4">{panel.content}</div>
    </section>)}
  </div>;
}
