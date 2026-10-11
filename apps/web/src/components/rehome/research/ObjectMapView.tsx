"use client";

// The audit's object map on the Results page (plan sociomap-formula-corrections chunk 5a),
// redesigned (plan object-map-3d-redesign).
//
// Renders the stored contract-3 artifact only: positions, Stress-1, pair states, heights and
// the envelope terrain come from the worker, and this view never computes or adjusts them.
// From above (the default): the stored terrain in ten display terraces on the absolute 0-1
// scale, the selected object's drawn relations (the one `mapLinks` rule; opacity |r|, sign as
// colour and dash), each object at its stored place. 3D is explicitly activated by the
// reader; top view unmounts it and is its immediate kill switch. Relief, camera, rotation and
// the opening animation are presentation state. The map is internal while D6 is open.

import { type KeyboardEvent, type PointerEvent, type ReactNode, type RefObject, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { boundedCamera, INITIAL_CAMERA, type TerrainCamera } from "@/lib/object-map-3d";
import { ObjectMapTerrain } from "./ObjectMapTerrain";
import { type MarkState, MapLabel, MapPin, PinButton, TERRACE, casing, layoutLabels, legendLabel, linkStyle } from "./ObjectMapMarks";

import { t, tv } from "@/i18n/t";
import {
  type BatteryWithMaps,
  type MapObject,
  type ObjectMapArtifact,
  type PairDetail,
  type Rect,
  type ViewSize,
  TERRACE_BANDS,
  belowFloor,
  mapLinks,
  mapObjects,
  originalRating,
  rankedByHeight,
  readObjectMap,
  relationsOf,
  screenScale,
  terraceEdges,
  terrainCells,
  toScreen,
  viewSpan,
} from "@/lib/object-map-view";
import { num } from "@/lib/sociomapping-view";

/** The stage's size before it is measured (and in tests, where nothing is laid out). */
const DEFAULT_VIEW: ViewSize = { width: 900, height: 560 };
const RISE_MS = 1600;
const ORBIT_MS = 30000;

const prefersReducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
const canAnimate = () => typeof window !== "undefined" && typeof window.requestAnimationFrame === "function" && !prefersReducedMotion();

export function ObjectMapView({ battery, dataOrigin }: { battery: BatteryWithMaps; dataOrigin: string | null }) {
  const read = readObjectMap(battery);
  if (!read.ok) {
    return read.reason === "contract" ? <p role="alert" className="text-sm text-status-fault">{t("research.exec.objectMap.unreadable")}</p> : null;
  }
  const { map, methodId, fingerprint } = read;
  const synthetic = dataOrigin !== null && dataOrigin.startsWith("SYNTHETIC");
  const facts = <Facts map={map} methodId={methodId} fingerprint={fingerprint} dataOrigin={synthetic ? dataOrigin : null} />;
  return (
    <section aria-label={battery.title} className="flex flex-col gap-3" data-testid={`object-map-${battery.battery_id}`}>
      <h3 className="text-sm font-semibold">{tv("research.exec.objectMap.title", { method: methodId })}</h3>
      <div className="flex flex-wrap gap-2 text-xs">
        <span title={t("research.exec.results.internal")} className="inline-flex items-center gap-1.5 rounded-full bg-status-world-wash px-2.5 py-1 text-ink">
          <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-ink" />{t("research.exec.objectMap.internalChip")}
        </span>
        {synthetic ? (
          <span title={tv("research.exec.objectMap.synthetic", { origin: dataOrigin! })} data-testid="object-map-synthetic" className="inline-flex items-center gap-1.5 rounded-full border border-status-fault px-2.5 py-1 text-status-fault">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-status-fault" />{t("research.exec.objectMap.syntheticChip")}
          </span>
        ) : null}
      </div>
      {map.outcome === "MAPPED" && map.layout ? (
        <MappedView key={fingerprint} battery={battery} map={map} methodId={methodId} facts={facts} />
      ) : (
        <>
          <p role="alert" className="text-sm text-status-fault">{tv("research.exec.objectMap.notMappable", { message: map.not_mappable?.message ?? "—" })}</p>
          {facts}
        </>
      )}
    </section>
  );
}

/** A size observed on an element; the default until it has been laid out. */
function useViewSize(ref: RefObject<HTMLElement | null>): ViewSize {
  const [size, setSize] = useState<ViewSize>(DEFAULT_VIEW);
  useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setSize((s) => (Math.round(s.width) === Math.round(width) && Math.round(s.height) === Math.round(height) ? s : { width: Math.round(width), height: Math.round(height) }));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref]);
  return size;
}

function MappedView({ battery, map, methodId, facts }: { battery: BatteryWithMaps; map: ObjectMapArtifact; methodId: string; facts: ReactNode }) {
  const objects = useMemo(() => mapObjects(battery, map), [battery, map]);
  const links = useMemo(() => mapLinks(map), [map]);
  const [selected, setSelected] = useState<string | null>(objects[0]?.id ?? null);
  const [partner, setPartner] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [mode, setMode] = useState<"3d" | "top">("top");
  const [camera, setCamera] = useState<TerrainCamera>(INITIAL_CAMERA);
  const [showLinks, setShowLinks] = useState(true);
  const [labelsOnly, setLabelsOnly] = useState(false);
  const [orbit, setOrbit] = useState(false);
  const [rise, setRise] = useState(1);
  const area = useRef<HTMLDivElement>(null);
  const hud = useRef<HTMLDivElement>(null);
  const tools = useRef<HTMLDivElement>(null);
  const view = useViewSize(area);
  const [obstacles, setObstacles] = useState<Rect[]>([]);
  const drag = useRef<{ x: number; y: number; camera: TerrainCamera } | null>(null);
  const frame = useRef<number | null>(null);
  const move = useCallback((change: Partial<TerrainCamera>) => setCamera((c) => boundedCamera({ ...c, ...change })), []);

  // The panels over the map, in the map's own pixels, so labels keep clear of them.
  useLayoutEffect(() => {
    const box = area.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    const next = [hud.current, tools.current].flatMap((el) => {
      const r = el?.getBoundingClientRect();
      if (!r || r.width === 0 || r.bottom <= box.top || r.top >= box.bottom) return [];
      return [{ x: r.left - box.left - 6, y: r.top - box.top - 6, w: r.width + 12, h: r.height + 12 }];
    });
    setObstacles((o) => (JSON.stringify(o) === JSON.stringify(next) ? o : next));
  }, [view, mode, orbit, labelsOnly, showLinks]);

  // The opening animation: the relief rises from flat. A presentation effect, never data over time.
  const play = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    if (!canAnimate()) { setRise(1); return; }
    const start = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - start) / RISE_MS);
      setRise(progress);
      frame.current = progress < 1 ? requestAnimationFrame(step) : null;
    };
    setRise(0);
    frame.current = requestAnimationFrame(step);
  }, []);
  useEffect(() => () => { if (frame.current !== null) cancelAnimationFrame(frame.current); }, []);

  // Auto-rotation, while 3D is on and the reader asked for it.
  useEffect(() => {
    if (!orbit || mode !== "3d" || typeof window.requestAnimationFrame !== "function") return;
    let last = performance.now();
    let id = requestAnimationFrame(function turn(now: number) {
      setCamera((c) => ({ ...c, yaw: c.yaw + ((now - last) / ORBIT_MS) * 2 * Math.PI }));
      last = now;
      id = requestAnimationFrame(turn);
    });
    return () => cancelAnimationFrame(id);
  }, [orbit, mode]);

  // The wheel zooms the 3D camera; in top view it scrolls the page as usual.
  useEffect(() => {
    const node = area.current;
    if (!node || mode !== "3d") return;
    const onWheel = (e: WheelEvent) => { e.preventDefault(); setCamera((c) => boundedCamera({ ...c, zoom: c.zoom * (e.deltaY < 0 ? 1.08 : 1 / 1.08) })); };
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [mode]);

  const show3d = () => { setMode("3d"); play(); };
  const showTop = () => { setMode("top"); setOrbit(false); };
  const select = (id: string) => { if (id !== selected) { setSelected(id); setPartner(null); } };

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
    setOrbit(false);
    drag.current = { x: e.clientX, y: e.clientY, camera };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const start = drag.current;
    if (start) move({ yaw: start.camera.yaw + (e.clientX - start.x) / 180, elevation: start.camera.elevation - (e.clientY - start.y) / 240 });
  };

  const layout = map.layout!;
  const rating = battery.rating_scale;
  const chosen = objects.find((o) => o.id === selected) ?? null;
  const relations = chosen ? relationsOf(battery, map, chosen.id) : [];
  const pair = relations.find((r) => r.id === partner) ?? null;
  // The selected object's drawn relations -- a subset of `mapLinks`, never more.
  const shownLinks = !showLinks ? [] : selected ? links.filter((l) => l.a === selected || l.b === selected) : links;
  const linked = new Set(shownLinks.flatMap((l) => [l.a, l.b]));
  const dimmed = new Set(selected && showLinks ? objects.filter((o) => o.id !== selected && o.id !== partner && !linked.has(o.id)).map((o) => o.id) : []);
  const marks: MarkState = { selected, partner, hovered, dimmed, labelsOnly };
  const pill = (on: boolean) => `rounded-full border px-3 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--viz-stage-ink)] ${on ? "border-[var(--viz-stage-ink)] bg-[var(--viz-stage-ink)] text-[var(--viz-stage)]" : "border-white/20 bg-white/5 text-[var(--viz-stage-ink)] hover:bg-white/10"}`;

  return (
    <div className="flex flex-wrap items-start gap-4">
      <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-2 [min-width:min(100%,560px)]">
        <div className="relative overflow-hidden rounded-[10px] bg-[var(--viz-stage)] text-[var(--viz-stage-ink)] ring-1 ring-border" data-testid="object-map-stage">
          <div className="flex flex-wrap items-start justify-between gap-2 p-3 sm:pointer-events-none sm:absolute sm:inset-x-0 sm:top-0 sm:z-10 sm:p-3.5">
            <div ref={hud} className="flex flex-col gap-1.5 rounded-lg border border-white/10 bg-[var(--viz-stage-raised)]/90 px-3 py-2.5 text-[11px] leading-[14px]">
              <span className="text-xs font-semibold">{tv("research.exec.objectMap.hudTitle", { method: methodId })}</span>
              <span className="flex flex-wrap items-center gap-2" data-testid="object-map-fit">
                <span className="sr-only">{t("research.exec.objectMap.fit")}: </span>
                <span className={`rounded-full px-2 py-px font-semibold ${layout.quality === "weak" || layout.quality === "unreliable" ? "border border-[var(--viz-link-negative)] text-[var(--viz-link-negative)]" : "bg-[var(--viz-stage-ink)] text-[var(--viz-stage)]"}`}>
                  {t(`research.exec.objectMap.qualityBadge.${layout.quality}`)}
                </span>
                <span className="tabular-nums">{tv("research.exec.objectMap.stressValue", { value: num(layout.stress_1) })}</span>
              </span>
              <span className="tabular-nums text-[var(--viz-stage-muted)]">{tv("research.exec.objectMap.hudSupport", { placed: map.support.placed, respondents: map.support.respondents })}</span>
              {!layout.converged ? <span className="text-[var(--viz-link-negative)]">{t("research.exec.objectMap.notConverged")}</span> : null}
            </div>
            <div ref={tools} role="group" aria-label={t("research.exec.objectMap.controls")} className="flex flex-wrap justify-end gap-1.5 sm:pointer-events-auto sm:max-w-[52%]">
              <button type="button" className={pill(mode === "3d")} aria-pressed={mode === "3d"} aria-label={t("research.exec.objectMap.view3d")} disabled={map.terrain.status !== "computed"} onClick={show3d}>{t("research.exec.objectMap.view3dShort")}</button>
              <button type="button" className={pill(mode === "top")} aria-pressed={mode === "top"} aria-label={t("research.exec.objectMap.viewTop")} onClick={showTop}>{t("research.exec.objectMap.viewTopShort")}</button>
              <button type="button" className={pill(orbit)} aria-pressed={orbit} title={t("research.exec.objectMap.autoRotateHelp")} disabled={mode !== "3d"} onClick={() => setOrbit(!orbit)}>{t("research.exec.objectMap.autoRotate")}</button>
              <button type="button" className={pill(labelsOnly)} aria-pressed={labelsOnly} title={t("research.exec.objectMap.labelsOnlyHelp")} onClick={() => setLabelsOnly(!labelsOnly)}>{t("research.exec.objectMap.labelsOnly")}</button>
              <button type="button" className={pill(showLinks)} aria-pressed={showLinks} title={t("research.exec.objectMap.linksHelp")} onClick={() => setShowLinks(!showLinks)}>{t("research.exec.objectMap.links")}</button>
              <button type="button" className={pill(false)} title={t("research.exec.objectMap.replayHelp")} onClick={play}>{t("research.exec.objectMap.replay")}</button>
            </div>
          </div>
          <div ref={area}
            className={`relative aspect-[16/10] min-h-[320px] w-full touch-none select-none sm:min-h-[420px] focus:outline focus:outline-2 focus:-outline-offset-2 focus:outline-[var(--viz-stage-ink)] ${mode === "3d" ? "cursor-grab active:cursor-grabbing" : ""}`}
            role="region" aria-label={t("research.exec.objectMap.workspace")} tabIndex={0} onKeyDown={onKey}
            onPointerDown={onDown} onPointerMove={onMove} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
            {mode === "3d"
              ? <ObjectMapTerrain map={map} objects={objects} camera={camera} view={view} rise={rise} links={shownLinks} marks={marks} obstacles={obstacles} ratingScale={rating} onSelect={select} onHover={setHovered} />
              : <TopView battery={battery} map={map} objects={objects} view={view} rise={rise} links={shownLinks} marks={marks} obstacles={obstacles} ratingScale={rating} onSelect={select} onHover={setHovered} />}
          </div>
        </div>
        <Legend map={map} scale={rating} />
        {mode === "3d" ? (
          <div className="flex flex-col gap-1">
            <div className="flex flex-wrap items-center gap-2 text-xs" role="group" aria-label={t("research.exec.objectMap.cameraControls")}>
              <button type="button" className="rounded border border-border-strong bg-surface-raised px-2 py-1" onClick={() => move({ yaw: camera.yaw - Math.PI / 12 })}>{t("research.exec.sociomapping.rotateLeft")}</button>
              <button type="button" className="rounded border border-border-strong bg-surface-raised px-2 py-1" onClick={() => move({ yaw: camera.yaw + Math.PI / 12 })}>{t("research.exec.sociomapping.rotateRight")}</button>
              <button type="button" className="rounded border border-border-strong bg-surface-raised px-2 py-1" onClick={() => move({ zoom: camera.zoom * 1.15 })}>{t("research.exec.sociomapping.zoomIn")}</button>
              <button type="button" className="rounded border border-border-strong bg-surface-raised px-2 py-1" onClick={() => move({ zoom: camera.zoom / 1.15 })}>{t("research.exec.sociomapping.zoomOut")}</button>
              <button type="button" className="rounded border border-border-strong bg-surface-raised px-2 py-1" onClick={() => setCamera(INITIAL_CAMERA)}>{t("research.exec.sociomapping.reset")}</button>
              <label className="flex flex-wrap items-center gap-2">{t("research.exec.objectMap.relief")}<input type="range" min="0.5" max="2" step="0.1" value={camera.relief} onChange={(e) => move({ relief: Number(e.target.value) })} /><output>{num(camera.relief, 1)}×</output></label>
            </div>
            <p className="text-xs text-ink-muted">{t("research.exec.objectMap.cameraHelp")}</p>
            <p className="text-xs text-ink-muted">{t("research.exec.objectMap.referencePlane")}</p>
          </div>
        ) : null}
        <p className="text-xs text-ink-muted">{t("research.exec.objectMap.labelHelp")}</p>
        {map.terrain.status === "not_computed" ? <p className="text-xs text-ink-muted">{tv("research.exec.objectMap.noTerrain", { reason: map.terrain.reason })}</p> : null}
      </div>

      <aside className="grid min-w-0 flex-[1_1_300px] grid-cols-[repeat(auto-fit,minmax(min(100%,280px),1fr))] content-start gap-3.5">
        <div className="flex flex-col gap-2.5 rounded-[10px] border border-border bg-surface-raised p-4">
          <p className="text-xs text-ink-muted">{t("research.exec.objectMap.selectedTitle")}</p>
          <label className="flex flex-col gap-1 text-sm">
            {t("research.exec.objectMap.object")}
            <select className="rounded border border-border-strong bg-surface-raised px-2 py-1" value={selected ?? ""} onChange={(e) => select(e.target.value)}>
              {objects.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
            </select>
          </label>
          {chosen ? <Selected o={chosen} relations={relations} partner={partner} rating={rating} onPair={(id) => setPartner(id === partner ? null : id)} /> : null}
          {chosen && relations.length ? (
            <label className="flex flex-col gap-1 text-sm">{tv("research.exec.objectMap.compareWith", { label: chosen.label })}
              <select value={partner ?? ""} className="rounded border border-border-strong bg-surface-raised px-2 py-1" onChange={(e) => setPartner(e.target.value || null)}>
                <option value="">{t("research.exec.objectMap.compareNone")}</option>
                {relations.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
              </select>
            </label>
          ) : null}
          {chosen && pair ? <PairCard a={chosen} pair={pair} onClose={() => setPartner(null)} onSwap={() => { setSelected(pair.id); setPartner(chosen.id); }} /> : null}
        </div>
        <Ranked objects={objects} selected={selected} onSelect={select} onHover={setHovered} />
        <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4 text-sm" data-testid="object-map-reading">
          <h4 className="text-xs font-semibold">{t("research.exec.objectMap.readingTitle")}</h4>
          <p className="text-xs leading-[17px] text-ink-muted">{t("research.exec.objectMap.howToRead")}</p>
          <details className="text-xs leading-[17px]">
            <summary className="cursor-pointer font-medium">{t("research.exec.objectMap.readingMore")}</summary>
            <p className="mt-2">{tv("research.exec.objectMap.readingIntro", { title: battery.title })}</p>
            <p className="mt-2">{t("research.exec.objectMap.surfaceMeaning")}</p>
            <p className="mt-2">{t("research.exec.objectMap.distanceMeaning")}</p>
          </details>
          <p className="text-xs leading-[17px]">{t(`research.exec.objectMap.${layout.quality === "weak" || layout.quality === "unreliable" ? "weakFitMeaning" : "fitMeaning"}`)}</p>
          {facts}
        </div>
      </aside>
    </div>
  );
}

/** The top view: the stored cells as terraces, the band steps, the drawn links, the objects. */
function TopView({ battery, map, objects, view, rise, links, marks, obstacles, ratingScale, onSelect, onHover }: {
  battery: BatteryWithMaps; map: ObjectMapArtifact; objects: MapObject[]; view: ViewSize; rise: number;
  links: ReturnType<typeof mapLinks>; marks: MarkState; obstacles: Rect[]; ratingScale?: [number, number];
  onSelect: (id: string) => void; onHover: (id: string | null) => void;
}) {
  const cells = useMemo(() => terrainCells(map), [map]);
  const edges = useMemo(() => terraceEdges(map), [map]);
  const span = viewSpan(map);
  const at = new Map(objects.map((o) => [o.id, toScreen(o.x, o.y, span, view)]));
  const cellPx = cells.length ? cells[0].size * screenScale(span, view) : 0;
  const corner = toScreen(-span, span, span, view);
  const side = 2 * span * screenScale(span, view);
  const path = edges.map((e) => {
    const a = toScreen(e.x1, e.y1, span, view), b = toScreen(e.x2, e.y2, span, view);
    return `M${a.sx.toFixed(1)},${a.sy.toFixed(1)}L${b.sx.toFixed(1)},${b.sy.toFixed(1)}`;
  }).join("");
  const labels = layoutLabels(objects, at, marks, view, obstacles, ratingScale);
  return (
    <svg viewBox={`0 0 ${view.width} ${view.height}`} className="absolute inset-0 h-full w-full" role="group"
      aria-label={tv("research.exec.objectMap.mapLabel", { title: battery.title, n: objects.length })} data-testid="object-map-svg">
      <rect x={corner.sx} y={corner.sy} width={side} height={side} fill="var(--viz-ground)" rx={4} />
      <g data-testid="object-map-terrain" opacity={rise}>
        {cells.map((c, k) => {
          const p = toScreen(c.x, c.y, span, view);
          return <rect key={k} x={p.sx - cellPx / 2} y={p.sy - cellPx / 2} width={cellPx + 0.5} height={cellPx + 0.5} fill={TERRACE(c.band)} />;
        })}
      </g>
      <path d={path} fill="none" stroke="white" strokeOpacity={0.4 * rise} strokeWidth={1} data-testid="object-map-terraces" />
      <g aria-hidden="true">
        {links.map((l) => { const a = at.get(l.a)!, b = at.get(l.b)!; return <line key={l.a + l.b} x1={a.sx} y1={a.sy} x2={b.sx} y2={b.sy} {...casing(linkStyle(l, marks.partner).strokeWidth)} />; })}
      </g>
      <g data-testid="object-map-links">
        {links.map((l) => {
          const a = at.get(l.a)!, b = at.get(l.b)!;
          return <line key={`${l.a}|${l.b}`} data-pair={`${l.a}|${l.b}`} x1={a.sx} y1={a.sy} x2={b.sx} y2={b.sy} strokeLinecap="round" {...linkStyle(l, marks.partner)} />;
        })}
      </g>
      {objects.map((o) => {
        const p = at.get(o.id)!;
        return (
          <PinButton key={o.id} o={o} marks={marks} onSelect={onSelect} onHover={onHover}>
            <MapPin o={o} x={p.sx} y={p.sy} marks={marks} />
            <MapLabel o={o} {...labels.get(o.id)!} marks={marks} />
          </PinButton>
        );
      })}
    </svg>
  );
}

/** The selected object: its stored numbers, then its relations to every other object. */
function Selected({ o, relations, partner, rating, onPair }: {
  o: MapObject; relations: PairDetail[]; partner: string | null; rating?: [number, number]; onPair: (id: string) => void;
}) {
  const original = originalRating(o.height, rating);
  return (
    <div className="flex flex-col gap-2.5" data-testid="object-map-details">
      <div className="flex items-center gap-2.5">
        <span aria-hidden className="h-3.5 w-3.5 shrink-0 rounded-full ring-1 ring-black/30" style={{ background: o.band === null ? "var(--viz-ground)" : TERRACE(o.band) }} />
        <span className="text-lg font-semibold leading-6">{o.label}</span>
      </div>
      <span className="text-xs text-ink-muted"><span className="sr-only">{t("research.exec.objectMap.role")}: </span>{o.primary ? t("research.exec.objectMap.primary") : t("research.exec.objectMap.secondary")}</span>
      <dl className="flex flex-wrap gap-x-5 gap-y-2">
        <div className="flex flex-col-reverse"><dt className="text-[11px] text-ink-muted">{t("research.exec.objectMap.storedHeight")}</dt><dd className="text-[22px] font-semibold leading-7 tabular-nums">{num(o.height, 2)}</dd></div>
        {rating ? <div className="flex flex-col-reverse"><dt className="text-[11px] text-ink-muted">{tv("research.exec.objectMap.originalRating", { low: num(rating[0], 0), high: num(rating[1], 0) })}</dt><dd className="text-[22px] font-semibold leading-7 tabular-nums">{num(original, 2)}</dd></div> : null}
        <div className="flex flex-col-reverse"><dt className="text-[11px] text-ink-muted">{t("research.exec.objectMap.displayBand")}</dt><dd className="text-[22px] font-semibold leading-7 tabular-nums">{o.band === null ? "—" : tv("research.exec.objectMap.bandOf", { band: o.band + 1, bands: TERRACE_BANDS })}</dd></div>
      </dl>
      <p className="mt-1 text-xs font-semibold">{t("research.exec.objectMap.relationsHint")}</p>
      <ul className="flex flex-col gap-0.5">
        {relations.map((r) => {
          const strength = r.r === null ? 0 : Math.abs(r.r);
          const reliable = r.state === "reliable";
          return (
            <li key={r.id}>
              <button type="button" aria-pressed={partner === r.id} onClick={() => onPair(r.id)}
                className={`grid w-full grid-cols-[minmax(0,1fr)_64px_48px] items-center gap-x-2 rounded px-1.5 py-1 text-left text-xs ${partner === r.id ? "bg-signal-wash" : "hover:bg-surface-sunken"}`}>
                <span className="truncate">{r.label}</span>
                <span aria-hidden className="relative h-1.5 rounded-full bg-border">
                  <span className="absolute inset-y-0 rounded-full" style={{
                    left: r.r !== null && r.r < 0 ? `${50 - strength * 50}%` : "50%", width: `${strength * 50}%`,
                    background: !reliable ? "var(--ink-muted)" : r.r !== null && r.r < 0 ? "var(--viz-div-6)" : "var(--signal)", opacity: reliable ? 1 : 0.45,
                  }} />
                </span>
                <span className={`text-right tabular-nums ${r.drawn ? "" : "text-ink-muted"}`}>{r.r === null ? "—" : num(r.r, 2)}</span>
                <span className="col-span-3 text-[11px] leading-[14px] text-ink-muted">
                  {r.r === null ? `${t("research.exec.objectMap.undefinedR")} · ` : ""}{r.state ? t(`research.exec.objectMap.state.${r.state}`) : "—"}{r.drawn ? ` · ${t("research.exec.objectMap.drawn")}` : ""}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** One pair's stored evidence. The verdict tells an UNKNOWN estimate from an r never computed. */
function PairCard({ a, pair, onClose, onSwap }: { a: MapObject; pair: PairDetail; onClose: () => void; onSwap: () => void }) {
  const verdict = pair.r === null ? "pairUndefined"
    : pair.state === "unknown" || pair.state === null ? "pairUnknownEstimate"
    : pair.state === "weak" ? "pairWeak"
    : pair.r > 0 ? "pairPositive" : pair.r < 0 ? "pairNegative" : "pairZero";
  const support = pair.n === null ? "—" : pair.nEffective === null || pair.nEffective === pair.n
    ? tv("research.exec.objectMap.pairSupportValue", { n: pair.n })
    : tv("research.exec.objectMap.pairSupportEffective", { n: pair.n, effective: num(pair.nEffective, 1) });
  return (
    <div className="mt-1 flex flex-col gap-2 rounded-lg bg-[var(--viz-stage)] p-3 text-[var(--viz-stage-ink)] ring-1 ring-border" data-testid="object-map-pair" role="group" aria-label={tv("research.exec.objectMap.pairTitle", { a: a.label, b: pair.label })}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-[13px] font-semibold">{tv("research.exec.objectMap.pairTitle", { a: a.label, b: pair.label })}</span>
        <button type="button" onClick={onClose} aria-label={t("research.exec.objectMap.pairClose")} className="px-1.5 text-xs">✕</button>
      </div>
      <dl className="flex flex-wrap gap-x-4 gap-y-1 tabular-nums">
        <div className="flex flex-col-reverse"><dt className="text-[11px] text-[var(--viz-stage-muted)]">{t("research.exec.objectMap.pairR")}</dt><dd className="text-xl font-semibold leading-[26px]">{pair.r === null ? "—" : num(pair.r, 3)}</dd></div>
        <div className="flex flex-col-reverse"><dt className="text-[11px] text-[var(--viz-stage-muted)]">{t("research.exec.objectMap.pairState")}</dt><dd className="text-sm leading-[26px]">{pair.state ? t(`research.exec.objectMap.state.${pair.state}`) : "—"}</dd></div>
        <div className="flex flex-col-reverse"><dt className="text-[11px] text-[var(--viz-stage-muted)]">{t("research.exec.objectMap.pairSupport")}</dt><dd className="text-sm leading-[26px]">{support}</dd></div>
      </dl>
      {pair.interval ? <p className="text-xs tabular-nums">{tv("research.exec.objectMap.pairInterval", { level: num((pair.confidence ?? 0.95) * 100, 0), low: num(pair.interval[0], 2), high: num(pair.interval[1], 2) })}</p> : null}
      {pair.floor !== null ? <p className="text-xs">{tv("research.exec.objectMap.pairFloor", { floor: num(pair.floor, 2), result: t(`research.exec.objectMap.${pair.meetsFloor === true ? "pairFloorYes" : pair.meetsFloor === false ? "pairFloorNo" : "pairFloorNone"}`) })}</p> : null}
      <p className="text-xs leading-[17px]">{tv("research.exec.objectMap.pairValue", { a: a.label, b: pair.label, r: pair.r === null ? "—" : num(pair.r, 3) })} {t(`research.exec.objectMap.${verdict}`)}</p>
      <p className="text-[11px] leading-[15px] text-[var(--viz-stage-muted)]" data-testid="object-map-pair-why">{t(`research.exec.objectMap.why.${pair.why}`)}</p>
      <button type="button" onClick={onSwap} className="self-start rounded-full border border-white/20 bg-white/5 px-2.5 py-1 text-xs">{t("research.exec.objectMap.pairSwap")}</button>
    </div>
  );
}

/** Every object by stored height, highest first. */
function Ranked({ objects, selected, onSelect, onHover }: { objects: MapObject[]; selected: string | null; onSelect: (id: string) => void; onHover: (id: string | null) => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4" data-testid="object-map-ranked">
      <p className="text-xs font-semibold">{t("research.exec.objectMap.rankedTitle")}</p>
      <ol className="flex flex-col">
        {rankedByHeight(objects).map((o, k) => (
          <li key={o.id}>
            <button type="button" aria-pressed={o.id === selected} onClick={() => onSelect(o.id)} onPointerEnter={() => onHover(o.id)} onPointerLeave={() => onHover(null)}
              className={`grid w-full grid-cols-[18px_12px_minmax(0,1fr)_auto] items-center gap-2 rounded px-1.5 py-1 text-left text-xs ${o.id === selected ? "bg-signal-wash font-semibold" : "hover:bg-surface-sunken"}`}>
              <span className="tabular-nums text-ink-muted">{k + 1}</span>
              <span aria-hidden className="h-3 w-3 rounded-full" style={{ background: o.band === null ? "var(--viz-ground)" : TERRACE(o.band) }} />
              <span className="truncate">{o.primary ? o.label : tv("research.exec.objectMap.contextSuffix", { label: o.label })}</span>
              <span className="tabular-nums">{num(o.height, 2)}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Legend({ map, scale }: { map: ObjectMapArtifact; scale?: [number, number] }) {
  const label = legendLabel(scale);
  const floor = map.relations.effect_floor;
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2.5 rounded-[10px] bg-[var(--viz-stage)] px-3.5 py-2.5 ring-1 ring-border text-[11px] leading-[14px] text-[var(--viz-stage-ink)]">
      <div className="flex flex-col gap-1" aria-label={label} role="img">
        <span className="text-xs font-semibold">{t("research.exec.objectMap.legendTitle")}</span>
        <span className="flex items-end gap-0.5" aria-hidden>
          {Array.from({ length: TERRACE_BANDS }, (_, k) => <span key={k} className="inline-block w-[18px] rounded-t-sm" style={{ height: 6 + Math.round((22 * (k + 1)) / TERRACE_BANDS), background: TERRACE(k) }} />)}
        </span>
        <span className="flex justify-between gap-3 text-[var(--viz-stage-muted)]" aria-hidden>
          <span>{scale ? num(scale[0], 0) : "0"}</span><span>{scale ? num((scale[0] + scale[1]) / 2, 1) : num(0.5, 1)}</span><span>{scale ? num(scale[1], 0) : "1"}</span>
        </span>
      </div>
      <div className="flex flex-wrap gap-3 text-[var(--viz-stage-muted)]">
        <span className="flex items-center gap-1.5"><span aria-hidden className="h-3 w-3 rounded-sm bg-[var(--viz-ground)] ring-1 ring-white/20" />{t("research.exec.objectMap.legendGround")}</span>
        <span className="flex items-center gap-1.5"><span aria-hidden className="h-[3px] w-[18px] rounded-sm bg-[var(--viz-link-positive)]" />{t("research.exec.objectMap.legendPositive")}</span>
        <span className="flex items-center gap-1.5"><span aria-hidden className="w-[18px] border-t-[3px] border-dashed border-[var(--viz-link-negative)]" />{t("research.exec.objectMap.legendNegative")}</span>
        <span className="flex items-center gap-1.5"><span aria-hidden className="h-2 w-2 rotate-45 bg-[var(--viz-map-context)]" />{t("research.exec.objectMap.legendContext")}</span>
      </div>
      <div className="flex flex-col gap-1 text-[var(--viz-stage-muted)]">
        <span>{floor !== undefined ? tv("research.exec.objectMap.legendLinesFloor", { floor: num(floor, 2) }) : t("research.exec.objectMap.legendLines")}</span>
        <span>{t("research.exec.objectMap.legendBands")}</span>
      </div>
    </div>
  );
}

/** What the artifact says about its support, its pairs and itself; none of it recomputed. */
function Facts({ map, methodId, fingerprint, dataOrigin }: { map: ObjectMapArtifact; methodId: string; fingerprint: string; dataOrigin: string | null }) {
  const s = map.support;
  const c = map.status_counts;
  const hidden = belowFloor(map);
  return (
    <div className="flex flex-col gap-1 text-[11px] leading-[15px] text-ink-muted tabular-nums" data-testid="object-map-support">
      <p>{tv("research.exec.objectMap.statusLine", { reliable: c.reliable ?? 0, weak: c.weak ?? 0, unknown: c.unknown ?? 0 })}</p>
      <p>{t("research.exec.objectMap.unknownNote")}</p>
      <p>{tv("research.exec.objectMap.support", { placed: s.placed, respondents: s.respondents, effective: s.effective_n === null ? "—" : num(s.effective_n, 1) })}</p>
      <p data-testid="object-map-not-placed">{tv("research.exec.objectMap.notPlaced", { count: s.not_placed })}</p>
      {hidden && map.relations.effect_floor !== undefined ? <p>{tv("research.exec.objectMap.belowFloor", { floor: num(map.relations.effect_floor, 2), count: hidden })}</p> : null}
      {map.spec.terrain ? <p>{tv("research.exec.objectMap.provisional", { sigma: num(map.spec.terrain.sigma, 2) })}</p> : null}
      {dataOrigin ? <p className="text-status-fault">{tv("research.exec.objectMap.synthetic", { origin: dataOrigin })}</p> : null}
      <p data-testid="object-map-method">{tv("research.exec.objectMap.method", { method: map.spec.methodology_version || methodId, fingerprint: fingerprint.slice(0, 12) })}</p>
    </div>
  );
}
