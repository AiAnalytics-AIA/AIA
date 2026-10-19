"use client";

// The research workbench (ADR 0026; plan research-lead-workbench chunks 3-4): the study screen as
// the research-lead prototype draws it (prototypes/research-lead-v2 @ 9b50963f) -- one study
// header, the phase-grouped stage navigator, and the conversation with the researcher's own
// Research Lead beside the stage's artifact -- over AIA's own stage screens, store and routes.
// The artifact body is the stage screen the classic layout shows; the Lead's edits arrive above
// it as change blocks the person accepts into the working copy; the stage's readiness and AI
// help sit in the inspector over it.

import { useRouter } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { ApiError, api, lead as leadApi, type Study } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { describeEdit, editStage, focusSelector, type LeadEdit, type LeadRequest, type LeadTurn, type LeadView } from "@/lib/lead";
import { type FocusMode, readSplit, writeSplit } from "@/lib/workbench-split";
import { PHASES, STAGES, STAGE_ORDER, stageHref, stageOf, stageState, type WorkbenchStage } from "@/lib/workbench-stages";
import { blockers, designLane, runLane } from "@/research/lane";
import type { ResearchState, ResearchStore } from "@/research/store";
import type { StepKey } from "@/research/steps";
import type { StudyFrame } from "../rehome/research/frame";
import { useRuns } from "../rehome/research/StageTrack";
import { Glyph, type GlyphTone } from "./Glyph";
import { Icon, Mark } from "./Icons";
import { LeadPane } from "./LeadPane";
import { Split } from "./Split";
import "./workbench.css";

const storage = () => {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
};

/** The URL hash, as the result views read it: the stage on Výsledky depends on it. */
function useHash(): string {
  return useSyncExternalStore(
    (on) => {
      window.addEventListener("hashchange", on);
      window.addEventListener("popstate", on);
      return () => {
        window.removeEventListener("hashchange", on);
        window.removeEventListener("popstate", on);
      };
    },
    () => window.location.hash,
    () => "",
  );
}

/** Wide enough for the workbench: under 1100 px the classic layout serves (the prototype's rule). */
const WIDE = "(min-width: 1100px)";
const canMatch = () => typeof window !== "undefined" && typeof window.matchMedia === "function";
export function useWideEnough(): boolean {
  return useSyncExternalStore(
    (on) => {
      if (!canMatch()) return () => {};
      const mq = window.matchMedia(WIDE);
      mq.addEventListener("change", on);
      return () => mq.removeEventListener("change", on);
    },
    // Without media queries (a test's DOM) the width is unknown: the classic layout serves.
    () => (canMatch() ? window.matchMedia(WIDE).matches : false),
    () => true,
  );
}

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
const usd = (n: number | null | undefined) => (typeof n === "number" ? n.toLocaleString("cs-CZ", { maximumFractionDigits: 2 }) : "?");

type EditMark = "accepted" | "dismissed" | { refused: string };

export function Workbench({ frame, step, store, save, inspector, reload, confirm, onAgentStarted, children }: {
  frame: StudyFrame;
  step: StepKey;
  store: ResearchStore;
  /** The save state, as SaveIndicator draws it. */
  save: ReactNode;
  /** The inspector column the classic layout draws beside the stage: readiness, AI help, blockers. */
  inspector: ReactNode;
  /** Read the working copy again from AIA: after the server applied accepted edits. */
  reload: () => void;
  /** Ask the person a yes/no question (the study's AskDialog). */
  confirm: (message: string) => Promise<boolean>;
  /** A design job the person approved on a Lead decision card has started. */
  onAgentStarted: (runId: string) => void;
  /** The stage's artifact body. */
  children: ReactNode;
}) {
  const router = useRouter();
  const state = useSyncExternalStore(store.subscribe, store.get, store.get);
  const hash = useHash();
  const stage = stageOf(step, hash);
  const runs = useRuns(frame.studyId, step);
  const lane = useMemo(() => ({ ...designLane(state), ...runLane(runs) }), [state, runs]);
  const [mode, setMode] = useState<FocusMode>("split");
  const [split, setSplit] = useState(() => readSplit(storage()));
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [turns, setTurns] = useState<LeadTurn[]>([]);
  const [leadEpoch, setLeadEpoch] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [study, setStudy] = useState<Study | null>(null);
  useEffect(() => {
    api.study(frame.studyId).then(setStudy, () => setStudy(null));
  }, [frame.studyId, runs]);


  const go = useCallback((target: WorkbenchStage) => {
    const s = STAGES[target];
    if (s.step === step && s.view) {
      window.location.hash = s.view;
      return;
    }
    router.push(stageHref(target, frame.stepHref));
  }, [router, step, frame.stepHref]);

  const onView = useCallback((ops: LeadView[]) => {
    for (const v of ops) {
      if (v.op === "open_stage") go(v.stage);
      else {
        // After a stage change the element appears on the next render: look again briefly.
        let tries = 0;
        const find = () => {
          const el = document.querySelector<HTMLElement>(focusSelector(v.target));
          if (el) {
            el.scrollIntoView({ block: "center", behavior: "smooth" });
            el.classList.add("just");
            setTimeout(() => el.classList.remove("just"), 2300);
          } else if (tries++ < 10) setTimeout(find, 150);
        };
        find();
      }
    }
  }, [go]);

  // A design job is approved on the server: the spend limit, the ledger row and the start together.
  const onRequest = useCallback(async (turn: LeadTurn, r: LeadRequest) => {
    if (r.kind !== "agent_job") {
      go(r.kind === "research_run" ? "fieldwork" : r.kind === "design_research" ? "design" : "report");
      return;
    }
    await store.flush();
    let confirmUsd: number | undefined;
    for (;;) {
      try {
        const started = await leadApi.approveRequest(frame.studyId, turn.turn_id, confirmUsd);
        onAgentStarted(started.run_id);
        setLeadEpoch((n) => n + 1);
        return;
      } catch (e) {
        if (e instanceof ApiError && e.code === "cost_confirmation_required" && confirmUsd === undefined) {
          const ceiling = Number(e.details.ceiling_usd);
          const limit = Number(e.details.limit_usd);
          if (!(await confirm(`Úloha může stát až ${usd(ceiling)} USD, což dosahuje limitu studie ${usd(limit)} USD. Spustit?`))) throw e;
          confirmUsd = ceiling;
          continue;
        }
        setNotice(e instanceof ApiError ? e.message : String(e));
        throw e;
      }
    }
  }, [go, store, frame.studyId, confirm, onAgentStarted]);

  // Alt+Shift+A / C / N: artifact focus, conversation focus, back to the split (the prototype's keys).
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (!(e.altKey && e.shiftKey)) return;
      const m = e.code === "KeyA" ? "artifact" : e.code === "KeyC" ? "conversation" : e.code === "KeyN" ? "split" : null;
      if (!m) return;
      e.preventDefault();
      setMode((cur) => (cur === m ? "split" : m));
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);

  // Every edit of every finished Lead turn, newest turn first, with what the person decided.
  const edits = useMemo(() => {
    const out: { key: string; edit: LeadEdit; turn: LeadTurn }[] = [];
    for (const t of [...turns].reverse()) {
      if (t.actor !== "lead" || t.status !== "COMPLETED") continue;
      (t.output?.edits ?? []).forEach((edit, i) => out.push({ key: `${t.turn_id}:${i}`, edit, turn: t }));
    }
    return out;
  }, [turns]);
  // What the person decided on each edit, as the approval ledger holds it (read with the turns).
  const marks = useMemo(() => {
    const out: Record<string, EditMark> = {};
    for (const t of turns) {
      for (const [i, d] of Object.entries(t.edit_decisions ?? {})) {
        out[`${t.turn_id}:${i}`] = d.status === "refused" ? { refused: d.reason ?? "Úpravu už nelze použít." } : d.status;
      }
    }
    return out;
  }, [turns]);
  const open = edits.filter((x) => !marks[x.key] || typeof marks[x.key] === "object");
  const here = open.filter((x) => editStage(x.edit) === stage);

  // Accepting or dismissing goes through the server's gate, one turn at a time: it applies the
  // edits to the working copy it holds, saves it and records each decision in the ledger.
  const decide = async (decision: "accept" | "dismiss", keys: string[]) => {
    setNotice(null);
    await store.flush().catch(() => {});
    const byTurn = new Map<string, number[]>();
    for (const key of keys) {
      const [turnId, i] = key.split(":");
      byTurn.set(turnId!, [...(byTurn.get(turnId!) ?? []), Number(i)]);
    }
    let changed = false;
    for (const [turnId, indices] of byTurn) {
      try {
        const r = await leadApi.decideEdits(frame.studyId, turnId, { decision, indices, base_revision: store.get().revision });
        if (r.results.some((x) => x.status === "accepted")) changed = true;
      } catch (e) {
        setNotice(e instanceof ApiError && e.code === "stale_revision"
          ? "Pracovní kopie se mezitím změnila. Načetl jsem ji znovu; zkuste změnu přijmout ještě jednou."
          : e instanceof ApiError ? e.message : String(e));
        if (e instanceof ApiError && e.code === "stale_revision") changed = true;
        break;
      }
    }
    setLeadEpoch((n) => n + 1);
    if (changed) reload();
  };

  const blocked = blockers(state).length;
  const leadPane = (
    <LeadPane studyId={frame.studyId} stage={stage} canEdit={frame.canEdit} focus={null} onView={onView} onRequest={onRequest} onTurns={setTurns} epoch={leadEpoch}
      mode={mode} onFocusMode={() => setMode((m) => (m === "conversation" ? "split" : "conversation"))} />
  );

  return (
    <div className="wb" data-workbench>
      <a href="#composer" className="skip">Přeskočit na zprávu</a>
      <StudyHeader frame={frame} study={study} pending={open.length} blocked={blocked} onPending={() => open[0] && go(editStage(open[0].edit))} />
      <StageNav stage={stage} lane={lane} onOpen={go} />
      <main className="workspace">
        <Split split={split} mode={mode} onSplit={setSplit} onCommit={(v) => { setSplit(v); writeSplit(storage(), v); }}
          left={leadPane}
          rail={<Rail pending={open.length} onOpen={() => setMode("split")} />}
          right={
            <div className="art" aria-label={`Artefakt ${STAGES[stage].label}`}>
              <div className="arthead">
                <div style={{ minWidth: 0 }}>
                  <div className="row"><h2 className="arthead__title">{STAGES[stage].label}</h2>{save}</div>
                  <div className="arthead__sub">{state.revision === null ? "Pracovní kopie zatím neuložena" : `Pracovní kopie · revize ${state.revision}`}{frame.canEdit ? "" : " · jen ke čtení"}</div>
                </div>
                <div className="arthead__actions">
                  <button type="button" className={`btn btn--sm btn--quiet${inspectorOpen ? " is-on" : ""}`} aria-expanded={inspectorOpen} onClick={() => setInspectorOpen((v) => !v)}>
                    <Icon name="inspector" size={14} />Připravenost a pomoc{blocked ? ` · ${blocked}` : ""}
                  </button>
                  <button type="button" className={`iconbtn${mode === "artifact" ? " is-on" : ""}`} aria-pressed={mode === "artifact"} title={mode === "artifact" ? "Zpět na 40 / 60" : "Soustředit se na artefakt"} aria-label={mode === "artifact" ? "Zpět na 40 / 60" : "Soustředit se na artefakt"} onClick={() => setMode((m) => (m === "artifact" ? "split" : "artifact"))}>
                    <Icon name={mode === "artifact" ? "normal" : "focusArtifact"} size={16} />
                  </button>
                </div>
              </div>
              {notice ? <div className="artbar artbar--stale" role="status"><Glyph tone="reopened" size={12} /><div className="artbar__grow">{notice}</div><button type="button" className="iconbtn" aria-label="Zavřít" onClick={() => setNotice(null)}><Icon name="close" size={14} /></button></div> : null}
              {here.length ? <EditsBar items={here} state={state} marks={marks} canEdit={frame.canEdit} onAccept={(keys) => void decide("accept", keys)} onDismiss={(keys) => void decide("dismiss", keys)} /> : null}
              <div className="artstage">
                <div className="artbody" id="artbody"><div className="wb-stage">{children}</div></div>
                <aside className="insp" aria-label="Připravenost a pomoc" hidden={!inspectorOpen}>
                  <div className="insp__head">
                    <div style={{ minWidth: 0, flex: 1 }}><div className="insp__title">Připravenost a pomoc</div><div className="insp__sub">{STAGES[stage].label}</div></div>
                    <button type="button" className="iconbtn" aria-label="Zavřít" title="Zavřít" onClick={() => setInspectorOpen(false)}><Icon name="close" size={16} /></button>
                  </div>
                  <div className="insp__body">{inspector}</div>
                </aside>
              </div>
            </div>
          } />
      </main>
    </div>
  );
}

function EditsBar({ items, state, marks, canEdit, onAccept, onDismiss }: {
  items: { key: string; edit: LeadEdit; turn: LeadTurn }[];
  state: ResearchState; marks: Record<string, EditMark>; canEdit: boolean;
  onAccept: (keys: string[]) => void; onDismiss: (keys: string[]) => void;
}) {
  const content = { project: state.project, analysis: state.analysis };
  const keys = items.map((x) => x.key);
  return (
    <div className="artbar artbar--you edits" role="region" aria-label="Návrhy Vedoucího">
      <div className="edits__head">
        <Glyph tone="you" size={12} />
        <div className="artbar__grow"><b>Vedoucí navrhuje {items.length === 1 ? "1 změnu" : `${items.length} změn`}</b> · nic se nezmění, dokud je nepřijmete</div>
        <button type="button" className="btn btn--sm btn--quiet" onClick={() => onDismiss(keys)}>Zahodit vše</button>
        <button type="button" className="btn btn--sm btn--primary" disabled={!canEdit} onClick={() => onAccept(keys)}>Přijmout vše</button>
      </div>
      {items.map(({ key, edit }) => {
        const d = describeEdit(content, edit);
        const m = marks[key];
        return (
          <div key={key} className="chg" data-aia={`lead-edit.${key}`}>
            <div className="chg__h">
              <span className="grow">{d.where}</span>
              {typeof m === "object" ? <span className="chg__refused">{m.refused}</span> : null}
              <button type="button" className="btn btn--sm btn--quiet" onClick={() => onDismiss([key])}>Zahodit</button>
              <button type="button" className="btn btn--sm" disabled={!canEdit} onClick={() => onAccept([key])}>Přijmout</button>
            </div>
            {d.before !== null ? <div className="chg__before">{d.before}</div> : null}
            {d.after !== null ? <div>{d.after}</div> : null}
            {edit.why ? <div className="chg__why">Proč: {edit.why}</div> : null}
          </div>
        );
      })}
    </div>
  );
}

function StudyHeader({ frame, study, pending, blocked, onPending }: { frame: StudyFrame; study: Study | null; pending: number; blocked: number; onPending: () => void }) {
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  const budget = study?.budget_usd ?? null;
  const spent = study?.spent_usd ?? null;
  const spentPct = budget && spent !== null ? Math.min(100, (spent / budget) * 100) : 0;
  return (
    <header className="shead">
      <span className="shead__band" aria-hidden="true" />
      <button type="button" className="shead__home" onClick={() => router.push(appRoutes.client(frame.clientId))} aria-label={`Klienti › ${frame.clientName}`}>
        <span className="shead__mono" aria-hidden="true">{initials(frame.clientName)}</span>
        <span className="shead__title"><span className="shead__client">Klienti › {frame.clientName}</span><span className="shead__study">{frame.studyName}</span></span>
      </button>
      <span className="shead__state"><Glyph tone={blocked ? "you" : "done"} size={11} />{blocked ? `Do spuštění zbývá ${blocked}` : "Návrh splňuje podmínky kroků"}</span>
      <span className="shead__spacer" />
      {pending > 0 ? <button type="button" className="shead__pending" onClick={onPending}><Glyph tone="you" size={11} />Čeká na vás: {pending}</button> : null}
      <span className="budgetmini" title="Rozpočet studie: utraceno / limit">
        <Icon name="budget" size={13} />
        <span className="budgetmini__bar" aria-hidden="true"><i style={{ width: `${spentPct}%` }} /></span>
        <span className="num">{budget === null ? "Rozpočet nenastaven" : `${usd(spent)} / ${usd(budget)} USD`}</span>
      </span>
      <div style={{ position: "relative" }}>
        <button type="button" className="iconbtn" aria-label="Nabídka" title="Nabídka" aria-expanded={menu} onClick={() => setMenu((v) => !v)}><Icon name="menu" size={16} /></button>
        {menu ? (
          <>
            <div className="scrim" onClick={() => setMenu(false)} />
            <div className="pop menu" style={{ right: 0, top: 34, width: 280 }} role="menu">
              <button type="button" role="menuitem" className="listbtn" onClick={() => router.push(appRoutes.lead())}>Můj Vedoucí výzkumu</button>
              <button type="button" role="menuitem" className="listbtn" onClick={() => router.push(appRoutes.client(frame.clientId))}>Pracovní prostor klienta</button>
              <button type="button" role="menuitem" className="listbtn" onClick={() => router.push(appRoutes.memory())}>Projektová paměť</button>
              <button type="button" role="menuitem" className="listbtn" onClick={() => router.push(appRoutes.settings())}>Nastavení</button>
            </div>
          </>
        ) : null}
      </div>
    </header>
  );
}

const STAGE_TONE: Record<string, GlyphTone> = { done: "done", running: "running", you: "you", fault: "fault", inert: "inert", ready: "ready" };

function StageNav({ stage, lane, onOpen }: { stage: WorkbenchStage; lane: Parameters<typeof stageState>[1]; onOpen: (s: WorkbenchStage) => void }) {
  const onKey = (e: React.KeyboardEvent<HTMLElement>) => {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) return;
    const btns = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>(".nav__stage"));
    const i = btns.indexOf(document.activeElement as HTMLButtonElement);
    const j = e.key === "Home" ? 0 : e.key === "End" ? btns.length - 1 : Math.max(0, Math.min(btns.length - 1, i + (e.key === "ArrowRight" ? 1 : -1)));
    btns[j]?.focus();
    e.preventDefault();
  };
  return (
    <nav className="nav" aria-label="Kroky studie" onKeyDown={onKey}>
      {PHASES.map((ph) => (
        <div className="nav__phase" key={ph.id} role="group" aria-label={ph.label}>
          <span className="nav__plabel">{ph.label}</span>
          {STAGE_ORDER.filter((s) => STAGES[s].phase === ph.id).map((s) => {
            const k = stageState(s, lane);
            const cur = s === stage;
            return (
              <button key={s} type="button" className={`nav__stage${cur ? " is-current" : ""}${k.tone === "inert" ? " is-inert" : ""}${k.tone === "you" ? " is-you" : ""}`}
                aria-current={cur ? "page" : undefined} title={`${STAGES[s].label}${k.line ? `: ${k.line}` : ""}`} onClick={() => onOpen(s)}>
                <Glyph tone={STAGE_TONE[k.tone] ?? "inert"} size={11} />{STAGES[s].short}{k.line ? <span className="sr-only">, {k.line}</span> : null}
              </button>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function Rail({ pending, onOpen }: { pending: number; onOpen: () => void }) {
  return (
    <div className="rail">
      <button type="button" className="iconbtn" style={{ width: 40, height: 40 }} aria-label="Otevřít konverzaci" title="Otevřít konverzaci" onClick={onOpen}><Mark size={20} /></button>
      {pending > 0 ? <span className="rail__badge" title={`Čeká na vás: ${pending}`}>{pending}</span> : null}
    </div>
  );
}
