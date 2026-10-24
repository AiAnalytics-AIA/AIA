// @vitest-environment jsdom
// Zpráva's pane with the report editor (artifact-report RPT8d): which documents are handed to the
// editor (never the client report), by which variant, and that the doc bar approves only the
// version on screen. The editor itself is stubbed here: it reports the version it shows.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type ReactNode, useEffect } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { deepResearch, research, type ResearchRun } from "@/lib/api";
import type { ReportDocumentModel, StoredReportDocument } from "@/lib/artifacts/report";
import type { EditorOpened, EditorVersionRead } from "@/lib/report-editor";
import type { EditorShown } from "./ReportEditor";
import { StudyFrameProvider } from "./frame";
import { ReportDocumentView } from "./ReportDocumentView";
import { TEST_FRAME } from "./test-frame";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: { reportDocument: vi.fn(), clientReportDocument: vi.fn(), prepareClientReport: vi.fn(), approveReport: vi.fn(), report: vi.fn(), openReportEditor: vi.fn(), reportEditorVersion: vi.fn() },
  deepResearch: { runs: vi.fn(), contextReport: vi.fn(), contextReportDocument: vi.fn(), prepareContextReport: vi.fn() },
}));

type Handed = { variant: string; review: string | null; line?: string | null };
const editor = vi.hoisted(() => ({
  handed: [] as { variant: string; review: string | null; line?: string | null }[],
  shows: null as EditorShown | null,
  /** What the editor shows later: an edit starting, say. */
  emit: (() => undefined) as (shown: EditorShown | null) => void,
}));

vi.mock("./ReportEditor", () => ({
  ReportEditor: ({ variant, review, line, children, onShown }: { variant: string; review: string | null; line?: string | null; children: ReactNode; onShown?: (v: EditorShown | null) => void }) => {
    useEffect(() => {
      editor.handed.push(line ? { variant, review, line } : { variant, review });
      onShown?.(editor.shows);
      editor.emit = (shown) => onShown?.(shown);
    }, [variant, review, line, onShown]);
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

// jsdom has <dialog> without showModal/close: the modal's open state, as a browser sets it.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute("open");
  };
});

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
    // The editor is handed the document by an effect after the bar names it: waited for, never
    // read in the same tick (it raced on a loaded CI runner).
    await waitFor(() => expect(editor.handed).toContainEqual({ variant: "context", review: "RUN-deep" }));
  });
});

const OPENED: EditorOpened = {
  document_server: "https://docs.aia.example.test", config: { token: "signed" }, line_id: "ART-docx", koncept: 2,
  version_artifact_id: "ART-edit", problem: null,
  lines: [
    { line_id: "ART-docx", koncept: 2, version_artifact_id: "ART-edit", saved_at: "2026-10-23T20:10:00+00:00", current_composition: true },
    { line_id: "ART-older", koncept: 4, version_artifact_id: "ART-older-4", saved_at: "2026-10-20T08:00:00+00:00", current_composition: false },
  ],
};
const version = (over: Partial<EditorVersionRead> = {}): EditorVersionRead => ({
  version_artifact_id: "ART-edit", line_id: "ART-docx", koncept: 2, edited_from: "ART-docx", author_names: ["Jana Výzkumná"],
  saved_at: "2026-10-23T20:10:00+00:00", review_state: "DRAFT_UNAPPROVED", approved_on: null, approval: null,
  changes: { uncomparable: null, changes: [{ kind: "changed", tag: "trust_total", was: "42,5 %", now: "50 %", paragraph: null }] },
  newest_in_line: { version_artifact_id: "ART-edit", koncept: 2 },
  edits: { saved: true, reason: null },
  ...over,
});
const versions = (...list: EditorVersionRead[]) =>
  vi.mocked(research.reportEditorVersion).mockImplementation(async (_s, _r, id) => {
    const found = list.find((v) => v.version_artifact_id === id);
    if (!found) throw new Error(`no ${id}`);
    return found;
  });
const editorBar = (c: HTMLElement) => c.querySelector("[data-editor-docbar]") as HTMLElement;
/** The editor's doc bar once it is on screen. */
const shownBar = (c: HTMLElement) => waitFor(() => {
  const found = editorBar(c);
  if (!found) throw new Error("no editor doc bar yet");
  return found;
});

describe("the doc bar while the editor shows the document", () => {
  it("names the version on screen and who saved it, never the composed draft's approval", async () => {
    editor.shows = { opened: OPENED, startedAt: null, dirty: false, seen: () => null };
    versions(version());
    const { container } = show();
    await waitFor(() => expect(editorBar(container)?.textContent).toContain("Koncept 2, uložen 23. 10. 2026 22:10 · Jana Výzkumná"));
    expect(within(bar(container)).queryByRole("button", { name: "Schválit pro interní použití" })).toBeNull();
    expect(bar(container).textContent).not.toContain("ART-docx");
  });

  it("lists what the version changed under Upraveno ručně", async () => {
    editor.shows = { opened: OPENED, startedAt: null, dirty: false, seen: () => null };
    versions(version());
    const { container } = show();
    const toggle = await within(container).findByRole("button", { name: "Upraveno ručně: 1 číslo" });
    expect(container.querySelector("[data-editor-changes]")).toBeNull();
    fireEvent.click(toggle);
    expect(container.querySelector("[data-editor-changes]")?.textContent).toBe("Číslo trust_total: 42,5 % → 50 %");
  });

  it("approves the edited version as itself, its changes named in the question", async () => {
    editor.shows = { opened: OPENED, startedAt: null, dirty: false, seen: () => null };
    versions(version());
    vi.mocked(research.approveReport).mockResolvedValue({ run_id: "RUN-1", artifact_id: "ART-edit", review_state: "APPROVED_INTERNAL", approved_on: "2026-10-23", stamped: true, approval: null, internal_only: true } as never);
    const heard: unknown[] = [];
    const on = (e: Event) => heard.push((e as CustomEvent).detail);
    window.addEventListener("aia:report-approved", on);
    const { container } = show();
    fireEvent.click(await within(await shownBar(container)).findByRole("button", { name: "Schválit koncept 2" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("Schválit interní zprávu, koncept 2 (ART-edit)?");
    expect(dialog.textContent).toContain("Číslo trust_total: 42,5 % → 50 %");
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" }));
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-edit", "", true, null));
    await waitFor(() => expect(heard).toContainEqual(expect.objectContaining({ artifactId: "ART-edit", kind: "internal" })));
    window.removeEventListener("aia:report-approved", on);
  });

  it("asks again when a later save exists, approving nothing", async () => {
    editor.shows = { opened: OPENED, startedAt: null, dirty: false, seen: () => null };
    versions(version());
    const { container } = show();
    const button = await within(await shownBar(container)).findByRole("button", { name: "Schválit koncept 2" });
    versions(version({ newest_in_line: { version_artifact_id: "ART-edit-3", koncept: 3 } }), version({ version_artifact_id: "ART-edit-3", koncept: 3, newest_in_line: { version_artifact_id: "ART-edit-3", koncept: 3 } }));
    fireEvent.click(button);
    expect(await within(await shownBar(container)).findByRole("alert")).toHaveProperty("textContent", "Editor mezitím uložil koncept 3; zkontrolujte jeho změny a schvalte znovu.");
    expect(await within(await shownBar(container)).findByRole("button", { name: "Schválit koncept 3" })).toBeTruthy();
    expect(research.approveReport).not.toHaveBeenCalled();
  });

  it("approves koncept 1, the composed draft, through the pane's own question", async () => {
    editor.shows = { opened: { ...OPENED, koncept: 1, version_artifact_id: "ART-docx", lines: [] }, startedAt: null, dirty: false, seen: () => null };
    versions(version({ version_artifact_id: "ART-docx", koncept: 1, changes: null, edited_from: null, newest_in_line: { version_artifact_id: "ART-docx", koncept: 1 } }));
    vi.mocked(research.report).mockResolvedValue({ artifact_id: "ART-docx", review_state: "DRAFT_UNAPPROVED", approved_on: null, stamped: false, pdf: null, approval_renders_pdf: false } as never);
    const { container } = show();
    fireEvent.click(await within(await shownBar(container)).findByRole("button", { name: "Schválit koncept 1" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog.textContent).toContain("ART-docx");
    expect(container.querySelector("[data-editor-edited]")).toBeNull();
    // Approved as its line's newest: the server refuses once a save moved the line on.
    fireEvent.click(within(dialog).getAllByRole("button").find((b) => !/Zrušit/.test(b.textContent ?? ""))!);
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith(TEST_FRAME.studyId, "RUN-1", "ART-docx", "", true, null));
  });

  it("approves koncept 1 nothing when an edit starts while its status is read, or while its question is open", async () => {
    const K1 = { ...OPENED, koncept: 1, version_artifact_id: "ART-docx", lines: [] };
    editor.shows = { opened: K1, startedAt: null, dirty: false, seen: () => null };
    versions(version({ version_artifact_id: "ART-docx", koncept: 1, changes: null, edited_from: null, newest_in_line: { version_artifact_id: "ART-docx", koncept: 1 } }));
    const READY = { artifact_id: "ART-docx", review_state: "DRAFT_UNAPPROVED", approved_on: null, stamped: false, pdf: null, approval_renders_pdf: false };
    let answer: (value: unknown) => void = () => undefined;
    vi.mocked(research.report).mockImplementationOnce(() => new Promise((resolve) => { answer = resolve; }) as never);
    const { container } = show();
    fireEvent.click(await within(await shownBar(container)).findByRole("button", { name: "Schválit koncept 1" }));
    act(() => editor.emit({ opened: K1, startedAt: Date.now(), dirty: true, seen: () => null })); // typed while the status is read
    await act(async () => { answer(READY); });
    expect(await screen.findByText(/V editoru jsou úpravy, které AIA ještě neuložila/)).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();

    // The edit stored, then another started while the question is open: the yes approves nothing.
    act(() => editor.emit({ opened: K1, startedAt: null, dirty: false, seen: () => null }));
    vi.mocked(research.report).mockResolvedValue(READY as never);
    fireEvent.click(await within(await shownBar(container)).findByRole("button", { name: "Schválit koncept 1" }));
    const dialog = await screen.findByRole("dialog");
    act(() => editor.emit({ opened: K1, startedAt: Date.now(), dirty: true, seen: () => null }));
    fireEvent.click(within(dialog).getAllByRole("button").find((b) => !/Zrušit/.test(b.textContent ?? ""))!);
    await waitFor(() => expect(screen.getAllByText(/V editoru jsou úpravy, které AIA ještě neuložila/).length).toBeGreaterThan(0));
    expect(research.approveReport).not.toHaveBeenCalled();
  });

  it("opens another line of the run when asked", async () => {
    editor.shows = { opened: OPENED, startedAt: null, dirty: false, seen: () => null };
    versions(version());
    const { container } = show();
    fireEvent.click(await within(await shownBar(container)).findByRole("button", { name: "Koncept 4 (ze starší složené zprávy)" }));
    await waitFor(() => expect(editor.handed).toContainEqual({ variant: "internal", review: null, line: "ART-older" }));
  });

  it("is the composed draft's, as before, while the editor shows nothing (off, or not answering)", async () => {
    editor.shows = null;
    const { container } = show();
    await screen.findByRole("article", { name: "Koncept zprávy" });
    expect(await within(bar(container)).findByRole("button", { name: "Schválit pro interní použití" })).toBeTruthy();
    expect(editorBar(container)).toBeNull();
  });
});
