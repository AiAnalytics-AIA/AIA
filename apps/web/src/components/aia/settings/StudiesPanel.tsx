"use client";

// Studie a rozpočty's study table as prototype v51 draws it (settings-redesign F7): one row per
// study -- its name and client, its status read, its spend against its budget with the share
// spent, the budget and the confirmation threshold set by a stepper in the row (I2: Shift x10, a
// value out of bounds refused at the field, never clamped), and the wallet pointed to where it is
// set. A study's status is not chosen here (the product owner, F7). A study above 90 % of its
// budget reads grey with ⚠: it needs a person, and the fault colour is not a state of the money
// (the product owner, 2026-10-22). Costs a caller may not see stay "náklady nevidíte".

import Link from "next/link";
import { useState } from "react";

import { money } from "@/i18n/cs";
import { t, tv } from "@/i18n/t";
import { type AdminClient, type Study, admin, research } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { formatNumber } from "@/lib/number-input";
import { nearLimit, usd } from "@/lib/researcher-spend";
import { FOCUS, SaveNote } from "../../ui/parts";
import { Stepper } from "../../ui/Stepper";
import { Button } from "../../rehome/ui";
import type { SaveState } from "@/lib/inline-edit";
import { clientAccent } from "../AppShell";
import { describeMemberError } from "./errors";

const P = "aia.settings.panel";
const S = `${P}.studiesTab`;
/** The highest budget or threshold the API takes (routers/scope.py, le=1_000_000). */
const MAX_USD = 1_000_000;
/** Below this a confirmation threshold asks about nearly everything; the design's floor. */
const MIN_THRESHOLD_USD = 10;

type Part<T> = { ok: true; data: T } | { ok: false; message: string };
export type StudyRow = { study: Study; detail: Part<Study> };

/** A study's status in words, with the prototype's glyph beside it (read only). */
const STATUS_GLYPH: Record<string, string> = { DRAFT: "✎", ACTIVE: "▶", IN_REVIEW: "◐", DELIVERED: "✓", ARCHIVED: "▪", CANCELLED: "✕" };
const TD = "border-t border-border px-2 py-2.5 align-top";

/** A save's refusal, said at the field as the API gave it (I9); the Stepper says Neuloženo beside. */
function useRefusal() {
  const [error, setError] = useState<string | null>(null);
  const guard = <T,>(op: () => Promise<T>) => {
    setError(null);
    return op().catch((e: unknown) => { setError(describeMemberError(e)); throw e; });
  };
  const shown = error ? <p role="alert" className="mt-1 max-w-56 text-xs text-status-fault">{error}</p> : null;
  return { guard, shown };
}

/**
 * The value a save answered with, held until the re-read brings the row up to it: without it the
 * field would show the old value between the PUT's answer and the reload's (seen in the settings
 * journey). Held only while the row still reads the value it was saved over.
 */
function useAnswered(current: number | null) {
  const [held, setHeld] = useState<{ over: number | null; value: number | null } | null>(null);
  const value = held && held.over === current ? held.value : current;
  return { value, hold: (next: number | null) => setHeld({ over: current, value: next }) };
}

function Spend({ costs }: { costs: Study }) {
  const budget = costs.budget_usd ?? 0;
  const spent = costs.spent_usd ?? 0;
  const pct = budget > 0 ? Math.min(100, Math.round((spent / budget) * 100)) : spent > 0 ? 100 : 0;
  const near = nearLimit(costs);
  // The prototype's line is "53 %" (and "· ⚠" near the limit); the rest of the sentence is read
  // to a screen reader, not drawn.
  return <>
    <span className="whitespace-nowrap font-mono text-sm tabular-nums">{usd(spent)}</span>
    <span aria-hidden="true" className="mt-1 block h-1.5 w-24 overflow-hidden rounded-pill bg-surface-sunken">
      <i className="block h-full bg-ink" style={{ width: `${pct}%` }} />
    </span>
    <span data-spend-line className="mt-0.5 block whitespace-nowrap text-xs text-ink-muted">
      {pct} %<span className="sr-only"> {t(`${S}.ofBudgetRest`)} · {tv(`${S}.remaining`, { usd: usd(costs.remaining_usd ?? Math.max(0, budget - spent)) })}</span>
      {near ? <><span aria-hidden="true"> · ⚠</span><span className="sr-only"> · {t(`${S}.nearLimit`)}</span></> : null}
    </span>
  </>;
}

function Budget({ costs, reload }: { costs: Study; reload: () => void }) {
  const refusal = useRefusal();
  const answered = useAnswered(costs.budget_usd);
  // Never below what the study has spent, rounded up to the cent: the field refuses it before
  // anything is sent (the API itself refuses only a negative budget). Open holds are not in it.
  const min = Math.ceil((costs.spent_usd ?? 0) * 100) / 100;
  return <>
    <Stepper label={tv(`${S}.budgetOf`, { study: costs.name })} value={answered.value} min={min} max={MAX_USD} step={10} decimals={2} unit="USD" unitShown={false} showBounds={false}
      onCommit={(v) => refusal.guard(() => admin.setStudyBudget(costs.study_id, v)).then(() => { answered.hold(v); reload(); })} note={tv(`${S}.budgetFloor`, { min: formatNumber(min, 2) })} />
    {refusal.shown}
  </>;
}

function Threshold({ costs, reload }: { costs: Study; reload: () => void }) {
  const answered = useAnswered(costs.spend_confirm_usd ?? null);
  const limit = answered.value;
  const budget = costs.budget_usd ?? MAX_USD;
  const [cleared, setCleared] = useState<SaveState>("idle");
  const refusal = useRefusal();
  const max = Math.max(MIN_THRESHOLD_USD, budget);
  return <>
    <Stepper label={tv(`${S}.thresholdOf`, { study: costs.name })} value={limit} min={MIN_THRESHOLD_USD} max={max} step={10} decimals={2} unit="USD" unitShown={false} showBounds={false}
      note={limit === null ? t(`${S}.never`) : null}
      onCommit={(v) => refusal.guard(() => research.setSpendConfirm(costs.study_id, v)).then(() => { answered.hold(v); reload(); })} />
    {refusal.shown}
    <span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
      {limit !== null ? <Button small variant="quiet" data-dense onClick={() => { setCleared("saving"); refusal.guard(() => research.setSpendConfirm(costs.study_id, null)).then(() => { answered.hold(null); setCleared("saved"); reload(); }, () => setCleared("failed")); }}>{t(`${S}.setNever`)}</Button> : null}
      <SaveNote state={cleared} />
    </span>
  </>;
}

export function StudiesTable({ studies, clients, reload }: {
  studies: Part<StudyRow[]>; clients: Part<AdminClient[]>; reload: () => void;
}) {
  const [query, setQuery] = useState("");
  const [named, setNamed] = useState(false);
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  const q = query.trim().toLocaleLowerCase("cs");
  const count = studies.ok ? studies.data.length : 0;
  // What each of the money columns is: the header's ⓘ on hover, and the four D-01 names, each with
  // where it is set, in the disclosure under the table, which a keyboard and a touch reach too.
  const info = (key: "studyBudget" | "confirmThreshold" | "wallet") => <span aria-hidden="true" title={t(`${S}.money.${key}`)} className="ml-1 cursor-help text-ink-faint">ⓘ</span>;
  return (
    <section id="set-studies-table" aria-labelledby="set-studies-table-title" className="rounded-md border border-border bg-surface-raised px-4 py-4 sm:px-6 sm:py-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="set-studies-table-title" className="flex items-center gap-2 text-base font-semibold">
          {t(`${P}.studies.title`)}
          {studies.ok ? <span className="inline-flex min-h-[22px] items-center rounded-pill border border-border px-2 text-xs font-normal text-ink-muted" aria-label={tv(`${S}.count`, { n: count })}>{count}</span> : null}
        </h3>
        <input type="search" aria-label={t(`${P}.studySearch`)} placeholder={`⌕ ${t(`${P}.studySearch`)}`} value={query} onChange={(e) => setQuery(e.target.value)}
          className={`min-h-9 w-full rounded-sm border border-border-strong bg-surface-raised px-2 text-sm sm:w-72 ${FOCUS}`} />
      </div>
      {!studies.ok ? <p role="alert" className="mt-3 text-sm text-status-fault">{studies.message}</p>
        : !studies.data.length ? <p className="mt-3 text-sm text-ink-muted">{t(`${P}.studies.none`)}</p>
        : (
          // The table scrolls in its own box where the page is narrower than its six columns; the box
          // is positioned so nothing absolute inside it (a screen-reader-only caption) widens the page.
          <div className="relative mt-3 min-w-0 overflow-x-auto">
            <table className="w-full min-w-[54rem] border-collapse text-sm">
              <caption className="sr-only">{t(`${P}.studies.title`)}: {money.studyBudget}: {t(`${S}.money.studyBudget`)} {money.confirmThreshold}: {t(`${S}.money.confirmThreshold`)} {money.wallet}: {t(`${S}.money.wallet`)}</caption>
              <thead><tr className="text-left text-xs text-ink-faint">
                <th scope="col" className="px-2 py-1.5 font-normal">{t(`${P}.studies.study`)}</th>
                <th scope="col" className="px-2 py-1.5 font-normal">{t(`${P}.studies.status`)}</th>
                <th scope="col" className="px-2 py-1.5 font-normal">{t(`${P}.studies.spent`)}</th>
                <th scope="col" className="px-2 py-1.5 font-normal">{money.studyBudget} (USD){info("studyBudget")}</th>
                <th scope="col" className="px-2 py-1.5 font-normal">{money.confirmThreshold} (USD){info("confirmThreshold")}</th>
                <th scope="col" className="px-2 py-1.5 font-normal">{money.wallet}{info("wallet")}</th>
              </tr></thead>
              <tbody>
                {studies.data.map(({ study, detail }) => {
                  // Both known, or neither drawn: an unknown spend never reads as 0 (A6).
                  const costs = detail.ok && detail.data.budget_usd !== null && detail.data.spent_usd !== null ? detail.data : null;
                  const client = clientName.get(study.client_id) ?? study.client_id;
                  const shown = `${study.name} ${client}`.toLocaleLowerCase("cs").includes(q);
                  const near = costs ? nearLimit(costs) : false;
                  // Filtered out, a row is hidden, never unmounted: a typed value survives the search.
                  return (
                    <tr key={study.study_id} data-study={study.study_id} data-near={near ? "true" : undefined} hidden={!shown} className={near ? "bg-surface-sunken" : undefined}>
                      <th scope="row" className={`${TD} text-left font-normal`}>
                        <span className="text-sm font-medium">{study.name}</span>
                        <span className="mt-0.5 flex items-center gap-1.5 text-xs text-ink-muted"><span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${clientAccent(study.client_id)}`} />{client}</span>
                      </th>
                      <td className={`${TD} whitespace-nowrap`}><span aria-hidden="true" className="inline-block w-[18px] text-ink-muted">{STATUS_GLYPH[study.status] ?? ""}</span>{t(`aia.status.${study.status}`)}</td>
                      {costs ? <>
                        <td className={TD}><Spend costs={costs} /></td>
                        <td className={TD}><Budget costs={costs} reload={reload} /></td>
                        <td className={TD}><Threshold costs={costs} reload={reload} /></td>
                      </> : (
                        <td colSpan={3} className={TD}>
                          <span title={detail.ok ? "" : detail.message} className="rounded-sm border border-dashed border-border-strong px-1.5 text-xs">{t(`${P}.studies.costsHidden`)}</span>
                        </td>
                      )}
                      <td className={TD}>
                        <Link href={appRoutes.area(study.client_id, "profile")} title={t(`${S}.profileRules`)} aria-label={tv(`${S}.rulesOf`, { client })}
                          className={`inline-flex min-h-11 items-center whitespace-nowrap text-sm text-signal hover:underline sm:min-h-0 ${FOCUS}`}>{t(`${S}.rules`)}<span aria-hidden="true"> ↗</span></Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      <p className="mt-2 text-xs leading-5 text-ink-muted">{t(`${P}.studies.permissionNote`)}</p>
      {/* A button, not a <details>: a settings tab carries no disclosure element (F2), and this one
          opens by keyboard and touch alike. */}
      <button type="button" aria-expanded={named} aria-controls="set-studies-money" onClick={() => setNamed((v) => !v)}
        className={`mt-1 inline-flex min-h-11 items-center gap-1 text-xs text-signal hover:underline sm:min-h-0 ${FOCUS}`}>
        <span aria-hidden="true">{named ? "▾" : "▸"}</span>{t(`${S}.moneyNames`)}
      </button>
      <dl id="set-studies-money" data-money-names hidden={!named} className="mt-1 grid gap-x-3 gap-y-1 text-xs leading-5 text-ink-muted sm:grid-cols-[max-content_1fr]">
        {(["clientBudget", "studyBudget", "wallet", "confirmThreshold"] as const).map((k) => (
          <div key={k} className="contents">
            <dt className="font-medium text-ink">{money[k]}</dt>
            <dd>{t(`${S}.money.${k}`)}{k === "confirmThreshold" ? ` ${tv(`${S}.thresholdBounds`, { min: formatNumber(MIN_THRESHOLD_USD, 0) })}` : ""}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
