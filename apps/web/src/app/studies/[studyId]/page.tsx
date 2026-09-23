"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { LiveShell } from "@/components/live/LiveShell";
import { Button, ErrorNote, Loading, Panel, Status } from "@/components/live/ui";
import { api, type Project, type Study } from "@/lib/api";
import { t } from "@/i18n/t";

export default function StudyPage() {
  const { studyId } = useParams<{ studyId: string }>();
  const [study, setStudy] = useState<Study | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.study(studyId).then(setStudy).catch(setError);
    api.projects(studyId).then(setProjects).catch(setError);
  }, [studyId]);

  useEffect(load, [load]);

  const createProject = async () => {
    setBusy(true);
    try {
      await api.createProject(studyId, `${t("live.newProjectTitle")} ${new Date().toISOString().slice(0, 16)}`);
      load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <LiveShell>
      <div className="space-y-4">
        <div className="text-xs text-zinc-500">
          <Link className="hover:underline" href="/studies">
            {t("live.studies")}
          </Link>{" "}
          / <span className="font-mono">{studyId}</span>
        </div>
        <ErrorNote error={error} />
        {study ? (
          <div>
            <h1 className="text-2xl font-semibold">{study.name}</h1>
            <div className="mt-1 flex items-center gap-3 text-sm text-zinc-600">
              <Status value={study.status} />
              {study.your_role ? <span>{t("live.yourRole")}: {study.your_role}</span> : null}
              {study.budget_usd !== null ? (
                <span>
                  {t("live.budget")}: {study.spent_usd?.toFixed(2)} / {study.budget_usd.toFixed(2)} USD
                </span>
              ) : null}
            </div>
          </div>
        ) : (
          <Loading />
        )}
        <Panel
          title={t("live.projects")}
          action={
            study?.accepts_work ? (
              <Button onClick={() => void createProject()} disabled={busy}>
                {t("live.newProject")}
              </Button>
            ) : null
          }
        >
          {projects === null && !error ? <Loading /> : null}
          {projects && projects.length === 0 ? <div>{t("live.noProjects")}</div> : null}
          {projects && projects.length > 0 ? (
            <table className="w-full text-left text-sm">
              <thead className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2">{t("live.name")}</th>
                  <th className="py-2">{t("live.revision")}</th>
                  <th className="py-2">{t("live.status")}</th>
                  <th className="py-2">{t("live.id")}</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <tr key={p.project_id} className="border-t border-zinc-100">
                    <td className="py-2 font-medium">
                      <Link
                        className="text-blue-700 hover:underline"
                        href={`/studies/${studyId}/projects/${p.project_id}`}
                      >
                        {p.title}
                      </Link>
                    </td>
                    <td className="py-2">{p.current_revision}</td>
                    <td className="py-2">
                      <Status value={p.status} />
                    </td>
                    <td className="py-2 font-mono text-xs text-zinc-500">{p.project_id}</td>
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
