// @vitest-environment jsdom
// Zpráva's pane with the report editor (artifact-report RPT8d): which documents are handed to the
// editor (never the client report), by which variant, and that the doc bar approves only the
// version on screen. The editor itself is stubbed here: it reports the version it shows.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type ReactNode, useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { deepResearch, research, type ResearchRun } from "@/lib/api";
import type { ReportDocumentModel, StoredReportDocument } from "@/lib/artifacts/report";
import { StudyFrameProvider } from "./frame";
import { ReportDocumentView } from "./ReportDocumentView";
import { TEST_FRAME } from "./test-frame";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: { reportDocument: vi.fn(), clientReportDocument: vi.fn(), prepareClientReport: vi.fn(), approveReport: vi.fn(), report: vi.fn(), openReportEditor: vi.fn() },
  deepResearch: { runs: vi.fn(), contextReport: vi.fn(), contextReportDocument: vi.fn(), prepareContextReport: vi.fn() },
}));

type Handed = { variant: string; review: string | null };
const editor = vi.hoisted(() => ({ handed: [] as { variant: string; review: string | null }[], shows: null as string | null }));

vi.mock("./ReportEditor", () => ({
  ReportEditor: ({ variant, review, children, onShown }: { variant: string; review: string | null; children: ReactNode; onShown?: (v: string | null) => void }) => {
    useEffect(() => {
      editor.handed.push({ variant, review });
      onShown?.(editor.shows);
    }, [variant, review, onShown]);
    return <div data-stub-editor={variant}>{children}</div>;
  },
}));

const DOC = JSON.parse(
  readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/report_document/internal.json"), "utf8"),
) as ReportDocumentModel;
const STORED: StoredReportDocument = {
  run_id: "RUN-1", artifact_id: "ART-doc", sha256: "a".repeat(64), report_artifact_id: "ART-docx",
  report_sha256: "b".repeat(64), review_state: "DRAFT_UNAPPROVED", approved_on: null, stamped: false, document: DOC,
};
const modelled = () => ({
  run_id: "RUN-1",
  steps: [
    { node_key: "run", kind: "research_fieldwork", status: "SUCCEEDED", data_origin: "MODELLED_AI_PANEL", data_origin_kind: "MODELLED" },
    { node_key: "report", kind: "research_report", status: "SUCCEEDED", artifact_id: "ART-docx" },
  ],
}) as unknown as ResearchRun;
const show = (run: ResearchRun = modelled()) =>
  render(<StudyFrameProvider frame={TEST_FRAME}><ReportDocumentView run={run} /></StudyFrameProvider>);
const bar = (c: HTMLElement) => c.querySelector("[data-report-docbar]") as HTMLElement;

beforeEach(() => {
  editor.handed = [];
  editor.shows = null;
  vi.mocked(deepResearch.runs).mockResolvedValue([]);
  vi.mocked(research.reportDocument).mockResolvedValue(STORED);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("which document the editor is handed", () => {
  it("is never the client report", async () => {
    const CLIENT: StoredReportDocument = { ...STORED, report_artifact_id: "ART-client", document: { ...DOC, meta: { ...DOC.meta, kind: "client" } } };
    vi.mocked(research.clientReportDocument).mockResolvedValue(CLIENT);
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    await waitFor(() => expect(editor.handed).toEqual<Handed[]>([{ variant: "internal", review: null }]));
    fireEvent.click(screen.getByRole("button", { name: "Klientská zpráva" }));
    await waitFor(() => expect(bar(container).textContent).toContain("ART-client"));
    expect(container.querySelector("[data-stub-editor]")).toBeNull();
    expect(screen.getByRole("article", { name: "Koncept zprávy" })).toBeTruthy();
    expect(editor.handed.every((h) => h.variant === "internal")).toBe(true);
  });

  it("is the report with literature by its review", async () => {
    const REVIEW = { run_id: "RUN-deep", purpose: "INTERPRETATION_RESEARCH", target: { research_run_id: "RUN-1" }, status: "COMPLETED", title: "Fiktivní rešerše" };
    vi.mocked(deepResearch.runs).mockResolvedValue([REVIEW] as never);
    vi.mocked(deepResearch.contextReportDocument).mockResolvedValue({ ...STORED, report_artifact_id: "ART-context" });
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    fireEvent.click(await screen.findByRole("button", { name: "Zpráva s rešerší" }));
    await waitFor(() => expect(bar(container).textContent).toContain("ART-context"));
    expect(editor.handed).toContainEqual({ variant: "context", review: "RUN-deep" });
  });
});

describe("approving from the doc bar while the editor is open", () => {
  it("is not offered for the composed draft while the editor shows a later version", async () => {
    editor.shows = "ART-edit";
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    await waitFor(() => expect(container.querySelector("[data-approval-edited]")).not.toBeNull());
    expect(within(bar(container)).queryByRole("button", { name: /^Schválit/ })).toBeNull();
    expect(research.approveReport).not.toHaveBeenCalled();
  });

  it("is not offered while the editor shows koncept 1 either: an edit saved there moves it past the draft", async () => {
    editor.shows = "ART-docx";
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    await waitFor(() => expect(container.querySelector("[data-approval-edited]")).not.toBeNull());
    expect(within(bar(container)).queryByRole("button", { name: /^Schválit/ })).toBeNull();
  });

  it("is offered as before while the editor shows nothing (off, or not answering)", async () => {
    editor.shows = null;
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(await within(bar(container)).findByRole("button", { name: /^Schválit/ })).toBeTruthy();
  });
});
