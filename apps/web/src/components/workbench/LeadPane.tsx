"use client";

// The Research Lead's conversation (ADR 0026; plan research-lead-workbench chunk 6), after the
// prototype's Conversation and Composer (prototypes/research-lead-v2 @ 9b50963f) and wired to AIA:
// the researcher's own session on this study, read from GET /lead and written by POST /lead/turns.
// Each Lead turn is a worker step; while one runs the pane reads the session again every 1.5 s.
// The Lead's view tools are applied when its turn arrives; its edits are change blocks in the
// artifact pane; its request is a decision card that starts nothing until the person approves.

import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { lead as leadApi, researcherLead, ApiError, type ResearchAgentJob } from "@/lib/api";
import { ACTION_LABELS } from "@/lib/research-agent-jobs";
import { appRoutes } from "@/lib/app-routes";
import type { LeadOutput, LeadRequest, LeadState, LeadTurn, LeadView, ResearcherLead, SelfUpdateDecision } from "@/lib/lead";
import { pendingSelfUpdate, targetLabel } from "@/lib/lead";
import { STAGES, isWorkbenchStage, type WorkbenchStage } from "@/lib/workbench-stages";
import { Glyph } from "./Glyph";
import { Icon, Mark } from "./Icons";

const POLL_MS = 1500;

/**
 * What the person is writing and what waits to be sent, per study, for as long as the page lives:
 * the pane is unmounted when the window narrows to the classic layout, and comes back empty
 * otherwise.
 */
type Queued = { text: string; stage: WorkbenchStage; focus: { id: string; label: string } | null };
const kept = new Map<string, { draft: string; queued: Queued[] }>();

/** An accepted self-update left a file another turn changed since; its notes did apply. The 200
 * names it, and the turn's decision keeps it after a reload. */
const STALE_SELF_UPDATE = "Soubor se mezitím změnil, požádejte Vedoucího znovu.";

const REASON: Record<string, string> = {
  research_lead_unavailable: "Vedoucí výzkumu není v tomto prostředí zapnutý.",
  research_lead_disabled: "Vedoucí výzkumu není v tomto prostředí zapnutý.",
  egress_unclassified_material: "Tuto zprávu zatím nelze poslat modelu: materiál studie není klasifikovaný. Rozhoduje o tom správce AIA.",
  egress_no_approved_route: "Vedoucí výzkumu čeká: pro model AI není schválená trasa.",
  egress_route_not_approved_for_class: "Tuto studii nelze poslat modelu: trasa AI není schválena pro třídu jejích dat.",
  research_lead_unconfigured: "Vedoucí výzkumu čeká: model AI není pro pracovníka nastavený.",
  ai_runtime_unavailable: "Vedoucí výzkumu čeká: AI v tomto prostředí neběží.",
  licence_undetermined: "Tuto studii nelze poslat modelu: licence dat panelu to neumožňuje.",
  lead_context_too_large: "Studie je pro jednu odpověď příliš velká. Zkuste se zeptat na konkrétní část.",
  lead_busy: "Vedoucí ještě odpovídá na předchozí zprávu.",
  lead_not_hatched: "Nejdřív si vylíhněte vlastního Vedoucího výzkumu.",
  AWAITING_BUDGET: "Vedoucí čeká na rozpočet studie.",
};
const reasonWords = (code: string | null) => (code ? REASON[code] ?? `Vedoucí se zastavil (${code}).` : "Vedoucí se zastavil.");

const time = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
};

/** The newest Lead turn that finished: the one whose view tools have been applied. */
const newestCompleted = (turns: LeadTurn[]) => [...turns].reverse().find((t) => t.actor === "lead" && t.status === "COMPLETED") ?? null;

export function LeadPane({ studyId, stage, canEdit, focus, picking, onPick, onClearFocus, onView, onRequest, onTurns, onFocusMode, mode, epoch, jobs = [], onOpenJob, onLead, beforeMessage }: {
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
  mode: "split" | "conversation" | "artifact";
}) {
  const [me, setMe] = useState<ResearcherLead | null>(null);
  const [session, setSession] = useState<LeadState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState(() => kept.get(studyId)?.draft ?? "");
  // A message written while the Lead works keeps the stage and the element it was written about.
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
      setError(null);
      return s;
    } catch (e) {
      setError(e instanceof ApiError && e.status === 404 ? "Vedoucí výzkumu v této verzi AIA zatím není." : e instanceof Error ? e.message : String(e));
      return null;
    } finally {
      setReads((n) => n + 1);
    }
  }, [studyId, onTurns]);

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

  // A message written while the Lead works waits, then goes.
  useEffect(() => {
    if (session?.busy || sending || held || !queued.length) return;
    const [next, ...rest] = queued;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the queue drains one message each time the Lead is free
    setQueued(rest);
    if (next) void message(next);
  }, [session, sending, held, queued, message]);

  const send = (text: string) => {
    const t = text.trim();
    if (!t) return;
    if (session?.busy || sending || held) setQueued((q) => [...q, { text: t, stage, focus }]);
    else void message({ text: t, stage, focus });
    setDraft("");
    onClearFocus();
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
  return (
    <div className="conv">
      <div className="conv__head">
        <div className="conv__avatar"><Mark size={18} onDark /></div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="conv__who">{name}</div>
          <div className="conv__sees">Vidí: {STAGES[stage].label} · pracovní kopie studie{focus ? ` · ${focus.label}` : ""}</div>
        </div>
        <Link className="iconbtn" href={appRoutes.lead()} title="Můj Vedoucí: jeho soubory a paměť" aria-label="Můj Vedoucí"><Icon name="user" size={16} /></Link>
        <button type="button" className={`iconbtn${mode === "conversation" ? " is-on" : ""}`} aria-pressed={mode === "conversation"} title={mode === "conversation" ? "Zpět na 40 / 60" : "Soustředit se na konverzaci"} aria-label={mode === "conversation" ? "Zpět na 40 / 60" : "Soustředit se na konverzaci"} onClick={onFocusMode}>
          <Icon name={mode === "conversation" ? "normal" : "focusChat"} size={16} />
        </button>
      </div>
      <Conversation turns={session?.turns ?? []} jobs={jobs} onOpenJob={onOpenJob} busy={!!session?.busy || sending} name={name} onFollow={send} onView={onView} onRequest={onRequest} onSelfUpdate={decideSelfUpdate} canEdit={canEdit}>
        {error ? <div className="msg"><div className="notice"><Glyph tone="fault" size={11} />{error}</div></div> : null}
        {held ? (
          <div className="msg"><div className="notice"><Glyph tone="fault" size={11} />Zprávu se nepodařilo odeslat. Čeká ve frontě.
            <button type="button" className="chip" onClick={() => { setError(null); setHeld(false); }}>Zkusit znovu</button></div></div>
        ) : null}
        {me && !me.hatched ? <HatchCard onHatch={hatch} /> : null}
        {session && !session.available ? <div className="msg"><div className="notice"><Glyph tone="inert" size={11} />{reasonWords(session.unavailable_reason ?? "research_lead_unavailable")}</div></div> : null}
      </Conversation>
      <Composer draft={draft} setDraft={setDraft} onSend={send} busy={!!session?.busy || sending} queued={queued.map((q) => q.text)} onUnqueue={(i) => setQueued((q) => q.filter((_, j) => j !== i))}
        disabled={!canEdit || !me?.hatched || !session?.available} focus={focus} picking={picking} onPick={onPick} onClearFocus={onClearFocus} />
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

function Conversation({ turns, jobs, onOpenJob, busy, name, onFollow, onView, onRequest, onSelfUpdate, canEdit, children }: {
  turns: LeadTurn[]; jobs: ResearchAgentJob[]; onOpenJob?: (job: ResearchAgentJob) => void; busy: boolean; name: string; canEdit: boolean;
  onFollow: (t: string) => void; onView: (ops: LeadView[]) => void; onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>;
  onSelfUpdate: (turn: LeadTurn, decision: "accept" | "dismiss") => Promise<SelfUpdateDecision | null>;
  children: React.ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const [away, setAway] = useState(false);
  const sig = `${turns.length}:${turns.at(-1)?.status ?? ""}:${busy}:${jobs.map((j) => j.status).join(",")}`;
  useLayoutEffect(() => {
    const el = box.current;
    if (el && atBottom.current) el.scrollTop = el.scrollHeight;
  }, [sig]);
  const onScroll = () => {
    const el = box.current!;
    const b = el.scrollHeight - el.scrollTop - el.clientHeight <= 24;
    atBottom.current = b;
    setAway(!b);
  };
  const lastLead = [...turns].reverse().find((t) => t.actor === "lead");
  return (
    <>
      <div className="conv__scroll" ref={box} onScroll={onScroll} tabIndex={0} role="log" aria-label={`Konverzace: ${name}`} aria-live="polite" aria-relevant="additions">
        <div>
          {children}
          {timeline(turns, jobs).map((x) => x.kind === "job"
            ? <ActivityCard key={x.job.run_id} job={x.job} onOpen={onOpenJob} />
            : x.turn.actor === "person"
              ? <PersonTurn key={x.turn.turn_id} t={x.turn} />
              : <LeadTurnView key={x.turn.turn_id} t={x.turn} name={name} last={x.turn.turn_id === lastLead?.turn_id} busy={busy} onFollow={onFollow} onView={onView} onRequest={onRequest} onSelfUpdate={onSelfUpdate} canEdit={canEdit}
                  job={jobs.find((j) => j.run_id === x.turn.request_decision?.run_id) ?? null} onOpenJob={onOpenJob} />)}
          <div style={{ height: 8 }} />
        </div>
      </div>
      {away ? (
        <div className="conv__latestwrap">
          <button type="button" className="btn btn--sm conv__latest" onClick={() => { const el = box.current!; el.scrollTop = el.scrollHeight; atBottom.current = true; setAway(false); }}><Icon name="down" size={13} />Na nejnovější</button>
        </div>
      ) : null}
    </>
  );
}

function PersonTurn({ t }: { t: LeadTurn }) {
  return (
    <div className="msg msg--user" data-msg={t.turn_id}>
      {t.focus ? <div className="bubble__ref"><Icon name="at" size={12} />{t.focus.label}</div> : null}
      <div className="bubble">{t.text}</div>
      <div className="msgacts" role="group" aria-label="Akce zprávy"><span className="msgmeta">{time(t.created_at)}</span></div>
    </div>
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

const VIEW_LABEL = (v: LeadView) => (v.op === "open_stage" ? `Otevřít ${isWorkbenchStage(v.stage) ? STAGES[v.stage].label : v.stage}` : `Ukázat: ${targetLabel(v.target)}`);

function LeadTurnView({ t, name, last, busy, onFollow, onView, onRequest, onSelfUpdate, canEdit, job, onOpenJob }: {
  t: LeadTurn; name: string; last: boolean; busy: boolean; canEdit: boolean; job: ResearchAgentJob | null; onOpenJob?: (job: ResearchAgentJob) => void;
  onFollow: (t: string) => void; onView: (ops: LeadView[]) => void; onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>;
  onSelfUpdate: (turn: LeadTurn, decision: "accept" | "dismiss") => Promise<SelfUpdateDecision | null>;
}) {
  if (t.status === "QUEUED" || t.status === "RUNNING") {
    return (
      <div className="msg"><div className="lead"><div className="lead__av"><Mark size={14} onDark /></div>
        <div style={{ minWidth: 0 }}><div className="lead__name"><b>{name}</b><span>{t.kind === "greeting" ? "připravuje přehled studie" : "pracuje"}</span></div>
          <div className="typing" aria-label={`${name} odpovídá`}><i /><i /><i /></div></div></div></div>
    );
  }
  if (t.status !== "COMPLETED" || !t.output) {
    return <div className="msg"><div className="notice"><Glyph tone={t.status === "WAITING" ? "world" : t.status === "CANCELLED" ? "cancelled" : "fault"} size={11} />{reasonWords(t.reason ?? t.status)}<span className="msgmeta">· {time(t.created_at)}</span></div></div>;
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
          {o.view?.length ? <div className="links">{o.view.map((v, i) => <button key={i} type="button" className="linkchip" onClick={() => onView([v])}><Icon name="open" size={12} />{VIEW_LABEL(v)}</button>)}</div> : null}
          <SelfUpdate t={t} o={o} canEdit={canEdit} onDecide={(d) => onSelfUpdate(t, d)} />
          {o.dropped?.length ? <div className="cap">{o.dropped.length === 1 ? "1 navržená změna se netýkala ničeho v pracovní kopii a byla vynechána." : `${o.dropped.length} navržené změny se netýkaly ničeho v pracovní kopii a byly vynechány.`}</div> : null}
        </div>
      </div>
      {o.request ? <RequestCard r={o.request} approved={t.request_decision ?? null} onApprove={() => onRequest(t, o.request!)} canEdit={canEdit} /> : null}
      {job ? <ActivityCard job={job} onOpen={onOpenJob} /> : null}
      {last && !busy && o.follow?.length ? (
        <div className="follow" aria-label="Navázat">{o.follow.map((f) => <button key={f} type="button" className="follow__btn" onClick={() => onFollow(f)}><Icon name="next" size={13} />{f}</button>)}</div>
      ) : null}
    </div>
  );
}

/** Turns and the jobs no turn started, in the order they happened. */
function timeline(turns: LeadTurn[], jobs: ResearchAgentJob[]): ({ kind: "turn"; turn: LeadTurn; at: number } | { kind: "job"; job: ResearchAgentJob; at: number })[] {
  const linked = new Set(turns.map((t) => t.request_decision?.run_id).filter(Boolean));
  const at = (iso: string | null | undefined) => Date.parse(iso ?? "") || 0;
  return [
    ...turns.map((turn) => ({ kind: "turn" as const, turn, at: at(turn.created_at) })),
    ...jobs.filter((j) => !linked.has(j.run_id)).map((job) => ({ kind: "job" as const, job, at: at(job.created_at) })),
  ].sort((a, b) => a.at - b.at);
}

const ADVICE = new Set(["critique_design", "design_copilot", "answer_memory"]);
const JOB_STATE: Record<string, { word: string; tone: "done" | "running" | "world" | "fault" | "cancelled" | "inert" }> = {
  COMPLETED: { word: "hotovo", tone: "done" },
  RUNNING: { word: "běží", tone: "running" },
  QUEUED: { word: "ve frontě", tone: "running" },
  FAILED: { word: "selhalo", tone: "fault" },
  CANCELLED: { word: "zrušeno", tone: "cancelled" },
};

/** A design job in the conversation, as the prototype's activity card: what, how it stands, the way to its result. */
function ActivityCard({ job, onOpen }: { job: ResearchAgentJob; onOpen?: (job: ResearchAgentJob) => void }) {
  const s = JOB_STATE[job.status] ?? (job.status.startsWith("WAITING") || job.status.startsWith("AWAITING") ? { word: "čeká", tone: "world" as const } : { word: job.status.toLowerCase(), tone: "inert" as const });
  const done = job.status === "COMPLETED";
  const cost = typeof job.actual_cost_usd === "number" ? ` · ${job.actual_cost_usd.toLocaleString("cs-CZ", { maximumFractionDigits: 3 })} USD` : "";
  return (
    <div className="msg" data-aia={`activity.${job.run_id}`}>
      <div className="act act--worker">
        <div className="act__row">
          <span className="act__type" title="Úloha AI"><Icon name="worker" size={13} /></span>
          <span className="act__title">{ACTION_LABELS[job.action] ?? job.action}</span>
          <span className="act__sum">· {s.word}{cost}</span>
          <span className="act__right">
            <Glyph tone={s.tone} size={12} title={s.word} />
            {done && onOpen ? <button type="button" className="btn btn--sm" onClick={() => onOpen(job)}>{ADVICE.has(job.action) ? "Otevřít" : "Zkontrolovat"}</button> : null}
          </span>
        </div>
      </div>
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
  design_research: { title: "Hloubkový výzkum k návrhu", action: "Otevřít hloubkový výzkum" },
  interpretation_research: { title: "Hloubkový výzkum k výkladu", action: "Otevřít výklad výsledků" },
};

function RequestCard({ r, approved, onApprove, canEdit }: { r: LeadRequest; approved: { run_id: string } | null; onApprove: () => Promise<void>; canEdit: boolean }) {
  const [state, setState] = useState<"open" | "busy" | "done" | "kept">(approved ? "done" : "open");
  const w = REQUEST_WORDS[r.kind];
  const paid = r.kind === "agent_job";
  return (
    <div className="msg">
      <div className={`dec${state === "done" || state === "kept" ? " is-decided" : ""}`}>
        <div className="dec__head"><Glyph tone={state === "done" ? "done" : state === "kept" ? "inert" : "you"} size={11} />{state === "done" ? "Rozhodnuto" : state === "kept" ? "Ponecháno" : "Rozhodnutí patří vám"}</div>
        <div className="dec__body">
          <p className="dec__title">{w.title}{r.kind === "agent_job" ? ` · ${ACTION_LABELS[r.action as keyof typeof ACTION_LABELS] ?? r.action}` : ""}</p>
          <p className="dec__reason">{r.why}</p>
          <p className="cap">{paid ? "Placená úloha: spustí se až vaším potvrzením a hradí se z rozpočtu studie." : "Nic se nespustí: otevře se krok, kde spuštění potvrdíte se všemi jeho kontrolami (připravenost, zodpověditelnost, limit útraty)."}</p>
          {state === "open" ? (
            <div className="dec__foot"><button type="button" className="btn btn--sm btn--quiet" onClick={() => setState("kept")}>Teď ne</button><span className="grow" />
              <button type="button" className="btn btn--primary btn--sm" disabled={!canEdit} onClick={() => { setState("busy"); onApprove().then(() => setState("done"), () => setState("open")); }}>{w.action}</button></div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Composer({ draft, setDraft, onSend, busy, queued, onUnqueue, disabled, focus, picking, onPick, onClearFocus }: {
  draft: string; setDraft: (v: string) => void; onSend: (t: string) => void; busy: boolean;
  queued: string[]; onUnqueue: (i: number) => void; disabled: boolean; focus: { id: string; label: string } | null;
  picking: boolean; onPick: () => void; onClearFocus: () => void;
}) {
  const ta = useRef<HTMLTextAreaElement>(null);
  return (
    <div className="composer-wrap">
      {queued.length ? (
        <div className="queue" aria-label="Čeká na odeslání">
          <div className="cap" style={{ padding: "2px 4px" }}>Odešle se, až Vedoucí doodpoví</div>
          {queued.map((q, i) => (
            <div className="queue__item" key={`${i}-${q}`}><Icon name="clock" size={13} /><span className="queue__text">{q}</span>
              <button type="button" className="iconbtn" aria-label="Odebrat z fronty" title="Odebrat z fronty" onClick={() => onUnqueue(i)}><Icon name="close" size={13} /></button></div>
          ))}
        </div>
      ) : null}
      {focus ? <div className="refchip"><Icon name="at" size={12} /><b>{focus.label}</b><button type="button" className="iconbtn" style={{ width: 20, height: 20 }} aria-label="Zrušit odkaz" onClick={onClearFocus}><Icon name="close" size={11} /></button></div> : null}
      <div className="composer">
        <label className="sr-only" htmlFor="composer">Napište Vedoucímu výzkumu</label>
        <textarea id="composer" ref={ta} rows={1} value={draft} disabled={disabled} placeholder={focus ? "Co se má změnit? Např. „kratší“, „přejmenovat na …“" : "Napište Vedoucímu výzkumu…"}
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
