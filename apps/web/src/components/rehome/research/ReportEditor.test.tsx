// @vitest-environment jsdom
// The draft in the report editor (artifact-report RPT8d): the version the API opens, from its own
// origin's api.js, the read-only draft whenever the editor is off, fails or does not answer.
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import type { EditorOpened } from "@/lib/report-editor";
import { type DocsApi, ReportEditor } from "./ReportEditor";

const OPENED: EditorOpened = {
  document_server: "https://docs.aia.example.test",
  config: { documentType: "word", document: { key: "ART-1.aaaa.1" }, editorConfig: { mode: "edit" }, token: "signed" },
  line_id: "ART-1",
  koncept: 2,
  version_artifact_id: "ART-2",
  lines: [],
  problem: null,
  api_integrity: `sha384-${"a".repeat(64)}`,
};
/** The one-time ticket the page spends by loading api.js through it (report-editor-hosting). */
const TICKET = { session_url: "https://docs.aia.example.test/__aia/session?ticket=t.k", expires_at: "2026-10-25T21:00:00Z" };
const SCRIPT = "https://docs.aia.example.test/__aia/session?ticket=t.k&next=%2Fweb-apps%2Fapps%2Fapi%2Fdocuments%2Fapi.js";
const ticket = () => vi.fn().mockResolvedValue(TICKET);

/** A stand-in DocsAPI: records each editor made and what it was configured with. */
function docsApi() {
  const made: { id: string; config: Record<string, unknown>; destroyed: boolean }[] = [];
  const api: DocsApi = {
    DocEditor: class {
      entry: (typeof made)[number];
      constructor(id: string, config: Record<string, unknown>) {
        this.entry = { id, config, destroyed: false };
        made.push(this.entry);
      }
      destroyEditor() { this.entry.destroyed = true; }
    },
  };
  return { api, made };
}

const events = (config: Record<string, unknown>) =>
  config.events as { onAppReady: () => void; onError: () => void; onDocumentStateChange: (e: { data: boolean }) => void };

const show = (props: Partial<Parameters<typeof ReportEditor>[0]> = {}) =>
  render(
    <ReportEditor studyId="STU-1" runId="RUN-1" variant="internal" review={null} ticket={ticket()} {...props}>
      <article>Koncept jen ke čtení</article>
    </ReportEditor>,
  );

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  Object.defineProperty(window, "innerWidth", { value: 1024, configurable: true });
});

describe("the draft in the report editor", () => {
  it("is the read-only draft, saying nothing, while the editor is off", async () => {
    const open = vi.fn().mockRejectedValue(new ApiError(404, "not_found", "No such resource.", null));
    const load = vi.fn();
    show({ open, load });
    await screen.findByText("Koncept jen ke čtení");
    await act(async () => {});
    expect(document.querySelector("[data-report-editor]")).toBeNull();
    expect(load).not.toHaveBeenCalled();
  });

  it("opens the version the API named, with the config it signed, from its own origin's api.js through the ticket, under its integrity", async () => {
    const { api, made } = docsApi();
    const open = vi.fn().mockResolvedValue(OPENED);
    const load = vi.fn().mockResolvedValue(api);
    show({ open, load });
    await vi.waitFor(() => expect(made).toHaveLength(1));
    expect(open).toHaveBeenCalledWith("STU-1", "RUN-1", { variant: "internal", deep_research_run_id: null, line: null, mode: "edit" });
    expect(load).toHaveBeenCalledWith(SCRIPT, OPENED.api_integrity);
    expect(made[0].config).toMatchObject({ token: "signed", document: { key: "ART-1.aaaa.1" } });
    expect(document.getElementById(made[0].id)).not.toBeNull();
    act(() => events(made[0].config).onAppReady());
    expect(document.querySelector("[data-report-editor]")?.getAttribute("data-report-editor")).toBe("ready");
    expect(screen.queryByText("Koncept jen ke čtení")).toBeNull();
  });

  it("tells the pane what it shows once ready, when this person last started an edit, and whether one is unsent", async () => {
    const { api, made } = docsApi();
    const onShown = vi.fn();
    show({ open: vi.fn().mockResolvedValue(OPENED), load: vi.fn().mockResolvedValue(api), onShown, report: vi.fn().mockResolvedValue(undefined) });
    await vi.waitFor(() => expect(made).toHaveLength(1));
    expect(onShown).toHaveBeenLastCalledWith(null);
    act(() => events(made[0].config).onAppReady());
    expect(onShown).toHaveBeenLastCalledWith({ opened: OPENED, startedAt: null, dirty: false, seen: expect.any(Function) });
    const before = Date.now();
    act(() => events(made[0].config).onDocumentStateChange({ data: true }));
    const first = onShown.mock.lastCall?.[0] as { startedAt: number; dirty: boolean };
    expect(first.dirty).toBe(true);
    expect(first.startedAt).toBeGreaterThanOrEqual(before);
    // false: the edit reached the Document Server, not AIA; the start stays, only "unsent" clears.
    act(() => events(made[0].config).onDocumentStateChange({ data: false }));
    expect(onShown).toHaveBeenLastCalledWith({ opened: OPENED, startedAt: first.startedAt, dirty: false, seen: expect.any(Function) });
    act(() => events(made[0].config).onError());
    expect(onShown).toHaveBeenLastCalledWith(null);
  });

  it("names only the edit of the session on screen: another line opened names none of the first's (RPT8f)", async () => {
    const { api, made } = docsApi();
    const onShown = vi.fn();
    const B: EditorOpened = { ...OPENED, line_id: "ART-9", config: { ...OPENED.config, document: { key: "ART-9.bbbb.1" } } };
    const open = vi.fn(async (_s: string, _r: string, body: { line?: string | null }) => (body.line === "ART-9" ? B : OPENED));
    const props = { open, load: vi.fn().mockResolvedValue(api), onShown, report: vi.fn().mockResolvedValue(undefined) };
    const view = render(
      <ReportEditor studyId="STU-1" runId="RUN-1" variant="internal" review={null} ticket={ticket()} {...props}><article /></ReportEditor>,
    );
    await vi.waitFor(() => expect(made).toHaveLength(1));
    act(() => events(made[0].config).onAppReady());
    act(() => events(made[0].config).onDocumentStateChange({ data: true }));
    const seen = () => (onShown.mock.lastCall?.[0] as { seen: () => unknown } | null)?.seen();
    expect(seen()).toMatchObject({ document_key: "ART-1.aaaa.1", seq: 1 });
    view.rerender(
      <ReportEditor studyId="STU-1" runId="RUN-1" variant="internal" review={null} line="ART-9" ticket={ticket()} {...props}><article /></ReportEditor>,
    );
    await vi.waitFor(() => expect(made).toHaveLength(2));
    act(() => events(made[1].config).onAppReady());
    expect(seen()).toBeNull();
    act(() => events(made[1].config).onDocumentStateChange({ data: true }));
    expect(seen()).toMatchObject({ document_key: "ART-9.bbbb.1", seq: 1 });
  });

  it("reports each edit start to AIA, counted from 1 in the session, and names the last as seen (RPT8f)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { api, made } = docsApi();
    const onShown = vi.fn();
    const report = vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValue(undefined);
    show({ open: vi.fn().mockResolvedValue(OPENED), load: vi.fn().mockResolvedValue(api), onShown, report });
    await vi.waitFor(() => expect(made).toHaveLength(1));
    act(() => events(made[0].config).onAppReady());
    const seen = () => (onShown.mock.lastCall?.[0] as { seen: () => unknown }).seen();
    expect(seen()).toBeNull();
    act(() => events(made[0].config).onDocumentStateChange({ data: true }));
    const first = seen() as { document_key: string; page: string; seq: number };
    expect(first).toMatchObject({ document_key: "ART-1.aaaa.1", seq: 1 });
    expect(first.page).toMatch(/^[0-9A-Za-z_-]{8,64}$/);
    act(() => events(made[0].config).onDocumentStateChange({ data: false })); // sent, not an edit
    expect(seen()).toEqual(first);
    expect(report).toHaveBeenCalledTimes(1);
    act(() => events(made[0].config).onDocumentStateChange({ data: true }));
    expect(seen()).toEqual({ ...first, seq: 2 });
    // The first report failed and is sent once more; each names the page and its count.
    await act(async () => { await vi.advanceTimersByTimeAsync(2_500); });
    expect(report.mock.calls).toEqual([
      ["STU-1", "RUN-1", "ART-1.aaaa.1", { page: first.page, seq: 1 }],
      ["STU-1", "RUN-1", "ART-1.aaaa.1", { page: first.page, seq: 2 }],
      ["STU-1", "RUN-1", "ART-1.aaaa.1", { page: first.page, seq: 1 }],
    ]);
  });

  it("opens the line asked for", async () => {
    const open = vi.fn().mockResolvedValue(OPENED);
    show({ open, load: vi.fn().mockResolvedValue(docsApi().api), line: "ART-old" });
    await vi.waitFor(() => expect(open).toHaveBeenCalledWith("STU-1", "RUN-1", { variant: "internal", deep_research_run_id: null, line: "ART-old", mode: "edit" }));
  });

  it("opens the report with literature by its review, and in view mode below 768 px", async () => {
    Object.defineProperty(window, "innerWidth", { value: 390, configurable: true });
    const open = vi.fn().mockResolvedValue(OPENED);
    show({ open, load: vi.fn().mockResolvedValue(docsApi().api), variant: "context", review: "RUN-feed" });
    await vi.waitFor(() => expect(open).toHaveBeenCalled());
    expect(open).toHaveBeenCalledWith("STU-1", "RUN-1", { variant: "context", deep_research_run_id: "RUN-feed", line: null, mode: "view" });
    expect(await screen.findByText(/Jen ke čtení \(úzká obrazovka\)/)).toBeTruthy();
  });

  it("keeps the read-only draft and says so when api.js does not load", async () => {
    show({ open: vi.fn().mockResolvedValue(OPENED), load: vi.fn().mockRejectedValue(new Error("api.js did not load")) });
    expect(await screen.findByText(/Editor zprávy neodpovídá/)).toBeTruthy();
    expect(screen.getByText("Koncept jen ke čtení")).toBeTruthy();
  });

  it("keeps the read-only draft and says so when the editor never says it is ready", async () => {
    const { api, made } = docsApi();
    show({ open: vi.fn().mockResolvedValue(OPENED), load: vi.fn().mockResolvedValue(api), timeoutMs: 50 });
    await vi.waitFor(() => expect(made).toHaveLength(1));
    expect(await screen.findByText(/Editor zprávy neodpovídá/)).toBeTruthy();
    expect(screen.getByText("Koncept jen ke čtení")).toBeTruthy();
    expect(made[0].destroyed).toBe(true);
  });

  it("keeps the read-only draft when the editor reports an error", async () => {
    const { api, made } = docsApi();
    show({ open: vi.fn().mockResolvedValue(OPENED), load: vi.fn().mockResolvedValue(api) });
    await vi.waitFor(() => expect(made).toHaveLength(1));
    act(() => events(made[0].config).onError());
    expect(await screen.findByText(/Editor zprávy neodpovídá/)).toBeTruthy();
    expect(screen.getByText("Koncept jen ke čtení")).toBeTruthy();
  });

  it("never loads a script from an origin that is not https", async () => {
    const load = vi.fn();
    show({ open: vi.fn().mockResolvedValue({ ...OPENED, document_server: "http://docs.aia.example.test" }), load });
    expect(await screen.findByText(/Editor zprávy neodpovídá/)).toBeTruthy();
    expect(load).not.toHaveBeenCalled();
  });

  it("loads no script without an integrity to check it against, and says so (RPT8e)", async () => {
    for (const api_integrity of [undefined, "", "sha256-abc"]) {
      const load = vi.fn();
      const spend = ticket();
      const { unmount } = show({ open: vi.fn().mockResolvedValue({ ...OPENED, api_integrity }), load, ticket: spend });
      expect(await screen.findByText("Skript editoru zprávy nelze ověřit; zobrazuje se koncept jen ke čtení.")).toBeTruthy();
      expect(screen.getByText("Koncept jen ke čtení")).toBeTruthy();
      expect(load).not.toHaveBeenCalled();
      expect(spend).not.toHaveBeenCalled(); // no ticket spent for a script that will not load
      unmount();
    }
  });

  it("keeps the read-only draft when no ticket is given, and loads nothing", async () => {
    const load = vi.fn();
    show({ open: vi.fn().mockResolvedValue(OPENED), ticket: vi.fn().mockRejectedValue(new ApiError(403, "not_a_member", "", null)), load });
    expect(await screen.findByText(/Editor zprávy neodpovídá/)).toBeTruthy();
    expect(load).not.toHaveBeenCalled();
  });

  it("puts api.js on the page under its integrity, with credentials, through the ticket", async () => {
    show({ open: vi.fn().mockResolvedValue(OPENED) });
    await vi.waitFor(() => expect(document.head.querySelector("script[integrity]")).not.toBeNull());
    const script = document.head.querySelector<HTMLScriptElement>("script[integrity]")!;
    expect(script.src).toBe(SCRIPT);
    expect(script.getAttribute("integrity")).toBe(OPENED.api_integrity);
    expect(script.getAttribute("crossorigin")).toBe("use-credentials");
    script.remove();
  });

  it("says a refusal in words beside the read-only draft", async () => {
    show({ open: vi.fn().mockRejectedValue(new ApiError(409, "report_not_editable", "", null)), load: vi.fn() });
    expect(await screen.findByText("Tuto verzi zprávy editor neotevře.")).toBeTruthy();
    expect(screen.getByText("Koncept jen ke čtení")).toBeTruthy();
  });

  it("says why the last save was not stored", async () => {
    show({ open: vi.fn().mockResolvedValue({ ...OPENED, problem: "document_server_restarted" }), load: vi.fn().mockResolvedValue(docsApi().api) });
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", expect.stringMatching(/restartoval/));
  });

  it("destroys the editor when the pane goes", async () => {
    const { api, made } = docsApi();
    const { unmount } = show({ open: vi.fn().mockResolvedValue(OPENED), load: vi.fn().mockResolvedValue(api) });
    await vi.waitFor(() => expect(made).toHaveLength(1));
    unmount();
    expect(made[0].destroyed).toBe(true);
  });
});


describe("an editor that gave up", () => {
  it("is never revived by a script that loads late or an editor that says it is ready late", async () => {
    const { api, made } = docsApi();
    let arrive: (value: DocsApi) => void = () => undefined;
    const late = new Promise<DocsApi>((resolve) => { arrive = resolve; });
    show({ open: vi.fn().mockResolvedValue(OPENED), load: vi.fn().mockReturnValue(late), timeoutMs: 30 });
    expect(await screen.findByText(/Editor zprávy neodpovídá/)).toBeTruthy();
    await act(async () => { arrive(api); await late; });
    expect(made).toHaveLength(0); // the script came after the timeout: nothing is built
    expect(screen.getByText("Koncept jen ke čtení")).toBeTruthy();
  });

  it("stays given up when the editor answers ready after the timeout", async () => {
    const { api, made } = docsApi();
    show({ open: vi.fn().mockResolvedValue(OPENED), load: vi.fn().mockResolvedValue(api), timeoutMs: 30 });
    await vi.waitFor(() => expect(made).toHaveLength(1));
    expect(await screen.findByText(/Editor zprávy neodpovídá/)).toBeTruthy();
    act(() => events(made[0].config).onAppReady());
    expect(screen.getByText(/Editor zprávy neodpovídá/)).toBeTruthy();
    expect(document.querySelector("[data-report-editor='ready']")).toBeNull();
    expect(screen.getByText("Koncept jen ke čtení")).toBeTruthy();
  });
});
