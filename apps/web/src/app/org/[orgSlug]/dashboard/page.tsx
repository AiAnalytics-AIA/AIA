import Link from "next/link";
import { t } from "@/i18n/t";
import { fixtureClient, fixtureStudies } from "@/fixtures";
import { FixtureNotice } from "@/components/aia/FixtureNotice";
import { roleLabel, studyStatusLabel } from "@/lib/labels";

/** Portfolio: studies across clients the viewer holds a grant on. */
export default async function PortfolioPage({ params }: { params: Promise<{ orgSlug: string }> }) {
  const { orgSlug } = await params;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">{t("portfolio.title")}</h1>
        <p className="text-sm text-zinc-600">{t("portfolio.subtitle")}</p>
      </div>
      <FixtureNotice capability="portfolio-studies" />
      <div className="overflow-x-auto rounded-md border border-zinc-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-50 text-xs font-semibold text-zinc-600">
            <tr>
              <th className="px-4 py-2">{t("portfolio.columns.study")}</th>
              <th className="px-4 py-2">{t("portfolio.columns.client")}</th>
              <th className="px-4 py-2">{t("portfolio.columns.status")}</th>
              <th className="px-4 py-2">{t("portfolio.columns.role")}</th>
            </tr>
          </thead>
          <tbody>
            {fixtureStudies.map((s) => (
              <tr key={s.study_id} className="border-t border-zinc-100">
                <td className="px-4 py-2 font-medium">
                  <Link className="text-blue-700 hover:underline" href={`/org/${orgSlug}/studies/${s.study_id}`}>{s.name}</Link>
                </td>
                <td className="px-4 py-2">{fixtureClient(s.client_id)?.name ?? s.client_id}</td>
                <td className="px-4 py-2">{studyStatusLabel(s.status)}</td>
                <td className="px-4 py-2">{roleLabel(s.your_role)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
