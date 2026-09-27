import type { ReactNode } from "react";
import { api, apiConfigured, type ApiResult } from "@/lib/api/server";
import type { AuditEntry, Client, Health, Member, SelfApprovalLevels, SettingsDocument, Study } from "@/lib/api/types";
import { t } from "@/i18n/t";
import { Section, Unavailable } from "@/components/settings/Section";
import { ControlBadge, SettingRow, Value } from "@/components/settings/SettingRow";
import {
  AuditPanel,
  ClientsPanel,
  DataClassesList,
  MembersPanel,
  ProvidersTable,
  RoleMatrix,
  SelfApprovalPanel,
  StagesList,
  StudiesPanel,
  type StudyRow,
} from "@/components/settings/LivePanels";

// Rendered per request: every value here is the server's current state.
export const dynamic = "force-dynamic";

// Groups with a dedicated panel, in page order. A group the API adds later still
// renders -- generically, after these -- so a new control is never hidden.
const ORDER = ["deployment", "access", "studies", "approvals", "ai", "residency", "workflow", "population", "evidence", "simulation"];

async function loadStudies(): Promise<ApiResult<StudyRow[]>> {
  const list = await api.get<Study[]>("/studies?include_archived=true");
  if (!list.ok) return list;
  // The list omits costs by design; the detail carries them only where the
  // caller may view costs, and a refusal is kept as a refusal, not a zero.
  const details = await Promise.all(list.data.map((s) => api.get<Study>(`/studies/${encodeURIComponent(s.study_id)}`)));
  return { ok: true, data: list.data.map((study, i) => ({ study, detail: details[i] })) };
}

export default async function SettingsPage() {
  if (!apiConfigured()) {
    return (
      <Page>
        <Unavailable what={t("settings.title")} reason={t("settings.notConnected")} />
      </Page>
    );
  }

  const [doc, health, ready] = await Promise.all([
    api.get<SettingsDocument>("/settings"),
    api.get<Health>("/health"),
    api.get<Health>("/ready"),
  ]);
  if (!doc.ok) {
    return (
      <Page>
        <Unavailable
          what={t("settings.title")}
          reason={`${doc.error.status === null ? "API nedostupné" : `HTTP ${doc.error.status}`} · ${doc.error.code}: ${doc.error.message}`}
        />
      </Page>
    );
  }

  const settings = doc.data;
  const admin = settings.may_administer;
  const vocab = settings.vocabularies;
  const [members, clients, studies, levels, audit] = await Promise.all([
    api.get<Member[]>("/members"),
    api.get<Client[]>("/clients?include_archived=true"),
    loadStudies(),
    admin ? api.get<SelfApprovalLevels>("/self-approval") : Promise.resolve(null),
    admin ? api.get<AuditEntry[]>("/access-audit?limit=50") : Promise.resolve(null),
  ]);

  const byKey = new Map(settings.groups.map((g) => [g.key, g]));
  const known = ORDER.filter((k) => byKey.has(k));
  const extra = settings.groups.map((g) => g.key).filter((k) => !ORDER.includes(k));
  const invariants = settings.groups.flatMap((g) => g.items.filter((i) => i.control === "INVARIANT"));

  const panels: Record<string, ReactNode> = {
    deployment: (
      <div className="flex flex-wrap gap-4 text-sm">
        <span>
          {t("settings.health.live")}: {health.ok ? <Value value={health.data.status} /> : <Value value={null} />}
        </span>
        <span>
          {t("settings.health.ready")}: {ready.ok ? <Value value={ready.data.status} /> : <span className="text-red-700">{ready.error.status ?? "—"} · {ready.error.code}</span>}
        </span>
      </div>
    ),
    access: (
      <>
        <MembersPanel members={members} vocab={vocab} canAdminister={admin} />
        <ClientsPanel clients={clients} members={members} vocab={vocab} canAdminister={admin} />
      </>
    ),
    studies: <StudiesPanel studies={studies} clients={clients} members={members} vocab={vocab} canAdminister={admin} />,
    approvals: <SelfApprovalPanel levels={levels} clients={clients} studies={studies} canAdminister={admin} />,
    ai: <ProvidersTable vocab={vocab} />,
    residency: <DataClassesList vocab={vocab} />,
    workflow: <StagesList vocab={vocab} />,
  };

  const nav = [
    ...known,
    ...extra,
    "roles",
    "audit",
    "invariants",
  ];

  return (
    <Page role={settings.your_role}>
      <div className="grid gap-6 lg:grid-cols-[200px_minmax(0,1fr)]">
        <nav aria-label={t("settings.title")} className="lg:sticky lg:top-20 lg:self-start">
          <ul className="space-y-0.5 text-sm">
            {nav.map((k) => (
              <li key={k}>
                <a href={`#${k}`} className="block rounded px-2 py-1 text-zinc-700 hover:bg-zinc-100">
                  {t(`settings.groups.${k}.title`)}
                </a>
              </li>
            ))}
          </ul>
          <div className="mt-4 space-y-1 border-t border-zinc-200 pt-3">
            {(["API", "DEPLOYMENT", "CODE", "INVARIANT"] as const).map((c) => (
              <div key={c} className="flex items-start gap-2 text-[11px] text-zinc-600">
                <ControlBadge control={c} />
                <span>{t(`settings.controlHelp.${c}`)}</span>
              </div>
            ))}
          </div>
        </nav>

        <div className="min-w-0 space-y-4">
          {[...known, ...extra].map((key) => {
            const group = byKey.get(key)!;
            return (
              <Section key={key} id={key} title={t(`settings.groups.${key}.title`)} intro={t(`settings.groups.${key}.intro`)}>
                {panels[key] ?? null}
                <div>
                  {group.items.map((item) => (
                    <SettingRow key={item.key} item={item} />
                  ))}
                </div>
              </Section>
            );
          })}

          <Section id="roles" title={t("settings.groups.roles.title")} intro={t("settings.groups.roles.intro")}>
            <RoleMatrix vocab={vocab} />
          </Section>

          <Section id="audit" title={t("settings.groups.audit.title")} intro={t("settings.groups.audit.intro")}>
            <AuditPanel audit={audit} members={members} />
          </Section>

          <Section id="invariants" title={t("settings.groups.invariants.title")} intro={t("settings.groups.invariants.intro")}>
            <div>
              {invariants.map((item) => (
                <SettingRow key={item.key} item={item} />
              ))}
            </div>
          </Section>
        </div>
      </div>
    </Page>
  );
}

function Page({ role, children }: { role?: string; children: ReactNode }) {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-zinc-900">{t("settings.title")}</h1>
        <p className="max-w-3xl text-sm text-zinc-600">
          {t("settings.intro")}
          {role ? (
            <>
              {" "}
              {t("settings.yourRole")}: <strong>{t(`settings.roles.${role}`)}</strong>.
            </>
          ) : null}
        </p>
      </header>
      {children}
    </div>
  );
}
