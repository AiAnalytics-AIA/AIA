"use client";

// Zpráva's doc bar while the report editor shows a document (artifact-report RPT8d): the version on
// screen by name ("Koncept N, uložen <kdy> · <kdo>"), what it changed in the numbers code wrote
// ("Upraveno ručně"), the run's other lines, and "Schválit" for exactly that version, its changes
// listed in the question. The version is read from the API (RPT8c), never from the editor: a save
// the editor made is approved only once AIA stored it, and a later save asks again.

import { useCallback, useEffect, useState } from "react";

import { research } from "@/lib/api";
import { approvalWords, reviewWords } from "@/lib/artifacts/report";
import {
  changeWords, editedApprovalQuestion, editedWords, type EditorLine, type EditorVersionRead, savedWords,
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
  /** Approve the composed draft through the pane's own flow (its PDF and status read on the ask). */
  approveComposed: () => void;
  /** An edited version was approved, as the server answered. */
  onApproved: (done: Approved) => void;
  /** Open another line in the editor. */
  onOpenLine: (lineId: string) => void;
};

/** The version `id` and, when a later save of its line exists, that one instead: the newest is the
 *  one the editor shows once its edits are saved. */
async function newestOf(studyId: string, runId: string, id: string): Promise<EditorVersionRead> {
  const read = await research.reportEditorVersion(studyId, runId, id);
  const newest = read.newest_in_line?.version_artifact_id;
  return newest && newest !== id ? research.reportEditorVersion(studyId, runId, newest) : read;
}

export function EditorDocBar({
  studyId, runId, shown, composedId, documentName, canApprove, approveComposed, onApproved, onOpenLine,
}: EditorDocBarProps) {
  const opened = shown.opened;
  const at = `${opened.line_id}:${opened.version_artifact_id}`;
  const [read, setRead] = useState<{ at: string; version: EditorVersionRead | null; error: string | null } | null>(null);
  const [open, setOpen] = useState(false);
  const [act, setAct] = useState<{ ask: Ask | null; busy: boolean; said: string | null }>({ ask: null, busy: false, said: null });
  const [reads, setReads] = useState(0);
  const again = useCallback(() => setReads((n) => n + 1), []);

  useEffect(() => {
    let live = true;
    newestOf(studyId, runId, opened.version_artifact_id).then(
      (version) => { if (live) setRead({ at, version, error: null }); },
      (error: unknown) => { if (live) setRead({ at, version: null, error: message(error) }); },
    );
    return () => { live = false; };
  }, [at, studyId, runId, opened.version_artifact_id, reads]);
  // Edits just saved: the line may have a newer version now.
  const [wasDirty, setWasDirty] = useState(shown.dirty);
  if (wasDirty !== shown.dirty) {
    setWasDirty(shown.dirty);
    if (!shown.dirty) setReads((n) => n + 1);
  }

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
          return setAct({ ask: null, busy: false, said: `Editor mezitím uložil koncept ${now.koncept}; zkontrolujte jeho změny a schvalte znovu.` });
        }
        if (reviewStatus(now.review_state) === "APPROVED") return setAct({ ask: null, busy: false, said: null });
        if (now.version_artifact_id === composedId) {
          setAct({ ask: null, busy: false, said: null });
          return approveComposed();
        }
        const ask: Ask = {
          kind: "confirm",
          message: editedApprovalQuestion(now, documentName),
          yes: `Schválit koncept ${now.koncept}`,
          resolve: (ok) => {
            if (!ok) return setAct({ ask: null, busy: false, said: null });
            setAct({ ask: null, busy: true, said: null });
            research.approveReport(studyId, runId, now.version_artifact_id).then(
              (done) => {
                setAct({ ask: null, busy: false, said: null });
                onApproved(done);
                again();
              },
              (error: unknown) => setAct({ ask: null, busy: false, said: approvalRefusal(error) }),
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
          <Button className="!min-h-11 ml-auto" disabled={act.busy || shown.dirty} onClick={approve}>
            Schválit koncept {version.koncept}
          </Button>
        ) : null}
      </div>
      {shown.dirty ? <p data-editor-unsaved>V editoru jsou neuložené úpravy; schválit lze až uložený koncept.</p> : null}
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
