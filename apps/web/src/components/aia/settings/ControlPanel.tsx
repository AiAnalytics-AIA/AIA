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
import { useRouter } from "next/navigation";
import { type FormEvent, type KeyboardEvent, type ReactNode, useEffect, useState } from "react";

import type { PublicConfig } from "@/app/config/route";
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
import { describeError } from "./errors";
import { SystemPromptsPanel } from "./SystemPromptsPanel";
import { Icon, type IconName } from "../../rehome/icons";
import { Button, Chip, Field, Select, Tag, TextInput } from "../../rehome/ui";
import { CARD, EYEBROW, Empty, Loaded } from "../states";
import { useResource } from "../useResource";

const P = "aia.settings.panel";
const R = `${P}.runtime`;
const H = `${P}.history`;

// ---------------------------------------------------------------- loading

/** One part of the panel: its data, or why it is missing. A part never blanks the page. */
export type Part<T> = { ok: true; data: T } | { ok: false; message: string };

const describe = describeError;

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

export async function loadPanel(): Promise<Panel> {
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
export function ControlBadge({ control }: { control: SettingControl }) {
  return (
    <span title={t(`${P}.controlHelp.${control}`)} data-control={control} className="inline-flex shrink-0">
      <Tag icon={CONTROL_ICON[control]}>{t(`${P}.control.${control}`)}</Tag>
    </span>
  );
}

/** A value. Null is "not configured" and looks like it: never blank, never zero. */
export function Value({ value, unit }: { value: SettingValue; unit?: string | null }) {
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
      {String(value)}
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

export function SettingRow({ item }: { item: SettingItem }) {
  return (
    <div data-setting={item.key} className="grid grid-cols-1 gap-1 border-t border-border py-2 first:border-t-0 md:grid-cols-[minmax(0,2fr)_minmax(0,2fr)_auto] md:items-center md:gap-4">
      <div className="min-w-0">
        <div className="text-sm text-ink">{t(`${P}.items.${item.key}`)}</div>
        <code className="break-all text-[11px] text-ink-faint">{item.source}</code>
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

function Section({ id, children }: { id: string; children: ReactNode }) {
  return (
    <section id={`set-${id}`} aria-labelledby={`set-${id}-h`} className={`${CARD} scroll-mt-20`}>
      <h2 id={`set-${id}-h`} className="text-base font-semibold">{t(`${P}.groups.${id}.title`)}</h2>
      <p className="mt-1 max-w-3xl text-sm text-ink-muted">{t(`${P}.groups.${id}.intro`)}</p>
      <div className="mt-4 flex flex-col gap-4">{children}</div>
    </section>
  );
}

function Sub({ children }: { children: ReactNode }) {
  return <h3 className={EYEBROW}>{children}</h3>;
}

const TH = "px-2 py-1 text-left font-mono text-[11px] font-normal uppercase tracking-[0.08em] text-ink-faint";
const TD = "px-2 py-1.5 align-top text-sm";

// ---------------------------------------------------------------- actions

/** A form over one API call: shows the API's answer verbatim, then re-reads the panel. */
function ActionForm({
  run,
  submit,
  reload,
  children,
}: {
  run: (form: FormData) => Promise<unknown>;
  submit: string;
  reload: () => void;
  children: ReactNode;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<{ ok: boolean; text: string } | null>(null);
  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setBusy(true);
    setAnswer(null);
    try {
      await run(form);
      setAnswer({ ok: true, text: t(`${P}.saved`) });
      reload();
    } catch (err) {
      if (err instanceof Unauthenticated) {
        router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
        return;
      }
      setAnswer({ ok: false, text: describe(err) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
      {children}
      <Button type="submit" small disabled={busy}>{busy ? t(`${P}.sending`) : submit}</Button>
      {answer ? (
        <span role="status" className={`text-xs ${answer.ok ? "text-status-done" : "text-status-fault"}`}>{answer.text}</span>
      ) : null}
    </form>
  );
}

const str = (form: FormData, name: string) => {
  const v = form.get(name);
  return typeof v === "string" ? v.trim() : "";
};

/** A budget is a number or it is refused -- an empty field is not a zero budget. */
function budget(form: FormData): number {
  const raw = str(form, "budget_usd");
  const n = raw === "" ? NaN : Number(raw);
  if (!Number.isFinite(n)) throw new Error(t(`${P}.studies.budgetInvalid`));
  return n;
}

function RoleSelect({ roles, label, prefix }: { roles: string[]; label: string; prefix: string }) {
  return (
    <Select name="role" aria-label={label} className="w-auto">
      {roles.map((r) => <option key={r} value={r}>{t(`${prefix}.${r}`)} ({r})</option>)}
    </Select>
  );
}

// ---------------------------------------------------------------- panels

function MembersPanel({ members, vocab, canAdminister, reload }: { members: Part<Member[]>; vocab: Vocabularies; canAdminister: boolean; reload: () => void }) {
  return (
    <div className="flex flex-col gap-3">
      <Sub>{t(`${P}.members.title`)}</Sub>
      {members.ok ? (
        <table className="w-full">
          <thead><tr><th className={TH}>E-mail</th><th className={TH}>{t(`${P}.members.name`)}</th><th className={TH}>{t(`${P}.members.role`)}</th><th className={TH}>{t(`${P}.members.active`)}</th></tr></thead>
          <tbody className="divide-y divide-border">
            {members.data.map((m) => (
              <tr key={m.user_id}>
                <td className={TD}>{m.email}</td>
                <td className={TD}>{m.display_name || <Value value={null} />}</td>
                <td className={TD}>{t(`aia.orgRoles.${m.organization_role}`)}</td>
                <td className={TD}><Value value={m.is_active} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <Unavailable what={t(`${P}.members.title`)} message={members.message} />}
      {canAdminister ? (
        <ActionForm
          submit={t(`${P}.members.add`)}
          reload={reload}
          run={(f) => admin.addMember({ email: str(f, "email"), display_name: str(f, "display_name"), role: str(f, "role") })}
        >
          <Field label="E-mail"><TextInput name="email" type="email" required className="w-64" /></Field>
          <Field label={t(`${P}.members.name`)}><TextInput name="display_name" className="w-48" /></Field>
          <Field label={t(`${P}.members.role`)}><RoleSelect roles={vocab.organization_roles} label={t(`${P}.members.role`)} prefix="aia.orgRoles" /></Field>
        </ActionForm>
      ) : null}
      <p className="text-xs text-ink-faint">{t(`${P}.members.note`)}</p>
    </div>
  );
}

function ClientsPanel({ clients, vocab, canAdminister, reload }: {
  clients: Part<AdminClient[]>; vocab: Vocabularies; canAdminister: boolean; reload: () => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <Sub>{t(`${P}.clients.title`)}</Sub>
      {!clients.ok ? <Unavailable what={t(`${P}.clients.title`)} message={clients.message} /> : !clients.data.length ? <Empty>{t(`${P}.clients.none`)}</Empty> : (
        <table className="w-full">
          <thead><tr><th className={TH}>{t(`${P}.clients.name`)}</th><th className={TH}>ID</th><th className={TH}>{t(`${P}.clients.studies`)}</th><th className={TH}>{t(`${P}.clients.status`)}</th></tr></thead>
          <tbody className="divide-y divide-border">
            {clients.data.map((c) => (
              <tr key={c.client_id} data-client={c.client_id}>
                <td className={TD}>{c.name}</td>
                <td className={`${TD} font-mono text-xs`}>{c.client_id}</td>
                <td className={`${TD} font-mono text-xs`}>{c.study_count}</td>
                <td className={TD}>
                  {canAdminister ? (
                    <ActionForm submit={t(`${P}.save`)} reload={reload} run={(f) => admin.setClientStatus(c.client_id, str(f, "status"))}>
                      <Select name="status" defaultValue={c.status} aria-label={t(`${P}.clients.status`)} className="w-auto">
                        {vocab.client_statuses.map((s) => <option key={s} value={s}>{t(`${P}.clientStatus.${s}`)}</option>)}
                      </Select>
                    </ActionForm>
                  ) : t(`${P}.clientStatus.${c.status}`)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function StudiesPanel({ studies, clients, vocab, reload }: {
  studies: Part<StudyRow[]>; clients: Part<AdminClient[]>; vocab: Vocabularies; reload: () => void;
}) {
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  if (!studies.ok) return <Unavailable what={t(`${P}.studies.title`)} message={studies.message} />;
  if (!studies.data.length) return <Empty>{t(`${P}.studies.none`)}</Empty>;
  return (
    <div className="flex flex-col gap-2">
      {studies.data.map(({ study, detail }) => {
        const costs = detail.ok && detail.data.budget_usd !== null ? detail.data : null;
        return (
          <details key={study.study_id} data-study={study.study_id} className="rounded-sm border border-border">
            <summary className="flex cursor-pointer flex-wrap items-center gap-3 px-3 py-2 text-sm">
              <span className="font-medium text-ink">{study.name}</span>
              <span className="text-xs text-ink-muted">{clientName.get(study.client_id) ?? study.client_id}</span>
              <Tag>{t(`aia.status.${study.status}`)}</Tag>
              <span className="ml-auto text-xs text-ink-muted">
                {costs ? (
                  <>
                    {t(`${P}.studies.budget`)}: <Value value={costs.budget_usd} unit="USD" /> · {t(`${P}.studies.spent`)}: <Value value={costs.spent_usd} unit="USD" /> · {t(`${P}.studies.remaining`)}: <Value value={costs.remaining_usd} unit="USD" />
                  </>
                ) : (
                  <span title={detail.ok ? "" : detail.message} className="rounded-sm border border-dashed border-border-strong px-1.5">{t(`${P}.studies.costsHidden`)}</span>
                )}
              </span>
            </summary>
            <div className="grid gap-4 border-t border-border p-3 lg:grid-cols-2">
              <div>
                <p className="mb-1 text-xs font-medium text-ink-muted">{t(`${P}.studies.status`)}</p>
                <ActionForm submit={t(`${P}.save`)} reload={reload} run={(f) => admin.setStudyStatus(study.study_id, str(f, "status"))}>
                  <Select name="status" defaultValue={study.status} aria-label={t(`${P}.studies.status`)} className="w-auto">
                    {vocab.study_statuses.map((s) => <option key={s} value={s}>{t(`aia.status.${s}`)}</option>)}
                  </Select>
                </ActionForm>
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-ink-muted">{t(`${P}.studies.ceiling`)}</p>
                <ActionForm submit={t(`${P}.save`)} reload={reload} run={(f) => admin.setStudyBudget(study.study_id, budget(f))}>
                  <TextInput
                    name="budget_usd" type="number" min={0} max={1000000} step="0.01" required
                    aria-label={t(`${P}.studies.ceiling`)} defaultValue={costs?.budget_usd ?? undefined} className="w-32"
                  />
                  <span className="pb-2 text-xs text-ink-faint">USD</span>
                </ActionForm>
              </div>
              <p className="text-xs text-ink-faint lg:col-span-2">{t(`${P}.studies.permissionNote`)}</p>
            </div>
          </details>
        );
      })}
    </div>
  );
}

function Tri({ value }: { value: boolean | null }) {
  if (value === null) return <span className="rounded-sm border border-dashed border-border-strong px-1.5 text-xs text-ink-muted">{t(`${P}.approvals.inherit`)}</span>;
  // A plain tag: the "you" glyph is reserved for work waiting on the viewer (DS-3).
  return <Tag>{t(value ? `${P}.approvals.allowed` : `${P}.approvals.forbidden`)}</Tag>;
}

function choice(form: FormData): boolean | null {
  const c = str(form, "allowed");
  if (c === "allow") return true;
  if (c === "forbid") return false;
  if (c === "inherit") return null;
  throw new Error(t(`${P}.approvals.chooseFirst`));
}

function target(form: FormData): { client_id?: string; study_id?: string } {
  const [kind, id] = str(form, "target").split(":", 2);
  return kind === "client" ? { client_id: id } : kind === "study" ? { study_id: id } : {};
}

function TriSelect() {
  return (
    <Select name="allowed" defaultValue="" required aria-label={t(`${P}.approvals.choose`)} className="w-auto">
      <option value="" disabled>{t(`${P}.approvals.choose`)}</option>
      <option value="forbid">{t(`${P}.approvals.forbid`)}</option>
      <option value="allow">{t(`${P}.approvals.allow`)}</option>
      <option value="inherit">{t(`${P}.approvals.inheritOption`)}</option>
    </Select>
  );
}

function SelfApprovalPanel({ levels, clients, studies, reload }: {
  levels: Part<SelfApprovalLevels> | null; clients: Part<AdminClient[]>; studies: Part<StudyRow[]>; reload: () => void;
}) {
  if (levels === null) return <p className="text-sm text-ink-muted">{t(`${P}.approvals.adminOnly`)}</p>;
  if (!levels.ok) return <Unavailable what={t(`${P}.approvals.title`)} message={levels.message} />;
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  const studyName = new Map(studies.ok ? studies.data.map((s) => [s.study.study_id, s.study.name]) : []);
  const set = (f: FormData) => admin.setSelfApproval({ allowed: choice(f), ...target(f) });
  const row = (key: string, label: string, value: boolean | null, targetValue: string) => (
    <tr key={key} data-level={key}>
      <td className={TD}>{label}</td>
      <td className={TD}><Tri value={value} /></td>
      <td className={TD}>
        <ActionForm submit={t(`${P}.save`)} reload={reload} run={set}>
          <input type="hidden" name="target" value={targetValue} />
          <TriSelect />
        </ActionForm>
      </td>
    </tr>
  );
  return (
    <div className="flex flex-col gap-3">
      <Sub>{t(`${P}.approvals.title`)}</Sub>
      <p className="text-sm text-ink-muted">{t(`${P}.approvals.rule`)}</p>
      <table className="w-full">
        <thead><tr><th className={TH}>{t(`${P}.approvals.level`)}</th><th className={TH}>{t(`${P}.approvals.stored`)}</th><th className={TH} /></tr></thead>
        <tbody className="divide-y divide-border">
          {row("organization", t(`${P}.approvals.organization`), levels.data.organization, "")}
          {levels.data.clients.map((c) => row(`client:${c.client_id}`, `${t(`${P}.clients.client`)}: ${clientName.get(c.client_id) ?? c.client_id}`, c.allowed, `client:${c.client_id}`))}
          {levels.data.studies.map((s) => row(`study:${s.study_id}`, `${t(`${P}.studies.study`)}: ${studyName.get(s.study_id) ?? s.study_id}`, s.allowed, `study:${s.study_id}`))}
        </tbody>
      </table>
      <div className="rounded-sm border border-border p-3">
        <p className="mb-2 text-xs font-medium text-ink-muted">{t(`${P}.approvals.addOverride`)}</p>
        <ActionForm submit={t(`${P}.save`)} reload={reload} run={set}>
          <Select name="target" required defaultValue="" aria-label={t(`${P}.approvals.chooseTarget`)} className="w-auto">
            <option value="" disabled>{t(`${P}.approvals.chooseTarget`)}</option>
            {clients.ok ? clients.data.map((c) => <option key={c.client_id} value={`client:${c.client_id}`}>{t(`${P}.clients.client`)}: {c.name}</option>) : null}
            {studies.ok ? studies.data.map(({ study }) => <option key={study.study_id} value={`study:${study.study_id}`}>{t(`${P}.studies.study`)}: {study.name}</option>) : null}
          </Select>
          <TriSelect />
        </ActionForm>
      </div>
    </div>
  );
}

// ---- what powers AIA: code facts beside the deployment's switches --------

const STATE_TONE = { configured: "neutral", off: "world", invalid: "fault", unknown: "neutral" } as const satisfies Record<ActivityState["kind"], "neutral" | "world" | "fault">;

/** Why an activity stands where it does, in words. Never "connected" or "verified". */
function reasonFor(state: ActivityState, activity: NativeActivity): string {
  switch (state.kind) {
    case "configured":
      return t(`${R}.reason.configured`);
    case "off":
      return `${tv(`${R}.reason.off`, { switch: state.switch })} ${t(`${R}.activity.${activity.key}.off`)}`;
    case "invalid":
      return tv(`${R}.reason.invalid`, { switch: state.switch });
    case "unknown":
      return state.switch ? tv(`${R}.reason.unknown`, { switch: state.switch }) : t(`${R}.reason.unknownConfig`);
  }
}

function Codes({ ids, title }: { ids: string[]; title?: (id: string) => string }) {
  return (
    <span className="flex flex-wrap gap-1">
      {ids.map((id) => <code key={id} title={title?.(id)} className="rounded-sm bg-surface-sunken px-1.5 text-xs">{id}</code>)}
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
        <code className="break-all text-[11px] text-ink-faint">{source}</code>
      </div>
      <div className="min-w-0 break-all">{children}</div>
    </div>
  );
}

function ActivityCard({ runtime, activity, switches }: { runtime: NativeRuntime; activity: NativeActivity; switches: SwitchValues | null }) {
  const state = activityState(runtime, activity, switches);
  const A = `${R}.activity.${activity.key}`;
  return (
    <article data-activity={activity.key} data-state={state.kind} className="flex flex-col gap-2 rounded-sm border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{t(`${A}.title`)}</h3>
        <Chip tone={STATE_TONE[state.kind]}>{t(`${R}.state.${state.kind}`)}</Chip>
      </div>
      <p className="text-sm text-ink-muted">{t(`${A}.text`)}</p>
      <p data-reason className="text-sm text-ink">{reasonFor(state, activity)}</p>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
        {activity.actions.length ? (
          <>
            <dt className="text-ink-faint">{t(`${R}.actions`)}</dt>
            <dd>{activity.actions.map((a) => t(`${R}.action.${a}`)).join(", ")}</dd>
          </>
        ) : null}
        <dt className="text-ink-faint">{t(`${R}.col.uses`)}</dt>
        <dd><Codes ids={activity.capabilities} title={(c) => t(`${P}.capability.${c}`)} /></dd>
        <dt className="text-ink-faint">{t(`${R}.col.versions`)}</dt>
        <dd className="flex flex-col gap-0.5">
          {activity.versions.map((v) => <span key={v.name}>{t(`${R}.version.${v.name}`)} <code className="break-all">{v.value}</code></span>)}
        </dd>
        <dt className="text-ink-faint">{t(`${R}.col.switches`)}</dt>
        <dd><Codes ids={activity.switches} /></dd>
      </dl>
    </article>
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
      <div data-config className="rounded-sm border border-border p-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <Sub>{t(`${R}.config`)}</Sub>
          <span className="text-[11px] text-ink-faint">{t(`${R}.configSource`)}</span>
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
                      <code className="text-xs">{c.id}</code>{" "}
                      <span className={`text-xs ${c.known ? "text-ink-muted" : "text-status-fault"}`}>— {c.known ? t(`${P}.dataClass.${c.id}`) : t(`${R}.unknownClass`)}</span>
                    </li>
                  ))}
                </ul>
              ) : <span className="text-sm text-ink-muted">{t(`${R}.approvedNone`)}</span>}
            </ConfigRow>
          </div>
        ) : <Unavailable what={t(`${R}.config`)} message={`${config.message} ${t(`${R}.configUnavailable`)}`} />}
      </div>
      <div className="flex flex-col gap-2">
        <Sub>{t(`${R}.activities`)}</Sub>
        <div className="grid gap-3 lg:grid-cols-2">
          {runtime.activities.map((a) => <ActivityCard key={a.key} runtime={runtime} activity={a} switches={switches} />)}
        </div>
        {runtime.unused_capabilities.length ? (
          <div data-activity="unused" className="rounded-sm border border-dashed border-border-strong p-3 text-sm">
            <span className="font-medium text-ink">{t(`${R}.unused`)}:</span>{" "}
            <Codes ids={runtime.unused_capabilities} title={(c) => t(`${P}.capability.${c}`)} />
            <p className="mt-1 text-xs text-ink-muted">{t(`${R}.unusedText`)}</p>
          </div>
        ) : null}
        <p className="text-xs text-ink-faint">{t(`${R}.capabilityNote`)}</p>
      </div>
      <p role="note" data-not-verified className="rounded-sm border border-border bg-surface-sunken p-3 text-sm text-ink">{t(`${R}.notVerified`)}</p>
    </div>
  );
}

/** The prototype's identifiers, for reading older records. Collapsed: nothing here is a choice. */
function HistoryPanel({ vocab, items }: { vocab: Vocabularies; items: SettingItem[] }) {
  const historical = vocab.providers.filter((p) => p.use === "HISTORICAL");
  return (
    <details data-history className="rounded-sm border border-border">
      <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-ink">{t(`${H}.show`)}</summary>
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
    </details>
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
  if (audit === null) return <p className="text-sm text-ink-muted">{t(`${P}.audit.adminOnly`)}</p>;
  if (!audit.ok) return <Unavailable what={t(`${P}.groups.audit.title`)} message={audit.message} />;
  if (!audit.data.length) return <Empty>{t(`${P}.audit.none`)}</Empty>;
  // An id the member list resolves is shown as an e-mail; one it does not stays an id.
  const who = new Map(members.ok ? members.data.map((m) => [m.user_id, m.email]) : []);
  const person = (id: string | null) => (id ? (who.get(id) ?? id) : "—");
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead><tr>{["when", "action", "actor", "subject", "scope", "detail"].map((k) => <th key={k} className={TH}>{t(`${P}.audit.${k}`)}</th>)}</tr></thead>
        <tbody className="divide-y divide-border">
          {audit.data.map((e) => (
            <tr key={e.event_id}>
              <td className={`${TD} font-mono text-xs`}>{e.created_at ?? "—"}</td>
              <td className={`${TD} font-mono text-xs`}>{e.action}</td>
              <td className={`${TD} font-mono text-xs`}>{person(e.actor_id)}</td>
              <td className={`${TD} font-mono text-xs`}>{person(e.subject_user_id)}</td>
              <td className={`${TD} font-mono text-xs`}>{e.study_id ?? e.client_id ?? "—"}</td>
              <td className={TD}>{[e.role, e.reason].filter(Boolean).join(" · ") || "—"}</td>
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
// Reference -- so a new control is never hidden. What powers AIA comes first: every
// reader needs it, the deployment's posture only administrators.
export const TABS = ["ai", "prompts", "access", "studies", "audit", "reference"] as const;
export type TabId = (typeof TABS)[number];

// The settings-document groups each tab shows, in order. "roles", "audit" and
// "invariants" are not API groups; the panel draws them itself.
const TAB_SECTIONS: Record<Exclude<TabId, "prompts">, string[]> = {
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

export function PanelView({ panel, reload }: { panel: Panel; reload: () => void }) {
  const { doc, runtime, members, clients, studies, levels, audit } = panel;
  const vocab = doc.vocabularies;
  const byKey = new Map(doc.groups.map((g) => [g.key, g]));
  const invariants = doc.groups.flatMap((g) => g.items.filter((i) => i.control === "INVARIANT"));
  const [active, setActive] = useState<TabId>("ai");
  const [drawn, setDrawn] = useState<ReadonlySet<TabId>>(new Set<TabId>(["ai"]));
  const select = (tab: TabId) => {
    setActive(tab);
    setDrawn((d) => (d.has(tab) ? d : new Set(d).add(tab)));
    if (typeof window !== "undefined") window.history.replaceState(null, "", `#${tab}`);
  };
  // A link to /app/settings#prompts opens that tab. Read after mount so the server and the
  // first client render agree.
  useEffect(() => {
    const fromHash = tabFromHash();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the URL is only readable after mount
    if (fromHash) select(fromHash);
  }, []);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const at = TABS.indexOf(active);
    const next =
      e.key === "ArrowRight" ? TABS[(at + 1) % TABS.length]
      : e.key === "ArrowLeft" ? TABS[(at + TABS.length - 1) % TABS.length]
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
    access: (
      <>
        <MembersPanel members={members} vocab={vocab} canAdminister={doc.may_administer} reload={reload} />
        <ClientsPanel clients={clients} vocab={vocab} canAdminister={doc.may_administer} reload={reload} />
      </>
    ),
    studies: <StudiesPanel studies={studies} clients={clients} vocab={vocab} reload={reload} />,
    approvals: <SelfApprovalPanel levels={levels} clients={clients} studies={studies} reload={reload} />,
    residency: <DataClasses vocab={vocab} />,
    workflow: <Stages vocab={vocab} />,
    roles: <RoleMatrix vocab={vocab} />,
    audit: <AuditPanel audit={audit} members={members} />,
  };
  // A group is drawn when the API sent it; the AI section, roles and audit always are.
  const present = (k: string) => byKey.has(k) || k === "ai" || k === "roles" || k === "audit";
  const known = new Set(Object.values(TAB_SECTIONS).flat());
  const unknown = doc.groups.map((g) => g.key).filter((k) => !known.has(k));
  const section = (key: string) => (
    <Section key={key} id={key}>
      {extra[key] ?? null}
      {OWN_ROWS.has(key) || key === "roles" || key === "audit" ? null : <div>{(byKey.get(key)?.items ?? []).map((item) => <SettingRow key={item.key} item={item} />)}</div>}
    </Section>
  );
  const body = (tab: TabId): ReactNode => {
    if (tab === "prompts") return <SystemPromptsSection doc={doc} members={members} clients={clients} studies={studies} />;
    const keys = [...TAB_SECTIONS[tab].filter(present), ...(tab === "reference" ? unknown : [])];
    return (
      <>
        {tab === "reference" ? <p className="max-w-3xl text-sm text-ink-muted">{t(`${P}.referenceNote`)}</p> : null}
        {keys.map(section)}
        {tab === "reference" ? <Section id="invariants"><div>{invariants.map((item) => <SettingRow key={item.key} item={item} />)}</div></Section> : null}
      </>
    );
  };
  return (
    <div className="flex flex-col gap-4">
      <div className={`${CARD} flex flex-col gap-3`}>
        <h2 className="text-base font-semibold">{t(`${P}.title`)}</h2>
        <p className="max-w-3xl text-sm text-ink-muted">{t(`${P}.intro`)}</p>
        <ul className="flex flex-wrap gap-4 border-t border-border pt-3">
          {(["API", "DEPLOYMENT", "CODE", "INVARIANT"] as const).map((c) => (
            <li key={c} className="flex items-center gap-2 text-xs text-ink-muted"><ControlBadge control={c} />{t(`${P}.controlHelp.${c}`)}</li>
          ))}
        </ul>
      </div>
      <div role="tablist" aria-label={t(`${P}.tabs.label`)} onKeyDown={onKey} className="flex flex-wrap gap-1 border-b border-border">
        {TABS.map((tab) => (
          <button
            key={tab}
            id={`tab-${tab}`}
            type="button"
            role="tab"
            aria-selected={active === tab}
            aria-controls={`panel-${tab}`}
            tabIndex={active === tab ? 0 : -1}
            onClick={() => select(tab)}
            className={`-mb-px rounded-t-sm border border-b-0 px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${active === tab ? "border-border bg-surface-raised font-semibold text-ink" : "border-transparent text-ink-muted hover:text-ink"}`}
          >
            {t(`${P}.tabs.${tab}`)}
          </button>
        ))}
      </div>
      {TABS.map((tab) => (
        <div key={tab} id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} hidden={active !== tab} className="flex flex-col gap-4">
          {tab === "prompts" && !drawn.has("prompts") ? null : body(tab)}
        </div>
      ))}
    </div>
  );
}

/** The prompts tab, drawn as a section like every other. Mounted on the first visit only. */
function SystemPromptsSection(props: React.ComponentProps<typeof SystemPromptsPanel>) {
  return (
    <Section id="prompts">
      <SystemPromptsPanel {...props} />
    </Section>
  );
}

export function ControlPanel() {
  const [res, retry] = useResource(loadPanel, []);
  return <Loaded res={res} retry={retry}>{(panel) => <PanelView panel={panel} reload={retry} />}</Loaded>;
}
