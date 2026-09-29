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

import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { t, tv } from "@/i18n/t";
import { CANCEL_CONFIRM, JobError, type JobUpdate } from "@/research/jobs";
import type { Template } from "@/research/model";
import { type StepKey, stepEyebrow } from "@/research/steps";
import { ResearchStore, loadResearch, newResearch } from "@/research/store";
import { appRoutes } from "@/lib/app-routes";
import { AppShell } from "../../aia/AppShell";
import { type Ask, AskDialog, Button, Toast } from "../ui";
import { JobPanel } from "./JobPanel";
import { ResearchRail } from "./ResearchRail";
import { SaveIndicator } from "./SaveIndicator";
import { StepPlaceholder } from "./StepPlaceholder";
import { ResearchContext, type RunJob } from "./context";
import { ACTIONS, ACTION_LABELS } from "@/lib/research-agent-jobs";
import { researchAgents, type ResearchAgentAction } from "@/lib/api";
import { useResearchAgents } from "./useResearchAgents";
import { type StudyFrame, useStudyFrame } from "./frame";
import { STEP_SCREENS } from "./steps";

type Loaded =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  | { kind: "awaiting_migration" }
  | { kind: "unrecoverable"; template: Template; canEdit: boolean }
  | { kind: "ready"; store: ResearchStore; template: Template; origin: string | null };

type Session = { studyId: string; loaded: Loaded; retry: () => void; startAgain: () => void; memory: Map<string, unknown> };
const SessionContext = createContext<Session | null>(null);

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The study's working content, loaded once and kept while the person stays in the study (its layout). */
export function ResearchSession({ studyId, children }: { studyId: string; children: ReactNode }) {
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });
  const [version, setVersion] = useState(0);
  const [memory] = useState(() => new Map<string, unknown>());

  useEffect(() => {
    let live = true;
    let store: ResearchStore | null = null;
    loadResearch(studyId).then(
      (r) => {
        if (!live) return;
        if (r.kind === "awaiting_migration") return setLoaded({ kind: "awaiting_migration" });
        if (r.kind === "unrecoverable") return setLoaded({ kind: "unrecoverable", template: r.template, canEdit: r.canEdit });
        const s = new ResearchStore(r.state, studyId);
        store = s;
        setLoaded({ kind: "ready", store: s, template: r.template, origin: r.origin });
      },
      (e: unknown) => live && setLoaded({ kind: "failed", message: message(e) }),
    );
    return () => {
      live = false;
      store?.dispose();
    };
  }, [studyId, version]);

  // Nothing survived in 18.6.6: a person who may edit starts again, explicitly,
  // from the template. The first save records it with the study (ADR 0018).
  const startAgain = useCallback(() => {
    setLoaded((l) => (l.kind === "unrecoverable" && l.canEdit ? { kind: "ready", store: new ResearchStore(newResearch(l.template), studyId), template: l.template, origin: null } : l));
  }, [studyId]);

  const value = useMemo(
    () => ({ studyId, loaded, retry: () => setVersion((v) => v + 1), startAgain, memory }),
    [studyId, loaded, startAgain, memory],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/** The AIA frame of one stage: client, study and stage in the breadcrumbs, the study's stages in its rail. */
function StageChrome({ frame, step, status, children }: { frame: StudyFrame; step: StepKey; status?: ReactNode; children: ReactNode }) {
  const eyebrow = stepEyebrow(step);
  return (
    <AppShell
      crumbs={[
        { label: t("aia.navClients"), href: appRoutes.clients() },
        { label: frame.clientName, href: appRoutes.client(frame.clientId) },
        { label: t("aia.study.crumbResearch"), href: appRoutes.area(frame.clientId, "research") },
        { label: frame.studyName, href: frame.stepHref("brief") },
        { label: t(`aia.stages.${step}`) },
      ]}
      title={t(`research.steps.${step}.0`)}
      sub={t(`research.steps.${step}.1`)}
      eyebrow={
        eyebrow.total ? (
          <span className="inline-flex items-center gap-2">
            {eyebrow.text}
            <span aria-hidden="true" className="inline-flex gap-0.5">
              {Array.from({ length: eyebrow.total }, (_, i) => (
                <i key={i} className={`block h-0.5 w-4 ${i < eyebrow.done ? "bg-signal" : "bg-border"}`} />
              ))}
            </span>
          </span>
        ) : (
          t("aia.kind.RESEARCH")
        )
      }
      status={status}
      aside={<ResearchRail stepHref={frame.stepHref} current={step} studyName={frame.studyName} />}
    >
      {frame.notice ? (
        <p role="alert" className="mb-4 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{frame.notice}</p>
      ) : null}
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

function Ready({ store, template, origin, memory, step, frame, reload }: {
  store: ResearchStore; template: Template; origin: string | null; memory: Map<string, unknown>; step: StepKey; frame: StudyFrame; reload: () => void;
}) {
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

  const agents = useResearchAgents(frame.studyId, store, setJob);
  const nativeRun = agents.run;

  // Every AI step of the research stages is an AIA research agent job (ADR 0016,
  // PR #63). Deep research has no agent yet (ADR 0017) and says so.
  const runJob: RunJob = useCallback(
    async (endpoint, payload, { title: jobTitle }) => {
      if (endpoint === "researchDeep") throw new JobError("Webový výzkum čeká na konfiguraci vyhledávací služby. Zadání zůstává uložené.", "error", null);
      try {
        return await nativeRun(ACTIONS[endpoint], payload, jobTitle);
      } catch (e) {
        if (e instanceof JobError && e.kind === "busy") setToast(e.message);
        throw e;
      }
    },
    [nativeRun],
  );

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

  const confirm = useCallback((m: string) => new Promise<boolean>((resolve) => setAsk({ kind: "confirm", message: m, resolve })), []);
  const prompt = useCallback(
    (m: string, initial = "") => new Promise<string | null>((resolve) => setAsk({ kind: "prompt", message: m, initial, resolve })),
    [],
  );
  const value = useMemo(
    () => ({ store, template, runJob, job, toast: setToast, confirm, prompt, memory, stepHref, frame }),
    [store, template, runJob, job, confirm, prompt, memory, stepHref, frame],
  );
  const askAgent = async (action: ResearchAgentAction, title: string) => {
    const instruction = action === "critique_design" ? "Zkontroluj současný návrh." : await prompt("Co chcete zjistit?");
    if (!instruction) return;
    try { await agents.run(action, { instruction }, title); }
    catch (e) { setToast(message(e)); }
  };
  const Screen = STEP_SCREENS[step];

  return (
    <ResearchContext.Provider value={value}>
      <StageChrome frame={frame} step={step} status={<SaveIndicator save={state.save} onRetry={() => void store.flush("retry").catch(() => {})} onReload={reload} />}>
        {origin ? <p role="status" data-content-origin="18.6.6" className="mb-4 max-w-3xl rounded-sm border border-border bg-surface-raised p-3 text-sm leading-6 text-ink">{origin}</p> : null}
        {Screen ? <Screen /> : <StepPlaceholder step={step} />}
        {frame.canEdit ? <section className="mt-6 flex flex-wrap gap-2 border-t border-border pt-4" aria-label="AI pomoc s výzkumem">
          <Button disabled={agents.busy} onClick={() => void askAgent("critique_design", "Kontrola návrhu")}>AI zkontroluje návrh</Button>
          <Button disabled={agents.busy} onClick={() => void askAgent("design_copilot", "Pomoc s návrhem")}>Zeptat se na návrh</Button>
          <Button disabled={agents.busy} onClick={() => void askAgent("answer_memory", "Klientské znalosti")}>Zeptat se na klientské znalosti</Button>
        </section> : null}
      {agents.notice ? <p role="status" className="my-3 text-sm text-ink-muted">{agents.notice}</p> : null}
      {agents.recent.some((j) => j.status === "COMPLETED") ? <section className="my-4 rounded-md border border-border p-4"><h2 className="font-semibold">Uložené návrhy AI</h2>
        {agents.recent.filter((j) => j.status === "COMPLETED").slice(0, 5).map((j) => <Button key={j.run_id} disabled={agents.busy} onClick={() => void agents.open(j)}>{ACTION_LABELS[j.action]} · {j.created_at ? new Date(j.created_at).toLocaleString("cs-CZ") : ""}</Button>)}
      </section> : null}
      </StageChrome>
      {job ? <JobPanel job={job} onCancel={onCancel} /> : null}
      {agents.dialog}
      <AskDialog ask={ask} onDone={() => setAsk(null)} />
      <Toast message={toast} />
    </ResearchContext.Provider>
  );
}
