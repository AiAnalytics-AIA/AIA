"use client";

// One research study on one stage (ADR 0014 area A4, re-homed by ADR 0015). A
// ResearchSession loads the study's working content from AIA (ADR 0018) into one
// ResearchStore and keeps it, with the page memory the classic interface keeps in
// globals (the audience preview, the model's dimension proposals), for as long as
// the person stays in the study: the /app/clients/<client>/research/<study> layout
// holds it, so moving between stages neither reloads nor drops a change still
// waiting to be saved. A study whose content still waits in 18.6.6, or was lost
// there, says so instead of showing an empty document. ResearchScreen draws the
// stage in the AIA shell -- client, study and stage in the breadcrumbs, the
// study's stages in its own rail -- and a stage AIA has not rebuilt says so.

import { type ReactNode, createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { t, tv } from "@/i18n/t";
import { CANCEL_CONFIRM, JobError, type JobUpdate } from "@/research/jobs";
import type { Template } from "@/research/model";
import { RAIL_STEPS, type StepKey } from "@/research/steps";
import { type ResearchState, ResearchStore, loadResearch, newResearch, readWorkingContent } from "@/research/store";
import { appRoutes } from "@/lib/app-routes";
import { AppShell } from "../../aia/AppShell";
import { type Ask, AskDialog, Button, Toast } from "../ui";
import { JobPanel } from "./JobPanel";
import { StageTrack, TRACK_STEPS } from "./StageTrack";
import { Blockers, InspectorProvider, ReadOnly } from "./Inspector";
import { ProposalReview } from "./ProposalReview";
import { SaveIndicator } from "./SaveIndicator";
import { StepPlaceholder } from "./StepPlaceholder";
import { ResearchContext, type RunJob, type SpendAsk } from "./context";
import { ACTIONS, ACTION_LABELS } from "@/lib/research-agent-jobs";
import { researchAgents, type ResearchAgentAction, type ResearchAgentJob, type WorkingContent } from "@/lib/api";
import { known } from "@/lib/reason-words";
import { AgentBudgetWaits } from "./AgentBudgetWaits";
import { useResearchAgents } from "./useResearchAgents";
import { type StudyFrame, useStudyFrame } from "./frame";
import { DesignSourceNote } from "./DesignSourceNote";
import { ReopenStudy, StudyStatusMenu } from "./StudyStatus";
import { STEP_SCREENS } from "./steps";
import { ResearchAssistance, isAdviceAction } from "./ResearchAssistance";
import { OPEN_REVIEW_KEY, Workbench } from "../../workbench/Workbench";
import { leadOwnsAiStarts } from "@/lib/lead-cards";
import { loadConfig } from "@/lib/auth";
import { SpendDialog } from "../../ui/SpendDialog";
import { readBudget } from "@/lib/budget-line";
import { type MoneyLine, spendAct } from "@/lib/spend";

// Contextual help keeps the same stage/action contract and native job boundaries.
const AI_HELP: { action: ResearchAgentAction; label: string; title: string; rail: readonly number[] | "all" }[] = [
  { action: "critique_design", label: "research.aiCritique", title: "Kontrola návrhu", rail: [2, 3, 4, 5, 6] },
  { action: "design_copilot", label: "research.aiCopilot", title: "Pomoc s návrhem", rail: [2, 3, 4, 5] },
  { action: "answer_memory", label: "research.aiMemory", title: "Klientské znalosti", rail: "all" },
];

export function aiHelpFor(step: StepKey) {
  // Průběh is Kontrola & spuštění's run, drawn on its rail entry.
  const n = RAIL_STEPS.findIndex((s) => s.key === (step === "progress" ? "run" : step)) + 1;
  return AI_HELP.filter((a) => a.rail === "all" || a.rail.includes(n));
}

type Loaded =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  | { kind: "awaiting_migration" }
  | { kind: "unrecoverable"; template: Template; canEdit: boolean }
  /** `forCanEdit`: what the study allowed (the session's `canEdit`) when this store was built. */
  | { kind: "ready"; store: ResearchStore; template: Template; origin: string | null; forCanEdit?: boolean };

type Session = { studyId: string; loaded: Loaded; retry: () => void; startAgain: () => void; memory: Map<string, unknown>; lost: string | null };
const SessionContext = createContext<Session | null>(null);

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
/** A design proposal a person has still to decide, as the server projects it (ADR 0026 decision 8). */
const pendingProposal = (j: ResearchAgentJob) => j.status === "COMPLETED" && !isAdviceAction(j.action) && j.proposal_state === "pending";

type StoreSwitches = { itemIds: boolean; editOps: boolean };

/** The store's switches once read (/config's stableItemIds, WCE1; editOps, WCE3a); null until then. */
let switchesKnown: StoreSwitches | null = null;

/** Whether the store keeps stable item ids and saves edits as operations: each off when the config cannot be read. */
function storeSwitches(): Promise<StoreSwitches> {
  if (switchesKnown !== null) return Promise.resolve(switchesKnown);
  return loadConfig().then(
    (c) => (switchesKnown = { itemIds: c.stableItemIds === true, editOps: c.editOps === true }),
    () => ({ itemIds: false, editOps: false }),
  );
}

/** The study's working content, loaded once and kept while the person stays in the study (its layout). */
export function ResearchSession({ studyId, initialContent, canEdit, children }: { studyId: string; initialContent?: WorkingContent; canEdit?: boolean; children: ReactNode }) {
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });
  const [version, setVersion] = useState(0);
  const [memory] = useState(() => new Map<string, unknown>());
  // A change the store being replaced could not save (the study closed under it): said, never dropped.
  const [lost, setLost] = useState<string | null>(null);
  // The store is built read-only or not from what the study allowed when it loaded. A status changed
  // on the study (reopened, closed) changes that: the content is read again and the store rebuilt, so
  // a reopened study takes edits and a closed one refuses them at the field, never silently (#892).
  const editable = useRef(canEdit);
  useEffect(() => {
    if (canEdit === undefined || editable.current === canEdit) return;
    editable.current = canEdit;
    setVersion((v) => v + 1);
  }, [canEdit]);

  useEffect(() => {
    let live = true;
    let store: ResearchStore | null = null;
    // Stable item ids (WCE1) and edits saved as operations (WCE3a) only behind their switches; a config that cannot be read is off.
    storeSwitches().then(({ itemIds, editOps }) =>
      (version === 0 && initialContent ? Promise.resolve(readWorkingContent(initialContent, { itemIds })) : loadResearch(studyId, undefined, { itemIds })).then((r) => ({ r, itemIds, editOps })),
    ).then(
      ({ r, itemIds, editOps }) => {
        if (!live) return;
        if (r.kind === "awaiting_migration") return setLoaded({ kind: "awaiting_migration" });
        if (r.kind === "unrecoverable") return setLoaded({ kind: "unrecoverable", template: r.template, canEdit: r.canEdit });
        // Read-only when the content says so or the study does: never a store that takes edits the
        // study refuses, nor one the screen would show enabled while it drops them.
        const s = new ResearchStore(r.state, studyId, { readOnly: !r.canEdit || editable.current === false, itemIds, editOps });
        store = s;
        setLoaded({ kind: "ready", store: s, template: r.template, origin: r.origin, forCanEdit: editable.current });
      },
      (e: unknown) => live && setLoaded({ kind: "failed", message: message(e) }),
    );
    return () => {
      live = false;
      store?.dispose((e) => setLost(message(e)));
    };
  }, [studyId, version, initialContent]);

  // Nothing survived in 18.6.6: a person who may edit starts again, explicitly,
  // from the template. The first save records it with the study (ADR 0018).
  const startAgain = useCallback(() => {
    setLoaded((l) => (l.kind === "unrecoverable" && l.canEdit ? { kind: "ready", store: new ResearchStore(newResearch(l.template), studyId, { itemIds: switchesKnown?.itemIds === true, editOps: switchesKnown?.editOps === true }), template: l.template, origin: null, forCanEdit: editable.current } : l));
  }, [studyId]);

  // A store built for what the study allowed before is not handed out: until the store for what it
  // allows now is in, the stages wait (loading), so no field is enabled over a store that drops its
  // edits, nor a read-only one shown over a store still taking them (Codex on #892).
  const value = useMemo(() => {
    const current: Loaded = loaded.kind === "ready" && canEdit !== undefined && loaded.forCanEdit !== canEdit ? { kind: "loading" } : loaded;
    return { studyId, loaded: current, retry: () => setVersion((v) => v + 1), startAgain, memory, lost };
  }, [studyId, loaded, canEdit, startAgain, memory, lost]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/** A change the replaced store could not save when the study's status changed under it. */
function LostEdit() {
  const lost = useContext(SessionContext)?.lost;
  return lost ? <p role="alert" data-lost-edit className="mb-4 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{tv("aia.study.status.lost", { reason: lost })}</p> : null;
}

/** The stages a person edits the design on: read-only, as one, when the study may not change. */
const DESIGN_STEPS: ReadonlySet<StepKey> = new Set<StepKey>(["brief", "plan", "questionnaire", "audience", "persona"]);

/**
 * A study that accepts no new work says so on every stage, once: what it is, what still works
 * and where it is reopened. Without it, a delivered study looked editable and every save was
 * refused as a role the person has (productization-coherence PC1).
 */
export function ClosedStudyNotice({ closed, studyId, onChanged, hold }: { closed: NonNullable<StudyFrame["closed"]>; studyId: string; onChanged?: () => Promise<void> | void; hold?: (on: boolean) => void }) {
  const when = closed.deliveredAt ? new Date(closed.deliveredAt).toLocaleDateString("cs-CZ") : null;
  const title =
    closed.status === "DELIVERED" && when
      ? tv("aia.study.closed.DELIVERED_on", { when })
      : known(`aia.study.closed.${closed.status}`) ?? t("aia.study.closed.other");
  return (
    <section role="status" data-study-closed={closed.status} className="mb-4 max-w-3xl rounded-sm border border-border-strong bg-surface-sunken p-3 text-sm leading-6 text-ink">
      <p className="font-semibold">{title}</p>
      <p>{t("aia.study.closed.help")}</p>
      {/* Reopened here, in place: the study is where its status is changed (F7). */}
      {onChanged ? <div className="mt-2"><ReopenStudy studyId={studyId} onChanged={onChanged} hold={hold} /></div> : null}
    </section>
  );
}

/** The AIA frame of one stage: client, study and stage in the breadcrumbs, the study's stages in its track. */
function StageChrome({ frame, step, state, status, help, flush, children }: {
  frame: StudyFrame; step: StepKey; state?: Pick<ResearchState, "project" | "analysis"> | null; status?: ReactNode; help?: ReactNode;
  /** Saves what is typed before the study's status changes (the store's flush). */
  flush?: () => Promise<unknown>; children: ReactNode;
}) {
  const onTrack = TRACK_STEPS.includes(step);
  // The track carries the order: a stage on it is named without its number.
  const title = t(`research.steps.${step}.0`);
  return (
    <AppShell
      crumbs={[
        { label: t("aia.navClients"), href: appRoutes.clients() },
        { label: frame.clientName, href: appRoutes.client(frame.clientId) },
        { label: t("aia.study.crumbResearch"), href: appRoutes.area(frame.clientId, "research") },
        { label: frame.studyName, href: frame.stepHref("brief") },
        { label: t(`aia.stages.${step}`) },
      ]}
      title={onTrack ? title.replace(/^\d+\.\s*/, "") : title}
      sub={t(`research.steps.${step}.1`)}
      client={{ id: frame.clientId, name: frame.clientName }}
      back={{ href: appRoutes.client(frame.clientId), label: t("aia.backToClient") }}
      eyebrow={onTrack ? undefined : t("aia.kind.RESEARCH")}
      status={status}
      action={frame.status && frame.refreshStudy ? <>{help}<StudyStatusMenu studyId={frame.studyId} status={frame.status} onChanged={frame.refreshStudy} beforeChange={flush} hold={frame.holdEdits} /></> : help}
      track={<StageTrack studyId={frame.studyId} state={state ?? null} current={step} stepHref={frame.stepHref} />}
    >
      {frame.notice ? (
        <p role="alert" className="mb-4 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{frame.notice}</p>
      ) : null}
      <LostEdit />
      {frame.closed ? <ClosedStudyNotice closed={frame.closed} studyId={frame.studyId} onChanged={frame.refreshStudy} hold={frame.holdEdits} /> : null}
      {children}
    </AppShell>
  );
}

export function ResearchScreen({ step, frame: given }: { step: StepKey; frame?: StudyFrame }) {
  const session = useContext(SessionContext);
  const inherited = useStudyFrame();
  const frame = given ?? inherited;
  if (!frame) throw new Error("ResearchScreen outside a study frame");
  // Outside the study's layout (a test), the screen holds its own session.
  if (!session || session.studyId !== frame.studyId) {
    return (
      <ResearchSession studyId={frame.studyId}>
        <ResearchScreen step={step} frame={frame} />
      </ResearchSession>
    );
  }
  const { loaded } = session;

  if (loaded.kind !== "ready") {
    return (
      <StageChrome frame={frame} step={step}>
        {loaded.kind === "loading" ? (
          <p className="py-10 text-sm text-ink-muted">{t("research.loading")}</p>
        ) : loaded.kind === "failed" ? (
          <section role="alert" className="rounded-md border border-status-fault/40 bg-status-fault-wash p-5">
            <h2 className="font-semibold text-status-fault">{t("research.loadFailed")}</h2>
            <p className="mt-1 text-sm text-ink">{loaded.message}</p>
            <Button className="mt-3" onClick={session.retry}>{t("research.retry")}</Button>
          </section>
        ) : loaded.kind === "awaiting_migration" ? (
          <section role="status" className="max-w-2xl rounded-md border border-status-you-ink/40 bg-status-you-wash p-6" data-content-state="AWAITING_MIGRATION">
            <h2 className="font-semibold">{t("research.awaitingMigration")}</h2>
            <p className="mt-1 text-sm leading-6 text-ink">{t("research.awaitingMigrationHelp")}</p>
          </section>
        ) : (
          <section role="status" className="max-w-2xl rounded-md border border-status-fault/40 bg-status-fault-wash p-6" data-content-state="UNRECOVERABLE">
            <h2 className="font-semibold text-status-fault">{t("research.unrecoverable")}</h2>
            <p className="mt-1 text-sm leading-6 text-ink">{t("research.unrecoverableHelp")}</p>
            {loaded.canEdit ? (
              <Button className="mt-3" variant="primary" onClick={session.startAgain}>{t("research.startAgain")}</Button>
            ) : (
              <p className="mt-2 text-sm text-ink-muted">{t("research.unrecoverableReadOnly")}</p>
            )}
          </section>
        )}
      </StageChrome>
    );
  }
  return <Ready store={loaded.store} template={loaded.template} origin={loaded.origin} memory={session.memory} step={step} frame={frame} reload={session.retry} />;
}

/** The workbench switch once read: later studies of the same page start with it, without a flash. */
let workbenchKnown: boolean | null = null;

/** Forgets the switch read, for a test that needs a fresh page. */
export function resetWorkbenchSwitch(): void {
  workbenchKnown = null;
}

/** The research workbench is on for this deployment (/config's workbench); null until read, so
 *  neither layout mounts and reads the study twice on a fresh page (the Dimenze audit, #798). No
 *  wait of its own: Ready mounts once the working copy is read, and every API read awaits the same
 *  cached /config (lib/api.ts), so it answers at once; a /config that fails serves classic. */
function useWorkbenchSwitch(): boolean | null {
  const [on, setOn] = useState<boolean | null>(workbenchKnown);
  useEffect(() => {
    let live = true;
    loadConfig().then(
      (c) => {
        workbenchKnown = c.workbench === true;
        if (live) setOn(workbenchKnown);
      },
      () => live && setOn(false),
    );
    return () => {
      live = false;
    };
  }, []);
  return on;
}

function Ready({ store, template, origin, memory, step, frame: given, reload }: {
  store: ResearchStore; template: Template; origin: string | null; memory: Map<string, unknown>; step: StepKey; frame: StudyFrame; reload: () => void;
}) {
  // The stages may edit only what the store that receives the edit takes: the study's permission and
  // the store's own editability, never the first alone.
  const frame = useMemo(() => (given.canEdit && !store.editable ? { ...given, canEdit: false } : given), [given, store]);
  const state = useSyncExternalStore(store.subscribe, store.get, store.get);
  const { onStage, stepHref } = frame;
  useEffect(() => {
    onStage?.(step);
  }, [onStage, step]);
  const [job, setJob] = useState<JobUpdate | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [ask, setAsk] = useState<Ask | null>(null);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(id);
  }, [toast]);

  const confirm = useCallback((m: string) => new Promise<boolean>((resolve) => setAsk({ kind: "confirm", message: m, resolve })), []);
  // Money asks in SpendDialog, with the study's budget read as it asks (design system v3, I-Penize).
  const [spend, setSpend] = useState<(SpendAsk & { lines: MoneyLine[]; key: number; resolve: (yes: boolean) => void }) | null>(null);
  const confirmSpend = useCallback(async (q: SpendAsk) => {
    const budget = await readBudget(frame.studyId);
    const lines: MoneyLine[] = [{ name: "study_budget", usd: budget?.budget_usd ?? null, remainingUsd: budget?.remaining_usd ?? null }];
    if (q.thresholdUsd !== undefined) lines.push({ name: "threshold", usd: q.thresholdUsd });
    return new Promise<boolean>((resolve) => setSpend({ ...q, lines, key: Date.now(), resolve }));
  }, [frame.studyId]);
  const answerSpend = (yes: boolean) => {
    spend?.resolve(yes);
    setSpend(null);
  };
  // A job reaching the study's confirmation threshold asks here first (LO15), in SpendDialog.
  const confirmJobCost = useCallback(
    (message: string, asked?: { ceiling: number; limit: number }) =>
      asked ? confirmSpend({ summary: t("input.spend.research.job"), ceilingUsd: asked.ceiling, thresholdUsd: asked.limit, act: t("input.spend.research.startJob") }) : confirm(message),
    [confirm, confirmSpend],
  );
  const agents = useResearchAgents(frame.studyId, store, setJob, true, true, confirmJobCost);
  const nativeRun = agents.run;

  // Design actions remain research agent jobs; Deep Research uses its own durable panel.
  const runJob: RunJob = useCallback(
    async (endpoint, payload, { title: jobTitle }) => {
      try {
        return await nativeRun(ACTIONS[endpoint], payload, jobTitle);
      } catch (e) {
        if (e instanceof JobError && e.kind === "busy") setToast(e.message);
        throw e;
      }
    },
    [nativeRun],
  );
  const nativeContinue = agents.continueJob;
  const continueJob = useCallback(
    async (jobId: string) => {
      try {
        return await nativeContinue(jobId);
      } catch (e) {
        if (e instanceof JobError && e.kind === "busy") setToast(e.message);
        throw e;
      }
    },
    [nativeContinue],
  );
  // One lift per waiting job (Codex on #533): a stage that shows a job's wait in place claims it,
  // and the screen's list of waiting jobs leaves that job out.
  const [claimed, setClaimed] = useState<readonly string[]>([]);
  const claimWait = useCallback((jobId: string) => {
    setClaimed((c) => [...c, jobId]);
    return () => setClaimed((c) => { const i = c.indexOf(jobId); return i < 0 ? c : [...c.slice(0, i), ...c.slice(i + 1)]; });
  }, []);
  // A wait lifted from the list goes on as the same job, its proposal opened like any other.
  const continueListed = useCallback((job: ResearchAgentJob) => {
    continueJob(job.run_id).catch((e: unknown) => { if (!(e instanceof JobError && e.kind === "busy")) setToast(message(e)); });
  }, [continueJob]);

  const onCancel = (jobId: string) =>
    setAsk({
      kind: "confirm",
      message: CANCEL_CONFIRM,
      resolve: (ok) => {
        if (!ok) return;
        researchAgents.cancel(frame.studyId, jobId).then(
          () => setToast(t("research.jobCancelling")),
          (e: unknown) => setToast(tv("research.jobCancelFailed", { message: message(e) })),
        );
      },
    });

  const prompt = useCallback(
    (m: string, initial = "") => new Promise<string | null>((resolve) => setAsk({ kind: "prompt", message: m, initial, resolve })),
    [],
  );
  const value = useMemo(
    () => ({ store, template, runJob, continueJob, claimWait, job, toast: setToast, confirm, confirmSpend, prompt, memory, stepHref, frame }),
    [store, template, runJob, continueJob, claimWait, job, confirm, confirmSpend, prompt, memory, stepHref, frame],
  );
  const Screen = STEP_SCREENS[step];
  const aiHelp = aiHelpFor(step);
  const workbench = useWorkbenchSwitch();
  // Another stage opens at the page's top in the classic layout, as its own page did: the stage's
  // page is empty now, and Next.js scrolls to no empty segment. The workbench resets its artifact.
  const scrolledFor = useRef(step);
  useLayoutEffect(() => {
    if (scrolledFor.current === step) return;
    scrolledFor.current = step;
    if (workbench !== true) window.scrollTo(0, 0);
  }, [step, workbench]);
  const onTrack = TRACK_STEPS.includes(step) && step !== "run" && step !== "progress" && step !== "results";
  // Stable across the editors' renders, so typing does not keep restarting the workbench's job poll.
  const refreshAgents = agents.refresh;
  const refreshJobs = useCallback(() => refreshAgents().catch(() => {}), [refreshAgents]);
  // The proposals a person has still to decide (ADR 0026 decision 8): an accepted, dismissed or
  // superseded one is not offered again.
  const savedProposals = agents.recent.filter(pendingProposal);
  // In the workbench every AI action goes through the Research Lead (D15): no AI pomoc, no stage
  // "Navrhnout", no job dialog -- each job is a card in the conversation. The workbench serves at
  // every width, the Lead beside the artifact or in a drawer over it (research-lead-workbench 26b,
  // D20, D21); only with the switch off does the classic layout, and its buttons, serve.
  const inWorkbench = workbench === true;
  const leadOwns = leadOwnsAiStarts(inWorkbench ? "workbench" : "classic");
  const starts = !leadOwns;
  // A card on another stage asked for this job's review: opened here once the jobs are read. The
  // job itself is kept, so one older than the newest page (the Lead's show_diff finds those through
  // ?pending=true) opens too; the page's copy is preferred when it holds one.
  const openAgent = agents.open;
  // The screen stays mounted from stage to stage (research-lead-workbench 34): a review left open on
  // the stage the person leaves is kept for later, as leaving the page kept it, never carried over
  // the next stage. Declared before the review a card asked the next stage for, which it opens.
  const review = agents.proposalReview ?? agents.adviceReview;
  const reviewedOn = useRef(step);
  useEffect(() => {
    if (reviewedOn.current === step) return;
    reviewedOn.current = step;
    review?.decide("keep");
  }, [step, review]);
  useEffect(() => {
    const wanted = memory.get(OPEN_REVIEW_KEY) as ResearchAgentJob | undefined;
    if (!wanted?.run_id || agents.busy) return;
    memory.delete(OPEN_REVIEW_KEY);
    void openAgent(agents.recent.find((j) => j.run_id === wanted.run_id) ?? wanted);
  }, [memory, agents.recent, agents.busy, openAgent, step]);

  // The layout is the switch's: mounting the classic one while it is unread would read and record
  // the stage twice, once for each layout. Until then the stage's chrome says it is loading.
  if (workbench === null) {
    return (
      <StageChrome frame={frame} step={step}>
        <p role="status" className="py-10 text-sm text-ink-muted">{t("research.loading")}</p>
      </StageChrome>
    );
  }
  return (
    <ResearchAssistance step={step} studyName={frame.studyName} canEdit={frame.canEdit} memory={memory} actions={aiHelp} agents={agents} job={job} onCancel={onCancel} studyId={frame.studyId} starts={starts}>
    {({ card, panel, expanded, ask: askAssistance }) => <ResearchContext.Provider value={{ ...value, leadOwnsAiStarts: leadOwns, askAssistance: leadOwns ? undefined : askAssistance }}>
      {inWorkbench ? (
        <InspectorProvider disabled={!frame.canEdit && DESIGN_STEPS.has(step)}>{(column) => (
          <Workbench frame={frame} step={step} store={store} memory={memory} reload={reload} confirm={confirm} onAgentStarted={() => void agents.refresh()}
            jobs={agents.recent} onOpenJob={(j) => void agents.open(j)} onRefreshJobs={refreshJobs}
            save={<SaveIndicator save={state.save} onRetry={() => void store.flush("retry").catch(() => {})} onReload={reload} />}
            inspector={column(<>
              {card}
              {onTrack ? <Blockers state={state} stepHref={stepHref} /> : null}
              {agents.notice ? <p role="status" className="text-sm text-ink-muted">{agents.notice}</p> : null}
              <AgentBudgetWaits jobs={agents.recent} studyId={frame.studyId} canEdit={frame.canEdit} onChanged={agents.refresh} exclude={claimed} onLifted={continueListed} />
              {savedProposals.length ? <section className="rounded-md border border-border p-3"><h2 className="mb-2 text-sm font-semibold">{t("research.aiSaved")}</h2>
                <div className="flex flex-wrap gap-2">
                  {savedProposals.slice(0, 5).map((j) => <Button key={j.run_id} disabled={agents.busy} onClick={() => void agents.open(j)}>{ACTION_LABELS[j.action]} · {j.created_at ? new Date(j.created_at).toLocaleString("cs-CZ") : ""}</Button>)}
                </div>
              </section> : null}
            </>)}>
            {frame.notice ? <p role="alert" className="mb-4 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{frame.notice}</p> : null}
            <LostEdit />
            {frame.closed ? <ClosedStudyNotice closed={frame.closed} studyId={frame.studyId} onChanged={frame.refreshStudy} hold={frame.holdEdits} /> : null}
            <DesignSourceNote clientId={frame.clientId} studyId={frame.studyId} />
            {origin ? <p role="status" data-content-origin="18.6.6" className="mb-4 max-w-3xl rounded-sm border border-border bg-surface-raised p-3 text-sm leading-6 text-ink">{origin}</p> : null}
            <div className="flex min-w-0 flex-col gap-4">
              {/* An advice answer opened from its card in the conversation: read here, never in a closed inspector. */}
              {panel}
              {agents.proposalReview ? <ProposalReview result={agents.proposalReview.result} action={agents.proposalReview.action} state={state} onDecision={agents.proposalReview.decide} canApply={frame.canEdit} stale={agents.proposalReview.stale} /> : null}
              <ReadOnly when={!frame.canEdit && DESIGN_STEPS.has(step)}>
                {Screen ? <Screen /> : <StepPlaceholder step={step} />}
              </ReadOnly>
            </div>
          </Workbench>
        )}</InspectorProvider>
      ) : (
      <StageChrome frame={frame} step={step} state={state} flush={() => store.flush()} status={<SaveIndicator save={state.save} onRetry={() => void store.flush("retry").catch(() => {})} onReload={reload} />}>
          <DesignSourceNote clientId={frame.clientId} studyId={frame.studyId} />
          {origin ? <p role="status" data-content-origin="18.6.6" className="mb-4 max-w-3xl rounded-sm border border-border bg-surface-raised p-3 text-sm leading-6 text-ink">{origin}</p> : null}
          <InspectorProvider disabled={!frame.canEdit && DESIGN_STEPS.has(step)}>{(column) => (
            <div data-research-workspace className="grid min-w-0 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,22rem)]">
              <div className="flex min-w-0 flex-col gap-4">
                {/* An AI proposal can be opened from the saved list on any stage: on a closed study it is
                    read and closed, never applied, whichever stage shows it. */}
                {agents.proposalReview ? <ProposalReview result={agents.proposalReview.result} action={agents.proposalReview.action} state={state} onDecision={agents.proposalReview.decide} canApply={frame.canEdit} stale={agents.proposalReview.stale} /> : null}
                {/* A design that may not change is read, never edited: every control of a design stage
                    is disabled as one (the run stages decide their own actions). */}
                <ReadOnly when={!frame.canEdit && DESIGN_STEPS.has(step)}>
                  {Screen ? <Screen /> : <StepPlaceholder step={step} />}
                </ReadOnly>
              </div>
              {column(<>
                {expanded ? panel : card}
                {TRACK_STEPS.includes(step) && step !== "run" && step !== "progress" && step !== "results" ? <Blockers state={state} stepHref={stepHref} /> : null}
              </>)}
              {expanded ? null : panel}
            </div>
          )}</InspectorProvider>
        {agents.notice ? <p role="status" className="my-3 text-sm text-ink-muted">{agents.notice}</p> : null}
        <AgentBudgetWaits jobs={agents.recent} studyId={frame.studyId} canEdit={frame.canEdit} onChanged={agents.refresh} exclude={claimed} onLifted={continueListed} />
        {savedProposals.length ? <section className="my-4 rounded-md border border-border p-4"><h2 className="mb-2 font-semibold">{t("research.aiSaved")}</h2>
          <div className="flex flex-wrap gap-2">
            {savedProposals.slice(0, 5).map((j) => <Button key={j.run_id} disabled={agents.busy} onClick={() => void agents.open(j)}>{ACTION_LABELS[j.action]} · {j.created_at ? new Date(j.created_at).toLocaleString("cs-CZ") : ""}</Button>)}
          </div>
        </section> : null}
        </StageChrome>
      )}
      {job && starts && !isAdviceAction(agents.activeAction) ? <JobPanel job={job} onCancel={onCancel} studyId={frame.studyId} /> : null}
      {agents.dialog}
      <AskDialog ask={ask} onDone={() => setAsk(null)} />
      <SpendDialog
        open={spend !== null}
        question={String(spend?.key ?? "")}
        kind="spend_confirm"
        summary={spend?.summary ?? ""}
        ceilingUsd={spend?.ceilingUsd ?? null}
        lines={spend?.lines ?? []}
        pays="study_budget"
        confirmLabel={spend ? spendAct(spend.act, spend.ceilingUsd) : ""}
        onConfirm={() => answerSpend(true)}
        onCancel={() => answerSpend(false)}
      />
      <Toast message={toast} />
    </ResearchContext.Provider>}
    </ResearchAssistance>
  );
}
