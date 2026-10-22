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
import { type KeyboardEvent as ReactKeyboardEvent, type ReactNode, type Ref, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { ApiError, api, lead as leadApi, research, type Readiness, type ResearchAgentJob, type ResearchRun, type Study } from "@/lib/api";
import { withBudget } from "@/lib/budget-line";
import { backEntry, closeStack, emptyStack, type InspectorEntry, type InspectorStack, onStage, openEntry, topEntry } from "@/lib/inspector-stack";
import { availabilityWords, leadAvailability, type LeadAvailability, type LeadStateWithWorker } from "@/lib/lead-availability";
import { JOB_STAGE, jobMovesByItself } from "@/lib/lead-cards";
import { unanswerableAsked } from "@/lib/answerability";
import { jobCostAsked } from "@/lib/research-agent-jobs";
import { appRoutes } from "@/lib/app-routes";
import { guardedNavigate } from "@/lib/guarded-navigation";
import { rovingIndex } from "@/lib/roving";
import { useDismiss } from "../ui/parts";
import {
  LEAD_REASON_WORDS, ANALYSIS_RETRY_MOVED_QUESTION, STALE_CARD_QUESTION, LEAD_REVEAL, applyLeadEdit, autoAcceptPlan, describeEdit, editRefusalWords, editStage, focusSelector, revertTextEdit, targetLabel, targetOfElement, textEditInverse,
  type LeadEdit, type LeadRequest, type LeadTurn, type LeadView, type ResearcherLead,
} from "@/lib/lead";
import {
  CLOSED, DRAWER_LAYOUT_MIN_PX, SPLIT_LAYOUT_MIN_PX, conversationShown, drawerForLayout, isCompact, isModal, nextDrawer, onEscape,
  type DrawerEvent, type DrawerState, type FocusTarget, type WorkbenchLayout,
} from "@/lib/workbench-layout";
import { parseAiaId } from "@/lib/workbench-artifacts";
import { type FocusMode, readSplit, writeSplit } from "@/lib/workbench-split";
import { PHASES, STAGES, STAGE_ORDER, stageHref, stageOf, stageState, type WorkbenchStage } from "@/lib/workbench-stages";
import { impactBase, impactMarks, type ImpactMark } from "@/lib/working-impact";
import { blockers, designLane, runLane } from "@/research/lane";
import { submitWorkingDesign, type ResearchState, type ResearchStore } from "@/research/store";
import type { StepKey } from "@/research/steps";
import type { StudyFrame } from "../rehome/research/frame";
import { readySetLimits, useSampleLimits } from "../rehome/research/useSampleLimits";
import { useRuns } from "../rehome/research/StageTrack";
import { LeadAskContext } from "../rehome/research/AskLead";
import { FrameNavigation } from "@/components/rehome/step";
import { ItemInspector } from "../rehome/research/ItemInspector";
import { Glyph, type GlyphTone } from "./Glyph";
import { Icon, Mark } from "./Icons";
import { ItemInspectBody } from "./ItemInspectBody";
import { ItemInspectorContext, type ItemInspectorApi } from "./item-inspector-context";
import { LeadPane, type LeadCardsContext } from "./LeadPane";
import { SampleView } from "./SampleView";
import { Split } from "./Split";
import { useWorkingImpact } from "./useWorkingImpact";
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

const canMatch = () => typeof window !== "undefined" && typeof window.matchMedia === "function";
const SPLIT_QUERY = `(min-width: ${SPLIT_LAYOUT_MIN_PX}px)`;
const DRAWER_QUERY = `(min-width: ${DRAWER_LAYOUT_MIN_PX}px)`;

/** The workbench's layout at the viewport's width (lib/workbench-layout.ts layoutFor): the split
 * from 1100 px, the side drawer from 768 px, the full-screen sheet below. Without media queries (a
 * test's DOM) and on the server the width is unknown, so the split serves. Changing it changes
 * classes and where the conversation sits, never what is mounted (D21). */
export function useWorkbenchLayout(): WorkbenchLayout {
  return useSyncExternalStore(
    (on) => {
      if (!canMatch()) return () => {};
      const queries = [window.matchMedia(SPLIT_QUERY), window.matchMedia(DRAWER_QUERY)];
      for (const mq of queries) mq.addEventListener("change", on);
      return () => {
        for (const mq of queries) mq.removeEventListener("change", on);
      };
    },
    () => {
      if (!canMatch()) return "split";
      if (window.matchMedia(SPLIT_QUERY).matches) return "split";
      return window.matchMedia(DRAWER_QUERY).matches ? "drawer" : "sheet";
    },
    () => "split",
  );
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
/** A job whose review a card asked for on another stage: that stage's screen opens it on mount. */
export const OPEN_REVIEW_KEY = "workbench:open-review";
const RUN_LINKS_KEY = "workbench:lead-run-links";
/** The run each prepared-run card started, by turn, in the study's page memory: the run's card then
 * stands with the turn that prepared it, across stage changes. */
function runLinks(memory: Map<string, unknown>): Map<string, string> {
  const kept = memory.get(RUN_LINKS_KEY);
  if (kept instanceof Map) return kept as Map<string, string>;
  const made = new Map<string, string>();
  memory.set(RUN_LINKS_KEY, made);
  return made;
}
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

/** The stage whose heading takes the focus once it opens (FrameNavigation's `next.go`); module
 *  scope, because a move to another route remounts the workbench. */
const headingFocus: { pending: { studyId: string; stage: WorkbenchStage } | null } = { pending: null };

/** An item the Lead's `inspect` opens on another stage: opened once that stage is shown, module
 *  scope for the same reason. A move a leave guard stopped leaves nothing pending. */
const leadInspect: { pending: { studyId: string; stage: WorkbenchStage; entry: InspectorEntry } | null } = { pending: null };
/** A stage's item stack as it opens: empty, or holding the Lead's pending `inspect` for it. Reads
 *  the pending entry without taking it (a render may run twice); the stage's effect takes it. */
const openingStack = (studyId: string, stage: WorkbenchStage): InspectorStack => {
  const want = leadInspect.pending;
  return want?.stage === stage && want.studyId === studyId ? openEntry(emptyStack(stage), want.entry) : emptyStack(stage);
};

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
  // Read again when the conversation starts a run, so its card follows it at once.
  const [runEpoch, setRunEpoch] = useState(0);
  const runs = useRuns(frame.studyId, step, runEpoch);
  // A tracked set judged by the readiness methodology in force, as compile judges it (#736).
  const setLimits = readySetLimits(useSampleLimits(frame.studyId));
  const lane = useMemo(() => ({ ...designLane(state, setLimits), ...runLane(runs) }), [state, runs, setLimits]);
  // What the working copy reopened since the newest run's design (before any run, the newest Design
  // Revision): the server's answer, unknown shown as nothing (working-copy-edit-ops WCE7d).
  const base = useMemo(() => impactBase(runs), [runs]);
  const impact = useWorkingImpact(frame.studyId, state.revision, base);
  const reopened = useMemo(() => impactMarks(impact, base), [impact, base]);
  const [mode, setMode] = useState<FocusMode>("split");
  // The conversation at every width (D20, D21): beside the artifact in the split, a side drawer or a
  // full-screen sheet over it below 1100 px. Its state survives a resize; the split has no drawer.
  const layout = useWorkbenchLayout();
  const compact = isCompact(layout);
  const [drawerState, setDrawerState] = useState<DrawerState>(CLOSED);
  const drawer = drawerForLayout(drawerState, layout);
  // Widening to the split closes the drawer for good: narrowing again does not reopen it. Adjusted
  // while rendering, on the layout's change (React's pattern for state derived from a change).
  const [layoutSeen, setLayoutSeen] = useState(layout);
  if (layoutSeen !== layout) {
    setLayoutSeen(layout);
    setDrawerState(drawerForLayout(drawerState, layout));
  }
  const launcher = useRef<HTMLButtonElement>(null);
  const moveFocus = useCallback((to: FocusTarget) => {
    if (!to || to.to === "target") return;
    // Into the conversation: the composer, or, while it is disabled (the session not read yet, the
    // Lead not hatched), the conversation's first control, so focus is never left behind it.
    requestAnimationFrame(() => {
      if (to.to === "launcher") return launcher.current?.focus();
      const composer = document.getElementById("composer") as HTMLTextAreaElement | null;
      if (composer && !composer.disabled) return composer.focus();
      document.querySelector<HTMLElement>(".split__left button:not([disabled]), .split__left a[href]")?.focus();
    });
  }, []);
  const drawerEvent = useCallback((event: DrawerEvent) => {
    const next = nextDrawer(drawer, event, layout);
    setDrawerState(next.state);
    moveFocus(next.focus);
  }, [drawer, layout, moveFocus]);
  const [split, setSplit] = useState(() => readSplit(storage()));
  // "Připravenost a pomoc" lies over the artifact: opening it takes the focus into it, and Escape
  // closes it before the drawer while it is the layer the person is in, giving the focus back to its
  // button (D21's one Escape order; workbench audit, 2026-10-22: it took neither the focus nor
  // Escape).
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const inspectorToggle = useRef<HTMLButtonElement>(null);
  const inspectorPanel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (inspectorOpen) inspectorPanel.current?.focus();
  }, [inspectorOpen]);
  // The item inspector (chunk 2): an item a screen opens (a finding, a cited number) over the
  // artifact, its back stack the stage's own; another stage starts it empty.
  const [items, setItems] = useState<InspectorStack>(() => openingStack(frame.studyId, stage));
  // Another stage starts it empty, stored so (reset while rendering, React's pattern for state
  // that follows a prop): a stage reached again (Výsledky's views by hash keep this workbench
  // mounted) never brings back the drawer it had.
  if (items.stage !== stage) setItems(openingStack(frame.studyId, stage));
  const shownItems = onStage(items, stage);
  // The bodies the opening screens gave, by entry id; another stage's are never shown (its stack is empty).
  const [itemBodies, setItemBodies] = useState<ReadonlyMap<string, () => ReactNode>>(() => new Map());
  const itemInspector = useMemo<ItemInspectorApi>(() => ({
    open: (entry, body) => {
      if (!parseAiaId(entry.id)) return false;
      if (body) setItemBodies((m) => new Map(m).set(entry.id, body));
      setItems((s) => openEntry(onStage(s, stage), entry));
      return true;
    },
    closeWhere: (prefix) => {
      setItems((s) => {
        const on = onStage(s, stage);
        const kept = on.entries.filter((e) => !e.id.startsWith(prefix));
        return kept.length === on.entries.length ? on : { ...on, entries: kept };
      });
    },
  }), [stage]);
  const itemDrawer = useRef<HTMLDivElement>(null);
  // One Escape handler for the drawer, the readiness panel and the item drawer: onEscape gives the
  // one order, after anything a handler already took (lib/workbench-layout.ts). Pointing ("@")
  // keeps its own. The item drawer never takes Escape from behind a modal (review of #623).
  const itemOpen = topEntry(shownItems) !== null;
  useEffect(() => {
    const modal = isModal(layout, drawer);
    if (!modal && !inspectorOpen && !itemOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      // The panel counts while it is the layer in use: not behind a modal drawer, and the focus in
      // it or on nothing (the body), never pulled out of the composer or a field.
      const active = document.activeElement;
      const inPanel = !modal && inspectorOpen && (active === document.body || !!inspectorPanel.current?.contains(active) || active === inspectorToggle.current);
      // The item drawer by the same rule; it lies over the panel, so it goes first.
      const inItem = !modal && itemOpen && (active === document.body || !!itemDrawer.current?.contains(active));
      const step = onEscape(drawer, { handled: e.defaultPrevented, askDialogOpen: !!document.querySelector("[data-ask-dialog][open], dialog[open]"), inspectorOpen: inItem || inPanel }, layout);
      if (step.action === "inspector" && inItem) {
        e.preventDefault();
        setItems((s) => closeStack(onStage(s, stage)));
      } else if (step.action === "inspector") {
        e.preventDefault();
        setInspectorOpen(false);
        inspectorToggle.current?.focus();
      } else if (step.action === "drawer") {
        e.preventDefault();
        setDrawerState(step.state);
        moveFocus(step.focus);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer, layout, moveFocus, inspectorOpen, itemOpen, stage]);
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
  // focus of the next message. Escape, or a click on nothing nameable, disarms it. It is a drawer
  // state: in the drawer and the sheet the conversation steps aside while armed and comes back at
  // the composer (lib/workbench-layout.ts).
  const picking = drawer.kind === "picking";
  const [focus, setFocus] = useState<{ id: string; label: string } | null>(null);
  useEffect(() => {
    if (!picking) return;
    const body = document.getElementById("artbody");
    const onClick = (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const t = targetOfElement(e.target as Element);
      if (t) setFocus(t);
      drawerEvent({ type: "picked" });
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const step = onEscape(drawer, { handled: e.defaultPrevented, askDialogOpen: !!document.querySelector("[data-ask-dialog][open], dialog[open]") }, layout);
      if (step.action !== "disarm_picking") return;
      e.preventDefault();
      setDrawerState(step.state);
      moveFocus(step.focus);
    };
    body?.addEventListener("click", onClick, true);
    window.addEventListener("keydown", onKey);
    return () => {
      body?.removeEventListener("click", onClick, true);
      window.removeEventListener("keydown", onKey);
    };
  }, [picking, drawer, layout, drawerEvent, moveFocus]);
  // Whether the Lead answers (27a), read from every read of GET /lead: the launcher's dot.
  const [availability, setAvailability] = useState<LeadAvailability>({ kind: "UNKNOWN", reason: null });
  const onSession = useCallback((s: LeadStateWithWorker | null, failed: boolean) => setAvailability(leadAvailability(s, failed)), []);
  const [notice, setNotice] = useState<string | null>(null);
  const [study, setStudy] = useState<Study | null>(null);
  // A job that moves on its own (queued or running) is read again, so its card in the conversation
  // follows it; every attempt, failed or not, moves the poll on, so one failed read does not freeze
  // the card. A job waiting for budget, recovery or the AI runtime moves only when a person acts: it
  // is read again on the window's focus, a card's action or a budget change, never on a timer.
  const moving = jobs.some(jobMovesByItself);
  const [jobPolls, setJobPolls] = useState(0);
  useEffect(() => {
    if (!moving) return;
    const t = setTimeout(() => void onRefreshJobs().finally(() => setJobPolls((n) => n + 1)), 3000);
    return () => clearTimeout(t);
  }, [moving, jobs, jobPolls, onRefreshJobs]);
  const waiting = jobs.some((j) => !j.is_terminal && !jobMovesByItself(j));
  useEffect(() => {
    if (!waiting) return;
    const onFocus = () => void onRefreshJobs();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [waiting, onRefreshJobs]);
  // The budget meter is read again whenever a run, a design job or a Lead turn changes state: all spend.
  const jobStates = jobs.map((j) => `${j.run_id}:${j.status}`).join(",");
  const turnStates = turns.map((t) => `${t.turn_id}:${t.status}`).join(",");
  useEffect(() => {
    api.study(frame.studyId).then(setStudy, () => setStudy(null));
  }, [frame.studyId, runs, jobStates, turnStates]);


  /** Opens a stage; true when it moved now, false when a stage's leave guard stopped it. */
  const go = useCallback((target: WorkbenchStage): boolean => {
    const s = STAGES[target];
    // Within one route the stage is its hash (a result view, or Vzorek on Dimenze's route).
    if (s.step === step) {
      window.location.hash = s.view ?? "";
      return true;
    }
    // Through a link's click, so a stage's leave guard (Návrh's unsaved edits) can stop it.
    return guardedNavigate(stageHref(target, frame.stepHref), (url) => router.push(url));
  }, [router, step, frame.stepHref]);

  // A stage's forward action (FrameNavigation's `next`): the stage after this one in the workbench's
  // order, opened as the navigator opens it, then the focus on the new stage's heading. The pressed
  // button may be hidden by the move (Vzorek hides Dimenze's screen), so the focus would fall to the
  // body; the heading names where the person is now. Kept across a route change, which remounts.
  const nextStage = STAGE_ORDER[STAGE_ORDER.indexOf(stage) + 1] ?? null;
  const frameNav = useMemo(() => ({
    next: nextStage ? {
      label: STAGES[nextStage].label,
      go: () => {
        // Only a move that went through asks for the focus: a leave guard that stopped it leaves
        // nothing pending to steal the focus on a later visit (review of #686).
        if (go(nextStage)) headingFocus.pending = { studyId: frame.studyId, stage: nextStage };
      },
    } : null,
  }), [nextStage, go, frame.studyId]);
  useEffect(() => {
    // Consumed on every stage change, matched or not, and only for this study.
    const want = headingFocus.pending;
    headingFocus.pending = null;
    if (want?.stage !== stage || want.studyId !== frame.studyId) return;
    requestAnimationFrame(() => document.querySelector<HTMLElement>("[data-workbench] .arthead__title")?.focus());
  }, [stage, frame.studyId]);
  // A Lead-opened item is titled by its id until its stage shows it: then by its own words on the
  // page (targetOfElement: an item row's words, a question's wording), never its opaque id (the
  // workbench audit's rule). Looked for briefly while the stage's content loads.
  const nameFromPage = useCallback((id: string) => {
    let tries = 0;
    const look = () => {
      const label = targetOfElement(document.querySelector(focusSelector(id)))?.label;
      if (label && label !== targetLabel(id, store.get())) setItems((s) => ({ ...s, entries: s.entries.map((e) => (e.id === id ? { ...e, title: label } : e)) }));
      else if (tries++ < 10) setTimeout(look, 150);
    };
    setTimeout(look, 0);
  }, [store]);
  useEffect(() => {
    // The Lead's `inspect` on another stage, opened by openingStack: taken on every stage change.
    const want = leadInspect.pending;
    leadInspect.pending = null;
    if (want?.stage === stage && want.studyId === frame.studyId) nameFromPage(want.entry.id);
  }, [stage, frame.studyId, nameFromPage]);

  const onView = useCallback((ops: LeadView[]) => {
    // In the drawer or the sheet the conversation steps aside so the person sees what the Lead pointed at.
    const last = ops[ops.length - 1];
    if (compact && last) setDrawerState(nextDrawer(drawer, { type: "view", target: last.op === "open_stage" ? last.stage : last.target }, layout).state);
    for (const v of ops) {
      if (v.op === "open_stage") go(v.stage);
      else if (v.op === "inspect") {
        // The item drawer over the target's own stage, the one a person's click opens; on another
        // stage it opens once that stage is shown (the move remounts on a route change).
        const t = parseAiaId(v.target);
        if (!t) continue;
        const entry = { id: v.target, title: targetLabel(v.target, store.get()) };
        if (t.stage === stage) {
          setItems((s) => openEntry(onStage(s, stage), entry));
          nameFromPage(v.target);
        } else {
          leadInspect.pending = { studyId: frame.studyId, stage: t.stage, entry };
          if (!go(t.stage)) leadInspect.pending = null;
        }
      } else {
        // After a stage change the element appears on the next render: look again briefly.
        let tries = 0;
        const find = () => {
          const el = document.querySelector<HTMLElement>(focusSelector(v.target));
          if (el) {
            el.scrollIntoView({ block: "center", behavior: "smooth" });
            // With the conversation stepped aside, focus follows to what the Lead pointed at.
            // The artifact is inert until the drawer's step aside has rendered: try again briefly.
            if (compact) {
              if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "-1");
              let attempts = 0;
              const take = () => {
                el.focus({ preventScroll: true });
                if (document.activeElement !== el && attempts++ < 10) setTimeout(take, 50);
              };
              take();
            }
            el.classList.add("just");
            setTimeout(() => el.classList.remove("just"), 2300);
          } else {
            if (!tries) window.dispatchEvent(new CustomEvent(LEAD_REVEAL, { detail: v.target }));
            if (tries++ < 10) setTimeout(find, 150);
          }
        };
        find();
      }
    }
  }, [go, compact, drawer, layout, stage, frame.studyId, nameFromPage, store]);

  // A design job is approved on the server: the spend limit, the ledger row and the start together.
  const onRequest = useCallback(async (turn: LeadTurn, r: LeadRequest) => {
    // A person's typed start (LO5) is started by its approval, a run too; the Lead's other cards open their stage.
    if (r.kind !== "agent_job" && !turn.command) {
      go(r.kind === "research_run" ? "fieldwork" : r.kind === "design_research" ? "design" : r.kind === "analysis_retry" ? "analysis" : "report");
      return;
    }
    await store.flush();
    let confirmUsd: number | undefined;
    let onRevision: number | undefined;
    // A typed analysis retry runs on the run its card named; a newer one only on the person's yes.
    let retryRunId = r.kind === "analysis_retry" ? r.run_id : undefined;
    let retryConfirmed = false;
    for (;;) {
      try {
        const started = await leadApi.approveRequest(frame.studyId, turn.turn_id, confirmUsd, onRevision, retryRunId);
        if (r.kind === "agent_job") onAgentStarted(started.run_id);
        else setRunEpoch((n) => n + 1);
        setLeadEpoch((n) => n + 1);
        return;
      } catch (e) {
        if (e instanceof ApiError && e.code === "cost_confirmation_required" && confirmUsd === undefined) {
          const ceiling = Number(e.details.ceiling_usd);
          const limit = Number(e.details.limit_usd);
          if (!(await confirm(`Úloha může stát až ${usd(ceiling)} USD, což dosahuje prahu potvrzení studie ${usd(limit)} USD. Spustit?`))) throw e;
          confirmUsd = ceiling;
          continue;
        }
        if (e instanceof ApiError && e.code === "analysis_retry_target_moved" && !retryConfirmed && typeof e.details.current_run_id === "string") {
          if (!(await confirm(ANALYSIS_RETRY_MOVED_QUESTION))) throw e;
          retryRunId = e.details.current_run_id;
          retryConfirmed = true;
          continue;
        }
        // The design moved since the card was prepared (LO10): it runs on the current one only on a yes.
        if (e instanceof ApiError && e.code === "stale_card" && onRevision === undefined && typeof e.details.current_revision === "number") {
          if (!(await confirm(STALE_CARD_QUESTION))) throw e;
          onRevision = e.details.current_revision;
          continue;
        }
        setNotice(e instanceof ApiError ? LEAD_REASON_WORDS[e.code] ?? e.message : String(e));
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

  const blocked = blockers(state, setLimits).length;
  const flushBeforeMessage = useCallback(() => store.flush(), [store]);
  // A stage may send the Lead a message as the person would type it (Návrh's "Požádat Vedoucího").
  const leadSend = useRef<((text: string) => void) | null>(null);
  const registerSend = useCallback((send: (text: string) => void) => { leadSend.current = send; }, []);
  const askLead = useCallback((text: string) => leadSend.current?.(text), []);

  // A finished job's review opens on the stage its proposal changes (chunk 23): the stage's screen
  // opens it when it mounts (ResearchScreen, OPEN_REVIEW_KEY in the study's page memory).
  const openJob = useCallback((job: ResearchAgentJob) => {
    const target = JOB_STAGE[job.action];
    if (!target || target === stage || !memory) return onOpenJob(job);
    memory.set(OPEN_REVIEW_KEY, job.run_id);
    go(target);
  }, [stage, memory, onOpenJob, go]);

  // The prepared research run's card (chunk 23): the design the person sees submitted and read as
  // Spuštění reads it on a visit, then started through Spuštění's own route, POST …/research/runs
  // (readiness, the study's spend limit and its confirmation, the default persona source, LIVE).
  const runOfTurn = useMemo(() => runLinks(memory ?? ownMemory), [memory, ownMemory]);
  const [, setRunLinksRead] = useState(0);
  const prepareRun = useCallback(async () => {
    const revision = await submitWorkingDesign(store, frame.studyId, "run");
    const [readiness, all] = await Promise.all([research.readiness(frame.studyId, revision.revision_id), research.runs(frame.studyId)]);
    return { readiness, runs: all };
  }, [store, frame.studyId]);
  const startRun = useCallback(async (readiness: Readiness, asked: { ceiling: number; limit: number } | null): Promise<ResearchRun | null> => {
    const ask = async (a: { ceiling: number; limit: number }) =>
      confirm(await withBudget(frame.studyId, `Běh může stát až ${usd(a.ceiling)} USD, což dosahuje prahu potvrzení studie ${usd(a.limit)} USD. Spustit?`, a.ceiling));
    let yes: number | undefined;
    if (asked) {
      if (!(await ask(asked))) return null;
      yes = asked.ceiling;
    }
    const source = readiness.persona_source;
    try {
      return await research.start(frame.studyId, readiness.design_revision_id, yes, undefined, source);
    } catch (e) {
      if (unanswerableAsked(e)) throw new Error("Návrh nezodpoví všechny výzkumné otázky: mezery potvrďte na Spuštění.");
      // The limit or the ceiling moved since the card read them: asked once more with the server's figure.
      const again = jobCostAsked(e);
      if (!again || yes !== undefined || !(await ask(again))) throw e;
      return research.start(frame.studyId, readiness.design_revision_id, again.ceiling, undefined, source);
    }
  }, [frame.studyId, confirm]);
  const cards: LeadCardsContext = useMemo(() => ({
    runs: runs ?? [],
    stepHref: frame.stepHref,
    onStage: go,
    prepareRun,
    startRun,
    runOfTurn,
    onJobsChanged: () => void onRefreshJobs(),
    onRunStarted: (turnId: string, run: ResearchRun) => {
      runOfTurn.set(turnId, run.run_id);
      setRunLinksRead((n) => n + 1);
      setRunEpoch((n) => n + 1);
    },
  }), [runs, frame.stepHref, go, prepareRun, startRun, runOfTurn, onRefreshJobs]);
  const leadPane = (
    <LeadPane studyId={frame.studyId} stage={stage} canEdit={frame.canEdit} focus={focus} picking={picking}
      onPick={() => drawerEvent({ type: picking ? "picked" : "pick" })} onSession={onSession} onClearFocus={() => setFocus(null)} jobs={[...jobs].reverse()} onOpenJob={openJob} cards={cards} onView={onView} onRequest={onRequest} onTurns={onTurns} onLead={onLead} beforeMessage={flushBeforeMessage} epoch={leadEpoch} registerSend={registerSend} design={state}
      mode={mode} onFocusMode={() => setMode((m) => (m === "conversation" ? "split" : "conversation"))}
      onClose={compact ? () => drawerEvent({ type: "close" }) : undefined} />
  );

  return (
    <div className={`wb wb--${layout}${picking ? " wb-picking" : ""}`} data-workbench data-layout={layout}>
      <a href="#composer" className="skip">Přeskočit na zprávu</a>
      <StudyHeader frame={frame} study={study} pending={open.length} blocked={blocked} onPending={() => open[0] && go(editStage(open[0].edit))} layout={layout} inert={isModal(layout, drawer)} />
      <StageNav stage={stage} lane={lane} marks={reopened} onOpen={go} layout={layout} inert={isModal(layout, drawer)} />
      <main className="workspace">
        <Split split={split} mode={mode} layout={layout} shown={conversationShown(layout, drawer)} leftLabel="Vedoucí výzkumu"
          onSplit={setSplit} onCommit={(v) => { setSplit(v); writeSplit(storage(), v); }}
          left={leadPane}
          rail={<Rail ref={launcher} pending={open.length} availability={availability} open={isModal(layout, drawer)} onOpen={() => (compact ? drawerEvent({ type: "open" }) : setMode("split"))} />}
          right={
            <div className="art" aria-label={`Artefakt ${STAGES[stage].label}`}>
              <div className="arthead">
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="row"><h1 className="arthead__title" tabIndex={-1}>{STAGES[stage].label}</h1>{save}</div>
                  <div className="arthead__sub">{state.revision === null ? "Pracovní kopie zatím neuložena" : `Pracovní kopie · revize ${state.revision}`}{frame.canEdit ? "" : " · jen ke čtení"}</div>
                </div>
                <div className="arthead__actions">
                  <button ref={inspectorToggle} type="button" className={`btn btn--sm btn--quiet${inspectorOpen ? " is-on" : ""}`} aria-expanded={inspectorOpen} onClick={() => setInspectorOpen((v) => !v)}>
                    {/* The sheet shows the icon and the count; the name stays whole for assistive technology. */}
                    <Icon name="inspector" size={14} /><span className="arthead__label">Připravenost a pomoc</span>{blocked ? <span>{` · ${blocked}`}</span> : null}
                  </button>
                  <button type="button" className={`iconbtn${mode === "artifact" ? " is-on" : ""}`} aria-pressed={mode === "artifact"} title={mode === "artifact" ? "Zpět na 40 / 60" : "Soustředit se na artefakt"} aria-label={mode === "artifact" ? "Zpět na 40 / 60" : "Soustředit se na artefakt"} onClick={() => setMode((m) => (m === "artifact" ? "split" : "artifact"))}>
                    <Icon name={mode === "artifact" ? "normal" : "focusArtifact"} size={16} />
                  </button>
                </div>
              </div>
              {picking ? <div className="artbar artbar--op" role="status"><Icon name="at" size={13} /><div className="artbar__grow">Klikněte na otázku, oddíl nebo část zadání, o které chcete s Vedoucím mluvit. Esc zruší.</div></div> : null}
              {drawer.kind === "peek" ? (
                <div className="artbar artbar--op" role="status" data-peek>
                  <Mark size={13} /><div className="artbar__grow">Vedoucí ukazuje: {drawer.target.includes(":") ? targetLabel(drawer.target, state) : STAGES[drawer.target as WorkbenchStage]?.label ?? drawer.target}</div>
                  <button type="button" className="btn btn--sm btn--quiet" onClick={() => drawerEvent({ type: "back" })}>Zpět k Vedoucímu</button>
                </div>
              ) : null}
              {notice ? <div className="artbar artbar--stale" role="status"><Glyph tone="reopened" size={12} /><div className="artbar__grow">{notice}</div><button type="button" className="iconbtn" aria-label="Zavřít" onClick={() => setNotice(null)}><Icon name="close" size={14} /></button></div> : null}
              {autoHere.length ? <AutoBar items={autoHere} state={state} canEdit={frame.canEdit} onRevert={revert} onHide={() => autoStore.set((a) => a.filter((x) => editStage(x.edit) !== stage))} /> : null}
              {here.length ? <EditsBar items={here} state={state} marks={marks} canEdit={frame.canEdit} onAccept={(keys) => void decide("accept", keys)} onDismiss={(keys) => void decide("dismiss", keys)} /> : null}
              <div className="artstage">
                <div className="artbody" id="artbody"><div className="wb-stage">
                  {stage === "sample" ? <SampleView project={state.project} onOpen={go} /> : null}
                  {/* Sample shows Dimenze's screen hidden, so its readiness still reaches the inspector. */}
                  <div hidden={stage === "sample"}><LeadAskContext.Provider value={askLead}><ItemInspectorContext.Provider value={itemInspector}><FrameNavigation.Provider value={frameNav}>{children}</FrameNavigation.Provider></ItemInspectorContext.Provider></LeadAskContext.Provider></div>
                </div></div>
                {/* Mounted while empty, so closing it gives the focus back to what opened it. */}
                <div ref={itemDrawer} className="itemdrawer" hidden={!itemOpen}>
                  <ItemInspector ownEscape={false} stack={shownItems} onBack={() => setItems((s) => backEntry(onStage(s, stage)))} onClose={() => setItems((s) => closeStack(onStage(s, stage)))}>
                    {(entry) => itemBodies.get(entry.id)?.() ?? <ItemInspectBody entry={entry} />}
                  </ItemInspector>
                </div>
                <aside ref={inspectorPanel} tabIndex={-1} className="insp" aria-label="Připravenost a pomoc" hidden={!inspectorOpen}>
                  <div className="insp__head">
                    <div style={{ minWidth: 0, flex: 1 }}><div className="insp__title">Připravenost a pomoc</div><div className="insp__sub">{STAGES[stage].label}</div></div>
                    <button type="button" className="iconbtn" aria-label="Zavřít" title="Zavřít" onClick={() => { setInspectorOpen(false); inspectorToggle.current?.focus(); }}><Icon name="close" size={16} /></button>
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

function StudyHeader({ frame, study, pending, blocked, onPending, layout = "split", inert = false }: { frame: StudyFrame; study: Study | null; pending: number; blocked: number; onPending: () => void; layout?: WorkbenchLayout; inert?: boolean }) {
  // Under 768 px (the sheet) the bar keeps the study's name and the menu; what waits and the budget
  // move into the menu (research-lead-workbench 26d).
  const narrow = layout === "sheet";
  const router = useRouter();
  const [menu, setMenu] = useState(false);
  // A menu by the keyboard too (the UX audit, #753): opened on its first item, ↑ ↓ Home End move,
  // Esc or a press outside closes it and gives the focus back to its button. No scrim: a press
  // outside reaches what it was meant for. The items are read from the open menu, so the rows that
  // only inform (under 768 px) are never stopped on.
  const menuBox = useRef<HTMLDivElement>(null);
  const menuToggle = useRef<HTMLButtonElement>(null);
  const closeMenu = useCallback(() => setMenu(false), []);
  useDismiss(menu, closeMenu, menuBox, menuToggle);
  const menuItems = () => Array.from(menuBox.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
  // Which item takes the focus once the menu has rendered (an effect: after the commit).
  const focusOnOpen = useRef<"first" | "last" | null>(null);
  const openMenu = (where: "first" | "last") => {
    focusOnOpen.current = where;
    setMenu(true);
  };
  useEffect(() => {
    const where = focusOnOpen.current;
    focusOnOpen.current = null;
    if (!menu || !where) return;
    const items = Array.from(menuBox.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
    (where === "first" ? items[0] : items[items.length - 1])?.focus();
  }, [menu]);
  const onMenuKey = (e: ReactKeyboardEvent<HTMLElement>) => {
    if (e.key === "Tab") return setMenu(false);
    const items = menuItems();
    const next = rovingIndex(items.indexOf(e.target as HTMLElement), e.key, items.length, () => false, "vertical");
    if (next === null) return;
    e.preventDefault();
    items[next]?.focus();
  };
  // Leaving the study goes through a link's click too, so Návrh's leave guard can stop it.
  const leave = (url: string) => {
    setMenu(false);
    guardedNavigate(url, (u) => router.push(u));
  };
  const budget = study?.budget_usd ?? null;
  const spent = study?.spent_usd ?? null;
  const spentPct = budget && spent !== null ? Math.min(100, (spent / budget) * 100) : 0;
  return (
    <header className="shead" inert={inert}>
      <span className="shead__band" aria-hidden="true" />
      <button type="button" className="shead__home" onClick={() => leave(appRoutes.client(frame.clientId))} aria-label={`Klienti › ${frame.clientName}`}>
        <span className="shead__mono" aria-hidden="true">{initials(frame.clientName)}</span>
        <span className="shead__title"><span className="shead__client">Klienti › {frame.clientName}</span><span className="shead__study">{frame.studyName}</span></span>
      </button>
      {narrow ? null : <span className="shead__state"><Glyph tone={blocked ? "you" : "done"} size={11} />{blocked ? `Do spuštění zbývá ${blocked}` : "Návrh splňuje podmínky kroků"}</span>}
      <span className="shead__spacer" />
      {pending > 0 && !narrow ? <button type="button" className="shead__pending" onClick={onPending}><Glyph tone="you" size={11} />Čeká na vás: {pending}</button> : null}
      {narrow ? null : (
        <span className="budgetmini" title="Rozpočet studie: utraceno / limit">
          <Icon name="budget" size={13} />
          <span className="budgetmini__bar" aria-hidden="true"><i style={{ width: `${spentPct}%` }} /></span>
          <span className="num">{budget === null ? "Rozpočet nenastaven" : `${usd(spent)} / ${usd(budget)} USD`}</span>
        </span>
      )}
      <div ref={menuBox} style={{ position: "relative" }}>
        <button ref={menuToggle} type="button" className="iconbtn" aria-label="Nabídka" title="Nabídka" aria-haspopup="menu" aria-expanded={menu}
          onClick={() => (menu ? setMenu(false) : openMenu("first"))}
          onKeyDown={(e) => { if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); openMenu(e.key === "ArrowDown" ? "first" : "last"); } }}><Icon name="menu" size={16} /></button>
        {menu ? (
          <>
            <div className="pop menu" style={{ right: 0, top: 34, width: 280 }} role="menu" aria-label="Nabídka" onKeyDown={onMenuKey}>
              {narrow ? (
                <>
                  <div className="menu__info" role="none"><Glyph tone={blocked ? "you" : "done"} size={11} />{blocked ? `Do spuštění zbývá ${blocked}` : "Návrh splňuje podmínky kroků"}</div>
                  <div className="menu__info num" role="none"><Icon name="budget" size={13} />{budget === null ? "Rozpočet nenastaven" : `Rozpočet: ${usd(spent)} / ${usd(budget)} USD`}</div>
                  {pending > 0 ? <button type="button" role="menuitem" className="listbtn" onClick={() => { setMenu(false); onPending(); }}>Čeká na vás: {pending}</button> : null}
                </>
              ) : null}
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

function StageNav({ stage, lane, marks = {}, onOpen, layout = "split", inert = false }: { stage: WorkbenchStage; lane: Parameters<typeof stageState>[1]; marks?: Partial<Record<WorkbenchStage, ImpactMark>>; onOpen: (s: WorkbenchStage) => void; layout?: WorkbenchLayout; inert?: boolean }) {
  const nav = useRef<HTMLElement>(null);
  const [listOpen, setListOpen] = useState(false);
  // In the drawer layout the navigator scrolls sideways: the current stage is kept in view.
  useEffect(() => {
    if (layout !== "drawer") return;
    nav.current?.querySelector<HTMLElement>(".nav__stage.is-current")?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [stage, layout]);
  const onKey = (e: React.KeyboardEvent<HTMLElement>) => {
    if (e.key === "Escape" && listOpen) {
      e.preventDefault();
      setListOpen(false);
      nav.current?.querySelector<HTMLButtonElement>(".nav__current")?.focus();
      return;
    }
    const keys = ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"];
    if (!keys.includes(e.key)) return;
    const btns = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>(".nav__stage"));
    if (!btns.length) return;
    const i = btns.indexOf(document.activeElement as HTMLButtonElement);
    const forward = e.key === "ArrowRight" || e.key === "ArrowDown";
    const j = e.key === "Home" ? 0 : e.key === "End" ? btns.length - 1 : Math.max(0, Math.min(btns.length - 1, i + (forward ? 1 : -1)));
    btns[j]?.focus();
    e.preventDefault();
  };
  const stageButton = (s: WorkbenchStage) => {
    const k = stageState(s, lane);
    const cur = s === stage;
    const mark = marks[s];
    return (
      <button key={s} type="button" className={`nav__stage${cur ? " is-current" : ""}${k.tone === "inert" ? " is-inert" : ""}${k.tone === "you" ? " is-you" : ""}`}
        aria-current={cur ? "page" : undefined} title={`${STAGES[s].label}${k.line ? `: ${k.line}` : ""}${mark ? `; ${mark.words}` : ""}`}
        data-impact={mark?.impact} onClick={() => { setListOpen(false); onOpen(s); }}>
        <Glyph tone={STAGE_TONE[k.tone] ?? "inert"} size={11} />{layout === "sheet" ? STAGES[s].label : STAGES[s].short}{k.line ? <span className="sr-only">, {k.line}</span> : null}
        {mark ? <><span className={`nav__impact nav__impact--${mark.impact.toLowerCase()}`} aria-hidden="true" /><span className="sr-only">, {mark.words}</span></> : null}
      </button>
    );
  };
  const phases = PHASES.map((ph) => (
    <div className="nav__phase" key={ph.id} role="group" aria-label={ph.label}>
      <span className="nav__plabel">{ph.label}</span>
      {STAGE_ORDER.filter((s) => STAGES[s].phase === ph.id).map(stageButton)}
    </div>
  ));
  if (layout === "sheet") {
    // Under 768 px: one button names the current stage and opens every stage, grouped by phase.
    return (
      <nav className="nav nav--sheet" aria-label="Kroky studie" onKeyDown={onKey} ref={nav} inert={inert}>
        <button type="button" className="nav__current" aria-expanded={listOpen} aria-haspopup="true" onClick={() => setListOpen((v) => !v)}>
          <Glyph tone={STAGE_TONE[stageState(stage, lane).tone] ?? "inert"} size={11} />
          <span className="nav__currentlabel">Krok: {STAGES[stage].label}</span>
          <Icon name="down" size={14} />
        </button>
        {listOpen ? (
          <>
            <div className="scrim" onClick={() => setListOpen(false)} />
            <div className="pop nav__list">{phases}</div>
          </>
        ) : null}
      </nav>
    );
  }
  return (
    <nav className={`nav${layout === "drawer" ? " nav--scroll" : ""}`} aria-label="Kroky studie" onKeyDown={onKey} ref={nav} inert={inert}>
      {phases}
    </nav>
  );
}

/** The launcher's dot: shape carries the state (Glyph's grammar); unknown is never drawn as on. */
const AVAILABILITY_TONE: Record<LeadAvailability["kind"], GlyphTone> = { ON: "done", WAITING: "world", OFF: "blocked", UNKNOWN: "inert" };

/** The way to the conversation when it is not beside the artifact: the rail in artifact focus and
 * the drawer, a bottom bar under 768 px. A waiting change is announced in its name, since the
 * hidden conversation's live region is silent. */
function Rail({ ref, pending, availability, open = false, onOpen }: { ref?: Ref<HTMLButtonElement>; pending: number; availability: LeadAvailability; open?: boolean; onOpen: () => void }) {
  const name = `Otevřít konverzaci s Vedoucím výzkumu${pending > 0 ? `, čeká na vás ${pending}` : ""}. ${availabilityWords(availability)}`;
  return (
    <div className="rail">
      <button ref={ref} type="button" className="iconbtn rail__launch" aria-label={name} title={name} aria-expanded={open} aria-haspopup="dialog" onClick={onOpen} data-lead-launcher data-availability={availability.kind}>
        <Mark size={20} /><span className="rail__dot"><Glyph tone={AVAILABILITY_TONE[availability.kind]} size={10} /></span>
      </button>
      {pending > 0 ? <span className="rail__badge" title={`Čeká na vás: ${pending}`}>{pending}</span> : null}
    </div>
  );
}
