"use client";

// One research of one client (ADR 0015). The /app/clients/<client>/research/<study>
// layout resolves the study through AIA's scope first -- 404 outside the caller's
// scope, and a study under the wrong client in the URL is "not here" too -- and
// only then loads the unit project its AIA binding names (OI-58). A new study's
// first save binds its working content; a person who may only read never starts it.

import { notFound, useRouter } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type StudyWorkspace, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { type StepKey, isStepKey, stepFromSlug } from "@/unit/research/steps";
import { ResearchScreen, ResearchSession } from "../rehome/research/ResearchScreen";
import { type StudyFrame, StudyFrameProvider, useStudyFrame } from "../rehome/research/frame";
import { AppShell } from "./AppShell";
import { useClient } from "./clients/ClientContext";
import { CARD, Loaded, NotFound } from "./states";
import { useResource } from "./useResource";

function Waiting({ children, name }: { children: ReactNode; name?: string }) {
  const { client } = useClient();
  return (
    <AppShell
      crumbs={[
        { label: t("aia.navClients"), href: appRoutes.clients() },
        { label: client.name, href: appRoutes.client(client.client_id) },
        { label: t("aia.study.crumbResearch"), href: appRoutes.area(client.client_id, "research") },
        { label: name ?? "…" },
      ]}
      title={name ?? t("aia.kind.RESEARCH")}
    >
      {children}
    </AppShell>
  );
}

function Frame({ w, children }: { w: StudyWorkspace; children: ReactNode }) {
  const { client } = useClient();
  const [notice, setNotice] = useState<string | null>(null);
  const studyId = w.study.study_id;
  const clientId = client.client_id;
  const canEdit = w.can_edit;
  const onIdAssigned = useCallback(
    (id: string) => {
      workspace.bind(studyId, id).then(
        () => setNotice(null),
        (e: unknown) => setNotice(tv("aia.study.bindFailed", { message: e instanceof Error ? e.message : String(e) })),
      );
    },
    [studyId],
  );
  const onStage = useCallback(
    (step: StepKey) => {
      if (canEdit) void workspace.recordStage(studyId, step).catch(() => {});
    },
    [studyId, canEdit],
  );
  const frame: StudyFrame = useMemo(
    () => ({
      clientId,
      clientName: client.name,
      studyId,
      studyName: w.study.name,
      unitProjectId: w.unit_project_id,
      lastStage: w.study.last_stage && isStepKey(w.study.last_stage) ? w.study.last_stage : null,
      canEdit,
      stepHref: (step: StepKey) => appRoutes.stage(clientId, studyId, step),
      onIdAssigned,
      onStage,
      notice,
    }),
    [clientId, client.name, studyId, w.study.name, w.unit_project_id, w.study.last_stage, canEdit, onIdAssigned, onStage, notice],
  );
  return (
    <StudyFrameProvider frame={frame}>
      <ResearchSession projectId={w.unit_project_id} onIdAssigned={onIdAssigned}>
        {children}
      </ResearchSession>
    </StudyFrameProvider>
  );
}

export function ResearchStudy({ studyId, children }: { studyId: string; children: ReactNode }) {
  const { client } = useClient();
  const [res, retry] = useResource(() => workspace.study(studyId), [studyId]);
  if (res.state !== "ready") {
    return (
      <Waiting>
        <Loaded res={res} retry={retry}>{() => null}</Loaded>
      </Waiting>
    );
  }
  const w = res.data;
  // The study must belong to the client in the URL, and be a research.
  if (w.study.client_id !== client.client_id || w.study.kind !== "RESEARCH") {
    return (
      <Waiting>
        <NotFound />
      </Waiting>
    );
  }
  if (!w.unit_project_id && !w.can_edit) {
    return (
      <Waiting name={w.study.name}>
        <section className={`${CARD} max-w-xl`}>
          <p className="text-sm">{t("aia.study.readOnly")}</p>
        </section>
      </Waiting>
    );
  }
  return <Frame w={w}>{children}</Frame>;
}

/** /research/<study>: continue where the study was left, else its brief. */
export function ResearchStudyEntry() {
  const frame = useStudyFrame();
  const router = useRouter();
  useEffect(() => {
    if (frame) router.replace(frame.stepHref(frame.lastStage ?? "brief"));
  }, [frame, router]);
  return null;
}

/** /research/<study>/<stage>: one stage, in the study's session. */
export function ResearchStage({ slug }: { slug: string }) {
  const frame = useStudyFrame();
  const step = stepFromSlug(slug);
  if (!step) notFound();
  if (!frame) return null;
  return <ResearchScreen projectId={frame.unitProjectId} step={step} frame={frame} />;
}
