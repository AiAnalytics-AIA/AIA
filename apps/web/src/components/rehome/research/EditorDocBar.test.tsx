// @vitest-environment jsdom
// The doc bar on the editor's version (artifact-report RPT8d): an edit is approved only once AIA
// stored it, and a save that lands before the ask or before the yes approves nothing.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

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
/** The line as stored: its newest koncept, and when each koncept's last change was (the server's clock). */
const line = { newest: 2, contentAt: {} as Record<number, string> };
const v = (koncept: number, newest = koncept): EditorVersionRead => ({
  version_artifact_id: `ART-${koncept}`, line_id: "ART-docx", koncept, edited_from: "ART-docx", author_names: ["Jana"],
  saved_at: "2026-10-23T20:10:00+00:00", review_state: "DRAFT_UNAPPROVED", approved_on: null, approval: null,
  changes: { uncomparable: null, changes: [{ kind: "changed", tag: "t", was: "1", now: "2", paragraph: null }] },
  newest_in_line: { version_artifact_id: `ART-${newest}`, koncept: newest },
  content_at: line.contentAt[koncept] ?? null, server_now: new Date().toISOString(),
});
const stored = () =>
  vi.mocked(research.reportEditorVersion).mockImplementation(async (_s, _r, id) => v(Number(id.slice(4)), line.newest));
/** A save stored as koncept `k`, its last change `ms` from now. */
const storeKoncept = (k: number, ms: number) => {
  line.contentAt[k] = new Date(Date.now() + ms).toISOString();
  line.newest = k;
};

const bar = (startedAt: number | null = null, pollMs = 20, dirty = false) => (
  <EditorDocBar studyId="STU-1" runId="RUN-1" shown={{ opened: OPENED, startedAt, dirty }} composedId="ART-docx" documentName="interní zprávu"
    canApprove approveComposed={vi.fn()} onApproved={vi.fn()} onOpenLine={vi.fn()} pollMs={pollMs} />
);
const approveButton = (koncept: number) => screen.findByRole("button", { name: `Schválit koncept ${koncept}` });
const isOff = async (koncept: number) => (await approveButton(koncept) as HTMLButtonElement).disabled;

beforeEach(() => {
  line.newest = 2;
  line.contentAt = {};
  stored();
});

describe("an edit waiting to be stored", () => {
  it("keeps the approval off until AIA stores a version holding it, whatever the editor says it saved", async () => {
    const { rerender } = render(bar());
    expect(await isOff(2)).toBe(false);
    // The person starts an edit; the editor then says it reached it (dirty false). AIA has stored nothing.
    rerender(bar(Date.now()));
    await waitFor(async () => expect(await isOff(2)).toBe(true));
    expect(document.querySelector("[data-editor-unsaved]")).not.toBeNull();
    const reads = vi.mocked(research.reportEditorVersion).mock.calls.length;
    await waitFor(() => expect(vi.mocked(research.reportEditorVersion).mock.calls.length).toBeGreaterThan(reads + 2));
    expect(await isOff(2)).toBe(true);
    storeKoncept(3, 2_000); // the Document Server's save, its last change after the edit
    await waitFor(async () => expect(await isOff(3)).toBe(false));
    expect(document.querySelector("[data-editor-unsaved]")).toBeNull();
  });

  it("is not released by a version saved before the latest edit, which does not hold it", async () => {
    const { rerender } = render(bar());
    await approveButton(2);
    rerender(bar(Date.now()));
    storeKoncept(3, -5_000); // a save in flight: an earlier snapshot, stored after the edit started
    expect(await isOff(3)).toBe(true);
    const reads = vi.mocked(research.reportEditorVersion).mock.calls.length;
    await waitFor(() => expect(vi.mocked(research.reportEditorVersion).mock.calls.length).toBeGreaterThan(reads + 2));
    expect(await isOff(3)).toBe(true);
    storeKoncept(4, 2_000);
    await waitFor(async () => expect(await isOff(4)).toBe(false));
  });

  it("is released by a save stored before the first read after the edit, never stuck", async () => {
    const { rerender } = render(bar());
    await approveButton(2);
    storeKoncept(3, 2_000); // stored before the bar reads again
    rerender(bar(Date.now()));
    await waitFor(async () => expect(await isOff(3)).toBe(false));
  });

  it("is not released by a save that does not say what it holds, and says a reload starts again", async () => {
    // Codex on #877: a snapshot taken, an edit made, the snapshot's callback arriving after it with no lastsave.
    const { rerender } = render(bar());
    await approveButton(2);
    rerender(bar(Date.now()));
    line.newest = 3; // stored now, with no content_at
    expect(await isOff(3)).toBe(true);
    expect((await screen.findByText(/Editor u konceptu 3 neuvedl, které úpravy obsahuje/)).textContent).toMatch(/po načtení stránky/);
    const reads = vi.mocked(research.reportEditorVersion).mock.calls.length;
    await waitFor(() => expect(vi.mocked(research.reportEditorVersion).mock.calls.length).toBeGreaterThan(reads + 2));
    expect(await isOff(3)).toBe(true);
    // Reloaded: no edit started in this editor, so the stored koncept is what it shows.
    rerender(bar(null));
    await waitFor(async () => expect(await isOff(3)).toBe(false));
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
    await waitFor(() => expect(research.approveReport).toHaveBeenCalledWith("STU-1", "RUN-1", "ART-2", "", true));
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
});

describe("an edit started while the question is open", () => {
  it("approves nothing", async () => {
    const { rerender } = render(bar(null, 60_000));
    fireEvent.click(await approveButton(2));
    const dialog = await screen.findByRole("dialog");
    rerender(bar(Date.now(), 60_000));
    await act(async () => { fireEvent.click(within(dialog).getByRole("button", { name: "Schválit koncept 2" })); });
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "V editoru jsou úpravy, které AIA ještě neuložila jako koncept; schválit lze až uložený koncept.");
    expect(research.approveReport).not.toHaveBeenCalled();
  });
});
