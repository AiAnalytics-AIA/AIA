"use client";

import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import type { ResearchRun } from "@/lib/api";
import { runState } from "@/lib/run-state";
import { t } from "@/i18n/t";
import { spendRows } from "@/lib/run-spend";
import { PanelShown } from "./panel-shown";

/** What the run has spent, by Průběh's Náklady rule (#774): the attempts' sum would read a call that came
 *  back without a price as nothing spent, so such calls are named beside it, said while the run goes on
 *  as possibly still in flight. Only the spent and unpriced rows: holds and the remainder are Průběh's. */
function spentWords(run: ResearchRun): ReactNode {
  const rows = spendRows(run.spend, run.is_terminal, null, run.cost_ceiling);
  if (!rows) return t("research.exec.spend.unknown");
  const spent = rows.find((r) => r.key === "spent")?.value;
  const unpriced = rows.find((r) => r.key === "unpriced");
  return unpriced ? <>{spent} · {unpriced.label}: {unpriced.value} <span className="text-xs font-normal text-ink-muted">({unpriced.note})</span></> : spent;
}

export type ResultPanel = { id: string; label: string; description: string; content: ReactNode };

/** Views of the same frozen run. Hidden panels stay mounted so map cameras and review selections survive. */
export function ResultsWorkspace({ run, panels, progressHref, notice, lead }: {
  /** The run's progress page; null where the page has none to link to (project memory). */
  run: ResearchRun; panels: ResultPanel[]; progressHref: string | null; notice: ReactNode;
  /** What the study ends in, above everything else (the complete report). */
  lead?: ReactNode;
}) {
  const [active, setActive] = useState("overview");
  const tabs = useRef<HTMLDivElement>(null);
  const prefix = useId();
  const keys = ["overview", ...panels.map(p => p.id)];
  const panelKeys = panels.map(p => p.id).join(",");
  useEffect(() => {
    const read = () => {
      const id = window.location.hash.slice(1);
      // Old result anchors still open their containing view.
      const aliases: Record<string, string> = { "res-sociomap": "maps", "res-sociomapping": "maps", "res-aggregate": "data", "res-analysis": "analysis", "res-report": "report", "res-literature": "report" };
      // A measure's card (#measure-<id>, result-reading.ts measureAnchor) is in Data.
      const next = id.startsWith("measure-") ? "data" : aliases[id] ?? id;
      const known = panelKeys.split(",").includes(next);
      setActive(next === "overview" || known ? next : "overview");
      // A view named by the address (a stage of its own: Výsledky, Sociomapa, Analýza, Zpráva) opens
      // scrolled to it, not under the run's notices; a measure's card scrolls itself into view.
      if (known && !id.startsWith("measure-")) pin();
    };
    // What sits above the tabs (the run's notices, its receipt) loads after them and pushes them
    // down, so the tabs stay pinned while it settles: every resize within 3 s scrolls them back,
    // until the person scrolls, touches or types.
    let release = () => {};
    const pin = () => {
      release();
      const root = tabs.current?.parentElement;
      const scroll = () => tabs.current?.scrollIntoView?.({ block: "start" });
      window.requestAnimationFrame(scroll);
      if (!root || typeof ResizeObserver === "undefined") return;
      const observer = new ResizeObserver(scroll);
      observer.observe(root);
      const stop = window.setTimeout(() => release(), 3000);
      const user = ["wheel", "touchstart", "keydown"] as const;
      release = () => { observer.disconnect(); window.clearTimeout(stop); user.forEach((e) => window.removeEventListener(e, release)); release = () => {}; };
      user.forEach((e) => window.addEventListener(e, release, { once: true, passive: true }));
    };
    read();
    window.addEventListener("hashchange", read);
    window.addEventListener("popstate", read);
    return () => { release(); window.removeEventListener("hashchange", read); window.removeEventListener("popstate", read); };
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
    {notice}
    {/* The study's report card belongs to Přehled and Rešerše a zpráva. On Data, Sociomapy and AI
        analýza it would push the view a person opened two screens down (artifact-results,
        Findings). Hidden, never unmounted, so its choices survive a switch, as the panels' do. */}
    {lead ? <div data-results-lead hidden={!(active === "overview" || active === "report")}>{lead}</div> : null}
    <section aria-label="Vybraný běh výzkumu" className="rounded-md border border-border bg-surface-raised p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-signal">Výsledky studie</p>
          <h2 className="mt-1 text-xl font-semibold">Od výsledků k souvislostem a zprávě</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">Projděte data, prozkoumejte mapy a ověřte, které části analýzy a externí podklady lze použít. Připravenost dokumentu zjistíte v oddílu Rešerše a zpráva.</p>
        </div>{progressHref ? <Link href={progressHref} className="rounded-control border border-border px-3 py-2 text-sm font-medium no-underline hover:bg-surface-sunken">Průběh tohoto běhu →</Link> : null}
      </div>
      <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2 border-t border-border pt-3 text-sm">
        <div><dt className="text-xs text-ink-muted">Stav běhu</dt><dd className="font-semibold">{runState(run).label}</dd></div>
        <div><dt className="text-xs text-ink-muted">Revize návrhu</dt><dd className="font-semibold">{run.design_revision}</dd></div>
        <div data-run-spent><dt className="text-xs text-ink-muted">{t("research.exec.spend.spent")}</dt><dd className="font-semibold">{spentWords(run)}</dd></div>
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
    <div ref={tabs} role="tablist" aria-label="Oddíly výsledků" className="scroll-mt-4 flex gap-1 overflow-x-auto border-b border-border pb-1">
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
      <div className="space-y-4"><PanelShown.Provider value={active === panel.id}>{panel.content}</PanelShown.Provider></div>
    </section>)}
  </div>;
}
