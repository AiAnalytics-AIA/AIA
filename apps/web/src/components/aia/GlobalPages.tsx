"use client";

// The three global destinations besides Klienti (ADR 0015 decision 3):
// Společenská inteligence (the shared layer), Projektová paměť (your work across
// your clients) and Nastavení (account and administration). Execution
// infrastructure lives here, not in the primary navigation. There is no way into
// the 18.6.6 interface from any of them (ADR 0018): what AIA does not have yet
// says so where the person meets it.

import Link from "next/link";
import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { type ClientCard, type PopulationRegistry, population, workspace } from "@/lib/api";
import { children, labelOf, outcomeValue, sharedVersions, shortSha, summarize, targetVerdict } from "@/lib/population";
import { appRoutes } from "@/lib/app-routes";
import { useSession } from "@/lib/auth";
import { relative } from "@/lib/format";
import { Field, Select, Tag } from "../rehome/ui";
import { AppShell } from "./AppShell";
import { MemorySearch } from "./MemorySearch";
import { PopulationCharacteristicsSection } from "./PopulationCharacteristics";
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
          {(registry) => (
            <>
              <PopulationRegistryView registry={registry} />
              {children(registry).length ? <MaterializedChildren registry={registry} /> : null}
              <PopulationCharacteristicsSection registry={registry} />
            </>
          )}
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
          {sharedVersions(registry).map((v) => (
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

// The organization's materialized dimensions (P4d4): each child with the target it was asked
// for beside what its derivation achieved. A target the derivation left unmet says so; a child
// without a recorded outcome says that, never "met".
function MaterializedChildren({ registry }: { registry: PopulationRegistry }) {
  const owned = children(registry);
  const [clientsRes] = useResource(() => workspace.clients(), []);
  const P = "aia.intelligence.population.children";
  const clientName = (id: string | null) =>
    (clientsRes.state === "ready" ? clientsRes.data.find((c) => c.client_id === id)?.name : undefined) ?? id ?? "—";
  return (
    <div className="mt-5">
      <h3 className="mb-1 text-sm font-semibold">{t(`${P}.title`)}</h3>
      <p className="mb-2 text-sm leading-6 text-ink-muted">{t(`${P}.text`)}</p>
      <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
        {owned.map((v) => {
          const m = v.materialized ?? null;
          const verdict = targetVerdict(m);
          return (
            <li key={v.version_id} className="flex flex-col gap-1 px-4 py-2 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-semibold text-ink">{m?.dimension_id ?? v.label}</span>
                <Tag>{t(`${P}.verdict.${verdict}`)}</Tag>
                <span className="text-xs text-ink-muted">{tv(`${P}.client`, { client: clientName(v.owner_client_id) })}</span>
                <span className="ml-auto text-xs text-ink-faint">{relative(v.imported_at)}</span>
              </div>
              {m ? (
                <p className="text-ink">
                  {tv(`${P}.outcome`, { target: outcomeValue(m.kind, m.target), achieved: outcomeValue(m.kind, m.achieved) })}
                  {verdict === "unmet" ? <span className="text-ink-muted"> · {t(`${P}.unmetNote`)}</span> : null}
                </p>
              ) : (
                <p className="text-ink-muted">{t(`${P}.noOutcome`)}</p>
              )}
              <p className="text-xs text-ink-faint">
                {tv(`${P}.over`, { base: labelOf(registry, v.parent_version_id) })} · <span className="font-mono">{shortSha(v.content_sha256)}</span>
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function MemoryPage() {
  const [res, retry] = useResource(() => workspace.clients(), []);
  const [clientId, setClientId] = useState("");
  return (
    <AppShell title={t("aia.memory.title")} sub={t("aia.memory.sub")}>
      <Loaded res={res} retry={retry}>
        {(clients: ClientCard[]) => {
          if (!clients.length) return <Empty>{t("aia.memory.empty")}</Empty>;
          return (
            <div className="flex flex-col gap-4">
              <Field label={t("aia.memory.client")} className="max-w-md">
                <Select value={clientId} onChange={(e) => setClientId(e.target.value)}>
                  <option value="">{t("aia.memory.chooseClient")}</option>
                  {clients.map((c) => (
                    <option key={c.client_id} value={c.client_id}>{c.name}</option>
                  ))}
                </Select>
              </Field>
              {clientId ? (
                <MemorySearch key={clientId} clientId={clientId}>
                  <p className="text-sm text-ink-muted">
                    <Link href={appRoutes.client(clientId)} className="text-ink underline-offset-2 hover:underline">
                      {clients.find((c) => c.client_id === clientId)?.name}
                    </Link>{" "}
                    · {t("aia.memory.typeMore")}
                  </p>
                </MemorySearch>
              ) : (
                <p className="text-sm text-ink-muted">{t("aia.memory.pickClient")}</p>
              )}
            </div>
          );
        }}
      </Loaded>
    </AppShell>
  );
}

export function SettingsPage() {
  const session = useSession();
  const [me, rereadMe] = useResource(() => workspace.me(), []);
  // "Organizace <name> / Nastavení", as the prototype's top bar; a name the API did not send is
  // left out, never guessed.
  const organization = me.state === "ready" ? me.data.organization_name : null;
  const crumbs = organization ? [{ prefix: t("aia.settings.organization"), label: organization }, { label: t("aia.settings.title") }] : [{ label: t("aia.settings.title") }];
  return (
    <AppShell title={t("aia.settings.title")} crumbs={crumbs} topbar bleed>
      <ControlPanel me={me} rereadMe={rereadMe} footer={
        <details className="mt-6 border-t border-border pt-3 text-sm text-ink-muted">
          <summary className="cursor-pointer font-medium"><span>{t("aia.settings.account")}</span>{session?.email ? <span className="font-normal"> · {session.email}</span> : null}</summary>
          {me.state === "ready" ? <p className="mt-2">{tv("aia.settings.orgRole", { role: t(`aia.orgRoles.${me.data.organization_role}`) })}</p> : null}
          <p className="mt-1">{t("aia.settings.accessNote")}</p>
        </details>
      } />
    </AppShell>
  );
}
