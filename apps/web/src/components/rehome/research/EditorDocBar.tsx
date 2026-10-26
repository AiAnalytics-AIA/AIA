"use client";

// Zpráva's doc bar while the report editor shows a document (artifact-report RPT8d): the version on
// screen by name ("Koncept N, uložen <kdy> · <kdo>"), what it changed in the numbers code wrote
// ("Upraveno ručně"), the run's other lines, and "Schválit" for exactly that version, its changes
// listed in the question. The version is read from the API (RPT8c), never from the editor: a save
// the editor made is approved only once AIA stored it, and a later save, before the ask or before
// the yes, asks again.

import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { research } from "@/lib/api";
import { approvalWords, reviewWords } from "@/lib/artifacts/report";
import { saveBlob } from "@/lib/download";
import {
  changeWords, editedApprovalQuestion, editedWords, type EditorLine, type EditorVersionRead, savedWords,
  type SeenEdit, UNSTORED, unsavedWords,
} from "@/lib/report-editor";
import { approvalRefusal, reviewStatus } from "@/lib/report-status";
import { downloadMismatch } from "@/lib/report-variant";
import type { EditorShown } from "./ReportEditor";
import { type Ask, AskDialog, Button } from "../ui";
import { Icon } from "../icons";


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
  /** Whether the reader may download (EXPORT_DELIVERABLE, as the pane's own exports). */
  canExport: boolean;
  /** The pane's exports of the composed draft, shown while the editor shows koncept 1 (RPT3c). */
  composedExports: ReactNode;
  /** Approve the composed draft through the pane's own flow (its PDF and status read on the ask),
   *  as its line's newest: the server refuses once a save moved the line on, and `held` (read on
   *  the pane's own ask and yes) refuses while an edit waits to be stored. */
  approveComposed: (held: () => string | null, seen: () => SeenEdit | null) => void;
  /** Open another line in the editor. */
  onOpenLine: (lineId: string) => void;
  /** How often the bar reads again while an edit waits to be stored (a seam for the tests). */
  pollMs?: number;
};

/** An edit is stored by the Document Server's next save (a forcesave or the timed autosave), not as
 *  it is typed: while one waits, the bar reads the line again this often. */
const POLL_MS = 10_000;

const MOVED = (koncept: number) => `Editor mezitím uložil koncept ${koncept}; zkontrolujte jeho změny a schvalte znovu.`; // = approvalRefusal's report_version_stale

/** The version `id` and, when a later save of its line exists, that one instead: the newest is the
 *  one the editor shows once its edits are saved. Read with the page's last edit (`seen`), so its
 *  verdict counts that edit too (RPT8f). */
async function newestOf(studyId: string, runId: string, id: string, seen: SeenEdit | null): Promise<EditorVersionRead> {
  const read = await research.reportEditorVersion(studyId, runId, id, seen);
  const newest = read.newest_in_line?.version_artifact_id;
  if (!newest || newest === id) return read;
  return research.reportEditorVersion(studyId, runId, newest, seen);
}

export function EditorDocBar({
  studyId, runId, shown, composedId, documentName, canApprove, canExport, composedExports, approveComposed, onOpenLine,
  pollMs = POLL_MS,
}: EditorDocBarProps) {
  const opened = shown.opened;
  const at = `${opened.line_id}:${opened.version_artifact_id}`;
  const [read, setRead] = useState<{ at: string; version: EditorVersionRead | null; error: string | null } | null>(null);
  const [open, setOpen] = useState(false);
  const [act, setAct] = useState<{ ask: Ask | null; busy: boolean; said: string | null }>({ ask: null, busy: false, said: null });
  const [reads, setReads] = useState(0);
  const again = useCallback(() => setReads((n) => n + 1), []);

  // The server decides (RPT8f): the approval waits until a read's verdict says the version holds
  // every edit its line's open session reported and this page's last one, read with that edit;
  // a read from before the page's newest edit says nothing of it. And while the editor holds an
  // edit not yet sent. The editor's own "saved" is no stored version.
  const startedAt = shown.startedAt;
  const seen = shown.seen;
  const [verdict, setVerdict] = useState<{ at: string; seq: number; saved: boolean } | null>(null);
  useEffect(() => {
    let live = true;
    const asked = seen();
    newestOf(studyId, runId, opened.version_artifact_id, asked).then(
      (version) => {
        if (!live) return;
        setRead({ at, version, error: null });
        setVerdict({ at, seq: asked?.seq ?? 0, saved: version.edits?.saved === true });
      },
      (error: unknown) => { if (live) setRead({ at, version: null, error: message(error) }); },
    );
    return () => { live = false; };
  }, [at, studyId, runId, opened.version_artifact_id, reads, startedAt, seen]);
  const counted = verdict !== null && verdict.at === at && verdict.saved && verdict.seq >= (seen()?.seq ?? 0);
  const waiting = !counted || shown.dirty;
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
    newestOf(studyId, runId, version.version_artifact_id, shown.seen()).then(
      (now) => {
        setRead({ at, version: now, error: null });
        if (now.version_artifact_id !== version.version_artifact_id) {
          return setAct({ ask: null, busy: false, said: MOVED(now.koncept) });
        }
        if (reviewStatus(now.review_state) === "APPROVED") return setAct({ ask: null, busy: false, said: null });
        if (now.version_artifact_id === composedId) {
          setAct({ ask: null, busy: false, said: null });
          return approveComposed(() => (waitingNow.current ? UNSTORED : null), shown.seen);
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
            newestOf(studyId, runId, now.version_artifact_id, shown.seen())
              .then((latest) => {
                if (latest.version_artifact_id !== now.version_artifact_id) {
                  setRead({ at, version: latest, error: null });
                  setAct({ ask: null, busy: false, said: MOVED(latest.koncept) });
                  return null;
                }
                // The server's verdict on that read, then an edit started while it was in flight:
                // checked again as the approval leaves.
                if (latest.edits?.saved !== true || waitingNow.current) {
                  setAct({ ask: null, busy: false, said: UNSTORED });
                  return null;
                }
                // The server's check is the last word (RPT8f): under the line's lock it refuses once the
                // line has moved on, or while an edit it received, or the last one this page made, is
                // in no stored version.
                return research.approveReport(studyId, runId, now.version_artifact_id, "", true, shown.seen());
              })
              .then(
                (done) => {
                  if (!done) return;
                  setAct({ ask: null, busy: false, said: null });
                  again();
                },
                (error: unknown) => {
                  setAct({ ask: null, busy: false, said: unsavedWords(error) ?? approvalRefusal(error) });
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

  // An edited koncept downloaded from where it is read (RPT3c): read again first, so a save since
  // the bar was read is never handed over as the koncept the bar names; the file is checked to be
  // that version in that review. Not while an edit waits to be stored: the file would not hold it.
  const download = () => {
    if (!version) return;
    setAct({ ask: null, busy: true, said: null });
    newestOf(studyId, runId, version.version_artifact_id, shown.seen())
      .then(async (now) => {
        setRead({ at, version: now, error: null });
        if (now.version_artifact_id !== version.version_artifact_id) return setAct({ ask: null, busy: false, said: MOVED(now.koncept) });
        const got = await research.downloadReportEditorVersion(studyId, runId, now.version_artifact_id);
        const why = downloadMismatch({ artifactId: got.artifactId, reviewState: got.reviewState }, { artifactId: now.version_artifact_id, reviewState: now.review_state });
        if (why) return setAct({ ask: null, busy: false, said: why });
        saveBlob(got.blob, got.filename ?? `zprava-koncept-${now.koncept}.docx`);
        setAct({ ask: null, busy: false, said: null });
      })
      .catch((error: unknown) => setAct({ ask: null, busy: false, said: `Verzi zprávy se nepodařilo stáhnout: ${message(error)}` }));
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
        {/* Koncept 1 by the pane's own exports, under the same rule as an edited koncept: not while an
            edit waits to be stored, since the file would not hold it (delta review of #985). */}
        {version && version.version_artifact_id === composedId ? (waiting ? null : composedExports) : canExport && version ? (
          <Button variant="quiet" className="!min-h-11" disabled={act.busy || waiting} onClick={download}>
            <Icon name="download" size={16} /> Stáhnout koncept {version.koncept} (DOCX)
          </Button>
        ) : null}
      </div>
      {waiting && version ? <p data-editor-unsaved>{UNSTORED}</p> : null}
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
