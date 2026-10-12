"use client";

// What an edit does, beside the methodology in force (ADR 0023 decision 7, plan S4b): the
// API computes both through the real engine on fixed fictional panels (POST .../compare) and
// this shows, per panel, what moved -- whether each maps, Stress-1 and its band, every pair
// whose status changes, how far each object moves once the draft is turned onto the map in
// force, heights, K100 and the terrain. What did not move says so, so silence is never read
// as "not checked".

import type { ReactNode } from "react";

import { t, tv } from "@/i18n/t";
import type { MethodCompare, MethodMapSummary, MethodPanel } from "@/lib/api";

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
      <p className="max-w-3xl text-xs text-ink-muted">{t(`${C}.intro`)}</p>
      {result.panels.map((p, i) => <Panel key={p.panel} panel={p} initiallyOpen={i === 0} />)}
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
