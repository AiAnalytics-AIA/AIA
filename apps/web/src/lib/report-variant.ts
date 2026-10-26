/**
 * One report variant, one content in DOCX and PDF (research-integrity-report 3).
 *
 * A researcher chooses the run's own report or the report with one completed interpretation
 * review. The card then says what that variant holds, offers both formats of the same stored
 * draft, and approves that draft. Pure: what to show from what the API said.
 */
import { t, tv } from "@/i18n/t";
import type { DeepResearchRun, ReportPdf, ReportPdfState, ReportVariant } from "./api";
import { EXACT, timeWords } from "./report-editor";
import { reviewStatus } from "./report-status";

/** Completed interpretation reviews of this research run, newest first: what a variant may add. */
export function reviewsFor(runs: readonly DeepResearchRun[], researchRunId: string): DeepResearchRun[] {
  return runs.filter(
    (r) => r.purpose === "INTERPRETATION_RESEARCH" && r.target?.research_run_id === researchRunId && r.status === "COMPLETED",
  );
}

/** A completed review as a list names it (RPT12): its title, else when it was started, else its
 *  place in the list (`i`, from 0), never its run id; the doc picker and Varianta share it, so two
 *  reviews of one run are told apart the same way in both. */
export function reviewLabel(r: Pick<DeepResearchRun, "title" | "created_at">, i: number): string {
  if (r.title) return r.title;
  return r.created_at && !Number.isNaN(Date.parse(r.created_at)) ? new Date(r.created_at).toLocaleString("cs-CZ") : `${i + 1}.`;
}

/** The variant as read, only when it is this run's report with the chosen review; else none. */
export function currentVariant(variant: ReportVariant | null, runId: string, review: string | null): ReportVariant | null {
  return variant && review !== null && variant.run_id === runId && variant.deep_research_run_id === review ? variant : null;
}

export type LiteratureState = "in" | "pending" | "excluded";

/** The literature part of the chosen variant: none for the base report, in once its draft exists. */
export function literatureState(review: string | null, variant: ReportVariant | null): LiteratureState {
  if (review === null) return "excluded";
  return variant?.deep_research_run_id === review && variant.state === "READY" ? "in" : "pending";
}

/** Each PDF state the server reports, in the card's words; `null`: ready to download. Total. */
const PDF_WHY: Record<ReportPdfState, string | null> = {
  NOT_REQUESTED: "PDF zatím nebylo vyžádáno.",
  RENDERING: "PDF se právě vytváří ze stejného konceptu jako DOCX.",
  READY: null,
  FAILED: "PDF se nepodařilo vytvořit; zpráva je k dispozici jako DOCX.",
  INVALID: "Uložené PDF neodpovídá této verzi zprávy, a proto se nenabízí; zpráva je k dispozici jako DOCX.",
};
/**
 * A reason the server gives that changes what the person can do, in words. ``pdf_disabled`` says
 * what AIA checked: the worker rendered nothing when it was asked -- never that it still renders
 * nothing, which AIA does not know once an operator may have turned the converter on.
 */
const PDF_REASON: Record<string, string> = {
  study_closed: "Studie je uzavřená, a proto se PDF nevytváří; zpráva je k dispozici jako DOCX.",
  pdf_disabled: "PDF se nevytvořilo, protože toto nasazení PDF tehdy nevytvářelo; zpráva je k dispozici jako DOCX.",
  pdf_corrupt: "Uložené PDF je poškozené, a proto se nenabízí; zpráva je k dispozici jako DOCX.",
  pdf_missing: "Uložené PDF chybí, a proto se nenabízí; zpráva je k dispozici jako DOCX.",
};

/** An approved version's PDF is its own rendering, asked for by the approval (D2): said so. */
const APPROVED_PDF_WHY: Partial<Record<ReportPdfState, string>> = {
  NOT_REQUESTED: "research.exec.report.review.pdfNotRequested",
  RENDERING: "research.exec.report.review.pdfRendering",
};
/**
 * Why an approved version's PDF was never asked for, when the server says: nothing was asked
 * because its draft's own PDF was refused (``pdf_disabled``), said of the draft.
 */
const APPROVED_NOT_REQUESTED_REASON: Record<string, string> = {
  pdf_disabled: "research.exec.report.review.pdfNotRequestedDisabled",
};

/**
 * Why a stored report's PDF (the run's own or a variant's) is not offered, in words; `null`
 * when it is ready to download. An older API's missing record reads as a run that made none.
 * ``approved``: the PDF is the approved version's, never its draft's.
 */
export function pdfWhy(pdf: ReportPdf | null | undefined, approved = false): string | null {
  if (!pdf) return "Tento běh PDF nevytvořil.";
  if (pdf.state === "READY") return null;
  const approvedWords = approved ? APPROVED_PDF_WHY[pdf.state] : undefined;
  const approvedReason = approved && pdf.state === "NOT_REQUESTED" && pdf.reason
    ? APPROVED_NOT_REQUESTED_REASON[pdf.reason]
    : undefined;
  // A state this page does not know is never offered as a download.
  const words = (approvedReason ? t(approvedReason) : undefined)
    ?? (pdf.reason ? PDF_REASON[pdf.reason] : undefined)
    ?? (approvedWords ? t(approvedWords) : undefined)
    ?? (pdf.state in PDF_WHY ? PDF_WHY[pdf.state] : "Stav PDF nelze přečíst; zpráva je k dispozici jako DOCX.");
  // "Znovu" only for a PDF that was asked for before: one never asked for is made the first time.
  if (!pdfAskable(pdf)) return words;
  return pdf.state === "NOT_REQUESTED" ? `${words} Můžete ho nechat vytvořit.` : `${words} Můžete ho nechat vytvořit znovu.`;
}

/** Where the variant's PDF stands, in the card's words; `null` when it is ready to download. */
export function variantPdfWhy(variant: ReportVariant | null): string | null {
  if (!variant || variant.state !== "READY") return "Nejprve připravte zprávu s vybranou rešerší.";
  const approved = reviewStatus(variant.review_state) === "APPROVED";
  return variant.pdf ? pdfWhy(variant.pdf, approved) : PDF_WHY.NOT_REQUESTED;
}

/**
 * Whether a person asking now starts a rendering of the same stored draft: exactly when the
 * server says so (never asked, failed or invalid, on a study that still starts work); a
 * response that does not say is never offered.
 */
export function pdfAskable(pdf: ReportPdf | null | undefined): boolean {
  return pdf?.askable === true;
}

/** The same for a variant: only once its draft is prepared. */
export const variantPdfAskable = (variant: ReportVariant | null): boolean =>
  !!variant && variant.state === "READY" && pdfAskable(variant.pdf);

/** Whether to read the variant again: its PDF is still being made. */
export function variantPending(variant: ReportVariant | null): boolean {
  return !!variant && variant.state === "READY" && variant.pdf?.state === "RENDERING";
}

/** Whether to read the run's own report again: a PDF a person asked for is being made. */
export const reportPdfPending = (pdf: ReportPdf | null | undefined): boolean => pdf?.state === "RENDERING";

/**
 * Whether the card may say a version's PDF states its review too (D2), from what the server said
 * alone: an approved version's once its own PDF is ready; a draft's only where the server says
 * approving it gives the approved version one (``approval_renders_pdf``: approving asks for a PDF
 * and this draft's own was rendered here). A closed study, a deployment without PDF, a PDF still
 * being made or one that failed is no promise (review 4: the card read an unknown as a yes).
 */
export function pdfStatesReview(
  reviewState: string | null | undefined,
  pdf: ReportPdf | null | undefined,
  approvalRendersPdf: boolean | null | undefined,
): boolean {
  return reviewStatus(reviewState) === "APPROVED" ? pdf?.state === "READY" : approvalRendersPdf === true;
}

/** A stored version as the card shows it, or as a download names it (its headers). */
export type VersionSeen = { artifactId: string | null; reviewState: string | null | undefined };

/**
 * Why a downloaded file is not handed over, or null. The server names the stored version its
 * bytes are (or, for a PDF, render) and the review they state; a file that is not the version
 * this card shows and approves -- or names none -- would let a person approve one document and
 * pass on another, and one whose review is not the card's would be passed on as what it is not
 * (D2). A missing review header reads as a draft, never as approved.
 */
export function downloadMismatch(downloaded: VersionSeen, shown: VersionSeen): string | null {
  if (shown.artifactId === null) return null;
  if (downloaded.artifactId !== shown.artifactId) return t("research.exec.report.review.otherVersion");
  if (reviewStatus(downloaded.reviewState) !== reviewStatus(shown.reviewState)) {
    return t("research.exec.report.review.otherState");
  }
  return null;
}

/** ``2026-10-18`` as ``18. 10. 2026``; anything else as it came, never guessed. */
export function czechDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return m ? `${Number(m[3])}. ${Number(m[2])}. ${m[1]}` : iso;
}

/** What the card knows of a stored version's review: the server's words for it. */
export type VersionReview = {
  version: string;
  reviewState: string | null | undefined;
  approvedOn: string | null | undefined;
  /** Whether its file states its review in its footers (D2); ``null``/absent: not known. */
  stamped: boolean | null | undefined;
  /** When it was stored (RPT3d); null/absent: not said. */
  storedAt?: string | null;
};

/**
 * The card's line about a version's review, as its file states it (research-integrity-report D2),
 * or ``null`` when the card cannot say what the file states: a version stored before the footer
 * layout (``stamped`` false: today's sentence about the stored draft applies), one whose layout the
 * server did not say, or an approval without its date. ``pdf``: whether this version's PDF states
 * it too (``pdfStatesReview``; the client report is DOCX only).
 */
export function reviewLine(review: VersionReview, pdf: boolean): string | null {
  if (review.stamped !== true) return null;
  if (reviewStatus(review.reviewState) === "APPROVED") {
    if (!review.approvedOn) return null;
    const key = pdf ? "approved" : "approvedDocx";
    return tv(`research.exec.report.review.${key}`, { date: czechDate(review.approvedOn), version: review.version });
  }
  return tv(`research.exec.report.review.${pdf ? "draft" : "draftDocx"}`, { version: review.version });
}

/** What a draft's file carries, as the approval question says it (D2, RPT3d): reviewLine's
 *  sentence without the version's id, which the question names by its time; null where the card
 *  would say nothing, and for an approved version, which is not asked about. */
export function fileLine(review: VersionReview, pdf: boolean): string | null {
  if (review.stamped !== true || reviewStatus(review.reviewState) === "APPROVED") return null;
  return t(`research.exec.report.review.${pdf ? "fileDraft" : "fileDraftDocx"}`);
}

/**
 * The question a person answers before approving (input-interactions B22, Q33, artifact-report RPT3,
 * RPT3d): the document by name, when its version was stored and its format, what the approval records
 * and hands over, that it cannot be undone, and on the client report that its numbers are modelled.
 * A version is named by its time, never its id; a time the server did not give is left out, never
 * guessed. What the file will carry is the card's own line (reviewLine), never promised here.
 */
export function approvalQuestion(
  name: string,
  { storedAt = null, pdf = false, modelled = false }: { storedAt?: string | null; pdf?: boolean; modelled?: boolean } = {},
): string {
  const k = "research.exec.report.approveAsk";
  return [
    tv(`${k}.question`, { what: name, when: storedAt ? tv(`${k}.storedAt`, { at: timeWords(storedAt) }) : "", format: t(`${k}.${pdf ? "docxPdf" : "docx"}`) }),
    EXACT,
    t(`${k}.final`),
    modelled ? t(`${k}.modelled`) : "",
  ].filter(Boolean).join(" ");
}
