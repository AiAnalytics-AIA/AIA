"use client";

// One research project on one step (ADR 0014, area A4). A ResearchSession
// loads the bootstrap and the project into one ResearchStore and keeps it, with
// the page memory the classic interface keeps in globals (the audience preview,
// the model's dimension proposals), for as long as the person stays in the
// project: the /app/research/<id> layout holds it, so moving between steps
// neither reloads the project nor drops a change still waiting to be saved.
// ResearchScreen draws the step in the shell with the project's steps in the
// rail; a step not yet rebuilt hands off to the classic interface.

import { useRouter } from "next/navigation";
import { type ReactNode, createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { classicHref } from "@/lib/interface-handoff";
import { t, tv } from "@/i18n/t";
import { type BootInfo, loadBoot } from "@/unit/boot";
import { CANCEL_CONFIRM, JobError, type JobUpdate, cancelJob, runJob as runUnitJob } from "@/unit/research/jobs";
import { activeProvider } from "@/unit/research/provider";
import { type StepKey, stepEyebrow } from "@/unit/research/steps";
import { type ResearchState, ResearchStore, loadResearch, newResearch } from "@/unit/research/store";
import { Shell } from "../Shell";
import { type Ask, AskDialog, Button, ClassicLink, Toast } from "../ui";
import { JobPanel } from "./JobPanel";
import { ResearchRail } from "./ResearchRail";
import { SaveIndicator } from "./SaveIndicator";
import { StepPlaceholder } from "./StepPlaceholder";
import { ResearchContext, type RunJob } from "./context";
import { STEP_SCREENS } from "./steps";

type Loaded =
  | { kind: "loading" }
  | { kind: "failed"; message: string }
  | { kind: "demo" | "simulation" }
  | { kind: "ready"; store: ResearchStore; boot: BootInfo };

type Session = { projectId: string | null; loaded: Loaded; retry: () => void; memory: Map<string, unknown> };
const SessionContext = createContext<Session | null>(null);

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/**
 * A new project's live store, handed from /app/research/new to the session of
 * the id it was just given, so the new route adopts it instead of loading a
 * copy that a change typed during the first save would be missing.
 */
const handedOver = new Map<string, { store: ResearchStore; boot: BootInfo; memory: Map<string, unknown> }>();

/** The project, loaded once and kept while the person stays in it (the [projectId] layout). */
export function ResearchSession({ projectId, children }: { projectId: string | null; children: ReactNode }) {
  const router = useRouter();
  const [loaded, setLoaded] = useState<Loaded>({ kind: "loading" });
  const [version, setVersion] = useState(0);
  const [memory, setMemory] = useState(() => new Map<string, unknown>());
  // Read when a new project gets its id, not dependencies of the load: the load
  // is per project id only, whatever the router object or the path is.
  const routerRef = useRef(router);
  const memoryRef = useRef(memory);
  useEffect(() => {
    routerRef.current = router;
    memoryRef.current = memory;
  }, [router, memory]);

  useEffect(() => {
    let live = true;
    let store: ResearchStore | null = null;
    let adopted = false;
    const taken = projectId ? handedOver.get(projectId) : undefined;
    if (taken && projectId) {
      handedOver.delete(projectId);
      store = taken.store;
      queueMicrotask(() => {
        if (!live) return;
        setMemory(taken.memory);
        setLoaded({ kind: "ready", store: taken.store, boot: taken.boot });
      });
    } else {
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
              onIdAssigned: (id) => {
                adopted = true;
                handedOver.set(id, { store: s, boot: r.boot, memory: memoryRef.current });
                const step = window.location.pathname.split("/").pop() || "brief";
                routerRef.current.replace(`/app/research/${encodeURIComponent(id)}/${step === "new" ? "brief" : step}`);
              },
            });
            store = s;
            setLoaded({ kind: "ready", store: s, boot: r.boot });
          },
          (e: unknown) => live && setLoaded({ kind: "failed", message: message(e) }),
        );
    }
    return () => {
      live = false;
      // A store handed to the new route is not this session's to close.
      if (!adopted) store?.dispose();
    };
  }, [projectId, version]);

  const value = useMemo(() => ({ projectId, loaded, retry: () => setVersion((v) => v + 1), memory }), [projectId, loaded, memory]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function ResearchScreen({ projectId, step }: { projectId: string | null; step: StepKey }) {
  const session = useContext(SessionContext);
  // Outside the project's layout (the new-project page, a test), the screen holds its own session.
  if (!session || session.projectId !== projectId) {
    return (
      <ResearchSession projectId={projectId}>
        <ResearchScreen projectId={projectId} step={step} />
      </ResearchSession>
    );
  }
  const { loaded } = session;
  const [title, sub] = [t(`research.steps.${step}.0`), t(`research.steps.${step}.1`)];

  if (loaded.kind !== "ready") {
    return (
      <Shell title={title} sub={sub} eyebrow={stepEyebrow(step).text}>
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
      </Shell>
    );
  }
  return <Ready store={loaded.store} boot={loaded.boot} memory={session.memory} step={step} title={title} sub={sub} />;
}

function Ready({ store, boot, memory, step, title, sub }: {
  store: ResearchStore; boot: BootInfo; memory: Map<string, unknown>; step: StepKey; title: string; sub: string;
}) {
  const state = useSyncExternalStore(store.subscribe, store.get, store.get);
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
    () => ({ store, boot, runJob, job, toast: setToast, confirm, prompt, memory }),
    [store, boot, runJob, job, confirm, prompt, memory],
  );
  const Screen = STEP_SCREENS[step];
  const eyebrow = stepEyebrow(step);

  return (
    <ResearchContext.Provider value={value}>
      <Shell
        title={title}
        sub={sub}
        eyebrow={
          <span className="inline-flex items-center gap-2">
            {eyebrow.text}
            {eyebrow.total ? (
              <span aria-hidden="true" className="inline-flex gap-0.5">
                {Array.from({ length: eyebrow.total }, (_, i) => (
                  <i key={i} className={`block h-0.5 w-4 ${i < eyebrow.done ? "bg-signal" : "bg-border"}`} />
                ))}
              </span>
            ) : null}
          </span>
        }
        context={<ResearchRail projectId={state.projectId} current={step} />}
        actions={<SaveIndicator save={state.save} onRetry={() => void store.flush("retry").catch(() => {})} />}
      >
        {Screen ? <Screen /> : <StepPlaceholder projectId={state.projectId} step={step} />}
      </Shell>
      {job ? <JobPanel job={job} onCancel={onCancel} /> : null}
      <AskDialog ask={ask} onDone={() => setAsk(null)} />
      <Toast message={toast} />
    </ResearchContext.Provider>
  );
}
