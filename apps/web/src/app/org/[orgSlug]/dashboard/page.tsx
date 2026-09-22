import Link from "next/link";
import { t } from "@/i18n/t";
import { getStudy, listClients, listProjects, listStudies } from "@/lib/api/endpoints";
import type { ClientResponse } from "@/lib/api/types";
import { ApiErrorPanel } from "@/components/aia/ApiErrorPanel";
import { ScopeHeader } from "@/components/aia/ScopeHeader";
import { Unavailable } from "@/components/aia/Unavailable";
import { ClientTile } from "@/components/aia/ClientTile";
import { roleLabel } from "@/lib/labels";
import { StatusChip, Value } from "@/components/ui";
import { StudyMoney } from "@/components/aia/StudyMoney";

export const dynamic = "force-dynamic";

/**
 * Portfolio: every study the viewer can reach, across clients, with the raw
 * system state the API gives — study status, the viewer's role, remaining
 * budget where the viewer may see costs, and each project's status. It does not
 * say what "needs you": that needs a viewer-actionability contract (OI-11).
 */
export default async function PortfolioPage({ params }: { params: Promise<{ orgSlug: string }> }) {
  const { orgSlug } = await params;
  const [clients, studies] = await Promise.all([listClients(), listStudies()]);

  const byId = new Map<string, ClientResponse>(clients.ok ? clients.data.map((c) => [c.client_id, c]) : []);
  // The list route carries neither the viewer's role nor costs; the study route does.
  const rows = studies.ok
    ? await Promise.all(studies.data.map(async (s) => ({ s, detail: await getStudy(s.study_id), projects: await listProjects(s.study_id) })))
    : [];

  return (
    <div className="space-y-4">
      <ScopeHeader client={null} />
      <div>
        <h1 className="text-2xl font-semibold">{t("portfolio.title")}</h1>
        <p className="text-sm text-ink-muted">{t("portfolio.subtitle")}</p>
      </div>

      <Unavailable id="needs-me" title={t("portfolio.needsMe")} />

      {!clients.ok ? <ApiErrorPanel error={clients.error} /> : null}
      {!studies.ok ? <ApiErrorPanel error={studies.error} /> : rows.length === 0 ? (
        <p className="rounded-md border border-border bg-surface-raised px-4 py-3 text-sm">{t("portfolio.empty")}</p>
      ) : (
        <div data-scroll-x tabIndex={0} aria-label={t("portfolio.title")} className="overflow-x-auto rounded-md border border-border bg-surface-raised">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-sunken text-xs font-semibold text-ink-muted">
              <tr>
                <th className="px-4 py-2">{t("portfolio.columns.study")} / {t("portfolio.columns.client")}</th>
                <th className="px-4 py-2">{t("portfolio.columns.status")}</th>
                <th className="px-4 py-2">{t("portfolio.columns.role")}</th>
                <th className="px-4 py-2">{t("portfolio.columns.projects")}</th>
                <th className="px-4 py-2 text-right">{t("portfolio.columns.remaining")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ s, detail, projects }) => {
                const client = byId.get(s.client_id);
                return (
                  <tr key={s.study_id} className="border-t border-border align-top">
                    <td className="px-4 py-2">
                      <Link className="font-medium text-signal hover:underline" href={`/org/${orgSlug}/studies/${s.study_id}`}>{s.name}</Link>
                      <div className="mt-1 text-xs">
                        {client ? (
                          <Link className="inline-flex items-center gap-2 text-ink hover:underline" href={`/org/${orgSlug}/clients/${client.client_id}`}>
                            <ClientTile client={client} /> {client.name}
                          </Link>
                        ) : <span className="font-mono text-ink-muted">{s.client_id}</span>}
                      </div>
                    </td>
                    <td className="px-4 py-2"><StatusChip kind="StudyStatus" value={s.status} small /></td>
                    <td className="px-4 py-2">{detail.ok ? roleLabel(detail.data.your_role) : <Value value={null} />}</td>
                    <td className="px-4 py-2">
                      {projects.ok ? (
                        projects.data.items.length === 0 ? <span className="text-ink-muted">0</span> : (
                          <ul className="flex flex-wrap gap-1">
                            {projects.data.items.map((p) => (
                              <li key={p.project_id}><StatusChip kind="ProjectStatus" value={p.status} small /></li>
                            ))}
                            {projects.data.page.has_more ? <li className="text-xs text-ink-muted">+{projects.data.page.total - projects.data.items.length}</li> : null}
                          </ul>
                        )
                      ) : <Value value={null} />}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {detail.ok ? <StudyMoney value={detail.data.remaining_usd} /> : <Value value={null} />}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
