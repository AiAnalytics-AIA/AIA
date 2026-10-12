"use client";

// What an edit does, beside the methodology in force (ADR 0023 decision 7, plan S4b): the
// API computes both through the real engine on fixed fictional panels (POST .../compare) and
// this shows, per panel, what moved -- whether each maps, Stress-1 and its band, every pair
// whose status changes, how far each object moves once the draft is turned onto the map in
// force, heights, K100 and the terrain. What did not move says so, so silence is never read
// as "not checked". For the support rules (plan G1d) the API decides fixed fictional cells
// instead, and this lists every cell the edit newly shows or newly suppresses, then all of them.
// For the response process (plan R1c) it answers fixed fictional questions for a fixed roster:
// each option's mean share, and how far one respondent moves from the model's vector.

import type { ReactNode } from "react";

import { t, tv } from "@/i18n/t";
import type { MethodAggregationPanel, MethodCompare, MethodEstimate, MethodMapSummary, MethodPanel, MethodResponseCompare, MethodResponseQuestion, MethodSupportCompare } from "@/lib/api";

const C = "aia.settings.methodology.versions.compare";
const number = new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 4 });
/** A change smaller than this is the arithmetic's, not the method's. */
const SAME = 1e-9;

const show = (v: number | null) => (v === null ? "—" : number.format(v));
const state = (s: string) => t(`research.exec.objectMap.state.${s}`);

function stress(m: MethodMapSummary): string {
  if (m.outcome !== "MAPPED" || m.stress_1 === null) {
    const reason = m.not_mappable ? t(`${C}.notMappable.${m.not_mappable}`) : "";
    return tv(`${C}.notMapped`, { reason });
  }
  return `${number.format(m.stress_1)} · ${m.quality ? t(`research.exec.objectMap.quality.${m.quality}`) : ""}`;
}

const counts = (m: MethodMapSummary) =>
  ["reliable", "weak", "unknown"].map((s) => `${state(s)} ${m.status_counts[s] ?? 0}`).join(" · ");

/** The rows of a per-object pair that moved, `[object, in force, draft]`. */
function moved(pairs: Record<string, [number | null, number | null]>): [string, number | null, number | null][] {
  return Object.entries(pairs)
    .filter(([, [a, b]]) => (a === null) !== (b === null) || (a !== null && b !== null && Math.abs(a - b) > SAME))
    .map(([id, [a, b]]) => [id, a, b]);
}

export function MethodologyComparison({ result }: { result: MethodCompare }) {
  return (
    <section aria-label={t(`${C}.title`)} data-methodology-compare className="flex min-w-0 flex-col gap-3">
      <h5 className="text-sm font-semibold">{tv(`${C}.heading`, { name: result.in_force })}</h5>
      {result.aggregation ? (
        <div data-compare-aggregation className="flex min-w-0 flex-col gap-3">
          <p className="max-w-3xl text-xs text-ink-muted">{t(`${A}.intro`)}</p>
          {result.aggregation.panels.map((p, i) => <AggregationPanel key={p.panel} panel={p} initiallyOpen={i === 0} />)}
        </div>
      ) : result.response ? (
        <ResponseCheck response={result.response} />
      ) : result.support ? (
        <SupportCheck support={result.support} />
      ) : (
        <>
          <p className="max-w-3xl text-xs text-ink-muted">{t(`${C}.intro`)}</p>
          {result.panels.map((p, i) => <Panel key={p.panel} panel={p} initiallyOpen={i === 0} />)}
        </>
      )}
    </section>
  );
}

function Panel({ panel: p, initiallyOpen }: { panel: MethodPanel; initiallyOpen: boolean }) {
  const heights = moved(p.heights);
  const k100 = moved(p.k100);
  const shifted = Object.entries(p.shifts).filter(([, d]) => d > SAME).sort((a, b) => b[1] - a[1]);
  return (
    <article data-compare-panel={p.panel} aria-label={p.label_cs} className="min-w-0 rounded-sm border border-border p-3 text-sm"><details open={initiallyOpen}><summary className="cursor-pointer"><h6 className="inline font-semibold">{p.label_cs}</h6></summary><div className="mt-3 flex min-w-0 flex-col gap-2">
      <div className="min-w-0 overflow-x-auto"><table className="w-full min-w-[23rem] text-xs">
        <thead>
          <tr className="text-left text-ink-muted">
            <th scope="col" className="py-1 pr-3 font-normal" />
            <th scope="col" className="py-1 pr-3 font-normal">{t(`${C}.inForce`)}</th>
            <th scope="col" className="py-1 font-normal">{t(`${C}.draft`)}</th>
          </tr>
        </thead>
        <tbody>
          <Row label={t(`${C}.stress`)} a={stress(p.in_force)} b={stress(p.draft)} />
          <Row label={t(`${C}.statuses`)} a={counts(p.in_force)} b={counts(p.draft)} />
          <Row label={t(`${C}.effectiveN`)} a={show(p.in_force.effective_n)} b={show(p.draft.effective_n)} />
        </tbody>
      </table></div>
      <Part title={t(`${C}.statusChanges`)} empty={t(`${C}.noStatusChange`)} has={p.status_changes.length > 0}>
        <ul className="flex flex-col gap-0.5 text-xs">
          {p.status_changes.map((c) => (
            <li key={`${c.a}|${c.b}`}>{c.a} – {c.b}: {state(c.in_force)} → <strong>{state(c.draft)}</strong></li>
          ))}
        </ul>
      </Part>
      <Part
        title={t(`${C}.shifts`)}
        empty={p.alignment_rmsd === null ? t(`${C}.shiftsNotMapped`) : t(`${C}.noShift`)}
        has={shifted.length > 0}
      >
        <p className="text-xs">
          {tv(`${C}.largestShift`, { value: number.format(shifted[0]?.[1] ?? 0), object: shifted[0]?.[0] ?? "" })}
        </p>
      </Part>
      <Part title={t(`${C}.heights`)} empty={t(`${C}.noChange`)} has={heights.length > 0}>
        <Changes rows={heights} />
      </Part>
      <Part title={t(`${C}.k100`)} empty={t(`${C}.noChange`)} has={k100.length > 0}>
        <Changes rows={k100} />
      </Part>
      <Part
        title={t(`${C}.terrain`)}
        empty={p.terrain_note ?? t(`${C}.noChange`)}
        has={p.terrain_max_change !== null && p.terrain_max_change > SAME}
      >
        <p className="text-xs">{tv(`${C}.terrainChange`, { value: show(p.terrain_max_change) })}</p>
      </Part>
      {p.notes.map((n) => <p key={n} className="text-xs text-ink-muted">{n}</p>)}
    </div></details></article>
  );
}

function Row({ label, a, b }: { label: string; a: string; b: string }) {
  return (
    <tr className="border-t border-border">
      <th scope="row" className="py-1 pr-3 text-left font-normal text-ink-muted">{label}</th>
      <td className="py-1 pr-3 font-mono tabular-nums">{a}</td>
      <td className={`py-1 font-mono tabular-nums ${a === b ? "" : "font-semibold"}`}>{b}</td>
    </tr>
  );
}

function Part({ title, empty, has, children }: { title: string; empty: string; has: boolean; children: ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium">{title}</p>
      {has ? children : <p className="text-xs text-ink-muted">{empty}</p>}
    </div>
  );
}

function Changes({ rows }: { rows: [string, number | null, number | null][] }) {
  return (
    <ul className="flex flex-col gap-0.5 font-mono text-xs tabular-nums">
      {rows.map(([id, a, b]) => <li key={id}>{id}: {show(a)} → {show(b)}</li>)}
    </ul>
  );
}

const S = `${C}.support`;
const status = (s: string) => t(`${S}.status.${s}`);

function SupportCheck({ support }: { support: MethodSupportCompare }) {
  const labels = new Map(support.cells.map((c) => [c.cell, c.label_cs]));
  const moved = (rows: [string, string][]) => (
    <ul className="flex flex-col gap-0.5 text-xs">
      {rows.map(([cell, surface]) => (
        <li key={`${cell}|${surface}`}>{labels.get(cell) ?? cell} · {t(`${S}.surface.${surface}`)}</li>
      ))}
    </ul>
  );
  return (
    <div data-compare-support className="flex min-w-0 flex-col gap-3">
      <p className="max-w-3xl text-xs text-ink-muted">{t(`${S}.intro`)}</p>
      <Part title={t(`${S}.newlyReported`)} empty={t(`${S}.noneReported`)} has={support.newly_reported.length > 0}>
        {moved(support.newly_reported)}
      </Part>
      <Part title={t(`${S}.newlySuppressed`)} empty={t(`${S}.noneSuppressed`)} has={support.newly_suppressed.length > 0}>
        {moved(support.newly_suppressed)}
      </Part>
      <details className="min-w-0">
        <summary className="cursor-pointer text-xs font-medium">{tv(`${S}.cells`, { count: support.cells.length })}</summary>
        <div className="mt-2 min-w-0 overflow-x-auto"><table className="w-full min-w-[36rem] text-xs" aria-label={tv(`${S}.cells`, { count: support.cells.length })}>
          <thead>
            <tr className="text-left text-ink-muted">
              <th scope="col" className="py-1 pr-3 font-normal">{t(`${S}.cell`)}</th>
              <th scope="col" className="py-1 pr-3 font-normal">n</th>
              <th scope="col" className="py-1 pr-3 font-normal">{t(`${C}.effectiveN`)}</th>
              <th scope="col" className="py-1 pr-3 font-normal">{t(`${S}.donors`)}</th>
              <th scope="col" className="py-1 pr-3 font-normal">{t(`${S}.results`)}</th>
              <th scope="col" className="py-1 font-normal">{t(`${S}.analysis`)}</th>
            </tr>
          </thead>
          <tbody>
            {support.cells.map((c) => (
              <tr key={c.cell} data-support-cell={c.cell} className="border-t border-border">
                <th scope="row" className="py-1 pr-3 text-left font-normal">{c.label_cs}</th>
                <td className="py-1 pr-3 font-mono tabular-nums">{c.n}</td>
                <td className="py-1 pr-3 font-mono tabular-nums">{number.format(c.effective_n)}</td>
                <td className="py-1 pr-3 font-mono tabular-nums">{c.donors}</td>
                <StatusCell pair={c.results} />
                <StatusCell pair={c.analysis} />
              </tr>
            ))}
          </tbody>
        </table></div>
      </details>
    </div>
  );
}

function StatusCell({ pair: [a, b] }: { pair: [string, string] }) {
  return (
    <td className="py-1 pr-3">
      {a === b ? status(a) : <>{status(a)} → <strong>{status(b)}</strong></>}
    </td>
  );
}

const A = `${C}.aggregation`;

/** An estimate with its interval as the draft check shows it: "41,0 (35,0–47,0)". */
function estimate([value, low, high]: [number | null, number | null, number | null]): string {
  if (value === null) return "—";
  return low === null || high === null ? number.format(value) : `${number.format(value)} (${number.format(low)}–${number.format(high)})`;
}

function measureLabel(r: MethodEstimate): string {
  if (r.measure.startsWith("share:")) return tv(`${A}.share`, { option: r.measure.slice("share:".length) });
  return t(`${A}.measure.${r.measure}`);
}

function AggregationPanel({ panel: p, initiallyOpen }: { panel: MethodAggregationPanel; initiallyOpen: boolean }) {
  const moved = p.rows.filter((r) => r.moved);
  const effective = Object.entries(p.effective_n).filter(([, [a, b]]) => Math.abs(a - b) > SAME);
  return (
    <article data-compare-aggregation-panel={p.panel} aria-label={p.label_cs} className="min-w-0 rounded-sm border border-border p-3 text-sm">
      <details open={initiallyOpen}>
        <summary className="cursor-pointer">
          <h6 className="inline font-semibold">{p.label_cs}</h6>{" "}
          <span className="text-xs text-ink-muted">{tv(`${A}.summary`, { moved: moved.length, rows: p.rows.length, respondents: p.respondents })}</span>
        </summary>
        <div className="mt-3 flex min-w-0 flex-col gap-2">
          <Part title={t(`${A}.moved`)} empty={t(`${A}.noneMoved`)} has={moved.length > 0}>
            <ul className="flex flex-col gap-0.5 text-xs">
              {moved.map((r) => (
                <li key={`${r.question}|${r.measure}`}>
                  <span className="font-mono">{r.question}</span> · {measureLabel(r)}: <span className="tabular-nums">{estimate(r.in_force)}</span> → <strong className="tabular-nums">{estimate(r.draft)}</strong>
                </li>
              ))}
            </ul>
          </Part>
          <Part title={t(`${A}.statuses`)} empty={t(`${A}.noStatusChange`)} has={p.status_changes.length > 0}>
            <ul className="flex flex-col gap-0.5 text-xs">
              {p.status_changes.map((s) => (
                <li key={s.question}><span className="font-mono">{s.question}</span>: {t(`${C}.support.status.${s.in_force}`)} → <strong>{t(`${C}.support.status.${s.draft}`)}</strong></li>
              ))}
            </ul>
          </Part>
          <Part title={t(`${C}.effectiveN`)} empty={t(`${C}.noChange`)} has={effective.length > 0}>
            <ul className="flex flex-col gap-0.5 text-xs tabular-nums">
              {effective.map(([q, [a, b]]) => <li key={q}><span className="font-mono">{q}</span>: {number.format(a)} → {number.format(b)}</li>)}
            </ul>
          </Part>
        </div>
      </details>
    </article>
  );
}

const R = `${C}.response`;
const pp = new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 2 });

function ResponseCheck({ response }: { response: MethodResponseCompare }) {
  return (
    <div data-compare-response className="flex min-w-0 flex-col gap-3">
      <p className="max-w-3xl text-xs text-ink-muted">{tv(`${R}.intro`, { respondents: response.respondents })}</p>
      <p className="text-xs" data-response-described>{tv(`${R}.described`, { before: response.described_in_force, after: response.described_draft, respondents: response.respondents })}</p>
      {response.questions.map((q, i) => <ResponseQuestion key={q.question} q={q} initiallyOpen={i === 0} />)}
    </div>
  );
}

function ResponseQuestion({ q, initiallyOpen }: { q: MethodResponseQuestion; initiallyOpen: boolean }) {
  return (
    <article data-compare-response-question={q.question} aria-label={q.label_cs} className="min-w-0 rounded-sm border border-border p-3 text-sm">
      <details open={initiallyOpen}>
        <summary className="cursor-pointer">
          <h6 className="inline font-semibold">{q.label_cs}</h6>{" "}
          <span className="text-xs text-ink-muted">{tv(`${R}.summary`, { moved: pp.format(q.moved_pp), before: pp.format(q.shift_in_force), after: pp.format(q.shift_draft) })}</span>
        </summary>
        <div className="mt-3 min-w-0 overflow-x-auto"><table className="w-full min-w-[23rem] text-xs" aria-label={q.label_cs}>
          <thead>
            <tr className="text-left text-ink-muted">
              <th scope="col" className="py-1 pr-3 font-normal">{t(`${R}.option`)}</th>
              <th scope="col" className="py-1 pr-3 font-normal">{t(`${R}.model`)}</th>
              <th scope="col" className="py-1 pr-3 font-normal">{t(`${C}.inForce`)}</th>
              <th scope="col" className="py-1 font-normal">{t(`${C}.draft`)}</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {q.labels.map((label, k) => (
              <tr key={label} className="border-t border-border">
                <th scope="row" className="py-1 pr-3 text-left font-normal">{label}</th>
                <td className="py-1 pr-3">{pp.format(q.model[k])} %</td>
                <td className="py-1 pr-3">{pp.format(q.in_force[k])} %</td>
                <td className={`py-1 ${Math.abs(q.in_force[k] - q.draft[k]) > SAME ? "font-semibold" : ""}`}>{pp.format(q.draft[k])} %</td>
              </tr>
            ))}
            <tr className="border-t border-border">
              <th scope="row" className="py-1 pr-3 text-left font-normal">{t(`${R}.shift`)}</th>
              <td className="py-1 pr-3" />
              <td className="py-1 pr-3">{pp.format(q.shift_in_force)} p. b.</td>
              <td className="py-1">{pp.format(q.shift_draft)} p. b.</td>
            </tr>
          </tbody>
        </table></div>
      </details>
    </article>
  );
}
