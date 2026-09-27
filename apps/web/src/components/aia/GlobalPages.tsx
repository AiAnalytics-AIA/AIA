"use client";

// The three global destinations besides Klienti (ADR 0015 decision 3):
// Společenská inteligence (the shared layer), Projektová paměť (your work across
// your clients) and Nastavení (account, administration, and the explicit ways
// into the classic interface). Execution infrastructure lives here, not in the
// primary navigation.

import Link from "next/link";
import { useMemo, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type ClientCard, type WorkspaceStudy, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import type { PublicConfig } from "@/app/config/route";
import { useSession } from "@/lib/auth";
import { relative } from "@/lib/format";
import { classicHref } from "@/lib/interface-handoff";
import { Icon } from "../rehome/icons";
import { ClassicLink, Field, Tag, TextInput } from "../rehome/ui";
import { AppShell } from "./AppShell";
import { studyHref } from "./clients/ClientOverview";
import { CARD, Empty, Loaded } from "./states";
import { ControlPanel } from "./settings/ControlPanel";
import { useResource } from "./useResource";

export function IntelligencePage() {
  return (
    <AppShell title={t("aia.intelligence.title")} sub={t("aia.intelligence.sub")}>
      <section className={`${CARD} max-w-2xl`}>
        <p className="text-sm leading-6">{t("aia.intelligence.text")}</p>
        <div className="mt-4">
          <ClassicLink href={classicHref({ switch: "library" })}>{t("aia.intelligence.openClassic")}</ClassicLink>
        </div>
      </section>
    </AppShell>
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
  const [runtime, retryRuntime] = useResource(async () => {
    const response = await fetch("/config", { cache: "no-store" });
    if (!response.ok) throw new Error(t("aia.settings.aiUnknown"));
    const config = await response.json() as PublicConfig;
    if (!config.aiRuntime) throw new Error(t("aia.settings.aiUnknown"));
    return config.aiRuntime;
  }, []);
  return (
    <AppShell title={t("aia.settings.title")} sub={t("aia.settings.sub")}>
      <div className="grid max-w-5xl gap-6 lg:grid-cols-2">
        <section className={CARD} aria-labelledby="set-account">
          <h2 id="set-account" className="text-base font-semibold">{t("aia.settings.account")}</h2>
          {session?.email ? <p className="mt-2 text-sm">{tv("aia.settings.signedInAs", { email: session.email })}</p> : null}
          {me.state === "ready" ? <p className="mt-1 text-sm text-ink-muted">{tv("aia.settings.orgRole", { role: t(`aia.orgRoles.${me.data.organization_role}`) })}</p> : null}
          <p className="mt-3 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm leading-6">{t("aia.settings.accessNote")}</p>
        </section>
        <section className={CARD} aria-labelledby="set-ai">
          <h2 id="set-ai" className="text-base font-semibold">Amazon Bedrock</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("aia.settings.aiManaged")}</p>
          <Loaded res={runtime} retry={retryRuntime}>
            {(ai) => (
              <div className="mt-3 space-y-2 text-sm">
                <p>{t(ai.enabled === null ? "aia.settings.aiInvalid" : ai.enabled ? "aia.settings.aiEnabled" : "aia.settings.aiDisabled")}</p>
                {ai.region ? <p>{tv("aia.settings.aiRegion", { region: ai.region })}</p> : null}
                {ai.model ? <p className="break-all">{tv("aia.settings.aiModel", { model: ai.model })}</p> : null}
                <p className="text-ink-muted">{t(ai.researchAgentsEnabled === null ? "aia.settings.aiDesignInvalid" : ai.researchAgentsEnabled ? "aia.settings.aiDesignEnabled" : "aia.settings.aiDesignDisabled")}</p>
                <p className="text-xs text-ink-faint">{t("aia.settings.aiConfigOnly")}</p>
              </div>
            )}
          </Loaded>
        </section>
        <section className={CARD} aria-labelledby="set-classic">
          <h2 id="set-classic" className="text-base font-semibold">{t("aia.settings.classic")}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("aia.settings.classicText")}</p>
          <ul className="mt-3 flex flex-col gap-2">
            <li><ClassicLink href={classicHref({ support: "bundle" })}>{t("aia.settings.diagnostics")}</ClassicLink></li>
          </ul>
          <div className="mt-4 border-t border-border pt-4">
            <Link href={appRoutes.classicProjects()} className="text-sm font-medium text-signal underline">{t("aia.settings.classicProjects")}</Link>
            <p className="mt-1 text-xs text-ink-faint">{t("aia.settings.classicProjectsText")}</p>
          </div>
        </section>
      </div>
      <div className="mt-6">
        <ControlPanel />
      </div>
    </AppShell>
  );
}
