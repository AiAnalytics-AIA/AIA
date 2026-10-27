"use client";

// Profil (client-workspace C5, decision D5): what the client record says about the client.
// Its basic details (short code, industry, market, a few sentences), the people at the
// client who receive results, its brands and competitors, and its rules. The details and
// contacts live on the client record and no model reads them; brands and competitors are
// ENTITY items of the client's knowledge, because studies use them. Name and status stay
// where they are set: the client's name at its creation, its status with the administrator.

import { type FormEvent, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  type ClientBudget,
  type ClientContact,
  type ClientProfile,
  type ClientProfileFields,
  type ContactWrite,
  type KnowledgeItem,
  admin,
  workspace,
} from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { relative } from "@/lib/format";
import Link from "next/link";
import { Button, Chip, Field, Select, TextArea, TextInput } from "../../rehome/ui";
import { UndoToast, useUndo } from "../../ui/UndoToast";
import { CARD, Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { said } from "./KnowledgeLibrary";
import { ClientPage, useClient } from "./ClientContext";
import { ClientRulesEditor } from "./ClientRules";
import { roleLabel } from "./ClientDirectory";

const FIELDS: (keyof ClientProfileFields)[] = ["short_code", "industry", "market", "description"];
const ERROR = "rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault";
type EntityRole = "own_brand" | "competitor";

function Details({ clientId, profile, mayEdit, onSaved }: { clientId: string; profile: ClientProfile; mayEdit: boolean; onSaved: () => void }) {
  const [draft, setDraft] = useState<ClientProfileFields>(() => ({
    short_code: profile.short_code,
    industry: profile.industry,
    market: profile.market,
    description: profile.description,
  }));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const dirty = FIELDS.some((f) => draft[f] !== profile[f]);
  const set = (f: keyof ClientProfileFields) => (value: string) => {
    setSaved(false);
    setDraft((d) => ({ ...d, [f]: value }));
  };
  const save = (e: FormEvent) => {
    e.preventDefault();
    workspace.saveProfile(clientId, draft).then(
      () => {
        setError(null);
        setSaved(true);
        onSaved();
      },
      (err: unknown) => setError(said(err)),
    );
  };
  return (
    <form className={CARD} aria-labelledby="profile-details" onSubmit={save}>
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 id="profile-details" className="flex-1 text-base font-semibold">{t("aia.profile.detailsTitle")}</h2>
        {saved && !dirty ? <span role="status" className="text-xs text-ink-muted">{t("aia.profile.saved")}</span> : null}
      </div>
      <p className="mt-1 text-xs text-ink-faint">{t("aia.profile.detailsHint")}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)]">
        <Field label={t("aia.profile.fields.short_code")}>
          <TextInput value={draft.short_code} maxLength={16} readOnly={!mayEdit} onChange={(e) => set("short_code")(e.target.value)} />
        </Field>
        <Field label={t("aia.profile.fields.industry")}>
          <TextInput value={draft.industry} maxLength={120} readOnly={!mayEdit} onChange={(e) => set("industry")(e.target.value)} />
        </Field>
        <Field label={t("aia.profile.fields.market")}>
          <TextInput value={draft.market} maxLength={120} readOnly={!mayEdit} onChange={(e) => set("market")(e.target.value)} />
        </Field>
      </div>
      <Field label={t("aia.profile.fields.description")} className="mt-3">
        <TextArea value={draft.description} maxLength={4000} readOnly={!mayEdit} placeholder={t("aia.profile.descriptionPlaceholder")} onChange={(e) => set("description")(e.target.value)} />
      </Field>
      {error ? <p role="alert" className={`mt-3 ${ERROR}`}>{error}</p> : null}
      {mayEdit ? (
        <div className="mt-3">
          <Button type="submit" variant="primary" disabled={!dirty}>{t("aia.profile.save")}</Button>
        </div>
      ) : null}
    </form>
  );
}

function Entities({ clientId, mayEdit }: { clientId: string; mayEdit: boolean }) {
  const [version, setVersion] = useState(0);
  const [res, retry] = useResource(() => workspace.knowledge(clientId, "knowledge"), [clientId, version]);
  const [name, setName] = useState("");
  const [role, setRole] = useState<EntityRole>("competitor");
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const roleOf = (i: KnowledgeItem): EntityRole | null => {
    const r = i.content?.role;
    return i.kind === "ENTITY" && (r === "own_brand" || r === "competitor") ? r : null;
  };
  const add = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    workspace.propose(clientId, { kind: "ENTITY", title: name.trim(), content: { role } }).then(
      (p) => {
        setError(null);
        setName("");
        // Where the client asked for independent review, an addition waits for someone else.
        setNote(p.status === "PROPOSED" ? t("aia.profile.entityWaits") : null);
        setVersion((v) => v + 1);
      },
      (err: unknown) => setError(said(err)),
    );
  };
  return (
    <section className={CARD} aria-labelledby="profile-entities">
      <h2 id="profile-entities" className="text-base font-semibold">{t("aia.profile.entitiesTitle")}</h2>
      <p className="mt-1 text-xs text-ink-faint">{t("aia.profile.entitiesHint")}</p>
      <Loaded res={res} retry={retry}>
        {(items) => {
          const groups: [EntityRole, KnowledgeItem[]][] = (["own_brand", "competitor"] as EntityRole[]).map((r) => [r, items.filter((i) => roleOf(i) === r)]);
          return (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {groups.map(([r, list]) => (
                <div key={r}>
                  <h3 className="text-xs font-semibold text-ink-muted">{t(`aia.profile.entityRoles.${r}`)}</h3>
                  {list.length ? (
                    <ul className="mt-1.5 flex flex-wrap gap-1.5">
                      {list.map((i) => (
                        <li key={i.item_id} className="inline-flex min-h-7 items-center rounded-pill border border-border bg-surface-raised px-2.5 text-[13px]">{i.title}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1.5 text-xs text-ink-faint">{t("aia.profile.entitiesNone")}</p>
                  )}
                </div>
              ))}
            </div>
          );
        }}
      </Loaded>
      {mayEdit ? (
        <form className="mt-4 flex flex-wrap items-end gap-2 border-t border-border pt-3" onSubmit={add}>
          <Field label={t("aia.profile.entityName")} className="min-w-[12rem] flex-1">
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label={t("aia.profile.entityRole")}>
            <Select value={role} onChange={(e) => setRole(e.target.value as EntityRole)}>
              <option value="own_brand">{t("aia.profile.entityRoles.own_brand")}</option>
              <option value="competitor">{t("aia.profile.entityRoles.competitor")}</option>
            </Select>
          </Field>
          <Button type="submit" disabled={!name.trim()}>{t("aia.profile.entityAdd")}</Button>
        </form>
      ) : null}
      {note ? <p role="status" className="mt-2 text-xs text-status-you-ink">{note}</p> : null}
      {error ? <p role="alert" className={`mt-2 ${ERROR}`}>{error}</p> : null}
      <Link href={appRoutes.area(clientId, "knowledge")} className="mt-3 inline-block text-xs font-medium text-signal underline">{t("aia.profile.entitiesEdit")}</Link>
    </section>
  );
}

const EMPTY_CONTACT: ContactWrite = { name: "", role: "", email: "", receives_reports: false };

function ContactForm({ initial, onSubmit, onCancel }: { initial: ContactWrite; onSubmit: (c: ContactWrite) => void; onCancel: () => void }) {
  const [c, setC] = useState<ContactWrite>(initial);
  return (
    <form
      className="grid gap-2 rounded-sm border border-border p-3 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (c.name.trim()) onSubmit(c);
      }}
      // Esc leaves the form, as Zrušit does (design system v3, I-Klavesnice).
      onKeyDown={(e) => { if (e.key === "Escape" && !e.defaultPrevented) { e.preventDefault(); onCancel(); } }}
    >
      <Field label={t("aia.profile.contact.name")}>
        <TextInput value={c.name} onChange={(e) => setC({ ...c, name: e.target.value })} autoFocus />
      </Field>
      <Field label={t("aia.profile.contact.role")}>
        <TextInput value={c.role} onChange={(e) => setC({ ...c, role: e.target.value })} />
      </Field>
      <Field label={t("aia.profile.contact.email")}>
        <TextInput type="email" value={c.email} onChange={(e) => setC({ ...c, email: e.target.value })} />
      </Field>
      <label className="flex items-center gap-2 self-end pb-2 text-sm">
        <input type="checkbox" className="size-4" checked={c.receives_reports} onChange={(e) => setC({ ...c, receives_reports: e.target.checked })} />
        {t("aia.profile.contact.receivesReports")}
      </label>
      <div className="flex gap-2 sm:col-span-2">
        <Button small type="submit" variant="primary" disabled={!c.name.trim()}>{t("aia.profile.contact.save")}</Button>
        <Button small variant="quiet" onClick={onCancel}>{t("aia.cancel")}</Button>
      </div>
    </form>
  );
}

function Contacts({ clientId, contacts, mayEdit, onChanged }: { clientId: string; contacts: ClientContact[]; mayEdit: boolean; onChanged: () => void }) {
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);
  // A removed contact can be put back for 8 s (design system v3, I-VratitNeboPotvrdit): the same
  // name, role, e-mail and report choice, written again.
  const undo = useUndo();
  const remove = (c: ClientContact) =>
    void workspace.removeContact(clientId, c.contact_id).then(
      () => {
        setError(null);
        onChanged();
        undo.offer({
          message: tv("aia.profile.contact.removed", { name: c.name }),
          undo: () => void done(workspace.addContact(clientId, { name: c.name, role: c.role, email: c.email, receives_reports: c.receives_reports })),
        });
      },
      (err: unknown) => setError(said(err)),
    );
  const done = (work: Promise<unknown>) =>
    work.then(
      () => {
        setError(null);
        setEditing(null);
        onChanged();
      },
      (err: unknown) => setError(said(err)),
    );
  return (
    <section className={CARD} aria-labelledby="profile-contacts">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 id="profile-contacts" className="flex-1 text-base font-semibold">{t("aia.profile.contactsTitle")}</h2>
        {mayEdit && editing === null ? (
          <Button small icon="plus" onClick={() => setEditing("new")}>{t("aia.profile.contact.add")}</Button>
        ) : null}
      </div>
      <p className="mt-1 text-xs text-ink-faint">{t("aia.profile.contactsHint")}</p>
      {error ? <p role="alert" className={`mt-3 ${ERROR}`}>{error}</p> : null}
      {editing === "new" ? (
        <div className="mt-3">
          <ContactForm initial={EMPTY_CONTACT} onCancel={() => setEditing(null)} onSubmit={(c) => void done(workspace.addContact(clientId, c))} />
        </div>
      ) : null}
      {contacts.length ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <caption className="sr-only">{t("aia.profile.contactsTitle")}</caption>
            <thead>
              <tr className="border-b border-border text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-ink-muted">
                <th scope="col" className="py-2 pr-3">{t("aia.profile.contact.name")}</th>
                <th scope="col" className="py-2 pr-3">{t("aia.profile.contact.role")}</th>
                <th scope="col" className="py-2 pr-3">{t("aia.profile.contact.email")}</th>
                <th scope="col" className="py-2 pr-3">{t("aia.profile.contact.reports")}</th>
                {mayEdit ? <th scope="col" className="py-2"><span className="sr-only">{t("aia.profile.contact.actions")}</span></th> : null}
              </tr>
            </thead>
            <tbody>
              {contacts.map((c) =>
                editing === c.contact_id ? (
                  <tr key={c.contact_id}>
                    <td colSpan={5} className="py-2">
                      <ContactForm initial={c} onCancel={() => setEditing(null)} onSubmit={(next) => void done(workspace.changeContact(clientId, c.contact_id, next))} />
                    </td>
                  </tr>
                ) : (
                  <tr key={c.contact_id} className="border-b border-border last:border-b-0">
                    <td className="py-2 pr-3 font-medium">{c.name}</td>
                    <td className="py-2 pr-3 text-ink-muted">{c.role}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{c.email}</td>
                    <td className="py-2 pr-3">
                      <Chip tone="neutral">{c.receives_reports ? t("aia.profile.contact.yes") : t("aia.profile.contact.no")}</Chip>
                    </td>
                    {mayEdit ? (
                      <td className="whitespace-nowrap py-2 text-right">
                        <Button small variant="quiet" onClick={() => setEditing(c.contact_id)} aria-label={tv("aia.profile.contact.editOne", { name: c.name })}>
                          {t("aia.profile.contact.edit")}
                        </Button>
                        <Button small variant="quiet" onClick={() => remove(c)} aria-label={tv("aia.profile.contact.removeOne", { name: c.name })}>
                          {t("aia.profile.contact.remove")}
                        </Button>
                      </td>
                    ) : null}
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      ) : editing !== "new" ? (
        <div className="mt-3">
          <Empty>{t("aia.profile.contactsNone")}</Empty>
        </div>
      ) : null}
      <UndoToast offer={undo.current} onDone={undo.clear} />
    </section>
  );
}

function Rules({ mayAdminister }: { mayAdminister: boolean }) {
  const { client, reload } = useClient();
  const [error, setError] = useState<string | null>(null);
  const allowed = client.self_approval_allowed;
  const toggle = () =>
    admin.setSelfApproval({ allowed: !allowed, client_id: client.client_id }).then(
      () => {
        setError(null);
        reload();
      },
      (err: unknown) => setError(said(err)),
    );
  return (
    <section className={CARD} aria-labelledby="profile-rules">
      <h2 id="profile-rules" className="text-base font-semibold">{t("aia.profile.rulesTitle")}</h2>
      <div className="mt-3 flex items-start gap-3">
        <span id="self-approval-label" className="flex-1 text-sm">
          <span className="block font-medium">{t("aia.profile.selfApproval")}</span>
          <span className="block text-xs text-ink-muted">
            {allowed == null ? t("aia.profile.selfApprovalUnknown") : allowed ? t("aia.profile.selfApprovalOn") : t("aia.profile.selfApprovalOff")}
          </span>
        </span>
        {mayAdminister && allowed != null ? (
          <button
            type="button"
            role="switch"
            aria-checked={allowed}
            aria-labelledby="self-approval-label"
            onClick={() => void toggle()}
            className={`relative h-6 w-11 shrink-0 rounded-pill border-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${allowed ? "bg-signal" : "bg-border-strong"}`}
          >
            <span aria-hidden="true" className={`absolute top-0.5 size-5 rounded-full bg-surface-raised transition-[left] ${allowed ? "left-[22px]" : "left-0.5"}`} />
          </button>
        ) : null}
      </div>
      {!mayAdminister ? <p className="mt-2 text-xs text-ink-faint">{t("aia.profile.selfApprovalAdmin")}</p> : null}
      {error ? <p role="alert" className={`mt-2 ${ERROR}`}>{error}</p> : null}
      {/* The data posture and the wallet ceiling (D-17): set here, read on Nastavení → Přístup. */}
      <ClientRulesEditor clientId={client.client_id} clientName={client.name} mayAdminister={mayAdminister} />
    </section>
  );
}

function History({ history }: { history: ClientProfile["history"] }) {
  return (
    <section className={CARD} aria-labelledby="profile-history">
      <h2 id="profile-history" className="text-base font-semibold">{t("aia.profile.historyTitle")}</h2>
      {history.length ? (
        <ol className="mt-3 flex flex-col gap-2 text-xs leading-4">
          {history.map((h, i) => (
            <li key={`${h.action}-${h.at}-${i}`}>
              <span className="block text-ink">
                {h.action === "CLIENT_PROFILE_CHANGED"
                  ? tv("aia.profile.history.profile", { fields: h.fields.map((f) => t(`aia.profile.fields.${f}`)).join(", ") })
                  : tv(`aia.profile.history.${h.action}`, { name: h.contact_name ?? "" })}
              </span>
              <span className="text-ink-faint">{relative(h.at)}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-sm text-ink-muted">{t("aia.profile.historyNone")}</p>
      )}
    </section>
  );
}

const usd = (n: number) => `${n.toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD`;

/** The client's own budget (client-budget CB1): it pays for AI work on the client, not its studies. */
function Budget({ clientId, mayManage }: { clientId: string; mayManage: boolean }) {
  const [version, setVersion] = useState(0);
  const [res, retry] = useResource(() => workspace.budget(clientId), [clientId, version]);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const save = (e: FormEvent) => {
    e.preventDefault();
    const value = Number(editing);
    if (!Number.isFinite(value) || value < 0) return;
    workspace.setBudget(clientId, value).then(
      () => {
        setError(null);
        setEditing(null);
        setSaved(true);
        setVersion((v) => v + 1);
      },
      (err: unknown) => setError(said(err)),
    );
  };
  return (
    <section className={CARD} aria-labelledby="profile-budget">
      <div className="flex flex-wrap items-baseline gap-2">
        <h2 id="profile-budget" className="flex-1 text-base font-semibold">{t("aia.profile.budget.title")}</h2>
        {saved && editing === null ? <span role="status" className="text-xs text-ink-muted">{t("aia.profile.budget.saved")}</span> : null}
      </div>
      <p className="mt-1 text-xs leading-5 text-ink-faint">{t("aia.profile.budget.hint")}</p>
      <Loaded res={res} retry={retry}>
        {(b: ClientBudget) => (
          <>
            <dl className="mt-3 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
              <dt className="text-ink-muted">{t("aia.profile.budget.limit")}</dt>
              <dd className="font-mono">{usd(b.budget_usd)}</dd>
              <dt className="text-ink-muted">{t("aia.profile.budget.spent")}</dt>
              <dd className="font-mono">{usd(b.spent_usd)}</dd>
              {b.reserved_usd > 0 ? (
                <>
                  <dt className="text-ink-muted">{t("aia.profile.budget.reserved")}</dt>
                  <dd className="font-mono">{usd(b.reserved_usd)}</dd>
                </>
              ) : null}
              <dt className="text-ink-muted">{t("aia.profile.budget.available")}</dt>
              <dd className="font-mono font-semibold">{usd(b.available_usd)}</dd>
            </dl>
            {b.budget_usd === 0 ? <p className="mt-3 text-xs leading-5 text-status-you-ink">{t("aia.profile.budget.none")}</p> : null}
            {b.budget_usd > 0 && b.budget_usd < b.spent_usd ? <p className="mt-3 text-xs leading-5 text-status-you-ink">{t("aia.profile.budget.belowSpent")}</p> : null}
            {mayManage && editing === null ? (
              <Button small className="mt-3" onClick={() => { setSaved(false); setEditing(String(b.budget_usd)); }}>{t("aia.profile.budget.set")}</Button>
            ) : null}
            {mayManage && editing !== null ? (
              <form className="mt-3 flex flex-wrap items-end gap-2" onSubmit={save}>
                <Field label={t("aia.profile.budget.field")}>
                  <TextInput type="number" min={0} max={1000000} step="0.01" required className="w-36" value={editing} onChange={(e) => setEditing(e.target.value)} />
                </Field>
                <Button small variant="primary" type="submit">{t("aia.profile.budget.save")}</Button>
                <Button small variant="quiet" onClick={() => { setEditing(null); setError(null); }}>{t("aia.profile.budget.cancel")}</Button>
              </form>
            ) : null}
            {error ? <p role="alert" className={`mt-3 ${ERROR}`}>{error}</p> : null}
          </>
        )}
      </Loaded>
    </section>
  );
}

export function ProfileArea() {
  const { client } = useClient();
  const mayEdit = client.permissions.includes("EDIT_CLIENT_PROFILE");
  const mayKnowledge = client.permissions.includes("VIEW_CLIENT_KNOWLEDGE");
  const mayPropose = client.permissions.includes("PROPOSE_CLIENT_KNOWLEDGE");
  const mayCosts = client.permissions.includes("VIEW_CLIENT_COSTS");
  const mayBudget = client.permissions.includes("MANAGE_CLIENT_BUDGET");
  const [version, setVersion] = useState(0);
  const [res, retry] = useResource(() => workspace.profile(client.client_id), [client.client_id, version]);
  const [me] = useResource(() => workspace.me(), []);
  const mayAdminister = me.state === "ready" && me.data.may_administer;
  const changed = () => setVersion((v) => v + 1);
  return (
    <ClientPage sub={t("aia.profile.sub")}>
      <Loaded res={res} retry={retry}>
        {(profile) => (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
            <div className="flex min-w-0 flex-col gap-6">
              <Details key={`${profile.short_code}|${profile.industry}|${profile.market}|${profile.description}`} clientId={client.client_id} profile={profile} mayEdit={mayEdit} onSaved={changed} />
              {mayKnowledge ? <Entities clientId={client.client_id} mayEdit={mayPropose} /> : null}
              <Contacts clientId={client.client_id} contacts={profile.contacts} mayEdit={mayEdit} onChanged={changed} />
            </div>
            <div className="flex flex-col gap-6">
              <section className={CARD} aria-labelledby="profile-record">
                <h2 id="profile-record" className="text-base font-semibold">{t("aia.profile.recordTitle")}</h2>
                <dl className="mt-3 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
                  <dt className="text-ink-muted">{t("aia.profile.name")}</dt>
                  <dd>{client.name}</dd>
                  <dt className="text-ink-muted">{t("aia.profile.status")}</dt>
                  <dd>
                    <Chip tone="neutral">{t(`aia.client.status.${client.status}`)}</Chip>
                  </dd>
                  <dt className="text-ink-muted">{t("aia.profile.yourRole")}</dt>
                  <dd>{roleLabel(client.your_role)}</dd>
                </dl>
                <p className="mt-4 text-xs leading-5 text-ink-faint">{t("aia.profile.statusOwner")}</p>
              </section>
              {mayCosts ? <Budget clientId={client.client_id} mayManage={mayBudget} /> : null}
              <Rules mayAdminister={mayAdminister} />
              <History history={profile.history} />
            </div>
          </div>
        )}
      </Loaded>
    </ClientPage>
  );
}
