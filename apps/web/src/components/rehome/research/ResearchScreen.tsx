"use client";

// One research study on one stage (ADR 0014 area A4, re-homed by ADR 0015). A
// ResearchSession loads the bootstrap and the study's working content into one
// ResearchStore and keeps it, with the page memory the classic interface keeps
// in globals (the audience preview, the model's dimension proposals), for as
// long as the person stays in the study: the /app/clients/<client>/research/<study>
// layout holds it, so moving between stages neither reloads nor drops a change
// still waiting to be saved. Which unit project holds the working content comes
// from the study's AIA binding (OI-58); a new study's first save binds it.
// ResearchScreen draws the stage in the AIA shell -- client, study and stage in
// the breadcrumbs, the study's stages in its own rail -- and a stage not yet
// rebuilt hands off to the classic interface, explicitly.

import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { classicHref } from "@/lib/interface-handoff";
import { t, tv } from "@/i18n/t";
import { type BootInfo, loadBoot } from "@/unit/boot";
import { CANCEL_CONFIRM, JobError, type JobUpdate, cancelJob, runJob as runUnitJob } from "@/unit/research/jobs";
import { activeProvider } from "@/unit/research/provider";
import { type StepKey, stepEyebrow } from "@/unit/research/steps";
import { type ResearchState, ResearchStore, loadResearch, newResearch } from "@/unit/research/store";
import { appRoutes } from "@/lib/app-routes";
import { AppShell } from "../../aia/AppShell";
import { type Ask, AskDialog, Button, ClassicLink, Toast } from "../ui";
import { JobPanel } from "./JobPanel";
import { ResearchRail } from "./ResearchRail";
import { SaveIndicator } from "./SaveIndicator";
import { StepPlaceholder } from "./StepPlaceholder";
import { ResearchContext, type RunJob } from "./context";
import { type StudyFrame, useStudyFrame } from "./frame";
import { STEP_SCREENS } from "./steps";

type Loaded =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  | { kind: "demo" | "simulation" }
  | { kind: "ready"; store: ResearchStore; boot: BootInfo };

type Session = { projectId: string | null; loaded: Loaded; retry: () => void; memory: Map<string, unknown> };
const SessionContext = createContext<Session | null>(null);

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The study's working content, loaded once and kept while the person stays in the study (its layout). */
export function ResearchSession({
  projectId,
  onIdAssigned,
  children,
}: {
  projectId: string | null;
  /** A new study's first save gave its working content an id: bind it (OI-58). */
  onIdAssigned?: (id: string) => void;
  children: ReactNode;
}) {
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });
  const [version, setVersion] = useState(0);
  const [memory] = useState(() => new Map<string, unknown>());
  // Read when a new project gets its id, not a dependency of the load: the load
  // is per project id only.
  const assignedRef = useRef(onIdAssigned);
  useEffect(() => {
    assignedRef.current = onIdAssigned;
  }, [onIdAssigned]);

  useEffect(() => {
    let live = true;
    let store: ResearchStore | null = null;
    loadBoot()
      .then(async (boot): Promise<{ boot: BootInfo; state: ResearchState } | { other: "demo" | "simulation" }> => {
        if (!projectId) return { boot, state: newResearch(boot) };
        const r = await loadResearch(projectId, boot);
        if (r.kind !== "research") return { other: r.kind };
        return { boot, state: r.state };
      })
      .then(
        (r) => {
          if (!live) return;
          if ("other" in r) return setLoaded({ kind: r.other });
          const s: ResearchStore = new ResearchStore(r.state, r.boot, {
            onIdAssigned: (id) => assignedRef.current?.(id),
          });
          store = s;
          setLoaded({ kind: "ready", store: s, boot: r.boot });
        },
        (e: unknown) => live && setLoaded({ kind: "failed", message: message(e) }),
      );
    return () => {
      live = false;
      store?.dispose();
    };
  }, [projectId, version]);

  const value = useMemo(() => ({ projectId, loaded, retry: () => setVersion((v) => v + 1), memory }), [projectId, loaded, memory]);
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

export function ResearchScreen({ projectId, step, frame: given }: { projectId: string | null; step: StepKey; frame?: StudyFrame }) {
  const session = useContext(SessionContext);
  const inherited = useStudyFrame();
  const frame = given ?? inherited;
  if (!frame) throw new Error("ResearchScreen outside a study frame");
  // Outside the study's layout (a test), the screen holds its own session.
  if (!session || session.projectId !== projectId) {
    return (
      <ResearchSession projectId={projectId} onIdAssigned={frame.onIdAssigned}>
        <ResearchScreen projectId={projectId} step={step} frame={frame} />
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
        ) : (
          <section className="max-w-2xl rounded-md border border-border bg-surface-raised p-6">
            <p className="text-sm">{loaded.kind === "demo" ? t("research.isDemo") : t("research.isSimulation")}</p>
            {projectId ? (
              <div className="mt-4">
                <ClassicLink href={classicHref({ open: projectId })} variant="primary">{t("research.openInClassic")}</ClassicLink>
              </div>
            ) : null}
          </section>
        )}
      </StageChrome>
    );
  }
  return <Ready store={loaded.store} boot={loaded.boot} memory={session.memory} step={step} frame={frame} />;
}

function Ready({ store, boot, memory, step, frame }: {
  store: ResearchStore; boot: BootInfo; memory: Map<string, unknown>; step: StepKey; frame: StudyFrame;
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

  const runJob: RunJob = useCallback(
    async (endpoint, payload, { title: jobTitle, warnMs = 45_000, model }) => {
      const s = store.get();
      const started = Date.now();
      let warned = false;
      let overHard = false;
      try {
        return await runUnitJob(endpoint, payload, {
          title: jobTitle,
          model,
          ctx: {
            projectId: s.projectId,
            revision: s.revision,
            provider: activeProvider(s.preferredProvider, s.project.run_policy?.provider, boot),
          },
          onUpdate: (u) => {
            setJob(u);
            // The classic job's two notices, once each: still working, and past the server's own time.
            if (!warned && Date.now() - started > warnMs) {
              warned = true;
              setToast(t("research.jobStillWorking"));
            }
            const hard = u.meta?.hardSeconds ?? 0;
            if (hard && !overHard && Date.now() - started > hard * 1000) {
              overHard = true;
              setToast(t("research.jobOverHardStop"));
            }
          },
        });
      } catch (e) {
        if (e instanceof JobError && e.kind === "busy") setToast(e.message);
        throw e;
      } finally {
        setJob(null);
      }
    },
    [store, boot],
  );

  const onCancel = (jobId: string) =>
    setAsk({
      kind: "confirm",
      message: CANCEL_CONFIRM,
      resolve: (ok) => {
        if (!ok) return;
        cancelJob(jobId).then(
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
    () => ({ store, boot, runJob, job, toast: setToast, confirm, prompt, memory, stepHref, frame }),
    [store, boot, runJob, job, confirm, prompt, memory, stepHref, frame],
  );
  const Screen = STEP_SCREENS[step];

  return (
    <ResearchContext.Provider value={value}>
      <StageChrome frame={frame} step={step} status={<SaveIndicator save={state.save} onRetry={() => void store.flush("retry").catch(() => {})} />}>
        {Screen ? <Screen /> : <StepPlaceholder projectId={state.projectId} step={step} />}
      </StageChrome>
      {job ? <JobPanel job={job} onCancel={onCancel} /> : null}
      <AskDialog ask={ask} onDone={() => setAsk(null)} />
      <Toast message={toast} />
    </ResearchContext.Provider>
  );
}
