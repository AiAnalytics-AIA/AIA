"use client";

// The settings page's control panel: every control AIA has, its current value,
// and how it is changed (GET /api/v1/settings). An API control is a live form
// over an existing route, sent with the signed-in bearer token; a deployment
// variable, a code constant and an invariant are shown, never offered as a
// switch. The API decides what is allowed -- its refusal is shown as given.
//
// What powers AIA's model calls is two sources side by side: the settings
// document's `ai_runtime` (from code) and /config's switches (from the
// deployment). Neither is a connection, and the page says so.

import Link from "next/link";
import { type KeyboardEvent, type ReactNode, memo, useEffect, useState } from "react";

import type { PublicConfig } from "@/lib/public-config";
import { t, tv } from "@/i18n/t";
import { type ActivityState, type SwitchValues, activityState, approvedClasses } from "@/lib/ai-runtime";
import {
  type AdminClient,
  type AuditEntry,
  type Member,
  type NativeActivity,
  type NativeRuntime,
  type SelfApprovalLevels,
  type SettingControl,
  type SettingItem,
  type SettingValue,
  type SettingsDocument,
  type Study,
  type Vocabularies,
  Unauthenticated,
  admin,
} from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { nearLimitTally } from "@/lib/researcher-spend";
import { ClientsCard, MembersCard, SelfApprovalCard } from "./AccessPanel";
import { describeMemberError } from "./errors";
import { DeepResearchSettingsPanel } from "./DeepResearchSettingsPanel";
import { MethodologyPanel } from "./MethodologyPanel";
import { ResearcherSpendCard } from "./ResearcherSpendCard";
import { StudiesTable } from "./StudiesPanel";
import { SETTING_HELP, TAB_GUIDE } from "./settings-guide";
import { SystemPromptsPanel } from "./SystemPromptsPanel";
import { Technical, TechnicalProvider, TechnicalSwitch, useTechnicalChoice } from "./technical";
import { Activity, BookOpen, Cpu, Database, History, type LucideIcon, ScrollText, Sigma, Telescope, Users, Wallet } from "lucide-react";
import { Icon, type IconName } from "../../rehome/icons";
import { Chip, Select, Tag, TextInput } from "../../rehome/ui";
import { CARD, EYEBROW, Empty, Loaded } from "../states";
import { useResource } from "../useResource";

const P = "aia.settings.panel";
const R = `${P}.runtime`;
const H = `${P}.history`;

// ---------------------------------------------------------------- loading

/** One part of the panel: its data, or why it is missing. A part never blanks the page. */
export type Part<T> = { ok: true; data: T } | { ok: false; message: string };

const describe = describeMemberError;

async function part<T>(p: Promise<T>): Promise<Part<T>> {
  try {
    return { ok: true, data: await p };
  } catch (e) {
    // Signed out is not a missing part: the page sends the person to sign in.
    if (e instanceof Unauthenticated) throw e;
    return { ok: false, message: describe(e) };
  }
}

export type StudyRow = { study: Study; detail: Part<Study> };

/** The deployment's AI configuration as /config reports it: a display, never a health check. */
export type RuntimeConfig = { switches: SwitchValues; region: string | null; model: string | null; approvedClasses: string[] };

export type Panel = {
  doc: SettingsDocument;
  runtime: Part<RuntimeConfig>;
  members: Part<Member[]>;
  clients: Part<AdminClient[]>;
  studies: Part<StudyRow[]>;
  levels: Part<SelfApprovalLevels> | null; // null: not an administrator, so not asked
  audit: Part<AuditEntry[]> | null;
};

async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  const response = await fetch("/config", { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const ai = ((await response.json()) as Partial<PublicConfig>).aiRuntime;
  // Without the switches there is nothing to read a state from: unknown, never "off".
  if (!ai || !ai.switches || typeof ai.switches !== "object" || !Array.isArray(ai.approvedClasses)) {
    throw new Error(t(`${R}.configMissing`));
  }
  return { switches: ai.switches, region: ai.region ?? null, model: ai.model ?? null, approvedClasses: ai.approvedClasses };
}

async function loadPanel(): Promise<Panel> {
  const doc = await admin.settings();
  // A document without its groups is not a settings document; say so rather than
  // render an empty page that looks like "no settings".
  if (!doc || !Array.isArray(doc.groups) || !doc.vocabularies || !doc.ai_runtime) throw new Error(t(`${P}.malformed`));
  const loadStudies = async (): Promise<StudyRow[]> => {
    const list = await admin.studies();
    // The list omits costs by design; the detail carries them only where the caller
    // may view costs, and a refusal stays a refusal -- never a zero.
    const details = await Promise.all(list.map((s) => part(admin.study(s.study_id))));
    return list.map((study, i) => ({ study, detail: details[i] }));
  };
  const [runtime, members, clients, studies, levels, audit] = await Promise.all([
    part(loadRuntimeConfig()),
    part(admin.members()),
    part(admin.clients()),
    part(loadStudies()),
    doc.may_administer ? part(admin.selfApproval()) : Promise.resolve(null),
    doc.may_administer ? part(admin.audit(50)) : Promise.resolve(null),
  ]);
  return { doc, runtime, members, clients, studies, levels, audit };
}

// ---------------------------------------------------------------- atoms

const CONTROL_ICON: Record<SettingControl, IconName> = {
  API: "settings",
  DEPLOYMENT: "command",
  CODE: "library",
  INVARIANT: "pin",
};

/** How a setting is changed. Icon and word, so it reads in greyscale too. */
function ControlBadge({ control }: { control: SettingControl }) {
  return (
    <span title={t(`${P}.controlHelp.${control}`)} data-control={control} className="inline-flex shrink-0">
      <Tag icon={CONTROL_ICON[control]}>{t(`${P}.control.${control}`)}</Tag>
    </span>
  );
}

/** A value. Null is "not configured" and looks like it: never blank, never zero. */
function Value({ value, unit }: { value: SettingValue; unit?: string | null }) {
  if (value === null) {
    return (
      <span data-value="null" className="rounded-sm border border-dashed border-border-strong px-1.5 text-xs text-ink-muted">
        ∅ {t(`${P}.notConfigured`)}
      </span>
    );
  }
  if (typeof value === "boolean") return <span className="font-mono text-sm">{t(value ? `${P}.yes` : `${P}.no`)}</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <span className="text-xs text-ink-muted">{t(`${P}.emptyList`)}</span>;
    return (
      <span className="flex flex-wrap gap-1">
        {value.map((v) => <code key={v} className="rounded-sm bg-surface-sunken px-1.5 text-xs">{v}</code>)}
      </span>
    );
  }
  return (
    <span className="font-mono text-sm tabular-nums">
      {typeof value === "number" ? new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: unit === "USD" ? 2 : 6 }).format(value) : String(value)}
      {unit ? <span className="ml-1 text-xs text-ink-faint">{unit}</span> : null}
    </span>
  );
}

// Where an API control's form lives, when it is not in this panel. The generic
// project's provider fields have no screen at all: only its API stores them.
const ELSEWHERE: Record<string, "clients" | "projectApi"> = {
  clients: "clients",
  studies: "clients",
  project_max_api_cost: "projectApi",
  project_provider_policy: "projectApi",
};

function ApiHint({ item }: { item: SettingItem }) {
  const where = ELSEWHERE[item.key];
  if (where === "clients") {
    return <Link href={appRoutes.clients()} className="text-xs text-signal underline">{t(`${P}.inClients`)}</Link>;
  }
  return <span className="text-xs text-ink-muted">{t(where === "projectApi" ? `${P}.onProjectApi` : `${P}.inPanel`)}</span>;
}

function SettingRow({ item }: { item: SettingItem }) {
  return (
    <div data-setting={item.key} className="grid grid-cols-1 gap-1 border-t border-border py-2 first:border-t-0 md:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_auto] md:items-center md:gap-4">
      <div className="min-w-0">
        <div className="text-sm font-medium text-ink">{t(`${P}.items.${item.key}`).startsWith(P) ? item.key.replaceAll("_", " ") : t(`${P}.items.${item.key}`)}</div>
        {SETTING_HELP[item.key] ? <p className="mt-1 text-xs leading-5 text-ink-muted">{SETTING_HELP[item.key]}</p> : null}
        <Technical><code data-technical className="mt-1 block break-all text-xs text-ink-faint">{item.source}</code></Technical>
      </div>
      <div className="min-w-0">{item.control === "API" ? <ApiHint item={item} /> : <Value value={item.value} unit={item.unit} />}</div>
      <ControlBadge control={item.control} />
    </div>
  );
}

function Unavailable({ what, message }: { what: string; message: string }) {
  return (
    <p role="alert" className="rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-ink">
      <span className="font-semibold text-status-fault">{tv(`${P}.unavailable`, { what })}</span> {message}
    </p>
  );
}

/** One group of a tab: its heading and one sentence, then its content. Nothing is collapsed. A
 *  group named like its tab keeps its heading for the outline only: the tab's header says it. */
function Section({ id, tab, children }: { id: string; tab?: TabId; children: ReactNode }) {
  const title = t(`${P}.groups.${id}.title`).startsWith(P) ? id.replaceAll("_", " ") : t(`${P}.groups.${id}.title`);
  const heading = <h2 id={`set-${id}-h`} className={tab && title === t(`${P}.tabs.${tab}`) ? "sr-only" : "text-base font-semibold"}>{title}</h2>;
  const intro = t(`${P}.groups.${id}.intro`);
  return <section id={`set-${id}`} aria-labelledby={`set-${id}-h`} className={`${CARD} min-w-0 scroll-mt-20`}>
    {heading}
    {intro.startsWith(P) ? null : <p className="mt-1 max-w-3xl text-sm leading-6 text-ink-muted">{intro}</p>}
    <div className="mt-4 flex flex-col gap-4">{children}</div>
  </section>;
}

function Sub({ children }: { children: ReactNode }) {
  return <h3 className={EYEBROW}>{children}</h3>;
}

const TH = "px-2 py-1 text-left font-mono text-[11px] font-normal uppercase tracking-[0.08em] text-ink-faint";
const TD = "px-2 py-1.5 align-top text-sm";
// Below sm a column that would push a row's action out of view: its content is shown in the row's first cell or not at all.

// ---------------------------------------------------------------- actions

// ---------------------------------------------------------------- panels

// ---- what powers AIA: code facts beside the deployment's switches --------

const STATE_TONE = { configured: "neutral", off: "world", invalid: "fault", unknown: "neutral" } as const satisfies Record<ActivityState["kind"], "neutral" | "world" | "fault">;

/** Why an activity stands where it does, in words. Never "connected" or "verified". */
function reasonFor(state: ActivityState, activity: NativeActivity): string {
  switch (state.kind) {
    case "configured":
      return t(`${R}.reason.configured`);
    case "off":
      return `${t(`${R}.reason.off`)} ${t(`${R}.activity.${activity.key}.off`)}`;
    case "invalid":
      return state.needs ? t(`${R}.reason.needs`) : t(`${R}.reason.invalid`);
    case "unknown":
      return state.switch ? t(`${R}.reason.unknown`) : t(`${R}.reason.unknownConfig`);
  }
}

/** Which deployment switch a state is about: technical detail. */
function switchFor(state: ActivityState): string | null {
  if (state.kind === "configured") return null;
  if (state.kind === "invalid" && state.needs) return tv(`${R}.reason.switchNeeds`, { switch: state.switch, needs: state.needs });
  return state.switch ? tv(`${R}.reason.switchNamed`, { switch: state.switch }) : null;
}

function Codes({ ids, title }: { ids: string[]; title?: (id: string) => string }) {
  return (
    <span className="flex flex-wrap gap-1">
      {ids.map((id) => <code key={id} title={title?.(id)} className="min-w-0 break-all rounded-sm bg-surface-sunken px-1.5 text-xs">{id}</code>)}
    </span>
  );
}

function SwitchWord({ value }: { value: boolean | null | undefined }) {
  if (value === undefined) return <Value value={null} />;
  return <span className="font-mono text-sm">{t(`${R}.switchValue.${value === null ? "invalid" : value ? "on" : "off"}`)}</span>;
}

function ConfigRow({ label, source, children }: { label: string; source: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 border-t border-border py-2 first:border-t-0 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:items-center md:gap-4">
      <div className="min-w-0">
        <div className="text-sm text-ink">{label}</div>
        <Technical><code className="break-all text-[11px] text-ink-faint">{source}</code></Technical>
      </div>
      <div className="min-w-0 break-all">{children}</div>
    </div>
  );
}

function ActivityRow({ runtime, activity, switches }: { runtime: NativeRuntime; activity: NativeActivity; switches: SwitchValues | null }) {
  const state = activityState(runtime, activity, switches);
  const A = `${R}.activity.${activity.key}`;
  const named = switchFor(state);
  return (
    <tr data-activity={activity.key} data-state={state.kind}>
      <td className={`${TD} min-w-48`}>
        <h3 className="text-sm font-semibold text-ink">{t(`${A}.title`)}</h3>
        <p className="mt-0.5 text-[13px] leading-5 text-ink-muted">{t(`${A}.text`)}</p>
      </td>
      <td className={`${TD} whitespace-nowrap`}><Chip tone={STATE_TONE[state.kind]}>{t(`${R}.state.${state.kind}`)}</Chip></td>
      <td className={TD}>
        <p data-reason className="break-words text-sm text-ink">{reasonFor(state, activity)}</p>
        <Technical>
          <dl data-technical className="mt-2 grid grid-cols-1 gap-x-3 gap-y-1 text-xs sm:grid-cols-[auto_minmax(0,1fr)]">
            {named ? <><dt className="text-ink-faint">{t(`${R}.col.switches`)}</dt><dd className="break-all font-mono">{named}</dd></> : null}
            {activity.actions.length ? <><dt className="text-ink-faint">{t(`${R}.actions`)}</dt><dd>{activity.actions.map((a) => t(`${R}.action.${a}`)).join(", ")}</dd></> : null}
            <dt className="text-ink-faint">{t(`${R}.col.uses`)}</dt>
            <dd><Codes ids={activity.capabilities} title={(c) => t(`${P}.capability.${c}`)} /></dd>
            <dt className="text-ink-faint">{t(`${R}.col.versions`)}</dt>
            <dd className="flex flex-col gap-0.5">{activity.versions.map((v) => <span key={v.name}>{t(`${R}.version.${v.name}`)} <code className="break-all">{v.value}</code></span>)}</dd>
          </dl>
        </Technical>
      </td>
    </tr>
  );
}

/** Code facts from the settings document beside the deployment's switches from /config. */
function RuntimePanel({ runtime, config, vocab }: { runtime: NativeRuntime; config: Part<RuntimeConfig>; vocab: Vocabularies }) {
  const switches = config.ok ? config.data.switches : null;
  const providers = runtime.providers.map((p) => p.label).join(", ");
  return (
    <div className="flex flex-col gap-4">
      <div className="flex max-w-3xl flex-col gap-1 text-sm">
        <p>{tv(`${R}.powers`, { provider: providers })}</p>
        <p>{t(`${R}.credential.${runtime.credential}`)}</p>
      </div>
      <div className="flex flex-col gap-2">
        <Sub>{t(`${R}.activities`)}</Sub>
        <div className="overflow-x-auto"><table className="w-full">
          <thead><tr><th className={TH}>{t(`${P}.col.capability`)}</th><th className={TH}>{t(`${P}.col.state`)}</th><th className={TH}>{t(`${P}.col.why`)}</th></tr></thead>
          <tbody className="divide-y divide-border">{runtime.activities.map((a) => <ActivityRow key={a.key} runtime={runtime} activity={a} switches={switches} />)}</tbody>
        </table></div>
        {runtime.unused_capabilities.length ? (
          <Technical>
            <div data-activity="unused" className="rounded-sm border border-dashed border-border-strong p-3 text-sm">
              <span className="font-medium text-ink">{t(`${R}.unused`)}:</span>{" "}
              <Codes ids={runtime.unused_capabilities} title={(c) => t(`${P}.capability.${c}`)} />
              <p className="mt-1 text-xs text-ink-muted">{t(`${R}.unusedText`)}</p>
            </div>
          </Technical>
        ) : null}
      </div>
      <div data-config className="rounded-sm border border-border p-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <Sub>{t(`${R}.config`)}</Sub>
          <Technical><span className="text-[11px] text-ink-faint">{t(`${R}.configSource`)}</span></Technical>
        </div>
        {config.ok ? (
          <div className="mt-1">
            <ConfigRow label={t(`${R}.switchLabel`)} source={runtime.switch}><SwitchWord value={config.data.switches[runtime.switch]} /></ConfigRow>
            <ConfigRow label={t(`${R}.region`)} source="AIA_BEDROCK_REGION"><Value value={config.data.region} /></ConfigRow>
            <ConfigRow label={t(`${R}.model`)} source="AIA_BEDROCK_MODEL_ID"><Value value={config.data.model} /></ConfigRow>
            <ConfigRow label={t(`${R}.approved`)} source="AIA_AI_ROUTE_APPROVED_FOR">
              {config.data.approvedClasses.length ? (
                <ul className="flex flex-col gap-0.5">
                  {approvedClasses(config.data.approvedClasses, vocab.data_classes).map((c) => (
                    <li key={c.id} className="text-sm">
                      <Technical><code className="mr-1 text-xs">{c.id}</code></Technical>
                      <span className={c.known ? "text-ink" : "text-status-fault"}>{c.known ? t(`${P}.dataClass.${c.id}`) : `${c.id}: ${t(`${R}.unknownClass`)}`}</span>
                    </li>
                  ))}
                </ul>
              ) : <span className="text-sm text-ink-muted">{t(`${R}.approvedNone`)}</span>}
            </ConfigRow>
          </div>
        ) : <Unavailable what={t(`${R}.config`)} message={`${config.message} ${t(`${R}.configUnavailable`)}`} />}
      </div>
      <p role="note" data-not-verified className="rounded-sm border border-border bg-surface-sunken p-3 text-sm text-ink">{t(`${R}.notVerified`)}</p>
    </div>
  );
}

/** The prototype's identifiers, for reading older records. Collapsed: nothing here is a choice. */
function HistoryPanel({ vocab, items }: { vocab: Vocabularies; items: SettingItem[] }) {
  const historical = vocab.providers.filter((p) => p.use === "HISTORICAL");
  return (
    <div data-history className="rounded-sm border border-border">
      <p className="px-3 py-2 text-sm font-medium text-ink">{t(`${H}.show`)}</p>
      <div className="grid gap-4 border-t border-border p-3 lg:grid-cols-2">
        <div>
          <Sub>{t(`${H}.providers`)}</Sub>
          <ul className="mt-1 flex flex-col gap-1">
            {historical.map((p) => (
              <li key={p.id} data-provider={p.id} className="text-sm">
                {p.label} <code className="text-xs text-ink-faint">{p.id}</code>{" "}
                <span className="text-xs text-ink-faint">· {t(p.paid ? `${H}.paid` : `${H}.subscription`)}</span>
                <p className="text-xs text-ink-muted">{t(`${H}.provider.${p.id}`)}</p>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <Sub>{t(`${H}.policies`)}</Sub>
          <ul className="mt-1 flex flex-col gap-1">
            {vocab.provider_policies.map((id) => <li key={id} className="text-sm"><code className="text-xs">{id}</code> <span className="text-xs text-ink-muted">— {t(`${P}.policy.${id}`)}</span></li>)}
          </ul>
        </div>
        <div className="lg:col-span-2">
          <Sub>{t(`${H}.fields`)}</Sub>
          <div>{items.map((item) => <SettingRow key={item.key} item={item} />)}</div>
        </div>
      </div>
    </div>
  );
}

function DataClasses({ vocab }: { vocab: Vocabularies }) {
  return (
    <div>
      <Sub>{t(`${P}.residency.classes`)}</Sub>
      <ul className="mt-1 flex flex-col gap-1">
        {vocab.data_classes.map((c) => <li key={c} className="text-sm"><code className="text-xs">{c}</code> <span className="text-xs text-ink-muted">— {t(`${P}.dataClass.${c}`)}</span></li>)}
      </ul>
    </div>
  );
}

function Stages({ vocab }: { vocab: Vocabularies }) {
  const col = (title: string, stages: Vocabularies["research_stages"]) => (
    <div>
      <Sub>{title}</Sub>
      <ol className="mt-1 list-decimal pl-5 text-sm">
        {stages.map((s) => <li key={s.id}>{s.label ?? s.id} <code className="text-[11px] text-ink-faint">{s.id}</code></li>)}
      </ol>
    </div>
  );
  return <div className="grid gap-4 md:grid-cols-2">{col(t(`${P}.stages.research`), vocab.research_stages)}{col(t(`${P}.stages.simulation`), vocab.simulation_stages)}</div>;
}

function RoleMatrix({ vocab }: { vocab: Vocabularies }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead><tr><th className={TH}>{t(`${P}.roles.permission`)}</th>{vocab.scope_roles.map((r) => <th key={r.role} className={TH}>{t(`aia.roles.${r.role}`)}</th>)}</tr></thead>
        <tbody className="divide-y divide-border">
          {vocab.permissions.map((p) => (
            <tr key={p}>
              <td className={TD}><code className="text-xs">{p}</code></td>
              {vocab.scope_roles.map((r) => (
                <td key={r.role} className={TD}>
                  {r.permissions.includes(p)
                    ? <span aria-label={t(`${P}.yes`)}><Icon name="done" size={14} /></span>
                    : <span aria-label={t(`${P}.no`)} className="text-ink-faint">—</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditPanel({ audit, members }: { audit: Part<AuditEntry[]> | null; members: Part<Member[]> }) {
  const [query, setQuery] = useState("");
  const [actor, setActor] = useState("");
  const [event, setEvent] = useState("");
  if (audit === null) return <p className="text-sm text-ink-muted">{t(`${P}.audit.adminOnly`)}</p>;
  if (!audit.ok) return <Unavailable what={t(`${P}.groups.audit.title`)} message={audit.message} />;
  if (!audit.data.length) return <Empty>{t(`${P}.audit.none`)}</Empty>;
  const who = new Map(members.ok ? members.data.map((m) => [m.user_id, m.email]) : []);
  const person = (id: string | null) => (id ? (who.get(id) ?? id) : "—");
  const names: Record<string, string> = { MEMBER_ADDED: "Přidání nebo úprava člena", USER_DEACTIVATED: "Deaktivace uživatele", CLIENT_CREATED: "Založení klienta", CLIENT_STATUS_CHANGED: "Změna stavu klienta", STUDY_CREATED: "Založení studie", STUDY_STATUS_CHANGED: "Změna stavu studie", STUDY_BUDGET_CHANGED: "Změna rozpočtu studie", STUDY_SPEND_CONFIRM_CHANGED: "Změna potvrzení útraty", SELF_APPROVAL_CONFIGURED: "Nastavení samoschválení", AIA_SESSION: "Přihlášení do AIA", PROMPT_ACTIVATED: "Aktivace systémového promptu", PROMPT_VERSION_CREATED: "Nová verze promptu", DR_TEST_POLICY_APPROVED: "Schválení testovacích pravidel rešerše", DR_TEST_POLICY_PROPOSED: "Návrh testovacích pravidel rešerše", CLIENT_GRANT: "Záznam přístupu ke klientovi", SELF_APPROVAL_CHANGED: "Změna samoschválení", ORGANIZATION_CREATED: "Založení organizace", AIA_SESSION_DENIED: "Odmítnuté přihlášení do AIA", MEMBER_ROLE_DENIED: "Odmítnutá změna role", IDENTITY_SUBJECT_CLEARED: "Uvolnění přihlašovací identity", PERMISSION_DENIED: "Odmítnutá akce", PROMPT_RESET_TO_BASELINE: "Návrat promptu na text z kódu", DR_SETTING_PROPOSED: "Návrh pravidla rešerše", DR_SETTING_APPROVED: "Schválení pravidla rešerše", DR_SETTING_WITHDRAWN: "Návrat pravidla rešerše na výchozí", METHODOLOGY_PROPOSED: "Nová verze metodiky", METHODOLOGY_ACTIVATED: "Uvedení metodiky v platnost", METHODOLOGY_RESET: "Návrat metodiky na verzi z kódu", CLIENT_KNOWLEDGE_AUTHORED: "Zápis znalosti klienta", CLIENT_KNOWLEDGE_DECIDED: "Rozhodnutí o návrhu znalosti", METHODOLOGIST_GRANTED: "Udělení značky Metodik", METHODOLOGIST_REVOKED: "Odebrání značky Metodik" };
  const actors = [...new Set(audit.data.map((entry) => entry.actor_id).filter((id): id is string => !!id))].sort((left, right) => person(left).localeCompare(person(right), "cs"));
  const events = [...new Set(audit.data.map((entry) => entry.action))].sort((left, right) => (names[left] ?? left).localeCompare(names[right] ?? right, "cs"));
  const visible = audit.data.filter((e) => (!actor || e.actor_id === actor) && (!event || e.action === event) && `${names[e.action] ?? e.action} ${person(e.actor_id)} ${person(e.subject_user_id)} ${e.study_id ?? e.client_id ?? ""} ${e.reason ?? ""}`.toLocaleLowerCase("cs").includes(query.trim().toLocaleLowerCase("cs")));
  return <div className="flex min-w-0 flex-col gap-3">
    <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(8rem,12rem)_minmax(8rem,14rem)]">
      <TextInput type="search" aria-label={t(`${P}.auditSearch`)} placeholder={t(`${P}.auditSearchPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)} />
      <Select aria-label="Osoba v historii" value={actor} onChange={(e) => setActor(e.target.value)}><option value="">Všechny osoby</option>{actors.map((id) => <option key={id} value={id}>{person(id)}</option>)}</Select>
      <Select aria-label="Typ události v historii" value={event} onChange={(e) => setEvent(e.target.value)}><option value="">Všechny události</option>{events.map((action) => <option key={action} value={action}>{names[action] ?? action.replaceAll("_", " ").toLocaleLowerCase("cs")}</option>)}</Select>
    </div>
    <p role="status" className="text-xs text-ink-muted">Zobrazeno {visible.length} z {audit.data.length} záznamů</p>
    {!visible.length ? <p role="status" className="text-sm text-ink-muted">{t(`${P}.noSearchResults`)}</p> : null}
    <ol className="flex flex-col gap-2">{visible.map((e) => <li key={e.event_id} className="rounded-md border border-border bg-surface p-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2"><strong>{names[e.action] ?? e.action.replaceAll("_", " ").toLocaleLowerCase("cs")}</strong><time dateTime={e.created_at ?? undefined} className="text-xs text-ink-muted">{e.created_at ? new Intl.DateTimeFormat("cs-CZ", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Prague" }).format(new Date(e.created_at)) : "—"}</time></div>
      <p className="mt-1 break-words text-xs text-ink-muted">{t(`${P}.audit.actor`)}: {person(e.actor_id)}{e.subject_user_id ? ` · ${t(`${P}.audit.subject`)}: ${person(e.subject_user_id)}` : ""}</p>
      {e.reason ? <p className="mt-2 break-words leading-6">{e.reason}</p> : null}
      <Technical><p data-technical className="mt-2 break-all font-mono text-xs text-ink-faint">{e.action} · {e.study_id ?? e.client_id ?? "—"} · {e.role ?? "—"}</p></Technical>
    </li>)}</ol>
  </div>;
}

// ---------------------------------------------------------------- the panel

// The page is split into tabs by what a person came to do. Every tab's panel stays
// mounted once drawn and only the open one is shown, so an unsaved edit in one tab is
// never lost by looking at another. A group the API adds later still renders -- in
// Reference -- so a new control is never hidden. What powers AIA comes first: every
// reader needs it, the deployment's posture only administrators.
export const TABS = ["methodology", "prompts", "deep_research", "ai", "access", "studies", "audit", "system", "reference", "data"] as const;
export type TabId = (typeof TABS)[number];
const TAB_GROUPS: { title: string; tabs: readonly TabId[] }[] = [
  { title: "Nastavení výzkumu", tabs: ["methodology", "prompts", "deep_research", "ai"] },
  { title: "Tým a peníze", tabs: ["access", "studies"] },
  { title: "Provoz", tabs: ["audit", "system", "reference", "data"] },
];
// Each tab's line under its name in the side navigation, and its icon (decorative: the name is the label).
const TAB_ICON: Record<TabId, LucideIcon> = {
  methodology: Sigma, prompts: ScrollText, deep_research: Telescope, ai: Cpu,
  access: Users, studies: Wallet,
  audit: History, system: Activity, reference: BookOpen, data: Database,
};
const TAB_FACTS: Record<TabId, { scope: string; owner: string }> = {
  methodology: { scope: "Budoucí běhy studií", owner: "Verze může upravovat vlastník nebo správce; účinná je až po aktivaci" },
  prompts: { scope: "Nově zadané AI úlohy organizace", owner: "Vlastník nebo správce; uložení a zapnutí jsou samostatné kroky" },
  deep_research: { scope: "Celá organizace", owner: "Vlastník nebo správce; návrh platí až po schválení" },
  ai: { scope: "Toto nasazení", owner: "Modely a připojení spravuje nasazení" },
  access: { scope: "Organizace, klient nebo studie", owner: "Změny podléhají roli a oprávnění ověřenému serverem" },
  studies: { scope: "Jednotlivá studie", owner: "Rozpočet se mění jen s oprávněním pro danou studii" },
  audit: { scope: "Historie organizace", owner: "Záznamy jsou jen ke čtení" },
  system: { scope: "Toto nasazení", owner: "Jen ke čtení; připravenost hlásí nasazení, chyby GlitchTip" },
  reference: { scope: "Toto nasazení a kód", owner: "Technické hodnoty a pevná pravidla zde nelze upravit" },
  data: { scope: "Organizace a její klienti", owner: "Vlastník nebo správce; smazání klienta je nevratné" },
};

const NO_ITEMS: SettingItem[] = [];

// Tabs that read their own route and are drawn on the first visit only.
const OWN_TABS = new Set<TabId>(["prompts", "deep_research", "methodology"]);

// The settings-document groups each tab shows, in order. "roles", "audit" and
// "invariants" are not API groups; the panel draws them itself.
const TAB_SECTIONS: Record<Exclude<TabId, "prompts" | "deep_research" | "methodology" | "system" | "data">, string[]> = {
  ai: ["ai", "ai_history"],
  access: ["access", "approvals", "roles"],
  studies: ["studies"],
  audit: ["audit"],
  reference: ["deployment", "residency", "workflow", "population", "evidence", "simulation"],
};
// Groups whose panel draws their rows itself (inside it), so they are not drawn twice.
const OWN_ROWS = new Set(["ai_history"]);

function tabFromHash(): TabId | null {
  if (typeof window === "undefined") return null;
  const id = window.location.hash.replace(/^#/, "");
  return (TABS as readonly string[]).includes(id) ? (id as TabId) : null;
}

function PanelView({ panel, reload }: { panel: Panel; reload: () => void }) {
  const { doc, runtime, members, clients, studies, levels, audit } = panel;
  const vocab = doc.vocabularies;
  const byKey = new Map(doc.groups.map((g) => [g.key, g]));
  const invariants = doc.groups.flatMap((g) => g.items.filter((i) => i.control === "INVARIANT"));
  const [active, setActive] = useState<TabId>("methodology");
  const [referenceQuery, setReferenceQuery] = useState("");
  const [technical, setTechnical] = useTechnicalChoice();
  const [drawn, setDrawn] = useState<ReadonlySet<TabId>>(new Set<TabId>(["methodology"]));
  const select = (tab: TabId) => {
    setActive(tab);
    setDrawn((d) => (d.has(tab) ? d : new Set(d).add(tab)));
    if (typeof window !== "undefined") window.history.replaceState(window.history.state, "", `#${tab}`);
  };
  // A link to /app/settings#prompts opens that tab. Read after mount so the server and the
  // first client render agree.
  useEffect(() => {
    const fromHash = tabFromHash();
    if (fromHash) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate the section from the browser URL after mount
      setActive(fromHash);
      setDrawn((d) => d.has(fromHash) ? d : new Set(d).add(fromHash));
    }
    const followHash = () => {
      const tab = tabFromHash();
      if (tab) { setActive(tab); setDrawn((d) => d.has(tab) ? d : new Set(d).add(tab)); }
    };
    window.addEventListener("hashchange", followHash);
    window.addEventListener("popstate", followHash);
    return () => { window.removeEventListener("hashchange", followHash); window.removeEventListener("popstate", followHash); };
  }, []);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const at = TABS.indexOf(active);
    const next =
      (e.key === "ArrowRight" || e.key === "ArrowDown") ? TABS[(at + 1) % TABS.length]
      : (e.key === "ArrowLeft" || e.key === "ArrowUp") ? TABS[(at + TABS.length - 1) % TABS.length]
      : e.key === "Home" ? TABS[0]
      : e.key === "End" ? TABS[TABS.length - 1]
      : null;
    if (!next) return;
    e.preventDefault();
    select(next);
    document.getElementById(`tab-${next}`)?.focus();
  };

  const extra: Record<string, ReactNode> = {
    ai: <RuntimePanel runtime={doc.ai_runtime} config={runtime} vocab={vocab} />,
    ai_history: <HistoryPanel vocab={vocab} items={byKey.get("ai_history")?.items ?? []} />,
    access: <MembersCard members={members} vocab={vocab} canAdminister={doc.may_administer} yourRole={doc.your_role} reload={reload} />,
    studies: (
      <>
        <ResearcherSpendCard nearLimitCount={studies.ok ? nearLimitTally(studies.data.map(({ detail }) => detail)) : null} />
        <StudiesTable studies={studies} clients={clients} vocab={vocab} reload={reload} />
      </>
    ),
    approvals: (
      <>
        <SelfApprovalCard levels={levels} canAdminister={doc.may_administer} reload={reload} studies={studies.ok ? studies.data.map(({ study }) => ({ study_id: study.study_id, name: study.name })) : []} />
        <ClientsCard clients={clients} levels={levels} vocab={vocab} canAdminister={doc.may_administer} reload={reload} />
      </>
    ),
    residency: <DataClasses vocab={vocab} />,
    workflow: <Stages vocab={vocab} />,
    roles: <RoleMatrix vocab={vocab} />,
    audit: <AuditPanel audit={audit} members={members} />,
  };
  // A group is drawn when the API sent it; the AI section and audit always are. The role
  // matrix and the prototype's AI history are reference material: technical details only.
  const present = (k: string) => (byKey.has(k) || k === "ai" || k === "roles" || k === "audit") && (technical || (k !== "roles" && k !== "ai_history"));
  const known = new Set([...Object.values(TAB_SECTIONS).flat(), "deep_research"]);
  const unknown = doc.groups.map((g) => g.key).filter((k) => !known.has(k));
  const section = (key: string, tab: TabId) => {
    const reference = TAB_SECTIONS.reference.includes(key) || unknown.includes(key);
    const query = referenceQuery.trim().toLocaleLowerCase("cs");
    const items = (byKey.get(key)?.items ?? []).filter((item) => !reference || !query || `${t(`${P}.items.${item.key}`)} ${SETTING_HELP[item.key] ?? ""} ${item.key} ${item.source} ${String(item.value)}`.toLocaleLowerCase("cs").includes(query));
    if (reference && query && !items.length && !t(`${P}.groups.${key}.title`).toLocaleLowerCase("cs").includes(query)) return null;
    const rows = <div data-setting-rows>{items.map((item) => <SettingRow key={item.key} item={item} />)}</div>;
    // A group with its own panel keeps the document's rows as technical details; a group
    // without one (the reference) is its rows.
    return <Section key={key} id={key} tab={tab}>
      {extra[key] ?? null}
      {OWN_ROWS.has(key) || key === "roles" || key === "audit" || !items.length ? null : extra[key] ? <Technical><Sub>{t(`${P}.relatedSettings`)}</Sub>{rows}</Technical> : rows}
    </Section>;
  };
  const body = (tab: TabId): ReactNode => {
    if (tab === "prompts") return <SystemPromptsSection doc={doc} members={members} />;
    if (tab === "deep_research") return <DeepResearchSection items={byKey.get("deep_research")?.items ?? NO_ITEMS} members={members} />;
    if (tab === "methodology") return <MethodologySection members={members} />;
    if (tab === "system") return <SystemSection />;
    if (tab === "data") return <DataSection />;
    const keys = [...TAB_SECTIONS[tab].filter(present), ...(tab === "reference" ? unknown : [])];
    return (
      <>
        {tab === "reference" ? <>
          <TextInput type="search" aria-label={t(`${P}.referenceSearch`)} placeholder={t(`${P}.referenceSearchPlaceholder`)} value={referenceQuery} onChange={(e) => setReferenceQuery(e.target.value)} />
          <nav aria-label={t(`${P}.referenceJump`)} data-reference-jump className="flex flex-wrap gap-2">
            {[...keys, "invariants"].map((key) => <a key={key} href={`#set-${key}`} onClick={(e) => { e.preventDefault(); document.getElementById(`set-${key}`)?.scrollIntoView({ block: "start" }); }} className="rounded-sm border border-border px-3 py-2 text-sm text-ink hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">{t(`${P}.groups.${key}.title`).startsWith(P) ? key.replaceAll("_", " ") : t(`${P}.groups.${key}.title`)}</a>)}
          </nav>
        </> : null}
        {keys.map((key) => section(key, tab))}
        {tab === "reference" ? <Section id="invariants"><div>{invariants.filter((item) => `${t(`${P}.items.${item.key}`)} ${SETTING_HELP[item.key] ?? ""} ${item.key}`.toLocaleLowerCase("cs").includes(referenceQuery.trim().toLocaleLowerCase("cs"))).map((item) => <SettingRow key={item.key} item={item} />)}</div></Section> : null}
      </>
    );
  };
  return (
    <TechnicalProvider on={technical}>
    <div data-settings-workspace className="flex flex-col gap-4 [&_button:not([data-dense])]:!min-h-11 [&_select]:!min-h-11 [&_input:not([type=checkbox]):not([type=radio])]:!min-h-11 [&_summary]:!min-h-11">
      <div className="grid min-w-0 gap-5 xl:grid-cols-[14.25rem_minmax(0,1fr)]">
      <div role="tablist" aria-label={t(`${P}.tabs.label`)} onKeyDown={onKey} className="flex h-fit min-w-0 gap-3 overflow-x-auto border-b border-border bg-surface-raised p-2 xl:sticky xl:top-28 xl:flex-col xl:overflow-visible xl:rounded-md xl:border">
        {TAB_GROUPS.map((group) => <div key={group.title} role="group" aria-label={group.title} className="flex shrink-0 gap-1 xl:flex-col">
          <p className="hidden px-2.5 pb-1.5 pt-3.5 text-[11px] uppercase tracking-[0.06em] text-ink-faint xl:block">{group.title}</p>
          {group.tabs.map((tab) => (
          <button
            key={tab}
            id={`tab-${tab}`}
            type="button"
            role="tab"
            aria-label={t(`${P}.tabs.${tab}`)}
            aria-selected={active === tab}
            aria-controls={`panel-${tab}`}
            tabIndex={active === tab ? 0 : -1}
            onClick={() => select(tab)}
            className={`flex min-w-28 items-start gap-2.5 rounded-md border px-2.5 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring xl:min-w-0 ${active === tab ? "border-transparent bg-signal-wash font-medium text-ink" : "border-transparent text-ink-muted hover:bg-surface-sunken hover:text-ink"}`}
          >
            <TabIcon tab={tab} active={active === tab} />
            <span className="min-w-0">
              <span className="block whitespace-nowrap">{t(`${P}.tabs.${tab}`)}</span>
              <span data-tab-subtitle className="hidden text-xs font-normal leading-4 text-ink-faint xl:block">{t(`${P}.tabSubtitles.${tab}`)}</span>
            </span>
          </button>
          ))}
        </div>)}
      </div>
      <div className="min-w-0">{TABS.map((tab) => (
        <div key={tab} id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} hidden={active !== tab} className="flex flex-col gap-4">
          <header data-tab-header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-border pb-4">
            <div className="min-w-0 max-w-3xl flex-[1_1_28rem]">
              <h2 className="text-lg font-semibold">{t(`${P}.tabs.${tab}`)}</h2>
              <p className="mt-1 text-sm font-medium leading-6 text-ink">{TAB_GUIDE[tab].purpose}</p>
              <p className="text-sm leading-6 text-ink-muted">{TAB_GUIDE[tab].action}</p>
              <p data-tab-facts className="mt-2 text-sm leading-6 text-ink"><span className="font-medium">{t(`${P}.appliesTo`)}:</span> {TAB_FACTS[tab].scope} <span aria-hidden="true" className="text-ink-faint">·</span> <span className="font-medium">{t(`${P}.changedBy`)}:</span> {TAB_FACTS[tab].owner}</p>
            </div>
            {tab === "methodology" ? null : <TechnicalSwitch on={technical} onChange={setTechnical} />}
          </header>
          {OWN_TABS.has(tab) && !drawn.has(tab) ? null : body(tab)}
        </div>
      ))}</div></div>
    </div>
    </TechnicalProvider>
  );
}

/** A tab's icon in the side navigation: decorative, the tab's name is its label. */
function TabIcon({ tab, active }: { tab: TabId; active: boolean }) {
  const Glyph = TAB_ICON[tab];
  return <Glyph aria-hidden="true" focusable="false" size={18} strokeWidth={1.75} className={`mt-px shrink-0 ${active ? "text-signal" : "text-ink-faint"}`} />;
}

/** One card of a tab whose content AIA does not have yet: its heading, what it will hold, and the plain fact. */
function NotYet({ id, title, holds }: { id: string; title: string; holds: string }) {
  return (
    <section id={`set-${id}`} aria-labelledby={`set-${id}-title`} className="rounded-md border border-border bg-surface-raised px-6 py-5">
      <h3 id={`set-${id}-title`} className="text-base font-semibold">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-ink-muted">{holds}</p>
      <p data-not-yet className="mt-3 inline-flex rounded-sm border border-dashed border-border-strong px-2 py-0.5 text-xs text-ink-muted">{t(`${P}.notYet`)}</p>
    </section>
  );
}

/** Stav systému: readiness after a deploy and error reporting (settings-redesign chunk 1; the content comes with its backend). */
function SystemSection() {
  const S = `${P}.system`;
  return (
    <div className="flex flex-col gap-4">
      <NotYet id="readiness" title={t(`${S}.readiness`)} holds={t(`${S}.readinessHolds`)} />
      <NotYet id="errors" title={t(`${S}.errors`)} holds={t(`${S}.errorsHolds`)} />
    </div>
  );
}

/** Správa dat: deleting a client and the records AIA keeps (settings-redesign chunk 1; the content comes with its backend). */
function DataSection() {
  const D = `${P}.data`;
  return (
    <div className="flex flex-col gap-4">
      <NotYet id="client-delete" title={t(`${D}.clientDelete`)} holds={t(`${D}.clientDeleteHolds`)} />
      <NotYet id="kept-records" title={t(`${D}.keptRecords`)} holds={t(`${D}.keptRecordsHolds`)} />
    </div>
  );
}

// The three tabs that read their own routes are memoised: the technical switch re-renders the
// page, and redrawing Metodika's formulas on every toggle cost ~0.5 s (settings_journey).

/** The prompts tab, drawn as a section like every other. Mounted on the first visit only. */
const SystemPromptsSection = memo(function SystemPromptsSection(props: React.ComponentProps<typeof SystemPromptsPanel>) {
  return (
    <section id="set-prompts" className="min-w-0">
      <SystemPromptsPanel {...props} />
    </section>
  );
});

/** The Metodika tab: the methodology, its versions and who made them (ADR 0023). */
const MethodologySection = memo(function MethodologySection({ members }: { members: Part<Member[]> }) {
  const emails = new Map(members.ok ? members.data.map((m) => [m.user_id, m.email]) : []);
  return (
    <section id="set-methodology" className="min-w-0">
      <MethodologyPanel people={(id) => (id ? (emails.get(id) ?? id) : "—")} />
    </section>
  );
});

/** The Deep Research tab: how its values are set, then the values from their own route (ADR 0022). */
const DeepResearchSection = memo(function DeepResearchSection({ items, members }: { items: SettingItem[]; members: Part<Member[]> }) {
  const emails = new Map(members.ok ? members.data.map((m) => [m.user_id, m.email]) : []);
  return (
    <section id="set-deep_research" className="min-w-0">
      <DeepResearchSettingsPanel people={(id) => (id ? (emails.get(id) ?? id) : "—")} />
      {items.length ? <Technical><div className="mt-4"><Sub>{t(`${P}.relatedSettings`)}</Sub>{items.map((item) => <SettingRow key={item.key} item={item} />)}</div></Technical> : null}
    </section>
  );
});

export function ControlPanel() {
  const [res, retry] = useResource(loadPanel, []);
  return <Loaded res={res} retry={retry}>{(panel) => <PanelView panel={panel} reload={retry} />}</Loaded>;
}
