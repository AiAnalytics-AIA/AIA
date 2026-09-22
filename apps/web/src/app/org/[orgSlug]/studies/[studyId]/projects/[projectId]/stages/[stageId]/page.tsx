import { notFound } from "next/navigation";
import { t } from "@/i18n/t";
import { fixtureProject } from "@/fixtures";
import { FixtureNotice } from "@/components/aia/FixtureNotice";
import { ArtifactsPanel } from "@/components/aia/ArtifactsPanel";
import { DocEditor } from "@/components/aia/DocEditor";
import { stageStatusLabel } from "@/lib/labels";

export default async function StagePage({
  params,
}: {
  params: Promise<{ orgSlug: string; studyId: string; projectId: string; stageId: string }>;
}) {
  const { studyId, projectId, stageId } = await params;
  const project = fixtureProject(studyId, projectId);
  const stage = project?.stages.find((s) => s.stage_type === stageId);
  if (!project || !stage) notFound();
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <section className="space-y-4">
        <div>
          <div className="text-sm text-zinc-600">{project.title}</div>
          <h1 className="text-2xl font-semibold">
            <span className="font-mono text-zinc-500">{String(stage.ordinal + 1).padStart(2, "0")}</span> {stage.label}
          </h1>
          <div className="text-sm text-zinc-600">{t("stage.status")}: {stageStatusLabel(stage.status)}</div>
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
