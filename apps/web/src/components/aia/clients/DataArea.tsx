"use client";

// Data: this client's own datasets, and -- kept apart, said as such -- what every
// study inherits from AIA's shared intelligence (ADR 0015 decision 7).

import Link from "next/link";

import { t, tv } from "@/i18n/t";
import { workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { relative } from "@/lib/format";
import { Tag } from "../../rehome/ui";
import { CARD, Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { ClientPage, useClient } from "./ClientContext";

export function DataArea() {
  const { client } = useClient();
  const mayView = client.permissions.includes("VIEW_CLIENT_KNOWLEDGE");
  const [res, retry] = useResource(
    () => (mayView ? workspace.knowledge(client.client_id, "data") : Promise.resolve([])),
    [client.client_id, mayView],
  );
  return (
    <ClientPage sub={t("aia.data.sub")}>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
        <section aria-labelledby="data-own">
          <h2 id="data-own" className="mb-3 text-base font-semibold">{t("aia.data.datasets")}</h2>
          {mayView ? (
            <Loaded res={res} retry={retry}>
              {(items) =>
                items.length ? (
                  <ul className="flex flex-col gap-2">
                    {items.map((i) => (
                      <li key={i.item_id} className={`${CARD} py-3`}>
                        <div className="flex items-start justify-between gap-2">
                          <span className="font-medium">{i.title}</span>
                          <Tag>{t(`aia.knowledge.kinds.${i.kind}`)}</Tag>
                        </div>
                        {i.summary ? <p className="mt-1 text-sm text-ink-muted">{i.summary}</p> : null}
                        <p className="mt-1 text-xs text-ink-faint">{tv("aia.knowledge.revision", { n: i.revision })} · {relative(i.modified_at)}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <Empty>{t("aia.data.empty")}</Empty>
                )
              }
            </Loaded>
          ) : (
            <Empty>{t("aia.knowledge.noAccess")}</Empty>
          )}
        </section>
        <section className={CARD} aria-labelledby="data-shared">
          <h2 id="data-shared" className="text-base font-semibold">{t("aia.data.inheritedTitle")}</h2>
          <p className="mt-2 text-sm leading-6 text-ink-muted">{t("aia.data.inheritedText")}</p>
          <Link href={appRoutes.intelligence()} className="mt-3 inline-block text-sm font-medium text-signal underline">
            {t("aia.data.openIntelligence")}
          </Link>
        </section>
      </div>
    </ClientPage>
  );
}
