import { notFound } from "next/navigation";
import Link from "next/link";
import { t } from "@/i18n/t";
import { fixtureClient, fixtureProjects, fixtureStudy } from "@/fixtures";
import { FixtureNotice } from "@/components/aia/FixtureNotice";
import { lifecycleLabel, projectStatusLabel, roleLabel, stageStatusLabel, studyStatusLabel } from "@/lib/labels";
import { stageLabel, type ProjectType } from "@/design/lifecycle";

export default async function StudyPage({ params }: { params: Promise<{ orgSlug: string; studyId: string }> }) {
  const { orgSlug, studyId } = await params;
  const study = fixtureStudy(studyId);
  if (!study) notFound();
  const client = fixtureClient(study.client_id);
  const projects = fixtureProjects[studyId] ?? [];
  return (
    <div className="space-y-4">
      <div>
        <div className="text-sm text-zinc-600">{client?.name ?? study.client_id}</div>
        <h1 className="text-2xl font-semibold">{study.name}</h1>
        <div className="text-sm text-zinc-600">{studyStatusLabel(study.status)} · {roleLabel(study.your_role)}</div>
      </div>
      <FixtureNotice capability="study-projects" />
      <section className="rounded-md border border-zinc-200 bg-white">
        <h2 className="border-b border-zinc-200 px-4 py-2 text-sm font-semibold">{t("study.projects")}</h2>
        {projects.length === 0 ? <p className="px-4 py-3 text-sm">{t("study.noProjects")}</p> : (
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-50 text-xs font-semibold text-zinc-600">
              <tr>
                <th className="px-4 py-2">{t("study.columns.project")}</th>
                <th className="px-4 py-2">{t("study.columns.lifecycle")}</th>
                <th className="px-4 py-2">{t("study.columns.currentStage")}</th>
                <th className="px-4 py-2">{t("study.columns.status")}</th>
                <th className="px-4 py-2">{t("study.columns.revision")}</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => {
                const current = p.stages.find((s) => s.stage_type === p.current_stage);
                return (
                  <tr key={p.project_id} className="border-t border-zinc-100">
                    <td className="px-4 py-2 font-medium">
                      <Link className="text-blue-700 hover:underline" href={`/org/${orgSlug}/studies/${studyId}/projects/${p.project_id}`}>{p.title}</Link>
                    </td>
                    <td className="px-4 py-2">{lifecycleLabel(p.project_type)}</td>
                    <td className="px-4 py-2">
                      {stageLabel(p.project_type as ProjectType, p.current_stage) ?? p.current_stage}
                      {current ? <span className="text-zinc-500"> · {stageStatusLabel(current.status)}</span> : null}
                    </td>
                    <td className="px-4 py-2">{projectStatusLabel(p.status)}</td>
                    <td className="px-4 py-2 font-mono">{p.current_revision}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
