"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { LiveShell } from "@/components/live/LiveShell";
import { Button, ErrorNote, Loading, Panel, Status } from "@/components/live/ui";
import { api, type Artifact, type Project, type Run, type RunSummary } from "@/lib/api";
import { t } from "@/i18n/t";

const POLL_MS = 2000;

export default function ProjectPage() {
  const { studyId, projectId } = useParams<{ studyId: string; projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const loadRuns = useCallback(() => {
    api.runs(studyId, projectId).then(setRuns).catch(setError);
  }, [studyId, projectId]);

  useEffect(() => {
    api.project(studyId, projectId).then(setProject).catch(setError);
    loadRuns();
  }, [studyId, projectId, loadRuns]);

  // Poll the selected run until the server says it is terminal. Real state
  // transitions only; nothing here estimates progress.
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const current = await api.run(studyId, projectId, selected);
        if (cancelled) return;
        setRun(current);
        if (!current.is_terminal) {
          timer = setTimeout(tick, POLL_MS);
        } else {
          loadRuns();
        }
      } catch (e) {
        if (!cancelled) setError(e);
      }
    };
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [selected, studyId, projectId, loadRuns]);

  // When the snapshot step has an artifact, read it back through the API.
  useEffect(() => {
    const artifactId = run?.steps[0]?.output?.artifact_id;
    if (!run?.is_terminal || typeof artifactId !== "string") {
      setArtifact(null);
      return;
    }
    api.artifact(studyId, projectId, artifactId).then(setArtifact).catch(setError);
  }, [run, studyId, projectId]);

  const startRun = async () => {
    setBusy(true);
    setError(null);
    try {
      const started = await api.startRun(studyId, projectId);
      setSelected(started.run_id);
      loadRuns();
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
          /{" "}
          <Link className="hover:underline" href={`/studies/${studyId}`}>
            <span className="font-mono">{studyId}</span>
          </Link>{" "}
          / <span className="font-mono">{projectId}</span>
        </div>
        <ErrorNote error={error} />
        {project ? (
          <div>
            <h1 className="text-2xl font-semibold">{project.title}</h1>
            <div className="mt-1 flex items-center gap-3 text-sm text-zinc-600">
              <Status value={project.status} />
              <span>
                {t("live.revision")} {project.current_revision}
              </span>
              <span>
                {t("live.stage")}: {project.current_stage}
              </span>
            </div>
          </div>
        ) : (
          <Loading />
        )}

        <Panel
          title={t("live.runs")}
          action={
            <Button onClick={() => void startRun()} disabled={busy}>
              {t("live.startSnapshot")}
            </Button>
          }
        >
          <p className="mb-3 text-xs text-zinc-500">{t("live.snapshotExplainer")}</p>
          {runs === null && !error ? <Loading /> : null}
          {runs && runs.length === 0 ? <div>{t("live.noRuns")}</div> : null}
          {runs && runs.length > 0 ? (
            <ul className="divide-y divide-zinc-100">
              {runs.map((r) => (
                <li key={r.run_id} className="flex items-center justify-between py-2">
                  <button
                    className={`font-mono text-xs ${selected === r.run_id ? "font-semibold" : "text-blue-700 hover:underline"}`}
                    onClick={() => setSelected(r.run_id)}
                  >
                    {r.run_id}
                  </button>
                  <span className="text-xs text-zinc-500">
                    {t("live.revision")} {r.project_revision}
                  </span>
                  <Status value={r.status} />
                </li>
              ))}
            </ul>
          ) : null}
        </Panel>

        {run ? (
          <Panel title={`${t("live.run")} ${run.run_id}`}>
            <div className="mb-3 flex items-center gap-3">
              <Status value={run.status} />
              {run.needs_attention ? (
                <span className="text-xs text-amber-800">{t("live.needsAttention")}</span>
              ) : null}
              {!run.is_terminal ? <span className="text-xs text-zinc-500">{t("live.polling")}</span> : null}
            </div>
            <table className="w-full text-left text-sm">
              <thead className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="py-2">{t("live.step")}</th>
                  <th className="py-2">{t("live.kind")}</th>
                  <th className="py-2">{t("live.status")}</th>
                  <th className="py-2">{t("live.attempts")}</th>
                  <th className="py-2">{t("live.worker")}</th>
                </tr>
              </thead>
              <tbody>
                {run.steps.map((s) => (
                  <tr key={s.step_id} className="border-t border-zinc-100 align-top">
                    <td className="py-2 font-mono text-xs">{s.node_key}</td>
                    <td className="py-2 font-mono text-xs">{s.kind}</td>
                    <td className="py-2">
                      <Status value={s.status} />
                      {s.waiting_reason ? <div className="text-xs text-zinc-500">{s.waiting_reason}</div> : null}
                    </td>
                    <td className="py-2 text-xs">
                      {s.attempts_recorded} / {s.max_attempts}
                      {s.attempts.some((a) => a.failure_class) ? (
                        <div className="text-red-700">
                          {s.attempts
                            .filter((a) => a.failure_class)
                            .map((a) => `#${a.attempt_number} ${a.failure_class}`)
                            .join(", ")}
                        </div>
                      ) : null}
                    </td>
                    <td className="py-2 font-mono text-xs text-zinc-500">
                      {s.attempts.at(-1)?.worker_id ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>
        ) : null}

        {artifact ? (
          <Panel title={`${t("live.artifact")} ${artifact.artifact_id}`}>
            <dl className="mb-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-4">
              <dt className="text-zinc-500">{t("live.type")}</dt>
              <dd className="font-mono">{artifact.artifact_type}</dd>
              <dt className="text-zinc-500">{t("live.stage")}</dt>
              <dd className="font-mono">{artifact.stage_type}</dd>
              <dt className="text-zinc-500">sha256</dt>
              <dd className="font-mono">{artifact.sha256.slice(0, 16)}…</dd>
              <dt className="text-zinc-500">{t("live.producedByBuild")}</dt>
              <dd className="font-mono">{artifact.runtime_version || "—"}</dd>
            </dl>
            <pre className="max-h-96 overflow-auto rounded-md bg-zinc-50 p-3 font-mono text-xs">
              {JSON.stringify(artifact.payload, null, 2)}
            </pre>
          </Panel>
        ) : null}
      </div>
    </LiveShell>
  );
}
