"use client";

// The settings page's control panel: every control AIA has, its current value,
// and how it is changed (GET /api/v1/settings). An API control is a live form
// over an existing route, sent with the signed-in bearer token; a deployment
// variable, a code constant and an invariant are shown, never offered as a
// switch. The API decides what is allowed -- its refusal is shown as given.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  type AdminClient,
  type AuditEntry,
  type Member,
  type SelfApprovalLevels,
  type SettingControl,
  type SettingItem,
  type SettingValue,
  type SettingsDocument,
  type Study,
  type Vocabularies,
  ApiError,
  Unauthenticated,
  admin,
} from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { Icon, type IconName } from "../../rehome/icons";
import { Button, Field, Select, Tag, TextInput } from "../../rehome/ui";
import { CARD, EYEBROW, Empty, Loaded } from "../states";
import { useResource } from "../useResource";

const P = "aia.settings.panel";

// ---------------------------------------------------------------- loading

/** One part of the panel: its data, or why it is missing. A part never blanks the page. */
export type Part<T> = { ok: true; data: T } | { ok: false; message: string };

function describe(e: unknown): string {
  if (e instanceof ApiError) return `HTTP ${e.status} · ${e.code}: ${e.message}${e.requestId ? ` (${e.requestId})` : ""}`;
  return e instanceof Error ? e.message : String(e);
}

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

export type Panel = {
  doc: SettingsDocument;
  members: Part<Member[]>;
  clients: Part<AdminClient[]>;
  studies: Part<StudyRow[]>;
  levels: Part<SelfApprovalLevels> | null; // null: not an administrator, so not asked
  audit: Part<AuditEntry[]> | null;
};

export async function loadPanel(): Promise<Panel> {
  const doc = await admin.settings();
  // A document without its groups is not a settings document; say so rather than
  // render an empty page that looks like "no settings".
  if (!doc || !Array.isArray(doc.groups) || !doc.vocabularies) throw new Error(t(`${P}.malformed`));
  const loadStudies = async (): Promise<StudyRow[]> => {
    const list = await admin.studies();
    // The list omits costs by design; the detail carries them only where the caller
    // may view costs, and a refusal stays a refusal -- never a zero.
    const details = await Promise.all(list.map((s) => part(admin.study(s.study_id))));
    return list.map((study, i) => ({ study, detail: details[i] }));
  };
  const [members, clients, studies, levels, audit] = await Promise.all([
    part(admin.members()),
    part(admin.clients()),
    part(loadStudies()),
    doc.may_administer ? part(admin.selfApproval()) : Promise.resolve(null),
    doc.may_administer ? part(admin.audit(50)) : Promise.resolve(null),
  ]);
  return { doc, members, clients, studies, levels, audit };
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

// Where an API control's form lives, when it is not in this panel.
const ELSEWHERE: Record<string, "clients" | "project"> = {
  clients: "clients",
  studies: "clients",
  project_max_api_cost: "project",
  project_provider_policy: "project",
};

function ApiHint({ item }: { item: SettingItem }) {
  const where = ELSEWHERE[item.key];
  if (where === "clients") {
    return <Link href={appRoutes.clients()} className="text-xs text-signal underline">{t(`${P}.inClients`)}</Link>;
  }
  return <span className="text-xs text-ink-muted">{t(where === "project" ? `${P}.onProject` : `${P}.inPanel`)}</span>;
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

function MemberSelect({ members }: { members: Member[] }) {
  return (
    <Select name="user_id" aria-label={t(`${P}.members.member`)} className="w-auto" required>
      {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name ? `${m.display_name} · ` : ""}{m.email}</option>)}
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

function ClientsPanel({ clients, members, vocab, canAdminister, reload }: {
  clients: Part<AdminClient[]>; members: Part<Member[]>; vocab: Vocabularies; canAdminister: boolean; reload: () => void;
}) {
  const scopeRoles = vocab.scope_roles.map((r) => r.role);
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
      {canAdminister && clients.ok && members.ok && clients.data.length ? (
        <div className="rounded-sm border border-border p-3">
          <p className="mb-2 text-xs font-medium text-ink-muted">{t(`${P}.clients.grant`)}</p>
          <ActionForm submit={t(`${P}.grant`)} reload={reload} run={(f) => admin.grantClient(str(f, "client_id"), str(f, "user_id"), str(f, "role"))}>
            <Select name="client_id" aria-label={t(`${P}.clients.client`)} className="w-auto">
              {clients.data.map((c) => <option key={c.client_id} value={c.client_id}>{c.name}</option>)}
            </Select>
            <MemberSelect members={members.data} />
            <RoleSelect roles={scopeRoles} label={t(`${P}.members.role`)} prefix="aia.roles" />
          </ActionForm>
          <p className="mt-2 text-xs text-ink-faint">{t(`${P}.clients.grantNote`)}</p>
        </div>
      ) : null}
    </div>
  );
}

function StudiesPanel({ studies, clients, members, vocab, reload }: {
  studies: Part<StudyRow[]>; clients: Part<AdminClient[]>; members: Part<Member[]>; vocab: Vocabularies; reload: () => void;
}) {
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  const scopeRoles = vocab.scope_roles.map((r) => r.role);
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
            <div className="grid gap-4 border-t border-border p-3 lg:grid-cols-3">
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
              <div>
                <p className="mb-1 text-xs font-medium text-ink-muted">{t(`${P}.studies.grant`)}</p>
                {members.ok ? (
                  <ActionForm submit={t(`${P}.grant`)} reload={reload} run={(f) => admin.grantStudy(study.study_id, str(f, "user_id"), str(f, "role"))}>
                    <MemberSelect members={members.data} />
                    <RoleSelect roles={scopeRoles} label={t(`${P}.members.role`)} prefix="aia.roles" />
                  </ActionForm>
                ) : <Unavailable what={t(`${P}.members.title`)} message={members.message} />}
              </div>
              <p className="text-xs text-ink-faint lg:col-span-3">{t(`${P}.studies.permissionNote`)}</p>
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

function ProvidersPanel({ vocab }: { vocab: Vocabularies }) {
  const list = (title: string, ids: string[], prefix: string) => (
    <div>
      <Sub>{title}</Sub>
      <ul className="mt-1 flex flex-col gap-1">
        {ids.map((id) => <li key={id} className="text-sm"><code className="text-xs">{id}</code> <span className="text-xs text-ink-muted">— {t(`${prefix}.${id}`)}</span></li>)}
      </ul>
    </div>
  );
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div>
        <Sub>{t(`${P}.ai.providers`)}</Sub>
        <ul className="mt-1 flex flex-col gap-1">
          {vocab.providers.map((p) => (
            <li key={p.id} className="text-sm">
              {p.label} <code className="text-xs text-ink-faint">{p.id}</code> <span className="text-xs text-ink-muted">— {t(p.paid ? `${P}.ai.paid` : `${P}.ai.subscription`)}</span>
            </li>
          ))}
        </ul>
      </div>
      {list(t(`${P}.ai.policies`), vocab.provider_policies, `${P}.policy`)}
      <div>
        {list(t(`${P}.ai.capabilities`), vocab.model_capabilities, `${P}.capability`)}
        <p className="mt-2 text-xs text-ink-faint">{t(`${P}.ai.capabilityNote`)}</p>
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

// Groups with a dedicated panel, in page order. A group the API adds later still
// renders -- generically, after these -- so a new control is never hidden.
const ORDER = ["deployment", "access", "studies", "approvals", "ai", "residency", "workflow", "population", "evidence", "simulation"];

export function PanelView({ panel, reload }: { panel: Panel; reload: () => void }) {
  const { doc, members, clients, studies, levels, audit } = panel;
  const vocab = doc.vocabularies;
  const byKey = new Map(doc.groups.map((g) => [g.key, g]));
  const keys = [...ORDER.filter((k) => byKey.has(k)), ...doc.groups.map((g) => g.key).filter((k) => !ORDER.includes(k))];
  const invariants = doc.groups.flatMap((g) => g.items.filter((i) => i.control === "INVARIANT"));
  const extra: Record<string, ReactNode> = {
    access: (
      <>
        <MembersPanel members={members} vocab={vocab} canAdminister={doc.may_administer} reload={reload} />
        <ClientsPanel clients={clients} members={members} vocab={vocab} canAdminister={doc.may_administer} reload={reload} />
      </>
    ),
    studies: <StudiesPanel studies={studies} clients={clients} members={members} vocab={vocab} reload={reload} />,
    approvals: <SelfApprovalPanel levels={levels} clients={clients} studies={studies} reload={reload} />,
    ai: <ProvidersPanel vocab={vocab} />,
    residency: <DataClasses vocab={vocab} />,
    workflow: <Stages vocab={vocab} />,
  };
  const nav = [...keys, "roles", "audit", "invariants"];
  return (
    <div className="flex flex-col gap-4">
      <nav aria-label={t(`${P}.title`)} className={`${CARD} flex flex-col gap-3`}>
        <h2 className="text-base font-semibold">{t(`${P}.title`)}</h2>
        <p className="max-w-3xl text-sm text-ink-muted">{t(`${P}.intro`)}</p>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {nav.map((k) => <li key={k}><a href={`#set-${k}`} className="text-signal underline-offset-2 hover:underline">{t(`${P}.groups.${k}.title`)}</a></li>)}
        </ul>
        <ul className="flex flex-wrap gap-4 border-t border-border pt-3">
          {(["API", "DEPLOYMENT", "CODE", "INVARIANT"] as const).map((c) => (
            <li key={c} className="flex items-center gap-2 text-xs text-ink-muted"><ControlBadge control={c} />{t(`${P}.controlHelp.${c}`)}</li>
          ))}
        </ul>
      </nav>
      {keys.map((key) => (
        <Section key={key} id={key}>
          {extra[key] ?? null}
          <div>{byKey.get(key)!.items.map((item) => <SettingRow key={item.key} item={item} />)}</div>
        </Section>
      ))}
      <Section id="roles"><RoleMatrix vocab={vocab} /></Section>
      <Section id="audit"><AuditPanel audit={audit} members={members} /></Section>
      <Section id="invariants"><div>{invariants.map((item) => <SettingRow key={item.key} item={item} />)}</div></Section>
    </div>
  );
}

export function ControlPanel() {
  const [res, retry] = useResource(loadPanel, []);
  return <Loaded res={res} retry={retry}>{(panel) => <PanelView panel={panel} reload={retry} />}</Loaded>;
}
