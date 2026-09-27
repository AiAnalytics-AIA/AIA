"use client";

// Výzkumy and Simulace: this client's studies of one kind, newest change first.

import Link from "next/link";

import { t } from "@/i18n/t";
import { type StudyKind, workspace } from "@/lib/api";
import { relative } from "@/lib/format";
import { Icon } from "../../rehome/icons";
import { Chip } from "../../rehome/ui";
import { Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { ClientPage, useClient } from "./ClientContext";
import { studyHref, studyWhere } from "./ClientOverview";

const TONE: Record<string, "running" | "done" | "neutral" | "you"> = {
  ACTIVE: "running",
  IN_REVIEW: "you",
  DELIVERED: "done",
};

export function StudyList({ kind }: { kind: StudyKind }) {
  const { client } = useClient();
  const [res, retry] = useResource(() => workspace.studies(client.client_id, kind), [client.client_id, kind]);
  const research = kind === "RESEARCH";
  return (
    <ClientPage>
      <h2 className="mb-3 text-base font-semibold">{research ? t("aia.studies.researchTitle") : t("aia.studies.simulationsTitle")}</h2>
      <Loaded res={res} retry={retry}>
        {(list) =>
          list.length ? (
            <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
              {list.map((s) => (
                <li key={s.study_id}>
                  <Link
                    href={studyHref(client.client_id, s)}
                    className="flex items-center gap-4 px-5 py-4 no-underline hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus-ring"
                  >
                    <Icon name={research ? "research" : "simulation"} className="text-ink-faint" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-ink">{s.name}</span>
                      <span className="block text-sm text-ink-muted">{s.has_working_content || !research ? studyWhere(s) : t("aia.studies.notStarted")}</span>
                    </span>
                    <Chip tone={TONE[s.status] ?? "neutral"}>{t(`aia.status.${s.status}`)}</Chip>
                    <span className="hidden w-28 text-right text-xs text-ink-faint sm:block">{relative(s.modified_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>{research ? t("aia.studies.researchEmpty") : t("aia.studies.simulationsEmpty")}</Empty>
          )
        }
      </Loaded>
    </ClientPage>
  );
}
