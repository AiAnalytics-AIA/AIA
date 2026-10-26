// @vitest-environment jsdom
// The report card after an edited version is approved in the pane (artifact-report RPT8d): the
// composed draft stays a draft, so the approved edit is downloaded as itself, never the draft.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deepResearch, research, type ResearchReport, type ResearchRun } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { CompleteReport } from "./CompleteReport";
import { StudyFrameProvider } from "./frame";
import { TEST_FRAME } from "./test-frame";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: { report: vi.fn(), clientReportDocument: vi.fn(), downloadReport: vi.fn(), downloadReportEditorVersion: vi.fn() },
  deepResearch: { runs: vi.fn(), contextReport: vi.fn() },
}));
vi.mock("@/lib/download", () => ({ saveBlob: vi.fn() }));

const RUN = {
  run_id: "RUN-1",
  steps: [
    { node_key: "run", kind: "research_fieldwork", status: "SUCCEEDED", data_origin: "SYNTHETIC_FIXTURE", data_origin_kind: "SIMULATED" },
    { node_key: "report", kind: "research_report", status: "SUCCEEDED", artifact_id: "ART-docx" },
  ],
} as unknown as ResearchRun;
const REPORT: ResearchReport = {
  run_id: "RUN-1", state: "READY", internal_only: true, review_state: "DRAFT_UNAPPROVED", artifact_id: "ART-docx",
  approved_edits: [{ artifact_id: "ART-edit", line_id: "ART-docx", koncept: 2, review_state: "APPROVED_INTERNAL", approved_on: "2026-10-24", stamped: true }],
};
const show = () => render(<StudyFrameProvider frame={TEST_FRAME}><CompleteReport run={RUN} /></StudyFrameProvider>);
const blob = new Blob(["docx"]);

beforeEach(() => {
  vi.mocked(deepResearch.runs).mockResolvedValue([]);
  vi.mocked(research.report).mockResolvedValue(REPORT);
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("an approved edit on the report card", () => {
  it("is downloaded as itself, approved, beside the composed draft", async () => {
    vi.mocked(research.downloadReportEditorVersion).mockResolvedValue({ blob, artifactId: "ART-edit", sha256: null, reviewState: "APPROVED_INTERNAL", filename: "AIA-koncept-2-schvaleno.docx" });
    show();
    fireEvent.click(await screen.findByRole("button", { name: /Stáhnout schválenou úpravu, koncept 2/ }));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(blob, "AIA-koncept-2-schvaleno.docx"));
    expect(research.downloadReportEditorVersion).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-edit");
    expect(research.downloadReport).not.toHaveBeenCalled();
  });

  it("hands over no file that is not that version, approved", async () => {
    vi.mocked(research.downloadReportEditorVersion).mockResolvedValue({ blob, artifactId: "ART-other", sha256: null, reviewState: "APPROVED_INTERNAL", filename: null });
    show();
    fireEvent.click(await screen.findByRole("button", { name: /Stáhnout schválenou úpravu, koncept 2/ }));
    await waitFor(() => expect(research.downloadReportEditorVersion).toHaveBeenCalled());
    await waitFor(() => expect(screen.getAllByRole("alert").length).toBeGreaterThan(0));
    expect(saveBlob).not.toHaveBeenCalled();
  });

  it("is not offered when no edit was approved", async () => {
    vi.mocked(research.report).mockResolvedValue({ ...REPORT, approved_edits: [] });
    show();
    await screen.findByRole("button", { name: "Stáhnout zprávu" });
    expect(screen.queryByRole("button", { name: /schválenou úpravu/ })).toBeNull();
  });
});
