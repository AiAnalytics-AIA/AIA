"use client";

// Výzkumy and Simulace: this client's studies of one kind as a table (client-workspace C2):
// where each stands, what it brought into the client's knowledge, when it last changed.
// Filters by status (archived ones out of the default view) and two orders. Výzkumy also
// searches the studies on what their designs say (project memory M1d); the client is
// this page's.

import Link from "next/link";
import { type ReactNode, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type StudyKind, type WorkspaceStudy, workspace } from "@/lib/api";
import { relative } from "@/lib/format";
import { codeWords } from "@/lib/reason-words";
import { CodedWords } from "../../rehome/research/CodedWords";
import { STUDY_FILTERS, STUDY_SORTS, type StudyFilter, type StudySort, brought, countByFilter, inFilter, sortStudies } from "@/lib/study-table";
import { Icon } from "../../rehome/icons";
import { Chip, Select } from "../../rehome/ui";
import { MemorySearch } from "../MemorySearch";
import { Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { ClientPage, useClient } from "./ClientContext";
import { studyHref, studyWhere } from "./ClientOverview";

const TONE: Record<string, "running" | "done" | "neutral" | "you"> = {
  ACTIVE: "running",
  IN_REVIEW: "you",
  DELIVERED: "done",
};

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

export function StudyList({ kind }: { kind: StudyKind }) {
  const { client } = useClient();
  const [res, retry] = useResource(() => workspace.studies(client.client_id, kind), [client.client_id, kind]);
  const research = kind === "RESEARCH";
  return (
    <ClientPage>
      <h2 className="mb-3 text-base font-semibold">{research ? t("aia.studies.researchTitle") : t("aia.studies.simulationsTitle")}</h2>
      <ListOrSearch clientId={client.client_id} research={research}>
        <Loaded res={res} retry={retry}>
          {(list) =>
            list.length ? (
              <StudyTable clientId={client.client_id} studies={list} research={research} />
            ) : (
              <Empty>{research ? t("aia.studies.researchEmpty") : t("aia.studies.simulationsEmpty")}</Empty>
            )
          }
        </Loaded>
      </ListOrSearch>
    </ClientPage>
  );
}

function StudyTable({ clientId, studies, research }: { clientId: string; studies: WorkspaceStudy[]; research: boolean }) {
  const [filter, setFilter] = useState<StudyFilter>("current");
  const [sort, setSort] = useState<StudySort>("modified");
  const counts = countByFilter(studies);
  const shown = sortStudies(studies.filter((s) => inFilter(s, filter)), sort);
  const showKnowledge = studies.some((s) => s.knowledge != null);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div role="group" aria-label={t("aia.studies.filterLabel")} className="flex flex-wrap gap-1.5">
          {STUDY_FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
              className={`inline-flex min-h-8 items-center gap-1.5 rounded-pill border px-3 text-[13px] ${FOCUS} ${filter === f ? "border-signal bg-signal-wash font-semibold text-signal" : "border-border bg-surface-raised text-ink hover:border-border-strong"}`}
            >
              {t(`aia.studies.filters.${f}`)}{" "}
              <span className="font-mono text-[11px] text-ink-faint">{counts[f]}</span>
            </button>
          ))}
        </div>
        <label className="ml-auto flex items-center gap-2 text-[13px] text-ink-muted">
          {t("aia.studies.sortLabel")}
          <Select value={sort} onChange={(e) => setSort(e.target.value as StudySort)} className="w-auto">
            {STUDY_SORTS.map((o) => (
              <option key={o} value={o}>{t(`aia.studies.sorts.${o}`)}</option>
            ))}
          </Select>
        </label>
      </div>
      {shown.length ? (
        <div className="overflow-x-auto rounded-md border border-border bg-surface-raised">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">{research ? t("aia.studies.researchTitle") : t("aia.studies.simulationsTitle")}</caption>
            <thead>
              <tr className="border-b border-border bg-surface-sunken text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-ink-muted">
                <th scope="col" className="px-4 py-2">{t("aia.studies.columns.study")}</th>
                <th scope="col" className="px-4 py-2">{t("aia.studies.columns.status")}</th>
                {/* Below sm the row is the study, its status and what of it waits for a person (under the status);
                    what it brought and when it changed are in the wider table, so the row fits a phone. */}
                {showKnowledge ? <th scope="col" className="hidden px-4 py-2 sm:table-cell">{t("aia.studies.columns.brought")}</th> : null}
                <th scope="col" className="hidden px-4 py-2 text-right sm:table-cell">{t("aia.studies.columns.modified")}</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((s) => (
                <tr key={s.study_id} className="border-b border-border last:border-b-0 hover:bg-surface">
                  <td className="px-4 py-3 align-top">
                    <Link href={studyHref(clientId, s)} className={`flex items-start gap-3 rounded-sm no-underline ${FOCUS}`}>
                      <Icon name={research ? "research" : "simulation"} className="mt-0.5 shrink-0 text-ink-faint" />
                      <span className="min-w-0">
                        <span className="block font-medium text-ink underline-offset-2 hover:underline">{s.name}</span>
                        <span className="block text-[13px] text-ink-muted">{s.has_working_content || !research ? studyWhere(s) : t("aia.studies.notStarted")}</span>
                      </span>
                    </Link>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <Chip tone={TONE[s.status] ?? "neutral"}><CodedWords inline coded={codeWords("aia.status", s.status, "research.exec.phase.other")} /></Chip>
                    {showKnowledge && brought(s)?.waiting ? (
                      <span className="mt-1 block text-[13px] font-medium text-status-you-ink sm:hidden">
                        {tv("aia.studies.waitingNarrow", { n: brought(s)!.waiting })}
                      </span>
                    ) : null}
                  </td>
                  {showKnowledge ? <td className="hidden px-4 py-3 align-top text-[13px] sm:table-cell">{broughtCell(s)}</td> : null}
                  <td className="hidden whitespace-nowrap px-4 py-3 text-right align-top text-xs text-ink-faint sm:table-cell">{relative(s.modified_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty>{t(`aia.studies.filterEmpty.${filter}`)}</Empty>
      )}
    </div>
  );
}

function broughtCell(s: WorkspaceStudy): ReactNode {
  const b = brought(s);
  if (!b) return null;
  if (!b.accepted && !b.waiting) return <span className="text-ink-faint">{t("aia.studies.broughtNothing")}</span>;
  return (
    <span className="flex flex-wrap gap-x-2">
      {b.accepted ? <span>{tv("aia.studies.broughtAccepted", { n: b.accepted })}</span> : null}
      {b.waiting ? <span className="font-medium text-status-you-ink">{tv("aia.studies.broughtWaiting", { n: b.waiting })}</span> : null}
    </span>
  );
}

/** Výzkumy: the search above the list, the list while nothing is searched. Simulace: the list. */
function ListOrSearch({ clientId, research, children }: { clientId: string; research: boolean; children: ReactNode }) {
  if (!research) return <>{children}</>;
  return (
    <MemorySearch clientId={clientId} kind="RESEARCH">
      {children}
    </MemorySearch>
  );
}
