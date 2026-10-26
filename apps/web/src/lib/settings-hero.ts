// The figures each Settings page's hero carries (settings-redesign F18, prototype v99's hero-meta),
// read from what the page already reads. Pure. A figure no read established is null, which the hero
// draws as "neznámé", never 0 (prototype-build PBA4); a count a truncated read cannot make whole is
// null too, never the part that was read.

import type { AdminClient, AuditEntry, Member, SelfApprovalLevels } from "./api";
import { inPeriod } from "./audit";

/** One figure, shaped as the hero takes it (components/aia/Hero.tsx HeroFigure). */
export type Figure = { label: string; value: string | null; mono?: boolean; you?: boolean };

/** A read the page made: its data, or the reason there is none. */
type Read<T> = { ok: true; data: T } | { ok: false } | null;

const data = <T,>(r: Read<T>): T | null => (r && r.ok ? r.data : null);
const n = (v: number) => new Intl.NumberFormat("cs-CZ").format(v);

/** Whether a member is active here: not deactivated in this organization, and active as a user. */
const active = (m: Member) => m.is_active && !m.deactivated_at;

export type AccessWords = {
  active: string; deactivated: string; methodologist: string; clients: string; selfApproval: string;
  allowed: string; forbidden: string; byDefault: string;
};

/**
 * Přístup a schvalování (Access.dc.html): active members, deactivated (only when there are any),
 * Metodik, clients, and the organization's self-approval rule. `levels` is null for a person who may
 * not administer: the rule is then not read, so unknown.
 */
export function accessFigures(members: Read<Member[]>, clients: Read<AdminClient[]>, levels: Read<SelfApprovalLevels>, w: AccessWords): Figure[] {
  const list = data(members);
  const figures: Figure[] = [{ label: w.active, value: list ? n(list.filter(active).length) : null }];
  // Deaktivovaní is drawn only when there are any (as the prototype does): with the members unread
  // there is no count to say, and an unknown figure for a row that is usually absent would be noise;
  // Aktivní členové already says the read failed.
  const deactivated = list ? list.filter((m) => !active(m)).length : null;
  if (deactivated) figures.push({ label: w.deactivated, value: n(deactivated) });
  // A member record without the Metodik mark (an older API) leaves the count unknown, never 0.
  const marked = list && list.every((m) => typeof m.methodologist === "boolean") ? list : null;
  figures.push({ label: w.methodologist, value: marked ? n(marked.filter((m) => active(m) && m.methodologist).length) : null });
  const known = data(clients);
  figures.push({ label: w.clients, value: known ? n(known.length) : null });
  const rule = data(levels);
  figures.push({
    label: w.selfApproval,
    value: !rule ? null : rule.organization === true ? w.allowed : rule.organization === false ? w.forbidden : w.byDefault,
  });
  return figures;
}

export type SystemWords = { ready: string; environment: string; build: string };

/**
 * Stav systému (System.dc.html): how many of the last smoke run's checks are ready, the environment
 * and the web's build, from Připravenost's and Prostředí a verze's reads. A smoke run not read, or
 * none kept, is unknown; so is a row Prostředí a verze could not read.
 */
export function systemFigures(ready: { ready: number; total: number } | null, rows: readonly { key: string; value: string | null }[] | null, w: SystemWords): Figure[] {
  const row = (key: string) => rows?.find((r) => r.key === key)?.value ?? null;
  return [
    { label: w.ready, value: ready ? `${n(ready.ready)} / ${n(ready.total)}` : null },
    { label: w.environment, value: row("environment") },
    { label: w.build, value: row("build"), mono: true },
  ];
}

export type AuditWords = { inPeriod: string; today: string; people: string; last: string };

/**
 * Audit (Audit.dc.html), over the last seven days: the events, today's, how many people changed
 * something, and when the newest change was. The page reads the newest `pageSize` events: when the
 * page is full and its oldest event still falls in the window, the window holds more than was read, so
 * its counts are unknown; the newest change is known whatever the page's size.
 */
export function auditFigures(audit: Read<AuditEntry[]>, pageSize: number, now: number, words: AuditWords, when: (iso: string) => string): Figure[] {
  const list = data(audit);
  if (!list) return [{ label: words.inPeriod, value: null }, { label: words.today, value: null }, { label: words.people, value: null }, { label: words.last, value: null }];
  const at = (e: AuditEntry) => (e.created_at ? Date.parse(e.created_at) : Number.NaN);
  const dated = list.filter((e) => Number.isFinite(at(e)));
  // The windows are the Audit table's own (lib/audit.ts inPeriod): "today" is Prague's day, whatever
  // the browser's time zone, so the hero and the rows beneath it count the same events.
  const clock = new Date(now);
  const within = (period: "today" | "week") => dated.filter((e) => inPeriod(e.created_at, period, clock));
  const oldest = dated.length ? dated.reduce((a, b) => (at(b) < at(a) ? b : a)) : null;
  // A full page whose oldest row is still inside a window has not read the whole window. A row
  // without a date could fall anywhere, so it leaves the counts unknown too.
  const whole = (period: "today" | "week") =>
    dated.length === list.length && !(list.length >= pageSize && oldest !== null && inPeriod(oldest.created_at, period, clock));
  const inWeek = within("week");
  const newest = dated.length ? dated.reduce((a, b) => (at(b) > at(a) ? b : a)) : null;
  return [
    { label: words.inPeriod, value: whole("week") ? n(inWeek.length) : null },
    { label: words.today, value: whole("today") ? n(within("today").length) : null },
    { label: words.people, value: whole("week") ? n(new Set(inWeek.map((e) => e.actor_id).filter((a) => a !== null)).size) : null },
    // No event at all is no change to name: unknown, never "now".
    { label: words.last, value: newest?.created_at ? when(newest.created_at) : null },
  ];
}
