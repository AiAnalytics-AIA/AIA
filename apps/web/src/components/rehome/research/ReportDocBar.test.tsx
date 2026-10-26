// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deepResearch, research } from "@/lib/api";
import type { StoredReportDocument } from "@/lib/artifacts/report";
import { saveBlob } from "@/lib/download";
import { ReportExports } from "./ReportDocBar";

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
    fireEvent.click(button(/DOCX/));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(research.downloadReport).toHaveBeenCalledWith("STU-1", "RUN-1");
    fireEvent.click(button(/DOCX/));
    expect((await screen.findByRole("alert")).textContent).toBeTruthy();
    expect(saveBlob).toHaveBeenCalledTimes(1);
  });

  it("offers the PDF only once the server says it exists, saying why not, and asks for it where it can be made", async () => {
    vi.mocked(research.report).mockResolvedValue(status({ state: "NOT_REQUESTED", askable: true }));
    vi.mocked(research.askReportPdf).mockResolvedValue(status({ state: "READY" }));
    vi.mocked(research.downloadReportPdf).mockResolvedValue(file("ART-docx"));
    show();
    expect(await screen.findByText(/PDF: PDF zatím nebylo vyžádáno/)).toBeTruthy();
    expect((button(/^PDF$/) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(await screen.findByRole("button", { name: "Vytvořit PDF" }));
    await waitFor(() => expect((button(/^PDF$/) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button(/^PDF$/));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(research.downloadReportPdf).toHaveBeenCalledWith("STU-1", "RUN-1");
  });

  it("downloads the client report as DOCX only, reading no PDF state", async () => {
    vi.mocked(research.downloadClientReport).mockResolvedValue(file("ART-client"));
    show({ kind: "client", stored: { ...STORED, report_artifact_id: "ART-client" } });
    expect((button(/^PDF$/) as HTMLButtonElement).disabled).toBe(true);
    expect(button(/^PDF$/).getAttribute("title")).toBe("Klientská zpráva je zatím jen DOCX.");
    fireEvent.click(button(/DOCX/));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(research.report).not.toHaveBeenCalled();
  });

  it("downloads the report with literature by its review", async () => {
    vi.mocked(deepResearch.contextReport).mockResolvedValue(status({ state: "READY" }, { deep_research_run_id: "RUN-deep", artifact_id: "ART-context" }));
    vi.mocked(deepResearch.downloadContextReportPdf).mockResolvedValue(file("ART-context"));
    show({ kind: "with_review", review: "RUN-deep", stored: { ...STORED, report_artifact_id: "ART-context" } });
    await waitFor(() => expect((button(/^PDF$/) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(button(/^PDF$/));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(deepResearch.downloadContextReportPdf).toHaveBeenCalledWith("STU-1", "RUN-1", "RUN-deep");
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
    expect(button(/DOCX/)).toBeTruthy();
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

  it("lets a reader who may not act download nothing", async () => {
    show({ canAct: false });
    expect((button(/DOCX/) as HTMLButtonElement).disabled).toBe(true);
  });
});
