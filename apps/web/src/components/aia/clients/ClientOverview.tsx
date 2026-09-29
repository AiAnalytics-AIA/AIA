"use client";

// Přehled: what a researcher needs to continue their work for this client --
// what is active and where it stands, recent outputs, the state of the client's
// knowledge, and what waits for their approval.

import Link from "next/link";

import { t, tv } from "@/i18n/t";
import { type ClientOverview as Overview, type WorkspaceStudy, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { relative } from "@/lib/format";
import { type StepKey, isStepKey } from "@/research/steps";
import { Icon } from "../../rehome/icons";
import { Chip, Tag } from "../../rehome/ui";
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

function Context({ clientId, o }: { clientId: string; o: Overview }) {
  if (!o.knowledge) return <p className="text-sm text-ink-muted">{t("aia.overview.noKnowledgeAccess")}</p>;
  const k = o.knowledge;
  const count = (kinds: string[]) => kinds.reduce((n, kind) => n + (k.items_by_kind[kind] ?? 0), 0);
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
      <Link href={appRoutes.area(clientId, "knowledge")} className="mt-3 inline-block text-sm font-medium text-signal underline">
        {t("aia.overview.openKnowledge")}
      </Link>
    </>
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
              <section aria-labelledby="ov-active">
                <h2 id="ov-active" className="mb-3 text-base font-semibold">{t("aia.overview.activeTitle")}</h2>
                <Active clientId={client.client_id} list={o.active} />
              </section>
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
              {o.knowledge ? (
                <section className={CARD} aria-labelledby="ov-pending">
                  <h2 id="ov-pending" className="text-base font-semibold">{t("aia.overview.pendingTitle")}</h2>
                  {o.pending.length ? (
                    <ul className="mt-3 flex flex-col gap-2 text-sm">
                      {o.pending.map((p) => (
                        <li key={p.proposal_id} className="flex items-start gap-2">
                          <Chip tone="you">{t(`aia.knowledge.kinds.${p.kind}`)}</Chip>
                          <span className="min-w-0 flex-1">
                            <span className="block">{p.title}</span>
                            {p.study_name ? <span className="block text-xs text-ink-faint">{tv("aia.knowledge.fromStudy", { name: p.study_name })}</span> : null}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-ink-muted">{t("aia.overview.pendingEmpty")}</p>
                  )}
                </section>
              ) : null}
            </div>
          </div>
        )}
      </Loaded>
    </ClientPage>
  );
}
