// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deepResearch, research } from "@/lib/api";
import type { StoredReportDocument } from "@/lib/artifacts/report";
import { saveBlob } from "@/lib/download";
import { t } from "@/i18n/t";
import { OTHER_VERSION, ReportExports } from "./ReportDocBar";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: {
    report: vi.fn(), downloadReport: vi.fn(), downloadReportPdf: vi.fn(), downloadClientReport: vi.fn(), askReportPdf: vi.fn(),
    downloadReportEditorVersion: vi.fn(),
  },
  deepResearch: { contextReport: vi.fn(), downloadContextReport: vi.fn(), downloadContextReportPdf: vi.fn(), askContextReportPdf: vi.fn(), prepareContextReport: vi.fn() },
}));
vi.mock("@/lib/download", () => ({ saveBlob: vi.fn() }));

const STORED = { run_id: "RUN-1", report_artifact_id: "ART-docx", review_state: "DRAFT_UNAPPROVED" } as StoredReportDocument;
const file = (artifactId: string, reviewState = "DRAFT_UNAPPROVED") =>
  ({ blob: new Blob(["x"]), filename: `${artifactId}.docx`, artifactId, reviewState }) as never;
const status = (pdf: object, more: object = {}) => ({ run_id: "RUN-1", state: "READY", artifact_id: "ART-docx", review_state: "DRAFT_UNAPPROVED", pdf, ...more }) as never;

const show = (props: Partial<Parameters<typeof ReportExports>[0]> = {}) =>
  render(<ReportExports studyId="STU-1" runId="RUN-1" kind="internal" review={null} stored={STORED} canAct {...props} />);
const button = (name: RegExp) => screen.getByRole("button", { name });

beforeEach(() => {
  vi.mocked(research.report).mockResolvedValue(status({ state: "NOT_REQUESTED" }));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("the doc bar's exports (RPT3c)", () => {
  it("downloads the draft on screen as DOCX, and hands over no file that is another version", async () => {
    vi.mocked(research.downloadReport).mockResolvedValueOnce(file("ART-docx")).mockResolvedValueOnce(file("ART-newer"));
    show();
    fireEvent.click(button(/Stáhnout DOCX/));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(research.downloadReport).toHaveBeenCalledWith("STU-1", "RUN-1");
    fireEvent.click(button(/Stáhnout DOCX/));
    expect((await screen.findByRole("alert")).textContent).toBeTruthy();
    expect(saveBlob).toHaveBeenCalledTimes(1);
  });

  it("offers the PDF only once the server says it exists, saying why not, and asks for it where it can be made", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "NOT_REQUESTED", askable: true }));
    vi.mocked(research.askReportPdf).mockResolvedValue(status({ state: "READY" }));
    vi.mocked(research.downloadReportPdf).mockResolvedValue(file("ART-docx"));
    show();
    expect(await screen.findByText(/Proč není PDF: PDF zatím nebylo vyžádáno/)).toBeTruthy();
    expect((button(/Stáhnout PDF/) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(await screen.findByRole("button", { name: "Vytvořit PDF" }));
    await waitFor(() => expect((button(/Stáhnout PDF/) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button(/Stáhnout PDF/));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(research.downloadReportPdf).toHaveBeenCalledWith("STU-1", "RUN-1");
  });

  it("downloads the client report as DOCX only, reading no PDF state", async () => {
    vi.mocked(research.downloadClientReport).mockResolvedValue(file("ART-client"));
    show({ kind: "client", stored: { ...STORED, report_artifact_id: "ART-client" } });
    expect((button(/Stáhnout PDF/) as HTMLButtonElement).disabled).toBe(true);
    expect(button(/Stáhnout PDF/).getAttribute("title")).toBe("Klientská zpráva je zatím jen DOCX.");
    fireEvent.click(button(/Stáhnout DOCX/));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(research.report).not.toHaveBeenCalled();
  });

  it("downloads the report with literature by its review", async () => {
    vi.mocked(deepResearch.contextReport).mockResolvedValue(status({ state: "READY" }, { deep_research_run_id: "RUN-deep", artifact_id: "ART-context" }));
    vi.mocked(deepResearch.downloadContextReportPdf).mockResolvedValue(file("ART-context"));
    show({ kind: "with_review", review: "RUN-deep", stored: { ...STORED, report_artifact_id: "ART-context" } });
    await waitFor(() => expect((button(/Stáhnout PDF/) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button(/Stáhnout PDF/));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(deepResearch.downloadContextReportPdf).toHaveBeenCalledWith("STU-1", "RUN-1", "RUN-deep");
  });

  it("offers no PDF, no ask and no edits from a status that names another version than the one on screen", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "FAILED", askable: true }, {
      artifact_id: "ART-newer", approved_edits: [{ artifact_id: "ART-k9", line_id: "ART-newer", koncept: 9, review_state: "APPROVED_INTERNAL" }],
    }));
    show();
    expect(await screen.findByText(OTHER_VERSION)).toBeTruthy();
    expect((button(/Stáhnout PDF/) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: /Vytvořit PDF/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /koncept 9/ })).toBeNull();
    // The draft on screen still downloads, checked to be itself.
    expect((button(/Stáhnout DOCX/) as HTMLButtonElement).disabled).toBe(false);
  });

  it("says a status read that failed, never that it is still loading", async () => {
    vi.mocked(research.report).mockRejectedValue(new Error("offline"));
    show();
    await waitFor(() => expect(button(/Stáhnout PDF/).getAttribute("title")).toBe("Stav PDF se nepodařilo načíst."));
  });

  it("keeps a report with literature of an earlier composition, says so, prepares it anew, and keeps it when that is refused", async () => {
    const earlier = status({ state: "NOT_REQUESTED" }, { deep_research_run_id: "RUN-deep", artifact_id: "ART-context", contract: "aia-contextual-report-3", contract_current: false });
    vi.mocked(deepResearch.contextReport).mockResolvedValue(earlier);
    vi.mocked(deepResearch.prepareContextReport).mockRejectedValue(new Error("refused"));
    show({ kind: "with_review", review: "RUN-deep", stored: { ...STORED, report_artifact_id: "ART-context" } });
    expect(await screen.findByText(/podle dřívější skladby zprávy \(aia-contextual-report-3\)\. Stáhnout a schválit/)).toBeTruthy();
    fireEvent.click(button(/Připravit znovu podle současné skladby/));
    await waitFor(() => expect(deepResearch.prepareContextReport).toHaveBeenCalledWith("STU-1", "RUN-1", "RUN-deep"));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(button(/Stáhnout DOCX/)).toBeTruthy();
  });

  it("keeps an approved report with literature of an earlier composition the report, and offers no new one", async () => {
    vi.mocked(deepResearch.contextReport).mockResolvedValue(status({ state: "READY" }, {
      deep_research_run_id: "RUN-deep", artifact_id: "ART-context", review_state: "APPROVED_INTERNAL", contract: "aia-contextual-report-3", contract_current: false,
    }));
    show({ kind: "with_review", review: "RUN-deep", stored: { ...STORED, report_artifact_id: "ART-context", review_state: "APPROVED_INTERNAL" } });
    expect(await screen.findByText(/a je schválená: zůstává zprávou této varianty/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Připravit znovu/ })).toBeNull();
  });

  it("downloads each approved edit as itself", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "NOT_REQUESTED" }, {
      approved_edits: [{ artifact_id: "ART-k2", line_id: "ART-docx", koncept: 2, review_state: "APPROVED_INTERNAL" }],
    }));
    vi.mocked(research.downloadReportEditorVersion).mockResolvedValue(file("ART-k2", "APPROVED_INTERNAL"));
    show();
    fireEvent.click(await screen.findByRole("button", { name: /koncept 2/ }));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(research.downloadReportEditorVersion).toHaveBeenCalledWith("STU-1", "RUN-1", "ART-k2");
  });

  it("says what the file carries of its review (D2), the PDF too only where the approval makes one", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "READY" }, { approval_renders_pdf: true }));
    const view = show({ stored: { ...STORED, stamped: true } });
    expect(await screen.findByText(t("research.exec.report.review.fileDraft"))).toBeTruthy();
    vi.mocked(research.report).mockResolvedValue(status({ state: "NOT_REQUESTED", reason: null, askable: true }, { review_state: "APPROVED_INTERNAL" }));
    view.rerender(<ReportExports studyId="STU-1" runId="RUN-1" kind="internal" review={null} canAct stored={{ ...STORED, stamped: true, review_state: "APPROVED_INTERNAL" }} />);
    expect(await screen.findByText(t("research.exec.report.review.fileApprovedDocx"))).toBeTruthy();
    expect(screen.queryByText(/DOCX i PDF/)).toBeNull();
  });

  it("says a version stored before the footer layout keeps its draft footer, approved or not", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "READY" }, { review_state: "APPROVED_INTERNAL" }));
    show({ stored: { ...STORED, stamped: false, review_state: "APPROVED_INTERNAL" } });
    expect(await screen.findByText(t("research.exec.report.review.olderApproved"))).toBeTruthy();
    expect(screen.queryByText(t("research.exec.report.review.older"))).toBeNull();
  });

  it("says what the client report holds, and that a draft is approved here first", async () => {
    show({ kind: "client", stored: { ...STORED, report_artifact_id: "ART-client" } });
    expect(screen.getByText(new RegExp(t("research.exec.results.reportClientHintDraft")))).toBeTruthy();
    cleanup();
    show({ kind: "client", stored: { ...STORED, report_artifact_id: "ART-client", review_state: "APPROVED_INTERNAL" } });
    expect(screen.queryByText(new RegExp(t("research.exec.results.reportClientHintDraft")))).toBeNull();
    expect(screen.getByText(new RegExp(t("research.exec.results.reportClientHint")))).toBeTruthy();
  });

  it("hands over no file whose review is not the one on screen", async () => {
    vi.mocked(research.downloadReport).mockResolvedValue(file("ART-docx", "APPROVED_INTERNAL"));
    show();
    fireEvent.click(button(/Stáhnout DOCX/));
    expect((await screen.findByRole("alert")).textContent).toBe(t("research.exec.report.review.otherState"));
    expect(saveBlob).not.toHaveBeenCalled();
  });

  it("offers no approved edit when none was approved, and hands over no edit file that is not that version, approved", async () => {
    const view = show();
    await waitFor(() => expect(research.report).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: /schválenou úpravu/ })).toBeNull();
    view.unmount();
    vi.mocked(research.report).mockResolvedValue(status({ state: "NOT_REQUESTED" }, {
      approved_edits: [{ artifact_id: "ART-k2", line_id: "ART-docx", koncept: 2, review_state: "APPROVED_INTERNAL" }],
    }));
    vi.mocked(research.downloadReportEditorVersion).mockResolvedValueOnce(file("ART-k3", "APPROVED_INTERNAL")).mockResolvedValueOnce(file("ART-k2", "DRAFT_UNAPPROVED"));
    show();
    fireEvent.click(await screen.findByRole("button", { name: /schválenou úpravu, koncept 2/ }));
    expect((await screen.findByRole("alert")).textContent).toBe(t("research.exec.report.review.otherVersion"));
    fireEvent.click(screen.getByRole("button", { name: /schválenou úpravu, koncept 2/ }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe(t("research.exec.report.review.otherState")));
    expect(saveBlob).not.toHaveBeenCalled();
  });

  it("says why there is no PDF in the server's words: a failed rendering, a deployment that made none", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "FAILED", reason: "pdf_conversion_failed", askable: false }));
    show();
    expect(await screen.findByText(`Proč není PDF: ${t("research.exec.results.reportPdfFailed")}`)).toBeTruthy();
    cleanup();
    vi.mocked(research.report).mockResolvedValue(status({ state: "FAILED", reason: "pdf_disabled", askable: false }));
    show();
    expect(await screen.findByText(/nasazení PDF tehdy nevytvářelo/)).toBeTruthy();
    // Not offered again: in that deployment asking only fails again (cross-review web#2).
    expect(screen.queryByRole("button", { name: /Vytvořit PDF/ })).toBeNull();
  });

  it("says an approved version's PDF was not asked for because its draft's was refused, and offers none", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "NOT_REQUESTED", reason: "pdf_disabled", askable: false }, { review_state: "APPROVED_INTERNAL" }));
    show({ stored: { ...STORED, review_state: "APPROVED_INTERNAL", stamped: true } });
    expect(await screen.findByText(`Proč není PDF: ${t("research.exec.report.review.pdfNotRequestedDisabled")}`)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Vytvořit PDF/ })).toBeNull();
  });

  it.each([
    // Its draft PDF ready, but a delivered study starts no work: approving asks for none.
    ["a closed study whose draft PDF is ready", { approval_renders_pdf: false, pdf: { state: "READY", askable: false } }],
    // A deployment that rendered no PDF: nothing says one ever will be.
    ["a deployment that made no PDF", { pdf: { state: "NOT_REQUESTED", reason: null, askable: true } }],
  ])("promises the approved version's DOCX alone for %s", async (_case, extra) => {
    vi.mocked(research.report).mockResolvedValue(status(extra.pdf, extra));
    show({ stored: { ...STORED, stamped: true } });
    expect(await screen.findByText(t("research.exec.report.review.fileDraftDocx"))).toBeTruthy();
    expect(screen.queryByText(/DOCX i PDF/)).toBeNull();
  });

  it("reads the status again once the version on screen is approved, and follows its approved PDF while it is made", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "READY" }, { approval_renders_pdf: true }));
    const view = show({ stored: { ...STORED, stamped: true } });
    await waitFor(() => expect(research.report).toHaveBeenCalledTimes(1));
    vi.mocked(research.report).mockResolvedValue(status({ state: "RENDERING" }, { review_state: "APPROVED_INTERNAL" }));
    view.rerender(<ReportExports studyId="STU-1" runId="RUN-1" kind="internal" review={null} canAct stored={{ ...STORED, stamped: true, review_state: "APPROVED_INTERNAL" }} />);
    expect(await screen.findByText(new RegExp(t("research.exec.report.review.pdfRendering")))).toBeTruthy();
    // Until that PDF exists the file line names the DOCX alone.
    expect(screen.getByText(t("research.exec.report.review.fileApprovedDocx"))).toBeTruthy();
    // Read again on the approval, and again while its PDF is being made.
    expect(vi.mocked(research.report).mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("says a client report the server refuses, in its words", async () => {
    vi.mocked(research.downloadClientReport).mockRejectedValue(new Error("Žádné číslo tohoto běhu nesplnilo pravidla pro klienta."));
    show({ kind: "client", stored: { ...STORED, report_artifact_id: "ART-client" } });
    fireEvent.click(button(/Stáhnout DOCX/));
    expect((await screen.findByRole("alert")).textContent).toContain("nesplnilo pravidla pro klienta");
  });

  it("offers a reader who may not act no export at all", async () => {
    show({ canAct: false });
    expect(screen.queryByRole("button")).toBeNull();
  });
});
