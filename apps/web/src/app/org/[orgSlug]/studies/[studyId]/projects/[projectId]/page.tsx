import { notFound } from "next/navigation";
import Link from "next/link";
import { t } from "@/i18n/t";
import { fixtureProject } from "@/fixtures";
import { FixtureNotice } from "@/components/aia/FixtureNotice";
import { lifecycleLabel, projectStatusLabel, stageStatusLabel } from "@/lib/labels";

export default async function ProjectPage({ params }: { params: Promise<{ orgSlug: string; studyId: string; projectId: string }> }) {
  const { orgSlug, studyId, projectId } = await params;
  const project = fixtureProject(studyId, projectId);
  if (!project) notFound();
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">{project.title}</h1>
        <div className="text-sm text-zinc-600">
          {lifecycleLabel(project.project_type)} · {projectStatusLabel(project.status)} · {t("project.revision")} <span className="font-mono">{project.current_revision}</span>
        </div>
      </div>
      <FixtureNotice capability="project-stages" />
      <section className="rounded-md border border-zinc-200 bg-white">
        <h2 className="border-b border-zinc-200 px-4 py-2 text-sm font-semibold">{t("project.stages")}</h2>
        <ol className="divide-y divide-zinc-100">
          {project.stages.map((s) => (
            <li key={s.stage_type} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
              <Link className="text-blue-700 hover:underline" href={`/org/${orgSlug}/studies/${studyId}/projects/${projectId}/stages/${s.stage_type}`}>
                <span className="font-mono text-zinc-500">{String(s.ordinal + 1).padStart(2, "0")}</span> {s.label}
              </Link>
              <span>
                {stageStatusLabel(s.status)}
                {s.waiting_reason ? <span className="text-zinc-500"> · {t("project.waitingReason")}: {s.waiting_reason}</span> : null}
              </span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
