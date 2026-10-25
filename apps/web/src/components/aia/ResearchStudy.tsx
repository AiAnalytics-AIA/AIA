"use client";

// One research of one client (ADR 0015). The /app/clients/<client>/research/<study>
// layout resolves the study through AIA's scope first -- 404 outside the caller's
// scope, and a study under the wrong client in the URL is "not here" too -- and
// then loads its working content from AIA by the study alone (ADR 0018). A person
// who may only read never starts a study's content.

import { notFound, useRouter, useSelectedLayoutSegment } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { t } from "@/i18n/t";
import { type StudyWorkspace, type WorkingContent, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { type StepKey, isStepKey, stepFromSlug } from "@/research/steps";
import { ClosedStudyNotice, ResearchScreen, ResearchSession } from "../rehome/research/ResearchScreen";
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
      client={{ id: client.client_id, name: client.name }}
    >
      {children}
    </AppShell>
  );
}

function Frame({ w: first, content, children }: { w: StudyWorkspace; content?: WorkingContent; children: ReactNode }) {
  const { client } = useClient();
  // The study as last read: a status changed on the study reads it again here, in place, so what
  // it allows (can_edit, closed) follows without the stage or its unsaved state remounting.
  const [w, setW] = useState(first);
  const studyId = w.study.study_id;
  const refreshStudy = useCallback(async () => { setW(await workspace.study(studyId)); }, [studyId]);
  const clientId = client.client_id;
  const canEdit = w.can_edit;
  const canReview = w.can_review;
  const closedStatus = w.study.accepts_work ? null : w.study.status;
  const deliveredAt = w.study.delivered_at ?? null;
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
      lastStage: w.study.last_stage && isStepKey(w.study.last_stage) ? w.study.last_stage : null,
      canEdit,
      canReview,
      closed: closedStatus ? { status: closedStatus, deliveredAt } : null,
      status: w.study.status,
      refreshStudy,
      stepHref: (step: StepKey) => appRoutes.stage(clientId, studyId, step),
      onStage,
    }),
    [clientId, client.name, studyId, w.study.name, w.study.last_stage, w.study.status, canEdit, canReview, closedStatus, deliveredAt, onStage, refreshStudy],
  );
  return (
    <StudyFrameProvider frame={frame}>
      <ResearchSession studyId={studyId} initialContent={content} canEdit={canEdit}>
        <ResearchStages />
        {children}
      </ResearchSession>
    </StudyFrameProvider>
  );
}

export function ResearchStudy({ studyId, children }: { studyId: string; children: ReactNode }) {
  const { client } = useClient();
  const [res, retry] = useResource(async () => {
    const w = await workspace.study(studyId);
    // Start the editor read directly after scope/relationship checks, without
    // waiting for another component mount. Wrong-client and empty read-only
    // workspaces never request working content.
    const permitted = w.study.client_id === client.client_id && w.study.kind === "RESEARCH" && !(w.content_state === "EMPTY" && !w.can_edit);
    return { w, content: permitted ? await workspace.content(studyId) : undefined };
  }, [studyId, client.client_id]);
  if (res.state !== "ready") {
    return (
      <Waiting>
        <Loaded res={res} retry={retry}>{() => null}</Loaded>
      </Waiting>
    );
  }
  const { w, content } = res.data;
  // The study must belong to the client in the URL, and be a research.
  if (w.study.client_id !== client.client_id || w.study.kind !== "RESEARCH") {
    return (
      <Waiting>
        <NotFound />
      </Waiting>
    );
  }
  if (w.content_state === "EMPTY" && !w.can_edit) {
    // Nothing was ever written, and nothing may be now: a closed study says why.
    return (
      <Waiting name={w.study.name}>
        {w.study.accepts_work ? (
          <section className={`${CARD} max-w-xl`}>
            <p className="text-sm">{t("aia.study.readOnly")}</p>
          </section>
        ) : (
          <ClosedStudyNotice closed={{ status: w.study.status, deliveredAt: w.study.delivered_at ?? null }} studyId={w.study.study_id} onChanged={retry} />
        )}
      </Waiting>
    );
  }
  return <Frame w={w} content={content}>{children}</Frame>;
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

/**
 * The study's stages, drawn in its layout (research-lead-workbench 34): the stage is read from the
 * address one level below it, so a stage change re-renders this one screen with another step and
 * swaps only the stage's body. The Lead's conversation, the split, the header and the navigator stay
 * mounted, with the study's reads; a page per stage remounted them all on every click.
 */
export function ResearchStages() {
  const segment = useSelectedLayoutSegment();
  const frame = useStudyFrame();
  const step = segment ? stepFromSlug(decodeURIComponent(segment)) : null;
  if (!step || !frame) return null;
  return <ResearchScreen step={step} frame={frame} />;
}

/** /research/<study>/<stage>: the address of a stage, drawn by ResearchStages; one that names none is not found. */
export function ResearchStage({ slug }: { slug: string }) {
  if (!stepFromSlug(slug)) notFound();
  return null;
}
