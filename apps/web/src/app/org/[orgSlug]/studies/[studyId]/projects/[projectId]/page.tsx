import Link from "next/link";
import { t } from "@/i18n/t";
import { getImpact, getProject, getStudy, listClients, listEvents } from "@/lib/api/endpoints";
import { orNotFound } from "@/lib/api/page";
import { ApiErrorPanel } from "@/components/aia/ApiErrorPanel";
import { ImpactPreview } from "@/components/aia/ImpactPreview";
import { ScopeHeader } from "@/components/aia/ScopeHeader";
import { Unavailable } from "@/components/aia/Unavailable";
import { lifecycleLabel } from "@/lib/labels";
import { Panel, StatusChip } from "@/components/ui";
import { IMPACT_FIELDS, PROJECT_TYPES } from "@/design/lifecycle";
import { parseEnum } from "@/design/enums";
import { formatDateTime } from "@/design/format";

export const dynamic = "force-dynamic";

/**
 * A project's workflow state as the API reports it: every stage of its
 * lifecycle with status, waiting reason and quota reset, the project history,
 * and the edit-impact preview. Runs, steps, gates and approvals have no HTTP
 * route yet and are shown as unavailable (OI-27) — never as "none".
 *
 * Stage statuses are drawn without a viewer: the API does not yet say whether a
 * waiting stage is this viewer's to resolve (OI-11), so WAITING_CREDITS reads
 * "waiting on team / admin", never "waiting on you".
 */
export default async function ProjectPage({
  params,
  searchParams,
}: {
  params: Promise<{ orgSlug: string; studyId: string; projectId: string }>;
  searchParams: Promise<{ field?: string | string[] }>;
}) {
  const { orgSlug, studyId, projectId } = await params;
  const { field: rawField } = await searchParams;
  const field = parseEnum(IMPACT_FIELDS, Array.isArray(rawField) ? rawField[0] : rawField);

  const studyR = orNotFound(await getStudy(studyId));
  if (!studyR.ok) return <ApiErrorPanel error={studyR.error} />;
  const projectR = orNotFound(await getProject(studyId, projectId));
  if (!projectR.ok) return <ApiErrorPanel error={projectR.error} />;
  const study = studyR.data;
  const project = projectR.data;

  const [clients, events, impact] = await Promise.all([
    listClients(),
    listEvents(studyId, projectId),
    field ? getImpact(studyId, projectId, field) : Promise.resolve(null),
  ]);
  const client = clients.ok ? clients.data.find((c) => c.client_id === study.client_id) ?? null : null;
  const type = parseEnum(PROJECT_TYPES, project.project_type);
  const base = `/org/${orgSlug}/studies/${studyId}/projects/${projectId}`;

  return (
    <div className="space-y-4">
      <ScopeHeader
        client={client ? { ...client, href: `/org/${orgSlug}/clients/${client.client_id}` } : { client_id: study.client_id, name: study.client_id }}
        crumbs={[{ label: study.name, href: `/org/${orgSlug}/studies/${studyId}` }, { label: project.title }]}
      />
      <div>
        <h1 className="text-2xl font-semibold">{project.title}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          <span>{lifecycleLabel(project.project_type)}</span>
          <StatusChip kind="ProjectStatus" value={project.status} small />
          <span>{t("project.revision")} <span className="font-mono">{project.current_revision}</span></span>
          <span>· {t("project.provider")}: {project.provider_label}</span>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <Panel title={`${t("project.stages")} (${project.stages.length})`} flush>
          <ol className="divide-y divide-border">
            {project.stages.map((s) => {
              const reset = formatDateTime(s.quota_reset_at);
              const started = formatDateTime(s.started_at);
              const finished = formatDateTime(s.finished_at);
              const isCurrent = s.stage_type === project.current_stage;
              return (
                <li key={s.stage_type} data-stage={s.stage_type} aria-current={isCurrent ? "step" : undefined} className={`grid gap-1 px-4 py-2 text-sm sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center ${isCurrent ? "bg-surface-sunken" : ""}`}>
                  <div className="min-w-0">
                    <Link className="text-signal hover:underline" href={`${base}/stages/${s.stage_type}`}>
                      <span className="font-mono text-ink-muted">{String(s.ordinal + 1).padStart(2, "0")}</span> {s.label || s.stage_type}
                    </Link>
                    {isCurrent ? <span className="ml-2 text-xs font-semibold text-ink-muted">{t("project.currentStage")}</span> : null}
                    {s.waiting_reason || reset || started || finished ? (
                      <div className="text-xs text-ink-muted">
                        {s.waiting_reason ? <>{t("project.waitingReason")}: <span className="font-mono">{s.waiting_reason}</span> </> : null}
                        {reset ? <>· {t("project.quotaResetAt")}: {reset} </> : null}
                        {started ? <>· {t("project.started")}: {started} </> : null}
                        {finished ? <>· {t("project.finished")}: {finished}</> : null}
                      </div>
                    ) : null}
                  </div>
                  <StatusChip kind="StageStatus" value={s.status} small showAudience />
                </li>
              );
            })}
          </ol>
        </Panel>

        <div className="space-y-4">
          <Unavailable id="approvals" title={t("project.approvals")} />
          <Unavailable id="workflow-runs" title={t("project.runs")} />
        </div>
      </div>

      <ImpactPreview projectType={type} field={field} result={impact} />

      <Panel title={t("events.title")} flush>
        {!events.ok ? <div className="p-3"><ApiErrorPanel error={events.error} /></div> : events.data.length === 0 ? <p className="px-4 py-3 text-sm">{t("events.empty")}</p> : (
          <ol className="divide-y divide-border text-sm">
            {events.data.map((e) => (
              <li key={e.event_id} className="grid gap-x-3 px-4 py-2 sm:grid-cols-[max-content_max-content_minmax(0,1fr)]">
                <span className="tabular-nums text-ink-muted">{formatDateTime(e.created_at) ?? "—"}</span>
                <span className="font-mono text-xs text-ink-muted">{e.event_type} · r{e.revision}{e.stage_type ? ` · ${e.stage_type}` : ""}</span>
                <span>{e.message}</span>
              </li>
            ))}
          </ol>
        )}
      </Panel>
    </div>
  );
}
