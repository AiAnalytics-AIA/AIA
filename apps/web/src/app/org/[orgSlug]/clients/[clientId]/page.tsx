import Link from "next/link";
import { notFound } from "next/navigation";
import { t } from "@/i18n/t";
import { listClients, listStudies } from "@/lib/api/endpoints";
import { ApiErrorPanel } from "@/components/aia/ApiErrorPanel";
import { ScopeHeader } from "@/components/aia/ScopeHeader";
import { StatusChip } from "@/components/ui";
import { formatDateTime } from "@/design/format";

export const dynamic = "force-dynamic";

/**
 * One client and the studies of it the viewer can reach. There is no client
 * detail route, so the client comes from the organization's client list; an id
 * that is not in it is a 404, like any other scope the viewer cannot see.
 */
export default async function ClientPage({ params }: { params: Promise<{ orgSlug: string; clientId: string }> }) {
  const { orgSlug, clientId } = await params;
  const [clients, studies] = await Promise.all([listClients(), listStudies(clientId)]);
  if (!clients.ok) return <ApiErrorPanel error={clients.error} />;
  const client = clients.data.find((c) => c.client_id === clientId);
  if (!client) notFound();

  return (
    <div className="space-y-4">
      <ScopeHeader client={client} />
      <div>
        <h1 className="text-2xl font-semibold">{client.name}</h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-muted">
          <StatusChip kind="ClientStatus" value={client.status} small />
          <span className="font-mono">{client.client_id}</span>
        </div>
      </div>
      {!studies.ok ? <ApiErrorPanel error={studies.error} /> : (
        <section aria-label={t("client.studies")} className="rounded-md border border-border bg-surface-raised">
          <h2 className="border-b border-border px-4 py-2 text-sm font-semibold">{t("client.studies")} ({studies.data.length})</h2>
          {studies.data.length === 0 ? <p className="px-4 py-3 text-sm">{t("client.empty")}</p> : (
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-sunken text-xs font-semibold text-ink-muted">
                <tr>
                  <th className="px-4 py-2">{t("portfolio.columns.study")}</th>
                  <th className="px-4 py-2">{t("portfolio.columns.status")}</th>
                  <th className="px-4 py-2">{t("portfolio.columns.modified")}</th>
                </tr>
              </thead>
              <tbody>
                {studies.data.map((s) => (
                  <tr key={s.study_id} className="border-t border-border">
                    <td className="px-4 py-2 font-medium">
                      <Link className="text-signal hover:underline" href={`/org/${orgSlug}/studies/${s.study_id}`}>{s.name}</Link>
                    </td>
                    <td className="px-4 py-2"><StatusChip kind="StudyStatus" value={s.status} small /></td>
                    <td className="px-4 py-2 tabular-nums text-ink-muted">{formatDateTime(s.modified_at) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  );
}
