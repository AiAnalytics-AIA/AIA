"use client";

// Audit as the redesign draws it (settings-redesign chunk 8, Audit board): categories with their
// counts in the period chosen, a period, a search and the person and event filters, then the
// records newest first as prototype v99's table (F10): Kdy, Kdo, Událost (its category's dot, its
// name, what it concerns) and Důvod / změna -- the change in words (lib/audit-change.ts) with the
// person's reason under it. Every action code reads in Czech (lib/audit.ts); a code it does not
// know is spelled out under Ostatní, never dropped. Read only.

import { useState } from "react";

import { t } from "@/i18n/t";
import type { AdminClient, AuditEntry, Member } from "@/lib/api";
import {
  type AuditCategory, type AuditPeriod, CATEGORIES, CATEGORY_NAMES, PERIODS, PERIOD_NAMES, actionName, categoryOf, inPeriod,
} from "@/lib/audit";
import { changeOf, concernsOf } from "@/lib/audit-change";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { FOCUS } from "../../ui/parts";
import { Select, TextInput } from "../../rehome/ui";
import { Empty } from "../states";
import { Technical } from "./technical";
import type { StudyRow } from "./StudiesPanel";

const P = "aia.settings.panel";
type Part<T> = { ok: true; data: T } | { ok: false; message: string };

// Wayfinding tints and neutral ink only: a category is not a status, so never coral (needs you),
// fault red, green (in force), the signal or a client's accent (review of #849).
const DOT: Record<AuditCategory, string> = {
  method: "bg-hue-violet", access: "bg-hue-blue", money: "bg-hue-orange", clients: "bg-hue-teal", dr: "bg-hue-slate",
  prompts: "bg-ink-faint", lead: "bg-ink-muted", data: "bg-ink", other: "bg-border-strong",
};
/** The page asks for this many records (admin.audit); a full page means older ones were not read. */
export const AUDIT_PAGE = 500;
const WHEN = new Intl.DateTimeFormat("cs-CZ", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Prague" });
const HEAD = "px-2 py-1.5 text-left text-xs font-normal text-ink-faint";
const CELL = "border-t border-border px-2 py-2 align-top text-sm";

export function AuditPanel({ audit, members, clients, studies }: {
  audit: Part<AuditEntry[]> | null; members: Part<Member[]>; clients: Part<AdminClient[]>; studies: Part<StudyRow[]>;
}) {
  const [query, setQuery] = useState("");
  const [actor, setActor] = useState("");
  const [event, setEvent] = useState("");
  const [category, setCategory] = useState<AuditCategory | "all">("all");
  const [period, setPeriod] = useState<AuditPeriod>("month");
  if (audit === null) return <p className="text-sm text-ink-muted">{t(`${P}.audit.adminOnly`)}</p>;
  if (!audit.ok) return <p role="alert" className="text-sm text-status-fault">{audit.message}</p>;
  if (!audit.data.length) return <Empty>{t(`${P}.audit.none`)}</Empty>;
  const who = new Map(members.ok ? members.data.map((m) => [m.user_id, m.display_name || m.email]) : []);
  const emailOf = new Map(members.ok ? members.data.map((m) => [m.user_id, m.email]) : []);
  const person = (id: string | null) => (id ? (who.get(id) ?? id) : t(`${P}.audit.system`));
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  const studyName = new Map(studies.ok ? studies.data.map(({ study }) => [study.study_id, study.name]) : []);
  // What a record concerns: the person, study and client it names, or, for an organization's
  // methodology, prompt or Deep Research rule, that thing by its page's name; "" for none.
  const subject = (e: AuditEntry) => [
    concernsOf(e),
    e.subject_user_id ? person(e.subject_user_id) : null,
    e.study_id ? (studyName.get(e.study_id) ?? e.study_id) : null,
    e.client_id ? (clientName.get(e.client_id) ?? e.client_id) : null,
  ].filter(Boolean).join(" · ");
  const now = new Date();
  const inTime = audit.data.filter((e) => inPeriod(e.created_at, period, now));
  // A full page holds the newest records only: a period reaching past the oldest one read may hold
  // more than its count says, so the counts read "≥ n" there (review of #849).
  const full = audit.data.length >= AUDIT_PAGE;
  const oldest = audit.data.map((e) => e.created_at).filter((x): x is string => !!x).sort()[0];
  const truncated = full && (period === "all" || (oldest !== undefined && inPeriod(oldest, period, now)));
  const countWords = (n: number) => (truncated ? `≥ ${n}` : String(n));
  const counts = new Map<AuditCategory, number>();
  for (const e of inTime) counts.set(categoryOf(e.action), (counts.get(categoryOf(e.action)) ?? 0) + 1);
  const actors = [...new Set(audit.data.map((e) => e.actor_id).filter((id): id is string => !!id))].sort((a, b) => person(a).localeCompare(person(b), "cs"));
  const events = [...new Set(audit.data.map((e) => e.action))].sort((a, b) => actionName(a).localeCompare(actionName(b), "cs"));
  const q = query.trim().toLocaleLowerCase("cs");
  // The search reads the change as the row shows it, in words, beside the reason as stored.
  const changeText = (e: AuditEntry) => { const c = changeOf(e); return `${c.change ?? ""} ${c.why ?? ""}`; };
  const visible = inTime.filter((e) => (category === "all" || categoryOf(e.action) === category) && (!actor || e.actor_id === actor) && (!event || e.action === event)
    && `${actionName(e.action)} ${CATEGORY_NAMES[categoryOf(e.action)]} ${person(e.actor_id)} ${subject(e)} ${e.reason ?? ""} ${changeText(e)} ${emailOf.get(e.actor_id ?? "") ?? ""} ${emailOf.get(e.subject_user_id ?? "") ?? ""}`.toLocaleLowerCase("cs").includes(q));
  const shownCategories = CATEGORIES.filter((c) => c !== "other" || counts.get("other"));
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div data-audit-categories className="flex flex-col gap-2">
        <span className="text-xs text-ink-faint">{t(`${P}.audit.categories`)}</span>
        <div className="flex flex-wrap gap-1.5">
          {(["all", ...shownCategories] as const).map((c) => {
            const on = c === category;
            const n = c === "all" ? inTime.length : (counts.get(c) ?? 0);
            return (
              <button key={c} type="button" data-audit-category={c} aria-pressed={on} onClick={() => setCategory(c)}
                className={`inline-flex min-h-8 items-center gap-1.5 rounded-pill border px-2.5 text-xs ${on ? "border-signal bg-signal-wash font-medium text-ink" : "border-border text-ink-muted hover:bg-surface-sunken"} ${FOCUS}`}>
                {c !== "all" ? <i aria-hidden="true" className={`size-2 rounded-full ${DOT[c]}`} /> : null}
                {c === "all" ? t(`${P}.audit.all`) : CATEGORY_NAMES[c]}
                <span className="font-mono tabular-nums text-ink-faint">{countWords(n)}</span>
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <ChoiceChips look="segmented" small label={t(`${P}.audit.period`)} value={period} options={PERIODS.map((p) => ({ key: p, label: PERIOD_NAMES[p] }))} onChange={setPeriod} />
      </div>
      <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(8rem,12rem)_minmax(8rem,14rem)]">
        <TextInput type="search" aria-label={t(`${P}.auditSearch`)} placeholder={t(`${P}.auditSearchPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)} />
        <Select aria-label={t(`${P}.audit.person`)} value={actor} onChange={(e) => setActor(e.target.value)}><option value="">{t(`${P}.audit.allPeople`)}</option>{actors.map((id) => <option key={id} value={id}>{person(id)}</option>)}</Select>
        <Select aria-label={t(`${P}.audit.eventType`)} value={event} onChange={(e) => setEvent(e.target.value)}><option value="">{t(`${P}.audit.allEvents`)}</option>{events.map((a) => <option key={a} value={a}>{actionName(a)}</option>)}</Select>
      </div>
      {full ? <p data-audit-truncated className="text-xs text-ink-muted">{t(`${P}.audit.truncated`)}</p> : null}
      <p className="text-xs text-ink-muted"><span role="status">Zobrazeno {visible.length} z {audit.data.length} záznamů</span> · {t(`${P}.audit.newestFirst`)}</p>
      {!visible.length ? <p role="status" className="text-sm text-ink-muted">{t(`${P}.noSearchResults`)}</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] border-collapse">
            <thead><tr>
              <th scope="col" className={`${HEAD} w-[9rem]`}>{t(`${P}.audit.when`)}</th><th scope="col" className={`${HEAD} w-[10rem]`}>{t(`${P}.audit.actor`)}</th>
              <th scope="col" className={HEAD}>{t(`${P}.audit.event`)}</th><th scope="col" className={HEAD}>{t(`${P}.audit.reason`)}</th>
            </tr></thead>
            <tbody>
              {visible.map((e) => {
                const c = categoryOf(e.action);
                const moved = changeOf(e);
                return (
                  <tr key={e.event_id} data-audit-entry={e.event_id} data-category={c}>
                    <td className={`${CELL} whitespace-nowrap text-ink-muted`}><time dateTime={e.created_at ?? undefined}>{e.created_at ? WHEN.format(new Date(e.created_at)) : "—"}</time></td>
                    <td className={`${CELL} break-words`}>{person(e.actor_id)}</td>
                    <td className={CELL}>
                      {/* The category's dot and its name for a reader; the event, then what it concerns. */}
                      <span className="flex items-start gap-2">
                        <i aria-hidden="true" title={CATEGORY_NAMES[c]} className={`mt-1.5 size-2 shrink-0 rounded-full ${DOT[c]}`} />
                        <span className="min-w-0 break-words">
                          <span className="sr-only">{CATEGORY_NAMES[c]}: </span>
                          <strong className="font-medium">{actionName(e.action)}</strong>
                          {subject(e) ? <span data-audit-concerns className="text-ink-muted"> · {subject(e)}</span> : null}
                          <Technical><span data-technical className="block break-all font-mono text-[11px] text-ink-faint">{e.action}{e.role ? ` · ${e.role}` : ""}</span></Technical>
                        </span>
                      </span>
                    </td>
                    <td className={`${CELL} break-words`}>
                      {moved.change ? <span data-audit-change className="block">{moved.change}</span> : null}
                      {moved.why ? <span data-audit-why className={`block ${moved.change ? "text-xs text-ink-muted" : ""}`}>{moved.why}</span> : null}
                      {!moved.change && !moved.why ? <span className="text-ink-faint">—</span> : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
