import { describe, expect, it } from "vitest";
import type { DeepResearchRun, ReportVariant } from "./api";
import {
  currentVariant,
  downloadMismatch,
  literatureState,
  pdfAskable,
  pdfWhy,
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
    expect(variantPdfWhy(variant(pdf("FAILED", "pdf_disabled")))).toContain("není v tomto nasazení");
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
    // The run's own report from an older API that recorded no PDF: it made none.
    expect(pdfWhy(null)).toBe("Tento běh PDF nevytvořil.");
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
    expect(downloadMismatch("ART-1", "ART-1")).toBeNull();
    expect(downloadMismatch("ART-9", "ART-1")).toContain("není koncept");
    expect(downloadMismatch(null, "ART-1")).toContain("není koncept");
  });
});
