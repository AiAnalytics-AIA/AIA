"use client";

// Zpráva's draft in the report editor (artifact-report RPT8d): the version the API opens (RPT8c),
// edited in ONLYOFFICE Docs from 768 px and read in its view mode below. The page loads the
// Document Server's api.js from the origin the API names and hands it the config the API signed;
// it signs nothing and stores nothing itself (saves reach the API from the Document Server).
// With the editor off (404) the read-only draft is the pane, as before; with a Document Server that
// fails or does not answer, the read-only draft stays and says so -- never a blank pane.

import { type ReactNode, useCallback, useEffect, useId, useRef, useState } from "react";

import { research } from "@/lib/api";
import {
  apiScriptUrl, documentKeyOf, EDIT_FROM_PX, EDITOR_TIMEOUT_MS, type EditorMode, type EditorOpened, editorMode, newPageId,
  openFailure, problemWords, type SeenEdit, UNREACHABLE,
} from "@/lib/report-editor";

/** What the editor shows once it is ready: the line and version opened, when this person last
 *  started an edit (`onDocumentStateChange` with `true`, by this browser's clock; null before any),
 *  and whether an edit is not yet sent to the Document Server (`dirty`). An edit is not a stored
 *  version: `false` only says it reached the Document Server, so the pane asks the API whether a
 *  version stored since holds it (`lib/report-editor.ts` `holdsEdit`). */
export type EditorShown = {
  opened: EditorOpened;
  startedAt: number | null;
  dirty: boolean;
  /** The last edit start this page made, read as the approval leaves (RPT8f): the server holds the
   *  approval until a stored version holds it; null before any. */
  seen: () => SeenEdit | null;
};

/** A report of an edit start that did not reach AIA is sent once more after this long; one that
 *  still fails holds the approval (`edit_not_received`) until the next edit's report arrives. */
const REPORT_RETRY_MS = 2_000;

/** What api.js puts on the page: one constructor (ONLYOFFICE's DocsAPI). */
export type DocsApi = {
  DocEditor: new (placeholderId: string, config: Record<string, unknown>) => { destroyEditor?: () => void };
};

declare global {
  interface Window {
    DocsAPI?: DocsApi;
  }
}

const scripts = new Map<string, Promise<DocsApi>>();

/** api.js from `url`, loaded once per page; a load that failed is tried again next time. */
function loadDocsApi(url: string): Promise<DocsApi> {
  const known = scripts.get(url);
  if (known) return known;
  const loaded = new Promise<DocsApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = url;
    script.async = true;
    script.onload = () => (window.DocsAPI ? resolve(window.DocsAPI) : reject(new Error("api.js defined no DocsAPI")));
    script.onerror = () => {
      script.remove();
      reject(new Error("api.js did not load"));
    };
    document.head.appendChild(script);
  });
  loaded.catch(() => scripts.delete(url));
  scripts.set(url, loaded);
  return loaded;
}

/** The mode the window's width opens the editor in, followed as it changes. */
function useMode(): EditorMode {
  const read = () => (typeof window === "undefined" ? "edit" : editorMode(window.innerWidth));
  const [mode, setMode] = useState<EditorMode>(read);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(`(min-width: ${EDIT_FROM_PX}px)`);
    const follow = () => setMode(query.matches ? "edit" : "view");
    query.addEventListener("change", follow);
    return () => query.removeEventListener("change", follow);
  }, []);
  return mode;
}

type State =
  | { at: string; kind: "opening" }
  | { at: string; kind: "off" }
  | { at: string; kind: "said"; words: string }
  | { at: string; kind: "open"; opened: EditorOpened; script: string };

export type ReportEditorProps = {
  studyId: string;
  runId: string;
  /** The internal report, or the report with the literature review `review` (the client report is
   *  never edited). */
  variant: "internal" | "context";
  review: string | null;
  /** The line to open; null for the one with the newest version (the API's default). */
  line?: string | null;
  /** The read-only draft: the pane whenever the editor is not on screen. */
  children: ReactNode;
  /** Told what the editor shows once it is ready, and null whenever it shows nothing: the doc bar
   *  names that version and approves only it. */
  onShown?: (shown: EditorShown | null) => void;
  /** Seams for the tests: the open route, the edit report and the script loader. */
  open?: typeof research.openReportEditor;
  report?: typeof research.reportEditorEdit;
  load?: (url: string) => Promise<DocsApi>;
  timeoutMs?: number;
};

export function ReportEditor({
  studyId, runId, variant, review, line = null, children, onShown, open = research.openReportEditor,
  report = research.reportEditorEdit, load = loadDocsApi,
  timeoutMs = EDITOR_TIMEOUT_MS,
}: ReportEditorProps) {
  const mode = useMode();
  const at = `${studyId}:${runId}:${variant}:${review ?? ""}:${line ?? ""}:${mode}`;
  const [state, setState] = useState<State>({ at, kind: "opening" });
  // The editor came up (`onAppReady`), or it failed after the route answered: this document only.
  const [up, setUp] = useState<{ at: string; ready: boolean; failed: boolean }>({ at, ready: false, failed: false });
  // When this person last started an edit, and whether one is not yet sent: this document only.
  const [edits, setEdits] = useState<{ at: string; startedAt: number | null; dirty: boolean }>({ at, startedAt: null, dirty: false });
  const host = useRef<HTMLDivElement>(null);
  // This page's edit starts in the session on screen, counted from 1 (RPT8f): a new session's key
  // starts the count again.
  const page = useRef<string | null>(null);
  const last = useRef<SeenEdit | null>(null);
  const seen = useCallback(() => last.current, []);
  const placeholder = `report-editor-${useId().replace(/[^a-zA-Z0-9-]/g, "")}`;

  useEffect(() => {
    let live = true;
    open(studyId, runId, { variant, deep_research_run_id: variant === "context" ? review : null, line, mode }).then(
      (opened) => {
        if (!live) return;
        const script = apiScriptUrl(opened.document_server);
        setState(script ? { at, kind: "open", opened, script } : { at, kind: "said", words: UNREACHABLE });
      },
      (error: unknown) => {
        if (!live) return;
        const failure = openFailure(error);
        setState(failure.kind === "off" ? { at, kind: "off" } : { at, kind: "said", words: failure.words });
      },
    );
    return () => { live = false; };
  }, [at, studyId, runId, variant, review, line, mode, open]);

  const opened = state.at === at && state.kind === "open" ? state : null;
  useEffect(() => {
    const element = host.current;
    if (!opened || !element) return;
    let live = true;
    let editor: { destroyEditor?: () => void } | null = null;
    // Failing ends this attempt for good: a script that loads late, or an editor that says it is
    // ready after the timeout, builds and revives nothing (the host it would use is gone).
    let failed = false;
    const going = () => live && !failed;
    const fail = () => {
      if (!going()) return;
      failed = true;
      clearTimeout(timer);
      editor?.destroyEditor?.();
      editor = null;
      setUp({ at, ready: false, failed: true });
    };
    // A Document Server that never says it is ready leaves the read-only draft, said so.
    const timer = setTimeout(fail, timeoutMs);
    load(opened.script).then(
      (api) => {
        if (!going()) return;
        // The editor replaces a node of its own, never one React renders.
        const node = document.createElement("div");
        node.id = placeholder;
        element.replaceChildren(node);
        try {
          editor = new api.DocEditor(placeholder, {
            ...opened.opened.config,
            width: "100%",
            height: "100%",
            events: {
              onAppReady: () => {
                if (!going()) return;
                clearTimeout(timer);
                setUp({ at, ready: true, failed: false });
              },
              onDocumentStateChange: (event: { data?: unknown }) => {
                if (!going()) return;
                const dirty = event?.data === true;
                const now = Date.now();
                const key = documentKeyOf(opened.opened.config);
                if (dirty && key) {
                  page.current ??= newPageId();
                  const seq = last.current?.document_key === key ? last.current.seq + 1 : 1;
                  const edit = { document_key: key, page: page.current, seq };
                  last.current = edit;
                  const send = () => report(studyId, runId, key, { page: edit.page, seq });
                  send().catch(() => setTimeout(() => { send().catch(() => undefined); }, REPORT_RETRY_MS));
                }
                setEdits((was) => ({ at, startedAt: dirty ? now : was.at === at ? was.startedAt : null, dirty }));
              },
              onError: fail,
            },
          });
        } catch {
          fail();
        }
      },
      fail,
    );
    return () => {
      live = false;
      clearTimeout(timer);
      editor?.destroyEditor?.();
      element.replaceChildren();
    };
  }, [opened, at, load, placeholder, timeoutMs, report, studyId, runId]);

  const current = state.at === at ? state : { at, kind: "opening" as const };
  const status = up.at === at ? up : { ready: false, failed: false };
  const shownOpened = current.kind === "open" && status.ready && !status.failed ? current.opened : null;
  const started = edits.at === at ? edits.startedAt : null;
  const unsent = edits.at === at && edits.dirty;
  useEffect(() => {
    onShown?.(shownOpened ? { opened: shownOpened, startedAt: started, dirty: unsent, seen } : null);
  }, [shownOpened, started, unsent, onShown, seen]);
  if (current.kind === "off") return <>{children}</>;
  if (current.kind === "said" || (current.kind === "open" && status.failed)) {
    return (
      <>
        <p role="status" className="mb-2 text-sm text-ink-muted" data-report-editor="unavailable">
          {current.kind === "said" ? current.words : UNREACHABLE}
        </p>
        {children}
      </>
    );
  }
  if (current.kind === "opening") {
    return (
      <>
        <p className="mb-2 text-sm text-ink-muted" data-report-editor="opening">Otevírám editor zprávy…</p>
        {children}
      </>
    );
  }
  const problem = problemWords(current.opened.problem);
  return (
    <section aria-label="Zpráva v editoru" data-report-editor={status.ready ? "ready" : "loading"} data-mode={mode}>
      {mode === "view" ? <p className="mb-2 text-xs text-ink-muted" data-report-editor-view>Jen ke čtení (úzká obrazovka)</p> : null}
      {problem ? <p role="alert" className="mb-2 text-sm text-status-fault" data-report-editor-problem>{problem}</p> : null}
      {status.ready ? null : <p className="mb-2 text-sm text-ink-muted">Načítám editor…</p>}
      <div ref={host} className="h-[75vh] min-h-[480px] w-full overflow-hidden rounded-card border border-border bg-surface-raised" />
    </section>
  );
}
