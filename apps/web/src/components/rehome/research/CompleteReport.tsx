"use client";

// The study's end (research-lane-redesign chunk 8, complete-study-report B1-B5): one card at
// the top of Výsledky that says what the downloadable report holds, part by part, hands it
// over and approves it. It reads the run as it is: a part is "ve zprávě" only when the report
// step composed it, and the client version is offered only for a run whose respondents were
// modelled from the population (the API refuses any other, by name). This card is the one
// place a report is downloaded and approved; the report panel below shows its provenance.

import { useEffect, useState } from "react";

import { t } from "@/i18n/t";
import { ApiError, type ResearchReport, type ResearchRun, research } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { Button } from "../ui";
import { Icon } from "../icons";
import { useFrame } from "./frame-hook";

type Part = { label: string; detail: string; state: "in" | "pending" | "later" };
type Version = "internal" | "client";
type Format = "docx" | "pdf";

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
    fromReport("Respondenti a výpočet", "Kdo odpovídal, populace běhu, verze metod"),
    { label: "Sociomapy", detail: "Mapy z uloženého výpočtu, se stavem metodiky", state: !map ? "later" : composed && map.status === "SUCCEEDED" ? "in" : "pending" },
    { label: "Literatura (Deep Research)", detail: "S vybranou rešerší níže, citace ze zachycených zdrojů", state: "pending" },
    fromReport("Tabulky všech otázek", "Podíly, průměry a intervaly ke každé otázce"),
    fromReport("Návrh studie a dotazník v příloze", "Revize návrhu, podle které běh proběhl"),
    fromReport("Omezení, původ dat a příloha evidence", "Modelovaná data, otisky artefaktů"),
  ];
}

const MARK: Record<Part["state"], string> = {
  in: "bg-status-done text-surface-raised",
  pending: "border-[1.5px] border-border-strong",
  later: "border-[1.5px] border-dashed border-border-strong",
};
const WORD: Record<Part["state"], string> = { in: "ve zprávě", pending: "čeká na běh nebo výběr", later: "běh ji nevytvořil" };

function Segment<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: readonly { id: T; text: string; disabled: string | null }[];
  onChange: (next: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex w-fit rounded-control border border-border bg-surface-sunken p-0.5">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={value === o.id}
          aria-disabled={o.disabled ? true : undefined}
          title={o.disabled ?? undefined}
          onClick={() => { if (!o.disabled) onChange(o.id); }}
          className={value === o.id
            ? "min-h-8 rounded-[4px] bg-surface-raised px-2.5 text-xs font-medium shadow-[0_0_0_1px_var(--color-border)]"
            : `min-h-8 rounded-[4px] px-2.5 text-xs font-medium ${o.disabled ? "cursor-not-allowed text-ink-faint" : "text-ink-muted"}`}
        >
          {o.text}
        </button>
      ))}
    </div>
  );
}

export function CompleteReport({ run }: { run: ResearchRun }) {
  const frame = useFrame();
  const [status, setStatus] = useState<ResearchReport | null | "hidden">(null);
  const [version, setVersion] = useState<Version>("internal");
  const [format, setFormat] = useState<Format>("docx");
  // The client draft the last download was: its artifact and whether it is approved.
  const [client, setClient] = useState<{ artifactId: string; approved: boolean } | null>(null);
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
  const report = status !== null && status.state === "READY" ? status : null;
  const modelled = report?.data_origin_kind === "MODELLED";
  const pdfReady = report?.pdf?.state === "READY";
  const parts = reportParts(run);

  const clientWhy = modelled ? null : "Klientská zpráva vzniká jen z běhu s AI respondenty z populace.";
  const pdfWhy = version === "client"
    ? "Klientská zpráva je zatím jen DOCX."
    : report?.pdf && report.pdf.state !== "READY"
      ? "PDF se nepodařilo vytvořit; zpráva je k dispozici jako DOCX."
      : pdfReady ? null : "Tento běh PDF nevytvořil.";
  const chosenFormat: Format = pdfWhy ? "docx" : format;
  const approved = version === "client" ? client?.approved === true : report?.review_state === "APPROVED_INTERNAL";
  const approvable = version === "client" ? client !== null : Boolean(report?.artifact_id);

  const run_ = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof ApiError && e.code === "separation_of_duties"
        ? t("research.exec.results.reportApproveIndependent") : message(e));
    } finally {
      setBusy(false);
    }
  };
  const download = () => run_(async () => {
    if (version === "client") {
      const got = await research.downloadClientReport(frame.studyId, run.run_id);
      saveBlob(got.blob, `AIA-${frame.studyId}-klient.docx`);
      setClient(got.artifactId ? { artifactId: got.artifactId, approved: got.reviewState === "APPROVED_INTERNAL" } : null);
    } else if (chosenFormat === "pdf") {
      saveBlob(await research.downloadReportPdf(frame.studyId, run.run_id), `AIA-${frame.studyId}-zprava.pdf`);
    } else {
      saveBlob(await research.downloadReport(frame.studyId, run.run_id), `AIA-${frame.studyId}-zprava.docx`);
    }
  });
  const approve = () => run_(async () => {
    if (version === "client" && client) {
      await research.approveReport(frame.studyId, run.run_id, client.artifactId);
      setClient({ ...client, approved: true });
    } else if (report?.artifact_id) {
      const done = await research.approveReport(frame.studyId, run.run_id, report.artifact_id);
      setStatus({ ...report, review_state: done.review_state });
    }
  });

  const stateLine = !report
    ? reportStep ? "Stav: zpráva se ještě skládá" : "Tento běh zprávu nevytváří"
    : version === "client" && !client
      ? "Stav: klientská zpráva se složí při stažení; schvalujete právě tu, kterou stáhnete"
      : approved ? "Stav: schváleno" : "Stav: koncept, zatím neschválený";

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
                  <span className={`block text-xs leading-4 ${p.state === "later" ? "text-ink-faint" : "text-ink-muted"}`}>{p.state === "later" ? `${p.detail} · ${WORD.later}` : p.detail}</span>
                </span>
              </li>
            ))}
          </ul>
          {version === "client" ? (
            <p className="text-xs leading-4 text-ink-muted">{t("research.exec.results.reportClientHint")}</p>
          ) : null}
        </div>
        <div className="flex flex-col gap-2.5 border-t border-border bg-surface p-4 lg:border-l lg:border-t-0">
          <span className="text-xs font-medium text-ink-muted">Verze</span>
          <Segment<Version>
            label="Verze zprávy"
            value={version}
            onChange={(v) => { setVersion(v); setError(null); }}
            options={[
              { id: "internal", text: "Interní", disabled: null },
              { id: "client", text: "Pro klienta", disabled: clientWhy },
            ]}
          />
          {clientWhy ? <p className="text-xs leading-4 text-ink-muted">Pro klienta: {clientWhy}</p> : null}
          <span className="text-xs font-medium text-ink-muted">Formát</span>
          <Segment<Format>
            label="Formát zprávy"
            value={chosenFormat}
            onChange={setFormat}
            options={[
              { id: "docx", text: "DOCX", disabled: null },
              { id: "pdf", text: "PDF", disabled: pdfWhy },
            ]}
          />
          <p className="text-xs leading-4 text-ink-muted">{stateLine}</p>
          <Button variant="primary" className="!min-h-11 justify-center" disabled={!report || busy || !frame.canEdit} onClick={() => void download()}>
            <Icon name="download" size={16} />
            {busy ? t("research.exec.results.reportDownloading") : version === "client" ? t("research.exec.results.reportDownloadClient") : "Stáhnout zprávu"}
          </Button>
          {report && approvable && !approved && frame.canEdit ? (
            <Button className="!min-h-11 justify-center" disabled={busy} onClick={() => void approve()}>
              {t("research.exec.results.reportApprove")}
            </Button>
          ) : null}
          <a href="#report" className="text-xs">Zpráva s literární rešerší</a>
          {error ? <p role="alert" className="text-xs text-status-fault">{error}</p> : null}
        </div>
      </div>
    </section>
  );
}
