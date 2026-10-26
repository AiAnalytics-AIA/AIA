"use client";

// The Research Lead's conversation (ADR 0026; plan research-lead-workbench chunk 6), after the
// prototype's Conversation and Composer (prototypes/research-lead-v2 @ 9b50963f) and wired to AIA:
// the researcher's own session on this study, read from GET /lead and written by POST /lead/turns.
// Each Lead turn is a worker step; while one runs the pane reads the session again every 1.5 s.
// The Lead's view tools are applied when its turn arrives; its edits are change blocks in the
// artifact pane; its request is a decision card that starts nothing until the person approves.

import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState } from "react";

import { lead as leadApi, researcherLead, ApiError, type Readiness, type ResearchAgentJob, type ResearchRun } from "@/lib/api";
import { ACTION_LABELS } from "@/lib/research-agent-jobs";
import { appRoutes } from "@/lib/app-routes";
import type { LeadOutput, LeadRequest, LeadState, LeadTurn, LeadView, ResearcherLead, RetryRun, SelfUpdateDecision } from "@/lib/lead";
import { commandRequest, composerHint, droppedLines, leadReasonWords as reasonWords, mapViewWords, pendingSelfUpdate, targetLabel, type TargetWords, TYPED_UNDECIDED_WHY } from "@/lib/lead";
import { conversationTimeline } from "@/lib/lead-cards";
import { isDayBreak, withDayBreaks } from "@/lib/day-label";
import { STAGES, isWorkbenchStage, type WorkbenchStage } from "@/lib/workbench-stages";
import type { StepKey } from "@/research/steps";
import { Glyph } from "./Glyph";
import { Icon, Mark } from "./Icons";
import { Facts, Pill, RunCardView, RunRequestCard, WorkerCardView } from "./LeadCards";
import { LeadSees } from "./LeadSees";

const POLL_MS = 1500;

/**
 * What the conversation's cards need beside the turns (chunk 23): the study's research runs, where
 * Průběh and Výsledky are, and the prepared run's start through Spuštění's route. Without it the
 * pane shows the design jobs alone.
 */
export type LeadCardsContext = {
  runs: ResearchRun[];
  stepHref: (step: StepKey) => string;
  onStage: (stage: WorkbenchStage) => void;
  prepareRun: () => Promise<{ readiness: Readiness; runs: ResearchRun[] }>;
  startRun: (readiness: Readiness, confirm: { ceiling: number; limit: number } | null) => Promise<ResearchRun | null>;
  /** The run each turn's card started, in this page's memory. */
  runOfTurn: ReadonlyMap<string, string>;
  onRunStarted: (turnId: string, run: ResearchRun) => void;
  /** Read the jobs again after a card acted on one (a resume): a waiting job is not polled. */
  onJobsChanged?: () => void;
};

/**
 * What the person is writing and what is not yet stored on the server (a post in flight, or one
 * the server did not take), per study, for as long as the page lives:
 * the pane is unmounted when the window narrows to the classic layout, and comes back empty
 * otherwise.
 */
type Queued = { text: string; stage: WorkbenchStage; focus: { id: string; label: string } | null };
const kept = new Map<string, { draft: string; queued: Queued[] }>();

/** An accepted self-update left a file another turn changed since; its notes did apply. The 200
 * names it, and the turn's decision keeps it after a reload. */
const STALE_SELF_UPDATE = "Soubor se mezitím změnil, požádejte Vedoucího znovu.";

const time = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
};

/** The newest Lead turn that finished: the one whose view tools have been applied. */
const newestCompleted = (turns: LeadTurn[]) => [...turns].reverse().find((t) => t.actor === "lead" && t.status === "COMPLETED") ?? null;

export function LeadPane({ studyId, stage, canEdit, focus, picking, onPick, onClearFocus, onView, onRequest, onTurns, onFocusMode, onClose, onSession, mode, epoch, jobs = [], onOpenJob, onLead, beforeMessage, cards, registerSend, design }: {
  studyId: string;
  stage: WorkbenchStage;
  canEdit: boolean;
  /** What the person has pointed at in the artifact, sent with the next message. */
  focus: { id: string; label: string } | null;
  /** Pointing at the artifact is armed: the next click there is the focus. */
  picking: boolean;
  onPick: () => void;
  onClearFocus: () => void;
  onView: (ops: LeadView[]) => void;
  onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>;
  /** Changes when something outside the pane decided on a turn: read the session again. */
  epoch: number;
  /** The study's design jobs, shown in the conversation as activity: the Lead's and the buttons'. */
  jobs?: ResearchAgentJob[];
  /** Open a finished job's proposal (or advice) for review. */
  onOpenJob?: (job: ResearchAgentJob) => void;
  /** Every read of the session, so the artifact pane can show the newest edits. */
  onTurns: (turns: LeadTurn[]) => void;
  /** The researcher's own Lead once read: its preferences decide what is accepted without a click. */
  onLead?: (me: ResearcherLead) => void;
  /** Before a message goes: the working copy's waiting change saved, so the Lead reads it and its
   * turn is frozen at the revision the person sees (an automatic accept needs the two equal). */
  beforeMessage?: () => Promise<void>;
  onFocusMode: () => void;
  /** In the drawer or the sheet (research-lead-workbench 26c): Zavřít, in place of the focus toggle. */
  onClose?: () => void;
  /** Every read of GET /lead, null and failed when it was refused: the launcher's availability (27a). */
  onSession?: (state: LeadState | null, failed: boolean) => void;
  mode: "split" | "conversation" | "artifact";
  /** The worker and run cards' context (chunk 23). */
  cards?: LeadCardsContext;
  /** Receives the way a stage sends the Lead a message, as the person would type it. */
  registerSend?: (send: (text: string) => void) => void;
  /** The working copy a view chip's research question or hypothesis is named from (F18). */
  design?: TargetWords | null;
}) {
  const [me, setMe] = useState<ResearcherLead | null>(null);
  const [session, setSession] = useState<LeadState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [seesOpen, setSeesOpen] = useState(false);
  const [draft, setDraft] = useState(() => kept.get(studyId)?.draft ?? "");
  // A message not yet stored keeps the stage and the element it was written about; once stored
  // it waits on the server, in every tab (ADR 0041 decision 7).
  const [queued, setQueued] = useState<Queued[]>(() => kept.get(studyId)?.queued ?? []);
  useEffect(() => {
    kept.set(studyId, { draft, queued });
  }, [studyId, draft, queued]);
  const [sending, setSending] = useState(false);
  // A message the server did not take goes back to the front of the queue, held until the person
  // says to try again: never lost, never resent in a loop.
  const [held, setHeld] = useState(false);
  // Every read, successful or not, moves this on, so a busy session is read again after a failed read.
  const [reads, setReads] = useState(0);
  const applied = useRef<string | null>(null);
  const greeted = useRef(false);

  const read = useCallback(async () => {
    try {
      const s = await leadApi.state(studyId);
      setSession(s);
      onTurns(s.turns);
      onSession?.(s, false);
      setError(null);
      return s;
    } catch (e) {
      onSession?.(null, true);
      setError(e instanceof ApiError && e.status === 404 ? "Vedoucí výzkumu v této verzi AIA zatím není." : e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setReads((n) => n + 1);
    }
  }, [studyId, onTurns, onSession]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reads the Lead's state from the API; its setters run when it answers
    if (epoch) void read();
  }, [epoch, read]);
  useEffect(() => {
    researcherLead.get().then(setMe, (e: unknown) => setError(e instanceof ApiError && e.status === 404 ? "Vedoucí výzkumu v této verzi AIA zatím není." : String(e)));
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reads the Lead's state from the API; its setters run when it answers
    void read();
  }, [read]);
  useEffect(() => {
    if (me) onLead?.(me);
  }, [me, onLead]);

  // While a turn runs, read again; when it finishes, apply the newest turn's view tools once.
  useEffect(() => {
    if (!session?.busy) return;
    const t = setTimeout(() => void read(), POLL_MS);
    return () => clearTimeout(t);
  }, [session, reads, read]);
  useEffect(() => {
    const last = session ? newestCompleted(session.turns) : null;
    if (!last || applied.current === last.turn_id) return;
    const first = applied.current === null;
    applied.current = last.turn_id;
    // On opening a study the old answer's navigation is not replayed.
    if (!first && last.output?.view?.length) onView(last.output.view);
  }, [session, onView]);

  const post = useCallback(async (body: Parameters<typeof leadApi.post>[1]): Promise<boolean> => {
    setSending(true);
    try {
      await leadApi.post(studyId, body);
    } catch (e) {
      setError(e instanceof ApiError ? reasonWords(e.code) : String(e));
      setSending(false);
      return false;
    }
    try {
      await read();
    } finally {
      setSending(false);
    }
    return true;
  }, [studyId, read]);

  const message = useCallback(async (m: Queued) => {
    // A save that fails does not hold the message: the Lead then reads the last stored revision.
    await beforeMessage?.().catch(() => {});
    if (await post({ kind: "message", text: m.text, stage: m.stage, focus: m.focus })) return;
    setQueued((q) => [m, ...q]);
    setHeld(true);
  }, [post, beforeMessage]);

  // The Lead greets a study it has not spoken in for eight hours (the server keeps the rule).
  useEffect(() => {
    if (greeted.current || !me?.hatched || !session?.available || !canEdit) return;
    greeted.current = true;
    void post({ kind: "greeting", stage });
  }, [me, session, canEdit, stage, post]);

  // Messages go one after another, in the order written; the server queues them while the Lead works.
  useEffect(() => {
    if (sending || held || !queued.length) return;
    const [next, ...rest] = queued;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the queue drains one message each time the Lead is free
    setQueued(rest);
    if (next) void message(next);
  }, [session, sending, held, queued, message]);

  const send = (text: string) => {
    const t = text.trim();
    if (!t) return;
    if (sending || held) setQueued((q) => [...q, { text: t, stage, focus }]);
    else void message({ text: t, stage, focus });
    setDraft("");
    onClearFocus();
  };
  // A stage's message (Návrh's "Požádat Vedoucího"): sent or queued as typed, the draft left alone.
  const fromStage = (text: string) => {
    const t = text.trim();
    if (!t) return;
    if (sending || held) setQueued((q) => [...q, { text: t, stage, focus: null }]);
    else void message({ text: t, stage, focus: null });
  };
  useEffect(() => {
    registerSend?.(fromStage);
  });

  // What waits for the Lead on the server, in queue order; any tab starts its turn once the Lead is
  // free (the server starts one, however many tabs ask).
  const waiting = (session?.turns ?? []).filter((t) => t.actor === "person" && t.queued);
  const asked = useRef<string | null>(null);
  // An ask that failed is said, with its reason and a retry: nothing else would ask again, and the
  // queue would read as answered soon while no turn is coming.
  const [drainFailed, setDrainFailed] = useState<string | null>(null);
  useEffect(() => {
    if (!session?.available || session.busy || sending || !waiting.length) return;
    // Asked again whenever the newest Lead turn moves on (a budget wait lifted and the turn
    // answered): a key of the waiting set alone would leave them waiting until a reload. Never
    // per read, which would ask again after every answer of its own.
    const newest = [...(session.turns ?? [])].reverse().find((t) => t.actor === "lead");
    const key = `${waiting.map((t) => t.turn_id).join(",")}|${newest?.turn_id ?? ""}:${newest?.status ?? ""}`;
    if (asked.current === key) return;
    asked.current = key;
    leadApi.answerQueued(studyId).then(
      (started) => {
        setDrainFailed(null);
        // A turn started is a busy Lead even if the read below fails: the poll keeps reading.
        if (started.turns.length) setSession((s) => (s ? { ...s, busy: true } : s));
        return read();
      },
      (e: unknown) => setDrainFailed(e instanceof ApiError ? reasonWords(e.code) : String(e)),
    );
  }, [session, sending, waiting, studyId, read]);
  const unqueue = async (key: string) => {
    if (key.startsWith("local:")) {
      const i = Number(key.slice(6));
      setQueued((q) => q.filter((_, j) => j !== i));
      return;
    }
    try {
      await leadApi.withdraw(studyId, key);
    } catch (e) {
      setError(e instanceof ApiError ? reasonWords(e.code) : String(e));
    }
    await read();
  };

  const hatch = async () => {
    try {
      setMe(await researcherLead.hatch());
      // The session read before hatching said the Lead was not hatched: read it again.
      await read();
    } catch (e) {
      setError(e instanceof ApiError ? reasonWords(e.code) : String(e));
    }
  };

  const decideSelfUpdate = useCallback(async (t: LeadTurn, decision: "accept" | "dismiss") => {
    let decided: SelfUpdateDecision | null = null;
    try {
      decided = await leadApi.decideSelfUpdate(studyId, t.turn_id, decision);
    } catch (e) {
      setError(e instanceof ApiError ? reasonWords(e.code) : String(e));
    }
    await read();
    return decided;
  }, [studyId, read]);

  const name = me?.lead?.name || "Vedoucí výzkumu";
  // The Vidí chip opens what the newest Lead turn could see (LC2): only a turn that froze one.
  const seenTurn = [...(session?.turns ?? [])].reverse().find((t) => t.actor === "lead" && t.run_id);
  return (
    <div className="conv">
      <div className="conv__head">
        <div className="conv__avatar"><Mark size={18} onDark /></div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="conv__who">{name}</div>
          {seenTurn ? (
            <button type="button" className="conv__sees conv__sees--chip" aria-expanded={seesOpen} aria-controls="lead-sees" title="Co Vedoucí viděl v poslední odpovědi" onClick={() => setSeesOpen((o) => !o)} data-lead-sees-chip>
              Vidí: {STAGES[stage].label} · pracovní kopie studie{focus ? ` · ${focus.label}` : ""}
            </button>
          ) : (
            <div className="conv__sees">Vidí: {STAGES[stage].label} · pracovní kopie studie{focus ? ` · ${focus.label}` : ""}</div>
          )}
        </div>
        <Link className="iconbtn" href={appRoutes.lead()} title="Můj Vedoucí: jeho soubory a paměť" aria-label="Můj Vedoucí"><Icon name="user" size={16} /></Link>
        {onClose ? (
          <button type="button" className="iconbtn" aria-label="Zavřít konverzaci" title="Zavřít (Esc)" onClick={onClose} data-lead-close>
            <Icon name="close" size={16} />
          </button>
        ) : (
          <button type="button" className={`iconbtn${mode === "conversation" ? " is-on" : ""}`} aria-pressed={mode === "conversation"} title={mode === "conversation" ? "Zpět na 40 / 60" : "Soustředit se na konverzaci"} aria-label={mode === "conversation" ? "Zpět na 40 / 60" : "Soustředit se na konverzaci"} onClick={onFocusMode}>
            <Icon name={mode === "conversation" ? "normal" : "focusChat"} size={16} />
          </button>
        )}
      </div>
      {seenTurn && seesOpen ? <LeadSees key={seenTurn.turn_id} studyId={studyId} turnId={seenTurn.turn_id} id="lead-sees" /> : null}
      <TypedCardFacts.Provider value={{ walletOn: session?.wallet_enabled === true, retryRun: session?.analysis_retry_run ?? null }}>
      <ViewWords.Provider value={design ?? null}>
      <Conversation turns={(session?.turns ?? []).filter((t) => !t.queued && !t.withdrawn)} jobs={jobs} cards={cards} studyId={studyId} onOpenJob={onOpenJob} busy={!!session?.busy || sending} name={name} onFollow={send} onView={onView} onRequest={onRequest} onSelfUpdate={decideSelfUpdate} canEdit={canEdit}>
        {error ? <div className="msg"><div className="notice"><Glyph tone="fault" size={11} />{error}</div></div> : null}
        {held ? (
          <div className="msg"><div className="notice"><Glyph tone="fault" size={11} />Zprávu se nepodařilo odeslat. Čeká ve frontě.
            <button type="button" className="chip" onClick={() => { setError(null); setHeld(false); }}>Zkusit znovu</button></div></div>
        ) : null}
        {drainFailed ? (
          <div className="msg"><div className="notice"><Glyph tone="fault" size={11} />Vedoucí zatím neodpovídá na zprávy ve frontě: {drainFailed}
            <button type="button" className="chip" onClick={() => { asked.current = null; setDrainFailed(null); void read(); }}>Zkusit znovu</button></div></div>
        ) : null}
        {me && !me.hatched ? <HatchCard onHatch={hatch} /> : null}
        {session && !session.available ? <div className="msg"><div className="notice"><Glyph tone="inert" size={11} />{reasonWords(session.unavailable_reason ?? "research_lead_unavailable")}</div></div> : null}
      </Conversation>
      </ViewWords.Provider>
      </TypedCardFacts.Provider>
      <Composer draft={draft} setDraft={setDraft} onSend={send} busy={!!session?.busy || sending} queued={[...waiting.map((t) => ({ key: t.turn_id, text: t.text ?? "" })), ...queued.map((q, i) => ({ key: `local:${i}`, text: q.text }))]} onUnqueue={(key) => void unqueue(key)}
        disabled={!canEdit || !me?.hatched || !session?.available} hint={composerHint({ canEdit, hatched: me?.hatched, available: session?.available, failed: error !== null })} focus={focus} picking={picking} onPick={onPick} onClearFocus={onClearFocus} />
    </div>
  );
}

function HatchCard({ onHatch }: { onHatch: () => void }) {
  return (
    <div className="msg">
      <div className="dec">
        <div className="dec__head"><Glyph tone="you" size={11} />Váš vlastní Vedoucí výzkumu</div>
        <div className="dec__body">
          <p className="dec__title">Vylíhněte si Vedoucího, který se učí s vámi.</p>
          <p className="dec__reason">Každý výzkumník má svého Vedoucího. Prací s ním ho tvarujete: zapamatuje si, jak pracujete, a přenese to do všech vašich studií. Jeho soubory si můžete kdykoli přečíst; měníte je jen rozhovorem s ním. Poznámky o klientovi zůstávají u toho klienta.</p>
          <div className="dec__foot"><span className="grow" /><button type="button" className="btn btn--primary btn--sm" onClick={onHatch}>Vylíhnout mého Vedoucího</button></div>
        </div>
      </div>
    </div>
  );
}

function Conversation({ turns, jobs, cards, studyId, onOpenJob, busy, name, onFollow, onView, onRequest, onSelfUpdate, canEdit, children }: {
  turns: LeadTurn[]; jobs: ResearchAgentJob[]; cards?: LeadCardsContext; studyId: string; onOpenJob?: (job: ResearchAgentJob) => void; busy: boolean; name: string; canEdit: boolean;
  onFollow: (t: string) => void; onView: (ops: LeadView[]) => void; onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>;
  onSelfUpdate: (turn: LeadTurn, decision: "accept" | "dismiss") => Promise<SelfUpdateDecision | null>;
  children: React.ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const [away, setAway] = useState(false);
  const runs = cards?.runs ?? [];
  const sig = `${turns.length}:${turns.at(-1)?.status ?? ""}:${busy}:${jobs.map((j) => j.status).join(",")}:${runs.map((r) => r.phase).join(",")}`;
  useLayoutEffect(() => {
    const el = box.current;
    if (el && atBottom.current) el.scrollTop = el.scrollHeight;
  }, [sig]);
  // "Na nejnovější" never leaves under the keyboard: the previous Tab's scroll can reach the bottom
  // and be committed just after the next Tab focused the button, so it stays while it has the focus
  // (F-BRF-2, lead_journey.mjs "Tab stays inside the open conversation"). A focus it lost without a
  // blur (the pane hidden) is let go at the next scroll.
  const latest = useRef<HTMLButtonElement>(null);
  const [onLatest, setOnLatest] = useState(false);
  const onScroll = () => {
    const el = box.current!;
    const b = el.scrollHeight - el.scrollTop - el.clientHeight <= 24;
    atBottom.current = b;
    setAway(!b);
    if (document.activeElement !== latest.current) setOnLatest(false);
  };
  const lastLead = [...turns].reverse().find((t) => t.actor === "lead");
  return (
    <>
      <div className="conv__scroll" ref={box} onScroll={onScroll} tabIndex={0} role="log" aria-label={`Konverzace: ${name}`} aria-live="polite" aria-relevant="additions">
        <div>
          {children}
          {withDayBreaks(conversationTimeline(turns, jobs, runs, cards?.runOfTurn), (x) => x.at || null).map((x) => isDayBreak(x)
            ? <h3 key={`day:${x.key}`} className="conv__day">{x.label}</h3>
            : x.kind === "job"
            ? <WorkerCardView key={x.job.run_id} job={x.job} studyId={studyId} onOpen={onOpenJob} onStage={cards?.onStage} onChanged={cards?.onJobsChanged} />
            : x.kind === "run"
              ? (cards ? <RunCardView key={x.run.run_id} run={x.run} studyId={studyId} stepHref={cards.stepHref} /> : null)
              : x.turn.actor === "person"
                ? <PersonTurn key={x.turn.turn_id} t={x.turn} canEdit={canEdit} onRequest={onRequest} studyId={studyId} cards={cards} onOpenJob={onOpenJob}
                    job={jobs.find((j) => j.run_id === x.turn.request_decision?.run_id) ?? null}
                    run={runs.find((r) => r.run_id === x.turn.request_decision?.run_id) ?? null} />
                : <LeadTurnView key={x.turn.turn_id} t={x.turn} name={name} last={x.turn.turn_id === lastLead?.turn_id} busy={busy} onFollow={onFollow} onView={onView} onRequest={onRequest} onSelfUpdate={onSelfUpdate} canEdit={canEdit}
                    job={jobs.find((j) => j.run_id === x.turn.request_decision?.run_id) ?? null} onOpenJob={onOpenJob} studyId={studyId} cards={cards}
                    run={runs.find((r) => r.run_id === cards?.runOfTurn.get(x.turn.turn_id)) ?? null} />)}
          <div style={{ height: 8 }} />
        </div>
      </div>
      {away || onLatest ? (
        <div className="conv__latestwrap">
          {/* Another window taking the focus is not the keyboard leaving: the button is kept for its return. */}
          <button ref={latest} type="button" className="btn btn--sm conv__latest" onFocus={() => setOnLatest(true)} onBlur={() => { if (document.hasFocus()) setOnLatest(false); }}
            onClick={(e) => {
              const el = box.current!;
              el.scrollTop = el.scrollHeight;
              atBottom.current = true;
              // A focus on the button goes to the newest message; where a click does not focus a button
              // (Safari), the focus stays where it was, the composer.
              if (document.activeElement === e.currentTarget) el.focus({ preventScroll: true });
              setAway(false);
            }}><Icon name="down" size={13} />Na nejnovější</button>
        </div>
      ) : null}
    </>
  );
}

/** What a typed start's card says beside the request (GET /lead): whether the wallet is on, and the
 *  run a typed analysis retry would retry (the PM on #744). */
const TypedCardFacts = createContext<{ walletOn: boolean; retryRun: RetryRun | null }>({ walletOn: false, retryRun: null });

const retryRunWords = (run: RetryRun) =>
  run.created_at ? `Běh z ${new Date(run.created_at).toLocaleString("cs-CZ", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" })}` : "Poslední běh s AI analýzou";

/** A person's message; a typed start (LO5) is followed by its card, theirs to approve, and then by
 *  the job or run it started. */
function PersonTurn({ t, canEdit, onRequest, studyId, cards, onOpenJob, job, run }: {
  t: LeadTurn; canEdit: boolean; onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>; studyId: string;
  cards?: LeadCardsContext; onOpenJob?: (job: ResearchAgentJob) => void; job: ResearchAgentJob | null; run: ResearchRun | null;
}) {
  const facts = useContext(TypedCardFacts);
  const command = t.command ? commandRequest(t) : null;
  // A typed analysis retry is approved on the run its card names, never on a newer one unasked.
  const typed = command?.kind === "analysis_retry" ? { ...command, run_id: facts.retryRun?.run_id } : command;
  return (
    <>
      <div className="msg msg--user" data-msg={t.turn_id}>
        {t.focus ? <div className="bubble__ref"><Icon name="at" size={12} />{t.focus.label}</div> : null}
        <div className="bubble">{t.text}</div>
        <div className="msgacts" role="group" aria-label="Akce zprávy"><span className="msgmeta">{time(t.created_at)}</span></div>
      </div>
      {typed ? <RequestCard r={typed} typed approved={t.request_decision ?? null} onApprove={() => onRequest(t, typed)} canEdit={canEdit} /> : null}
      {/* A job found already started is shown where it started, once; this card points to it. */}
      {job && !t.request_decision?.reused ? <WorkerCardView job={job} studyId={studyId} onOpen={onOpenJob} onStage={cards?.onStage} onChanged={cards?.onJobsChanged} /> : null}
      {run && cards && !t.request_decision?.reused ? <RunCardView run={run} studyId={studyId} stepHref={cards.stepHref} /> : null}
    </>
  );
}

function Prose({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  return <>{blocks.map((b, i) => {
    const lines = b.split("\n");
    if (lines.every((l) => /^\s*[-•*]\s+/.test(l))) return <ul key={i}>{lines.map((l, j) => <li key={j}>{l.replace(/^\s*[-•*]\s+/, "")}</li>)}</ul>;
    return <p key={i}>{b}</p>;
  })}</>;
}

/** The working copy a view chip's target is named from (F18). */
const ViewWords = createContext<TargetWords | null>(null);

const stageWords = (stage: string) => (isWorkbenchStage(stage) ? STAGES[stage].label : stage);
const VIEW_LABEL = (v: LeadView, design: TargetWords | null) =>
  v.op === "open_stage" ? `Otevřít ${stageWords(v.stage)}`
  : v.op === "show_diff" ? `Změny: ${stageWords(v.stage)}`
  : v.op === "select" || v.op === "filter" ? mapViewWords(v, design)
  : `${v.op === "inspect" ? "Detail" : "Ukázat"}: ${targetLabel(v.target, design)}`;

function LeadTurnView({ t, name, last, busy, onFollow, onView, onRequest, onSelfUpdate, canEdit, job, onOpenJob, studyId, cards, run }: {
  t: LeadTurn; name: string; last: boolean; busy: boolean; canEdit: boolean; job: ResearchAgentJob | null; onOpenJob?: (job: ResearchAgentJob) => void;
  studyId: string; cards?: LeadCardsContext; run: ResearchRun | null;
  onFollow: (t: string) => void; onView: (ops: LeadView[]) => void; onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>;
  onSelfUpdate: (turn: LeadTurn, decision: "accept" | "dismiss") => Promise<SelfUpdateDecision | null>;
}) {
  const design = useContext(ViewWords);
  if (t.status === "QUEUED" || t.status === "RUNNING") {
    return (
      <div className="msg"><div className="lead"><div className="lead__av"><Mark size={14} onDark /></div>
        <div style={{ minWidth: 0 }}><div className="lead__name"><b>{name}</b><span>{t.kind === "greeting" ? "připravuje přehled studie" : "pracuje"}</span></div>
          <div className="typing" aria-label={`${name} odpovídá`}><i /><i /><i /></div></div></div></div>
    );
  }
  if (t.status !== "COMPLETED" || !t.output) {
    // Parked on the study's budget: coral for whoever can raise it (anyone who can edit the study,
    // ADR 0019), slate for a reader who cannot (the product owner, 2026-10-23, Q85). Any other wait is slate.
    const parkedOnBudget = t.status === "WAITING" && t.reason === "budget_exceeded";
    const tone = parkedOnBudget && canEdit ? "you" : t.status === "WAITING" ? "world" : t.status === "CANCELLED" ? "cancelled" : "fault";
    return <div className="msg"><div className="notice" data-lead-wait={t.reason ?? t.status}><Glyph tone={tone} size={11} />{reasonWords(t.reason ?? t.status)}<span className="msgmeta">· {time(t.created_at)}</span></div></div>;
  }
  const o: LeadOutput = t.output;
  const edits = o.edits ?? [];
  return (
    <div className="msg" data-msg={t.turn_id}>
      <div className="lead">
        <div className="lead__av"><Mark size={14} onDark /></div>
        <div style={{ minWidth: 0 }}>
          <div className="lead__name"><b>{name}</b><span>{time(t.created_at)}</span>{t.workspace_revision !== null ? <span className="histnote">četl revizi {t.workspace_revision}</span> : null}</div>
          <div className="prose"><Prose text={o.reply} /></div>
          {edits.length ? (
            <div className="links"><button type="button" className="linkchip" onClick={() => onView([{ op: "open_stage", stage: t.stage && isWorkbenchStage(t.stage) ? t.stage : "brief" }])}><Icon name="pencil" size={12} />{edits.length === 1 ? "1 návrh změny v artefaktu" : `${edits.length} návrhů změn v artefaktu`}</button></div>
          ) : null}
          {o.view?.length ? <div className="links">{o.view.map((v, i) => <button key={i} type="button" className="linkchip" onClick={() => onView([v])}><Icon name="open" size={12} />{VIEW_LABEL(v, design)}</button>)}</div> : null}
          <SelfUpdate t={t} o={o} canEdit={canEdit} onDecide={(d) => onSelfUpdate(t, d)} />
          {o.dropped?.length ? droppedLines(o.dropped).map((line) => <div key={line} className="cap">{line}</div>) : null}
        </div>
      </div>
      {o.request?.kind === "research_run" && cards
        ? <RunRequestCard studyId={studyId} why={o.request.why} canEdit={canEdit} prepare={cards.prepareRun} start={cards.startRun} stepHref={cards.stepHref} onStarted={(r) => cards.onRunStarted(t.turn_id, r)} />
        : o.request ? <RequestCard r={o.request} approved={t.request_decision ?? null} onApprove={() => onRequest(t, o.request!)} canEdit={canEdit} /> : null}
      {job ? <WorkerCardView job={job} studyId={studyId} onOpen={onOpenJob} onStage={cards?.onStage} onChanged={cards?.onJobsChanged} /> : null}
      {run && cards ? <RunCardView run={run} studyId={studyId} stepHref={cards.stepHref} /> : null}
      {last && !busy && o.follow?.length ? (
        <div className="follow" aria-label="Navázat">{o.follow.map((f) => <button key={f} type="button" className="follow__btn" onClick={() => onFollow(f)}><Icon name="next" size={13} />{f}</button>)}</div>
      ) : null}
    </div>
  );
}

/**
 * The Lead's changes to its own files and memory. What stays inside this study's client (a client
 * note kept or forgotten) was applied with the turn. What would reach all of the researcher's work
 * (a personal note kept or forgotten, SOUL, USER, the name) waits for the researcher's yes.
 */
const FILE_WORDS: Record<"name" | "soul" | "user", string> = { name: "Jméno", soul: "SOUL", user: "USER" };

function SelfUpdate({ t, o, canEdit, onDecide }: { t: LeadTurn; o: LeadOutput; canEdit: boolean; onDecide: (d: "accept" | "dismiss") => Promise<SelfUpdateDecision | null> }) {
  const [busy, setBusy] = useState(false);
  const [answered, setAnswered] = useState<SelfUpdateDecision["stale"]>([]);
  const u = o.self_update;
  if (!u) return null;
  const clientNotes = (u.remember ?? []).filter((m) => m.scope === "client").map((m) => m.text);
  const forgotten = t.changes?.forgotten?.length ?? 0;
  const applied = [
    clientNotes.length ? `zapamatováno u klienta: ${clientNotes.join("; ")}` : null,
    forgotten ? `zapomenuto u klienta ${forgotten}×` : null,
  ].filter(Boolean);
  const waiting = pendingSelfUpdate(t.self_update_waiting);
  const hasWaiting = waiting.notes.length > 0 || waiting.forget.length > 0 || waiting.files.length > 0;
  const decided = t.self_update_decision?.status ?? null;
  const decide = (d: "accept" | "dismiss") => {
    setBusy(true);
    void onDecide(d).then((r) => setAnswered(r?.stale ?? [])).finally(() => setBusy(false));
  };
  const stale = t.self_update_decision?.stale?.length ? t.self_update_decision.stale : answered;
  return (
    <>
      {applied.length ? <div className="notice" style={{ marginTop: 6 }}><Icon name="memory" size={12} />Upraveno: {applied.join(" · ")} · <Link href={appRoutes.lead()} className="linkbtn">Můj Vedoucí</Link></div> : null}
      {hasWaiting ? (
        <div className={`dec${decided ? " is-decided" : ""}`} data-aia="lead.self_update" style={{ marginTop: 6 }}>
          <div className="dec__head"><Glyph tone={decided === "accepted" ? "done" : decided === "dismissed" ? "inert" : "you"} size={11} />{decided === "accepted" ? "Zapamatováno pro všechnu vaši práci" : decided === "dismissed" ? "Zahozeno" : "Rozhodnutí patří vám"}</div>
          <div className="dec__body">
            <p className="dec__title">Vedoucí chce změnit pro všechnu vaši práci, u všech klientů:</p>
            <ul>
              {waiting.notes.map((n, i) => <li key={`n${i}`}>Poznámka: {n}</li>)}
              {waiting.forget.map((n, i) => <li key={`f${i}`}>Zapomenout: {n}</li>)}
              {waiting.files.map((f) => <li key={f.file}>{f.file}: {f.text}</li>)}
            </ul>
            {stale.length ? (
              <p className="cap" data-aia="lead.self_update.stale">{stale.map((f) => FILE_WORDS[f]).join(", ")}: {STALE_SELF_UPDATE}</p>
            ) : null}
            {t.self_update_pending && !decided ? (
              <div className="dec__foot"><button type="button" className="btn btn--sm btn--quiet" disabled={!canEdit || busy} onClick={() => decide("dismiss")}>Zahodit</button><span className="grow" />
                <button type="button" className="btn btn--primary btn--sm" disabled={!canEdit || busy} onClick={() => decide("accept")}>Pamatovat si</button></div>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}

const REQUEST_WORDS: Record<LeadRequest["kind"], { title: string; action: string }> = {
  agent_job: { title: "Návrhová úloha AI", action: "Spustit úlohu" },
  research_run: { title: "Spuštění výzkumu", action: "Otevřít Kontrolu a spuštění" },
  analysis_retry: { title: "Opakování analýzy", action: "Zopakovat analýzu" },
  design_research: { title: "Hloubkový výzkum k návrhu", action: "Otevřít hloubkový výzkum" },
  interpretation_research: { title: "Hloubkový výzkum k výkladu", action: "Otevřít výklad výsledků" },
  deep_research_retry: { title: "Opakování hloubkového výzkumu", action: "Otevřít hloubkový výzkum" },
};

/** `typed`: the person's own typed start (LO5), started by its approval whatever its kind: a run
 *  starts here on the deployment's run settings, under the same checks as Spuštění's. */
const TYPED_RUN_WORDS = { title: "Spuštění výzkumu", action: "Spustit výzkum" };

function RequestCard({ r, approved, onApprove, canEdit, typed = false }: { r: LeadRequest; approved: { run_id: string; reused?: boolean } | null; onApprove: () => Promise<void>; canEdit: boolean; typed?: boolean }) {
  const { walletOn, retryRun } = useContext(TypedCardFacts);
  const [state, setState] = useState<"open" | "busy" | "done" | "kept">(approved ? "done" : "open");
  const w = typed && r.kind === "research_run" ? TYPED_RUN_WORDS : REQUEST_WORDS[r.kind];
  const paid = r.kind === "agent_job" || typed;
  const decided = state === "done" || !!approved;
  // Approved on what an earlier approval had already started for this design: nothing started.
  const reused = !!approved?.reused;
  // As every card in the conversation reads (chunk 23): eyebrow, title with its state pill, the
  // Lead's why, the key facts as label/value rows, the actions on the right.
  const pill = reused ? { word: "Už proběhlo", tone: "done" as const } : state === "done" ? { word: "Rozhodnuto", tone: "done" as const } : state === "kept" ? { word: "Ponecháno", tone: "inert" as const } : { word: paid ? "Čeká na schválení" : "Otevře krok", tone: "you" as const };
  return (
    <div className="msg" data-card="request" data-typed={typed || undefined}>
      <div className={`dec${state === "done" || state === "kept" ? " is-decided" : ""}`}>
        <div className="dec__body">
          {state === "done" || state === "kept" ? null : <p className="card__eyebrow">{typed ? "Váš příkaz" : "Rozhodnutí patří vám"}</p>}
          <div className="card__titlerow"><p className="dec__title">{w.title}</p><Pill word={pill.word} tone={pill.tone} /></div>
          {decided && r.why === TYPED_UNDECIDED_WHY ? null : <p className="dec__reason">{r.why}</p>}
          <Facts facts={reused
            ? [{ label: "Výsledek", value: r.kind === "research_run" ? "Tento návrh už běží nebo doběhl" : r.kind === "analysis_retry" ? "Analýza tohoto běhu se už opakuje" : "Tato úloha pro tento návrh už proběhla", sub: "Nic nového se nespustilo ani nezaplatilo; její karta je výše v konverzaci." }]
            : r.kind === "analysis_retry"
            // The stage's own retry (decision (b), 2026-10-22): no wallet charge, said in words.
            ? [{ label: "Co se stane", value: "Znovu se zeptá jen modulů analýzy, které v posledním běhu selhaly", sub: "Nad daty, která běh už sebral; nová data se nesbírají. Práh potvrzení se kontroluje jako na Výsledcích." },
              ...(decided ? [] : [{ label: "Který běh", value: retryRun ? retryRunWords(retryRun) : "Studie zatím nemá běh s AI analýzou" }]),
              { label: "Platba", value: "z rozpočtu studie", ...(walletOn ? { sub: "Opakování analýzy se nestrhává z Peněženky." } : {}) }]
            : typed && r.kind === "research_run"
            ? [{ label: "Co se stane", value: "Spustí se výzkum s výchozím nastavením", sub: walletOn ? "Připravenost, práh potvrzení a Peněženka se kontrolují jako na Spuštění." : "Připravenost a práh potvrzení se kontrolují jako na Spuštění." }]
            : paid
            ? [{ label: "Úloha", value: ACTION_LABELS[(r as { action: string }).action as keyof typeof ACTION_LABELS] ?? (r as { action: string }).action }, { label: "Platba", value: "z rozpočtu studie", ...(decided ? {} : { sub: TYPED_UNDECIDED_WHY }) }]
            : [{ label: "Co se stane", value: "Otevře se krok, kde spuštění potvrdíte", sub: "Se všemi jeho kontrolami: připravenost, zodpověditelnost, limit útraty." }]} />
          {state === "open" ? (
            <div className="card__actions"><button type="button" className="btn btn--sm btn--quiet" onClick={() => setState("kept")}>Teď ne</button>
              <button type="button" className="btn btn--primary btn--sm" disabled={!canEdit} onClick={() => { setState("busy"); onApprove().then(() => setState("done"), () => setState("open")); }}>{w.action}</button></div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Composer({ draft, setDraft, onSend, busy, queued, onUnqueue, disabled, hint, focus, picking, onPick, onClearFocus }: {
  draft: string; setDraft: (v: string) => void; onSend: (t: string) => void; busy: boolean;
  queued: { key: string; text: string }[]; onUnqueue: (key: string) => void; disabled: boolean;
  /** Why the composer is shut, in its own field (composerHint); null while it is open. */
  hint: string | null;
  focus: { id: string; label: string } | null;
  picking: boolean; onPick: () => void; onClearFocus: () => void;
}) {
  const ta = useRef<HTMLTextAreaElement>(null);
  return (
    <div className="composer-wrap">
      {queued.length ? (
        <div className="queue" aria-label="Čeká na Vedoucího">
          <div className="cap" style={{ padding: "2px 4px" }}>Vedoucí na ně odpoví, až doodpoví</div>
          {queued.map((q) => (
            <div className="queue__item" key={q.key}><Icon name="clock" size={13} /><span className="queue__text">{q.text}</span>
              <button type="button" className="iconbtn" aria-label="Odebrat z fronty" title="Odebrat z fronty" onClick={() => onUnqueue(q.key)}><Icon name="close" size={13} /></button></div>
          ))}
        </div>
      ) : null}
      {focus ? <div className="refchip"><Icon name="at" size={12} /><b>{focus.label}</b><button type="button" className="iconbtn refchip__clear" aria-label="Zrušit odkaz" onClick={onClearFocus}><Icon name="close" size={11} /></button></div> : null}
      <div className="composer">
        <label className="sr-only" htmlFor="composer">Napište Vedoucímu výzkumu</label>
        <textarea id="composer" ref={ta} rows={1} value={draft} disabled={disabled} placeholder={disabled && hint ? hint : focus ? "Co se má změnit? Např. „kratší“, „přejmenovat na …“" : "Napište Vedoucímu výzkumu…"}
          onChange={(e) => { setDraft(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${Math.min(180, e.target.scrollHeight)}px`; }}
          onKeyDown={(e) => {
            if (e.nativeEvent.isComposing) return;
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(draft); }
          }} />
        <div className="composer__bar">
          <button type="button" className={`iconbtn${picking ? " is-on" : ""}`} aria-pressed={picking} aria-label="Ukázat na prvek artefaktu (@)" title="Ukázat na prvek artefaktu (@)" disabled={disabled} onClick={onPick}><Icon name="at" size={16} /></button>
          <button type="button" className="btn btn--sm btn--quiet" disabled={disabled} onClick={() => onSend("Kde jsme a co mám udělat dál?")}>Kde jsme?</button>
          <button type="button" className="btn btn--sm btn--quiet" disabled={disabled} onClick={() => onSend("Projdi tento krok a navrhni konkrétní úpravy.")}>Navrhni úpravy</button>
          <button type="button" className="composer__send" aria-label={busy ? "Zařadit do fronty" : "Odeslat"} title={busy ? "Zařadit do fronty" : "Odeslat"} disabled={disabled || !draft.trim()} onClick={() => onSend(draft)}><Icon name="send" size={16} /></button>
        </div>
      </div>
      <div className="composer__hint">Enter odešle · Shift+Enter nový řádek · Vedoucí nic nezmění bez vás</div>
    </div>
  );
}
