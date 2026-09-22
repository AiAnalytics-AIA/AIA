import Link from "next/link";
import { t } from "@/i18n/t";
import { getProject, getStudy, listClients, listProjects } from "@/lib/api/endpoints";
import { orNotFound } from "@/lib/api/page";
import { ApiErrorPanel } from "@/components/aia/ApiErrorPanel";
import { ScopeHeader } from "@/components/aia/ScopeHeader";
import { StudyMoney } from "@/components/aia/StudyMoney";
import { Unavailable } from "@/components/aia/Unavailable";
import { lifecycleLabel, roleLabel } from "@/lib/labels";
import { Panel, StatusChip, Value } from "@/components/ui";
import { PROJECT_TYPES, stageLabel } from "@/design/lifecycle";
import { parseEnum } from "@/design/enums";

export const dynamic = "force-dynamic";

/** Study overview: status, the viewer's role, the budget where visible, and each project's live stage. */
export default async function StudyPage({ params }: { params: Promise<{ orgSlug: string; studyId: string }> }) {
  const { orgSlug, studyId } = await params;
  const studyR = orNotFound(await getStudy(studyId));
  if (!studyR.ok) return <ApiErrorPanel error={studyR.error} />;
  const study = studyR.data;

  const [clients, projects] = await Promise.all([listClients(), listProjects(studyId)]);
  const client = clients.ok ? clients.data.find((c) => c.client_id === study.client_id) ?? null : null;
  // The list route has no stage states; the detail route does. One call per project.
  const details = projects.ok ? await Promise.all(projects.data.items.map((p) => getProject(studyId, p.project_id))) : [];

  return (
    <div className="space-y-4">
      <ScopeHeader
        client={client ? { ...client, href: `/org/${orgSlug}/clients/${client.client_id}` } : { client_id: study.client_id, name: study.client_id }}
        crumbs={[{ label: study.name }]}
      />
      {!clients.ok ? <ApiErrorPanel error={clients.error} /> : null}
      <div>
        <h1 className="text-2xl font-semibold">{study.name}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          <StatusChip kind="StudyStatus" value={study.status} small />
          <span>{study.accepts_work ? t("study.acceptsWork") : t("study.acceptsWorkNo")}</span>
          <span>· {t("study.role")}: {roleLabel(study.your_role)}</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel title={t("study.budget")}>
          <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1 text-sm">
            <dt className="text-ink-muted">{t("study.budgetTotal")}</dt>
            <dd className="text-right"><StudyMoney value={study.budget_usd} /></dd>
            <dt className="text-ink-muted">{t("study.spent")}</dt>
            <dd className="text-right"><StudyMoney value={study.spent_usd} /></dd>
            <dt className="text-ink-muted">{t("study.remaining")}</dt>
            <dd className="text-right font-semibold"><StudyMoney value={study.remaining_usd} /></dd>
          </dl>
        </Panel>
        <Unavailable id="budget-reservations" title={t("study.reservations")} />
      </div>

      {!projects.ok ? <ApiErrorPanel error={projects.error} /> : (
        <Panel title={`${t("study.projects")} (${projects.data.page.total})`} flush>
          {projects.data.items.length === 0 ? <p className="px-4 py-3 text-sm">{t("study.noProjects")}</p> : (
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-sunken text-xs font-semibold text-ink-muted">
                <tr>
                  <th className="px-4 py-2">{t("study.columns.project")}</th>
                  <th className="px-4 py-2">{t("study.columns.lifecycle")}</th>
                  <th className="px-4 py-2">{t("study.columns.currentStage")}</th>
                  <th className="px-4 py-2">{t("study.columns.status")}</th>
                  <th className="px-4 py-2">{t("study.columns.revision")}</th>
                </tr>
              </thead>
              <tbody>
                {projects.data.items.map((p, i) => {
                  const d = details[i];
                  const current = d?.ok ? d.data.stages.find((s) => s.stage_type === p.current_stage) : undefined;
                  const type = parseEnum(PROJECT_TYPES, p.project_type);
                  return (
                    <tr key={p.project_id} className="border-t border-border align-top">
                      <td className="px-4 py-2 font-medium">
                        <Link className="text-signal hover:underline" href={`/org/${orgSlug}/studies/${studyId}/projects/${p.project_id}`}>{p.title}</Link>
                      </td>
                      <td className="px-4 py-2">{lifecycleLabel(p.project_type)}</td>
                      <td className="px-4 py-2">
                        <div>{current?.label || (type ? stageLabel(type, p.current_stage) : null) || p.current_stage}</div>
                        {current ? <StatusChip kind="StageStatus" value={current.status} small showAudience /> : <Value value={null} />}
                      </td>
                      <td className="px-4 py-2"><StatusChip kind="ProjectStatus" value={p.status} small /></td>
                      <td className="px-4 py-2 font-mono">{p.current_revision}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Panel>
      )}
    </div>
  );
}
