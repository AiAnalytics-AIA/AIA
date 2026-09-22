import { notFound } from "next/navigation";
import { t } from "@/i18n/t";
import { getProject } from "@/lib/api/endpoints";
import { orNotFound } from "@/lib/api/page";
import { ApiErrorPanel } from "@/components/aia/ApiErrorPanel";
import { FixtureNotice } from "@/components/aia/FixtureNotice";
import { ArtifactsPanel } from "@/components/aia/ArtifactsPanel";
import { DocEditor } from "@/components/aia/DocEditor";
import { StatusChip } from "@/components/ui";

export const dynamic = "force-dynamic";

/** One stage. Its status is real; its artifacts and the report draft are still fixtures (no HTTP route). */
export default async function StagePage({
  params,
}: {
  params: Promise<{ orgSlug: string; studyId: string; projectId: string; stageId: string }>;
}) {
  const { studyId, projectId, stageId } = await params;
  const r = orNotFound(await getProject(studyId, projectId));
  if (!r.ok) return <ApiErrorPanel error={r.error} />;
  const project = r.data;
  const stage = project.stages.find((s) => s.stage_type === stageId);
  if (!stage) notFound();
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="min-w-0 space-y-4">
        <div>
          <div className="text-sm text-ink-muted">{project.title}</div>
          <h1 className="text-2xl font-semibold">
            <span className="font-mono text-ink-muted">{String(stage.ordinal + 1).padStart(2, "0")}</span> {stage.label || stage.stage_type}
          </h1>
          <div className="flex items-center gap-2 text-sm text-ink-muted">{t("stage.status")}: <StatusChip kind="StageStatus" value={stage.status} showAudience /></div>
        </div>
        {stage.stage_type === "REPORT" ? (
          <>
            <FixtureNotice capability="report-draft" />
            <DocEditor studyId={studyId} />
          </>
        ) : null}
      </section>
      <aside className="space-y-4">
        <FixtureNotice capability="stage-artifacts" />
        <ArtifactsPanel projectId={projectId} />
      </aside>
    </div>
  );
}
