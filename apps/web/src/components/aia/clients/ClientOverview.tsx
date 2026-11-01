"use client";

// Přehled: what a researcher needs to continue their work for this client
// (client-workspace C10) -- first what waits on a person's decision, then the
// work in progress, what changed in the client's knowledge, recent outputs, and
// the knowledge at a glance with what in it wants attention (unchanged for a
// year, in no folder), each a link to the view that shows it.

import Link from "next/link";

import { t, tv } from "@/i18n/t";
import { type ClientOverview as Overview, type WorkspaceStudy, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { relative } from "@/lib/format";
import { type StepKey, isStepKey } from "@/research/steps";
import { Icon } from "../../rehome/icons";
import { StatusPill, Tag } from "../../rehome/ui";
import { CARD, Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { ClientPage, useClient } from "./ClientContext";

export function studyHref(clientId: string, s: WorkspaceStudy): string {
  if (s.kind === "SIMULATION") return appRoutes.study(clientId, s.study_id, "SIMULATION");
  const stage: StepKey = s.last_stage && isStepKey(s.last_stage) ? s.last_stage : "brief";
  return appRoutes.stage(clientId, s.study_id, stage);
}

export function studyWhere(s: WorkspaceStudy): string {
  const stage = s.kind === "RESEARCH" && s.last_stage && isStepKey(s.last_stage) ? t(`aia.stages.${s.last_stage}`) : t(`aia.status.${s.status}`);
  return tv("aia.overview.stage", { kind: t(`aia.kind.${s.kind}`), stage });
}

function Active({ clientId, list }: { clientId: string; list: WorkspaceStudy[] }) {
  if (!list.length) return <Empty>{t("aia.overview.activeEmpty")}</Empty>;
  return (
    <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
      {list.map((s) => (
        <li key={s.study_id}>
          <Link
            href={studyHref(clientId, s)}
            className="flex items-center gap-4 px-5 py-4 no-underline hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus-ring"
          >
            <Icon name={s.kind === "SIMULATION" ? "simulation" : "research"} className="text-ink-faint" />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-ink">{s.name}</span>
              <span className="block text-sm text-ink-muted">{studyWhere(s)}</span>
            </span>
            <span className="hidden text-xs text-ink-faint sm:block">{s.modified_at ? tv("aia.overview.updated", { when: relative(s.modified_at) ?? "" }) : null}</span>
            <span className="text-sm font-medium text-signal">{t("aia.overview.continue")}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

const SECTION_COUNTS: [string, string[]][] = [
  ["sources", ["SOURCE", "DOCUMENT"]],
  ["knowledge", ["FACT", "FINDING", "TERM", "ENTITY"]],
  ["dimensions", ["DIMENSION"]],
  ["audiences", ["AUDIENCE"]],
];

const knowledgeView = (clientId: string, view: "review" | "unfiled" | "old") => `${appRoutes.area(clientId, "knowledge")}?view=${view}`;

function Context({ clientId, o }: { clientId: string; o: Overview }) {
  if (!o.knowledge) return <p className="text-sm text-ink-muted">{t("aia.overview.noKnowledgeAccess")}</p>;
  const k = o.knowledge;
  const count = (kinds: string[]) => kinds.reduce((n, kind) => n + (k.items_by_kind[kind] ?? 0), 0);
  const stale = k.stale_items ?? 0;
  const unfiled = k.unfiled_items ?? 0;
  return (
    <>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        {SECTION_COUNTS.map(([section, kinds]) => (
          <div key={section} className="flex items-baseline justify-between gap-2">
            <dt className="text-ink-muted">{t(`aia.knowledge.sections.${section}`)}</dt>
            <dd className="font-mono tabular-nums">{count(kinds)}</dd>
          </div>
        ))}
        <div className="flex items-baseline justify-between gap-2">
          <dt className="text-ink-muted">{t("aia.overview.previous")}</dt>
          <dd className="font-mono tabular-nums">{o.previous_count}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-ink-faint">
        {tv("aia.overview.revision", { n: k.context_revision })} ·{" "}
        {k.last_approved_at ? tv("aia.overview.contextUpdated", { when: relative(k.last_approved_at) ?? "" }) : t("aia.overview.contextNever")}
      </p>
      <ul className="mt-3 flex flex-col gap-1 border-t border-border pt-3 text-[13px]">
        {stale ? (
          <li>
            <Link href={knowledgeView(clientId, "old")} className="text-status-you-ink underline-offset-2 hover:underline">{tv("aia.overview.stale", { n: stale })}</Link>
          </li>
        ) : null}
        {unfiled ? (
          <li>
            <Link href={knowledgeView(clientId, "unfiled")} className="text-ink-muted underline-offset-2 hover:underline">{tv("aia.overview.unfiled", { n: unfiled })}</Link>
          </li>
        ) : null}
        {!stale && !unfiled ? <li className="text-ink-faint">{t("aia.overview.healthAll")}</li> : null}
      </ul>
      <Link href={appRoutes.area(clientId, "knowledge")} className="mt-3 inline-block text-sm font-medium text-signal underline">
        {t("aia.overview.openKnowledge")}
      </Link>
    </>
  );
}

/** What stands until someone decides it: proposals for the client's knowledge, studies in review. */
function YourTurn({ clientId, o }: { clientId: string; o: Overview }) {
  const waiting = o.knowledge?.pending_proposals ?? 0;
  const inReview = o.active.filter((s) => s.status === "IN_REVIEW");
  if (!waiting && !inReview.length) return <Empty>{t("aia.overview.youEmpty")}</Empty>;
  return (
    <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
      {waiting ? (
        <li className="flex flex-wrap items-start gap-3 px-5 py-3">
          <StatusPill tone="you">{t("aia.library.views.review")}</StatusPill>
          <span className="min-w-0 flex-1">
            <span className="block font-medium">{tv("aia.overview.youProposals", { n: waiting })}</span>
            <span className="block text-sm text-ink-muted">
              {o.pending.slice(0, 3).map((p) => p.title).join(" · ")}
              {waiting > 3 ? ` ${tv("aia.overview.youProposalsMore", { n: waiting - 3 })}` : ""}
            </span>
          </span>
          <Link href={knowledgeView(clientId, "review")} className="text-sm font-medium text-signal">{t("aia.overview.review")}</Link>
        </li>
      ) : null}
      {inReview.map((s) => (
        <li key={s.study_id}>
          <Link href={studyHref(clientId, s)} className="flex flex-wrap items-center gap-3 px-5 py-3 no-underline hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus-ring">
            <StatusPill tone="you">{t("aia.overview.youReview")}</StatusPill>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-ink">{s.name}</span>
              <span className="block text-sm text-ink-muted">{studyWhere(s)}</span>
            </span>
            <span className="text-sm font-medium text-signal">{t("aia.overview.continue")}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Changes({ o }: { o: Overview }) {
  const changes = o.recent_changes ?? [];
  if (!changes.length) return <Empty>{t("aia.overview.changesEmpty")}</Empty>;
  return (
    <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
      {changes.map((c) => (
        <li key={`${c.item_id}@${c.revision}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-5 py-3">
          <span className="min-w-0 flex-1 font-medium">{c.title}</span>
          <span className="text-xs text-ink-muted">
            {t(`aia.overview.changeOrigin.${c.origin}`)} · {tv("aia.overview.changeRevision", { n: c.revision })}
          </span>
          <span className="w-24 text-right text-xs text-ink-faint">{relative(c.at)}</span>
        </li>
      ))}
    </ul>
  );
}

export function ClientOverview() {
  const { client } = useClient();
  const [res, retry] = useResource(() => workspace.overview(client.client_id), [client.client_id]);
  return (
    <ClientPage>
      <Loaded res={res} retry={retry}>
        {(o) => (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
            <div className="flex min-w-0 flex-col gap-6">
              <section aria-labelledby="ov-you">
                <h2 id="ov-you" className="mb-3 text-base font-semibold">{t("aia.overview.youTitle")}</h2>
                <YourTurn clientId={client.client_id} o={o} />
              </section>
              <section aria-labelledby="ov-active">
                <h2 id="ov-active" className="mb-3 text-base font-semibold">{t("aia.overview.activeTitle")}</h2>
                {/* A study in review is listed once, under Čeká na vás. */}
                <Active clientId={client.client_id} list={o.active.filter((s) => s.status !== "IN_REVIEW")} />
              </section>
              {o.knowledge ? (
                <section aria-labelledby="ov-changes">
                  <h2 id="ov-changes" className="mb-3 text-base font-semibold">{t("aia.overview.changesTitle")}</h2>
                  <Changes o={o} />
                </section>
              ) : null}
              <section aria-labelledby="ov-outputs">
                <h2 id="ov-outputs" className="mb-3 text-base font-semibold">{t("aia.overview.outputsTitle")}</h2>
                {o.recent_outputs.length ? (
                  <ul className="flex flex-col gap-2">
                    {o.recent_outputs.map((a) => (
                      <li key={a.artifact_id} className={`${CARD} flex flex-wrap items-center gap-3 py-3`}>
                        <Tag>{a.artifact_type}</Tag>
                        <span className="flex-1 text-sm">{a.study_name}</span>
                        <span className="text-xs text-ink-faint">{relative(a.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <Empty>{t("aia.overview.outputsEmpty")}</Empty>
                )}
              </section>
            </div>
            <div className="flex flex-col gap-6">
              <section className={CARD} aria-labelledby="ov-context">
                <h2 id="ov-context" className="text-base font-semibold">{t("aia.overview.contextTitle")}</h2>
                <div className="mt-3">
                  <Context clientId={client.client_id} o={o} />
                </div>
              </section>
            </div>
          </div>
        )}
      </Loaded>
    </ClientPage>
  );
}
