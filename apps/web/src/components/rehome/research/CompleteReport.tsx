"use client";

// The study's end (research-lane-redesign chunk 8, complete-study-report B1-B5): one card at
// the top of Výsledky that says what the downloadable report holds, part by part, hands it
// over and approves it. It reads the run as it is: a part is "ve zprávě" only when the report
// step composed it, and the client version is offered only for a run whose respondents were
// modelled from the population (the API refuses any other, by name). This card is the one
// place a report is downloaded and approved; the report panel below shows its provenance.

import { useEffect, useState } from "react";

import { t } from "@/i18n/t";
import { ApiError, deepResearch, type DeepResearchRun, type ReportVariant, type ResearchReport, type ResearchRun, research } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { currentVariant, downloadMismatch, literatureState, reviewsFor, variantPdfAskable, variantPdfWhy, variantPending } from "@/lib/report-variant";
import { Button, Select } from "../ui";
import { Icon } from "../icons";
import { useFrame } from "./frame-hook";

type Part = { label: string; detail: string; state: "in" | "pending" | "later" | "excluded" };
type Version = "internal" | "client";
type Format = "docx" | "pdf";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/**
 * What the report holds, from the run's own steps; nothing here is guessed from elsewhere.
 * The report is composed once every analysis module is done (its own step), so a part is
 * in it only when that step succeeded; the Sociomap only when the run computed one.
 */
export function reportParts(
  run: { steps: readonly { kind?: string | null; node_key?: string; status: string }[] },
  literature: Part["state"] = "pending",
): Part[] {
  const composed = run.steps.some((s) => s.kind === "research_report" && s.status === "SUCCEEDED");
  const map = run.steps.find((s) => s.node_key === "sociomap");
  const fromReport = (label: string, detail: string): Part => ({ label, detail, state: composed ? "in" : "pending" });
  return [
    fromReport("Shrnutí a dopady pro rozhodnutí", "Z AI analýzy, každé číslo z ověřené evidence"),
    fromReport("Výzkumné otázky, objekty, segmenty, hypotézy", "Osm modulů analýzy"),
    fromReport("Respondenti a výpočet", "Kdo odpovídal, populace běhu, verze metod"),
    { label: "Sociomapy", detail: "Mapy z uloženého výpočtu, se stavem metodiky", state: !map ? "later" : composed && map.status === "SUCCEEDED" ? "in" : "pending" },
    { label: "Literatura (Deep Research)", detail: literature === "excluded" ? "Jen ve variantě s vybranou rešerší" : "Vybraná rešerše, citace ze zachycených zdrojů", state: literature },
    fromReport("Tabulky všech otázek", "Podíly, průměry a intervaly ke každé otázce"),
    fromReport("Návrh studie a dotazník v příloze", "Revize návrhu, podle které běh proběhl"),
    fromReport("Omezení, původ dat a příloha evidence", "Modelovaná data, otisky artefaktů"),
  ];
}

const MARK: Record<Part["state"], string> = {
  in: "bg-status-done text-surface-raised",
  pending: "border-[1.5px] border-border-strong",
  later: "border-[1.5px] border-dashed border-border-strong",
  excluded: "border-[1.5px] border-dashed border-border-strong",
};
const WORD: Record<Part["state"], string> = {
  in: "ve zprávě",
  pending: "čeká na přípravu zprávy",
  later: "běh ji nevytvořil",
  excluded: "není v této variantě",
};

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

/**
 * ``review`` is the literature review the report variant adds (research-integrity-report 3), held
 * by the results page so the literature panel below and this card never disagree; ``null`` is the
 * run's own report. Both formats are the same stored draft of the chosen variant.
 */
export function CompleteReport({ run, review = null, onReview }: { run: ResearchRun; review?: string | null; onReview?: (id: string | null) => void }) {
  const frame = useFrame();
  // The completed reviews, and the choice they were read for: a choice is undone only against a
  // list read after it was made, never against one still loading, stale or unread.
  const [listed, setListed] = useState<{ asked: string | null; reviews: DeepResearchRun[] } | null>(null);
  const reviews = listed?.reviews ?? null;
  const [variant, setVariant] = useState<ReportVariant | null>(null);
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
  // The completed reviews a variant may add: read on mount and whenever the choice moves.
  useEffect(() => {
    let live = true;
    const asked = review;
    deepResearch.runs(frame.studyId, 100).then(
      (all) => live && setListed({ asked, reviews: reviewsFor(all, run.run_id) }),
      // Unread is unknown, never "none": the list stays as it was.
      () => undefined,
    );
    return () => { live = false; };
  }, [frame.studyId, run.run_id, review]);
  // A review that is not a completed review of this run has no report: the choice goes back to the
  // run's own report, so this card and the literature panel below never name different documents.
  useEffect(() => {
    if (review === null || listed === null || listed.asked !== review) return;
    if (!listed.reviews.some((r) => r.run_id === review)) onReview?.(null);
  }, [review, listed, onReview]);
  // Only the chosen review's draft is read as the variant: a read still answering for a review the
  // person has since left is never shown, downloaded or approved under the new choice.
  const current = currentVariant(variant, run.run_id, review);
  const pending = variantPending(current);
  useEffect(() => {
    if (review === null || !frame.canEdit) { setVariant(null); return; }
    let live = true;
    const read = () => deepResearch.contextReport(frame.studyId, run.run_id, review).then(
      (v) => live && setVariant(v),
      (e: unknown) => live && setError(message(e)),
    );
    void read();
    const timer = pending ? setInterval(() => { void read(); }, 2500) : null;
    return () => { live = false; if (timer) clearInterval(timer); };
  }, [frame.studyId, frame.canEdit, run.run_id, review, pending]);
  if (status === "hidden") return null;
  const report = status !== null && status.state === "READY" ? status : null;
  const modelled = report?.data_origin_kind === "MODELLED";
  const pdfReady = report?.pdf?.state === "READY";
  const withReview = version === "internal" && review !== null;
  const parts = reportParts(run, withReview ? literatureState(review, current) : "excluded");
  const variantReady = withReview && current?.state === "READY";

  const clientWhy = modelled ? null : "Klientská zpráva vzniká jen z běhu s AI respondenty z populace.";
  const pdfWhy = version === "client"
    ? "Klientská zpráva je zatím jen DOCX."
    : withReview
      ? variantPdfWhy(current)
      : report?.pdf && report.pdf.state !== "READY"
      ? "PDF se nepodařilo vytvořit; zpráva je k dispozici jako DOCX."
      : pdfReady ? null : "Tento běh PDF nevytvořil.";
  const chosenFormat: Format = pdfWhy ? "docx" : format;
  const approved = version === "client"
    ? client?.approved === true
    : withReview ? current?.review_state === "APPROVED_INTERNAL" : report?.review_state === "APPROVED_INTERNAL";
  const approvable = version === "client" ? client !== null : withReview ? Boolean(current?.artifact_id) : Boolean(report?.artifact_id);
  // The stored draft the chosen internal variant is: what its download must be and what is approved.
  const shown = withReview ? current?.artifact_id ?? null : report?.artifact_id ?? null;

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
    } else if (withReview && review !== null && !variantReady) {
      // Store the draft once and ask the worker for its PDF: both formats of one document.
      setVariant(await deepResearch.prepareContextReport(frame.studyId, run.run_id, review));
    } else {
      const name = `AIA-${frame.studyId}-${run.run_id}-${withReview ? review : "zakladni"}.${chosenFormat}`;
      const got = withReview && review !== null
        ? await (chosenFormat === "pdf" ? deepResearch.downloadContextReportPdf : deepResearch.downloadContextReport)(frame.studyId, run.run_id, review)
        : await (chosenFormat === "pdf" ? research.downloadReportPdf : research.downloadReport)(frame.studyId, run.run_id);
      // The file must be the draft this card shows and approves; any other is not handed over.
      const why = downloadMismatch(got.artifactId, shown);
      if (why) throw new Error(why);
      saveBlob(got.blob, name);
    }
  });
  // The variant's PDF asked for again: the same stored draft, rendered by a new job.
  const askPdf = () => run_(async () => {
    if (review !== null) setVariant(await deepResearch.prepareContextReport(frame.studyId, run.run_id, review));
  });
  const approve = () => run_(async () => {
    if (version === "client" && client) {
      await research.approveReport(frame.studyId, run.run_id, client.artifactId);
      setClient({ ...client, approved: true });
    } else if (withReview && current?.artifact_id) {
      const done = await research.approveReport(frame.studyId, run.run_id, current.artifact_id);
      setVariant({ ...current, review_state: done.review_state });
    } else if (report?.artifact_id) {
      const done = await research.approveReport(frame.studyId, run.run_id, report.artifact_id);
      setStatus({ ...report, review_state: done.review_state });
    }
  });

  const stateLine = !report
    ? reportStep ? "Stav: zpráva se ještě skládá" : "Tento běh zprávu nevytváří"
    : version === "client" && !client
      ? "Stav: klientská zpráva se složí při stažení; schvalujete právě tu, kterou stáhnete"
      : withReview && !variantReady
        ? "Stav: zprávu s rešerší je třeba jednou připravit; pak ji stáhnete jako DOCX i PDF"
        : approved ? "Stav: schváleno" : "Stav: koncept, zatím neschválený";
  const chosenReview = reviews?.find((r) => r.run_id === review) ?? null;
  const limitation = report?.synthetic
    ? "Odpovídali syntetičtí respondenti: zpráva nepopisuje skutečné osoby."
    : modelled ? "Čísla jsou modelovaná AI respondenty, nejsou měřením." : null;

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
          {version === "internal" ? (
            <>
              <label className="flex flex-col gap-1">
                <span className="text-xs font-medium text-ink-muted">Varianta</span>
                <Select
                  aria-label="Varianta zprávy"
                  value={review ?? ""}
                  onChange={(e) => { onReview?.(e.target.value || null); setError(null); }}
                  disabled={!frame.canEdit}
                >
                  <option value="">Základní zpráva, bez literární rešerše</option>
                  {/* Chosen, and not (yet) in the list read: shown as chosen, never as another. */}
                  {review !== null && !reviews?.some((r) => r.run_id === review) ? <option value={review}>S rešerší · {review}</option> : null}
                  {(reviews ?? []).map((r) => (
                    <option key={r.run_id} value={r.run_id}>
                      S rešerší {r.created_at ? new Date(r.created_at).toLocaleDateString("cs-CZ") : ""} · {r.run_id}
                    </option>
                  ))}
                </Select>
              </label>
              {reviews !== null && !reviews.length ? <p className="text-xs leading-4 text-ink-muted">K tomuto běhu zatím není dokončená rešerše.</p> : null}
            </>
          ) : null}
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
            {busy
              ? t("research.exec.results.reportDownloading")
              : version === "client"
                ? t("research.exec.results.reportDownloadClient")
                : withReview && !variantReady ? "Připravit zprávu s rešerší" : "Stáhnout zprávu"}
          </Button>
          {withReview && version === "internal" && variantPdfAskable(current) && frame.canEdit ? (
            <Button variant="quiet" className="justify-center" disabled={busy} onClick={() => void askPdf()}>
              Vytvořit PDF znovu
            </Button>
          ) : null}
          {report && approvable && !approved && frame.canEdit ? (
            <Button className="!min-h-11 justify-center" disabled={busy} onClick={() => void approve()}>
              {t("research.exec.results.reportApprove")}
            </Button>
          ) : null}
          {/* What the downloaded file is, visible before it is downloaded: the same lines it prints. */}
          <dl aria-label="Co stahujete" className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs leading-4 text-ink-muted">
            <dt>Běh</dt><dd className="break-all font-mono">{run.run_id}</dd>
            <dt>Rešerše</dt><dd className="break-all font-mono">{withReview ? review : "žádná (základní zpráva)"}</dd>
            {chosenReview?.title ? <><dt>Název</dt><dd>{chosenReview.title}</dd></> : null}
            <dt>Literatura</dt><dd>{withReview ? (variantReady ? "kapitola s rešerší a zdroji" : "po přípravě zprávy") : "není součástí"}</dd>
            {version === "internal" && shown ? <><dt>Koncept</dt><dd className="break-all font-mono">{shown}</dd></> : null}
            {version === "internal" && shown ? <><dt>Schválení</dt><dd>{approved ? "schváleno v AIA" : "neschváleno"}</dd></> : null}
            {limitation ? <><dt>Omezení</dt><dd>{limitation}</dd></> : null}
          </dl>
          {/* The file never changes once stored: an approval is AIA's record about it, so the file
              keeps its draft footer (research-integrity-report D2). Said before it surprises anyone. */}
          {approvable ? <p className="text-xs leading-4 text-ink-muted">Schválení se zaznamená v AIA u tohoto uloženého souboru. Soubor se tím nemění a v zápatí dál nese „KONCEPT — NESCHVÁLENO“.</p> : null}
          <a href="#res-literature" className="text-xs">Literární rešerše k výsledkům</a>
          {error ? <p role="alert" className="text-xs text-status-fault">{error}</p> : null}
        </div>
      </div>
    </section>
  );
}
