"use client";

// Přístup a schvalování as the redesign draws it (settings-redesign chunk 3, design artifact
// 8W9LR8Ju9BWnR5JACmiWv7, Access board): members with their role chosen in the row, the roles
// explained, self-approval above the clients, and each client's status and self-approval chosen
// in its row. Every change is one API call made where the value is shown (input standard I3/I4);
// a role change offers Vrátit for 8 s (I6). The Metodik mark is the OWNER's to grant (#823, D-14);
// deactivating a member seals their Lead (#830, ADR 0030), both at once with Vrátit. A client's
// data posture and wallet ceiling are read here (#853) and set on its Profil → Pravidla (D-17).

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type KeyboardEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type AdminClient, type ClientRules, type Member, type SelfApprovalLevels, type Vocabularies, ApiError, Unauthenticated, admin, clientRules } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { useSession } from "@/lib/auth";
import type { SaveState } from "@/lib/inline-edit";
import { usd } from "@/lib/researcher-spend";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { InlineText } from "../../ui/InlineText";
import { Switch } from "../../ui/Switch";
import { FOCUS, SaveNote } from "../../ui/parts";
import { UndoToast, useUndo } from "../../ui/UndoToast";
import { Button } from "../../rehome/ui";
import { describeError, describeMemberError } from "./errors";

const P = "aia.settings.panel";
const A = `${P}.accessTab`;

type Part<T> = { ok: true; data: T } | { ok: false; message: string };

/** One save made where its value is shown: its state beside the value, a refusal said there. */
function useSave(reload: () => void) {
  const router = useRouter();
  const [state, setState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const run = async (call: () => Promise<unknown>): Promise<boolean> => {
    setState("saving");
    setError(null);
    try {
      await call();
      setState("saved");
      reload();
      return true;
    } catch (e) {
      if (e instanceof Unauthenticated) {
        router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search + window.location.hash)}`);
        return false;
      }
      setState("failed");
      setError(describeMemberError(e));
      return false;
    }
  };
  return { state, error, run };
}

function CardHead({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-base font-semibold">{title}</h3>
      {children ? <div className="flex flex-wrap items-center gap-1.5">{children}</div> : null}
    </div>
  );
}

function Count({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "signal" }) {
  return <span className={`inline-flex min-h-[22px] items-center rounded-pill border px-2 text-xs whitespace-nowrap ${tone === "signal" ? "border-signal-edge bg-signal-tint text-ink" : "border-border bg-surface-raised text-ink-muted"}`}>{children}</span>;
}

/** The plain fact that AIA does not have something yet, where it would be. */
function NotYetChip() {
  return <span data-not-yet className="inline-flex rounded-sm border border-dashed border-border-strong px-2 py-0.5 text-xs whitespace-nowrap text-ink-muted">{t(`${P}.notYet`)}</span>;
}

const CARD = "rounded-md border border-border bg-surface-raised px-6 py-5";
const GRID_HEAD = "px-2 py-1.5 text-left text-xs font-normal text-ink-faint";

// ---------------------------------------------------------------- members

function MemberRow({ m, roles, locked, lockedWhy, canAdminister, owner, self, reload, offerUndo }: {
  m: Member; roles: readonly string[]; locked: boolean; lockedWhy: string | null; canAdminister: boolean;
  /** The signed-in person is an OWNER: only they grant the Metodik mark. */
  owner: boolean;
  /** The signed-in person's own row. */
  self: boolean;
  reload: () => void;
  offerUndo: (message: string, undo: () => void) => void;
}) {
  const { state, error, run } = useSave(reload);
  const [note, setNote] = useState<string | null>(null);
  // The membership call writes the name and the role together: each save sends the newest of both,
  // so a role chosen while the list is still re-reading a new name never writes the old name back.
  const typed = useRef<string | null>(null);
  // Once the list shows a name read back, that read is the newest.
  useEffect(() => { typed.current = null; }, [m.display_name]);
  const name = () => typed.current ?? m.display_name;
  const save = (display_name: string, role: string) => admin.addMember({ email: m.email, display_name, role });
  const setRole = async (role: string) => {
    const before = m.organization_role;
    setNote(null);
    if (await run(() => save(name(), role))) {
      // An OWNER who steps down is no OWNER to undo it (owner_only): another owner restores it.
      if (self && before === "OWNER" && role !== "OWNER") { setNote(t(`${A}.selfDemoted`)); return; }
      offerUndo(tv(`${A}.roleChanged`, { who: name() || m.email, role: t(`aia.orgRoles.${role}`) }), () => {
        void run(() => save(name(), before));
      });
    }
  };
  const setName = (value: string) => {
    typed.current = value.trim();
    // A refused name is not the newest: a later role change must not send it again.
    return save(typed.current, m.organization_role).then(reload, (e: unknown) => { typed.current = null; throw e; });
  };
  const who = m.display_name || m.email;
  const deactivatedHere = !!m.deactivated_at;
  const mark = useSave(reload);
  const membership = useSave(reload);
  const setMark = async (on: boolean) => {
    if (await mark.run(() => admin.setMethodologist(m.user_id, on))) {
      offerUndo(tv(`${A}.${on ? "metodikGranted" : "metodikRevoked"}`, { who }), () => { void mark.run(() => admin.setMethodologist(m.user_id, !on)); });
    }
  };
  // Deactivation is at once and undone by reactivating: within 30 days the Lead is unsealed for them.
  const deactivate = async () => {
    if (await membership.run(() => admin.deactivateMember(m.user_id))) {
      offerUndo(tv(`${A}.deactivated`, { who }), () => { void membership.run(() => admin.reactivateMember(m.user_id)); });
    }
  };
  const eraseOn = m.lead_erase_after ? new Intl.DateTimeFormat("cs-CZ", { dateStyle: "medium", timeZone: "Europe/Prague" }).format(new Date(m.lead_erase_after)) : null;
  const initials = (m.display_name || m.email).split(/[\s.@]+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
  return (
    <div role="row" data-member={m.user_id} data-deactivated={deactivatedHere ? "true" : undefined} className={`contents ${m.is_active ? "" : "[&>div]:text-ink-faint"}`}>
      <div role="cell" className="flex min-w-0 items-center gap-2 border-t border-border px-2 py-2">
        <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-sunken text-xs font-medium text-ink-muted">{initials}</span>
        <span className="min-w-0">
          {canAdminister ? (
            <InlineText value={m.display_name} label={tv(`${A}.nameOf`, { who: m.email })} placeholder={t(`${P}.members.noName`)}
              onCommit={setName} />
          ) : <span className="block truncate">{m.display_name || <span className="text-ink-muted">{t(`${P}.members.noName`)}</span>}</span>}
          <span className="block truncate text-xs text-ink-faint">{m.email}</span>
        </span>
      </div>
      <div role="cell" className="border-t border-border px-2 py-2">
        {canAdminister && !locked ? (
          <ChoiceChips label={tv(`${A}.roleOf`, { who: m.email })} value={m.organization_role} options={roles.map((r) => ({ key: r, label: t(`aia.orgRoles.${r}`) }))} onChange={(role) => void setRole(role)} />
        ) : (
          <span className="text-sm">{t(`aia.orgRoles.${m.organization_role}`)}{lockedWhy ? <span className="block text-xs text-ink-faint">{lockedWhy}</span> : null}</span>
        )}
        {error ? <p role="alert" className="mt-1 text-xs text-status-fault">{error}</p> : null}
        {note ? <p role="status" data-self-demoted className="mt-1 max-w-64 text-xs text-ink-muted">{note}</p> : null}
      </div>
      <div role="cell" className="border-t border-border px-2 py-2">
        <Switch on={m.methodologist} label={tv(`${A}.metodikOf`, { who: m.email })} disabled={!owner || !m.is_active || mark.state === "saving"} onChange={(on) => void setMark(on)} />
        {!owner && canAdminister ? <span className="block text-xs text-ink-faint">{t(`${A}.metodikOwnerOnly`)}</span> : null}
        {mark.error ? <p role="alert" className="mt-1 max-w-56 text-xs text-status-fault">{mark.error}</p> : null}
      </div>
      <div role="cell" className="border-t border-border px-2 py-2 text-sm">
        {t(`${A}.${m.is_active ? "active" : "inactive"}`)}
        {deactivatedHere ? <span data-lead-sealed={m.user_id} className="block max-w-64 text-xs leading-5 text-ink-faint">{eraseOn ? tv(`${A}.sealed`, { when: eraseOn }) : t(`${A}.sealedNoDate`)}</span> : null}
        <span className="block"><SaveNote state={state === "idle" ? (mark.state === "idle" ? membership.state : mark.state) : state} /></span>
        {membership.error ? <p role="alert" className="mt-1 max-w-56 text-xs text-status-fault">{membership.error}</p> : null}
      </div>
      <div role="cell" className="border-t border-border px-2 py-2">
        {canAdminister && m.is_active && !self ? (
          <Button small variant="quiet" disabled={locked || membership.state === "saving"} aria-label={tv(`${A}.deactivateOf`, { who: m.email })} onClick={() => void deactivate()}>{t(`${A}.deactivate`)}</Button>
        ) : null}
        {canAdminister && deactivatedHere ? (
          <Button small disabled={membership.state === "saving"} aria-label={tv(`${A}.restoreOf`, { who: m.email })} onClick={() => void membership.run(() => admin.reactivateMember(m.user_id))}>{t(`${A}.restore`)}</Button>
        ) : null}
      </div>
    </div>
  );
}

/** One address, one @, a dot in the domain: what a person can be invited at. The API decides the rest. */
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function AddMemberRow({ roles, reload }: { roles: readonly string[]; reload: () => void }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("MEMBER");
  const { state, error, run } = useSave(reload);
  const [problem, setProblem] = useState<string | null>(null);
  const cancel = () => { setOpen(false); setEmail(""); setProblem(null); };
  const add = async () => {
    const e = email.trim();
    if (!e) return;
    // Said at the field (I9): the row has no form, so the browser's own e-mail check never runs.
    if (!EMAIL.test(e)) { setProblem(t(`${A}.badEmail`)); return; }
    setProblem(null);
    if (await run(() => admin.addMember({ email: e, display_name: "", role }))) { setEmail(""); setOpen(false); }
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") { e.preventDefault(); void add(); }
    if (e.key === "Escape") { e.preventDefault(); cancel(); }
  };
  if (!open) {
    return <div role="row" className="contents"><div role="cell" className="col-span-full border-t border-border px-2 py-2">
      <Button small variant="quiet" onClick={() => setOpen(true)}>{`+ ${t(`${P}.members.add`)}`}</Button>
      <SaveNote state={state} />
    </div></div>;
  }
  const choices = roles.filter((r) => r !== "OWNER");
  return (
    <div role="row" data-member-new className="contents">
      <div role="cell" className="border-t border-border bg-surface-sunken px-2 py-2">
        <input type="email" autoFocus aria-label={t(`${A}.newEmail`)} aria-invalid={problem ? true : undefined} placeholder="jmeno@organizace.cz" value={email} onChange={(e) => { setEmail(e.target.value); if (problem && EMAIL.test(e.target.value.trim())) setProblem(null); }} onKeyDown={onKey}
          className={`min-h-9 w-full rounded-sm border border-border-strong bg-surface-raised px-2 text-sm ${FOCUS}`} />
        <span className="mt-1 block text-xs text-ink-faint">{t(`${A}.newHint`)}</span>
        {problem ? <p role="alert" className="mt-1 text-xs text-status-fault">{problem}</p> : null}
        {error ? <p role="alert" className="mt-1 text-xs text-status-fault">{error}</p> : null}
      </div>
      <div role="cell" className="border-t border-border bg-surface-sunken px-2 py-2">
        <ChoiceChips label={t(`${A}.newRole`)} value={role} options={choices.map((r) => ({ key: r, label: t(`aia.orgRoles.${r}`) }))} onChange={setRole} />
      </div>
      <div role="cell" className="border-t border-border bg-surface-sunken px-2 py-2 text-xs leading-5 text-ink-muted">{t(`${P}.members.note`)}</div>
      <div role="cell" className="flex items-start gap-1 border-t border-border bg-surface-sunken px-2 py-2">
        <Button small variant="primary" disabled={!email.trim() || state === "saving"} onClick={() => void add()}>{t(`${A}.add`)}</Button>
        <Button small variant="quiet" onClick={cancel}>{t(`${A}.cancel`)}</Button>
      </div>
    </div>
  );
}

const ROLE_BOXES = ["OWNER", "ADMIN", "MEMBER", "METODIK"] as const;

export function MembersCard({ members, vocab, canAdminister, yourRole, reload }: {
  members: Part<Member[]>; vocab: Vocabularies; canAdminister: boolean; yourRole: string; reload: () => void;
}) {
  const undo = useUndo();
  const me = useSession()?.email?.toLocaleLowerCase() ?? null;
  // Only an OWNER grants or removes OWNER (the API refuses it, owner_only); the last active OWNER
  // is not offered a demotion the API refuses (last_owner).
  const owner = yourRole === "OWNER";
  const roles = owner ? vocab.organization_roles : vocab.organization_roles.filter((r) => r !== "OWNER");
  const list = members.ok ? members.data : [];
  const activeOwners = list.filter((m) => m.is_active && m.organization_role === "OWNER").length;
  const ordered = [...list.filter((m) => m.is_active), ...list.filter((m) => !m.is_active)];
  const inactive = list.filter((m) => !m.is_active).length;
  return (
    <section id="set-members" aria-labelledby="set-members-title" className={CARD}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="set-members-title" className="text-base font-semibold">{t(`${A}.members`)}</h3>
        <div className="flex flex-wrap items-center gap-1.5">
          {members.ok ? <Count>{tv(`${A}.activeCount`, { n: list.length - inactive })}</Count> : null}
          {inactive ? <Count>{tv(`${A}.inactiveCount`, { n: inactive })}</Count> : null}
          {members.ok ? <Count>{tv(`${A}.metodikCount`, { n: list.filter((m) => m.methodologist).length })}</Count> : null}
          <Count tone={canAdminister ? "signal" : "neutral"}>{t(`${A}.${canAdminister ? "youManage" : "managedBy"}`)}</Count>
        </div>
      </div>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${A}.membersHelp`)}</p>
      {members.ok ? (
        <div role="table" aria-label={t(`${A}.members`)} className="mt-3 grid min-w-0 grid-cols-[minmax(12rem,1.4fr)_minmax(10rem,max-content)_max-content_minmax(7rem,1fr)_max-content] overflow-x-auto">
          <div role="row" className="contents">
            <div role="columnheader" className={GRID_HEAD}>{t(`${P}.col.member`)}</div>
            <div role="columnheader" className={GRID_HEAD}>{t(`${P}.members.role`)}</div>
            <div role="columnheader" className={GRID_HEAD}>{t(`${A}.metodik`)}</div>
            <div role="columnheader" className={GRID_HEAD}>{t(`${A}.state`)}</div>
            {/* relative: the sr-only label is absolute, and must stay inside the scrolling table. */}
            <div role="columnheader" className={`relative ${GRID_HEAD}`}><span className="sr-only">{t(`${A}.deactivate`)}</span></div>
          </div>
          {ordered.map((m) => {
            const isOwnerRow = m.organization_role === "OWNER";
            const locked = isOwnerRow && !(owner && activeOwners > 1);
            const lockedWhy = isOwnerRow && canAdminister ? t(`${P}.members.${owner ? "lastOwner" : "ownerOnly"}`) : null;
            return <MemberRow key={m.user_id} m={m} roles={roles} locked={locked} lockedWhy={locked ? lockedWhy : null} canAdminister={canAdminister} owner={owner}
              self={me !== null && m.email.toLocaleLowerCase() === me} reload={reload} offerUndo={(message, back) => undo.offer({ message, undo: back })} />;
          })}
          {canAdminister ? <AddMemberRow roles={roles} reload={reload} /> : null}
        </div>
      ) : <p role="alert" className="mt-3 text-sm text-status-fault">{members.message}</p>}
      {inactive ? <p className="mt-2 text-xs leading-5 text-ink-muted">{t(`${A}.deactivatedHelp`)}</p> : null}
      <div className="mt-5 border-t border-border pt-4">
        <h4 className="text-sm font-semibold">{t(`${A}.rolesTitle`)}</h4>
        <div className="mt-2.5 grid grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] gap-2.5">
          {ROLE_BOXES.map((r) => (
            <div key={r} data-role-box={r} className={`rounded-md border px-3.5 py-3 ${r === "METODIK" ? "border-signal-edge bg-signal-tint" : "border-border"}`}>
              <b className="text-sm font-medium">{t(`${A}.roles.${r}.name`)}</b>
              <p className="mt-1 text-xs leading-[18px] text-ink-muted">{t(`${A}.roles.${r}.can`)}</p>
            </div>
          ))}
        </div>
      </div>
      <UndoToast offer={undo.current} onDone={undo.clear} />
    </section>
  );
}

// ---------------------------------------------------------------- self-approval and clients

type Tri = "inherit" | "allow" | "forbid";
const tri = (v: boolean | null | undefined): Tri => (v === true ? "allow" : v === false ? "forbid" : "inherit");
const allowed = (v: Tri): boolean | null => (v === "allow" ? true : v === "forbid" ? false : null);

function OrgSelfApproval({ value, canAdminister, reload }: { value: boolean | null; canAdminister: boolean; reload: () => void }) {
  const { state, error, run } = useSave(reload);
  return (
    <div data-level="organization" className="mt-3.5 flex flex-wrap items-center gap-3">
      <b className="min-w-[7.5rem] text-sm font-medium">{t(`${P}.approvals.organization`)}</b>
      {/* Výchozí clears the organization's rule (allowed: null): the code's default, allowed, applies again. */}
      <ChoiceChips label={t(`${A}.orgSelf`)} disabled={!canAdminister} value={tri(value)}
        options={[{ key: "inherit" as const, label: t(`${A}.orgDefaultChip`) }, { key: "allow" as const, label: t(`${P}.approvals.allow`) }, { key: "forbid" as const, label: t(`${P}.approvals.forbid`) }]}
        onChange={(k) => void run(() => admin.setSelfApproval({ allowed: allowed(k) }))} />
      <SaveNote state={state} />
      <span className="text-xs leading-5 text-ink-muted">{value === null ? t(`${A}.orgDefault`) : t(`${A}.orgHelp`)}</span>
      {error ? <p role="alert" className="w-full text-xs text-status-fault">{error}</p> : null}
    </div>
  );
}

/** A study's own rule, set where it is listed: Dědit removes it, so the client's or organization's applies. */
function StudyRule({ studyId, name, value, canAdminister, reload }: { studyId: string; name: string; value: Tri; canAdminister: boolean; reload: () => void }) {
  const { state, error, run } = useSave(reload);
  return (
    <li data-study-rule={studyId} className="flex flex-wrap items-center gap-3">
      <span className="min-w-[10rem] text-sm">{name}</span>
      <ChoiceChips label={tv(`${A}.selfOfStudy`, { study: name })} disabled={!canAdminister} value={value}
        options={[{ key: "inherit" as const, label: t(`${A}.inherit`) }, { key: "allow" as const, label: t(`${P}.approvals.allow`) }, { key: "forbid" as const, label: t(`${P}.approvals.forbid`) }]}
        onChange={(k) => void run(() => admin.setSelfApproval({ allowed: allowed(k), study_id: studyId }))} />
      <SaveNote state={state} />
      {error ? <p role="alert" className="w-full text-xs text-status-fault">{error}</p> : null}
    </li>
  );
}

/** A new study rule: the study, then Povolit or Zakázat, which saves it. */
function AddStudyRule({ studies, reload }: { studies: { study_id: string; name: string }[]; reload: () => void }) {
  const [open, setOpen] = useState(false);
  const [studyId, setStudyId] = useState("");
  const { state, error, run } = useSave(reload);
  if (!studies.length) return null;
  if (!open) return <Button small className="mt-3" onClick={() => setOpen(true)}>{t(`${A}.addStudyRule`)}</Button>;
  return (
    <div data-add-study-rule className="mt-3 flex flex-wrap items-center gap-3">
      <select aria-label={t(`${A}.chooseStudy`)} value={studyId} onChange={(e) => setStudyId(e.target.value)}
        className={`min-h-9 min-w-[10rem] rounded-sm border border-border-strong bg-surface-raised px-2 text-sm ${FOCUS}`}>
        <option value="">{t(`${A}.chooseStudy`)}</option>
        {studies.map((s) => <option key={s.study_id} value={s.study_id}>{s.name}</option>)}
      </select>
      <ChoiceChips label={t(`${A}.newStudyRule`)} disabled={!studyId} value={null}
        options={[{ key: "allow" as const, label: t(`${P}.approvals.allow`) }, { key: "forbid" as const, label: t(`${P}.approvals.forbid`) }]}
        onChange={(k) => void run(() => admin.setSelfApproval({ allowed: allowed(k), study_id: studyId })).then((ok) => { if (ok) { setStudyId(""); setOpen(false); } })} />
      <Button small variant="quiet" onClick={() => { setOpen(false); setStudyId(""); }}>{t(`${A}.cancel`)}</Button>
      <SaveNote state={state} />
      {error ? <p role="alert" className="w-full text-xs text-status-fault">{error}</p> : null}
    </div>
  );
}

export function SelfApprovalCard({ levels, studies, canAdminister, reload }: {
  levels: Part<SelfApprovalLevels> | null; studies: { study_id: string; name: string }[]; canAdminister: boolean; reload: () => void;
}) {
  const studyName = new Map(studies.map((s) => [s.study_id, s.name]));
  return (
    <section id="set-self-approval" aria-labelledby="set-self-approval-title" className={CARD}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="set-self-approval-title" className="text-base font-semibold">{t(`${P}.approvals.title`)}</h3>
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-ink-muted" aria-label={t(`${A}.precedence`)}>
          <span>{t(`${A}.wins`)}</span><Count>{t(`${A}.levelStudy`)}</Count><span aria-hidden="true">→</span><Count>{t(`${A}.levelClient`)}</Count><span aria-hidden="true">→</span><Count>{t(`${A}.levelOrg`)}</Count>
        </div>
      </div>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${A}.selfHelp`)}</p>
      {levels === null ? <p className="mt-3 text-sm text-ink-muted">{t(`${P}.approvals.adminOnly`)}</p>
        : !levels.ok ? <p role="alert" className="mt-3 text-sm text-status-fault">{levels.message}</p>
        : <>
          <OrgSelfApproval value={levels.data.organization} canAdminister={canAdminister} reload={reload} />
          <div data-study-overrides className="mt-4 border-t border-border pt-3">
            <span className="text-sm font-medium">{t(`${A}.studyOverrides`)}</span>
            {levels.data.studies.length ? (
              <ul className="mt-1.5 flex flex-col gap-2">
                {levels.data.studies.map((s) => <StudyRule key={s.study_id} studyId={s.study_id} name={studyName.get(s.study_id) ?? s.study_id} value={tri(s.allowed)} canAdminister={canAdminister} reload={reload} />)}
              </ul>
            ) : <p className="mt-1 text-xs text-ink-muted">{t(`${A}.noStudyRules`)}</p>}
            {canAdminister ? <AddStudyRule studies={studies.filter((s) => !levels.data.studies.some((r) => r.study_id === s.study_id))} reload={reload} /> : null}
          </div>
        </>}
    </section>
  );
}

/** Every client's rules from one read: a 404 is "not in AIA yet", a client not answered for unknown. */
type RulesRead = { state: "loading" } | { state: "not_yet" } | { state: "ready"; byClient: Map<string, ClientRules> } | { state: "refused"; message: string };

function useClientRules(): RulesRead {
  const [read, setRead] = useState<RulesRead>({ state: "loading" });
  useEffect(() => {
    let live = true;
    clientRules.list().then(
      (rows) => { if (live) setRead(Array.isArray(rows) ? { state: "ready", byClient: new Map(rows.map((r) => [r.client_id, r])) } : { state: "refused", message: t(`${A}.rulesMalformed`) }); },
      (e: unknown) => { if (live) setRead(e instanceof ApiError && e.status === 404 && e.code === "http_404" ? { state: "not_yet" } : { state: "refused", message: describeError(e) }); },
    );
    return () => { live = false; };
  }, []);
  return read;
}

function RulesCell({ id, read }: { id: string; read: RulesRead }) {
  if (read.state === "not_yet") return <NotYetChip />;
  if (read.state === "loading") return <span data-client-rules="loading" className="text-xs text-ink-faint">…</span>;
  // A refused read is said once, above the table; here the row is unknown.
  const r = read.state === "ready" ? read.byClient.get(id) : undefined;
  if (!r) return <span data-client-rules="unknown" className="text-sm text-ink-muted">{t(`${A}.rulesUnknown`)}</span>;
  return (
    <span data-client-rules="read" className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <span className="inline-flex min-h-[22px] items-center rounded-pill border border-border px-2 font-mono text-xs">{t(`${A}.posture.${r.effective_posture}`)}</span>
      {r.data_posture === null ? <span className="text-xs text-ink-muted">{t(`${A}.postureUnset`)}</span> : null}
      <span>{r.wallet_ceiling_usd === null ? t(`${A}.noCeiling`) : tv(`${A}.ceilingOf`, { amount: usd(r.wallet_ceiling_usd) })}</span>
    </span>
  );
}

function ClientRow({ c, statuses, self, rules, canAdminister, reload }: {
  c: AdminClient; statuses: readonly string[]; self: Tri | null; rules: RulesRead; canAdminister: boolean; reload: () => void;
}) {
  const status = useSave(reload);
  const approval = useSave(reload);
  return (
    <div role="row" data-client={c.client_id} className="contents">
      <div role="cell" className="border-t border-border px-2 py-2 text-sm">
        {c.name}
        <span className="block text-xs text-ink-faint">{tv(`${A}.studyCount`, { n: c.study_count })}</span>
      </div>
      <div role="cell" className="border-t border-border px-2 py-2">
        {canAdminister ? (
          <ChoiceChips label={tv(`${A}.statusOf`, { client: c.name })} value={c.status} options={statuses.map((s) => ({ key: s, label: t(`${P}.clientStatus.${s}`) }))}
            onChange={(s) => void status.run(() => admin.setClientStatus(c.client_id, s))} />
        ) : <span className="text-sm">{t(`${P}.clientStatus.${c.status}`)}</span>}
        <SaveNote state={status.state} />
        {status.error ? <p role="alert" className="mt-1 text-xs text-status-fault">{status.error}</p> : null}
      </div>
      <div role="cell" className="border-t border-border px-2 py-2">
        {self === null ? <span className="text-xs text-ink-faint">{t(`${A}.adminOnlyShort`)}</span> : (
          <ChoiceChips label={tv(`${A}.selfOf`, { client: c.name })} disabled={!canAdminister} value={self}
            options={[{ key: "inherit" as const, label: t(`${A}.inherit`) }, { key: "allow" as const, label: t(`${P}.approvals.allow`) }, { key: "forbid" as const, label: t(`${P}.approvals.forbid`) }]}
            onChange={(k) => void approval.run(() => admin.setSelfApproval({ allowed: allowed(k), client_id: c.client_id }))} />
        )}
        <SaveNote state={approval.state} />
        {approval.error ? <p role="alert" className="mt-1 text-xs text-status-fault">{approval.error}</p> : null}
      </div>
      <div role="cell" className="border-t border-border px-2 py-2">
        <RulesCell id={c.client_id} read={rules} />
        <Link href={appRoutes.area(c.client_id, "profile")} className={`mt-1 block text-xs text-signal hover:underline ${FOCUS}`}>{t(`${A}.changeInProfile`)}</Link>
      </div>
    </div>
  );
}

export function ClientsCard({ clients, levels, vocab, canAdminister, reload }: {
  clients: Part<AdminClient[]>; levels: Part<SelfApprovalLevels> | null; vocab: Vocabularies; canAdminister: boolean; reload: () => void;
}) {
  const byClient = new Map(levels?.ok ? levels.data.clients.map((c) => [c.client_id, c.allowed]) : []);
  const rules = useClientRules();
  return (
    <section id="set-clients" aria-labelledby="set-clients-title" className={CARD}>
      <CardHead title={t(`${P}.clients.title`)}>{clients.ok ? <Count>{tv(`${A}.clientCount`, { n: clients.data.length })}</Count> : null}</CardHead>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${A}.clientsHelp`)}</p>
      {rules.state === "refused" ? <p role="alert" className="mt-2 text-sm text-status-fault">{rules.message}</p> : null}
      {!clients.ok ? <p role="alert" className="mt-3 text-sm text-status-fault">{clients.message}</p>
        : !clients.data.length ? <p className="mt-3 text-sm text-ink-muted">{t(`${P}.clients.none`)}</p>
        : (
          <div role="table" aria-label={t(`${P}.clients.title`)} className="mt-3 grid min-w-0 grid-cols-[minmax(10rem,1fr)_max-content_max-content_minmax(10rem,1fr)] overflow-x-auto">
            <div role="row" className="contents">
              <div role="columnheader" className={GRID_HEAD}>{t(`${P}.clients.client`)}</div>
              <div role="columnheader" className={GRID_HEAD}>{t(`${P}.clients.status`)}</div>
              <div role="columnheader" className={GRID_HEAD}>{t(`${P}.approvals.title`)}</div>
              <div role="columnheader" className={GRID_HEAD}>{t(`${A}.postureCeiling`)}</div>
            </div>
            {clients.data.map((c) => (
              <ClientRow key={c.client_id} c={c} statuses={vocab.client_statuses} rules={rules} reload={reload} canAdminister={canAdminister}
                self={levels === null || !levels.ok ? null : tri(byClient.get(c.client_id))} />
            ))}
          </div>
        )}
    </section>
  );
}
