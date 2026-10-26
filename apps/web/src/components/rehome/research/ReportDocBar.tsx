"use client";

// The doc bar's exports (artifact-report RPT3c, spec szz Z2): the document on screen downloaded
// from where it is read, as DOCX or PDF, beside its review and approval. Every file is checked to
// be the version shown, in the review shown (D2), before it is handed over; a PDF is offered only
// where the server says one exists, and asked for again only where it says one can be made.
// Downloads stay free before approval (RPT3b, Q73 (c)).

import { useEffect, useState } from "react";

import { type ApprovedEdit, deepResearch, type ReportVariant, type ResearchReport, research } from "@/lib/api";
import type { StoredReportDocument } from "@/lib/artifacts/report";
import { saveBlob } from "@/lib/download";
import { approvalRefusal, reviewStatus } from "@/lib/report-status";
import { downloadMismatch, pdfAskable, pdfWhy, reportPdfPending, variantPdfAskable, variantPdfWhy, variantPending } from "@/lib/report-variant";
import { Button } from "../ui";
import { Icon } from "../icons";

export type ExportKind = "internal" | "client" | "with_review";

type Status = { kind: "internal"; value: ResearchReport } | { kind: "with_review"; value: ReportVariant };

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The client report is DOCX only; the others as the server states their PDF. */
function exportPdfWhy(kind: ExportKind, status: Status | null): string | null {
  if (kind === "client") return "Klientská zpráva je zatím jen DOCX.";
  if (!status) return "Stav PDF se načítá.";
  if (status.kind === "with_review") return variantPdfWhy(status.value);
  return pdfWhy(status.value.pdf, reviewStatus(status.value.review_state) === "APPROVED");
}

export function ReportExports({ studyId, runId, kind, review, stored, canAct }: {
  studyId: string; runId: string; kind: ExportKind; review: string | null; stored: StoredReportDocument; canAct: boolean;
}) {
  const [status, setStatus] = useState<{ at: string; value: Status } | null>(null);
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<{ at: string; words: string } | null>(null);
  // One document's status: another's (a switch, or a newer version) is never shown for it.
  const at = `${runId}:${kind}:${review ?? ""}:${stored.report_artifact_id}:${stored.review_state}`;
  const current = status?.at === at ? status.value : null;
  const pending = current?.kind === "with_review" ? variantPending(current.value) : current ? reportPdfPending(current.value.pdf) : false;
  useEffect(() => {
    if (kind === "client") return;
    let live = true;
    const read = () => (kind === "with_review" && review !== null
      ? deepResearch.contextReport(studyId, runId, review).then((value): Status => ({ kind: "with_review", value }))
      : research.report(studyId, runId).then((value): Status => ({ kind: "internal", value }))
    ).then(
      (value) => { if (live) setStatus({ at, value }); },
      (error: unknown) => { if (live) setSaid({ at, words: `Stav zprávy se nepodařilo načíst: ${message(error)}` }); },
    );
    void read();
    // Read again while its PDF is being made, so the PDF is offered once it exists.
    const timer = pending ? setInterval(() => { void read(); }, 2500) : null;
    return () => { live = false; if (timer) clearInterval(timer); };
  }, [studyId, runId, kind, review, at, pending]);

  const shown = { artifactId: stored.report_artifact_id, reviewState: stored.review_state };
  const pdfReason = exportPdfWhy(kind, current);
  const askable = current?.kind === "with_review" ? variantPdfAskable(current.value) : current ? pdfAskable(current.value.pdf) : false;
  const edits: ApprovedEdit[] = current?.value.approved_edits ?? [];
  const base = `AIA-${studyId}-${runId}-${kind === "with_review" ? "s-resersi" : kind === "client" ? "klient" : "zakladni"}`;

  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setSaid(null);
    try {
      await work();
    } catch (e) {
      setSaid({ at, words: approvalRefusal(e) });
    } finally {
      setBusy(false);
    }
  };
  const download = (format: "docx" | "pdf") => act(async () => {
    const got = kind === "client"
      ? await research.downloadClientReport(studyId, runId)
      : kind === "with_review" && review !== null
        ? await (format === "pdf" ? deepResearch.downloadContextReportPdf : deepResearch.downloadContextReport)(studyId, runId, review)
        : await (format === "pdf" ? research.downloadReportPdf : research.downloadReport)(studyId, runId);
    // The file must be the version on screen, in the review on screen; any other is not handed over.
    const why = downloadMismatch({ artifactId: got.artifactId, reviewState: got.reviewState }, shown);
    if (why) throw new Error(why);
    saveBlob(got.blob, got.filename ?? `${base}.${format}`);
  });
  const downloadEdit = (edit: ApprovedEdit) => act(async () => {
    const got = await research.downloadReportEditorVersion(studyId, runId, edit.artifact_id);
    const why = downloadMismatch({ artifactId: got.artifactId, reviewState: got.reviewState }, { artifactId: edit.artifact_id, reviewState: edit.review_state });
    if (why) throw new Error(why);
    saveBlob(got.blob, got.filename ?? `${base}-koncept-${edit.koncept}.docx`);
  });
  // A report with literature stored under an earlier composition, prepared anew under today's: a new
  // draft that needs its own approval; the earlier one stays if composing is refused. Never offered
  // for an approved version, which stays the report (cross-review interactions#5).
  const earlier = current?.kind === "with_review" && current.value.state === "READY" && current.value.contract_current === false ? current.value : null;
  const earlierApproved = earlier !== null && reviewStatus(earlier.review_state) === "APPROVED";
  const prepareAgain = () => act(async () => {
    if (review !== null) setStatus({ at, value: { kind: "with_review", value: await deepResearch.prepareContextReport(studyId, runId, review) } });
  });
  // The same stored draft rendered again by a new job, composing nothing.
  const askPdf = () => act(async () => {
    const value: Status = kind === "with_review" && review !== null
      ? { kind: "with_review", value: await deepResearch.askContextReportPdf(studyId, runId, review) }
      : { kind: "internal", value: await research.askReportPdf(studyId, runId) };
    setStatus({ at, value });
  });

  const words = said?.at === at ? said.words : null;
  return (
    <span className="contents" data-report-exports>
      <Button variant="quiet" className="!min-h-11" disabled={busy || !canAct} onClick={() => void download("docx")}>
        <Icon name="download" size={16} /> DOCX
      </Button>
      <Button variant="quiet" className="!min-h-11" disabled={busy || !canAct || pdfReason !== null} title={pdfReason ?? undefined} onClick={() => void download("pdf")}>
        <Icon name="download" size={16} /> PDF
      </Button>
      {askable && canAct ? (
        <Button variant="quiet" className="!min-h-11" disabled={busy} onClick={() => void askPdf()}>
          {current?.value.pdf?.state === "NOT_REQUESTED" ? "Vytvořit PDF" : "Vytvořit PDF znovu"}
        </Button>
      ) : null}
      {edits.map((edit) => (
        <Button key={edit.artifact_id} variant="quiet" className="!min-h-11" disabled={busy || !canAct} onClick={() => void downloadEdit(edit)}>
          <Icon name="download" size={16} /> Schválená úprava, koncept {edit.koncept} (DOCX)
        </Button>
      ))}
      {earlier ? (
        <span data-variant-earlier className="basis-full text-xs text-ink-muted">
          {earlierApproved
            ? `Tato zpráva s rešerší byla připravena podle dřívější skladby zprávy${earlier.contract ? ` (${earlier.contract})` : ""} a je schválená: zůstává zprávou této varianty a stahuje se taková, jaká byla schválena.`
            : `Tato zpráva s rešerší byla připravena podle dřívější skladby zprávy${earlier.contract ? ` (${earlier.contract})` : ""}. Stáhnout a schválit ji lze dál; připravená znovu bude nový koncept, který potřebuje vlastní schválení.`}
        </span>
      ) : null}
      {earlier && !earlierApproved && canAct ? (
        <Button variant="quiet" className="!min-h-11" disabled={busy} onClick={() => void prepareAgain()}>Připravit znovu podle současné skladby</Button>
      ) : null}
      {/* Why no PDF, as text: a disabled button's title reaches no touch or keyboard reader. */}
      {pdfReason && kind !== "client" && current ? <span data-pdf-why className="basis-full text-xs text-ink-muted">PDF: {pdfReason}</span> : null}
      {words ? <span role="alert" className="basis-full text-sm text-status-fault">{words}</span> : null}
    </span>
  );
}
