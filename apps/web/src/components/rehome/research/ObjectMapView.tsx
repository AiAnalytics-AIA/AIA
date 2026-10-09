"use client";

// The audit's object map on the Results page (plan sociomap-formula-corrections chunk 5a).
//
// Renders the stored contract-3 artifact only: positions, Stress-1, pair states, heights and
// the envelope terrain come from the worker, and this view never computes or adjusts them.
// From above: the terrain's cells in the sequential palette (mean rating), a line for each
// pair that passes both of Q6's gates (opacity |r|, sign as colour), each object at its
// place. The map is internal while D6 is open; the Results card that holds it says so first.

import { useMemo, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  type BatteryWithMaps,
  type ObjectMapArtifact,
  MAP_VIEW,
  belowFloor,
  mapLinks,
  mapObjects,
  readObjectMap,
  relationsOf,
  terrainCells,
  toScreen,
  viewSpan,
} from "@/lib/object-map-view";
import { labelOffsets, num } from "@/lib/sociomapping-view";

const SEQ = (band: number) => `var(--viz-seq-${band + 1})`;
const SIGN = { positive: "var(--viz-div-7)", negative: "var(--viz-div-1)" } as const;

export function ObjectMapView({ battery, dataOrigin }: { battery: BatteryWithMaps; dataOrigin: string | null }) {
  const read = readObjectMap(battery);
  if (!read.ok) {
    return read.reason === "contract" ? <p role="alert" className="text-sm text-status-fault">{t("research.exec.objectMap.unreadable")}</p> : null;
  }
  const { map, methodId, fingerprint } = read;
  return (
    <section aria-label={battery.title} className="flex flex-col gap-3" data-testid={`object-map-${battery.battery_id}`}>
      <h3 className="text-sm font-semibold">{tv("research.exec.objectMap.title", { method: methodId })}</h3>
      {dataOrigin && dataOrigin.startsWith("SYNTHETIC") ? (
        <p className="text-sm text-status-fault">{tv("research.exec.objectMap.synthetic", { origin: dataOrigin })}</p>
      ) : null}
      {map.spec.terrain ? (
        <p className="text-xs text-ink-muted">{tv("research.exec.objectMap.provisional", { sigma: num(map.spec.terrain.sigma, 2) })}</p>
      ) : null}
      {map.outcome === "MAPPED" && map.layout ? (
        <MappedView battery={battery} map={map} />
      ) : (
        <p role="alert" className="text-sm text-status-fault">{tv("research.exec.objectMap.notMappable", { message: map.not_mappable?.message ?? "—" })}</p>
      )}
      <Support map={map} />
      <p className="text-xs text-ink-muted">{tv("research.exec.objectMap.method", { method: map.spec.methodology_version, fingerprint: fingerprint.slice(0, 12) })}</p>
    </section>
  );
}

function MappedView({ battery, map }: { battery: BatteryWithMaps; map: ObjectMapArtifact }) {
  const objects = useMemo(() => mapObjects(battery, map), [battery, map]);
  const links = useMemo(() => mapLinks(map), [map]);
  const cells = useMemo(() => terrainCells(map), [map]);
  const [selected, setSelected] = useState<string | null>(objects[0]?.id ?? null);
  const span = viewSpan(map);
  const at = new Map(objects.map((o) => [o.id, toScreen(o.x, o.y, span)]));
  const labelAt = labelOffsets(objects.map((o) => ({ id: o.id, ...at.get(o.id)! })), 15, 70);
  const cellPx = cells.length ? (cells[0].size * (MAP_VIEW.size - 2 * MAP_VIEW.pad)) / (2 * span) : 0;
  const layout = map.layout!;
  const chosen = objects.find((o) => o.id === selected) ?? null;
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <div>
        <svg
          viewBox={`0 0 ${MAP_VIEW.size} ${MAP_VIEW.size}`}
          role="img"
          aria-label={tv("research.exec.objectMap.mapLabel", { title: battery.title, n: objects.length })}
          className="w-full rounded border border-border bg-surface-raised"
          data-testid="object-map-svg"
        >
          <g data-testid="object-map-terrain">
            {cells.map((c, k) => {
              const p = toScreen(c.x, c.y, span);
              return <rect key={k} x={p.sx - cellPx / 2} y={p.sy - cellPx / 2} width={cellPx + 0.5} height={cellPx + 0.5} fill={SEQ(c.band)} opacity={0.55} />;
            })}
          </g>
          <g data-testid="object-map-links">
            {links.map((l) => {
              const a = at.get(l.a)!;
              const b = at.get(l.b)!;
              return (
                <line
                  key={`${l.a}|${l.b}`}
                  x1={a.sx}
                  y1={a.sy}
                  x2={b.sx}
                  y2={b.sy}
                  stroke={SIGN[l.sign]}
                  strokeWidth={2}
                  strokeOpacity={0.25 + 0.75 * l.strength}
                  strokeDasharray={l.sign === "negative" ? "6 4" : undefined}
                />
              );
            })}
          </g>
          {objects.map((o) => {
            const p = at.get(o.id)!;
            const on = o.id === selected;
            return (
              <g key={o.id} onClick={() => setSelected(o.id)} className="cursor-pointer" data-testid={`object-map-point-${o.id}`}>
                <circle cx={p.sx} cy={p.sy} r={on ? 9 : 7} fill={o.band === null ? "var(--surface)" : SEQ(o.band)} stroke={on ? "var(--ink)" : "var(--ink-muted)"} strokeWidth={on ? 2.5 : 1.2} />
                <text x={p.sx + 11} y={p.sy + (labelAt.get(o.id) ?? -8)} fontSize={13} fill="var(--ink)">{o.label}</text>
              </g>
            );
          })}
        </svg>
        <Legend />
        <p className="mt-1 text-xs text-ink-muted">{t("research.exec.objectMap.howToRead")}</p>
        {map.terrain.status === "not_computed" ? <p className="mt-1 text-xs text-ink-muted">{tv("research.exec.objectMap.noTerrain", { reason: map.terrain.reason })}</p> : null}
      </div>
      <div className="flex flex-col gap-3">
        <p className="text-sm" data-testid="object-map-fit">
          <span className="font-semibold">{t("research.exec.objectMap.fit")}: </span>
          {tv("research.exec.objectMap.stress", { value: num(layout.stress_1), quality: t(`research.exec.objectMap.quality.${layout.quality}`) })}
        </p>
        {!layout.converged ? <p className="text-xs text-status-fault">{t("research.exec.objectMap.notConverged")}</p> : null}
        <label className="flex flex-col gap-1 text-sm">
          {t("research.exec.objectMap.object")}
          <select className="rounded border border-border bg-surface-raised px-2 py-1" value={selected ?? ""} onChange={(e) => setSelected(e.target.value)}>
            {objects.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
          </select>
        </label>
        {chosen ? (
          <div className="rounded border border-border p-3 text-sm" data-testid="object-map-details">
            <p className="font-semibold">{chosen.label}</p>
            <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
              <dt className="text-ink-muted">{t("research.exec.objectMap.height")}</dt>
              <dd className="tabular-nums">{num(chosen.height, 2)}</dd>
              <dt className="text-ink-muted">{t("research.exec.objectMap.role")}</dt>
              <dd>{chosen.primary ? t("research.exec.objectMap.primary") : t("research.exec.objectMap.secondary")}</dd>
            </dl>
            <p className="mt-2 text-xs font-semibold">{t("research.exec.objectMap.relations")}</p>
            <table className="mt-1 w-full text-xs">
              <tbody>
                {relationsOf(battery, map, chosen.id).map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="py-0.5 pr-2">{r.label}</td>
                    <td className={`py-0.5 tabular-nums ${r.r !== null && r.r < 0 ? "text-status-fault" : ""}`}>{num(r.r, 2)}</td>
                    <td className="py-0.5 text-ink-muted">{r.state ? t(`research.exec.objectMap.state.${r.state}`) : "—"}{r.drawn ? ` · ${t("research.exec.objectMap.drawn")}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Legend() {
  return (
    <div className="mt-2 flex flex-col gap-1 text-xs" aria-label={t("research.exec.objectMap.legendHeight")}>
      <span className="flex items-center gap-2">
        <span>{t("research.exec.objectMap.legendHeight")}:</span>
        <span>0</span>
        <span className="flex" aria-hidden>
          {[0, 1, 2, 3, 4, 5, 6].map((k) => <span key={k} className="inline-block h-3 w-5" style={{ background: SEQ(k) }} />)}
        </span>
        <span>1</span>
      </span>
      <span className="flex items-center gap-3">
        <span>{t("research.exec.objectMap.legendLinks")}:</span>
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-6" style={{ background: SIGN.positive }} aria-hidden />{t("research.exec.objectMap.positive")}</span>
        <span className="flex items-center gap-1"><span className="inline-block h-0.5 w-6 border-t-2 border-dashed" style={{ borderColor: SIGN.negative }} aria-hidden />{t("research.exec.objectMap.negative")}</span>
      </span>
    </div>
  );
}

function Support({ map }: { map: ObjectMapArtifact }) {
  const s = map.support;
  const c = map.status_counts;
  const hidden = belowFloor(map);
  return (
    <div className="flex flex-col gap-1 text-xs text-ink-muted" data-testid="object-map-support">
      <p>
        {tv("research.exec.objectMap.support", {
          placed: s.placed,
          respondents: s.respondents,
          effective: s.effective_n === null ? "—" : num(s.effective_n, 1),
          pairs: tv("research.exec.objectMap.pairs", { reliable: c.reliable ?? 0, weak: c.weak ?? 0, unknown: c.unknown ?? 0 }),
        })}
      </p>
      <p data-testid="object-map-not-placed">{tv("research.exec.objectMap.notPlaced", { count: s.not_placed })}</p>
      {hidden && map.relations.effect_floor !== undefined ? (
        <p>{tv("research.exec.objectMap.belowFloor", { floor: num(map.relations.effect_floor, 2), count: hidden })}</p>
      ) : null}
    </div>
  );
}
