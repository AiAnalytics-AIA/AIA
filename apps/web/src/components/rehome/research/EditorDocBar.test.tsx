// @vitest-environment jsdom
// The doc bar on the editor's version (artifact-report RPT8d): an edit is approved only once AIA
// stored it, and a save that lands before the ask or before the yes approves nothing.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, research } from "@/lib/api";
import type { EditorOpened, EditorVersionRead, SeenEdit } from "@/lib/report-editor";
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
/** The line as the server holds it: its newest koncept, and its verdict on each (RPT8f): whether that
 *  koncept holds every edit reported, unset meaning it does. */
const line = { newest: 2, saved: {} as Record<number, boolean> };
const v = (koncept: number, newest = koncept): EditorVersionRead => ({
  version_artifact_id: `ART-${koncept}`, line_id: "ART-docx", koncept, edited_from: "ART-docx", author_names: ["Jana"],
  saved_at: "2026-10-23T20:10:00+00:00", review_state: "DRAFT_UNAPPROVED", approved_on: null, approval: null,
  changes: { uncomparable: null, changes: [{ kind: "changed", tag: "t", was: "1", now: "2", paragraph: null }] },
  newest_in_line: { version_artifact_id: `ART-${newest}`, koncept: newest },
  content_at: null, server_now: new Date().toISOString(),
  edits: (line.saved[koncept] ?? true) ? { saved: true, reason: null } : { saved: false, reason: "edit_not_saved" },
});
const stored = () =>
  vi.mocked(research.reportEditorVersion).mockImplementation(async (_s, _r, id) => v(Number(id.slice(4)), line.newest));
/** A save stored as koncept `k`, which the server says holds every edit, or not. */
const storeKoncept = (k: number, holds: boolean) => {
  line.saved[k] = holds;
  line.newest = k;
};

const bar = (startedAt: number | null = null, pollMs = 20, dirty = false, seen: () => SeenEdit | null = () => null) => (
  <EditorDocBar studyId="STU-1" runId="RUN-1" shown={{ opened: OPENED, startedAt, dirty, seen }} composedId="ART-docx" documentName="interní zprávu"
    canApprove approveComposed={vi.fn()} onApproved={vi.fn()} onOpenLine={vi.fn()} pollMs={pollMs} />
);
const approveButton = (koncept: number) => screen.findByRole("button", { name: `Schválit koncept ${koncept}` });
const isOff = async (koncept: number) => (await approveButton(koncept) as HTMLButtonElement).disabled;

beforeEach(() => {
  line.newest = 2;
  line.saved = {};
  stored();
});

describe("an edit waiting to be stored", () => {
  /** The person starts an edit: its report reaches AIA, so the server holds the koncept on screen. */
  const edits = (koncept = line.newest) => { line.saved[koncept] = false; };

  it("keeps the approval off until the server says a stored version holds it, whatever the editor says it saved", async () => {
    const { rerender } = render(bar());
    expect(await isOff(2)).toBe(false);
    edits();
    rerender(bar(Date.now())); // the editor then says it reached it (dirty false); AIA has stored nothing
    await waitFor(async () => expect(await isOff(2)).toBe(true));
    expect(document.querySelector("[data-editor-unsaved]")).not.toBeNull();
    const reads = vi.mocked(research.reportEditorVersion).mock.calls.length;
    await waitFor(() => expect(vi.mocked(research.reportEditorVersion).mock.calls.length).toBeGreaterThan(reads + 2));
    expect(await isOff(2)).toBe(true);
    storeKoncept(3, true); // the Document Server's save, which the server says holds the edit
    await waitFor(async () => expect(await isOff(3)).toBe(false));
    expect(document.querySelector("[data-editor-unsaved]")).toBeNull();
  });

  it("is not released by a version the server says does not hold the edit, and is once its verdict moves on", async () => {
    const { rerender } = render(bar());
    await approveButton(2);
    edits();
    rerender(bar(Date.now()));
    storeKoncept(3, false); // a snapshot from before the edit, stored after it
    expect(await isOff(3)).toBe(true);
    const reads = vi.mocked(research.reportEditorVersion).mock.calls.length;
    await waitFor(() => expect(vi.mocked(research.reportEditorVersion).mock.calls.length).toBeGreaterThan(reads + 2));
    expect(await isOff(3)).toBe(true);
    // The clean-report recovery: a later save of the same bytes, after the page's clean report,
    // and the server says the koncept holds the edit; nothing on the page guesses it.
    line.saved[3] = true;
    await waitFor(async () => expect(await isOff(3)).toBe(false));
  });

  it("asks the server about the page's own last edit; a verdict read before it says nothing of it", async () => {
    let seen: SeenEdit | null = null;
    const { rerender } = render(bar(null, 60_000, false, () => seen));
    expect(await isOff(2)).toBe(false);
    let answer: (value: EditorVersionRead) => void = () => undefined;
    vi.mocked(research.reportEditorVersion).mockImplementationOnce(() => new Promise((resolve) => { answer = resolve; }));
    seen = { document_key: "KEY.1", page: "p0123456789", seq: 1 };
    rerender(bar(Date.now(), 60_000, false, () => seen));
    await waitFor(async () => expect(await isOff(2)).toBe(true)); // no verdict counts edit 1 yet
    await act(async () => { answer(v(2)); });
    await waitFor(async () => expect(await isOff(2)).toBe(false));
    expect(vi.mocked(research.reportEditorVersion)).toHaveBeenCalledWith("STU-1", "RUN-1", "ART-2", seen);
  });

  it("keeps the approval off while the editor holds an edit not yet sent", async () => {
    render(bar(null, 20, true));
    expect(await isOff(2)).toBe(true);
    expect(document.querySelector("[data-editor-unsaved]")).not.toBeNull();
  });
});

describe("approving the editor's version", () => {
  it("approves nothing when a save lands while the question is open", async () => {
    render(bar(null, 60_000));
    fireEvent.click(await approveButton(2));
    const dialog = await screen.findByRole("dialog");
    line.newest = 3; // a co-editor's autosave, while the person reads the question
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" })); });
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Editor mezitím uložil koncept 3; zkontrolujte jeho změny a schvalte znovu.");
    expect(research.approveReport).not.toHaveBeenCalled();
    expect(await approveButton(3)).toBeTruthy();
  });

  it("approves the version asked about when nothing moved", async () => {
    vi.mocked(research.approveReport).mockResolvedValue({ run_id: "RUN-1", artifact_id: "ART-2", review_state: "APPROVED_INTERNAL" } as never);
    render(bar(null, 60_000));
    fireEvent.click(await approveButton(2));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" }));
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith("STU-1", "RUN-1", "ART-2", "", true, null));
  });
});

describe("the server's last word", () => {
  it("says a refusal that the line moved on, and reads the line again", async () => {
    vi.mocked(research.approveReport).mockImplementation(async () => {
      line.newest = 3; // stored between the page's last read and the server's check
      throw new ApiError(409, "report_version_stale", "A later version…", null, { newest_artifact_id: "ART-3", koncept: 3 });
    });
    render(bar(null, 60_000));
    fireEvent.click(await approveButton(2));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Schválit koncept 2" }));
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "Editor mezitím uložil koncept 3; zkontrolujte jeho změny a schvalte znovu.");
    expect(await approveButton(3)).toBeTruthy();
  });

  it("names the page's last edit, read as the approval leaves, and says why the server held it (RPT8f)", async () => {
    const edit: SeenEdit = { document_key: "KEY.1", page: "p0123456789", seq: 1 };
    let seen: SeenEdit | null = null;
    vi.mocked(research.approveReport).mockRejectedValue(
      new ApiError(409, "report_edits_unsaved", "An edit…", null, { reason: "edit_not_received" }),
    );
    const { rerender } = render(bar(null, 60_000, false, () => seen));
    fireEvent.click(await approveButton(2));
    const dialog = await screen.findByRole("dialog");
    // Made after the question opened, and read again with it: the server counts it (here as
    // saved), and the yes names it, so the server's lock has the last word.
    seen = edit;
    rerender(bar(Date.now(), 60_000, false, () => seen));
    await waitFor(() => expect(research.reportEditorVersion).toHaveBeenLastCalledWith("STU-1", "RUN-1", "ART-2", edit));
    await waitFor(() => expect(document.querySelector("[data-editor-unsaved]")).toBeNull());
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" })); });
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith("STU-1", "RUN-1", "ART-2", "", true, edit));
    expect(await screen.findByRole("alert")).toHaveProperty(
      "textContent", "Poslední úprava z editoru ještě nedorazila do AIA; schvalte znovu za chvíli.",
    );
  });
});

describe("an edit started while the yes's read is in flight", () => {
  it("approves nothing", async () => {
    const { rerender } = render(bar(null, 60_000));
    fireEvent.click(await approveButton(2));
    const dialog = await screen.findByRole("dialog");
    let answer: (value: EditorVersionRead) => void = () => undefined;
    vi.mocked(research.reportEditorVersion).mockImplementationOnce(() => new Promise((resolve) => { answer = resolve; }));
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" })); });
    line.saved[2] = false; // its report reached AIA: the server holds koncept 2
    rerender(bar(Date.now(), 60_000)); // typed while the yes's read is out
    await act(async () => { answer(v(2)); });
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "V editoru jsou úpravy, které AIA ještě neuložila jako koncept; schválit lze až uložený koncept.");
    expect(research.approveReport).not.toHaveBeenCalled();
  });
});

describe("an edit started while the question is open", () => {
  it("approves nothing", async () => {
    const { rerender } = render(bar(null, 60_000));
    fireEvent.click(await approveButton(2));
    const dialog = await screen.findByRole("dialog");
    line.saved[2] = false; // its report reached AIA: the server holds koncept 2
    rerender(bar(Date.now(), 60_000));
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" })); });
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "V editoru jsou úpravy, které AIA ještě neuložila jako koncept; schválit lze až uložený koncept.");
    expect(research.approveReport).not.toHaveBeenCalled();
  });
});
