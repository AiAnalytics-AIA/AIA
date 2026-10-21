"use client";

// The research workbench (ADR 0026; plan research-lead-workbench chunks 3-4): the study screen as
// the research-lead prototype draws it (prototypes/research-lead-v2 @ 9b50963f) -- one study
// header, the phase-grouped stage navigator, and the conversation with the researcher's own
// Research Lead beside the stage's artifact -- over AIA's own stage screens, store and routes.
// The artifact body is the stage screen the classic layout shows; the Lead's edits arrive above
// it as change blocks the person accepts into the working copy; the stage's readiness and AI
// help sit in the inspector over it. A researcher who chose to (Můj Vedoucí; plan inline-decisions
// chunk 2) has the Lead's text edits accepted when its turn finishes -- through the same server
// gate, recorded as automatic -- shown as "Přijato automaticky" with Vrátit; structure still waits.

import { useRouter } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { ApiError, api, lead as leadApi, type ResearchAgentJob, type Study } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { guardedNavigate } from "@/lib/guarded-navigation";
import {
  applyLeadEdit, autoAcceptPlan, describeEdit, editRefusalWords, editStage, focusSelector, revertTextEdit, targetOfElement, textEditInverse,
  type LeadEdit, type LeadRequest, type LeadTurn, type LeadView, type ResearcherLead,
} from "@/lib/lead";
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
import { SampleView } from "./SampleView";
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
const noSubscription = () => () => {};
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

/** Whether this stage is shown in the workbench: the width when the stage opened, kept until another
 * stage opens. A resize across the breakpoint would otherwise remount the stage's screen in the other
 * layout and drop what its editors hold locally (Návrh's narrative, a measurement being edited)
 * without their leave guard; the next stage opens in the layout the width then allows. */
export function useStageWide(stage: string): boolean {
  const live = useWideEnough();
  // Hydration renders the server's guess first; only the browser's own answer is kept.
  const inBrowser = useSyncExternalStore(noSubscription, () => true, () => false);
  const [kept, setKept] = useState<{ stage: string; wide: boolean } | null>(null);
  if (inBrowser && (kept === null || kept.stage !== stage)) setKept({ stage, wide: live });
  return kept && kept.stage === stage ? kept.wide : live;
}

const initials = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
const usd = (n: number | null | undefined) => (typeof n === "number" ? n.toLocaleString("cs-CZ", { maximumFractionDigits: 2 }) : "?");

type EditMark = "accepted" | "dismissed" | { refused: string };
/**
 * A text edit accepted by the researcher's standing choice in this study, with the edit that puts
 * its wording back and the working revision the accept wrote: Vrátit waits until the copy holds it.
 */
type AutoApplied = { key: string; edit: LeadEdit; inverse: LeadEdit | null; revision: number | null };

/**
 * The text edits accepted automatically in this study, kept in the study's page memory rather than
 * in one stage's screen: a stage change -- the Lead's own open_stage among them -- mounts another
 * screen, and the edits accepted on the way still show on their stage, with Vrátit.
 */
type AutoList = {
  get: () => AutoApplied[];
  set: (change: (items: AutoApplied[]) => AutoApplied[]) => void;
  subscribe: (listener: () => void) => () => void;
};
const AUTO_KEY = "workbench:lead-auto-applied";
function autoList(memory: Map<string, unknown>): AutoList {
  const kept = memory.get(AUTO_KEY) as AutoList | undefined;
  if (kept) return kept;
  let items: AutoApplied[] = [];
  const listeners = new Set<() => void>();
  const list: AutoList = {
    get: () => items,
    set: (change) => {
      items = change(items);
      for (const l of listeners) l();
    },
    subscribe: (l) => {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
  };
  memory.set(AUTO_KEY, list);
  return list;
}

export function Workbench({ frame, step, store, memory, save, inspector, reload, confirm, onAgentStarted, jobs, onOpenJob, onRefreshJobs, children }: {
  frame: StudyFrame;
  step: StepKey;
  store: ResearchStore;
  /** The study's page memory (ResearchSession): what outlives one stage's screen. */
  memory?: Map<string, unknown>;
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
  /** The study's design jobs, newest first, as the AI help lists them; shown in the conversation. */
  jobs: ResearchAgentJob[];
  onOpenJob: (job: ResearchAgentJob) => void;
  /** Read the jobs again: done while one of them still moves. */
  onRefreshJobs: () => Promise<unknown>;
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
  // Automatic text edits (inline-decisions 2): the researcher's choice, the turns already finished
  // when the conversation was first read (never replayed), the turns already tried, what was applied.
  const [autoOn, setAutoOn] = useState(false);
  const seen = useRef<Set<string> | null>(null);
  const tried = useRef(new Set<string>());
  const [ownMemory] = useState(() => new Map<string, unknown>());
  const autoStore = useMemo(() => autoList(memory ?? ownMemory), [memory, ownMemory]);
  const autoApplied = useSyncExternalStore(autoStore.subscribe, autoStore.get, autoStore.get);
  const onLead = useCallback((me: ResearcherLead) => setAutoOn(!!me.lead?.preferences?.auto_accept_text_edits), []);
  const onTurns = useCallback((ts: LeadTurn[]) => {
    if (seen.current === null) seen.current = new Set(ts.filter((t) => t.actor === "lead" && t.status === "COMPLETED").map((t) => t.turn_id));
    setTurns(ts);
  }, []);
  // Pointing at the artifact: "@" arms it, the next click on an element the Lead can name is the
  // focus of the next message. Escape, or a click on nothing nameable, disarms it.
  const [picking, setPicking] = useState(false);
  const [focus, setFocus] = useState<{ id: string; label: string } | null>(null);
  useEffect(() => {
    if (!picking) return;
    const body = document.getElementById("artbody");
    const onClick = (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const t = targetOfElement(e.target as Element);
      if (t) setFocus(t);
      setPicking(false);
      document.getElementById("composer")?.focus();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPicking(false);
    };
    body?.addEventListener("click", onClick, true);
    window.addEventListener("keydown", onKey);
    return () => {
      body?.removeEventListener("click", onClick, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [picking]);
  const [notice, setNotice] = useState<string | null>(null);
  const [study, setStudy] = useState<Study | null>(null);
  // A job that still moves is read again, so its card in the conversation follows it; every attempt,
  // failed or not, moves the poll on, so one failed read does not freeze the card.
  const moving = jobs.some((j) => !j.is_terminal);
  const [jobPolls, setJobPolls] = useState(0);
  useEffect(() => {
    if (!moving) return;
    const t = setTimeout(() => void onRefreshJobs().finally(() => setJobPolls((n) => n + 1)), 3000);
    return () => clearTimeout(t);
  }, [moving, jobs, jobPolls, onRefreshJobs]);
  // The budget meter is read again whenever a run, a design job or a Lead turn changes state: all spend.
  const jobStates = jobs.map((j) => `${j.run_id}:${j.status}`).join(",");
  const turnStates = turns.map((t) => `${t.turn_id}:${t.status}`).join(",");
  useEffect(() => {
    api.study(frame.studyId).then(setStudy, () => setStudy(null));
  }, [frame.studyId, runs, jobStates, turnStates]);


  const go = useCallback((target: WorkbenchStage) => {
    const s = STAGES[target];
    // Within one route the stage is its hash (a result view, or Vzorek on Dimenze's route).
    if (s.step === step) {
      window.location.hash = s.view ?? "";
      return;
    }
    // Through a link's click, so a stage's leave guard (Návrh's unsaved edits) can stop it.
    guardedNavigate(stageHref(target, frame.stepHref), (url) => router.push(url));
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
        out[`${t.turn_id}:${i}`] = d.status === "refused" ? { refused: editRefusalWords(d.reason) } : d.status;
      }
    }
    return out;
  }, [turns]);
  const open = edits.filter((x) => !marks[x.key] || typeof marks[x.key] === "object");
  const here = open.filter((x) => editStage(x.edit) === stage);
  const autoHere = autoApplied.filter((x) => editStage(x.edit) === stage);

  // The researcher's standing choice is their decision (ADR 0026): when a turn finishes, its text
  // edits are accepted through the same gate as a click, as that person, on the working revision,
  // marked automatic in the ledger. The server refuses the call unless the choice is on, any edit
  // that is not wording, and a turn written from an older working copy (stale_turn: someone saved
  // while the Lead worked); the inverse of each is kept from the content it was applied to.
  const autoAccept = useCallback(async (plan: { turnId: string; indices: number[]; edits: LeadEdit[] }[]) => {
    // Only over a copy with nothing waiting to be saved: a change still being typed is the person's,
    // and the Lead's wording waits for their click beside it rather than racing it.
    const now = store.get();
    if (now.save.kind !== "saved" && now.save.kind !== "new") {
      setNotice("Textové úpravy Vedoucího čekají k přijetí: v pracovní kopii máte neuložené změny.");
      return;
    }
    let base = now.revision;
    let content = { project: now.project, analysis: now.analysis };
    const applied: AutoApplied[] = [];
    for (const { turnId, indices, edits: turnEdits } of plan) {
      try {
        const r = await leadApi.decideEdits(frame.studyId, turnId, { decision: "accept", indices, base_revision: base, auto: true });
        for (const x of r.results) {
          const edit = turnEdits[x.index];
          if (x.status !== "accepted" || !edit) continue;
          const inverse = textEditInverse(content, edit);
          const next = applyLeadEdit(content, edit);
          if ("content" in next) content = next.content;
          applied.push({ key: `${turnId}:${x.index}`, edit, inverse, revision: r.workspace_revision });
        }
        if (r.workspace_revision !== null) base = r.workspace_revision;
      } catch (e) {
        setNotice(e instanceof ApiError && (e.code === "stale_revision" || e.code === "stale_turn")
          ? "Pracovní kopie se mezitím změnila, textové úpravy Vedoucího proto čekají k přijetí."
          : e instanceof ApiError ? e.message : String(e));
        break;
      }
    }
    if (applied.length) autoStore.set((a) => [...a, ...applied]);
    setLeadEpoch((n) => n + 1);
    if (!applied.length) return;
    // AIA wrote a new revision: read it into this copy in place. A change the person made while the
    // gate answered is not dropped (nor saved over the newer revision by a disposed copy): it stays
    // on screen, the copy in conflict, and they are told.
    try {
      if (!(await store.reload(undefined, { since: now }))) {
        setNotice("Vedoucí přijal textové úpravy, zatímco jste psali. Vaše změna zůstala na obrazovce, ale neuložila se: zkopírujte si ji a pracovní kopii načtěte znovu.");
      }
    } catch (e) {
      setNotice(e instanceof Error ? e.message : String(e));
    }
  }, [store, frame.studyId, autoStore]);
  useEffect(() => {
    if (!frame.canEdit || seen.current === null) return;
    const plan = autoAcceptPlan(turns, autoOn, seen.current, tried.current);
    if (!plan.length) return;
    for (const p of plan) tried.current.add(p.turnId);
    void autoAccept(plan.map((p) => ({ ...p, edits: turns.find((t) => t.turn_id === p.turnId)?.output?.edits ?? [] })));
  }, [turns, autoOn, frame.canEdit, autoAccept]);

  // Vrátit: the wording the edit replaced, written back as the person's own edit of the working copy
  // (the normal, revision-checked save). The ledger's accept stands: a decision is made once.
  const revert = (key: string) => {
    const item = autoApplied.find((x) => x.key === key);
    if (!item?.inverse) return;
    const s = store.get();
    // Until the copy holds what the accept wrote, the wording to put back is not on screen yet.
    if (!holds(s, item)) return;
    const r = revertTextEdit({ project: s.project, analysis: s.analysis }, item.edit, item.inverse);
    if ("refused" in r) {
      setNotice(r.refused);
      return;
    }
    store.update(() => ({ project: r.content.project, analysis: r.content.analysis }));
    autoStore.set((a) => a.filter((x) => x.key !== key));
  };

  // Accepting or dismissing goes through the server's gate, one turn at a time: it applies the
  // edits to the working copy it holds, saves it and records each decision in the ledger.
  const decide = async (decision: "accept" | "dismiss", keys: string[]) => {
    setNotice(null);
    // Unsaved edits are saved first; if they cannot be (a conflict), nothing is decided and the
    // working copy's own conflict state stays as it is: reloading here would lose those edits.
    try {
      await store.flush();
    } catch {
      setNotice("Pracovní kopii se nepodařilo uložit. Nejdřív vyřešte uložení (vpravo nahoře), potom změny přijměte.");
      return;
    }
    let base = store.get().revision;
    const byTurn = new Map<string, number[]>();
    for (const key of keys) {
      const [turnId, i] = key.split(":");
      byTurn.set(turnId!, [...(byTurn.get(turnId!) ?? []), Number(i)]);
    }
    let changed = false;
    for (const [turnId, indices] of byTurn) {
      try {
        const r = await leadApi.decideEdits(frame.studyId, turnId, { decision, indices, base_revision: base });
        if (r.results.some((x) => x.status === "accepted")) changed = true;
        // An edit the server refused stays open; say why, in words (a sample size outside the
        // valid range, RQC9, among them).
        const refused = [...new Set(r.results.filter((x) => x.status === "refused").map((x) => editRefusalWords(x.reason)))];
        if (refused.length) setNotice(refused.join(" "));
        // The next turn's edits are decided on the revision this one wrote.
        if (r.workspace_revision !== null) base = r.workspace_revision;
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
  const flushBeforeMessage = useCallback(() => store.flush(), [store]);
  const leadPane = (
    <LeadPane studyId={frame.studyId} stage={stage} canEdit={frame.canEdit} focus={focus} picking={picking}
      onPick={() => setPicking((p) => !p)} onClearFocus={() => setFocus(null)} jobs={[...jobs].reverse()} onOpenJob={onOpenJob} onView={onView} onRequest={onRequest} onTurns={onTurns} onLead={onLead} beforeMessage={flushBeforeMessage} epoch={leadEpoch}
      mode={mode} onFocusMode={() => setMode((m) => (m === "conversation" ? "split" : "conversation"))} />
  );

  return (
    <div className={`wb${picking ? " wb-picking" : ""}`} data-workbench>
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
              {picking ? <div className="artbar artbar--op" role="status"><Icon name="at" size={13} /><div className="artbar__grow">Klikněte na otázku, oddíl nebo část zadání, o které chcete s Vedoucím mluvit. Esc zruší.</div></div> : null}
              {notice ? <div className="artbar artbar--stale" role="status"><Glyph tone="reopened" size={12} /><div className="artbar__grow">{notice}</div><button type="button" className="iconbtn" aria-label="Zavřít" onClick={() => setNotice(null)}><Icon name="close" size={14} /></button></div> : null}
              {autoHere.length ? <AutoBar items={autoHere} state={state} canEdit={frame.canEdit} onRevert={revert} onHide={() => autoStore.set((a) => a.filter((x) => editStage(x.edit) !== stage))} /> : null}
              {here.length ? <EditsBar items={here} state={state} marks={marks} canEdit={frame.canEdit} onAccept={(keys) => void decide("accept", keys)} onDismiss={(keys) => void decide("dismiss", keys)} /> : null}
              <div className="artstage">
                <div className="artbody" id="artbody"><div className="wb-stage">
                  {stage === "sample" ? <SampleView project={state.project} onOpen={go} /> : null}
                  {/* Sample shows Dimenze's screen hidden, so its readiness still reaches the inspector. */}
                  <div hidden={stage === "sample"}>{children}</div>
                </div></div>
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

function AutoBar({ items, state, canEdit, onRevert, onHide }: {
  items: AutoApplied[]; state: ResearchState; canEdit: boolean; onRevert: (key: string) => void; onHide: () => void;
}) {
  const content = { project: state.project, analysis: state.analysis };
  const wording = (e: LeadEdit | null) => (!e ? null : e.op === "set_text" || e.op === "list_replace" ? e.value : e.op === "question_edit" ? e.text : null);
  return (
    <div className="artbar artbar--op edits" role="region" aria-label="Přijato automaticky">
      <div className="edits__head">
        <Glyph tone="done" size={12} />
        <div className="artbar__grow"><b>Přijato automaticky (vaše nastavení)</b> · textové úpravy Vedoucího, struktura čeká na vás</div>
        <button type="button" className="btn btn--sm btn--quiet" onClick={onHide}>Skrýt</button>
      </div>
      {items.map((item) => {
        const { key, edit, inverse } = item;
        const loaded = holds(state, item);
        return (
        <div key={key} className="chg" data-aia={`lead-auto.${key}`}>
          <div className="chg__h">
            <span className="grow">{describeEdit(content, edit).where} · Přijato automaticky (vaše nastavení)</span>
            <button type="button" className="btn btn--sm" disabled={!canEdit || !inverse || !loaded}
              title={loaded ? undefined : "Načítám pracovní kopii s přijatým zněním…"} onClick={() => onRevert(key)}>Vrátit</button>
          </div>
          {wording(inverse) !== null ? <div className="chg__before">{wording(inverse)}</div> : null}
          {wording(edit) !== null ? <div>{wording(edit)}</div> : null}
        </div>
        );
      })}
    </div>
  );
}

/** Whether the working copy holds the revision an automatic accept wrote: only then is Vrátit's wording on screen. */
function holds(state: ResearchState, item: AutoApplied): boolean {
  return item.revision !== null && state.revision !== null && state.revision >= item.revision;
}

function StudyHeader({ frame, study, pending, blocked, onPending }: { frame: StudyFrame; study: Study | null; pending: number; blocked: number; onPending: () => void }) {
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  // Leaving the study goes through a link's click too, so Návrh's leave guard can stop it.
  const leave = (url: string) => {
    setMenu(false);
    guardedNavigate(url, (u) => router.push(u));
  };
  const budget = study?.budget_usd ?? null;
  const spent = study?.spent_usd ?? null;
  const spentPct = budget && spent !== null ? Math.min(100, (spent / budget) * 100) : 0;
  return (
    <header className="shead">
      <span className="shead__band" aria-hidden="true" />
      <button type="button" className="shead__home" onClick={() => leave(appRoutes.client(frame.clientId))} aria-label={`Klienti › ${frame.clientName}`}>
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
              <button type="button" role="menuitem" className="listbtn" onClick={() => leave(appRoutes.lead())}>Můj Vedoucí výzkumu</button>
              <button type="button" role="menuitem" className="listbtn" onClick={() => leave(appRoutes.client(frame.clientId))}>Pracovní prostor klienta</button>
              <button type="button" role="menuitem" className="listbtn" onClick={() => leave(appRoutes.memory())}>Projektová paměť</button>
              <button type="button" role="menuitem" className="listbtn" onClick={() => leave(appRoutes.settings())}>Nastavení</button>
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
