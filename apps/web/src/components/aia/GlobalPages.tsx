"use client";

// The three global destinations besides Klienti (ADR 0015 decision 3):
// Společenská inteligence (the shared layer), Projektová paměť (your work across
// your clients) and Nastavení (account and administration). Execution
// infrastructure lives here, not in the primary navigation. There is no way into
// the 18.6.6 interface from any of them (ADR 0018): what AIA does not have yet
// says so where the person meets it.

import Link from "next/link";
import { useMemo, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type ClientCard, type PopulationRegistry, type WorkspaceStudy, population, workspace } from "@/lib/api";
import { labelOf, shortSha, summarize } from "@/lib/population";
import { appRoutes } from "@/lib/app-routes";
import { useSession } from "@/lib/auth";
import { relative } from "@/lib/format";
import { Icon } from "../rehome/icons";
import { Field, Tag, TextInput } from "../rehome/ui";
import { AppShell } from "./AppShell";
import { studyHref } from "./clients/ClientOverview";
import { CARD, Empty, Loaded } from "./states";
import { ControlPanel } from "./settings/ControlPanel";
import { useResource } from "./useResource";

export function IntelligencePage() {
  const [res, retry] = useResource(() => population.registry(), []);
  return (
    <AppShell title={t("aia.intelligence.title")} sub={t("aia.intelligence.sub")}>
      <section className={`${CARD} max-w-2xl`}>
        <p className="text-sm leading-6">{t("aia.intelligence.text")}</p>
        <p role="status" className="mt-4 rounded-sm border border-border bg-surface-sunken p-3 text-sm leading-6 text-ink">
          {t("aia.intelligence.notInAia")}
        </p>
      </section>
      <section className={`${CARD} mt-6 max-w-4xl`} aria-labelledby="pop-title">
        <h2 id="pop-title" className="text-base font-semibold">{t("aia.intelligence.population.title")}</h2>
        <p className="mt-1 text-sm leading-6 text-ink-muted">{t("aia.intelligence.population.text")}</p>
        <Loaded res={res} retry={retry}>
          {(registry) => <PopulationRegistryView registry={registry} />}
        </Loaded>
      </section>
    </AppShell>
  );
}

// The registry as a person reads it: which version LIVE is on, the reference, every
// version with where it stands, and every move. Nothing here writes (P2).
function PopulationRegistryView({ registry }: { registry: PopulationRegistry }) {
  if (!registry.versions.length) return <Empty>{t("aia.intelligence.population.empty")}</Empty>;
  const s = summarize(registry);
  const P = "aia.intelligence.population";
  return (
    <div className="mt-4 flex flex-col gap-5">
      <dl className="grid gap-3 sm:grid-cols-2">
        {[
          { label: t(`${P}.live`), v: s.live },
          { label: t(`${P}.reference`), v: s.reference },
        ].map(({ label, v }) => (
          <div key={label} className="rounded-sm border border-border p-3">
            <dt className="text-xs uppercase tracking-wide text-ink-faint">{label}</dt>
            <dd className="mt-1 text-sm text-ink">
              {v ? (
                <>
                  <span className="font-semibold">{v.label}</span> <span className="font-mono text-xs text-ink-faint">{shortSha(v.content_sha256)}</span>
                </>
              ) : (
                t(`${P}.none`)
              )}
            </dd>
          </div>
        ))}
      </dl>
      {s.candidates ? <p className="text-sm text-ink-muted">{tv(`${P}.candidates`, { n: s.candidates })}</p> : null}
      <div>
        <h3 className="mb-2 text-sm font-semibold">{t(`${P}.versions`)}</h3>
        <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
          {registry.versions.map((v) => (
            <li key={v.version_id} className="flex flex-wrap items-center gap-3 px-4 py-2 text-sm">
              <span className="font-semibold text-ink">{v.label}</span>
              <Tag>{t(`${P}.status.${v.status}`)}</Tag>
              <span className="font-mono text-xs text-ink-faint">{shortSha(v.content_sha256)}</span>
              <span className="text-xs text-ink-muted">{tv(`${P}.rows`, { n: v.row_count })}</span>
              {v.companions_attached ? null : <span className="text-xs text-ink-muted">{t(`${P}.companionsMissing`)}</span>}
              <span className="ml-auto text-xs text-ink-faint">{relative(v.imported_at)}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold">{t(`${P}.history`)}</h3>
        {s.history.length ? (
          <ul className="flex flex-col gap-1 text-sm">
            {s.history.map((h) => (
              <li key={`${h.population_id}-${h.promoted_at}-${h.to_version_id}`} className="flex flex-wrap gap-2">
                <span className="text-ink">
                  {tv(`${P}.moved`, { population: h.population_id, from: labelOf(registry, h.from_version_id), to: labelOf(registry, h.to_version_id) })}
                </span>
                <span className="text-ink-muted">{h.reason}</span>
                <span className="ml-auto text-xs text-ink-faint">{relative(h.promoted_at)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-muted">{t(`${P}.noHistory`)}</p>
        )}
      </div>
    </div>
  );
}

type Row = WorkspaceStudy & { clientName: string };

export function MemoryPage() {
  const [res, retry] = useResource(async () => {
    const clients: ClientCard[] = await workspace.clients();
    const lists = await Promise.all(clients.map((c) => workspace.studies(c.client_id).then((s) => s.map((x) => ({ ...x, clientName: c.name })))));
    return lists.flat();
  }, []);
  const [q, setQ] = useState("");
  const needle = q.trim().toLocaleLowerCase("cs");
  const filter = useMemo(() => (rows: Row[]) => (needle ? rows.filter((r) => `${r.name} ${r.clientName}`.toLocaleLowerCase("cs").includes(needle)) : rows), [needle]);
  return (
    <AppShell title={t("aia.memory.title")} sub={t("aia.memory.sub")}>
      <Field label={t("aia.memory.search")} className="mb-4 max-w-md">
        <TextInput type="search" value={q} onChange={(e) => setQ(e.target.value)} />
      </Field>
      <Loaded res={res} retry={retry}>
        {(rows) => {
          const shown = filter(rows);
          if (!shown.length) return <Empty>{t("aia.memory.empty")}</Empty>;
          const byClient = new Map<string, Row[]>();
          for (const r of shown) byClient.set(r.client_id, [...(byClient.get(r.client_id) ?? []), r]);
          return (
            <div className="flex flex-col gap-6">
              {[...byClient.entries()].map(([clientId, list]) => (
                <section key={clientId} aria-labelledby={`mem-${clientId}`}>
                  <h2 id={`mem-${clientId}`} className="mb-2 text-base font-semibold">
                    <Link href={appRoutes.client(clientId)} className="text-ink underline-offset-2 hover:underline">{list[0].clientName}</Link>
                  </h2>
                  <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
                    {list.map((s) => (
                      <li key={s.study_id}>
                        <Link href={studyHref(clientId, s)} className="flex items-center gap-3 px-5 py-3 no-underline hover:bg-surface">
                          <Icon name={s.kind === "SIMULATION" ? "simulation" : "research"} className="text-ink-faint" />
                          <span className="flex-1 text-ink">{s.name}</span>
                          <Tag>{t(`aia.status.${s.status}`)}</Tag>
                          <span className="w-28 text-right text-xs text-ink-faint">{relative(s.modified_at)}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          );
        }}
      </Loaded>
    </AppShell>
  );
}

export function SettingsPage() {
  const session = useSession();
  const [me] = useResource(() => workspace.me(), []);
  return (
    <AppShell title={t("aia.settings.title")} sub={t("aia.settings.sub")}>
      <div className="grid max-w-5xl gap-6 lg:grid-cols-2">
        <section className={CARD} aria-labelledby="set-account">
          <h2 id="set-account" className="text-base font-semibold">{t("aia.settings.account")}</h2>
          {session?.email ? <p className="mt-2 text-sm">{tv("aia.settings.signedInAs", { email: session.email })}</p> : null}
          {me.state === "ready" ? <p className="mt-1 text-sm text-ink-muted">{tv("aia.settings.orgRole", { role: t(`aia.orgRoles.${me.data.organization_role}`) })}</p> : null}
          <p className="mt-3 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm leading-6">{t("aia.settings.accessNote")}</p>
        </section>
      </div>
      <div className="mt-6">
        <ControlPanel />
      </div>
    </AppShell>
  );
}
