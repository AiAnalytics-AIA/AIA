"use client";

// Zpráva's doc bar while the report editor shows a document (artifact-report RPT8d): the version on
// screen by name ("Koncept N, uložen <kdy> · <kdo>"), what it changed in the numbers code wrote
// ("Upraveno ručně"), the run's other lines, and "Schválit" for exactly that version, its changes
// listed in the question. The version is read from the API (RPT8c), never from the editor: a save
// the editor made is approved only once AIA stored it, and a later save, before the ask or before
// the yes, asks again.

import { useCallback, useEffect, useRef, useState } from "react";

import { research } from "@/lib/api";
import { approvalWords, reviewWords } from "@/lib/artifacts/report";
import {
  changeWords, editedApprovalQuestion, editedWords, type EditorLine, type EditorVersionRead, holdsEdit, savedWords,
} from "@/lib/report-editor";
import { approvalRefusal, reviewStatus } from "@/lib/report-status";
import type { EditorShown } from "./ReportEditor";
import { type Ask, AskDialog, Button } from "../ui";

type Approved = Awaited<ReturnType<typeof research.approveReport>>;

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export type EditorDocBarProps = {
  studyId: string;
  runId: string;
  shown: EditorShown;
  /** The composed draft the pane read: koncept 1 of the current composition, approved as before. */
  composedId: string;
  /** The document by name, for the question ("interní zprávu"). */
  documentName: string;
  canApprove: boolean;
  /** Approve the composed draft through the pane's own flow (its PDF and status read on the ask),
   *  as its line's newest: the server refuses once a save moved the line on, and `held` (read on
   *  the pane's own ask and yes) refuses while an edit waits to be stored. */
  approveComposed: (held: () => string | null) => void;
  /** An edited version was approved, as the server answered. */
  onApproved: (done: Approved) => void;
  /** Open another line in the editor. */
  onOpenLine: (lineId: string) => void;
  /** How often the bar reads again while an edit waits to be stored (a seam for the tests). */
  pollMs?: number;
};

/** An edit is stored by the Document Server's next save (a forcesave or the timed autosave), not as
 *  it is typed: while one waits, the bar reads the line again this often. */
const POLL_MS = 10_000;

const UNSTORED = "V editoru jsou úpravy, které AIA ještě neuložila jako koncept; schválit lze až uložený koncept.";
const MOVED = (koncept: number) => `Editor mezitím uložil koncept ${koncept}; zkontrolujte jeho změny a schvalte znovu.`; // = approvalRefusal's report_version_stale

/** The version `id` and, when a later save of its line exists, that one instead: the newest is the
 *  one the editor shows once its edits are saved. */
async function newestOf(studyId: string, runId: string, id: string): Promise<EditorVersionRead> {
  const read = await research.reportEditorVersion(studyId, runId, id);
  const newest = read.newest_in_line?.version_artifact_id;
  return newest && newest !== id ? research.reportEditorVersion(studyId, runId, newest) : read;
}

export function EditorDocBar({
  studyId, runId, shown, composedId, documentName, canApprove, approveComposed, onApproved, onOpenLine, pollMs = POLL_MS,
}: EditorDocBarProps) {
  const opened = shown.opened;
  const at = `${opened.line_id}:${opened.version_artifact_id}`;
  const [read, setRead] = useState<{ at: string; version: EditorVersionRead | null; error: string | null } | null>(null);
  const [open, setOpen] = useState(false);
  const [act, setAct] = useState<{ ask: Ask | null; busy: boolean; said: string | null }>({ ask: null, busy: false, said: null });
  const [reads, setReads] = useState(0);
  const again = useCallback(() => setReads((n) => n + 1), []);

  // The latest edit this person started, held off until a read finds a stored version that holds it
  // (`holdsEdit`: its last change no earlier than the edit, on the server's clock), and while the
  // editor holds an edit not yet sent. The editor's own "saved" is no stored version, and a version
  // stored before the edit, or saved while it was still being typed, does not hold it.
  const startedAt = shown.startedAt;
  const [held, setHeld] = useState<number | null>(null);
  useEffect(() => {
    let live = true;
    newestOf(studyId, runId, opened.version_artifact_id).then(
      (version) => {
        if (!live) return;
        const answeredAt = Date.now();
        setRead({ at, version, error: null });
        if (startedAt !== null && holdsEdit(version, startedAt, answeredAt)) setHeld((was) => Math.max(was ?? 0, startedAt));
      },
      (error: unknown) => { if (live) setRead({ at, version: null, error: message(error) }); },
    );
    return () => { live = false; };
  }, [at, studyId, runId, opened.version_artifact_id, reads, startedAt]);
  const waiting = (startedAt !== null && (held === null || held < startedAt)) || shown.dirty;
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(again, pollMs);
    return () => clearInterval(timer);
  }, [waiting, again, pollMs]);
  // Read on the yes, which a dialog left open may give long after the click.
  const waitingNow = useRef(waiting);
  useEffect(() => { waitingNow.current = waiting; }, [waiting]);

  const current = read?.at === at ? read : null;
  const version = current?.version ?? null;

  const approve = () => {
    if (!version) return;
    setAct({ ask: null, busy: true, said: null });
    // Read again on the ask: a save since the bar was read is the version on screen now.
    newestOf(studyId, runId, version.version_artifact_id).then(
      (now) => {
        setRead({ at, version: now, error: null });
        if (now.version_artifact_id !== version.version_artifact_id) {
          return setAct({ ask: null, busy: false, said: MOVED(now.koncept) });
        }
        if (reviewStatus(now.review_state) === "APPROVED") return setAct({ ask: null, busy: false, said: null });
        if (now.version_artifact_id === composedId) {
          setAct({ ask: null, busy: false, said: null });
          return approveComposed(() => (waitingNow.current ? UNSTORED : null));
        }
        const ask: Ask = {
          kind: "confirm",
          message: editedApprovalQuestion(now, documentName),
          yes: `Schválit koncept ${now.koncept}`,
          resolve: (ok) => {
            if (!ok) return setAct({ ask: null, busy: false, said: null });
            // An edit started while the question was open is in no stored version yet.
            if (waitingNow.current) return setAct({ ask: null, busy: false, said: UNSTORED });
            setAct({ ask: null, busy: true, said: null });
            // Read again on the yes: the dialog may have stayed open while a save stored the next koncept.
            newestOf(studyId, runId, now.version_artifact_id)
              .then((latest) => {
                if (latest.version_artifact_id !== now.version_artifact_id) {
                  setRead({ at, version: latest, error: null });
                  setAct({ ask: null, busy: false, said: MOVED(latest.koncept) });
                  return null;
                }
                // The server's check is the last word: it refuses once the line has moved on.
                return research.approveReport(studyId, runId, now.version_artifact_id, "", true);
              })
              .then(
                (done) => {
                  if (!done) return;
                  setAct({ ask: null, busy: false, said: null });
                  onApproved(done);
                  again();
                },
                (error: unknown) => {
                  setAct({ ask: null, busy: false, said: approvalRefusal(error) });
                  again();
                },
              );
          },
        };
        setAct({ ask, busy: false, said: null });
      },
      (error: unknown) => setAct({ ask: null, busy: false, said: `Verzi zprávy se nepodařilo načíst: ${message(error)}` }),
    );
  };

  const others = opened.lines.filter((l: EditorLine) => l.line_id !== (version?.line_id ?? opened.line_id));
  const edited = version ? editedWords(version) : null;
  const changes = version?.changes?.changes ?? [];
  const approved = version !== null && reviewStatus(version.review_state) === "APPROVED";
  return (
    <div className="mb-2.5 flex flex-col gap-1.5 text-xs text-ink-muted" data-editor-docbar>
      <div className="flex flex-wrap items-center gap-2">
        {version ? (
          <>
            <span className="font-semibold text-ink" data-editor-version={version.version_artifact_id}>{savedWords(version)}</span>
            <span>· {reviewWords(version)}</span>
            {version.approval ? <span>· {approvalWords(version.approval, version.approved_on)}</span> : null}
          </>
        ) : current?.error ? (
          <span role="alert" className="text-status-fault">Verzi v editoru se nepodařilo načíst: {current.error}</span>
        ) : (
          <span>Načítám verzi v editoru…</span>
        )}
        {canApprove && version && !approved ? (
          <Button className="!min-h-11 ml-auto" disabled={act.busy || waiting} onClick={approve}>
            Schválit koncept {version.koncept}
          </Button>
        ) : null}
      </div>
      {waiting ? <p data-editor-unsaved>{UNSTORED}</p> : null}
      {edited ? (
        changes.length ? (
          <div>
            <button type="button" className="underline decoration-dotted" aria-expanded={open} onClick={() => setOpen((o) => !o)} data-editor-edited>
              {edited}
            </button>
            {open ? (
              <ul className="mt-1 list-disc pl-5 text-ink" data-editor-changes>
                {changes.map((c, i) => <li key={`${c.kind}:${c.tag ?? ""}:${i}`}>{changeWords(c)}</li>)}
              </ul>
            ) : null}
          </div>
        ) : <p data-editor-edited>{edited}</p>
      ) : null}
      {others.length ? (
        <div className="flex flex-wrap items-center gap-2" data-editor-lines>
          <span>Další řady úprav:</span>
          {others.map((l) => (
            <Button key={l.line_id} variant="quiet" className="!min-h-11" onClick={() => onOpenLine(l.line_id)}>
              Koncept {l.koncept}{l.current_composition ? "" : " (ze starší složené zprávy)"}
            </Button>
          ))}
        </div>
      ) : null}
      {act.said ? <p role="alert" className="text-sm text-status-fault">{act.said}</p> : null}
      <AskDialog ask={act.ask} onDone={() => setAct((was) => ({ ...was, ask: null }))} />
    </div>
  );
}
