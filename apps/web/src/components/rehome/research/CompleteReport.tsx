"use client";

// The study's end (research-lane-redesign chunk 8): one card at the top of Výsledky
// that says what the downloadable report holds, part by part, and hands it over.
// It reads the run as it is: a part is "ve zprávě" only when the internal report
// AIA composes today carries it (application/report.py compose_internal_report),
// and a part AIA does not compose yet says so rather than pretending. The client
// version and PDF are drawn and refused with their reason: AIA does not compose the
// client version yet (research-lane-redesign B5; the owner admitted modelled data to
// it on 2026-10-13, each number labelled), and it renders DOCX only.

import { useEffect, useState } from "react";

import { t } from "@/i18n/t";
import { ApiError, type ResearchReport, type ResearchRun, research } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { Button } from "../ui";
import { Icon } from "../icons";
import { useFrame } from "./frame-hook";

type Part = { label: string; detail: string; state: "in" | "pending" | "later" };

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/**
 * What the report holds, from the run's own steps; nothing here is guessed from elsewhere.
 * The report is composed once every analysis module is done (its own step), so a part is
 * in it only when that step succeeded; the Sociomap only when the run computed one.
 */
export function reportParts(run: { steps: readonly { kind?: string | null; node_key?: string; status: string }[] }): Part[] {
  const composed = run.steps.some((s) => s.kind === "research_report" && s.status === "SUCCEEDED");
  const map = run.steps.find((s) => s.node_key === "sociomap");
  const fromReport = (label: string, detail: string): Part => ({ label, detail, state: composed ? "in" : "pending" });
  return [
    fromReport("Shrnutí a dopady pro rozhodnutí", "Z AI analýzy, každé číslo z ověřené evidence"),
    fromReport("Výzkumné otázky, objekty, segmenty, hypotézy", "Osm modulů analýzy"),
    fromReport("Metodika", "Populace, AI respondenti, verze výpočtů"),
    { label: "Sociomapy", detail: "Mapy z uloženého výpočtu, s verzí metodiky", state: !map ? "later" : composed && map.status === "SUCCEEDED" ? "in" : "pending" },
    { label: "Literatura (Deep Research)", detail: "S vybranou rešerší níže, citace ze zachycených zdrojů", state: "pending" },
    fromReport("Omezení, původ dat a příloha evidence", "Modelovaná data, otisky artefaktů"),
    { label: "Tabulky všech otázek", detail: "Průměry a intervaly ke každé otázce", state: "later" },
    { label: "Zadání, návrh a dotazník v příloze", detail: "Revize návrhu, podle které běh proběhl", state: "later" },
  ];
}

const MARK: Record<Part["state"], string> = {
  in: "bg-status-done text-surface-raised",
  pending: "border-[1.5px] border-border-strong",
  later: "border-[1.5px] border-dashed border-border-strong",
};
const WORD: Record<Part["state"], string> = { in: "ve zprávě", pending: "čeká na běh nebo výběr", later: "AIA zatím neskládá" };

export function CompleteReport({ run }: { run: ResearchRun }) {
  const frame = useFrame();
  const [status, setStatus] = useState<ResearchReport | null | "hidden">(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reportStep = run.steps.find((s) => s.kind === "research_report");
  useEffect(() => {
    if (!reportStep) return;
    let live = true;
    research.report(frame.studyId, run.run_id).then(
      (value) => live && setStatus(value),
      (e: unknown) => live && (e instanceof ApiError && e.status === 403 ? setStatus("hidden") : setError(message(e))),
    );
    return () => { live = false; };
  }, [frame.studyId, run.run_id, reportStep?.status, reportStep?.artifact_id, reportStep]);
  if (status === "hidden") return null;
  const ready = status !== null && status.state === "READY";
  const parts = reportParts(run);
  const download = async () => {
    setBusy(true);
    setError(null);
    try {
      saveBlob(await research.downloadReport(frame.studyId, run.run_id), `AIA-${frame.studyId}-zprava.docx`);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section aria-labelledby="complete-report-title" data-complete-report className="overflow-hidden rounded-card border border-ink bg-surface-raised">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex flex-col gap-3 p-4">
          <div className="flex items-center gap-2.5">
            {/* eslint-disable-next-line @next/next/no-img-element -- the identity's own SVG, served by this app */}
            <img src="/skin/brand/aia-mark.svg" alt="" width={28} height={28} />
            <div>
              <h2 id="complete-report-title" className="text-[17px] font-semibold leading-6">Kompletní zpráva studie</h2>
              <p className="text-xs text-ink-muted">{frame.studyName} · {frame.clientName} · se značkou AI Analytics</p>
            </div>
          </div>
          <ul className="grid gap-x-4 sm:grid-cols-2">
            {parts.map((p) => (
              <li key={p.label} className="grid grid-cols-[18px_1fr] items-start gap-2 border-b border-border py-1.5">
                <span aria-hidden="true" className={`mt-px inline-flex size-[18px] items-center justify-center rounded-full ${MARK[p.state]}`}>
                  {p.state === "in" ? <Icon name="done" size={10} /> : null}
                </span>
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium leading-[18px]">{p.label}<span className="sr-only"> · {WORD[p.state]}</span></span>
                  <span className={`block text-xs leading-4 ${p.state === "later" ? "text-ink-faint" : "text-ink-muted"}`}>{p.state === "later" ? `${p.detail} · AIA zatím neskládá` : p.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-2.5 border-t border-border bg-surface p-4 lg:border-l lg:border-t-0">
          <span className="text-xs font-medium text-ink-muted">Verze</span>
          <div role="radiogroup" aria-label="Verze zprávy" className="inline-flex w-fit rounded-control border border-border bg-surface-sunken p-0.5">
            <button type="button" role="radio" aria-checked="true" className="min-h-8 rounded-[4px] bg-surface-raised px-2.5 text-xs font-medium shadow-[0_0_0_1px_var(--color-border)]">Interní</button>
            <button type="button" role="radio" aria-checked="false" aria-disabled="true" aria-describedby="report-client-why" className="min-h-8 cursor-not-allowed rounded-[4px] px-2.5 text-xs font-medium text-ink-faint">Pro klienta</button>
          </div>
          <p id="report-client-why" className="text-xs leading-4 text-ink-muted">Pro klienta: klientskou verzi (s modelovanými daty označenými „modelováno“) AIA zatím neskládá.</p>
          <span className="text-xs font-medium text-ink-muted">Formát</span>
          <div role="radiogroup" aria-label="Formát zprávy" className="inline-flex w-fit rounded-control border border-border bg-surface-sunken p-0.5">
            <button type="button" role="radio" aria-checked="true" className="min-h-8 rounded-[4px] bg-surface-raised px-2.5 text-xs font-medium shadow-[0_0_0_1px_var(--color-border)]">DOCX</button>
            <button type="button" role="radio" aria-checked="false" aria-disabled="true" title="PDF AIA zatím nevytváří" className="min-h-8 cursor-not-allowed rounded-[4px] px-2.5 text-xs font-medium text-ink-faint">PDF</button>
          </div>
          <p className="text-xs leading-4 text-ink-muted">
            {ready
              ? status.review_state === "APPROVED_INTERNAL" ? "Stav: schváleno pro interní použití" : "Stav: koncept, zatím neschválený"
              : reportStep ? "Stav: zpráva se ještě skládá" : "Tento běh zprávu nevytváří"}
          </p>
          <Button variant="primary" className="!min-h-11 justify-center" disabled={!ready || busy || !frame.canEdit} onClick={() => void download()}>
            <Icon name="download" size={16} />
            {busy ? t("research.exec.results.reportDownloading") : "Stáhnout zprávu"}
          </Button>
          <a href="#report" className="text-xs">Zpráva s literární rešerší</a>
          {error ? <p role="alert" className="text-xs text-status-fault">{error}</p> : null}
        </div>
      </div>
    </section>
  );
}
