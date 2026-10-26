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
import { type ReactNode, memo, useState } from "react";

import type { PublicConfig } from "@/lib/public-config";
import { t, tv } from "@/i18n/t";
import { type ActivityState, type SwitchValues, activityState, approvedClasses } from "@/lib/ai-runtime";
import {
  type AdminClient,
  type AiActivityAnswered,
  type AuditEntry,
  type Me,
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
  settingsStatus,
  workspace,
} from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { relative } from "@/lib/format";
import { nearLimitTally } from "@/lib/researcher-spend";
import { ClientsCard, MembersCard, SelfApprovalCard } from "./AccessPanel";
import { describeMemberError } from "./errors";
import { DeepResearchSettingsPanel } from "./DeepResearchSettingsPanel";
import { MethodologyPanel } from "./MethodologyPanel";
import { ResearcherSpendCard } from "./ResearcherSpendCard";
import { StudiesTable } from "./StudiesPanel";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { AUDIT_PAGE, AuditPanel } from "./AuditPanel";
import { DataPanel } from "./DataPanel";
import { SystemPanel } from "./SystemPanel";
import { SETTING_HELP } from "./settings-guide";
import { SystemPromptsPanel } from "./SystemPromptsPanel";
import { useSection } from "./SectionMenu";
import { SECTIONS, type SectionId, sectionLinkClick } from "./sections";
import { InfoButton } from "./InfoButton";
import { FOCUS } from "../../ui/parts";
import { Technical, TechnicalProvider, TechnicalSwitch, useTechnicalChoice } from "./technical";
import { Icon, type IconName } from "../../rehome/icons";
import { Chip, Tag, TextInput } from "../../rehome/ui";
import { CARD, EYEBROW, Loaded } from "../states";
import { type Resource, useResource } from "../useResource";

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
  /** Who you are: null while the page that holds the read has not finished it. */
  me: Part<Me> | null;
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

/** `readMe`: false when the page passes its own /workspace/me read down (it is read once). */
async function loadPanel(readMe: boolean): Promise<Panel> {
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
  const [runtime, members, clients, studies, levels, audit, me] = await Promise.all([
    part(loadRuntimeConfig()),
    part(admin.members()),
    part(admin.clients()),
    part(loadStudies()),
    doc.may_administer ? part(admin.selfApproval()) : Promise.resolve(null),
    doc.may_administer ? part(admin.audit(AUDIT_PAGE)) : Promise.resolve(null),
    readMe ? part(workspace.me()) : Promise.resolve(null),
  ]);
  return { doc, runtime, members, clients, studies, levels, audit, me };
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

/** Who changes a reference value: the deployment, a rule in code (code or invariant), or AIA's own API. */
type RefOwner = "deployment" | "fixed" | "app";
const ownerOf = (c: SettingControl): RefOwner => (c === "DEPLOYMENT" ? "deployment" : c === "API" ? "app" : "fixed");
const itemName = (key: string) => (t(`${P}.items.${key}`).startsWith(P) ? key.replaceAll("_", " ") : t(`${P}.items.${key}`));

/** A reference value as a table row: Hodnota, Nastaveno, Kdo mění, Co znamená (the redesign's Reference). */
function ReferenceRow({ item }: { item: SettingItem }) {
  return (
    <tr data-setting={item.key} data-owner={ownerOf(item.control)}>
      <td className="border-t border-border px-2 py-2 align-top text-sm font-medium text-ink">
        {itemName(item.key)}
        <Technical><code data-technical className="mt-1 block break-all text-xs font-normal text-ink-faint">{item.source}</code></Technical>
      </td>
      <td className="border-t border-border px-2 py-2 align-top">{item.control === "API" ? <ApiHint item={item} /> : <Value value={item.value} unit={item.unit} />}</td>
      <td className="whitespace-nowrap border-t border-border px-2 py-2 align-top"><ControlBadge control={item.control} /></td>
      <td className="border-t border-border px-2 py-2 align-top text-xs leading-5 text-ink-muted">{SETTING_HELP[item.key] ?? "—"}</td>
    </tr>
  );
}

function ReferenceTable({ items }: { items: SettingItem[] }) {
  const head = "px-2 py-1.5 text-left text-xs font-normal text-ink-faint";
  return (
    <div data-setting-rows className="overflow-x-auto">
      <table className="w-full min-w-[36rem] border-collapse">
        <thead><tr>
          <th scope="col" className={`${head} w-[24%]`}>{t(`${P}.reference.col.value`)}</th>
          <th scope="col" className={`${head} w-[22%]`}>{t(`${P}.reference.col.set`)}</th>
          <th scope="col" className={head}>{t(`${P}.reference.col.owner`)}</th>
          <th scope="col" className={head}>{t(`${P}.reference.col.means`)}</th>
        </tr></thead>
        <tbody>{items.map((item) => <ReferenceRow key={item.key} item={item} />)}</tbody>
      </table>
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

/** An activity's last answered call, as the usage ledger recorded it (F14, OI-75 (a)): a fact about
 *  the past, read by an OWNER or ADMIN. "None recorded" is not "not working", and an answer is
 *  not "working now": the line says when, on which model, by which build, nothing more. */
type Answered = Resource<AiActivityAnswered | null>;

function LastAnswered({ answered, activity }: { answered: Answered; activity: string }) {
  // Loading, or a member's (nothing asked): nothing said.
  if (answered.state === "loading" || (answered.state === "ready" && answered.data === null)) return null;
  // A read that failed, or an answer not of the shape asked for, says so and claims nothing.
  if (answered.state !== "ready" || answered.data === null || !Array.isArray(answered.data.activities)) return <p data-answered="unread" className="mt-1 text-xs text-ink-muted">{t(`${R}.answered.unread`)}</p>;
  const row = answered.data.activities.find((a) => a.key === activity);
  if (!row) return null;
  const last = row.last_answered;
  if (!last) return <p data-answered="none" className="mt-1 text-xs text-ink-muted">{t(`${R}.answered.none`)}</p>;
  return (
    <p data-answered="at" title={t(`${R}.answered.help`)} className="mt-1 text-xs text-ink-muted">
      <time dateTime={last.at}>{tv(`${R}.answered.at`, { when: relative(last.at) ?? last.at })}</time>
      {" · "}{tv(`${R}.answered.on`, { model: last.model })}
      {last.build ? <>{" · "}<span className="font-mono">{tv(`${R}.answered.build`, { build: last.build.slice(0, 7) })}</span></> : null}
    </p>
  );
}

function ActivityRow({ runtime, activity, switches, answered }: { runtime: NativeRuntime; activity: NativeActivity; switches: SwitchValues | null; answered: Answered }) {
  const state = activityState(runtime, activity, switches);
  const A = `${R}.activity.${activity.key}`;
  const named = switchFor(state);
  // The switch this activity has of its own; the master switch is said once, above the table.
  const own = activity.switches.filter((x) => x !== runtime.switch);
  return (
    <tr data-activity={activity.key} data-state={state.kind} className={state.kind === "off" || state.kind === "unknown" ? "text-ink-muted" : ""}>
      <td className={`${TD} min-w-48`}>
        <h3 className="text-sm font-semibold text-ink">{t(`${A}.title`)}</h3>
        <p className="mt-0.5 text-[13px] leading-5 text-ink-muted">{t(`${A}.text`)}</p>
        {/* Why it stands as it does, and its last answered call, under the activity (prototype v99). */}
        <p data-reason className="mt-1 break-words text-xs leading-5 text-ink">{reasonFor(state, activity)}</p>
        <LastAnswered answered={answered} activity={activity.key} />
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
      <td className={`${TD} whitespace-nowrap`}><Chip tone={STATE_TONE[state.kind]}>{t(`${R}.state.${state.kind}`)}</Chip></td>
      <td className={`${TD} break-all font-mono text-xs`}>{(own.length ? own : [runtime.switch]).join(" + ")}</td>
      <td className={`${TD} text-xs`}>{t(`${R}.modelOf.${activity.key}`)}</td>
    </tr>
  );
}

/** Where an activity sits on the AI běh board (the redesign's groups). */
const GROUP_OF: Record<string, string> = {
  study_lead: "study", design_agents: "study",
  respondent_fieldwork: "run", research_analysis: "run",
  deep_research: "dr", deep_research_lead: "dr",
};
const GROUPS = ["study", "run", "out", "dr", "client"] as const;
/**
 * Activities the settings document does not list yet: their switch is read by the worker, not by
 * /config, so their state is unknown here, never on or off; and two not built at all. Each names
 * its switch and what it runs on, from the code.
 */
const LISTED_ONLY: { key: string; group: (typeof GROUPS)[number]; switch: string; built: boolean }[] = [
  { key: "lead_plans", group: "study", switch: "AIA_LEAD_PLANS_ENABLED", built: false },
  { key: "population_personas", group: "run", switch: "AIA_AI_POPULATION_PERSONAS_ENABLED", built: true },
  { key: "run_qc", group: "run", switch: "AIA_RUN_QC_ENABLED", built: false },
  { key: "report_pdf", group: "out", switch: "AIA_REPORT_PDF_ENABLED", built: true },
  { key: "client_source_proposals", group: "client", switch: "AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED", built: true },
];

/** An activity's group: the board's own, then the code-listed row's, else Běh a analýza. */
const groupOf = (key: string): string => GROUP_OF[key] ?? LISTED_ONLY.find((e) => e.key === key)?.group ?? "run";

function ListedOnlyRow({ entry }: { entry: (typeof LISTED_ONLY)[number] }) {
  const A = `${R}.activity.${entry.key}`;
  return (
    <tr data-activity={entry.key} data-state={entry.built ? "unread" : "not_built"} className="text-ink-muted">
      <td className={`${TD} min-w-48`}>
        <h3 className="text-sm font-semibold text-ink">{t(`${A}.title`)}</h3>
        <p className="mt-0.5 text-[13px] leading-5 text-ink-muted">{t(`${A}.text`)}</p>
        <p data-reason className="mt-1 break-words text-xs leading-5 text-ink-muted">{t(`${R}.reason.${!entry.built ? "notBuilt" : entry.key === "population_personas" ? "unreadApi" : "unread"}`)}</p>
      </td>
      <td className={`${TD} whitespace-nowrap`}><Chip tone="neutral">{t(`${R}.state.${entry.built ? "unread" : "not_built"}`)}</Chip></td>
      <td className={`${TD} break-all font-mono text-xs`}>{entry.switch}</td>
      <td className={`${TD} text-xs`}>{t(`${R}.modelOf.${entry.key}`)}</td>
    </tr>
  );
}

function Tile({ label, children, note }: { label: string; children: ReactNode; note?: ReactNode }) {
  return (
    <div className="min-w-0 rounded-md border border-border px-3.5 py-3">
      <div className="text-xs text-ink-faint">{label}</div>
      <div className="mt-1 break-words text-sm font-medium">{children}</div>
      {note ? <div className="mt-0.5 text-xs text-ink-muted">{note}</div> : null}
    </div>
  );
}

/** The regions Bedrock's route may name, by their city (prototype v99's "Frankfurt · EU"). A region
 *  not listed shows its code alone, never a guessed city. */
const REGION_CITY: Record<string, string> = {
  "eu-central-1": "Frankfurt", "eu-central-2": "Curych", "eu-west-1": "Irsko", "eu-west-2": "Londýn", "eu-west-3": "Paříž",
  "eu-north-1": "Stockholm", "eu-south-1": "Milán", "eu-south-2": "Španělsko",
};
/** AWS names London and Zurich "eu-" too, but the United Kingdom and Switzerland are not in the EU:
 *  only these regions read "v EU" (review of #961). */
const EU_REGIONS = new Set(["eu-central-1", "eu-west-1", "eu-west-3", "eu-north-1", "eu-south-1", "eu-south-2"]);
/** A data class's letter, as v99's chips draw it: CLASS_A_… is "A". */
const classLetter = (id: string): string => /^CLASS_([A-Z])_/.exec(id)?.[1] ?? id;

/** Code facts from the settings document beside the deployment's switches from /config: AI běh. */
function RuntimePanel({ runtime, config, vocab, mayAdminister }: { runtime: NativeRuntime; config: Part<RuntimeConfig>; vocab: Vocabularies; mayAdminister: boolean }) {
  const switches = config.ok ? config.data.switches : null;
  // Each activity's last answered call: an organization-wide read, an OWNER's or ADMIN's alone
  // (OI-75 (a)); a member asks nothing and is shown nothing of it.
  const [answered] = useResource<AiActivityAnswered | null>(() => (mayAdminister ? settingsStatus.aiActivity() : Promise.resolve(null)), [mayAdminister]);
  const providers = runtime.providers.map((p) => p.label).join(", ");
  const states = runtime.activities.map((a) => activityState(runtime, a, switches).kind);
  const region = config.ok ? config.data.region : null;
  const [explained, setExplained] = useState<"route" | "acts" | null>(null);
  const toggle = (k: "route" | "acts") => setExplained((v) => (v === k ? null : k));
  // Two flat cards, as prototype v99 draws AI běh (F11): Trasa modelu as tiles, Činnosti as one
  // table; what each explains behind its ⓘ.
  return (
    <div className="flex flex-col gap-4">
      <section data-config aria-labelledby="ai-route-h" className={CARD}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <h2 id="ai-route-h" className="text-base font-semibold">{t(`${R}.route`)}</h2>
            <InfoButton label={t(`${R}.routeInfo`)} controls="ai-route-about" expanded={explained === "route"} onToggle={() => toggle("route")} title={t(`${R}.whoChanges`)} />
          </div>
          <Technical><span className="text-[11px] text-ink-faint">{t(`${R}.configSource`)}</span></Technical>
        </div>
        <div id="ai-route-about" hidden={explained !== "route"} className="mt-1 flex max-w-3xl flex-col gap-1 text-xs leading-5 text-ink-muted">
          <p>{tv(`${R}.powers`, { provider: providers })}</p>
          <p>{t(`${R}.credential.${runtime.credential}`)}</p>
          <p>{t(`${R}.whoChanges`)}</p>
        </div>
        {config.ok ? (
          <div className="mt-2.5 grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-2.5">
            <Tile label={t(`${R}.switchLabel`)} note={<Technical><code className="break-all">{runtime.switch}</code></Technical>}><SwitchWord value={config.data.switches[runtime.switch]} /></Tile>
            <Tile label={t(`${R}.provider`)}>{providers}</Tile>
            <Tile label={t(`${R}.region`)} note={<>
              {region !== null && REGION_CITY[region] ? <span data-region-city className="block">{REGION_CITY[region]}</span> : null}
              {region === null ? null : <span className="block">{EU_REGIONS.has(region) ? t(`${R}.inEu`) : t(`${R}.notEu`)}</span>}
              <Technical><code className="break-all">AIA_BEDROCK_REGION</code></Technical>
            </>}><Value value={region} /></Tile>
            <Tile label={t(`${R}.model`)} note={<Technical><code>AIA_BEDROCK_MODEL_ID</code></Technical>}><Value value={config.data.model} /></Tile>
            <Tile label={t(`${R}.approved`)} note={<Technical><code className="break-all">AIA_AI_ROUTE_APPROVED_FOR</code></Technical>}>
              {config.data.approvedClasses.length ? (
                // The classes as v99's chips (A, B, C), each named for a reader and on hover; an unknown
                // one stands out in words, never as a chip that looks approved.
                <ul data-approved-classes className="flex flex-wrap gap-1">
                  {approvedClasses(config.data.approvedClasses, vocab.data_classes).map((c) => (
                    <li key={c.id} data-class={c.id} className="text-sm font-normal">
                      {c.known ? (
                        <span title={t(`${P}.dataClass.${c.id}`)} className="inline-flex min-h-[22px] items-center rounded-pill border border-border px-2 text-xs">
                          <span aria-hidden="true">{classLetter(c.id)}</span>
                          <span className="sr-only">{t(`${P}.dataClass.${c.id}`)}</span>
                        </span>
                      ) : <span className="text-status-fault">{`${c.id}: ${t(`${R}.unknownClass`)}`}</span>}
                      <Technical><code className="ml-1 text-xs">{c.id}</code></Technical>
                    </li>
                  ))}
                </ul>
              ) : <span className="text-sm font-normal text-ink-muted">{t(`${R}.approvedNone`)}</span>}
            </Tile>
          </div>
        ) : <Unavailable what={t(`${R}.config`)} message={`${config.message} ${t(`${R}.configUnavailable`)}`} />}
      </section>
      <section aria-labelledby="ai-acts-h" className={`${CARD} flex flex-col gap-2`}>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1">
            <h2 id="ai-acts-h" className="text-base font-semibold">{t(`${R}.activities`)}</h2>
            <InfoButton label={t(`${R}.activitiesInfo`)} controls="ai-acts-about" expanded={explained === "acts"} onToggle={() => toggle("acts")} title={t(`${R}.activitiesHelp`)} />
          </div>
          {/* Counted only from switches read: with /config unreadable every activity is unknown, and
              "0 zapnuto" would say a known nothing (review of #961). */}
          {switches !== null ? <>
            <span data-count="on" className="inline-flex min-h-[22px] items-center rounded-pill border border-border px-2 text-xs">{tv(`${R}.count.on`, { n: states.filter((k) => k === "configured").length })}</span>
            <span data-count="off" className="inline-flex min-h-[22px] items-center rounded-pill border border-border px-2 text-xs">{tv(`${R}.count.off`, { n: states.filter((k) => k === "off").length })}</span>
          </> : <span data-count="unknown" className="inline-flex min-h-[22px] items-center rounded-pill border border-dashed border-border-strong px-2 text-xs text-ink-muted">{t(`${R}.count.unknown`)}</span>}
          <span data-count="new" className="inline-flex min-h-[22px] items-center rounded-pill border border-dashed border-border-strong px-2 text-xs text-ink-muted">{tv(`${R}.count.notBuilt`, { n: LISTED_ONLY.filter((e) => !e.built && !runtime.activities.some((a) => a.key === e.key)).length })}</span>
          {/* The deploy's smoke test, on Stav systému: what is ready after a deploy. It makes no model
              call (AI reads "Nešlo ověřit" there), so it does not verify that a call goes through. */}
          <a href="#system" onClick={sectionLinkClick("system")} title={t(`${R}.smokeLinkHelp`)} className={`ml-auto inline-flex min-h-11 items-center text-xs text-signal hover:underline sm:min-h-6 ${FOCUS}`}>{t(`${R}.smokeLink`)} ↗</a>
        </div>
        <p id="ai-acts-about" hidden={explained !== "acts"} className="max-w-3xl text-xs leading-5 text-ink-muted">{t(`${R}.activitiesHelp`)}</p>
        <div className="overflow-x-auto"><table className="w-full">
          <thead><tr><th className={TH}>{t(`${P}.col.capability`)}</th><th className={TH}>{t(`${P}.col.state`)}</th><th className={TH}>{t(`${R}.col.switch`)}</th><th className={TH}>{t(`${R}.col.model`)}</th></tr></thead>
          {GROUPS.map((g) => (
            <tbody key={g} data-ai-group={g} className="divide-y divide-border">
              <tr><th colSpan={4} scope="rowgroup" className="px-2 pb-1 pt-4 text-left text-[11px] font-normal uppercase tracking-[0.06em] text-ink-faint">{t(`${R}.group.${g}`)}</th></tr>
              {runtime.activities.filter((a) => groupOf(a.key) === g).map((a) => <ActivityRow key={a.key} runtime={runtime} activity={a} switches={switches} answered={answered} />)}
              {LISTED_ONLY.filter((e) => e.group === g && !runtime.activities.some((a) => a.key === e.key)).map((e) => <ListedOnlyRow key={e.key} entry={e} />)}
            </tbody>
          ))}
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
      </section>
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

// ---------------------------------------------------------------- the panel

// The page is split into tabs by what a person came to do. Every tab's panel stays
// mounted once drawn and only the open one is shown, so an unsaved edit in one tab is
// never lost by looking at another. A group the API adds later still renders -- in
// Stav systému, among the technical values -- so a new control is never hidden. What powers AIA comes first: every
// reader needs it, the deployment's posture only administrators.
const TABS = SECTIONS;
type TabId = SectionId;
/** A chip in a tab's head: who reads it and who may change it, as the prototype draws them. */
type HeadChip = { label: string; tone?: "you" | "deployment"; glyph?: string };

/** The tab head's chips. They say only what the API told this page (may_administer, the Metodik
 *  mark): a mark that could not be read claims nothing about editing. */
function headChips(tab: TabId, mayAdminister: boolean, methodologist: boolean | null): HeadChip[] {
  const c = (key: string, tone?: HeadChip["tone"], glyph?: string): HeadChip => ({ label: t(`${P}.chips.${key}`), tone, glyph });
  switch (tab) {
    case "methodology": return [c("everyone"), methodologist ? c("methodologist", "you") : c("methodologistOnly")];
    case "prompts": return [mayAdminister ? c("promptsYou", "you") : c("promptsAdmin")];
    case "deep_research": return [c("everyone"), mayAdminister ? c("drYou", "you") : c("drAdmin")];
    case "ai": return [c("deployedReadOnly", "deployment")];
    case "access": return [mayAdminister ? c("accessYou", "you") : c("accessAdmin")];
    // ADR 0019: every member holds the study permissions, a budget's among them.
    case "studies": return [c("studiesYou", "you", "✎")];
    case "system": return [c("deployed", "deployment")];
    case "data": return [c("adminOnly")];
    default: return [];
  }
}

const CHIP_TONE: Record<NonNullable<HeadChip["tone"]> | "plain", string> = {
  plain: "border-border bg-surface-raised text-ink-muted",
  you: "border-signal-edge bg-signal-tint text-ink",
  deployment: "border-status-world bg-status-world-wash text-ink",
};

const NO_ITEMS: SettingItem[] = [];

// Tabs that read their own route and are drawn on the first visit only: opening Settings reads
// nothing of a tab not yet opened (Stav systému's error read reaches GlitchTip; review of #854).
// Stav systému is drawn at once for its technical values, which come with the settings document;
// its readiness and error reporting, which read their own routes, wait for its first visit.
const OWN_TABS = new Set<TabId>(["prompts", "deep_research", "methodology", "data"]);

// The settings-document groups each tab shows, in order. "roles", "audit" and
// "invariants" are not API groups; the panel draws them itself.
const TAB_SECTIONS: Record<Exclude<TabId, "prompts" | "deep_research" | "methodology" | "system" | "data">, string[]> = {
  ai: ["ai", "ai_history"],
  access: ["access", "approvals", "roles"],
  studies: ["studies"],
  audit: ["audit"],
};
// Reference is folded into Stav systému (settings-redesign F17, Nigel 25 Oct 2026 23:13-23:15 UTC:
// "merge Reference into it, drop what is irrelevant"): what the deployment runs and the rules in
// code, under the readiness and error reporting. A group the API adds later lands there too.
const SYSTEM_REFERENCE = ["deployment", "residency", "workflow", "population"];
// Dropped with it, as not the system's state: the evidence thresholds are the code's reference
// values, while what a run applies is the support module in force, shown in Metodika -> Práh
// zobrazení (the decision log: the thresholds live only in Metodika); the simulation constants
// belong to Simulace, hidden for the MVP (AUD-6). Their invariants stay, under Invarianty.
const NOT_DRAWN = ["evidence", "simulation"];
// Groups whose panel draws their rows itself (inside it), so they are not drawn twice.
const OWN_ROWS = new Set(["ai_history"]);

function PanelView({ panel, reload, footer }: { panel: Panel; reload: () => void; footer?: ReactNode }) {
  const { doc, runtime, members, clients, studies, levels, audit } = panel;
  const vocab = doc.vocabularies;
  const byKey = new Map(doc.groups.map((g) => [g.key, g]));
  const invariants = doc.groups.flatMap((g) => g.items.filter((i) => i.control === "INVARIANT"));
  // The section is the page's address (#deep_research), chosen in the top bar's section menu
  // (prototype v54): a link, a deep link and the back button all land on it.
  const active = useSection();
  const [referenceQuery, setReferenceQuery] = useState("");
  const [referenceCategory, setReferenceCategory] = useState<string>("all");
  const [referenceOwner, setReferenceOwner] = useState<"all" | RefOwner>("all");
  const [technical, setTechnical] = useTechnicalChoice();
  // A section that reads its own route is drawn from its first visit on, and kept drawn after: a
  // draft in it survives a visit elsewhere. Derived while rendering, from the section opened.
  const [drawn, setDrawn] = useState<ReadonlySet<TabId>>(() => new Set<TabId>([active]));
  if (!drawn.has(active)) setDrawn(new Set(drawn).add(active));

  // A member's role in words beside their spend ("Správce · Metodik"); unknown for anyone the
  // members list did not include.
  const roleOf = (userId: string): string | null => {
    const m = members.ok ? members.data.find((x) => x.user_id === userId) : undefined;
    if (!m) return null;
    const role = t(`aia.orgRoles.${m.organization_role}`);
    return `${role.charAt(0).toLocaleUpperCase("cs")}${role.slice(1)}${m.methodologist ? ` · ${t(`${P}.accessTab.metodik`)}` : ""}`;
  };
  const extra: Record<string, ReactNode> = {
    ai: <RuntimePanel runtime={doc.ai_runtime} config={runtime} vocab={vocab} mayAdminister={doc.may_administer} />,
    ai_history: <HistoryPanel vocab={vocab} items={byKey.get("ai_history")?.items ?? []} />,
    access: <MembersCard members={members} vocab={vocab} canAdminister={doc.may_administer} yourRole={doc.your_role} reload={reload} myId={panel.me?.ok ? panel.me.data.user_id : null} />,
    studies: (
      <>
        <ResearcherSpendCard nearLimitCount={studies.ok ? nearLimitTally(studies.data.map(({ detail }) => detail)) : null} roleOf={roleOf} />
        <StudiesTable studies={studies} clients={clients} reload={reload} />
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
    audit: <AuditPanel audit={audit} members={members} clients={clients} studies={studies} />,
  };
  // A group is drawn when the API sent it; the AI section and audit always are. The role
  // matrix and the prototype's AI history are reference material: technical details only.
  const present = (k: string) => (byKey.has(k) || k === "ai" || k === "roles" || k === "audit") && (technical || (k !== "roles" && k !== "ai_history"));
  const known = new Set([...Object.values(TAB_SECTIONS).flat(), ...SYSTEM_REFERENCE, ...NOT_DRAWN, "deep_research"]);
  const unknown = doc.groups.map((g) => g.key).filter((k) => !known.has(k));
  const referenceMatch = (item: SettingItem) => (referenceOwner === "all" || ownerOf(item.control) === referenceOwner)
    && `${itemName(item.key)} ${SETTING_HELP[item.key] ?? ""} ${item.key} ${item.source} ${String(item.value)}`.toLocaleLowerCase("cs").includes(referenceQuery.trim().toLocaleLowerCase("cs"));
  // A reference group's own values: its invariants are listed once, under Invarianty.
  const groupItems = (key: string) => (key === "invariants" ? invariants : (byKey.get(key)?.items ?? []).filter((i) => i.control !== "INVARIANT"));
  const section = (key: string, tab: TabId) => {
    const reference = SYSTEM_REFERENCE.includes(key) || unknown.includes(key);
    const query = referenceQuery.trim().toLocaleLowerCase("cs");
    // An invariant is listed once, under Invarianty, not again in its group (review of #851).
    const items = (byKey.get(key)?.items ?? []).filter((item) => !reference || (item.control !== "INVARIANT" && referenceMatch(item)));
    if (reference && (referenceCategory !== "all" && referenceCategory !== key)) return null;
    if (reference && (query || referenceOwner !== "all") && !items.length) return null;
    const rows = reference ? <ReferenceTable items={items} /> : <div data-setting-rows>{items.map((item) => <SettingRow key={item.key} item={item} />)}</div>;
    // A group with its own panel keeps the document's rows as technical details. A reference group
    // is its rows, always: a search or category that finds a value shows it, and only each row's
    // source waits for technical details (ReferenceRow), never the table (review of #851).
    return <Section key={key} id={key} tab={tab}>
      {extra[key] ?? null}
      {OWN_ROWS.has(key) || key === "roles" || key === "audit" || !items.length ? null : extra[key] && !reference ? <Technical><Sub>{t(`${P}.relatedSettings`)}</Sub>{rows}</Technical> : rows}
    </Section>;
  };
  const body = (tab: TabId): ReactNode => {
    if (tab === "prompts") return <SystemPromptsSection doc={doc} members={members} />;
    if (tab === "deep_research") return <DeepResearchSection items={byKey.get("deep_research")?.items ?? NO_ITEMS} members={members} />;
    if (tab === "methodology") return <MethodologySection members={members} />;
    if (tab === "system") return <>{drawn.has("system") ? <SystemPanel mayAdminister={doc.may_administer} /> : null}{systemReference()}</>;
    if (tab === "data") return <DataPanel mayAdminister={doc.may_administer} clients={clients} reload={reload} />;
    // Studie a rozpočty as prototype v51 draws it: the figures, the spend by researcher and the
    // studies straight under the tab's head, in no further card; the settings document's own rows
    // for the group wait under technical details.
    // AI běh as prototype v99 draws it (F11): its two cards straight under the tab's head, in no
    // further card; the settings document's own rows for the group, and the prototype's AI history,
    // under technical details.
    if (tab === "ai") return <div id="set-ai" className="flex min-w-0 flex-col gap-4">
      {extra.ai}
      {groupItems("ai").length ? <Technical><Sub>{t(`${P}.relatedSettings`)}</Sub><div data-setting-rows>{(byKey.get("ai")?.items ?? []).map((item) => <SettingRow key={item.key} item={item} />)}</div></Technical> : null}
      {present("ai_history") ? section("ai_history", tab) : null}
    </div>;
    if (tab === "studies") return <div id="set-studies" className="flex min-w-0 flex-col gap-4">
      {extra.studies}
      {groupItems("studies").length ? <Technical><Sub>{t(`${P}.relatedSettings`)}</Sub><div data-setting-rows>{groupItems("studies").map((item) => <SettingRow key={item.key} item={item} />)}</div></Technical> : null}
    </div>;
    // Přístup a schvalování as prototype v58 draws it (F9): three flat cards straight under the tab's
    // head -- Členové, Samoschválení, Klienti -- in no further card; the settings document's own rows
    // for the two groups wait under technical details, and the role matrix with them.
    if (tab === "access") {
      const related = [...(byKey.get("access")?.items ?? []), ...(byKey.get("approvals")?.items ?? [])];
      return <div id="set-access" className="flex min-w-0 flex-col gap-4">
        {extra.access}
        {extra.approvals}
        {related.length ? <Technical><Sub>{t(`${P}.relatedSettings`)}</Sub><div data-setting-rows>{related.map((item) => <SettingRow key={item.key} item={item} />)}</div></Technical> : null}
        {present("roles") ? section("roles", tab) : null}
      </div>;
    }
    return <>{TAB_SECTIONS[tab].filter(present).map((key) => section(key, tab))}</>;
  };
  // Stav systému's technical values and the rules in code (once Reference, F17): searchable, by
  // category and by who changes them, every invariant once under Invarianty. Read by every member.
  const systemReference = (): ReactNode => {
    const keys = [...SYSTEM_REFERENCE.filter(present), ...unknown];
    const total = [...keys, "invariants"].reduce((n, key) => n + groupItems(key).length, 0);
    const shown = [...keys, "invariants"].filter((key) => referenceCategory === "all" || referenceCategory === key).reduce((n, key) => n + groupItems(key).filter(referenceMatch).length, 0);
    const owners = (["all", "deployment", "fixed", "app"] as const).filter((o) => o === "all" || [...keys, "invariants"].some((key) => groupItems(key).some((i) => ownerOf(i.control) === o)));
    return (
      <>
        <section data-reference-filters aria-labelledby="sys-reference-h" className={`${CARD} flex flex-col gap-3`}>
          <div>
            <h2 id="sys-reference-h" className="text-base font-semibold">{t(`${P}.reference.title`)}</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-ink-muted">{tv(`${P}.reference.intro`, { support: t("aia.settings.methodology.name.support") })}</p>
          </div>
          <TextInput type="search" aria-label={t(`${P}.referenceSearch`)} placeholder={t(`${P}.referenceSearchPlaceholder`)} value={referenceQuery} onChange={(e) => setReferenceQuery(e.target.value)} />
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-xs text-ink-faint">{t(`${P}.reference.categories`)}</span>
            <span role="status" className="text-xs text-ink-muted">{tv(`${P}.reference.shown`, { shown, total })}</span>
          </div>
          <div data-reference-categories className="flex flex-wrap gap-1.5">
            {["all", ...keys, "invariants"].map((key) => {
              const on = referenceCategory === key;
              // A chip counts what its group shows under the search and Kdo mění, as the tables do.
              const n = (key === "all" ? [...keys, "invariants"] : [key]).reduce((sum, k) => sum + groupItems(k).filter(referenceMatch).length, 0);
              const label = key === "all" ? t(`${P}.reference.all`) : t(`${P}.groups.${key}.title`).startsWith(P) ? key.replaceAll("_", " ") : t(`${P}.groups.${key}.title`);
              return <button key={key} type="button" data-reference-category={key} aria-pressed={on} onClick={() => setReferenceCategory(key)}
                className={`inline-flex min-h-8 items-center gap-1.5 rounded-pill border px-2.5 text-xs ${on ? "border-signal bg-signal-wash font-medium text-ink" : "border-border text-ink-muted hover:bg-surface-sunken"} focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring`}>
                {label}<span className="font-mono tabular-nums text-ink-faint">{n}</span>
              </button>;
            })}
          </div>
          <ChoiceChips look="segmented" small label={t(`${P}.reference.owner`)} value={referenceOwner} options={owners.map((o) => ({ key: o, label: t(`${P}.reference.owners.${o}`) }))} onChange={setReferenceOwner} />
        </section>
        {keys.map((key) => section(key, "system"))}
        {(referenceCategory === "all" || referenceCategory === "invariants") && invariants.some(referenceMatch) ? <Section id="invariants"><ReferenceTable items={invariants.filter(referenceMatch)} /></Section> : null}
        {![...keys, "invariants"].filter((k) => referenceCategory === "all" || referenceCategory === k).some((k) => groupItems(k).some(referenceMatch)) ? <p role="status" className="text-sm text-ink-muted">{t(`${P}.reference.none`)}</p> : null}
      </>
    );
  };
  const methodologist = panel.me?.ok ? panel.me.data.methodologist === true : null;
  return (
    <TechnicalProvider on={technical}>
    <div data-settings-workspace className="flex min-w-0 flex-1 flex-col [&_button:not([data-dense])]:!min-h-11 [&_select]:!min-h-11 [&_input:not([type=checkbox]):not([type=radio])]:!min-h-11 [&_summary]:!min-h-11">
      {/* The sections are chosen in the top bar's menu (prototype v54); the content takes the width. */}
      <div className="min-w-0 flex-1 px-4 pb-16 pt-4 md:px-8 md:pt-6">{TABS.map((tab) => {
        const chips = headChips(tab, doc.may_administer, methodologist);
        return (
        <section key={tab} id={`panel-${tab}`} data-section={tab} aria-labelledby={`section-${tab}-h`} hidden={active !== tab} className="flex flex-col gap-4">
          <header data-tab-header className="mb-0.5 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 id={`section-${tab}-h`} className="font-serif text-2xl font-semibold leading-[30px]">{t(`${P}.tabs.${tab}`)}</h1>
              <p data-tab-lede className="mt-1.5 max-w-[720px] text-sm leading-6 text-ink-muted">{t(`${P}.lede.${tab}`)}</p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
              {chips.length ? <div data-tab-chips className="flex flex-wrap items-center gap-1.5">{chips.map((chip) => (
                <span key={chip.label} data-chip-tone={chip.tone ?? "plain"} className={`inline-flex min-h-[22px] items-center gap-[5px] whitespace-nowrap rounded-[11px] border px-2 text-xs ${CHIP_TONE[chip.tone ?? "plain"]}`}>{chip.glyph ? <span aria-hidden="true">{chip.glyph}</span> : null}{chip.label}</span>
              ))}</div> : null}
              {/* One switch for the whole page's technical detail (the product owner, 2026-10-13): the
                  prototype has no place for it, so it sits at the end of the head, beside the chips. */}
              {active === tab ? <div data-technical-switch><TechnicalSwitch on={technical} onChange={setTechnical} /></div> : null}
            </div>
          </header>
          {OWN_TABS.has(tab) && !drawn.has(tab) ? null : body(tab)}
        </section>
        );
      })}{footer}</div>
    </div>
    </TechnicalProvider>
  );
}

/** One card of a tab whose content AIA does not have yet: its heading, what it will hold, and the plain fact. */

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

export function ControlPanel({ footer, me, rereadMe }: { footer?: ReactNode; me?: Resource<Me>; rereadMe?: () => void } = {}) {
  const passed = me !== undefined;
  const [res, reloadPanel] = useResource(() => loadPanel(!passed), [passed]);
  // A change in the panel may be your own (your role, your Metodik mark): who you are is read again
  // with it, or the heads keep the old answer (review of #870). The read keeps its value meanwhile.
  const retry = () => { reloadPanel(); if (passed) rereadMe?.(); };
  // The page is edge to edge (AppShell bleed); a loading or failed read keeps the content's gutter,
  // and the page keeps its one heading in every state.
  if (res.state !== "ready") {
    return <div className="px-4 py-5 md:px-8">
      <h1 className="font-serif text-2xl font-semibold leading-[30px]">{t("aia.settings.title")}</h1>
      <Loaded res={res} retry={retry}>{() => null}</Loaded>{footer}
    </div>;
  }
  const panel = passed ? { ...res.data, me: me.state === "ready" ? { ok: true as const, data: me.data } : me.state === "loading" ? null : { ok: false as const, message: me.state === "failed" ? me.message : "" } } : res.data;
  return <PanelView panel={panel} reload={retry} footer={footer} />;
}
