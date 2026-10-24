// @vitest-environment jsdom
// The doc bar on the editor's version (artifact-report RPT8d): an edit is approved only once AIA
// stored it, and a save that lands before the ask or before the yes approves nothing.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ApiError, research } from "@/lib/api";
import type { EditorOpened, EditorVersionRead } from "@/lib/report-editor";
import { EditorDocBar } from "./EditorDocBar";

vi.mock("@/lib/api", async () => ({
  ApiError: (await vi.importActual<typeof import("@/lib/api")>("@/lib/api")).ApiError,
  research: { reportEditorVersion: vi.fn(), approveReport: vi.fn() },
}));

// jsdom has <dialog> without showModal/close: the modal's open state, as a browser sets it.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) { this.removeAttribute("open"); };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const OPENED: EditorOpened = {
  document_server: "https://docs.aia.example.test", config: { token: "signed" }, line_id: "ART-docx", koncept: 2,
  version_artifact_id: "ART-2", problem: null, lines: [],
};
const v = (koncept: number, newest = koncept): EditorVersionRead => ({
  version_artifact_id: `ART-${koncept}`, line_id: "ART-docx", koncept, edited_from: "ART-docx", author_names: ["Jana"],
  saved_at: "2026-10-23T20:10:00+00:00", review_state: "DRAFT_UNAPPROVED", approved_on: null, approval: null,
  changes: { uncomparable: null, changes: [{ kind: "changed", tag: "t", was: "1", now: "2", paragraph: null }] },
  newest_in_line: { version_artifact_id: `ART-${newest}`, koncept: newest },
});
/** The line as stored: its newest koncept, every version up to it readable. */
const line = { newest: 2 };
const stored = () =>
  vi.mocked(research.reportEditorVersion).mockImplementation(async (_s, _r, id) => v(Number(id.slice(4)), line.newest));

const bar = (edits = 0, pollMs = 20) => (
  <EditorDocBar studyId="STU-1" runId="RUN-1" shown={{ opened: OPENED, edits }} composedId="ART-docx" documentName="interní zprávu"
    canApprove approveComposed={vi.fn()} onApproved={vi.fn()} onOpenLine={vi.fn()} pollMs={pollMs} />
);
const approveButton = (koncept: number) => screen.findByRole("button", { name: `Schválit koncept ${koncept}` });

describe("an edit waiting to be stored", () => {
  it("keeps the approval off until AIA stores a newer version, whatever the editor says it saved", async () => {
    line.newest = 2;
    stored();
    const { rerender } = render(bar(0));
    expect((await approveButton(2) as HTMLButtonElement).disabled).toBe(false);
    // The person starts editing: the edit reached the Document Server, not AIA.
    rerender(bar(1));
    await waitFor(async () => expect((await approveButton(2) as HTMLButtonElement).disabled).toBe(true));
    expect(document.querySelector("[data-editor-unsaved]")).not.toBeNull();
    // Polls that find no newer version keep it off.
    const reads = vi.mocked(research.reportEditorVersion).mock.calls.length;
    await waitFor(() => expect(vi.mocked(research.reportEditorVersion).mock.calls.length).toBeGreaterThan(reads + 2));
    expect((await approveButton(2) as HTMLButtonElement).disabled).toBe(true);
    // The Document Server's save is stored as koncept 3: that is the version on screen now.
    line.newest = 3;
    expect((await approveButton(3) as HTMLButtonElement).disabled).toBe(false);
    expect(document.querySelector("[data-editor-unsaved]")).toBeNull();
  });
});

describe("approving the editor's version", () => {
  it("approves nothing when a save lands while the question is open", async () => {
    line.newest = 2;
    stored();
    render(bar(0, 60_000));
    fireEvent.click(await approveButton(2));
    const dialog = await screen.findByRole("dialog");
    line.newest = 3; // a co-editor's autosave, while the person reads the question
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" })); });
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Editor mezitím uložil koncept 3; zkontrolujte jeho změny a schvalte znovu.");
    expect(research.approveReport).not.toHaveBeenCalled();
    expect(await approveButton(3)).toBeTruthy();
  });

  it("approves the version asked about when nothing moved", async () => {
    line.newest = 2;
    stored();
    vi.mocked(research.approveReport).mockResolvedValue({ run_id: "RUN-1", artifact_id: "ART-2", review_state: "APPROVED_INTERNAL" } as never);
    render(bar(0, 60_000));
    fireEvent.click(await approveButton(2));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" }));
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith("STU-1", "RUN-1", "ART-2", "", true));
  });
});

describe("the server's last word", () => {
  it("says a refusal that the line moved on, and reads the line again", async () => {
    line.newest = 2;
    stored();
    vi.mocked(research.approveReport).mockImplementation(async () => {
      line.newest = 3; // stored between the page's last read and the server's check
      throw new ApiError(409, "report_version_stale", "A later version…", null, { newest_artifact_id: "ART-3", koncept: 3 });
    });
    render(bar(0, 60_000));
    fireEvent.click(await approveButton(2));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Schválit koncept 2" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Editor mezitím uložil koncept 3; zkontrolujte jeho změny a schvalte znovu.");
    expect(await approveButton(3)).toBeTruthy();
  });
});
