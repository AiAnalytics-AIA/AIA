import { describe, expect, it } from "vitest";
import { attachmentName, type DeepResearchRun, type ReportVariant } from "./api";
import {
  currentVariant,
  czechDate,
  downloadMismatch,
  literatureState,
  pdfAskable,
  pdfStatesReview,
  pdfWhy,
  reviewLine,
  reviewsFor,
  variantPdfAskable,
  variantPdfWhy,
  variantPending,
} from "./report-variant";

const review = (id: string, status: string, target = "RUN-r1", purpose = "INTERPRETATION_RESEARCH") =>
  ({ run_id: id, status, purpose, target: { research_run_id: target } }) as unknown as DeepResearchRun;
const variant = (pdf: ReportVariant["pdf"], state: ReportVariant["state"] = "READY", deep = "RUN-d1"): ReportVariant => ({
  run_id: "RUN-r1", deep_research_run_id: deep, state, artifact_id: "ART-1", internal_only: true, pdf,
});
const pdf = (state: NonNullable<ReportVariant["pdf"]>["state"], reason: string | null = null) => ({
  state, artifact_id: state === "READY" ? "ART-2" : null, size_bytes: state === "READY" ? 9 : null, reason,
});

describe("report variant (research-integrity-report 3)", () => {
  it("offers only completed interpretation reviews of this run", () => {
    const runs = [review("RUN-d1", "COMPLETED"), review("RUN-d2", "RUNNING"), review("RUN-d3", "COMPLETED", "RUN-other"), review("RUN-d4", "COMPLETED", "RUN-r1", "DESIGN_RESEARCH")];
    expect(reviewsFor(runs, "RUN-r1").map((r) => r.run_id)).toEqual(["RUN-d1"]);
  });

  it("reads a variant only as the chosen review's report of this run", () => {
    const d1 = variant(null);
    expect(currentVariant(d1, "RUN-r1", "RUN-d1")).toBe(d1);
    // A read still answering for the review the person left is never the new choice's draft.
    expect(currentVariant(d1, "RUN-r1", "RUN-d2")).toBeNull();
    expect(currentVariant(d1, "RUN-other", "RUN-d1")).toBeNull();
    expect(currentVariant(d1, "RUN-r1", null)).toBeNull();
  });

  it("says the base report has no literature, and the variant has it once its draft exists", () => {
    expect(literatureState(null, null)).toBe("excluded");
    expect(literatureState("RUN-d1", variant(null, "NOT_PREPARED"))).toBe("pending");
    expect(literatureState("RUN-d1", variant(null))).toBe("in");
    expect(literatureState("RUN-d9", variant(null))).toBe("pending"); // another review's draft
  });

  it("offers the PDF only when it renders the variant's own draft, and words every server state", () => {
    expect(variantPdfWhy(variant(pdf("READY")))).toBeNull();
    expect(variantPdfWhy(variant(pdf("RENDERING")))).toContain("vytváří");
    expect(variantPdfWhy(variant(pdf("NOT_REQUESTED")))).toContain("nebylo vyžádáno");
    expect(variantPdfWhy(variant(pdf("FAILED", "pdf_conversion_failed")))).toContain("nepodařilo");
    expect(variantPdfWhy(variant(pdf("FAILED", "pdf_disabled")))).toContain("tehdy nevytvářelo");
    expect(variantPdfWhy(variant(pdf("INVALID", "pdf_not_this_report")))).toContain("neodpovídá");
    expect(variantPdfWhy(variant(pdf("INVALID", "pdf_corrupt")))).toContain("poškozené");
    expect(variantPdfWhy(variant(pdf("NOT_REQUESTED", "study_closed")))).toContain("uzavřená");
    expect(variantPdfWhy(variant(null, "NOT_PREPARED"))).toContain("připravte");
    // A state this page does not know is never a download.
    expect(variantPdfWhy(variant({ ...pdf("READY"), state: "SOMETHING" as never }))).toContain("nelze přečíst");
  });

  it("says a new rendering can be asked for exactly when the server says so", () => {
    const failed = { ...pdf("FAILED", "pdf_conversion_failed"), askable: true };
    expect(pdfWhy(failed)).toContain("Můžete ho nechat vytvořit znovu.");
    expect(pdfWhy({ ...failed, askable: false })).not.toContain("znovu");
    // Never asked for: it is made, not made again.
    expect(pdfWhy({ ...pdf("NOT_REQUESTED"), askable: true })).toBe("PDF zatím nebylo vyžádáno. Můžete ho nechat vytvořit.");
    expect(pdfWhy({ ...pdf("NOT_REQUESTED"), askable: true }, true)).toBe(
      "PDF schválené verze zatím nebylo vyžádáno. Můžete ho nechat vytvořit.",
    );
    // The run's own report from an older API that recorded no PDF: it made none.
    expect(pdfWhy(null)).toBe("Tento běh PDF nevytvořil.");
  });

  it("never offers again a PDF a worker without a converter refused, and says it was refused then", () => {
    // Cross-review web#2: "PDF není v tomto nasazení zapnuté … Můžete ho nechat vytvořit znovu".
    const disabled = { ...pdf("FAILED", "pdf_disabled"), askable: false };
    // What AIA checked is that the worker rendered nothing when it was asked, never that it
    // still does not: an operator may have turned the converter on since.
    expect(pdfWhy(disabled)).toBe("PDF se nevytvořilo, protože toto nasazení PDF tehdy nevytvářelo; zpráva je k dispozici jako DOCX.");
    expect(pdfWhy(disabled)).not.toContain("není v tomto nasazení");
    expect(pdfWhy(disabled, true)).not.toContain("znovu");
    expect(variantPdfAskable(variant(disabled))).toBe(false);
    // An approved version's PDF was never asked for: its draft's refusal is why, said of the draft.
    const approvedNever = { ...pdf("NOT_REQUESTED", "pdf_disabled"), askable: false };
    expect(pdfWhy(approvedNever, true)).toBe(
      "PDF schválené verze nebylo vyžádáno: PDF jejího konceptu se nevytvořilo, protože toto nasazení PDF tehdy nevytvářelo; zpráva je k dispozici jako DOCX.",
    );
    expect(pdfWhy(approvedNever, true)).not.toContain("Můžete");
  });

  it("calls a PDF that does not match a version, never a draft, what it is", () => {
    // Cross-review web#10: an approved version's invalid PDF read "neodpovídá tomuto konceptu".
    for (const approved of [false, true]) {
      const why = pdfWhy(pdf("INVALID", "pdf_not_this_report"), approved);
      expect(why).toContain("neodpovídá této verzi zprávy");
      expect(why).not.toContain("koncept");
    }
  });

  it("asks for a PDF again only when the server would start a rendering", () => {
    expect(variantPdfAskable(variant({ ...pdf("FAILED", "pdf_conversion_failed"), askable: true }))).toBe(true);
    expect(variantPdfAskable(variant({ ...pdf("INVALID", "pdf_corrupt"), askable: true }))).toBe(true);
    // The server's no is final: a closed study, a ready or rendering PDF, or an older API.
    expect(variantPdfAskable(variant({ ...pdf("NOT_REQUESTED", "study_closed"), askable: false }))).toBe(false);
    expect(variantPdfAskable(variant(pdf("FAILED", "pdf_conversion_failed")))).toBe(false);
    expect(variantPdfAskable(variant(null))).toBe(false);
    expect(variantPdfAskable(variant({ ...pdf("NOT_REQUESTED"), askable: true }, "NOT_PREPARED"))).toBe(false);
    expect(pdfAskable({ ...pdf("NOT_REQUESTED"), askable: true })).toBe(true);
  });

  it("reads again only while the PDF is being made", () => {
    expect(variantPending(variant(pdf("RENDERING")))).toBe(true);
    expect(variantPending(variant(pdf("READY")))).toBe(false);
    expect(variantPending(variant(pdf("FAILED", "x")))).toBe(false);
  });

  it("hands over a file only when it is the draft the card shows and approves", () => {
    const seen = (artifactId: string | null, reviewState: string | null = "DRAFT_UNAPPROVED") => ({ artifactId, reviewState });
    expect(downloadMismatch(seen("ART-1"), seen("ART-1"))).toBeNull();
    // A version, not "a draft": the card may show an approved one (cross-review web#10).
    expect(downloadMismatch(seen("ART-9"), seen("ART-1"))).toContain("není verze");
    expect(downloadMismatch(seen(null), seen("ART-1", "APPROVED_INTERNAL"))).toContain("není verze");
    expect(downloadMismatch(seen("ART-9"), seen("ART-1"))).not.toContain("koncept");
    // D2: the version the card shows, in the review it shows -- approved since, or not yet.
    expect(downloadMismatch(seen("ART-1", "APPROVED_INTERNAL"), seen("ART-1"))).toContain("jiný stav schválení");
    expect(downloadMismatch(seen("ART-1"), seen("ART-1", "APPROVED_INTERNAL"))).toContain("jiný stav schválení");
    expect(downloadMismatch(seen("ART-1", "APPROVED_INTERNAL"), seen("ART-1", "APPROVED_INTERNAL"))).toBeNull();
    // A review header not sent reads as a draft, never as approved.
    expect(downloadMismatch(seen("ART-1", null), seen("ART-1"))).toBeNull();
    expect(downloadMismatch(seen("ART-1", null), seen("ART-1", "APPROVED_INTERNAL"))).toContain("jiný stav schválení");
    expect(downloadMismatch(seen("ART-1"), seen(null))).toBeNull(); // nothing shown yet
  });

  it("says what a version's file states only from what the server said (D2)", () => {
    const review = { version: "ART-1", reviewState: "DRAFT_UNAPPROVED", approvedOn: null, stamped: true };
    expect(reviewLine(review, true)).toBe(
      "Stav: Koncept · verze ART-1 — soubor nese v zápatí „KONCEPT — NESCHVÁLENO“; po schválení ponese DOCX i PDF této verze „SCHVÁLENO“ s datem.",
    );
    expect(reviewLine(review, false)).toContain("po schválení ponese DOCX této verze");
    const approved = { ...review, reviewState: "APPROVED_INTERNAL", approvedOn: "2026-10-08" };
    // "Stav:" like every other state line (cross-review web#10).
    expect(reviewLine(approved, true)).toBe("Stav: Schváleno 8. 10. 2026 · verze ART-1 — DOCX i PDF této verze to nesou v zápatí");
    expect(reviewLine(approved, false)).toBe("Stav: Schváleno 8. 10. 2026 · verze ART-1 — DOCX této verze to nese v zápatí");
    // Stored before the footer layout, or not said: the card claims nothing about the footers.
    expect(reviewLine({ ...approved, stamped: false }, true)).toBeNull();
    expect(reviewLine({ ...review, stamped: undefined }, true)).toBeNull();
    // Approved without its date: the line would print a guess.
    expect(reviewLine({ ...approved, approvedOn: null }, true)).toBeNull();
  });

  it("says a version's PDF states its review only from what the server said (review 4)", () => {
    // A draft: only where the server says approving gives the approved version a PDF.
    expect(pdfStatesReview("DRAFT_UNAPPROVED", pdf("READY"), true)).toBe(true);
    expect(pdfStatesReview("DRAFT_UNAPPROVED", pdf("READY"), false)).toBe(false); // e.g. a closed study
    expect(pdfStatesReview("DRAFT_UNAPPROVED", pdf("NOT_REQUESTED"), undefined)).toBe(false); // not said
    expect(pdfStatesReview(undefined, pdf("READY"), null)).toBe(false);
    // Approved: only once its own PDF exists.
    expect(pdfStatesReview("APPROVED_INTERNAL", pdf("READY"), false)).toBe(true);
    for (const state of ["RENDERING", "FAILED", "INVALID", "NOT_REQUESTED"] as const) {
      expect(pdfStatesReview("APPROVED_INTERNAL", pdf(state), true)).toBe(false);
    }
    expect(pdfStatesReview("APPROVED_INTERNAL", null, true)).toBe(false);
  });

  it("writes a date as Czech reads it, and anything else as it came", () => {
    expect(czechDate("2026-10-18")).toBe("18. 10. 2026");
    expect(czechDate("2026-01-05")).toBe("5. 1. 2026");
    expect(czechDate("18.10.2026")).toBe("18.10.2026");
  });

  it("says an approved version's PDF is its own, being made or not yet asked for", () => {
    expect(pdfWhy(pdf("RENDERING"), true)).toContain("PDF schválené verze se právě vytváří");
    expect(pdfWhy(pdf("NOT_REQUESTED"), true)).toContain("PDF schválené verze zatím nebylo vyžádáno");
    expect(pdfWhy(pdf("RENDERING"))).toContain("ze stejného konceptu");
    // A reason the server gives still decides the words.
    expect(pdfWhy(pdf("NOT_REQUESTED", "study_closed"), true)).toContain("uzavřená");
    const approvedVariant = { ...variant(pdf("RENDERING")), review_state: "APPROVED_INTERNAL" as const };
    expect(variantPdfWhy(approvedVariant)).toContain("schválené verze");
  });

  it("reads the file name the server gives a download", () => {
    expect(attachmentName('attachment; filename="AIA-STU-1-RUN-1-zakladni-ART-1-schvaleno.docx"'))
      .toBe("AIA-STU-1-RUN-1-zakladni-ART-1-schvaleno.docx");
    expect(attachmentName("attachment")).toBeNull();
    expect(attachmentName(null)).toBeNull();
  });
});
