"use client";

// The audit's object map on the Results page (plan sociomap-formula-corrections chunk 5a).
//
// Renders the stored contract-3 artifact only: positions, Stress-1, pair states, heights and
// the envelope terrain come from the worker, and this view never computes or adjusts them.
// 3D is explicitly activated by the reader; top view is its immediate kill switch.
// From above: the terrain's cells in the sequential palette (mean rating), a line for each
// pair that passes both of Q6's gates (opacity |r|, sign as colour), each object at its
// place. The map is internal while D6 is open; the Results card that holds it says so first.

import { type KeyboardEvent, type PointerEvent, useMemo, useRef, useState } from "react";
import { boundedCamera, INITIAL_CAMERA, type TerrainCamera } from "@/lib/object-map-3d";
import { Button } from "../ui";
import { ObjectMapTerrain } from "./ObjectMapTerrain";

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
  const [mode, setMode] = useState<"3d" | "top">("top");
  const [camera, setCamera] = useState<TerrainCamera>(INITIAL_CAMERA);
  const [expanded, setExpanded] = useState(true);
  const [showLinks, setShowLinks] = useState(true);
  const [partner, setPartner] = useState<string | null>(objects[1]?.id ?? null);
  const drag = useRef<{ x: number; y: number; camera: TerrainCamera } | null>(null);
  const move = (change: Partial<TerrainCamera>) => setCamera((c) => boundedCamera({ ...c, ...change }));
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget || mode !== "3d") return;
    const keys: Record<string, Partial<TerrainCamera>> = {
      ArrowLeft: { yaw: camera.yaw - Math.PI / 12 }, ArrowRight: { yaw: camera.yaw + Math.PI / 12 },
      ArrowUp: { elevation: camera.elevation + 0.1 }, ArrowDown: { elevation: camera.elevation - 0.1 },
      "+": { zoom: camera.zoom * 1.15 }, "-": { zoom: camera.zoom / 1.15 },
    };
    if (e.key === "Home") { e.preventDefault(); setCamera(INITIAL_CAMERA); }
    else if (keys[e.key]) { e.preventDefault(); move(keys[e.key]); }
  };
  const onDown = (e: PointerEvent<HTMLDivElement>) => {
    if (mode !== "3d" || e.button !== 0 || (e.target as Element).closest('[role="button"]')) return;
    drag.current = { x: e.clientX, y: e.clientY, camera };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const start = drag.current;
    if (start) move({ yaw: start.camera.yaw + (e.clientX - start.x) / 180, elevation: start.camera.elevation - (e.clientY - start.y) / 240 });
  };
  const span = viewSpan(map);
  const at = new Map(objects.map((o) => [o.id, toScreen(o.x, o.y, span)]));
  const labelAt = labelOffsets(objects.map((o) => ({ id: o.id, ...at.get(o.id)! })), 15, 70);
  const cellPx = cells.length ? (cells[0].size * (MAP_VIEW.size - 2 * MAP_VIEW.pad)) / (2 * span) : 0;
  const layout = map.layout!;
  const chosen = objects.find((o) => o.id === selected) ?? null;
  const relations = chosen ? relationsOf(battery, map, chosen.id) : [];
  const pair = relations.find((r) => r.id === partner) ?? relations[0];
  const rating = battery.rating_scale;
  return (
    <div className={`grid gap-4 ${expanded ? "" : "lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]"}`}>
      <div className="min-w-0">
        <p className="mb-3 text-sm" data-testid="object-map-fit">
          <span className="font-semibold">{t("research.exec.objectMap.fit")}: </span>
          {tv("research.exec.objectMap.stress", { value: num(layout.stress_1), quality: t(`research.exec.objectMap.quality.${layout.quality}`) })}
        </p>
        {!layout.converged ? <p className="text-xs text-status-fault">{t("research.exec.objectMap.notConverged")}</p> : null}

        <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label={t("research.exec.sociomapping.controls")}>
          <Button small aria-pressed={mode === "3d"} disabled={map.terrain.status !== "computed"} onClick={() => setMode("3d")}>{t("research.exec.objectMap.view3d")}</Button>
          <Button small aria-pressed={mode === "top"} onClick={() => setMode("top")}>{t("research.exec.sociomapping.viewTop")}</Button>
          <Button small disabled={mode !== "3d"} onClick={() => move({ yaw: camera.yaw - Math.PI / 12 })}>{t("research.exec.sociomapping.rotateLeft")}</Button>
          <Button small disabled={mode !== "3d"} onClick={() => move({ yaw: camera.yaw + Math.PI / 12 })}>{t("research.exec.sociomapping.rotateRight")}</Button>
          <Button small disabled={mode !== "3d"} onClick={() => move({ zoom: camera.zoom * 1.15 })}>{t("research.exec.sociomapping.zoomIn")}</Button>
          <Button small disabled={mode !== "3d"} onClick={() => move({ zoom: camera.zoom / 1.15 })}>{t("research.exec.sociomapping.zoomOut")}</Button>
          <Button small onClick={() => setCamera(INITIAL_CAMERA)}>{t("research.exec.sociomapping.reset")}</Button>
          <Button small aria-pressed={expanded} onClick={() => setExpanded(!expanded)}>{t(`research.exec.objectMap.${expanded ? "compact" : "expand"}`)}</Button>
        </div>
        <div className="mb-2 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
          <label className="flex items-center gap-2"><input type="checkbox" checked={showLinks} onChange={(e) => setShowLinks(e.target.checked)} />{t("research.exec.objectMap.showLinks")}</label>
          {mode === "3d" ? <label className="flex flex-wrap items-center gap-2">{t("research.exec.objectMap.relief")}<input type="range" min="0.5" max="2" step="0.1" value={camera.relief} onChange={(e) => move({ relief: Number(e.target.value) })} /><output>{num(camera.relief, 1)}×</output></label> : null}
        </div>
        <div className="touch-none select-none overflow-hidden rounded border border-border bg-surface-raised focus:outline focus:outline-2 focus:outline-[var(--focus-ring)]"
          role="region" aria-label={t("research.exec.objectMap.workspace")} tabIndex={0} onKeyDown={onKey}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
        {mode === "3d" ? <ObjectMapTerrain map={map} objects={objects} camera={camera} selected={selected} partner={pair?.id ?? null} showLinks={showLinks} onSelect={setSelected} /> : <svg
          viewBox={`0 0 ${MAP_VIEW.size} ${MAP_VIEW.size}`}
          role="group"
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
            {(showLinks ? links : []).map((l) => {
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
              <g key={o.id} role="button" tabIndex={0} aria-label={tv("research.exec.objectMap.selectObject", { label: o.label })} aria-pressed={on} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(o.id); } }} onClick={() => setSelected(o.id)} className="cursor-pointer" data-testid={`object-map-point-${o.id}`}>
                <circle cx={p.sx} cy={p.sy} r={on ? 9 : 7} fill={o.band === null ? "var(--surface)" : SEQ(o.band)} stroke={on ? "var(--ink)" : "var(--ink-muted)"} strokeWidth={on ? 2.5 : 1.2} />
                <text x={p.sx + 11} y={p.sy + (labelAt.get(o.id) ?? -8)} fontSize={13} fill="var(--ink)">{o.label}</text>
              </g>
            );
          })}
        </svg>}
        </div>
        {mode === "3d" ? <><p className="mt-2 text-xs text-ink-muted">{t("research.exec.objectMap.referencePlane")}</p><p className="mt-1 text-xs text-ink-muted">{t("research.exec.objectMap.cameraHelp")}</p><p className="mt-1 text-xs text-ink-muted">{t("research.exec.objectMap.labelHelp")}</p></> : null}
        <Legend />
        <p className="mt-1 text-xs text-ink-muted">{t("research.exec.objectMap.howToRead")}</p>
        {map.terrain.status === "not_computed" ? <p className="mt-1 text-xs text-ink-muted">{tv("research.exec.objectMap.noTerrain", { reason: map.terrain.reason })}</p> : null}
      </div>
      <div className={`grid gap-4 ${expanded ? "md:grid-cols-2" : ""}`}>
      <div className="flex min-w-0 flex-col gap-3">
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
              {rating ? <><dt className="text-ink-muted">{tv("research.exec.objectMap.originalRating", { low: num(rating[0], 0), high: num(rating[1], 0) })}</dt><dd>{num(chosen.height === null ? null : rating[0] + chosen.height * (rating[1] - rating[0]), 2)}</dd></> : null}
              <dt className="text-ink-muted">{t("research.exec.objectMap.role")}</dt>
              <dd>{chosen.primary ? t("research.exec.objectMap.primary") : t("research.exec.objectMap.secondary")}</dd>
            </dl>
            <p className="mt-2 text-xs font-semibold">{t("research.exec.objectMap.relations")}</p>
            <table className="mt-1 w-full text-xs">
              <tbody>
                {relations.map((r) => (
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
      <div className="rounded border border-border bg-surface p-4 text-sm" data-testid="object-map-reading">
        <h4 className="font-semibold">{t("research.exec.objectMap.readingTitle")}</h4>
        <p className="mt-2">{tv("research.exec.objectMap.readingIntro", { title: battery.title })}</p>
        <p className="mt-2">{t("research.exec.objectMap.surfaceMeaning")}</p>
        <p className="mt-2">{t("research.exec.objectMap.distanceMeaning")}</p>
        <p className="mt-2">{t(`research.exec.objectMap.${layout.quality === "weak" || layout.quality === "unreliable" ? "weakFitMeaning" : "fitMeaning"}`)}</p>
        {chosen && pair ? <>
          <label className="mt-4 flex flex-col gap-1">{tv("research.exec.objectMap.compareWith", { label: chosen.label })}
            <select value={pair.id} className="rounded border border-border bg-surface-raised px-2 py-1" onChange={(e) => setPartner(e.target.value)}>
              {relations.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          </label>
          <p className="mt-2" data-testid="object-map-pair">{tv("research.exec.objectMap.pairValue", { a: chosen.label, b: pair.label, r: num(pair.r, 3) })} {t(`research.exec.objectMap.${pair.state === "unknown" || pair.r === null ? "pairUnknown" : pair.state === "weak" ? "pairWeak" : pair.r > 0 ? "pairPositive" : pair.r < 0 ? "pairNegative" : "pairZero"}`)}</p>
          {!pair.drawn ? <p className="mt-1 text-xs text-ink-muted">{t("research.exec.objectMap.pairHidden")}</p> : null}
        </> : null}
      </div>
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
