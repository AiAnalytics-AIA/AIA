"use client";

// A past research of one client, read-only (plans/project-memory-reuse.md M2c): what each of its
// Design Revisions says, the runs of the chosen one with their labels, and a run's results as the
// Results stage draws them -- under a frame that may not edit, so no download, no action, no
// working content. Everything is read through the Study (404 outside the caller's scope), and the
// study must be a research of the client in the URL. Nothing here writes.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  ApiError,
  type DesignRevision,
  type ResearchReport,
  type ResearchRun,
  type ResearchRunSummary,
  type StudyWorkspace,
  research,
  workspace,
} from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { type RunLabels, designSummary, runLabels } from "@/lib/memory";
import { runState } from "@/lib/run-state";
import { PERSONA_DIM_LABELS } from "@/research/persona";
import type { StepKey } from "@/research/steps";
import { RunResults } from "../rehome/research/ExecutionSteps";
import { type StudyFrame, StudyFrameProvider } from "../rehome/research/frame";
import { Button, StatusPill, Field, Select, Tag, TextInput } from "../rehome/ui";
import { AppShell } from "./AppShell";
import { useClient } from "./clients/ClientContext";
import { CARD, Empty, Loaded, NotFound } from "./states";
import { useResource } from "./useResource";
import { errorText } from "@/lib/error-words";

const S = "aia.memory.study";
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString("cs-CZ") : "—");

export function MemoryStudy({ studyId }: { studyId: string }) {
  const { client } = useClient();
  const [res, retry] = useResource(() => workspace.study(studyId), [studyId]);
  const w = res.state === "ready" ? res.data : null;
  const here = w && w.study.client_id === client.client_id && w.study.kind === "RESEARCH";
  return (
    <AppShell
      crumbs={[
        { label: t("aia.navClients"), href: appRoutes.clients() },
        { label: client.name, href: appRoutes.client(client.client_id) },
        { label: t(`${S}.crumb`), href: appRoutes.memory() },
        { label: here ? w.study.name : "…" },
      ]}
      title={here ? w.study.name : t(`${S}.crumb`)}
      sub={t(`${S}.sub`)}
      client={{ id: client.client_id, name: client.name }}
      action={
        here ? (
          <Link href={appRoutes.study(client.client_id, studyId, "RESEARCH")} className="text-sm font-medium text-signal underline">
            {t(`${S}.open`)}
          </Link>
        ) : undefined
      }
    >
      {w ? here ? <PastStudy w={w} /> : <NotFound /> : <Loaded res={res} retry={retry}>{() => null}</Loaded>}
    </AppShell>
  );
}

function PastStudy({ w }: { w: StudyWorkspace }) {
  const { client } = useClient();
  const studyId = w.study.study_id;
  const [revisions, retry] = useResource(() => research.revisions(studyId), [studyId]);
  // The client's own dimensions are named by their titles; without them, a dimension shows its id.
  const [knowledge] = useResource(() => workspace.knowledge(client.client_id, "dimensions"), [client.client_id]);
  const labels = useMemo(() => {
    const out: Record<string, string> = { ...PERSONA_DIM_LABELS };
    if (knowledge.state === "ready") for (const k of knowledge.data) if (k.kind === "DIMENSION") out[k.item_id] = k.title;
    return out;
  }, [knowledge]);
  const frame: StudyFrame = useMemo(
    () => ({
      clientId: client.client_id,
      clientName: client.name,
      studyId,
      studyName: w.study.name,
      lastStage: null,
      canEdit: false,
      stepHref: (step: StepKey) => appRoutes.stage(client.client_id, studyId, step),
    }),
    [client.client_id, client.name, studyId, w.study.name],
  );
  return (
    <Loaded res={revisions} retry={retry}>
      {(list) =>
        list.length ? (
          <StudyFrameProvider frame={frame}>
            <Revisions studyId={studyId} studyName={w.study.name} revisions={list} labels={labels} />
          </StudyFrameProvider>
        ) : (
          <Draft studyId={studyId} labels={labels} />
        )
      }
    </Loaded>
  );
}

function Revisions({ studyId, studyName, revisions, labels }: { studyId: string; studyName: string; revisions: DesignRevision[]; labels: Record<string, string> }) {
  const [chosen, setChosen] = useState(revisions[0].revision_id);
  const revision = revisions.find((r) => r.revision_id === chosen) ?? revisions[0];
  return (
    <div className="flex flex-col gap-6">
      <section aria-labelledby="mem-revisions">
        <h2 id="mem-revisions" className="mb-2 text-base font-semibold">{t(`${S}.revisions`)}</h2>
        <ul className="flex flex-wrap gap-2">
          {revisions.map((r) => (
            <li key={r.revision_id}>
              <button
                type="button"
                aria-pressed={r.revision_id === revision.revision_id}
                onClick={() => setChosen(r.revision_id)}
                className={`rounded-control border px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-focus-ring ${
                  r.revision_id === revision.revision_id ? "border-signal bg-signal-wash" : "border-border bg-surface-raised hover:bg-surface"
                }`}
              >
                <span className="block font-medium">{tv(`${S}.revision`, { revision: r.revision })}</span>
                <span className="block text-xs text-ink-muted">{tv(`${S}.revisionMeta`, { when: when(r.created_at), stage: r.source_stage })}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <RevisionDesign key={revision.revision_id} studyId={studyId} revision={revision} labels={labels} />
      <ReuseDesign key={`reuse-${revision.revision_id}`} studyId={studyId} studyName={studyName} revision={revision} />
      <RevisionRuns key={`runs-${revision.revision_id}`} studyId={studyId} revision={revision} />
    </div>
  );
}

function DesignFields({ content, labels }: { content: Record<string, unknown>; labels: Record<string, string> }) {
  const fields = designSummary(content, labels);
  if (!fields.length) return <p className="text-sm text-ink-muted">{t(`${S}.designEmpty`)}</p>;
  return (
    <dl className="flex flex-col gap-3">
      {fields.map((f) => (
        <div key={f.field}>
          <dt className="text-xs text-ink-muted">{t(`${S}.field.${f.field}`)}</dt>
          <dd>
            {f.values.length === 1 ? (
              <p className="text-sm">{f.values[0]}</p>
            ) : (
              <ul className="list-disc pl-5 text-sm">{f.values.map((v) => <li key={v}>{v}</li>)}</ul>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function RevisionDesign({ studyId, revision, labels }: { studyId: string; revision: DesignRevision; labels: Record<string, string> }) {
  const [res, retry] = useResource(() => research.revision(studyId, revision.revision_id), [studyId, revision.revision_id]);
  return (
    <section className={CARD} aria-labelledby="mem-design">
      <h2 id="mem-design" className="mb-3 text-base font-semibold">
        {t(`${S}.design`)} · {tv(`${S}.revision`, { revision: revision.revision })}
      </h2>
      <Loaded res={res} retry={retry}>{(r) => <DesignFields content={r.content} labels={labels} />}</Loaded>
    </section>
  );
}

/**
 * Start a study from this revision (project memory M3e): a new research study of the client, or
 * one of its empty ones. The server derives the labels and refuses a target with content; this
 * only asks where, then opens the study it started.
 */
function ReuseDesign({ studyId, studyName, revision }: { studyId: string; studyName: string; revision: DesignRevision }) {
  const { client } = useClient();
  const router = useRouter();
  const [into, setInto] = useState<"new" | "empty">("new");
  const [name, setName] = useState(tv(`${S}.reuse.nameDefault`, { name: studyName }));
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [studies] = useResource(() => workspace.studies(client.client_id, "RESEARCH"), [client.client_id]);
  // Empty as far as the list knows; the server checks the design too and refuses otherwise.
  const empty = studies.state === "ready" ? studies.data.filter((x) => x.study_id !== studyId && !x.has_working_content && x.content_state === "EMPTY") : [];
  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      const done = await workspace.memoryReuse(client.client_id, {
        source_study_id: studyId,
        source_revision_id: revision.revision_id,
        ...(into === "new" ? { new_study_name: name.trim() } : { target_study_id: target }),
      });
      router.push(appRoutes.study(client.client_id, done.study_id, "RESEARCH"));
    } catch (e) {
      const code = e instanceof ApiError ? e.code : null;
      setError(code && [`target_not_empty`, `not_research`, `not_found`].includes(code) ? t(`${S}.reuse.refused.${code}`) : errorText(e));
      setBusy(false);
    }
  };
  const ready = into === "new" ? name.trim().length > 0 : target !== "";
  return (
    <section className={CARD} aria-labelledby="mem-reuse">
      <h2 id="mem-reuse" className="mb-1 text-base font-semibold">{t(`${S}.reuse.title`)}</h2>
      <p className="mb-3 text-sm text-ink-muted">{t(`${S}.reuse.text`)}</p>
      <fieldset className="flex flex-col gap-3">
        <legend className="sr-only">{t(`${S}.reuse.title`)}</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name="reuse-into" checked={into === "new"} onChange={() => setInto("new")} />
          {t(`${S}.reuse.intoNew`)}
        </label>
        {into === "new" ? (
          <Field label={t(`${S}.reuse.name`)} className="max-w-md pl-6">
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
        ) : null}
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name="reuse-into" checked={into === "empty"} onChange={() => setInto("empty")} />
          {t(`${S}.reuse.intoEmpty`)}
        </label>
        {into === "empty" ? (
          empty.length ? (
            <Field label={t(`${S}.reuse.empty`)} className="max-w-md pl-6">
              <Select value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="">—</option>
                {empty.map((x) => <option key={x.study_id} value={x.study_id}>{x.name}</option>)}
              </Select>
            </Field>
          ) : (
            <p className="pl-6 text-sm text-ink-muted">{t(`${S}.reuse.noEmpty`)}</p>
          )
        ) : null}
      </fieldset>
      <Button variant="primary" className="mt-4" disabled={!ready || busy} onClick={() => void start()}>
        {busy ? t(`${S}.reuse.starting`) : t(`${S}.reuse.start`)}
      </Button>
      {error ? <p role="alert" className="mt-2 text-sm text-status-fault">{error}</p> : null}
    </section>
  );
}

/** A study with no Design Revision: its working content, said to be a draft, never a design. */
function Draft({ studyId, labels }: { studyId: string; labels: Record<string, string> }) {
  const [res, retry] = useResource(() => workspace.content(studyId), [studyId]);
  return (
    <section className={`${CARD} max-w-3xl`} aria-labelledby="mem-draft">
      <h2 id="mem-draft" className="mb-1 text-base font-semibold">{t(`${S}.noDesign`)}</h2>
      <Loaded res={res} retry={retry}>
        {(c) =>
          c.content ? (
            <>
              <p role="note" className="mb-3 text-sm font-semibold text-status-you-ink">{t(`${S}.draft`)}</p>
              <DesignFields content={c.content} labels={labels} />
            </>
          ) : (
            <p className="text-sm text-ink-muted">{t(`${S}.nothing`)}</p>
          )
        }
      </Loaded>
    </section>
  );
}

function RevisionRuns({ studyId, revision }: { studyId: string; revision: DesignRevision }) {
  const [res, retry] = useResource(() => research.runs(studyId), [studyId]);
  const [chosen, setChosen] = useState<string | null>(null);
  return (
    <section aria-labelledby="mem-runs" className="flex flex-col gap-4">
      <h2 id="mem-runs" className="text-base font-semibold">{t(`${S}.runs`)}</h2>
      <Loaded res={res} retry={retry}>
        {(all) => {
          const runs = all.filter((r) => r.design_revision_id === revision.revision_id);
          if (!runs.length) return <Empty>{t(`${S}.noRuns`)}</Empty>;
          const open = runs.find((r) => r.run_id === chosen) ?? runs[0];
          return (
            <>
              <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
                {runs.map((r) => (
                  <li key={r.run_id}>
                    <button
                      type="button"
                      aria-pressed={r.run_id === open.run_id}
                      onClick={() => setChosen(r.run_id)}
                      className={`flex w-full flex-wrap items-center gap-3 px-5 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus-ring ${
                        r.run_id === open.run_id ? "bg-signal-wash" : "hover:bg-surface"
                      }`}
                    >
                      <span className="flex-1 text-sm font-medium">{tv(`${S}.run`, { when: when(r.created_at) })}</span>
                      <Tag>{runState(r).label}</Tag>
                      <LabelChips labels={runLabels(r)} brief />
                    </button>
                  </li>
                ))}
              </ul>
              <OpenRun key={open.run_id} studyId={studyId} summary={open} />
            </>
          );
        }}
      </Loaded>
    </section>
  );
}

function LabelChips({ labels, brief = false }: { labels: RunLabels; brief?: boolean }): ReactNode {
  return (
    <span className="flex flex-wrap gap-2">
      <StatusPill tone={labels.data === "synthetic" ? "fault" : "neutral"}>{t(`${S}.data.${labels.data}`)}</StatusPill>
      {brief ? null : <StatusPill tone={labels.report === "approved_internal" ? "done" : "neutral"}>{t(`${S}.report.${labels.report}`)}</StatusPill>}
      {!brief && labels.internal ? <StatusPill tone="you">{t(`${S}.internal`)}</StatusPill> : null}
    </span>
  );
}

/** The chosen run, read in full: its labels, then its results as the Results stage draws them. */
function OpenRun({ studyId, summary }: { studyId: string; summary: ResearchRunSummary }) {
  const [run, retry] = useResource(() => research.run(studyId, summary.run_id), [studyId, summary.run_id]);
  return (
    <Loaded res={run} retry={retry}>
      {(r) => (
        <div className="flex flex-col gap-4">
          <RunLabelsCard studyId={studyId} run={r} />
          <RunResults run={r} progressHref={null} />
        </div>
      )}
    </Loaded>
  );
}

function RunLabelsCard({ studyId, run }: { studyId: string; run: ResearchRun }) {
  const hasReport = run.steps.some((s) => s.kind === "research_report");
  // A report the API will not show (403) or that failed to load stays unknown, never approved.
  const [report, setReport] = useState<ResearchReport | null>(null);
  useEffect(() => {
    if (!hasReport) return;
    let live = true;
    research.report(studyId, run.run_id).then(
      (value) => live && setReport(value),
      () => {},
    );
    return () => {
      live = false;
    };
  }, [studyId, run.run_id, hasReport]);
  return (
    <section className={CARD} aria-label={t(`${S}.labels`)}>
      <h3 className="mb-2 text-sm font-semibold">{t(`${S}.labels`)}</h3>
      <LabelChips labels={runLabels(run, report)} />
    </section>
  );
}
