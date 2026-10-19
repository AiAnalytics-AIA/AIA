"use client";

// The Research Lead's conversation (ADR 0026; plan research-lead-workbench chunk 6), after the
// prototype's Conversation and Composer (prototypes/research-lead-v2 @ 9b50963f) and wired to AIA:
// the researcher's own session on this study, read from GET /lead and written by POST /lead/turns.
// Each Lead turn is a worker step; while one runs the pane reads the session again every 1.5 s.
// The Lead's view tools are applied when its turn arrives; its edits are change blocks in the
// artifact pane; its request is a decision card that starts nothing until the person approves.

import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { lead as leadApi, researcherLead, ApiError } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import type { LeadOutput, LeadRequest, LeadState, LeadTurn, LeadView, ResearcherLead } from "@/lib/lead";
import { STAGES, isWorkbenchStage, type WorkbenchStage } from "@/lib/workbench-stages";
import { Glyph } from "./Glyph";
import { Icon, Mark } from "./Icons";

const POLL_MS = 1500;

const REASON: Record<string, string> = {
  research_lead_unavailable: "Vedoucí výzkumu není v tomto prostředí zapnutý.",
  research_lead_unconfigured: "Vedoucí výzkumu čeká: model AI není pro pracovníka nastavený.",
  ai_runtime_unavailable: "Vedoucí výzkumu čeká: AI v tomto prostředí neběží.",
  egress_route_not_approved_for_class: "Tuto studii nelze poslat modelu: trasa AI není schválena pro třídu jejích dat.",
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

export function LeadPane({ studyId, stage, canEdit, focus, onView, onRequest, onTurns, onFocusMode, mode, epoch }: {
  studyId: string;
  stage: WorkbenchStage;
  canEdit: boolean;
  /** What the person has pointed at in the artifact, sent with the next message. */
  focus: { id: string; label: string } | null;
  onView: (ops: LeadView[]) => void;
  onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>;
  /** Changes when something outside the pane decided on a turn: read the session again. */
  epoch: number;
  /** Every read of the session, so the artifact pane can show the newest edits. */
  onTurns: (turns: LeadTurn[]) => void;
  onFocusMode: () => void;
  mode: "split" | "conversation" | "artifact";
}) {
  const [me, setMe] = useState<ResearcherLead | null>(null);
  const [session, setSession] = useState<LeadState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [queued, setQueued] = useState<string[]>([]);
  const [sending, setSending] = useState(false);
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
    }
  }, [studyId, onTurns]);

  useEffect(() => {
    if (epoch) void read();
  }, [epoch, read]);
  useEffect(() => {
    researcherLead.get().then(setMe, (e: unknown) => setError(e instanceof ApiError && e.status === 404 ? "Vedoucí výzkumu v této verzi AIA zatím není." : String(e)));
    void read();
  }, [read]);

  // While a turn runs, read again; when it finishes, apply the newest turn's view tools once.
  useEffect(() => {
    if (!session?.busy) return;
    const t = setTimeout(() => void read(), POLL_MS);
    return () => clearTimeout(t);
  }, [session, read]);
  useEffect(() => {
    const last = session ? newestCompleted(session.turns) : null;
    if (!last || applied.current === last.turn_id) return;
    const first = applied.current === null;
    applied.current = last.turn_id;
    // On opening a study the old answer's navigation is not replayed.
    if (!first && last.output?.view?.length) onView(last.output.view);
  }, [session, onView]);

  const post = useCallback(async (body: Parameters<typeof leadApi.post>[1]) => {
    setSending(true);
    try {
      await leadApi.post(studyId, body);
      await read();
    } catch (e) {
      setError(e instanceof ApiError ? reasonWords(e.code) : String(e));
    } finally {
      setSending(false);
    }
  }, [studyId, read]);

  // The Lead greets a study it has not spoken in for eight hours (the server keeps the rule).
  useEffect(() => {
    if (greeted.current || !me?.hatched || !session?.available || !canEdit) return;
    greeted.current = true;
    void post({ kind: "greeting", stage });
  }, [me, session, canEdit, stage, post]);

  // A message written while the Lead works waits, then goes.
  useEffect(() => {
    if (session?.busy || sending || !queued.length) return;
    const [next, ...rest] = queued;
    setQueued(rest);
    void post({ kind: "message", text: next, stage, focus });
  }, [session, sending, queued, post, stage, focus]);

  const send = (text: string) => {
    const t = text.trim();
    if (!t) return;
    if (session?.busy || sending) setQueued((q) => [...q, t]);
    else void post({ kind: "message", text: t, stage, focus });
    setDraft("");
  };

  const hatch = async () => {
    try {
      setMe(await researcherLead.hatch());
    } catch (e) {
      setError(e instanceof ApiError ? reasonWords(e.code) : String(e));
    }
  };

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
      <Conversation turns={session?.turns ?? []} busy={!!session?.busy || sending} name={name} onFollow={send} onView={onView} onRequest={onRequest} canEdit={canEdit}>
        {error ? <div className="msg"><div className="notice"><Glyph tone="fault" size={11} />{error}</div></div> : null}
        {me && !me.hatched ? <HatchCard onHatch={hatch} /> : null}
        {session && !session.available ? <div className="msg"><div className="notice"><Glyph tone="inert" size={11} />{reasonWords(session.unavailable_reason ?? "research_lead_unavailable")}</div></div> : null}
      </Conversation>
      <Composer draft={draft} setDraft={setDraft} onSend={send} busy={!!session?.busy || sending} queued={queued} onUnqueue={(i) => setQueued((q) => q.filter((_, j) => j !== i))}
        disabled={!canEdit || !me?.hatched || !session?.available} focus={focus} />
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

function Conversation({ turns, busy, name, onFollow, onView, onRequest, canEdit, children }: {
  turns: LeadTurn[]; busy: boolean; name: string; canEdit: boolean;
  onFollow: (t: string) => void; onView: (ops: LeadView[]) => void; onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>;
  children: React.ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);
  const atBottom = useRef(true);
  const [away, setAway] = useState(false);
  const sig = `${turns.length}:${turns.at(-1)?.status ?? ""}:${busy}`;
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
          {turns.map((t) => t.actor === "person"
            ? <PersonTurn key={t.turn_id} t={t} />
            : <LeadTurnView key={t.turn_id} t={t} name={name} last={t.turn_id === lastLead?.turn_id} busy={busy} onFollow={onFollow} onView={onView} onRequest={onRequest} canEdit={canEdit} />)}
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

const VIEW_LABEL = (v: LeadView) => (v.op === "open_stage" ? `Otevřít ${isWorkbenchStage(v.stage) ? STAGES[v.stage].label : v.stage}` : `Ukázat ${v.target}`);

function LeadTurnView({ t, name, last, busy, onFollow, onView, onRequest, canEdit }: {
  t: LeadTurn; name: string; last: boolean; busy: boolean; canEdit: boolean;
  onFollow: (t: string) => void; onView: (ops: LeadView[]) => void; onRequest: (turn: LeadTurn, r: LeadRequest) => Promise<void>;
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
          <SelfUpdate o={o} />
          {o.dropped?.length ? <div className="cap">{o.dropped.length === 1 ? "1 navržená změna se netýkala ničeho v pracovní kopii a byla vynechána." : `${o.dropped.length} navržené změny se netýkaly ničeho v pracovní kopii a byly vynechány.`}</div> : null}
        </div>
      </div>
      {o.request ? <RequestCard r={o.request} approved={t.request_decision ?? null} onApprove={() => onRequest(t, o.request!)} canEdit={canEdit} /> : null}
      {last && !busy && o.follow?.length ? (
        <div className="follow" aria-label="Navázat">{o.follow.map((f) => <button key={f} type="button" className="follow__btn" onClick={() => onFollow(f)}><Icon name="next" size={13} />{f}</button>)}</div>
      ) : null}
    </div>
  );
}

function SelfUpdate({ o }: { o: LeadOutput }) {
  const u = o.self_update;
  if (!u) return null;
  const parts = [
    u.name ? "jméno" : null,
    u.soul ? "SOUL" : null,
    u.user ? "USER" : null,
    u.remember?.length ? `zapamatováno: ${u.remember.map((m) => m.text).join("; ")}` : null,
    u.forget?.length ? `zapomenuto ${u.forget.length}×` : null,
  ].filter(Boolean);
  if (!parts.length) return null;
  return <div className="notice" style={{ marginTop: 6 }}><Icon name="memory" size={12} />Upraveno: {parts.join(" · ")} · <Link href={appRoutes.lead()} className="linkbtn">Můj Vedoucí</Link></div>;
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
          <p className="dec__title">{w.title}{r.kind === "agent_job" ? ` · ${r.action}` : ""}</p>
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

function Composer({ draft, setDraft, onSend, busy, queued, onUnqueue, disabled, focus }: {
  draft: string; setDraft: (v: string) => void; onSend: (t: string) => void; busy: boolean;
  queued: string[]; onUnqueue: (i: number) => void; disabled: boolean; focus: { id: string; label: string } | null;
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
      {focus ? <div className="refchip"><Icon name="at" size={12} /><b>{focus.label}</b></div> : null}
      <div className="composer">
        <label className="sr-only" htmlFor="composer">Napište Vedoucímu výzkumu</label>
        <textarea id="composer" ref={ta} rows={1} value={draft} disabled={disabled} placeholder={focus ? "Co se má změnit? Např. „kratší“, „přejmenovat na …“" : "Napište Vedoucímu výzkumu…"}
          onChange={(e) => { setDraft(e.target.value); e.target.style.height = "auto"; e.target.style.height = `${Math.min(180, e.target.scrollHeight)}px`; }}
          onKeyDown={(e) => {
            if (e.nativeEvent.isComposing) return;
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(draft); }
          }} />
        <div className="composer__bar">
          <button type="button" className="btn btn--sm btn--quiet" disabled={disabled} onClick={() => onSend("Kde jsme a co mám udělat dál?")}>Kde jsme?</button>
          <button type="button" className="btn btn--sm btn--quiet" disabled={disabled} onClick={() => onSend("Projdi tento krok a navrhni konkrétní úpravy.")}>Navrhni úpravy</button>
          <button type="button" className="composer__send" aria-label={busy ? "Zařadit do fronty" : "Odeslat"} title={busy ? "Zařadit do fronty" : "Odeslat"} disabled={disabled || !draft.trim()} onClick={() => onSend(draft)}><Icon name="send" size={16} /></button>
        </div>
      </div>
      <div className="composer__hint">Enter odešle · Shift+Enter nový řádek · Vedoucí nic nezmění bez vás</div>
    </div>
  );
}
