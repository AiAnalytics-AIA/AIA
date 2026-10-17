/**
 * One report variant, one content in DOCX and PDF (research-integrity-report 3).
 *
 * A researcher chooses the run's own report or the report with one completed interpretation
 * review. The card then says what that variant holds, offers both formats of the same stored
 * draft, and approves that draft. Pure: what to show from what the API said.
 */
import type { DeepResearchRun, ReportPdf, ReportPdfState, ReportVariant } from "./api";

/** Completed interpretation reviews of this research run, newest first: what a variant may add. */
export function reviewsFor(runs: readonly DeepResearchRun[], researchRunId: string): DeepResearchRun[] {
  return runs.filter(
    (r) => r.purpose === "INTERPRETATION_RESEARCH" && r.target?.research_run_id === researchRunId && r.status === "COMPLETED",
  );
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
  INVALID: "Uložené PDF neodpovídá tomuto konceptu, a proto se nenabízí; zpráva je k dispozici jako DOCX.",
};
/** A reason the server gives that changes what the person can do, in words. */
const PDF_REASON: Record<string, string> = {
  study_closed: "Studie je uzavřená, a proto se PDF nevytváří; zpráva je k dispozici jako DOCX.",
  pdf_disabled: "PDF není v tomto nasazení zapnuté; zpráva je k dispozici jako DOCX.",
  pdf_corrupt: "Uložené PDF je poškozené, a proto se nenabízí; zpráva je k dispozici jako DOCX.",
  pdf_missing: "Uložené PDF chybí, a proto se nenabízí; zpráva je k dispozici jako DOCX.",
};

/**
 * Why a stored report's PDF (the run's own or a variant's) is not offered, in words; `null`
 * when it is ready to download. An older API's missing record reads as a run that made none.
 */
export function pdfWhy(pdf: ReportPdf | null | undefined): string | null {
  if (!pdf) return "Tento běh PDF nevytvořil.";
  if (pdf.state === "READY") return null;
  // A state this page does not know is never offered as a download.
  const words = (pdf.reason ? PDF_REASON[pdf.reason] : undefined)
    ?? (pdf.state in PDF_WHY ? PDF_WHY[pdf.state] : "Stav PDF nelze přečíst; zpráva je k dispozici jako DOCX.");
  return pdfAskable(pdf) ? `${words} Můžete ho nechat vytvořit znovu.` : words;
}

/** Where the variant's PDF stands, in the card's words; `null` when it is ready to download. */
export function variantPdfWhy(variant: ReportVariant | null): string | null {
  if (!variant || variant.state !== "READY") return "Nejprve připravte zprávu s vybranou rešerší.";
  return variant.pdf ? pdfWhy(variant.pdf) : PDF_WHY.NOT_REQUESTED;
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
 * Why a downloaded file is not handed over, or null. The server names the stored draft its bytes
 * are (or, for a PDF, render); a file that is not the draft this card shows and approves -- or
 * names none -- would let a person approve one document and pass on another.
 */
export function downloadMismatch(downloaded: string | null, shown: string | null): string | null {
  if (shown === null) return null;
  if (downloaded === shown) return null;
  return "Stažený soubor není koncept, který karta ukazuje (mezitím vznikl jiný). Obnovte stránku a stáhněte ho znovu.";
}
