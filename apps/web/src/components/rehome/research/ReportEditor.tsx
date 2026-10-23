"use client";

// Zpráva's draft in the report editor (artifact-report RPT8d): the version the API opens (RPT8c),
// edited in ONLYOFFICE Docs from 768 px and read in its view mode below. The page loads the
// Document Server's api.js from the origin the API names and hands it the config the API signed;
// it signs nothing and stores nothing itself (saves reach the API from the Document Server).
// With the editor off (404) the read-only draft is the pane, as before; with a Document Server that
// fails or does not answer, the read-only draft stays and says so -- never a blank pane.

import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import { research } from "@/lib/api";
import {
  apiScriptUrl, EDIT_FROM_PX, EDITOR_TIMEOUT_MS, type EditorMode, type EditorOpened, editorMode, openFailure,
  problemWords, UNREACHABLE,
} from "@/lib/report-editor";

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
  /** The read-only draft: the pane whenever the editor is not on screen. */
  children: ReactNode;
  /** Seams for the tests: the open route and the script loader. */
  open?: typeof research.openReportEditor;
  load?: (url: string) => Promise<DocsApi>;
  timeoutMs?: number;
};

export function ReportEditor({
  studyId, runId, variant, review, children, open = research.openReportEditor, load = loadDocsApi,
  timeoutMs = EDITOR_TIMEOUT_MS,
}: ReportEditorProps) {
  const mode = useMode();
  const at = `${studyId}:${runId}:${variant}:${review ?? ""}:${mode}`;
  const [state, setState] = useState<State>({ at, kind: "opening" });
  // The editor came up (`onAppReady`), or it failed after the route answered: this document only.
  const [up, setUp] = useState<{ at: string; ready: boolean; failed: boolean }>({ at, ready: false, failed: false });
  const host = useRef<HTMLDivElement>(null);
  const placeholder = `report-editor-${useId().replace(/[^a-zA-Z0-9-]/g, "")}`;

  useEffect(() => {
    let live = true;
    open(studyId, runId, { variant, deep_research_run_id: variant === "context" ? review : null, mode }).then(
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
  }, [at, studyId, runId, variant, review, mode, open]);

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
  }, [opened, at, load, placeholder, timeoutMs]);

  const current = state.at === at ? state : { at, kind: "opening" as const };
  const status = up.at === at ? up : { ready: false, failed: false };
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
      <p className="mb-2 text-xs text-ink-muted" data-report-editor-version>
        Koncept {current.opened.koncept}{mode === "view" ? " · jen ke čtení (úzká obrazovka)" : ""}
      </p>
      {problem ? <p role="alert" className="mb-2 text-sm text-status-fault" data-report-editor-problem>{problem}</p> : null}
      {status.ready ? null : <p className="mb-2 text-sm text-ink-muted">Načítám editor…</p>}
      <div ref={host} className="h-[75vh] min-h-[480px] w-full overflow-hidden rounded-card border border-border bg-surface-raised" />
    </section>
  );
}
