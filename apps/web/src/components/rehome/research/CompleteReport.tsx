"use client";

// The study's end (research-lane-redesign chunk 8, complete-study-report B1-B5): one card at
// the top of Výsledky that says what the downloadable report holds, part by part, hands it
// over and approves it. It reads the run as it is: a part is "ve zprávě" only when the report
// step composed it, and the client version is offered only for a run whose respondents were
// modelled from the population (the API refuses any other, by name). This card is the one
// place a report is downloaded and approved; the report panel below shows its provenance.

import { useEffect, useState } from "react";
import { approvalRefusal, reportStatus, reportStatusWords, reviewStatus } from "@/lib/report-status";

import { t, tv } from "@/i18n/t";
import { ApiError, deepResearch, type DeepResearchRun, type ReportVariant, type ResearchReport, type ResearchRun, research } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { resultOriginKind, runOriginKinds, type OriginKind } from "@/lib/research-execution";
import {
  currentVariant,
  czechDate,
  downloadMismatch,
  literatureState,
  pdfAskable,
  pdfStatesReview,
  pdfWhy,
  reportPdfPending,
  reviewLine,
  reviewsFor,
  variantPdfAskable,
  variantPdfWhy,
  variantPending,
  type VersionReview,
} from "@/lib/report-variant";
import { Button, Select } from "../ui";
import { Icon } from "../icons";
import { canReview } from "./frame";
import { useFrame } from "./frame-hook";
import { CLIENT_PREPARED, REPORT_APPROVED, type ReportApproved } from "./ReportDocumentView";

type Part = { label: string; detail: string; state: "in" | "pending" | "later" | "excluded" };
type Version = "internal" | "client";
type Format = "docx" | "pdf";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/**
 * What the report holds, from the run's own steps; nothing here is guessed from elsewhere.
 * The report is composed once every analysis module is done (its own step), so a part is
 * in it only when that step succeeded; the Sociomap only when the run computed one.
 * ``prepared``: the chosen variant's draft is stored. It is composed on its own, with the same
 * chapters, so its parts are in it whatever the run's own report step did (review 2).
 */
export function reportParts(
  run: { steps: readonly { kind?: string | null; node_key?: string; status: string }[] },
  literature: Part["state"] = "pending",
  prepared = false,
  origins: ReadonlySet<OriginKind> = new Set(),
): Part[] {
  const composed = prepared || run.steps.some((s) => s.kind === "research_report" && s.status === "SUCCEEDED");
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
    fromReport("Omezení, původ dat a příloha evidence", `${originWords(origins)}, otisky artefaktů`),
  ];
}

/** The order a run's origin kinds are said in, so a mixed run always reads the same. */
const ORIGIN_ORDER: readonly OriginKind[] = ["SIMULATED", "MODELLED", "UNKNOWN"];

/**
 * The data's origin in words, from the kinds the run's steps and its report stated (CR-5): one
 * kind its own word, a mixed run every kind it holds, and nothing stated yet unknown -- never
 * presumed modelled.
 */
export function originWords(origins: ReadonlySet<OriginKind>): string {
  const kinds = ORIGIN_ORDER.filter((k) => origins.has(k));
  if (kinds.length === 0) return t("research.exec.originKind.UNKNOWN");
  return kinds.map((k) => t(`research.exec.originKind.${k}`)).join(" + ");
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
            ? "min-h-8 rounded-[4px] bg-surface-raised px-2.5 text-xs font-medium shadow-[0_0_0_1px_var(--border)]"
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
  // Everything this card does a closed study still allows: choose, prepare, download, approve.
  const mayReview = canReview(frame);
  // The completed reviews, and the choice they were read for: a choice is undone only against a
  // list read after it was made, never against one still loading, stale or unread.
  const [listed, setListed] = useState<{ asked: string | null; reviews: DeepResearchRun[] } | null>(null);
  const reviews = listed?.reviews ?? null;
  const [variant, setVariant] = useState<ReportVariant | null>(null);
  const [status, setStatus] = useState<ResearchReport | null | "hidden">(null);
  const [version, setVersion] = useState<Version>("internal");
  const [format, setFormat] = useState<Format>("docx");
  // The client version the last download was, as the server named it: its artifact and review
  // (the approval's answer adds its date and whether its file states it).
  const [client, setClient] = useState<{
    artifactId: string;
    reviewState: string | null;
    approvedOn: string | null;
    stamped: boolean | null;
  } | null>(null);
  // The client version stored for this run, read without composing (RD3): prepared in the
  // document pane, it is approvable here with no download first. A read that finds none (404)
  // or is refused leaves what the card knew; a download still prepares it.
  const [prepared, setPrepared] = useState(0);
  useEffect(() => {
    const on = (e: Event) => { if ((e as CustomEvent<string>).detail === run.run_id) setPrepared((n) => n + 1); };
    window.addEventListener(CLIENT_PREPARED, on);
    return () => window.removeEventListener(CLIENT_PREPARED, on);
  }, [run.run_id]);
  useEffect(() => {
    if (version !== "client") return;
    let live = true;
    research.clientReportDocument(frame.studyId, run.run_id).then(
      (stored) => {
        if (!live || typeof stored?.report_artifact_id !== "string") return;
        // A read sent before the pane's approval answered never takes that approval back.
        setClient((was) => (was?.artifactId === stored.report_artifact_id && reviewStatus(was.reviewState) === "APPROVED" ? was
          : { artifactId: stored.report_artifact_id, reviewState: stored.review_state, approvedOn: stored.approved_on, stamped: stored.stamped }));
      },
      () => undefined,
    );
    return () => { live = false; };
  }, [version, prepared, frame.studyId, run.run_id]);
  const [error, setError] = useState<string | null>(null);
  // A report approved in the document pane's doc bar (RPT3a), as the server answered it: the card
  // says it, approving nothing itself.
  useEffect(() => {
    let live = true;
    const on = (e: Event) => {
      const got = (e as CustomEvent<ReportApproved>).detail;
      if (got?.runId !== run.run_id) return;
      if (got.kind === "client") {
        setClient({ artifactId: got.artifactId, reviewState: got.reviewState, approvedOn: got.approvedOn, stamped: got.stamped });
      } else if (got.kind === "with_review") {
        // The variant read again only when it is the review chosen here; another's is not this card's (D2).
        if (!got.review || got.review !== review) return;
        deepResearch.contextReport(frame.studyId, run.run_id, got.review).then(
          (value) => { if (live) { setVariant(value); setError(null); } },
          (error: unknown) => { if (live) setError(message(error)); },
        );
      } else {
        // The approved PDF is rendered after approval: read again, the card follows it (D2); a
        // read that fails is said, never left showing the draft as if nothing happened.
        research.report(frame.studyId, run.run_id).then(
          (value) => { if (live) { setStatus(value); setError(null); } },
          (error: unknown) => { if (live) setError(message(error)); },
        );
      }
    };
    window.addEventListener(REPORT_APPROVED, on);
    return () => { live = false; window.removeEventListener(REPORT_APPROVED, on); };
  }, [frame.studyId, run.run_id, review]);
  const [busy, setBusy] = useState(false);
  const reportStep = run.steps.find((s) => s.kind === "research_report");
  // The run's own report, read again while a PDF a person asked for is being made.
  const basePending = status !== null && status !== "hidden" && reportPdfPending(status.pdf);
  useEffect(() => {
    if (!reportStep) return;
    let live = true;
    const read = () => research.report(frame.studyId, run.run_id).then(
      (value) => live && setStatus(value),
      (e: unknown) => live && (e instanceof ApiError && e.status === 403 ? setStatus("hidden") : setError(message(e))),
    );
    void read();
    const timer = basePending ? setInterval(() => { void read(); }, 2500) : null;
    return () => { live = false; if (timer) clearInterval(timer); };
  }, [frame.studyId, run.run_id, reportStep?.status, reportStep?.artifact_id, reportStep, basePending]);
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
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a review left or not permitted shows no variant
    if (review === null || !mayReview) { setVariant(null); return; }
    let live = true;
    const read = () => deepResearch.contextReport(frame.studyId, run.run_id, review).then(
      (v) => live && setVariant(v),
      (e: unknown) => live && setError(message(e)),
    );
    void read();
    const timer = pending ? setInterval(() => { void read(); }, 2500) : null;
    return () => { live = false; if (timer) clearInterval(timer); };
  }, [frame.studyId, mayReview, run.run_id, review, pending]);
  if (status === "hidden") return null;
  const report = status !== null && status.state === "READY" ? status : null;
  const modelled = report?.data_origin_kind === "MODELLED";
  const withReview = version === "internal" && review !== null;
  const variantReady = withReview && current?.state === "READY";
  // Stored under an earlier composition: still the report prepared (and maybe approved), said so,
  // and offered to be prepared anew; never hidden (review 3).
  const variantEarlier = variantReady && current?.contract_current === false;
  // The origin as the run's steps stamped it and as the stored report states it: every label
  // reads the origin, so a fictional run never reads "Modelovaná data" (CR-5).
  const origins = new Set(runOriginKinds(run));
  const reportKind = report ? resultOriginKind(report) : null;
  if (reportKind) origins.add(reportKind);
  const parts = reportParts(run, withReview ? literatureState(review, current) : "excluded", variantReady, origins);

  const clientWhy = modelled ? null : "Klientská zpráva vzniká jen z běhu s AI respondenty z populace.";
  // Why PDF is not offered for the chosen version, in the one wording every PDF state has.
  const formatWhy = version === "client"
    ? "Klientská zpráva je zatím jen DOCX."
    : withReview ? variantPdfWhy(current) : pdfWhy(report?.pdf, reviewStatus(report?.review_state) === "APPROVED");
  const chosenFormat: Format = formatWhy ? "docx" : format;
  // A new rendering of the stored draft is offered exactly when the server would start one.
  const askable = version === "internal" && (withReview ? variantPdfAskable(current) : !!report && pdfAskable(report.pdf));
  const approved = version === "client"
    ? reviewStatus(client?.reviewState) === "APPROVED"
    : reviewStatus(withReview ? current?.review_state : report?.review_state) === "APPROVED";
  const approvable = version === "client" ? client !== null : withReview ? Boolean(current?.artifact_id) : Boolean(report?.artifact_id);
  // The stored draft the chosen internal variant is: what its download must be and what is approved.
  const shown = withReview ? current?.artifact_id ?? null : report?.artifact_id ?? null;
  const shownState = withReview ? current?.review_state : report?.review_state;
  // The version shown and its review as the server last said it (D2): the card says what its file
  // states only from that, never from a click here.
  const seen: VersionReview | null = version === "client"
    ? client && { version: client.artifactId, reviewState: client.reviewState, approvedOn: client.approvedOn, stamped: client.stamped }
    : shown
      ? {
          version: shown,
          reviewState: shownState,
          approvedOn: withReview ? current?.approved_on : report?.approved_on,
          stamped: withReview ? current?.stamped : report?.stamped,
        }
      : null;
  // Whether this version's PDF states its review too: the client report is DOCX only; otherwise
  // as the server said (F35, review 4: a PDF is promised only where one will be made, never read
  // from a reason the server did not give).
  const pdfToo = version === "internal" && pdfStatesReview(
    shownState,
    withReview ? current?.pdf : report?.pdf,
    withReview ? current?.approval_renders_pdf : report?.approval_renders_pdf,
  );
  const fileLine = seen ? reviewLine(seen, pdfToo) : null;

  const run_ = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(approvalRefusal(e));
    } finally {
      setBusy(false);
    }
  };
  const download = () => run_(async () => {
    if (version === "client") {
      const got = await research.downloadClientReport(frame.studyId, run.run_id);
      saveBlob(got.blob, got.filename ?? `AIA-${frame.studyId}-klient.docx`);
      setClient(got.artifactId ? { artifactId: got.artifactId, reviewState: got.reviewState, approvedOn: null, stamped: null } : null);
    } else if (withReview && review !== null && !variantReady) {
      // Store the draft once and ask the worker for its PDF: both formats of one document.
      setVariant(await deepResearch.prepareContextReport(frame.studyId, run.run_id, review));
    } else {
      const name = `AIA-${frame.studyId}-${run.run_id}-${withReview ? review : "zakladni"}.${chosenFormat}`;
      const got = withReview && review !== null
        ? await (chosenFormat === "pdf" ? deepResearch.downloadContextReportPdf : deepResearch.downloadContextReport)(frame.studyId, run.run_id, review)
        : await (chosenFormat === "pdf" ? research.downloadReportPdf : research.downloadReport)(frame.studyId, run.run_id);
      // The file must be the version this card shows and approves, in the review the card shows;
      // any other is not handed over. Its name is the server's: the version and its review.
      const why = downloadMismatch(
        { artifactId: got.artifactId, reviewState: got.reviewState },
        { artifactId: shown, reviewState: shownState },
      );
      if (why) throw new Error(why);
      saveBlob(got.blob, got.filename ?? name);
    }
  });
  // An earlier composition's draft prepared anew under today's: a new draft, which needs its
  // own approval; the earlier one stays downloadable if composing is refused. Never offered for
  // an approved version, which stays the report.
  const prepareAgain = () => run_(async () => {
    if (review !== null) setVariant(await deepResearch.prepareContextReport(frame.studyId, run.run_id, review));
  });
  // The chosen report's PDF asked for again: the same stored draft, rendered by a new job,
  // composing nothing.
  const askPdf = () => run_(async () => {
    if (withReview && review !== null) setVariant(await deepResearch.askContextReportPdf(frame.studyId, run.run_id, review));
    else setStatus(await research.askReportPdf(frame.studyId, run.run_id));
  });
  // The report's state by the one rule (6e); a report still being read is said to be loading.
  // The variant with a review is its own draft: its state never waits on the run's own report.
  const internal = !reportStep ? "NONE" : status === null ? null : reportStatus(status, run.is_terminal);
  const stateLine = withReview
    ? !variantReady
      // A PDF is promised only where one will be made: not on a closed study, not where this
      // deployment renders none (review 2).
      ? "Stav: zprávu s rešerší je třeba jednou připravit. Pak ji stáhnete jako DOCX; PDF se stejným obsahem vznikne, pokud ho toto prostředí a stav studie dovolí"
      : fileLine ?? `Stav: ${reportStatusWords(approved ? "APPROVED" : "DRAFT")}`
    : internal === null
      ? t("research.loading")
      : !report
        ? `Stav: ${reportStatusWords(internal)}`
        : version === "client"
          ? !client
            // An approved client report is the one downloaded, whatever composing would give today.
            ? "Stav: schválená klientská zpráva se stáhne taková, jaká byla schválena; dokud žádná schválená není, složí se při stažení; schvaluje se v panelu Zpráva, na verzi, kterou tam čtete"
            // The file the client receives: approving signs it off for them, never "for internal use".
            : fileLine ?? `Stav: ${t(`research.exec.report.review.${approved ? "clientApproved" : "clientDraft"}`)}`
          : fileLine ?? `Stav: ${reportStatusWords(approved ? "APPROVED" : "DRAFT")}`;
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
            <p className="text-xs leading-4 text-ink-muted">
              {t("research.exec.results.reportClientHint")}
              {/* A draft only where the card knows it is one (its last download said so): never
                  beside an approved version, never guessed before a download (cross-review web#4). */}
              {client && !approved ? ` ${t("research.exec.results.reportClientHintDraft")}` : null}
            </p>
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
                  disabled={!mayReview}
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
              { id: "pdf", text: "PDF", disabled: formatWhy },
            ]}
          />
          {/* Why no PDF, as text: a disabled option's tooltip reaches no touch or keyboard reader,
              and the panel below no longer repeats it (review 3). */}
          {formatWhy ? <p data-format-why className="text-xs leading-4 text-ink-muted">{formatWhy}</p> : null}
          {/* A live region: approving removes the focused button and changes this line, which a
              screen reader then announces (cross-review web#11). */}
          <p role="status" data-report-state className="text-xs leading-4 text-ink-muted">{stateLine}</p>
          {/* The variant with a review needs no ready run report: preparing it is refused by name
              when the run's analysis is incomplete. */}
          <Button variant="primary" className="!min-h-11 justify-center" disabled={(!withReview && !report) || busy || !mayReview} onClick={() => void download()}>
            <Icon name="download" size={16} />
            {busy
              ? t("research.exec.results.reportDownloading")
              : version === "client"
                ? t("research.exec.results.reportDownloadClient")
                : withReview && !variantReady ? "Připravit zprávu s rešerší" : "Stáhnout zprávu"}
          </Button>
          {variantEarlier && approved ? (
            // An approved version stays the report: preparing anew would compose nothing over it
            // (cross-review interactions#5), so it is not offered.
            <p data-variant-earlier className="text-xs leading-4 text-ink-muted">
              Tato zpráva s rešerší byla připravena podle dřívější skladby zprávy{current?.contract ? ` (${current.contract})` : ""} a je schválená: zůstává zprávou této varianty a stahuje se taková, jaká byla schválena.
            </p>
          ) : variantEarlier ? (
            <>
              <p data-variant-earlier className="text-xs leading-4 text-ink-muted">
                Tato zpráva s rešerší byla připravena podle dřívější skladby zprávy{current?.contract ? ` (${current.contract})` : ""}. Stáhnout a schválit ji lze dál; připravená znovu bude nový koncept, který potřebuje vlastní schválení.
              </p>
              {mayReview ? (
                <Button variant="quiet" className="justify-center" disabled={busy} onClick={() => void prepareAgain()}>
                  Připravit znovu podle současné skladby
                </Button>
              ) : null}
            </>
          ) : null}
          {askable && mayReview ? (
            <Button variant="quiet" className="justify-center" disabled={busy} onClick={() => void askPdf()}>
              {(withReview ? current?.pdf : report?.pdf)?.state === "NOT_REQUESTED" ? "Vytvořit PDF" : "Vytvořit PDF znovu"}
            </Button>
          ) : null}
          {/* Every report is approved on the document being read, in the pane's doc bar (RPT3a): the
              card keeps the downloads, and says where a draft is approved so it never looks unapprovable. */}
          {version === "internal" && approvable && !approved && mayReview ? (
            <p data-approve-where className="text-xs leading-4 text-ink-muted">{t("research.exec.results.reportApproveWhere")}</p>
          ) : null}
          {/* What the downloaded file is, visible before it is downloaded: the same lines it prints. */}
          <dl aria-label="Co stahujete" className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs leading-4 text-ink-muted">
            <dt>Běh</dt><dd className="break-all font-mono">{run.run_id}</dd>
            <dt>Rešerše</dt><dd className="break-all font-mono">{withReview ? review : "žádná (základní zpráva)"}</dd>
            {chosenReview?.title ? <><dt>Název</dt><dd>{chosenReview.title}</dd></> : null}
            <dt>Literatura</dt><dd>{withReview ? (variantReady ? "kapitola s rešerší a zdroji" : "po přípravě zprávy") : "není součástí"}</dd>
            {version === "internal" && shown ? <><dt>Uložená verze</dt><dd className="break-all font-mono">{shown}</dd></> : null}
            {version === "internal" && shown ? (
              <>
                <dt>Schválení</dt>
                <dd>
                  {!approved
                    ? t("research.exec.report.review.notApproved")
                    : seen?.approvedOn
                      ? tv("research.exec.report.review.approvedOn", { date: czechDate(seen.approvedOn) })
                      : t("research.exec.report.review.approvedInAia")}
                </dd>
              </>
            ) : null}
            {limitation ? <><dt>Omezení</dt><dd>{limitation}</dd></> : null}
          </dl>
          {/* A version stored before its status moved to the footers (D2) is served as stored once
              approved, never partly stamped: its file keeps its draft footer, said before it
              surprises anyone. A version whose layout the server did not say gets no claim at all. */}
          {approvable && seen?.stamped === false ? (
            <p data-review-older className="text-xs leading-4 text-ink-muted">
              {t(approved ? "research.exec.report.review.olderApproved" : "research.exec.report.review.older")}
            </p>
          ) : null}
          <a href="#res-literature" className="text-xs">Literární rešerše k výsledkům</a>
          {error ? <p role="alert" className="text-xs text-status-fault">{error}</p> : null}
        </div>
      </div>
    </section>
  );
}
