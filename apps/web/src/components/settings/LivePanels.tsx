import type { Client, Member, SelfApprovalLevels, Study, Vocabularies, AuditEntry } from "@/lib/api/types";
import type { ApiResult } from "@/lib/api/server";
import { t } from "@/i18n/t";
import {
  addMember,
  createClient,
  createStudy,
  grantClientAccess,
  grantStudyAccess,
  setClientStatus,
  setSelfApproval,
  setStudyBudget,
  setStudyStatus,
} from "@/app/org/[orgSlug]/admin/settings/actions";
import { ActionForm, Field } from "./ActionForm";
import { inputClass } from "./styles";
import { Subhead, Unavailable } from "./Section";
import { Value } from "./SettingRow";

function errorText(result: ApiResult<unknown>): string {
  if (result.ok) return "";
  const e = result.error;
  return `${e.status === null ? "API nedostupné" : `HTTP ${e.status}`} · ${e.code}: ${e.message}`;
}

function Th({ children }: { children?: React.ReactNode }) {
  return <th className="px-2 py-1 text-left text-[11px] font-semibold uppercase tracking-wide text-zinc-500">{children}</th>;
}
function Td({ children, mono = false }: { children: React.ReactNode; mono?: boolean }) {
  return <td className={`px-2 py-1.5 align-top text-sm ${mono ? "font-mono text-xs" : ""}`}>{children}</td>;
}

function RoleSelect({ roles, name = "role", defaultValue }: { roles: string[]; name?: string; defaultValue?: string }) {
  return (
    <select name={name} defaultValue={defaultValue ?? roles[0]} className={inputClass}>
      {roles.map((r) => (
        <option key={r} value={r}>
          {t(`settings.roles.${r}`)} ({r})
        </option>
      ))}
    </select>
  );
}

function MemberSelect({ members }: { members: Member[] }) {
  return (
    <select name="user_id" className={inputClass} required>
      {members.map((m) => (
        <option key={m.user_id} value={m.user_id}>
          {m.display_name ? `${m.display_name} · ` : ""}
          {m.email}
        </option>
      ))}
    </select>
  );
}

// ------------------------------------------------------------------ members

export function MembersPanel({
  members,
  vocab,
  canAdminister,
}: {
  members: ApiResult<Member[]>;
  vocab: Vocabularies;
  canAdminister: boolean;
}) {
  return (
    <div className="space-y-3">
      <Subhead>{t("settings.members.title")}</Subhead>
      {members.ok ? (
        <table className="w-full">
          <thead>
            <tr><Th>E-mail</Th><Th>{t("settings.members.name")}</Th><Th>{t("settings.members.role")}</Th><Th>{t("settings.members.active")}</Th></tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {members.data.map((m) => (
              <tr key={m.user_id}>
                <Td>{m.email}</Td>
                <Td>{m.display_name || <Value value={null} />}</Td>
                <Td>{t(`settings.roles.${m.organization_role}`)} <code className="text-[11px] text-zinc-500">{m.organization_role}</code></Td>
                <Td><Value value={m.is_active} /></Td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <Unavailable what={t("settings.members.title")} reason={errorText(members)} />
      )}
      {canAdminister ? (
        <ActionForm action={addMember} submit={t("settings.members.add")} inline>
          <Field label="E-mail"><input name="email" type="email" required className={inputClass} /></Field>
          <Field label={t("settings.members.name")}><input name="display_name" className={inputClass} /></Field>
          <Field label={t("settings.members.role")}><RoleSelect roles={vocab.organization_roles} defaultValue="MEMBER" /></Field>
        </ActionForm>
      ) : null}
      <p className="text-xs text-zinc-500">{t("settings.members.note")}</p>
    </div>
  );
}

// ------------------------------------------------------------------ clients

export function ClientsPanel({
  clients,
  members,
  vocab,
  canAdminister,
}: {
  clients: ApiResult<Client[]>;
  members: ApiResult<Member[]>;
  vocab: Vocabularies;
  canAdminister: boolean;
}) {
  const scopeRoles = vocab.scope_roles.map((r) => r.role);
  return (
    <div className="space-y-3">
      <Subhead>{t("settings.clients.title")}</Subhead>
      {clients.ok ? (
        clients.data.length === 0 ? (
          <p className="text-xs text-zinc-600">{t("settings.clients.none")}</p>
        ) : (
          <table className="w-full">
            <thead>
              <tr><Th>{t("settings.clients.name")}</Th><Th>ID</Th><Th>{t("settings.clients.studies")}</Th><Th>{t("settings.clients.status")}</Th></tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {clients.data.map((c) => (
                <tr key={c.client_id}>
                  <Td>
                    {c.name} <span className="text-xs text-zinc-500">/{c.slug}</span>
                  </Td>
                  <Td mono>{c.client_id}</Td>
                  <Td mono>{c.study_count}</Td>
                  <Td>
                    {canAdminister ? (
                      <ActionForm action={setClientStatus} submit={t("settings.save")} inline>
                        <input type="hidden" name="client_id" value={c.client_id} />
                        <select name="status" defaultValue={c.status} className={inputClass}>
                          {vocab.client_statuses.map((s) => (
                            <option key={s} value={s}>{t(`settings.clientStatus.${s}`)}</option>
                          ))}
                        </select>
                      </ActionForm>
                    ) : (
                      t(`settings.clientStatus.${c.status}`)
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : (
        <Unavailable what={t("settings.clients.title")} reason={errorText(clients)} />
      )}
      {canAdminister ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-lg border border-zinc-100 p-3">
            <div className="mb-2 text-xs font-medium text-zinc-700">{t("settings.clients.create")}</div>
            <ActionForm action={createClient} submit={t("settings.clients.createSubmit")}>
              <Field label={t("settings.clients.name")}><input name="name" required className={inputClass} /></Field>
              <Field label="Slug"><input name="slug" required pattern="[a-z0-9][a-z0-9-]*" className={inputClass} /></Field>
              <Field label={t("settings.clients.reference")}><input name="reference" className={inputClass} /></Field>
            </ActionForm>
          </div>
          <div className="rounded-lg border border-zinc-100 p-3">
            <div className="mb-2 text-xs font-medium text-zinc-700">{t("settings.clients.grant")}</div>
            {clients.ok && members.ok && clients.data.length > 0 ? (
              <ActionForm action={grantClientAccess} submit={t("settings.grant")}>
                <Field label={t("settings.clients.client")}>
                  <select name="client_id" className={inputClass}>
                    {clients.data.map((c) => <option key={c.client_id} value={c.client_id}>{c.name}</option>)}
                  </select>
                </Field>
                <Field label={t("settings.members.member")}><MemberSelect members={members.data} /></Field>
                <Field label={t("settings.members.role")}><RoleSelect roles={scopeRoles} /></Field>
              </ActionForm>
            ) : (
              <p className="text-xs text-zinc-600">{t("settings.clients.grantNeeds")}</p>
            )}
            <p className="mt-2 text-xs text-zinc-500">{t("settings.clients.grantNote")}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------ studies

export type StudyRow = { study: Study; detail: ApiResult<Study> };

export function StudiesPanel({
  studies,
  clients,
  members,
  vocab,
  canAdminister,
}: {
  studies: ApiResult<StudyRow[]>;
  clients: ApiResult<Client[]>;
  members: ApiResult<Member[]>;
  vocab: Vocabularies;
  canAdminister: boolean;
}) {
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  const scopeRoles = vocab.scope_roles.map((r) => r.role);
  return (
    <div className="space-y-3">
      <Subhead>{t("settings.studies.title")}</Subhead>
      {studies.ok ? (
        studies.data.length === 0 ? (
          <p className="text-xs text-zinc-600">{t("settings.studies.none")}</p>
        ) : (
          <div className="space-y-2">
            {studies.data.map(({ study, detail }) => (
              <details key={study.study_id} className="rounded-lg border border-zinc-200">
                <summary className="flex cursor-pointer flex-wrap items-center gap-3 px-3 py-2 text-sm">
                  <span className="font-medium text-zinc-900">{study.name}</span>
                  <span className="text-xs text-zinc-500">{clientName.get(study.client_id) ?? study.client_id}</span>
                  <span className="rounded border border-zinc-200 px-1.5 text-xs">{t(`settings.studyStatus.${study.status}`)}</span>
                  <span className="ml-auto text-xs text-zinc-600">
                    {detail.ok && detail.data.budget_usd !== null ? (
                      <>
                        {t("settings.studies.budget")}: <Value value={detail.data.budget_usd} unit="USD" /> · {t("settings.studies.spent")}:{" "}
                        <Value value={detail.data.spent_usd} unit="USD" /> · {t("settings.studies.remaining")}:{" "}
                        <Value value={detail.data.remaining_usd} unit="USD" />
                      </>
                    ) : (
                      <span title={errorText(detail)} className="rounded border border-dashed border-zinc-400 px-1.5">
                        {t("settings.studies.costsHidden")}
                      </span>
                    )}
                  </span>
                </summary>
                <div className="grid gap-4 border-t border-zinc-100 p-3 lg:grid-cols-3">
                  <div>
                    <div className="mb-1 text-xs font-medium text-zinc-700">{t("settings.studies.status")}</div>
                    <ActionForm action={setStudyStatus} submit={t("settings.save")} inline>
                      <input type="hidden" name="study_id" value={study.study_id} />
                      <select name="status" defaultValue={study.status} className={inputClass}>
                        {vocab.study_statuses.map((s) => <option key={s} value={s}>{t(`settings.studyStatus.${s}`)}</option>)}
                      </select>
                    </ActionForm>
                  </div>
                  <div>
                    <div className="mb-1 text-xs font-medium text-zinc-700">{t("settings.studies.budgetCeiling")}</div>
                    <ActionForm action={setStudyBudget} submit={t("settings.save")} inline>
                      <input type="hidden" name="study_id" value={study.study_id} />
                      <input
                        name="budget_usd"
                        type="number"
                        min={0}
                        max={1000000}
                        step="0.01"
                        required
                        defaultValue={detail.ok && detail.data.budget_usd !== null ? detail.data.budget_usd : undefined}
                        className={`${inputClass} w-32`}
                      />
                      <span className="pb-2 text-xs text-zinc-500">USD</span>
                    </ActionForm>
                  </div>
                  <div>
                    <div className="mb-1 text-xs font-medium text-zinc-700">{t("settings.studies.grant")}</div>
                    {members.ok ? (
                      <ActionForm action={grantStudyAccess} submit={t("settings.grant")} inline>
                        <input type="hidden" name="study_id" value={study.study_id} />
                        <MemberSelect members={members.data} />
                        <RoleSelect roles={scopeRoles} />
                      </ActionForm>
                    ) : (
                      <Unavailable what={t("settings.members.title")} reason={errorText(members)} />
                    )}
                  </div>
                  <p className="text-xs text-zinc-500 lg:col-span-3">{t("settings.studies.permissionNote")}</p>
                </div>
              </details>
            ))}
          </div>
        )
      ) : (
        <Unavailable what={t("settings.studies.title")} reason={errorText(studies)} />
      )}
      {canAdminister && clients.ok && clients.data.length > 0 ? (
        <div className="rounded-lg border border-zinc-100 p-3">
          <div className="mb-2 text-xs font-medium text-zinc-700">{t("settings.studies.create")}</div>
          <ActionForm action={createStudy} submit={t("settings.studies.createSubmit")} inline>
            <Field label={t("settings.clients.client")}>
              <select name="client_id" className={inputClass}>
                {clients.data.map((c) => <option key={c.client_id} value={c.client_id}>{c.name}</option>)}
              </select>
            </Field>
            <Field label={t("settings.studies.name")}><input name="name" required className={inputClass} /></Field>
            <Field label="Slug"><input name="slug" required pattern="[a-z0-9][a-z0-9-]*" className={inputClass} /></Field>
            <Field label={`${t("settings.studies.budget")} (USD)`}>
              <input name="budget_usd" type="number" min={0} max={1000000} step="0.01" required className={`${inputClass} w-32`} />
            </Field>
          </ActionForm>
        </div>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------- self-approval

function Tri({ value }: { value: boolean | null }) {
  if (value === null) return <span className="rounded border border-dashed border-zinc-400 px-1.5 text-xs">{t("settings.approvals.inherit")}</span>;
  return value ? (
    <span className="rounded border border-amber-300 bg-amber-50 px-1.5 text-xs text-amber-900">{t("settings.approvals.allowed")}</span>
  ) : (
    <span className="rounded border border-zinc-300 px-1.5 text-xs">{t("settings.approvals.forbidden")}</span>
  );
}

function TriSelect() {
  return (
    <select name="allowed" defaultValue="" required className={inputClass}>
      <option value="" disabled>{t("settings.approvals.choose")}</option>
      <option value="forbid">{t("settings.approvals.forbid")}</option>
      <option value="allow">{t("settings.approvals.allow")}</option>
      <option value="inherit">{t("settings.approvals.inheritOption")}</option>
    </select>
  );
}

export function SelfApprovalPanel({
  levels,
  clients,
  studies,
  canAdminister,
}: {
  levels: ApiResult<SelfApprovalLevels> | null;
  clients: ApiResult<Client[]>;
  studies: ApiResult<StudyRow[]>;
  canAdminister: boolean;
}) {
  if (!canAdminister || levels === null) {
    return <p className="text-xs text-zinc-600">{t("settings.approvals.adminOnly")}</p>;
  }
  if (!levels.ok) return <Unavailable what={t("settings.approvals.title")} reason={errorText(levels)} />;
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  const studyName = new Map(studies.ok ? studies.data.map((s) => [s.study.study_id, s.study.name]) : []);
  return (
    <div className="space-y-3">
      <Subhead>{t("settings.approvals.title")}</Subhead>
      <p className="text-xs text-zinc-600">{t("settings.approvals.rule")}</p>
      <table className="w-full">
        <thead><tr><Th>{t("settings.approvals.level")}</Th><Th>{t("settings.approvals.stored")}</Th><Th /></tr></thead>
        <tbody className="divide-y divide-zinc-100">
          <tr>
            <Td>{t("settings.approvals.organization")}</Td>
            <Td><Tri value={levels.data.organization} /></Td>
            <Td>
              <ActionForm action={setSelfApproval} submit={t("settings.save")} inline>
                <input type="hidden" name="target" value="" />
                <TriSelect />
              </ActionForm>
            </Td>
          </tr>
          {levels.data.clients.map((c) => (
            <tr key={c.client_id}>
              <Td>{t("settings.clients.client")}: {clientName.get(c.client_id) ?? c.client_id}</Td>
              <Td><Tri value={c.allowed} /></Td>
              <Td>
                <ActionForm action={setSelfApproval} submit={t("settings.save")} inline>
                  <input type="hidden" name="target" value={`client:${c.client_id}`} />
                  <TriSelect />
                </ActionForm>
              </Td>
            </tr>
          ))}
          {levels.data.studies.map((s) => (
            <tr key={s.study_id}>
              <Td>{t("settings.studies.study")}: {studyName.get(s.study_id) ?? s.study_id}</Td>
              <Td><Tri value={s.allowed} /></Td>
              <Td>
                <ActionForm action={setSelfApproval} submit={t("settings.save")} inline>
                  <input type="hidden" name="target" value={`study:${s.study_id}`} />
                  <TriSelect />
                </ActionForm>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="rounded-lg border border-zinc-100 p-3">
        <div className="mb-2 text-xs font-medium text-zinc-700">{t("settings.approvals.addOverride")}</div>
        <ActionForm action={setSelfApproval} submit={t("settings.save")} inline>
          <select name="target" required className={inputClass} defaultValue="">
            <option value="" disabled>{t("settings.approvals.chooseTarget")}</option>
            {clients.ok ? clients.data.map((c) => <option key={c.client_id} value={`client:${c.client_id}`}>{t("settings.clients.client")}: {c.name}</option>) : null}
            {studies.ok ? studies.data.map(({ study }) => <option key={study.study_id} value={`study:${study.study_id}`}>{t("settings.studies.study")}: {study.name}</option>) : null}
          </select>
          <TriSelect />
        </ActionForm>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------- the rest

export function ProvidersTable({ vocab }: { vocab: Vocabularies }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div>
        <Subhead>{t("settings.ai.providers")}</Subhead>
        <table className="mt-1 w-full">
          <tbody className="divide-y divide-zinc-100">
            {vocab.providers.map((p) => (
              <tr key={p.id}>
                <Td>{p.label}</Td>
                <Td mono>{p.id}</Td>
                <Td>{p.paid ? t("settings.ai.paid") : t("settings.ai.subscription")}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <Subhead>{t("settings.ai.policies")}</Subhead>
        <ul className="mt-1 space-y-1">
          {vocab.provider_policies.map((p) => (
            <li key={p} className="text-sm">
              <code className="text-xs">{p}</code> <span className="text-xs text-zinc-600">— {t(`settings.policy.${p}`)}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <Subhead>{t("settings.ai.capabilities")}</Subhead>
        <ul className="mt-1 space-y-1">
          {vocab.model_capabilities.map((c) => (
            <li key={c} className="text-sm">
              <code className="text-xs">{c}</code> <span className="text-xs text-zinc-600">— {t(`settings.capability.${c}`)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-zinc-500">{t("settings.ai.modelPolicyNote")}</p>
      </div>
    </div>
  );
}

export function DataClassesList({ vocab }: { vocab: Vocabularies }) {
  return (
    <div>
      <Subhead>{t("settings.residency.classes")}</Subhead>
      <ul className="mt-1 space-y-1">
        {vocab.data_classes.map((c) => (
          <li key={c} className="text-sm">
            <code className="text-xs">{c}</code> <span className="text-xs text-zinc-600">— {t(`settings.dataClass.${c}`)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RoleMatrix({ vocab }: { vocab: Vocabularies }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr>
            <Th>{t("settings.roles.permission")}</Th>
            {vocab.scope_roles.map((r) => <Th key={r.role}>{t(`settings.roles.${r.role}`)}</Th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {vocab.permissions.map((p) => (
            <tr key={p}>
              <Td><code className="text-xs">{p}</code></Td>
              {vocab.scope_roles.map((r) => (
                <Td key={r.role}>
                  {r.permissions.includes(p) ? <span aria-label="ano">●</span> : <span aria-label="ne" className="text-zinc-300">○</span>}
                </Td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StagesList({ vocab }: { vocab: Vocabularies }) {
  const col = (title: string, stages: Vocabularies["research_stages"]) => (
    <div>
      <Subhead>{title}</Subhead>
      <ol className="mt-1 list-decimal pl-5 text-sm">
        {stages.map((s) => <li key={s.id}>{s.label ?? s.id} <code className="text-[11px] text-zinc-500">{s.id}</code></li>)}
      </ol>
    </div>
  );
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {col(t("settings.stages.research"), vocab.research_stages)}
      {col(t("settings.stages.simulation"), vocab.simulation_stages)}
    </div>
  );
}

export function AuditPanel({ audit, members }: { audit: ApiResult<AuditEntry[]> | null; members: ApiResult<Member[]> }) {
  // User ids are shown as e-mails where the member list resolves them; an id the
  // list does not know stays an id rather than becoming a guess.
  const who = new Map(members.ok ? members.data.map((m) => [m.user_id, m.email]) : []);
  const person = (id: string | null) => (id ? (who.get(id) ?? id) : "—");
  if (audit === null) return <p className="text-xs text-zinc-600">{t("settings.audit.adminOnly")}</p>;
  if (!audit.ok) return <Unavailable what={t("settings.audit.title")} reason={errorText(audit)} />;
  if (audit.data.length === 0) return <p className="text-xs text-zinc-600">{t("settings.audit.none")}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead><tr><Th>{t("settings.audit.when")}</Th><Th>{t("settings.audit.action")}</Th><Th>{t("settings.audit.actor")}</Th><Th>{t("settings.audit.subject")}</Th><Th>{t("settings.audit.scope")}</Th><Th>{t("settings.audit.detail")}</Th></tr></thead>
        <tbody className="divide-y divide-zinc-100">
          {audit.data.map((e) => (
            <tr key={e.event_id}>
              <Td mono>{e.created_at ?? "—"}</Td>
              <Td mono>{e.action}</Td>
              <Td mono>{person(e.actor_id)}</Td>
              <Td mono>{person(e.subject_user_id)}</Td>
              <Td mono>{e.study_id ?? e.client_id ?? "—"}</Td>
              <Td>{[e.role, e.reason].filter(Boolean).join(" · ") || "—"}</Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
