"use client";

// Zpráva's document first (artifact-report RPT2): the run's internal draft rendered in the pane from
// its stored document model (report-delivery RD5a), in the report's print order -- sections,
// paragraphs, tables and figures, each number a chip that opens its claim in the item inspector.
// The DOCX stays the deliverable; this reads the document beside it and prints only what it holds:
// a number is the text the DOCX prints, a suppressed one is never shown, an unknown ref is "?".

import { type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { ApiError, deepResearch, type DeepResearchRun, research, type ResearchRun } from "@/lib/api";
import {
  type Block, type Cell, claimLines, claimTarget, gradeWords, type Inline, type LedgerEntry, type ListItem,
  approvalWords, readDocument, type ReportDocumentModel, reviewWords, type Section, sectionTarget, blockTarget,
  type StoredReportDocument, editedLineWords, markSpans, sentenceMarks, unresolvedRefs, valueWords, warningsWords,
} from "@/lib/artifacts/report";
import { backEntry, closeStack, emptyStack, openEntry, type InspectorStack } from "@/lib/inspector-stack";
import { isModelled, stepOf } from "@/lib/research-execution";
import { useFrame } from "./frame-hook";
import { useItemInspector } from "@/components/workbench/item-inspector-context";
import { ItemInspector } from "./ItemInspector";
import { EditorDocBar } from "./EditorDocBar";
import { ReportExports } from "./ReportDocBar";
import { type EditorShown, ReportEditor } from "./ReportEditor";
import { canReview } from "./frame";
import { type Ask, AskDialog, Button } from "../ui";
import { t } from "@/i18n/t";
import { approvalQuestion, fileLine, pdfStatesReview, reviewLabel, reviewsFor, type VersionReview } from "@/lib/report-variant";
import { approvalRefusal, reviewStatus } from "@/lib/report-status";
import { type SeenEdit, unsavedWords } from "@/lib/report-editor";
import { coverageRecord, type CoverageLine } from "@/lib/artifacts/report-coverage";

// A line carrying an id or a SHA-256 breaks anywhere: an unbroken hash would widen the page past a
// phone's width (the 390 px journey).
const WRAPS = "[overflow-wrap:anywhere]";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

type Loaded =
  | { state: "loading" }
  | { state: "none" }
  // `prepared`: a preparation answered so too, so preparing again would change nothing (an approved
  // version is handed over as approved, and no document is composed beside it).
  | { state: "not_stored"; prepared?: boolean }
  | { state: "unprepared" }
  | { state: "refused"; prepared?: boolean }
  | { state: "failed"; message: string }
  | { state: "ready"; stored: StoredReportDocument; doc: ReportDocumentModel };

type Approved = Awaited<ReturnType<typeof research.approveReport>>;

/** A composed draft's approval asked from the editor's doc bar: why it must wait, or null. */
type EditorAsk = { held: () => string | null; seen: () => SeenEdit | null };

/** Which document the pane reads: the internal draft, the client report (RD3), or the report with
 *  one completed literature review (RPT3a). */
type Kind = "internal" | "client" | "with_review";

const KIND_NAME: Record<Kind, string> = { internal: "Interní zpráva", client: "Klientská zpráva", with_review: "Zpráva s rešerší" };

/** The run's stored draft of `kind` (with `review`, the literature review it carries), read once per
 *  state of its report step. A client report or a report with literature not yet prepared is
 *  `unprepared`: `prepare` composes and stores it, and answers its document. */
function useReportDocument(studyId: string, run: ResearchRun, kind: Kind, review: string | null): {
  loaded: Loaded; prepare: () => void; approved: (version: string, done: Approved) => void;
} {
  const step = stepOf(run, "report");
  // A report with literature is composed on its own: the run's own report need not have succeeded.
  const ready = kind === "with_review" || step?.status === "SUCCEEDED";
  const key = `${studyId}:${run.run_id}:${step?.status ?? ""}:${step?.artifact_id ?? ""}:${kind}:${review ?? ""}`;
  const [answer, setAnswer] = useState<{ key: string; loaded: Loaded } | null>(null);
  // The document asked for now: an answer for another (a prepare that returns after a switch) is dropped.
  const current = useRef(key);
  useEffect(() => { current.current = key; }, [key]);
  const settle = useCallback((read: Promise<StoredReportDocument>, at: string, live: () => boolean, prepared = false) => {
    read.then(
      (stored) => {
        const doc = readDocument(stored.document);
        if (live()) setAnswer({ key: at, loaded: doc ? { state: "ready", stored, doc } : { state: "refused" } });
      },
      (error: unknown) => {
        if (!live()) return;
        const code = error instanceof ApiError ? error.code : "";
        const status = error instanceof ApiError ? error.status : 0;
        const loaded: Loaded =
          // 404: none stored yet, which for the client report means not prepared; 403: a reader
          // who may not see this draft sees nothing of it.
          status === 404 ? (kind === "client" ? { state: "unprepared" }
            // A review or run not found: said, the switch kept, never the pane gone with it.
            : kind === "with_review" ? { state: "failed", message: "Zprávu s touto rešerší AIA nenašla." } : { state: "none" })
            // The switch stays when another document is refused: the internal draft is one click back.
            : status === 403 ? (kind === "internal" ? { state: "none" } : { state: "failed", message: kind === "client" ? "Klientskou zprávu číst nemůžete." : "Zprávu s rešerší číst nemůžete." })
              : code === "context_report_not_prepared" ? { state: "unprepared" }
              : code === "report_document_not_stored" ? { state: "not_stored", prepared }
                : code === "report_artifact_invalid" ? { state: "refused", prepared }
                  : { state: "failed", message: message(error) };
        setAnswer({ key: at, loaded });
      },
    );
  }, [kind]);
  useEffect(() => {
    if (!ready) return;
    let live = true;
    const read = kind === "with_review" && review !== null ? deepResearch.contextReportDocument(studyId, run.run_id, review)
      : kind === "client" ? research.clientReportDocument(studyId, run.run_id) : research.reportDocument(studyId, run.run_id);
    settle(read, key, () => live);
    return () => { live = false; };
  }, [studyId, run.run_id, key, ready, kind, review, settle]);
  const prepare = useCallback(() => {
    setAnswer({ key, loaded: { state: "loading" } });
    const prepared = kind === "with_review" && review !== null
      // Stored once with its document, its PDF asked for; then that document read (RPT3a).
      ? deepResearch.prepareContextReport(studyId, run.run_id, review).then(() => deepResearch.contextReportDocument(studyId, run.run_id, review))
      : research.prepareClientReport(studyId, run.run_id);
    settle(prepared, key, () => current.current === key, true);
  }, [key, kind, review, settle, studyId, run.run_id]);
  // An approval made here, as the server answered it, on the version it names: the document stays
  // on screen (no reload, no lost place), and only a version still shown takes it.
  const approved = useCallback((version: string, done: Approved) => {
    setAnswer((was) => (was?.key === key && was.loaded.state === "ready" && was.loaded.stored.report_artifact_id === version
      ? { key, loaded: { ...was.loaded, stored: { ...was.loaded.stored, review_state: done.review_state, approved_on: done.approved_on ?? null, stamped: done.stamped ?? was.loaded.stored.stamped, approval: done.approval ?? null } } }
      : was));
  }, [key]);
  if (!ready) return { loaded: { state: "none" }, prepare, approved };
  return { loaded: answer?.key === key ? answer.loaded : { state: "loading" }, prepare, approved };
}

/** ``review``: the literature review the results page holds (InterpretationResearch's "Použít ve
 *  zprávě"); choosing it opens the report with that review here, and choosing a document here tells
 *  ``onReview`` which review it carries, null for none (RPT3c, spec Z9). */
export function ReportDocumentView({ run, review: held = null, onReview }: { run: ResearchRun; review?: string | null; onReview?: (id: string | null) => void }) {
  const frame = useFrame();
  // The client report exists only for a run whose respondents were modelled from the population;
  // the pane shows one document at a time, so the Lead's report: ids name exactly one.
  const offersClient = isModelled(run);
  // The completed literature reviews of this run, each a report of its own (RPT3a): read for a
  // reader who may review, as the route asks; unread is none offered, never a guess.
  const [reviews, setReviews] = useState<{ runId: string; list: DeepResearchRun[] } | null>(null);
  const mayReview = canReview(frame);
  // Read again while any review of the run is still under way, so one that completes on this page
  // is offered without a reload (the card's approval of it is gone, RPT3a).
  const [reviewReads, setReviewReads] = useState(0);
  useEffect(() => {
    if (!mayReview) return;
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    deepResearch.runs(frame.studyId, 100).then(
      (all) => {
        if (!live) return;
        setReviews({ runId: run.run_id, list: reviewsFor(all, run.run_id) });
        const underWay = all.some((r) => r.purpose === "INTERPRETATION_RESEARCH" && r.target?.research_run_id === run.run_id && !r.is_terminal);
        if (underWay) timer = setTimeout(() => setReviewReads((n) => n + 1), 10_000);
      },
      () => undefined,
    );
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, [frame.studyId, run.run_id, mayReview, reviewReads]);
  const offered = reviews?.runId === run.run_id ? reviews.list : [];
  const [chosen, setChosen] = useState<{ kind: Kind; review: string | null }>(held ? { kind: "with_review", review: held } : { kind: "internal", review: null });
  // The page's review moved (chosen on the review panel): the pane follows that change, during
  // render; a document chosen here is the pane's own and is only told onward.
  const [followed, setFollowed] = useState(held);
  if (held !== followed) {
    setFollowed(held);
    // A review completed since the list was read is offered once the list is read again.
    if (held) setReviewReads((n) => n + 1);
    setChosen(held ? { kind: "with_review", review: held } : (was) => (was.kind === "with_review" ? { kind: "internal", review: null } : was));
  }
  const kind: Kind = chosen.kind === "client" ? (offersClient ? "client" : "internal")
    : chosen.kind === "with_review" ? (offered.some((r) => r.run_id === chosen.review) ? "with_review" : "internal") : "internal";
  const review = kind === "with_review" ? chosen.review : null;
  // One id per document an approval's slot names; the inspector's entries name the kind alone, so
  // their ids stay within the target grammar (one document is shown at a time).
  const docId = review ? `with_review:${review}` : kind;
  const { loaded, prepare, approved } = useReportDocument(frame.studyId, run, kind, review);
  // Approval on the document being read (RPT3a): the version shown is the version approved, asked
  // first by name (B22). Its question, its flight and its refusal belong to that slot (the document
  // and version shown): another document on screen shows none of them, so a question never outlives
  // the version it named. `done`: approved here where no document is shown to say so.
  const [act, setAct] = useState<{ slot: string; ask: Ask | null; busy: boolean; refused: string | null; done?: boolean } | null>(null);
  // A slot names the run, its report step's artifact and the document: an unshown draft's slot is
  // never another run's or another version's.
  const slotOf = (shown: StoredReportDocument | null) =>
    `${run.run_id}:${stepOf(run, "report")?.artifact_id ?? ""}:${docId}:${shown?.report_artifact_id ?? "notice"}`;
  // The slot on screen now: a read that answers after it moved is dropped, never asked about.
  const slotNow = useRef("");
  const unshownInternal = kind !== "client" && (loaded.state === "not_stored" || loaded.state === "refused" || loaded.state === "failed");
  const currentSlot = loaded.state === "ready" ? slotOf(loaded.stored) : unshownInternal ? slotOf(null) : "";
  useEffect(() => { slotNow.current = currentSlot; }, [currentSlot]);
  // `editor`: asked from the editor's doc bar (RPT8d), where the draft is koncept 1 of the line shown:
  // approved as that line's newest, and only while `held()` says no edit waits to be stored, read on
  // the yes as on the ask (an edit can start while the status is read or the question is open).
  // Asked by the document's name and when its version was stored (RPT3d, spec Z4), never its id.
  // The client report's numbers are modelled.
  const confirm = (slot: string, version: string, file: VersionReview, pdf: boolean, shown: StoredReportDocument | null, editor?: EditorAsk) => {
    const title = kind === "with_review" ? offered.find((r) => r.run_id === review)?.title : null;
    const question = approvalQuestion(title ? `${KIND_NAME[kind]} · ${title}` : KIND_NAME[kind], { storedAt: file.storedAt, pdf, modelled: kind === "client" });
    // What the file carries (D2): known only when stamped; the version named above, not by its id.
    const carries = fileLine(file, pdf);
    // The version's checks (RD0 on the client report, RD7 on every report): warnings named in the
    // question, recorded with the yes.
    const warned = warningsWords(shown?.warnings, shown?.document);
    const ask: Ask = {
      kind: "confirm",
      message: [question, carries, warned].filter(Boolean).join(" "),
      yes: t("research.exec.report.approveAsk.yes"),
      resolve: (ok) => {
        if (!ok) return;
        const held = editor?.held();
        if (held) return setAct({ slot, ask: null, busy: false, refused: held });
        setAct({ slot, ask: null, busy: true, refused: null });
        (editor ? research.approveReport(frame.studyId, run.run_id, version, "", true, editor.seen()) : research.approveReport(frame.studyId, run.run_id, version)).then(
          (done) => {
            setAct(shown ? null : { slot, ask: null, busy: false, refused: null, done: true });
            if (shown) approved(version, done);
          },
          (error: unknown) => setAct({ slot, ask: null, busy: false, refused: unsavedWords(error) ?? approvalRefusal(error) }),
        );
      },
    };
    setAct({ slot, ask, busy: false, refused: null });
  };
  // `shown`: the document on screen, or null for an internal draft or a report with literature the
  // pane cannot show (stored before its document, or refused), approved as the version its run
  // names: the DOCX its download hands over, as the card approved it before.
  const askApproval = (shown: StoredReportDocument | null, editor?: EditorAsk) => {
    const slot = slotOf(shown);
    if (kind === "client") {
      if (shown) confirm(slot, shown.report_artifact_id, { version: shown.report_artifact_id, reviewState: shown.review_state, approvedOn: shown.approved_on, stamped: shown.stamped, storedAt: shown.stored_at }, false, shown);
      return;
    }
    // An internal draft's approval, with or without literature, also approves its PDF, so the
    // question says so only as its status states it now, for exactly this version (D2): read on
    // the ask, never remembered.
    setAct({ slot, ask: null, busy: true, refused: null });
    const status = review !== null ? deepResearch.contextReport(frame.studyId, run.run_id, review) : research.report(frame.studyId, run.run_id);
    status.then(
      (report) => {
        if (slotNow.current !== slot) return;
        const version = report.artifact_id;
        const refuse = (refused: string) => setAct({ slot, ask: null, busy: false, refused });
        if (!version) return refuse("Běh zatím neuvádí žádnou verzi zprávy ke schválení.");
        if (shown && version !== shown.report_artifact_id) {
          return refuse(`Běh nyní uvádí jinou verzi zprávy (${version}), než je zde zobrazena; načtěte stránku znovu.`);
        }
        // Approved meanwhile, by someone else: said as such, the document shown updated in place.
        if (reviewStatus(report.review_state) === "APPROVED") {
          const done: Approved = { run_id: run.run_id, artifact_id: version, review_state: "APPROVED_INTERNAL", approved_on: report.approved_on ?? null, stamped: report.stamped ?? null, approval: null, internal_only: true };
          if (shown) {
            setAct(null);
            approved(version, done);
          } else setAct({ slot, ask: null, busy: false, refused: null, done: true });
          return;
        }
        // A version saved over the draft in the editor stands over it: the draft is not offered.
        const over = editedLineWords(report.edited_line);
        if (over) return refuse(over);
        const held = editor?.held();
        if (held) return refuse(held);
        confirm(slot, version, { version, reviewState: report.review_state, approvedOn: report.approved_on, stamped: report.stamped, storedAt: report.stored_at },
          pdfStatesReview(report.review_state, report.pdf, report.approval_renders_pdf), shown, editor);
      },
      (error: unknown) => { if (slotNow.current === slot) setAct({ slot, ask: null, busy: false, refused: `Stav zprávy se nepodařilo načíst: ${message(error)}` }); },
    );
  };
  // The approval controls for one slot: the button while it is not approved, its refusal, its question.
  const approval = (shown: StoredReportDocument | null) => {
    const mine = act?.slot === slotOf(shown) ? act : null;
    const approvedAlready = mine?.done || (shown !== null && reviewStatus(shown.review_state) === "APPROVED");
    const over = editedLineWords(shown?.edited_line);
    return {
      button: canReview(frame) && !approvedAlready && !over ? (
        <Button className="!min-h-11 ml-auto" disabled={mine?.busy} onClick={() => askApproval(shown)}>
          {t(kind === "client" ? "research.exec.results.reportApproveClient" : "research.exec.results.reportApprove")}
        </Button>
      ) : null,
      after: (
        <>
          {mine?.done ? <p role="status" className="mb-2 text-sm text-ink-muted">{t("research.exec.results.reportApprovedInternal")}</p> : null}
          {mine?.refused ? <p role="alert" className="mb-2 text-sm text-status-fault">{mine.refused}</p> : null}
          <AskDialog ask={mine?.ask ?? null} onDone={() => setAct((was) => (was ? { ...was, ask: null } : was))} />
        </>
      ),
    };
  };
  // What the report editor shows for which document, if it shows one, and the line asked for (RPT8d).
  const [shownInEditor, setShownInEditor] = useState<{ doc: string; shown: EditorShown | null } | null>(null);
  const showInEditor = useCallback((shown: EditorShown | null) => setShownInEditor({ doc: docId, shown }), [docId]);
  const [lineAsked, setLineAsked] = useState<{ doc: string; line: string } | null>(null);
  const [stack, setStack] = useState<InspectorStack>(() => emptyStack("report"));
  // Inside the workbench a claim opens in its one item drawer, under the frame's Escape order;
  // outside it (and for a ref the target grammar refuses) in this view's own.
  const inspector = useItemInspector();
  // A claim belongs to one document's ledger: switching closes it, in this view's drawer and in
  // the workbench's (the old document's entries, review of #689).
  const setDoc = (k: Kind, r: string | null = null) => {
    if (k !== kind || r !== review) inspector?.closeWhere(`report:ref:${kind}:`);
    setChosen({ kind: k, review: r });
    setStack(closeStack);
    const carries = k === "with_review" ? r : null;
    if (carries !== held) onReview?.(carries);
  };
  const openOwn = useCallback((ref: string) => setStack((s) => openEntry(s, { id: ref, title: `Tvrzení ${ref}`, sub: "Číslo ve zprávě a jeho evidence" })), []);
  const back = useCallback(() => setStack(backEntry), []);
  const close = useCallback(() => setStack(closeStack), []);

  // One document at a time, chosen in the doc bar; the client report is read here, never downloaded
  // to be read (RD3), and approved on the version read (RPT3a).
  const docs: { kind: Kind; review: string | null; label: string }[] = [
    { kind: "internal", review: null, label: KIND_NAME.internal },
    ...(offersClient ? [{ kind: "client" as const, review: null, label: KIND_NAME.client }] : []),
    // One per completed review; named by its title where several could be told apart by nothing else.
    ...offered.map((r, i) => ({ kind: "with_review" as const, review: r.run_id, label: offered.length > 1 ? `${KIND_NAME.with_review} · ${reviewLabel(r, i)}` : KIND_NAME.with_review })),
  ];
  const choose = docs.length > 1 ? (
    <div role="group" aria-label="Dokument" className="mb-2 flex flex-wrap gap-2" data-report-kind>
      {docs.map((d) => {
        const on = d.kind === kind && d.review === review;
        return (
          <Button key={`${d.kind}:${d.review ?? ""}`} variant={on ? "primary" : "quiet"} className="!min-h-11" aria-pressed={on} onClick={() => setDoc(d.kind, d.review)}>
            {d.label}
          </Button>
        );
      })}
    </div>
  ) : null;
  const notice = noticeOf(loaded, kind, prepare, mayReview);
  // Nothing stored for this document: the picker still offers the others (a report with literature
  // is prepared whatever the run's own report did).
  if (notice === undefined) return choose ? <div>{choose}</div> : null;
  if (notice !== null || loaded.state !== "ready") {
    // An internal draft the pane cannot show is still approved here, on the version its run names.
    // It is downloaded here too, as the version the run names (RPT3c: the card no longer does).
    const unshown = unshownInternal ? approval(null) : null;
    return (
      <div>
        {choose}{notice}
        {unshown ? (
          <div className="mt-2 flex flex-wrap items-center gap-2" data-report-docbar>
            {unshown.button}
            <ReportExports studyId={frame.studyId} runId={run.run_id} kind={kind} review={review} stored={null} canAct={mayReview} />
          </div>
        ) : null}
        {unshown?.after}
      </div>
    );
  }

  const { stored, doc } = loaded;
  const controls = approval(stored);
  // The doc bar names and approves the version on screen (RPT3a): while the editor shows the
  // document, that is the editor's version, read from the API (RPT8d), not the composed draft.
  const inEditor = shownInEditor?.doc === docId ? shownInEditor.shown : null;
  const line = lineAsked?.doc === docId ? lineAsked.line : null;
  const missing = unresolvedRefs(doc);
  // The sentences the check marks (RD7), by block: marked where they are, never refused.
  const marks = sentenceMarks(stored.warnings);
  const entry = (ref: string): LedgerEntry | undefined => doc.ledger.refs[ref];
  const claim = (ref: string) => <ul className="flex flex-col gap-1">{claimLines(entry(ref)).map((line) => <li key={line}>{line}</li>)}</ul>;
  const open = (ref: string) => {
    const framed = inspector?.open({ id: `report:ref:${kind}:${ref}`, title: `Tvrzení ${ref}`, sub: "Číslo ve zprávě a jeho evidence" }, () => claim(ref));
    if (!framed) openOwn(ref);
  };
  const draft = (
    <article aria-label="Koncept zprávy" className="rounded-card border border-border bg-surface-raised px-4 py-5 font-serif shadow-sm sm:px-8 lg:px-14 lg:py-10">
      <header className="mb-4 border-b border-border pb-4">
        <p className="font-sans text-xs text-ink-muted">{doc.meta.client_name} · {doc.meta.study_name}</p>
        <h1 className="mt-1 text-2xl font-semibold leading-tight sm:text-[28px]">{doc.meta.title}</h1>
        <p className="mt-1 font-sans text-sm text-ink-muted">{doc.meta.subtitle}</p>
      </header>
      {doc.sections.map((section) => (
        <DocSection key={section.id} section={section} entry={entry} onClaim={open} refs={Object.keys(doc.ledger.refs)} marks={marks} />
      ))}
      <footer className="mt-6 border-t border-border pt-2 font-sans text-[11px] text-ink-muted" data-report-foot>
        {/* No ids on the stage (RPT12): the review in words and the revision the draft was composed from. */}
        {reviewWords(stored, kind === "client" ? "client" : "internal")} · revize {doc.meta.revision}
      </footer>
    </article>
  );
  return (
    // The pane's own width decides the layout, not the window's: the workbench's split can leave the
    // artifact narrow on a wide screen.
    <div className="@container" data-report-document="ready"><div className="flex min-w-0 flex-col gap-3 @3xl:flex-row @3xl:items-start">
      <div className="min-w-0 flex-1">
        {choose}
        {/* The version shown, for the tests and the journeys, never as text (RPT12). */}
        <div className="mb-2.5 flex flex-wrap items-center gap-2 text-xs text-ink-muted" data-report-docbar data-report-version={inEditor ? undefined : stored.report_artifact_id}>
          <span className="font-semibold text-ink">{KIND_NAME[kind]}</span>
          {inEditor ? <span>· v editoru</span> : (
            <>
              <span>· {reviewWords(stored, kind === "client" ? "client" : "internal")}</span>
              {stored.approval ? <span data-approval>· {approvalWords(stored.approval, stored.approved_on)}</span> : null}
              {controls.button}
              {/* Every export of the document on screen, from where it is read (RPT3c). */}
              <ReportExports studyId={frame.studyId} runId={run.run_id} kind={kind} review={review} stored={stored} canAct={mayReview} />
            </>
          )}
        </div>
        {/* The editor names its own version; without it, what stands over the draft is said here. */}
        {!inEditor && stored.edited_line ? (
          <p role="status" className="mb-2 text-sm text-ink-muted" data-report-edited-line>{editedLineWords(stored.edited_line)}</p>
        ) : null}
        {inEditor ? (
          // Read again once the composed draft's review moves (koncept 1 approved through the pane).
          <EditorDocBar
            key={`${docId}:${stored.review_state}`} studyId={frame.studyId} runId={run.run_id} shown={inEditor} composedId={stored.report_artifact_id}
            documentName={KIND_NAME[kind]} canApprove={canReview(frame)}
            approveComposed={(held, seen) => askApproval(stored, { held, seen })} onOpenLine={(l) => setLineAsked({ doc: docId, line: l })}
          />
        ) : null}
        {controls.after}
        {missing.length ? (
          <p role="alert" className="mb-2 text-sm text-status-fault">Dokument cituje čísla, která jeho evidence nemá ({missing.join(", ")}); zobrazují se jako „?“.</p>
        ) : null}
        {kind === "client" ? draft : (
          // The draft in the report editor where it is configured (RPT8d), else read here as before.
          <ReportEditor studyId={frame.studyId} runId={run.run_id} variant={kind === "with_review" ? "context" : "internal"} review={review} line={line} onShown={showInEditor}>
            {draft}
          </ReportEditor>
        )}
        <Coverage lines={coverageRecord(run, doc.unread)} />
      </div>
      {/* Beside the document in a wide pane, a column only while a claim is open; in a narrow one, a sheet
          over the page's foot, so the claim opens where it was asked. */}
      <div className={`fixed inset-x-3 bottom-3 z-30 flex max-h-[60vh] flex-col @3xl:sticky @3xl:top-3 @3xl:max-h-none @3xl:shrink-0 ${stack.entries.length ? "@3xl:w-80" : "@3xl:w-0"}`}>
        <ItemInspector stack={stack} onBack={back} onClose={close}>
          {(top) => claim(top.id)}
        </ItemInspector>
      </div>
    </div></div>
  );
}

/** What the draft does not hold and why (RPT4): beside the document, never part of its text. */
function Coverage({ lines }: { lines: CoverageLine[] }) {
  return (
    <section aria-labelledby="report-coverage" data-report-coverage className="mt-3 rounded-card border border-border bg-surface px-4 py-3 text-sm">
      <h2 id="report-coverage" className="font-semibold">Záznam pokrytí <span className="font-normal text-ink-muted">(mimo text zprávy)</span></h2>
      <ul className="mt-1.5 flex flex-col gap-1">
        {lines.map((line, i) => (
          <li key={i} data-coverage={line.kind} className="min-w-0 break-words">
            <span className="font-medium">{line.label}</span>: {line.state}
            {line.why ? <span className="text-ink-muted"> — {line.why}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** What the pane says instead of a document: undefined, nothing at all; null, the document. */
function noticeOf(loaded: Loaded, kind: Kind, prepare: () => void, mayPrepare: boolean): ReactNode | undefined {
  const again = kind === "internal" || !(loaded.state === "not_stored" || loaded.state === "refused") ? null
    : loaded.prepared ? <span>K této verzi AIA dokument nesloží; lze ji jen stáhnout.</span>
      : mayPrepare ? <Button className="!min-h-11" onClick={prepare}>{kind === "client" ? "Připravit klientskou zprávu znovu" : "Připravit zprávu s rešerší znovu"}</Button> : null;
  switch (loaded.state) {
    case "none": return undefined;
    case "ready": return null;
    case "loading": return <p className="text-sm text-ink-muted" data-report-document="loading">Načítám koncept zprávy…</p>;
    case "failed": return <p role="alert" className="text-sm text-status-fault" data-report-document="failed">{loaded.message}</p>;
    case "unprepared": return (
      <div role="note" className="flex flex-wrap items-center gap-3 text-sm text-ink-muted" data-report-document="unprepared">
        <span>{KIND_NAME[kind]} k tomuto běhu ještě není připravená. Připravíte ji ke čtení zde; žádný soubor přitom neodchází.</span>
        {mayPrepare ? <Button className="!min-h-11" onClick={prepare}>{kind === "client" ? "Připravit klientskou zprávu" : "Připravit zprávu s rešerší"}</Button> : null}
      </div>
    );
    // A client report stored without its document, or with one of an older contract, is prepared
    // again: that stores its document, the only one it can be approved on (RD0, RPT3a).
    case "not_stored": return (
      <div role="note" className="flex flex-wrap items-center gap-3 text-sm text-ink-muted" data-report-document="not_stored">
        <span>Tuto zprávu AIA složila dřív, než začala ukládat její dokument; v panelu ji proto zobrazit nelze.{kind !== "client" ? " Koncept DOCX stáhnete zde." : ""}</span>
        {again}
      </div>
    );
    case "refused": return (
      <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-status-fault" data-report-document="refused">
        <span>Uložený dokument zprávy neodpovídá jejímu souboru DOCX nebo je v jiném formátu; AIA ho nezobrazí.{kind !== "client" ? " Koncept DOCX stáhnete zde." : ""}</span>
        {again}
      </div>
    );
  }
}

type Read = {
  entry: (ref: string) => LedgerEntry | undefined;
  onClaim: (ref: string) => void;
  /** Every ref the ledger holds, in its order: what the evidence appendix lists. */
  refs: string[];
};

/** The words a marked sentence says beside it (RD7). */
const MARK_WORDS = "srovnání bez doloženého čísla";

function DocSection({ section, marks, ...read }: { section: Section; marks: Map<string, string[]> } & Read) {
  return (
    <section data-aia={sectionTarget(section)} className="mb-2">
      <h2 className="mb-1.5 mt-5 font-sans text-base font-semibold">{section.appendix ? `Příloha · ${section.title}` : section.title}</h2>
      {section.blocks.map((block) => {
        const marked = marks.get(block.id) ?? [];
        // A sentence no single inline holds whole is named under its block, never dropped.
        const texts = blockTexts(block);
        const unplaced = marked.filter((sentence) => !texts.some((t) => t.includes(sentence)));
        return (
          <div key={block.id} data-aia={blockTarget(block)} className="mb-2.5">
            <DocBlock block={block} {...read} point={pointer(block)} marked={marked} />
            {unplaced.map((sentence) => (
              <p key={sentence} className="mt-1 font-sans text-xs text-status-you-ink" data-sentence-mark>Upozornění: {MARK_WORDS}: „{sentence}“</p>
            ))}
          </div>
        );
      })}
    </section>
  );
}

/** A block's text inlines, as Inlines renders them: where a marked sentence can be marked. */
function blockTexts(block: Block): string[] {
  const of = (content: Inline[]) => content.flatMap((i) => (i.type === "text" ? [i.text] : []));
  const items = (list: ListItem[]): string[] => list.flatMap((item) => [...of(item.content), ...items(item.children)]);
  if (block.type === "paragraph" || block.type === "callout") return of(block.content);
  if (block.type === "list") return items(block.items);
  return [];
}

/** A number as a chip: the DOCX's text for it; a click opens its claim. Suppressed: never a number. */
type Chip = Pick<Read, "entry" | "onClaim"> & {
  /** The chip's `data-aia` in its block: the first chip of a ref only, so no two elements share an id. */
  point: (ref: string) => string | undefined;
  /** The block's sentences the check marks (RD7). */
  marked?: readonly string[];
};

/** A text inline's words, a sentence the check marks in a `mark` that says why (RD7). */
function Marked({ text, marked }: { text: string; marked?: readonly string[] }): ReactNode {
  if (!marked?.length) return text;
  return markSpans(text, marked).map((span, i) => span.marked ? (
    <mark key={i} data-sentence-mark title={MARK_WORDS} className="rounded-sm bg-status-you-wash text-ink underline decoration-status-you-ink decoration-dotted underline-offset-2">
      {span.text}<span className="sr-only"> ({MARK_WORDS})</span>
    </mark>
  ) : <span key={i}>{span.text}</span>);
}

/** A block's pointer: `report:<block id>:<ref>` for a ref's first chip in the block, none after. */
function pointer(block: Block): (ref: string) => string | undefined {
  const seen = new Set<string>();
  return (ref) => {
    if (seen.has(ref)) return undefined;
    seen.add(ref);
    return claimTarget(block, ref) ?? undefined;
  };
}

function Claim({ ref_, withInterval, entry, onClaim, point }: { ref_: string; withInterval: boolean } & Chip) {
  const target = point(ref_);
  return (
    <button type="button" onClick={() => onClaim(ref_)} data-aia={target} data-claim={ref_}
      className="mx-px inline rounded-sm bg-surface-sunken px-1 font-mono text-[0.92em] text-ink hover:bg-signal-wash focus-visible:outline-2 focus-visible:outline-focus-ring">
      {valueWords(entry(ref_), withInterval)}
    </button>
  );
}

/** A block's own refs (a callout's or a finding's marks) as chips after its text. */
function Marks({ refs, ...chip }: { refs: string[] } & Chip) {
  if (!refs.length) return null;
  return <span className="ml-1 font-sans">{refs.map((ref) => <Claim key={ref} ref_={ref} withInterval={false} {...chip} />)}</span>;
}

function Inlines({ content, ...chip }: { content: Inline[] } & Chip): ReactNode {
  return content.map((inline, i) => {
    switch (inline.type) {
      case "text": {
        const words = <Marked text={inline.text} marked={chip.marked} />;
        return inline.emphasis === "strong" ? <strong key={i}>{words}</strong> : inline.emphasis === "em" ? <em key={i}>{words}</em> : <span key={i}>{words}</span>;
      }
      case "value":
        return <Claim key={i} ref_={inline.ref} withInterval={inline.with_interval} {...chip} />;
      case "footnote":
        return <sup key={i} title={inline.text} className="font-sans text-ink-muted">*</sup>;
      case "cross_ref":
        return <span key={i} className="font-sans text-ink-muted">(viz {inline.target})</span>;
      case "link":
        return <span key={i}>{inline.text} <span className="font-sans text-xs text-ink-muted">({inline.url})</span></span>;
      default:
        return null;
    }
  });
}

function Items({ items, ordered, ...chip }: { items: ListItem[]; ordered: boolean } & Chip) {
  const List = ordered ? "ol" : "ul";
  return <List className={`${ordered ? "list-decimal" : "list-disc"} ml-6 text-[15px] leading-6`}>
    {items.map((item, i) => <li key={i}><Inlines content={item.content} {...chip} />
      {item.children.length ? <Items items={item.children} ordered={ordered} {...chip} /> : null}</li>)}
  </List>;
}

function TableCell({ cell, ...chip }: { cell: Cell } & Chip) {
  if (cell.type === "text") return <>{cell.text}</>;
  if (cell.type === "empty") return <span className="text-ink-muted">{cell.reason}</span>;
  return <Claim ref_={cell.ref} withInterval={cell.with_interval} {...chip} />;
}

function DocBlock({ block, entry, onClaim, refs, point, marked }: { block: Block; point: Chip["point"]; marked: readonly string[] } & Read) {
  const read = { entry, onClaim, point };
  const prose = { ...read, marked };
  switch (block.type) {
    case "heading":
      return block.level === 2 ? <h3 className="mt-3 font-sans text-[15px] font-semibold">{block.text}</h3> : <h4 className="mt-2 font-sans text-sm font-semibold">{block.text}</h4>;
    case "paragraph":
      return <p className={block.role === "lede" ? "text-[17px] leading-7" : block.role === "lead_in" ? "font-sans text-sm font-semibold" : "text-[15px] leading-6"}>
        <Inlines content={block.content} {...prose} /><Marks refs={block.marks} {...read} />
      </p>;
    case "list":
      return <Items items={block.items} ordered={block.ordered} {...prose} />;
    case "quote":
      return <blockquote className="border-l-2 border-border pl-3 text-[15px] italic leading-6">„{block.text}“ <span className="font-sans text-xs not-italic text-ink-muted">— {block.attribution}{block.synthetic ? " (smyšlený respondent)" : ""}</span></blockquote>;
    case "callout":
      return <div className="rounded-control border border-border bg-surface-sunken px-3 py-2 font-sans text-sm leading-6" data-callout={block.kind}>
        {block.title ? <p className="font-semibold">{block.title}<Marks refs={block.marks} {...read} /></p> : null}
        <p><Inlines content={block.content} {...prose} />{block.title ? null : <Marks refs={block.marks} {...read} />}</p>
      </div>;
    case "key_finding":
      return <div className="border-l-2 border-signal pl-3 text-[15px] leading-6">
        <p className="font-sans font-semibold">{block.headline}<Marks refs={block.marks} {...read} /></p>
        <p>{block.finding}</p>
        <p className="font-sans text-sm text-ink-muted">Evidence: {block.evidence} · Význam: {block.meaning} · Jistota: {block.confidence}</p>
      </div>;
    case "recommendation":
      return <div className="text-[15px] leading-6"><p className="font-sans font-semibold">{block.action}<Marks refs={block.marks} {...read} /></p><p>{block.why}</p><p className="font-sans text-xs text-ink-muted">Priorita: {block.priority}</p></div>;
    case "kpi_row":
      return <div className="flex flex-wrap gap-3 font-sans">{block.items.map((kpi) => (
        <div key={kpi.ref} className="min-w-32 rounded-control border border-border px-3 py-2">
          <Claim ref_={kpi.ref} withInterval {...read} />
          <p className="text-xs text-ink-muted">{kpi.label}</p>
        </div>))}</div>;
    case "table":
      return <figure className="font-sans">
        <figcaption className="mb-1 text-xs text-ink-muted">Tabulka · {block.title}</figcaption>
        <div className="overflow-x-auto"><table className="w-full border-collapse text-sm">
          <thead><tr>{block.columns.map((c, i) => <th key={i} scope="col" className={`border-b border-border px-2 py-1 font-semibold ${c.align === "right" ? "text-right" : "text-left"}`}>{c.label}{c.unit ? ` (${c.unit})` : ""}</th>)}</tr></thead>
          <tbody>{block.rows.map((row, r) => <tr key={r} className={row.emphasis ? "font-semibold" : undefined}>
            {row.cells.map((cell, i) => <td key={i} className={`border-b border-border px-2 py-1 ${block.columns[i]?.align === "right" ? "text-right" : ""}`}><TableCell cell={cell} {...read} /></td>)}
          </tr>)}</tbody>
        </table></div>
        <p className={`mt-1 text-xs text-ink-muted ${WRAPS}`}>Zdroj: {block.source}{block.suppressed_rows ? ` · odstraněno řádků pro nedostatečnou podporu: ${block.suppressed_rows}` : ""}</p>
        {block.notes.map((note) => <p key={note} className="text-xs text-ink-muted">{note}</p>)}
      </figure>;
    case "figure":
      // The chart's numbers as a table: the DOCX draws the chart, the pane lists what it plots.
      return <figure className="rounded-control border border-border px-3 py-2 font-sans">
        <figcaption className="mb-1 text-xs text-ink-muted">Graf · {block.title} <span className="sr-only">({block.alt})</span></figcaption>
        <div className="overflow-x-auto"><table className="w-full text-sm">
          <thead><tr><th scope="col" className="text-left font-semibold">{block.chart.value_label}</th>{block.chart.series.map((s) => <th key={s.name} scope="col" className="text-right font-semibold">{s.name}{s.modelled ? " (modelováno)" : ""}</th>)}</tr></thead>
          <tbody>{block.chart.categories.map((category, c) => <tr key={category}><th scope="row" className="text-left font-normal">{category}</th>
            {block.chart.series.map((s) => { const ref = s.refs[c]; return <td key={s.name} className="text-right">{ref ? <Claim ref_={ref} withInterval={false} {...read} /> : <span className="text-ink-muted">—</span>}</td>; })}
          </tr>)}</tbody>
        </table></div>
        <p className={`mt-1 text-xs text-ink-muted ${WRAPS}`}>Zdroj: {block.source}</p>
      </figure>;
    case "sociomap_figure":
      return <figure className="rounded-control border border-border px-3 py-2 font-sans text-sm" data-map-figure={block.anchor}>
        <figcaption className="text-xs text-ink-muted">Mapa · {block.title} · {block.methodology_status}{block.fit_caption ? ` · ${block.fit_caption}` : block.stress_1 != null ? ` · Stress-1 ${block.stress_1}` : ""}</figcaption>
        <p className="mt-1">Obrázek mapy je v souboru DOCX; v AIA ji otevřete na stupni Sociomapa.</p>
      </figure>;
    case "evidence_key":
      return <p className="font-sans text-xs text-ink-muted">U každého čísla je uveden stupeň jeho evidence; otevřete číslo pro podrobnosti.</p>;
    case "evidence_appendix":
      return <EvidenceAppendix {...read} refs={refs} />;
    case "audit":
      return <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 font-sans text-xs">{block.entries.map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-muted">{k}</dt><dd className="break-all font-mono">{v}</dd></div>)}</dl>;
    case "page_break":
      return null;
    default:
      return <p className="font-sans text-xs text-ink-muted" data-unrendered>Tento blok zprávy AIA v panelu zatím nezobrazuje; je v souboru DOCX.</p>;
  }
}

/** One row per ref the document cites, admitted or suppressed, as the DOCX's evidence appendix. */
function EvidenceAppendix({ refs, ...chip }: Pick<Read, "refs"> & Chip) {
  const { entry } = chip;
  return <div className="overflow-x-auto font-sans"><table className="w-full text-sm" data-evidence-appendix>
    <thead><tr>{["Tvrzení", "Hodnota", "Základ", "Stupeň"].map((h) => <th key={h} scope="col" className="border-b border-border px-2 py-1 text-left font-semibold">{h}</th>)}</tr></thead>
    <tbody>{refs.map((ref) => { const e = entry(ref); return <tr key={ref}>
      <td className="border-b border-border px-2 py-1 font-mono text-xs">{ref}</td>
      <td className="border-b border-border px-2 py-1"><Claim ref_={ref} withInterval {...chip} /></td>
      <td className="border-b border-border px-2 py-1">{e && !e.suppressed ? e.base_text ?? "n = ?" : "—"}</td>
      <td className="border-b border-border px-2 py-1">{e && !e.suppressed ? gradeWords(e.grade) : e ? "potlačeno" : "?"}</td>
    </tr>; })}</tbody>
  </table></div>;
}
