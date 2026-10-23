"use client";

// Studie a rozpočty's study table as the redesign draws it (settings-redesign chunk 4, Studies
// board): each study's status chosen in its row, its spend against its budget with the share
// spent, the budget and the confirmation threshold set by a stepper where they are shown (I2:
// bounds stated, Shift x10, a value out of bounds refused at the field, never clamped), and the
// wallet pointed to where it is set. A study at 90 % of its budget is highlighted: it needs a
// person (the product owner, 2026-10-22). Costs a caller may not see stay "náklady nevidíte".

import Link from "next/link";
import { type ReactNode, useState } from "react";

import { money } from "@/i18n/cs";
import { t, tv } from "@/i18n/t";
import { type AdminClient, type Study, type Vocabularies, admin, research } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { nearLimit, usd } from "@/lib/researcher-spend";
import { ChoiceChips } from "../../ui/ChoiceChips";
import { FOCUS, SaveNote } from "../../ui/parts";
import { Stepper } from "../../ui/Stepper";
import { Button } from "../../rehome/ui";
import type { SaveState } from "@/lib/inline-edit";
import { describeMemberError } from "./errors";

const P = "aia.settings.panel";
const S = `${P}.studiesTab`;
/** The highest budget or threshold the API takes (routers/scope.py, le=1_000_000). */
const MAX_USD = 1_000_000;
/** Below this a confirmation threshold asks about nearly everything; the design's floor. */
const MIN_THRESHOLD_USD = 10;

type Part<T> = { ok: true; data: T } | { ok: false; message: string };
export type StudyRow = { study: Study; detail: Part<Study> };

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="min-w-0"><span className="mb-1 block text-xs text-ink-faint">{label}</span>{children}</div>;
}

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

function StatusCell({ study, statuses, reload }: { study: Study; statuses: readonly string[]; reload: () => void }) {
  const [state, setState] = useState<SaveState>("idle");
  const [error, setError] = useState<string | null>(null);
  const choose = async (status: string) => {
    setState("saving"); setError(null);
    try { await admin.setStudyStatus(study.study_id, status); setState("saved"); reload(); }
    catch (e) { setState("failed"); setError(describeMemberError(e)); }
  };
  return <>
    <ChoiceChips label={tv(`${S}.statusOf`, { study: study.name })} value={study.status} options={statuses.map((s) => ({ key: s, label: t(`aia.status.${s}`) }))} onChange={(s) => void choose(s)} />
    <SaveNote state={state} />
    {error ? <p role="alert" className="mt-1 text-xs text-status-fault">{error}</p> : null}
  </>;
}

function Spend({ costs }: { costs: Study }) {
  const budget = costs.budget_usd ?? 0;
  const spent = costs.spent_usd ?? 0;
  const pct = budget > 0 ? Math.min(100, Math.round((spent / budget) * 100)) : spent > 0 ? 100 : 0;
  const near = nearLimit(costs);
  return <>
    <span className="font-mono text-sm tabular-nums">{usd(spent)}</span>
    <span aria-hidden="true" className="mt-1 block h-1.5 w-28 overflow-hidden rounded-pill bg-surface-sunken">
      <i className={`block h-full ${near ? "bg-status-you" : "bg-signal"}`} style={{ width: `${pct}%` }} />
    </span>
    <span className="mt-0.5 block text-xs text-ink-muted">{tv(`${S}.ofBudget`, { pct })} · {tv(`${S}.remaining`, { usd: usd(costs.remaining_usd ?? Math.max(0, budget - spent)) })}{near ? ` · ${t(`${S}.nearLimit`)}` : ""}</span>
  </>;
}

function Budget({ costs, reload }: { costs: Study; reload: () => void }) {
  const refusal = useRefusal();
  const answered = useAnswered(costs.budget_usd);
  return <>
    <Stepper label={tv(`${S}.budgetOf`, { study: costs.name })} value={answered.value} min={Math.ceil((costs.spent_usd ?? 0) * 100) / 100} max={MAX_USD} step={10} decimals={2} unit="USD"
      onCommit={(v) => refusal.guard(() => admin.setStudyBudget(costs.study_id, v)).then(() => { answered.hold(v); reload(); })} note={t(`${S}.budgetNote`)} />
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
    <Stepper label={tv(`${S}.thresholdOf`, { study: costs.name })} value={limit} min={MIN_THRESHOLD_USD} max={max} step={10} decimals={2} unit="USD" showBounds={false}
      note={limit === null ? t(`${S}.never`) : null}
      onCommit={(v) => refusal.guard(() => research.setSpendConfirm(costs.study_id, v)).then(() => { answered.hold(v); reload(); })} />
    {refusal.shown}
    <span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-faint">
      {tv(`${S}.thresholdBounds`, { min: usd(MIN_THRESHOLD_USD) })}
      {limit !== null ? <Button small variant="quiet" data-dense onClick={() => { setCleared("saving"); refusal.guard(() => research.setSpendConfirm(costs.study_id, null)).then(() => { answered.hold(null); setCleared("saved"); reload(); }, () => setCleared("failed")); }}>{t(`${S}.setNever`)}</Button> : null}
      <SaveNote state={cleared} />
    </span>
  </>;
}

export function StudiesTable({ studies, clients, vocab, reload }: {
  studies: Part<StudyRow[]>; clients: Part<AdminClient[]>; vocab: Vocabularies; reload: () => void;
}) {
  const [query, setQuery] = useState("");
  const clientName = new Map(clients.ok ? clients.data.map((c) => [c.client_id, c.name]) : []);
  const q = query.trim().toLocaleLowerCase("cs");
  const count = studies.ok ? studies.data.length : 0;
  return (
    <section id="set-studies-table" aria-labelledby="set-studies-table-title" className="rounded-md border border-border bg-surface-raised px-6 py-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="set-studies-table-title" className="text-base font-semibold">{t(`${P}.studies.title`)}</h3>
        <div className="flex flex-wrap items-center gap-2">
          {studies.ok ? <span className="inline-flex min-h-[22px] items-center rounded-pill border border-border px-2 text-xs text-ink-muted">{tv(`${S}.count`, { n: count })}</span> : null}
          <input type="search" aria-label={t(`${P}.studySearch`)} placeholder={t(`${P}.studySearchPlaceholder`)} value={query} onChange={(e) => setQuery(e.target.value)}
            className={`min-h-9 w-56 rounded-sm border border-border-strong bg-surface-raised px-2 text-sm ${FOCUS}`} />
        </div>
      </div>
      <p className="mt-1 text-xs leading-5 text-ink-muted">{t(`${S}.tableHelp`)}</p>
      {!studies.ok ? <p role="alert" className="mt-3 text-sm text-status-fault">{studies.message}</p>
        : !studies.data.length ? <p className="mt-3 text-sm text-ink-muted">{t(`${P}.studies.none`)}</p>
        : (
          // A list of study rows, each its name and status over a grid of its four numbers that wraps
          // with the width: two steppers and a status choice do not fit one table row under 1440 px.
          <ul aria-label={t(`${P}.studies.title`)} className="mt-3 divide-y divide-border border-y border-border">
            {studies.data.map(({ study, detail }) => {
              const costs = detail.ok && detail.data.budget_usd !== null ? detail.data : null;
              const shown = `${study.name} ${clientName.get(study.client_id) ?? ""}`.toLocaleLowerCase("cs").includes(q);
              const near = costs ? nearLimit(costs) : false;
              // Filtered out, a row is hidden, never unmounted: a typed value survives the search.
              return (
                <li key={study.study_id} data-study={study.study_id} data-near={near ? "true" : undefined} hidden={!shown}
                  className={`px-2 py-3 ${near ? "bg-status-you-wash" : ""}`}>
                  <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                    <div className="min-w-0">
                      <span className="text-sm font-medium">{study.name}</span>
                      <span className="block text-xs text-ink-muted">{clientName.get(study.client_id) ?? study.client_id}</span>
                    </div>
                    <div><StatusCell study={study} statuses={vocab.study_statuses} reload={reload} /></div>
                  </div>
                  <div className="mt-2.5 grid grid-cols-[repeat(auto-fill,minmax(13rem,1fr))] gap-x-4 gap-y-3">
                    {costs ? <>
                      <Field label={t(`${P}.studies.spent`)}><Spend costs={costs} /></Field>
                      <Field label={money.studyBudget}><Budget costs={costs} reload={reload} /></Field>
                      <Field label={money.confirmThreshold}><Threshold costs={costs} reload={reload} /></Field>
                    </> : (
                      <Field label={t(`${P}.studies.spent`)}>
                        <span title={detail.ok ? "" : detail.message} className="rounded-sm border border-dashed border-border-strong px-1.5 text-xs">{t(`${P}.studies.costsHidden`)}</span>
                      </Field>
                    )}
                    <Field label={money.wallet}>
                      <Link href={appRoutes.area(study.client_id, "profile")} className={`text-sm text-signal hover:underline ${FOCUS}`}>{t(`${S}.profileRules`)}</Link>
                      <span className="block text-xs text-ink-faint">{t(`${S}.walletCap`)}</span>
                    </Field>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      <p className="mt-2 text-xs leading-5 text-ink-muted">{t(`${P}.studies.permissionNote`)}</p>
    </section>
  );
}

/** "Čtyři čísla peněz": the four amounts by their names, each with where it is set (money, D-01). */
export function MoneyNames() {
  const items = [
    [money.studyBudget, t(`${S}.money.studyBudget`)],
    [money.confirmThreshold, t(`${S}.money.confirmThreshold`)],
    [money.wallet, t(`${S}.money.wallet`)],
    [money.clientBudget, t(`${S}.money.clientBudget`)],
  ] as const;
  return (
    <div data-money-names className="mt-5 border-t border-border pt-4">
      <h4 className="text-sm font-semibold">{t(`${S}.money.title`)}</h4>
      <div className="mt-2.5 grid grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] gap-2.5">
        {items.map(([name, where]) => (
          <div key={name} className="rounded-md border border-border px-3.5 py-3">
            <b className="text-sm font-medium">{name}</b>
            <p className="mt-1 text-xs leading-[18px] text-ink-muted">{where}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
