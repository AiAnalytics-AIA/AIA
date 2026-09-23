"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { LiveShell } from "@/components/live/LiveShell";
import { ErrorNote, Loading, Panel, Status } from "@/components/live/ui";
import { api, type Study } from "@/lib/api";
import { t } from "@/i18n/t";

export default function StudiesPage() {
  const [studies, setStudies] = useState<Study[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api.studies().then(setStudies).catch(setError);
  }, []);

  return (
    <LiveShell>
      <div className="space-y-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{t("live.badge")}</div>
          <h1 className="mt-1 text-2xl font-semibold">{t("live.studies")}</h1>
          <p className="mt-1 text-sm text-zinc-600">{t("live.studiesIntro")}</p>
        </div>
        <ErrorNote error={error} />
        <Panel title={t("live.studies")}>
          {studies === null && !error ? <Loading /> : null}
          {studies && studies.length === 0 ? <div>{t("live.noStudies")}</div> : null}
          {studies && studies.length > 0 ? (
            <table className="w-full text-left text-sm">
              <thead className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2">{t("live.name")}</th>
                  <th className="py-2">{t("live.status")}</th>
                  <th className="py-2">{t("live.id")}</th>
                </tr>
              </thead>
              <tbody>
                {studies.map((s) => (
                  <tr key={s.study_id} className="border-t border-zinc-100">
                    <td className="py-2 font-medium">
                      <Link className="text-blue-700 hover:underline" href={`/studies/${s.study_id}`}>
                        {s.name}
                      </Link>
                    </td>
                    <td className="py-2">
                      <Status value={s.status} />
                    </td>
                    <td className="py-2 font-mono text-xs text-zinc-500">{s.study_id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </Panel>
      </div>
    </LiveShell>
  );
}
