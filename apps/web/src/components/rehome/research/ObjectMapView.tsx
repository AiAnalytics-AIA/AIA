"use client";

// The audit's object map on the Results page (plan sociomap-formula-corrections chunk 5a),
// built to the approved design (plan object-map-3d-redesign; the standalone prototype is its
// visual acceptance specification, chunk 6, checklist V1-V25).
//
// Renders the stored contract-3 artifact only: positions, Stress-1, pair states, heights and
// the envelope terrain come from the worker, and this view never computes or adjusts them.
// From above (the default): the stored terrain as ten flat display terraces on the absolute
// 0-1 scale, the selected object's drawn relations (the one `mapLinks` rule), each object at
// its stored place. 3D is explicitly activated by the reader; top view unmounts it and is its
// immediate kill switch. Relief, camera, rotation and the opening choreography are
// presentation state. The map is internal while D6 is open.

import { type KeyboardEvent, type PointerEvent, type ReactNode, type RefObject, useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { boundedCamera, easeOut, INITIAL_CAMERA, terraceLayers, TOP_CAMERA, type TerrainCamera } from "@/lib/object-map-3d";
import { ObjectMapTerrain } from "./ObjectMapTerrain";
import { type MarkState, LabelShadow, MapLabel, MapPin, PinButton, TERRACE, casing, fmt, layoutLabels, legendLabel, linkStyle, partialCurve } from "./ObjectMapMarks";

import { t, tv } from "@/i18n/t";
import {
  type BatteryWithMaps,
  type Frame,
  type MapLink,
  type MapObject,
  type ObjectMapArtifact,
  type PairDetail,
  type Rect,
  type ViewSize,
  TERRACE_BANDS,
  belowFloor,
  frameScale,
  frameToScreen,
  mapFrame,
  mapLinks,
  mapObjects,
  originalRating,
  rankedByHeight,
  readObjectMap,
  relationsOf,
  resolveVars,
  type RegisterEntry,
} from "@/lib/object-map-view";
import { num } from "@/lib/sociomapping-view";
import { type OriginKind, originKind } from "@/lib/research-execution";

/** The chip and the sentence each origin kind says on the map; an unknown origin is never real. */
const ORIGIN_CHIP: Record<OriginKind, { chip: string; text: string; className: string; dot: string }> = {
  SIMULATED: { chip: "research.exec.objectMap.syntheticChip", text: "research.exec.objectMap.synthetic", className: "border-status-fault text-status-fault", dot: "bg-status-fault" },
  MODELLED: { chip: "research.exec.objectMap.modelledChip", text: "research.exec.objectMap.modelled", className: "border-ink text-ink", dot: "bg-ink" },
  UNKNOWN: { chip: "research.exec.objectMap.unknownChip", text: "research.exec.objectMap.unknown", className: "border-status-fault text-status-fault", dot: "bg-status-fault" },
};

/** The stage's size before it is measured (and in tests, where nothing is laid out). */
const DEFAULT_VIEW: ViewSize = { width: 964, height: 602 };
/** The approved design's choreography, in milliseconds. */
const MOTION = { rise: 1600, pinsAt: 900, pinStep: 60, pin: 600, labelsAt: 1350, labels: 250, arc: 700, glide: 900, orbit: 75000 };

const prefersReducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches === true;
const canAnimate = () => typeof window !== "undefined" && typeof window.requestAnimationFrame === "function" && !prefersReducedMotion();
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

export function ObjectMapView({ battery, dataOrigin, approvalOf }: {
  battery: BatteryWithMaps;
  dataOrigin: string | null;
  /** The register's approval of the map stored under a method id; absent or null is internal. */
  approvalOf?: (methodId: string) => RegisterEntry | null;
}) {
  const read = readObjectMap(battery);
  if (!read.ok) {
    return read.reason === "contract" ? <p role="alert" className="text-sm text-status-fault">{t("research.exec.objectMap.unreadable")}</p> : null;
  }
  const { map, methodId, fingerprint } = read;
  const approval = approvalOf?.(methodId) ?? null;
  const kind = originKind(dataOrigin);
  const origin = ORIGIN_CHIP[kind];
  const originText = tv(origin.text, { origin: dataOrigin ?? "—" });
  const facts = <Facts map={map} title={battery.title} methodId={methodId} fingerprint={fingerprint} originText={originText} />;
  return (
    <section aria-label={battery.title} className="flex flex-col gap-4 text-sm leading-5" data-testid={`object-map-${battery.battery_id}`}>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-xs text-ink-muted">{tv("research.exec.objectMap.title", { method: methodId })}</p>
          <h3 className="text-2xl font-semibold leading-[30px]">{battery.title}</h3>
        </div>
        <p className="text-xs text-ink-muted">{t("research.exec.objectMap.hint")}</p>
      </header>
      <div className="flex flex-wrap gap-2 text-xs">
        {approval ? (
          <span title={approval.reader_note} data-testid="object-map-approval" className="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-ink">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-ink" />{t("research.exec.objectMap.approvedChip")}
          </span>
        ) : (
          <span title={t("research.exec.results.internal")} className="inline-flex items-center gap-1.5 rounded-full bg-status-world-wash px-2.5 py-1 text-ink">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-ink" />{t("research.exec.objectMap.internalChip")}
          </span>
        )}
        <span title={originText} data-testid="object-map-origin" data-origin-kind={kind} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${origin.className}`}>
          <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${origin.dot}`} />{t(origin.chip)}
        </span>
      </div>
      {map.outcome === "MAPPED" && map.layout ? (
        <MappedView approved={approval !== null} key={fingerprint} battery={battery} map={map} methodId={methodId} fingerprint={fingerprint} facts={facts} />
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

type Cue = "open" | "links" | "glide";

/**
 * The approved design's choreography as one clock: the opening (terraces rise, pins pop in
 * turn, labels appear), an arc drawing itself in after a selection, the glide into 3D. Each
 * cue starts at a time; while any runs the clock ticks, then every cue reads as finished.
 * Under reduced motion, or without animation frames, nothing runs and everything is final.
 */
function useChoreography() {
  const [cues, setCues] = useState<Record<Cue, number | null>>({ open: null, links: null, glide: null });
  const [now, setNow] = useState(0);
  const cue = useCallback((...kinds: Cue[]) => {
    if (!canAnimate()) return;
    const at = performance.now();
    setNow(at);
    setCues((c) => ({ ...c, ...Object.fromEntries(kinds.map((k) => [k, at])) }));
  }, []);
  useEffect(() => {
    const ends = [cues.open !== null && cues.open + MOTION.pinsAt + 12 * MOTION.pinStep + MOTION.pin, cues.links !== null && cues.links + MOTION.arc, cues.glide !== null && cues.glide + MOTION.glide].filter((v): v is number => typeof v === "number");
    if (!ends.length) return;
    const end = Math.max(...ends);
    let id = requestAnimationFrame(function tick(time: number) {
      setNow(time);
      if (time < end) id = requestAnimationFrame(tick);
      else setCues({ open: null, links: null, glide: null });
    });
    return () => cancelAnimationFrame(id);
  }, [cues]);
  const since = (k: Cue) => (cues[k] === null ? Infinity : now - cues[k]!);
  return { cue, since };
}

function MappedView({ battery, map, methodId, fingerprint, facts, approved }: { battery: BatteryWithMaps; map: ObjectMapArtifact; methodId: string; fingerprint: string; facts: ReactNode; approved: boolean }) {
  const objects = useMemo(() => mapObjects(battery, map), [battery, map]);
  const links = useMemo(() => mapLinks(map), [map]);
  const frame = useMemo(() => mapFrame(map, objects), [map, objects]);
  const [selected, setSelected] = useState<string | null>(objects[0]?.id ?? null);
  const [partner, setPartner] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [mode, setMode] = useState<"3d" | "top">("top");
  const [camera, setCamera] = useState<TerrainCamera>(INITIAL_CAMERA);
  const [showLinks, setShowLinks] = useState(true);
  const [labelsOnly, setLabelsOnly] = useState(false);
  const [orbit, setOrbit] = useState(false);
  const area = useRef<HTMLDivElement>(null);
  const hud = useRef<HTMLDivElement>(null);
  const tools = useRef<HTMLDivElement>(null);
  const caption = useRef<HTMLParagraphElement>(null);
  const view = useViewSize(area);
  const [obstacles, setObstacles] = useState<Rect[]>([]);
  const drag = useRef<{ x: number; y: number; camera: TerrainCamera } | null>(null);
  const { cue, since } = useChoreography();
  const move = useCallback((change: Partial<TerrainCamera>) => setCamera((c) => boundedCamera({ ...c, ...change })), []);

  // The opening plays once the map is on screen.
  useEffect(() => { cue("open", "links"); }, [cue]);

  // The panels over the map, in the map's own pixels, so labels keep clear of them.
  useLayoutEffect(() => {
    const box = area.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    const next = [hud.current, tools.current, caption.current].flatMap((el) => {
      const r = el?.getBoundingClientRect();
      if (!r || r.width === 0 || r.bottom <= box.top || r.top >= box.bottom) return [];
      return [{ x: r.left - box.left - 6, y: r.top - box.top - 6, w: r.width + 12, h: r.height + 12 }];
    });
    setObstacles((o) => (JSON.stringify(o) === JSON.stringify(next) ? o : next));
  }, [view, mode, orbit, labelsOnly, showLinks, selected]);

  // Auto-rotation, while 3D is on and the reader asked for it (the design's slow orbit).
  useEffect(() => {
    if (!orbit || mode !== "3d" || typeof window.requestAnimationFrame !== "function") return;
    let last = performance.now();
    let id = requestAnimationFrame(function turn(now: number) {
      setCamera((c) => ({ ...c, yaw: c.yaw + ((now - last) / MOTION.orbit) * 2 * Math.PI }));
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

  const show3d = () => { if (mode !== "3d") { setMode("3d"); cue("glide"); } };
  const showTop = () => { setMode("top"); setOrbit(false); };
  const toggleOrbit = () => { if (mode !== "3d") show3d(); setOrbit(!orbit); };
  const select = (id: string) => { if (id !== selected) { setSelected(id); setPartner(null); cue("links"); } };
  const pairWith = (id: string | null) => { setPartner(id); cue("links"); };

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
    if (mode !== "3d" || e.button !== 0 || (e.target as Element).closest('[role="button"], button')) return;
    setOrbit(false);
    drag.current = { x: e.clientX, y: e.clientY, camera };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const start = drag.current;
    if (start) move({ yaw: start.camera.yaw + (e.clientX - start.x) / 180, elevation: start.camera.elevation - (e.clientY - start.y) / 240 });
  };

  // The choreography's state at this frame.
  const rise = easeOut(since("open") / MOTION.rise);
  const pop = (k: number) => easeOut((since("open") - MOTION.pinsAt - k * MOTION.pinStep) / MOTION.pin);
  const labelOpacity = clamp01((since("open") - MOTION.labelsAt) / MOTION.labels);
  const reveal = rise >= 0.95 ? easeOut(since("links") / MOTION.arc) : 0;
  const glide = easeOut(since("glide") / MOTION.glide);
  const shown: TerrainCamera = glide >= 1 ? camera : {
    yaw: TOP_CAMERA.yaw + (camera.yaw - TOP_CAMERA.yaw) * glide,
    elevation: TOP_CAMERA.elevation + (camera.elevation - TOP_CAMERA.elevation) * glide,
    zoom: camera.zoom, relief: camera.relief,
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
  const pill = (on: boolean) => `cursor-pointer rounded-full border border-white/[.18] px-[11px] py-[5px] text-xs leading-4 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--viz-stage-ink)] ${on ? "bg-[var(--viz-stage-ink)] text-[var(--viz-stage)]" : "bg-white/[.06] text-[var(--viz-stage-ink)] hover:bg-white/[.12]"}`;
  const snapshot = () => void saveSnapshot(area.current, snapshotNaming(approved, methodId, fingerprint));

  return (
    <div className="flex flex-wrap items-start gap-4">
      <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-2 [min-width:min(100%,560px)] lg:sticky lg:top-4 lg:z-[1]">
        <div className="ring-1 ring-inset ring-white/[.07] relative aspect-[16/10] min-h-[420px] w-full overflow-hidden rounded-[10px] bg-[var(--viz-stage)] text-[var(--viz-stage-ink)]" data-testid="object-map-stage"
          style={{ backgroundImage: "radial-gradient(ellipse 70% 60% at 50% 48%, rgba(255,255,255,0.035), transparent 72%)" }}>
          <div ref={area}
            className={`absolute inset-0 touch-none select-none focus:outline focus:outline-2 focus:-outline-offset-2 focus:outline-[var(--viz-stage-ink)] ${mode === "3d" ? "cursor-grab active:cursor-grabbing" : ""}`}
            role="region" aria-label={t("research.exec.objectMap.workspace")} tabIndex={0} onKeyDown={onKey}
            onPointerDown={onDown} onPointerMove={onMove} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
            {mode === "3d"
              ? <ObjectMapTerrain map={map} objects={objects} camera={camera} shown={shown} frame={frame} view={view} rise={rise} pop={pop} labels={labelOpacity} reveal={reveal} links={shownLinks} marks={marks} obstacles={obstacles} ratingScale={rating} onSelect={select} onHover={setHovered} />
              : <TopView battery={battery} map={map} objects={objects} frame={frame} view={view} rise={rise} pop={pop} labels={labelOpacity} reveal={reveal} links={shownLinks} marks={marks} obstacles={obstacles} ratingScale={rating} onSelect={select} onHover={setHovered} />}
          </div>
          <div ref={hud} className="pointer-events-none absolute left-3.5 top-3.5 flex max-w-[calc(50%-21px)] flex-col gap-1.5 rounded-lg border border-white/[.12] bg-[rgba(20,23,28,0.72)] px-3 py-2.5 text-[11px] leading-[14px] sm:max-w-none">
            <span className="text-xs font-semibold">{tv("research.exec.objectMap.hudTitle", { method: methodId })}</span>
            {layout.quality !== undefined && layout.stress_1 !== undefined ? (
              <span className="flex flex-wrap items-center gap-2" data-testid="object-map-fit">
                <span className="sr-only">{t("research.exec.objectMap.fit")}: </span>
                <span className="rounded-full px-[7px] py-px font-semibold text-[var(--viz-stage)]" style={{ background: `var(--viz-fit-${layout.quality})` }}>
                  {t(`research.exec.objectMap.qualityBadge.${layout.quality}`)}
                </span>
                <span className="tabular-nums">{tv("research.exec.objectMap.stressValue", { value: num(layout.stress_1) })}</span>
              </span>
            ) : null}
            <span className="tabular-nums text-[var(--viz-stage-muted)]">{tv("research.exec.objectMap.hudSupport", { placed: map.support.placed, respondents: map.support.respondents })}</span>
            {!layout.converged ? <span className="text-[var(--viz-link-negative)]">{t("research.exec.objectMap.notConverged")}</span> : null}
          </div>
          <div ref={tools} role="group" aria-label={t("research.exec.objectMap.controls")} className="absolute right-3.5 top-3.5 flex max-w-[50%] flex-wrap justify-end gap-1.5">
            <button type="button" className={pill(mode === "3d")} aria-pressed={mode === "3d"} aria-label={t("research.exec.objectMap.view3d")} disabled={map.terrain.status !== "computed"} onClick={show3d}>{t("research.exec.objectMap.view3dShort")}</button>
            <button type="button" className={pill(mode === "top")} aria-pressed={mode === "top"} aria-label={t("research.exec.objectMap.viewTop")} onClick={showTop}>{t("research.exec.objectMap.viewTopShort")}</button>
            <button type="button" className={pill(orbit)} aria-pressed={orbit} title={t("research.exec.objectMap.autoRotateHelp")} disabled={map.terrain.status !== "computed"} onClick={toggleOrbit}>{t("research.exec.objectMap.autoRotate")}</button>
            <button type="button" className={pill(labelsOnly)} aria-pressed={labelsOnly} title={t("research.exec.objectMap.labelsOnlyHelp")} onClick={() => setLabelsOnly(!labelsOnly)}>{t("research.exec.objectMap.labelsOnly")}</button>
            <button type="button" className={pill(showLinks)} aria-pressed={showLinks} title={t("research.exec.objectMap.linksHelp")} onClick={() => { setShowLinks(!showLinks); cue("links"); }}>{t("research.exec.objectMap.links")}</button>
            <button type="button" className={pill(false)} title={t("research.exec.objectMap.replayHelp")} onClick={() => cue("open", "links")}>{t("research.exec.objectMap.replay")}</button>
          </div>
          {/* Which relations the lines are: a reader who clicks another object sees the network change and why. */}
          <p ref={caption} aria-live="polite" data-testid="object-map-links-caption"
            className="pointer-events-none absolute bottom-3.5 left-3.5 max-w-[calc(100%-28px)] rounded-lg border border-white/[.12] bg-[rgba(20,23,28,0.72)] px-2.5 py-1.5 text-[11px] leading-[14px] text-[var(--viz-stage-muted)]">
            {!showLinks ? t("research.exec.objectMap.linksHidden")
              : chosen && shownLinks.length ? tv("research.exec.objectMap.linksFor", { label: chosen.label, count: shownLinks.length })
              : chosen ? tv("research.exec.objectMap.linksNone", { label: chosen.label }) : null}
          </p>
        </div>
        <Legend map={map} scale={rating} />
        {mode === "3d" ? (
          <details className="text-xs text-ink-muted">
            <summary className="cursor-pointer">{t("research.exec.objectMap.cameraDisclosure")}</summary>
            <div className="mt-2 flex flex-wrap items-center gap-2" role="group" aria-label={t("research.exec.objectMap.cameraControls")}>
              {([
                [t("research.exec.sociomapping.rotateLeft"), () => move({ yaw: camera.yaw - Math.PI / 12 })],
                [t("research.exec.sociomapping.rotateRight"), () => move({ yaw: camera.yaw + Math.PI / 12 })],
                [t("research.exec.sociomapping.zoomIn"), () => move({ zoom: camera.zoom * 1.15 })],
                [t("research.exec.sociomapping.zoomOut"), () => move({ zoom: camera.zoom / 1.15 })],
                [t("research.exec.sociomapping.reset"), () => setCamera(INITIAL_CAMERA)],
              ] as [string, () => void][]).map(([label, act]) => <button key={label} type="button" className="rounded-full border border-border-strong bg-surface-raised px-3 py-1 text-ink" onClick={act}>{label}</button>)}
              <label className="flex flex-wrap items-center gap-2">{t("research.exec.objectMap.relief")}<input type="range" min="0.5" max="2" step="0.1" value={camera.relief} onChange={(e) => move({ relief: Number(e.target.value) })} /><output>{num(camera.relief, 1)}×</output></label>
            </div>
            <p className="mt-2">{t("research.exec.objectMap.cameraHelp")}</p>
            <p className="mt-1">{t("research.exec.objectMap.referencePlane")}</p>
          </details>
        ) : null}
        {map.terrain.status === "not_computed" ? <p className="text-xs text-ink-muted">{tv("research.exec.objectMap.noTerrain", { reason: map.terrain.reason })}</p> : null}
      </div>

      <aside className="grid min-w-0 flex-[1_1_300px] grid-cols-[repeat(auto-fit,minmax(min(100%,280px),1fr))] content-start gap-3.5">
        <div className="flex flex-col gap-2.5 rounded-[10px] border border-border bg-surface-raised p-4">
          <p className="text-xs text-ink-muted">{t("research.exec.objectMap.selectedTitle")}</p>
          {chosen ? <Selected o={chosen} relations={relations} partner={partner} rating={rating} onPair={(id) => pairWith(id === partner ? null : id)} /> : null}
          {chosen && pair ? <PairCard a={chosen} pair={pair} onClose={() => pairWith(null)} onSwap={() => { setSelected(pair.id); setPartner(chosen.id); cue("links"); }} /> : null}
        </div>
        <Ranked objects={objects} selected={selected} hovered={hovered} onSelect={select} onHover={setHovered} />
        <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4" data-testid="object-map-reading">
          <h4 className="text-xs font-semibold">{t("research.exec.objectMap.readingTitle")}</h4>
          <p className="text-xs leading-[17px] text-ink-muted">{t("research.exec.objectMap.howToRead")}</p>
          {facts}
          <button type="button" onClick={snapshot} className="mt-1 self-start rounded-full border border-border-strong bg-surface-raised px-3 py-1.5 text-xs text-ink">{t("research.exec.objectMap.snapshot")}</button>
        </div>
      </aside>
    </div>
  );
}

/** The top view: the framed plinth, the stored terrain as flat terraces with a light rim and a
 * soft shadow at each step, the drawn links, the objects with their rings and labels. */
function TopView({ battery, map, objects, frame, view, rise, pop, labels: labelOpacity, reveal, links, marks, obstacles, ratingScale, onSelect, onHover }: {
  battery: BatteryWithMaps; map: ObjectMapArtifact; objects: MapObject[]; frame: Frame; view: ViewSize; rise: number;
  pop: (k: number) => number; labels: number; reveal: number;
  links: MapLink[]; marks: MarkState; obstacles: Rect[]; ratingScale?: [number, number];
  onSelect: (id: string) => void; onHover: (id: string | null) => void;
}) {
  const shadow = `omtop${useId().replace(/:/g, "")}`;
  const layers = useMemo(() => terraceLayers(map), [map]);
  const k = frameScale(frame, view);
  const toS = (x: number, y: number) => frameToScreen(x, y, frame, view);
  const paths = useMemo(() => layers.map((layer) => ({
    band: layer.band,
    fill: layer.pieces.map((piece) => piece.map((p, i) => { const s = frameToScreen(p.x, p.y, frame, view); return `${i ? "L" : "M"}${s.sx.toFixed(1)},${s.sy.toFixed(1)}`; }).join("") + "Z").join(""),
    rim: layer.edges.map((e) => { const a = frameToScreen(e.a.x, e.a.y, frame, view), b = frameToScreen(e.b.x, e.b.y, frame, view); return `M${a.sx.toFixed(1)},${a.sy.toFixed(1)}L${b.sx.toFixed(1)},${b.sy.toFixed(1)}`; }).join(""),
  })), [layers, frame, view]);
  const at = new Map(objects.map((o) => [o.id, toS(o.x, o.y)]));
  const marked = { ...marks, shadow };
  const placed = layoutLabels(objects, at, marked, view, obstacles, ratingScale);
  const corner = toS(frame.cx - frame.half, frame.cy + frame.half);
  const side = 2 * frame.half * k;
  const rim = side * 0.02;
  return (
    <svg viewBox={`0 0 ${view.width} ${view.height}`} className="absolute inset-0 h-full w-full" role="group"
      aria-label={tv("research.exec.objectMap.mapLabel", { title: battery.title, n: objects.length })} data-testid="object-map-svg">
      <LabelShadow id={shadow} />
      <rect x={corner.sx - rim} y={corner.sy - rim} width={side + 2 * rim} height={side + 2 * rim} fill="var(--viz-stage-raised)" stroke="white" strokeOpacity={0.16} filter={`url(#${shadow})`} />
      <rect x={corner.sx} y={corner.sy} width={side} height={side} fill="var(--viz-ground)" />
      <g data-testid="object-map-terrain">
        {paths.map((p) => {
          // The terraces build up from the base during the opening.
          const show = clamp01(rise * TERRACE_BANDS - p.band * 0.6);
          return (
            <g key={p.band} opacity={show} data-band={p.band}>
              <path d={p.fill} fill="black" fillOpacity={0.3} transform="translate(1.6 2.2)" />
              {p.band > 0 ? <path d={p.fill} fill="white" fillOpacity={0.14} transform="translate(-0.9 -1.1)" /> : null}
              <path d={p.fill} fill={TERRACE(p.band)} />
              {p.band > 0 ? <path d={p.rim} fill="none" stroke="white" strokeOpacity={0.38} strokeWidth={1} /> : null}
            </g>
          );
        })}
      </g>
      <g aria-hidden="true">
        {links.map((l) => { const a = at.get(l.a)!, b = at.get(l.b)!; return <path key={l.a + l.b} d={partialCurve(a, { sx: (a.sx + b.sx) / 2, sy: (a.sy + b.sy) / 2 }, b, reveal)} fill="none" {...casing(linkStyle(l, marks.partner).strokeWidth)} />; })}
      </g>
      <g data-testid="object-map-links">
        {links.map((l) => {
          const a = at.get(l.a)!, b = at.get(l.b)!;
          return <path key={`${l.a}|${l.b}`} data-pair={`${l.a}|${l.b}`} d={partialCurve(a, { sx: (a.sx + b.sx) / 2, sy: (a.sy + b.sy) / 2 }, b, reveal)} fill="none" strokeLinecap="round" {...linkStyle(l, marks.partner)} />;
        })}
      </g>
      {objects.map((o, i) => {
        const p = at.get(o.id)!;
        return (
          <PinButton key={o.id} o={o} marks={marked} onSelect={onSelect} onHover={onHover}>
            <MapPin o={o} x={p.sx} y={p.sy} marks={marked} pop={pop(i)} ring={{ x: p.sx, y: p.sy, flat: 1 }} />
            <g opacity={labelOpacity}><MapLabel o={o} {...placed.get(o.id)!} marks={marked} /></g>
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
  const stat = "flex flex-col";
  const value = "text-[22px] font-semibold leading-7 tabular-nums";
  const caption = "text-[11px] leading-[14px] text-ink-muted";
  return (
    <div className="flex flex-col gap-2.5" data-testid="object-map-details">
      <div className="flex items-center gap-2.5">
        <span aria-hidden className="h-3.5 w-3.5 shrink-0 rounded-full shadow-[0_0_0_1px_rgba(15,18,22,0.3)]" style={{ background: o.band === null ? "var(--viz-ground)" : TERRACE(o.band) }} />
        <span className="text-lg font-semibold leading-6">{o.label}</span>
      </div>
      <span className="text-xs text-ink-muted"><span className="sr-only">{t("research.exec.objectMap.role")}: </span>{o.primary ? t("research.exec.objectMap.primary") : t("research.exec.objectMap.secondary")}</span>
      <dl className="flex gap-5">
        <div className={stat}><dd className={value}>{fmt(o.height, 2)}</dd><dt className={caption}>{t("research.exec.objectMap.storedHeight")}</dt></div>
        {rating ? <div className={stat}><dd className={value}>{fmt(original, 1)}</dd><dt className={caption}>{tv("research.exec.objectMap.scaleValue", { low: num(rating[0], 0), high: num(rating[1], 0) })}</dt></div> : null}
        <div className={stat}><dd className={value}>{o.band === null ? "—" : tv("research.exec.objectMap.bandOf", { band: o.band + 1, bands: TERRACE_BANDS })}</dd><dt className={caption}>{t("research.exec.objectMap.displayBand")}</dt></div>
      </dl>
      <p className="mt-1.5 text-xs font-semibold">{t("research.exec.objectMap.relationsHint")}</p>
      <ul className="flex flex-col gap-0.5">
        {relations.map((r) => {
          const strength = r.r === null ? 0 : Math.abs(r.r);
          const reliable = r.state === "reliable";
          return (
            <li key={r.id}>
              <button type="button" aria-pressed={partner === r.id} onClick={() => onPair(r.id)}
                className={`grid w-full grid-cols-[minmax(0,1fr)_64px_40px] items-center gap-x-2 rounded px-1.5 py-1 text-left text-xs ${partner === r.id ? "bg-signal-wash" : "hover:bg-surface-sunken"}`}>
                <span className="truncate">{r.label}</span>
                <span aria-hidden className="relative h-1.5 rounded-full bg-border">
                  <span className="absolute inset-y-0 rounded-full" style={{
                    left: r.r !== null && r.r < 0 ? `${50 - strength * 50}%` : "50%", width: `${strength * 50}%`,
                    background: !reliable ? "var(--ink-muted)" : r.r !== null && r.r < 0 ? "var(--viz-terrace-9)" : "var(--signal)", opacity: reliable ? 1 : 0.45,
                  }} />
                </span>
                <span className={`text-right tabular-nums ${r.drawn ? "" : "text-ink-muted"}`}>{fmt(r.r, 2)}</span>
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
  const caption = "text-[11px] text-[var(--viz-stage-muted)]";
  const evidence = [
    pair.nEffective !== null && pair.n !== null && pair.nEffective !== pair.n ? tv("research.exec.objectMap.pairEffective", { effective: num(pair.nEffective, 1) }) : null,
    pair.interval ? tv("research.exec.objectMap.pairInterval", { level: num((pair.confidence ?? 0.95) * 100, 0), low: fmt(pair.interval[0], 2), high: fmt(pair.interval[1], 2) }) : null,
    pair.floor !== null ? tv("research.exec.objectMap.pairFloor", { floor: num(pair.floor, 2), result: t(`research.exec.objectMap.${pair.meetsFloor === true ? "pairFloorYes" : pair.meetsFloor === false ? "pairFloorNo" : "pairFloorNone"}`) }) : null,
    pair.drawn ? t("research.exec.objectMap.pairDrawn") : null,
  ].filter(Boolean);
  return (
    <div className="ring-1 ring-inset ring-white/[.07] mt-1 flex flex-col gap-2 rounded-lg bg-[var(--viz-stage)] p-3 text-[var(--viz-stage-ink)]" data-testid="object-map-pair" role="group" aria-label={tv("research.exec.objectMap.pairTitle", { a: a.label, b: pair.label })}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-[13px] font-semibold">{tv("research.exec.objectMap.pairTitle", { a: a.label, b: pair.label })}</span>
        <button type="button" onClick={onClose} aria-label={t("research.exec.objectMap.pairClose")} className="px-1.5 text-xs">✕</button>
      </div>
      <dl className="flex gap-4 tabular-nums">
        <div className="flex flex-col"><dd className="text-xl font-semibold leading-[26px]" data-testid="object-map-pair-r">{fmt(pair.r, 3)}</dd><dt className={caption}>{t("research.exec.objectMap.pairR")}</dt></div>
        <div className="flex flex-col"><dd className="text-sm leading-[26px]">{pair.state ? t(`research.exec.objectMap.state.${pair.state}`) : "—"}</dd><dt className={caption}>{t("research.exec.objectMap.pairState")}</dt></div>
        <div className="flex flex-col"><dd className="text-sm leading-[26px]">{pair.n === null ? "n = —" : tv("research.exec.objectMap.pairSupportValue", { n: pair.n })}</dd><dt className={caption}>{t("research.exec.objectMap.pairSupport")}</dt></div>
      </dl>
      {evidence.length ? <p className={`${caption} leading-[15px] tabular-nums`} data-testid="object-map-pair-evidence">{evidence.join(" · ")}</p> : null}
      <p className="text-xs leading-[17px] [text-wrap:pretty]">{t(`research.exec.objectMap.${verdict}`)}</p>
      {!pair.drawn ? <p className={`${caption} leading-[15px]`} data-testid="object-map-pair-why">{t(`research.exec.objectMap.why.${pair.why}`)}</p> : null}
      <button type="button" onClick={onSwap} className="self-start rounded-full border border-white/20 bg-white/[.06] px-2.5 py-1 text-xs">{t("research.exec.objectMap.pairSwap")}</button>
    </div>
  );
}

/** Every object by stored height, highest first. */
function Ranked({ objects, selected, hovered, onSelect, onHover }: { objects: MapObject[]; selected: string | null; hovered: string | null; onSelect: (id: string) => void; onHover: (id: string | null) => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4" data-testid="object-map-ranked">
      <p className="text-xs font-semibold">{t("research.exec.objectMap.rankedTitle")}</p>
      <ol className="flex flex-col">
        {rankedByHeight(objects).map((o, k) => (
          <li key={o.id}>
            <button type="button" aria-pressed={o.id === selected} onClick={() => onSelect(o.id)} onPointerEnter={() => onHover(o.id)} onPointerLeave={() => onHover(null)}
              className={`grid w-full grid-cols-[18px_12px_minmax(0,1fr)_auto] items-center gap-2 rounded px-1.5 py-[5px] text-left text-xs ${o.id === selected ? "bg-signal-wash font-semibold" : o.id === hovered ? "bg-surface" : ""}`}>
              <span className="tabular-nums text-ink-muted">{k + 1}</span>
              <span aria-hidden className="h-3 w-3 rounded-full" style={{ background: o.band === null ? "var(--viz-ground)" : TERRACE(o.band) }} />
              <span className="truncate">{o.label}</span>
              <span className="tabular-nums">{fmt(o.height, 2)}</span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Legend({ map, scale }: { map: ObjectMapArtifact; scale?: [number, number] }) {
  const floor = map.relations.effect_floor;
  return (
    <div className="ring-1 ring-inset ring-white/[.07] flex flex-wrap items-center gap-x-6 gap-y-2.5 rounded-[10px] bg-[var(--viz-stage-raised)] px-3.5 py-2.5 text-[11px] leading-[14px] text-[var(--viz-stage-ink)]">
      <div className="flex flex-col gap-1" aria-label={legendLabel(scale)} role="img">
        <span className="text-xs font-semibold">{t("research.exec.objectMap.legendTitle")}</span>
        <span className="flex items-end gap-0.5" aria-hidden>
          {Array.from({ length: TERRACE_BANDS }, (_, k) => <span key={k} className="inline-block w-[18px] rounded-t-sm" style={{ height: 6 + Math.round((22 * (k + 1)) / TERRACE_BANDS), background: TERRACE(k) }} />)}
        </span>
        <span className="flex justify-between gap-3 text-[var(--viz-stage-muted)]" aria-hidden><span>0</span><span>{num(0.5, 1)}</span><span>1</span></span>
      </div>
      <div className="flex flex-wrap gap-3">
        <span className="flex items-center gap-1.5"><span aria-hidden className="h-3 w-3 rounded-sm bg-[var(--viz-ground)]" />{t("research.exec.objectMap.legendGround")}</span>
        <span className="flex items-center gap-1.5"><span aria-hidden className="h-[3px] w-[18px] rounded-sm bg-[var(--viz-link-positive)]" />{t("research.exec.objectMap.legendPositive")}</span>
        <span className="flex items-center gap-1.5"><span aria-hidden className="w-[18px] border-t-[3px] border-dashed border-[var(--viz-link-negative)]" />{t("research.exec.objectMap.legendNegative")}</span>
      </div>
      <div className="flex flex-wrap gap-3 text-[var(--viz-stage-muted)]">
        <span>{floor !== undefined ? tv("research.exec.objectMap.legendLinesFloor", { floor: num(floor, 2) }) : t("research.exec.objectMap.legendLines")}</span>
        <span className="flex items-center gap-1.5"><span aria-hidden className="h-2 w-2 rotate-45 bg-[var(--viz-map-context)]" />{t("research.exec.objectMap.legendContext")}</span>
      </div>
    </div>
  );
}

/** What the artifact says about its pairs, support and itself; none of it recomputed. The
 * first three lines are the approved design's; the rest waits behind a disclosure. */
function Facts({ map, title, methodId, fingerprint, originText }: { map: ObjectMapArtifact; title: string; methodId: string; fingerprint: string; originText: string }) {
  const quality = map.layout?.quality;
  const s = map.support;
  const c = map.status_counts;
  const hidden = belowFloor(map);
  return (
    <div className="flex flex-col gap-0.5 text-[11px] leading-[15px] text-ink-muted tabular-nums" data-testid="object-map-support">
      <span>{tv("research.exec.objectMap.statusLine", { reliable: c.reliable ?? 0, weak: c.weak ?? 0, unknown: c.unknown ?? 0 })}</span>
      <span data-testid="object-map-not-placed">{tv("research.exec.objectMap.notPlaced", { count: s.not_placed })}</span>
      <span data-testid="object-map-method">{tv("research.exec.objectMap.method", { method: map.spec.methodology_version || methodId, fingerprint: fingerprint.slice(0, 12) })}</span>
      <details className="mt-1">
        <summary className="cursor-pointer">{t("research.exec.objectMap.detailsTitle")}</summary>
        <span className="mt-1 flex flex-col gap-1.5">
          <span>{tv("research.exec.objectMap.readingIntro", { title })}</span>
          <span>{t("research.exec.objectMap.surfaceMeaning")}</span>
          <span>{t("research.exec.objectMap.distanceMeaning")}</span>
          {quality ? <span>{t(`research.exec.objectMap.${quality === "weak" || quality === "unreliable" ? "weakFitMeaning" : "fitMeaning"}`)}</span> : null}
          <span>{t("research.exec.objectMap.legendBands")}</span>
          <span>{t("research.exec.objectMap.labelHelp")}</span>
          <span>{t("research.exec.objectMap.unknownNote")}</span>
          <span>{tv("research.exec.objectMap.support", { placed: s.placed, respondents: s.respondents, effective: s.effective_n === null ? "—" : num(s.effective_n, 1) })}</span>
          {hidden && map.relations.effect_floor !== undefined ? <span>{tv("research.exec.objectMap.belowFloor", { floor: num(map.relations.effect_floor, 2), count: hidden })}</span> : null}
          {map.spec.terrain ? <span>{tv("research.exec.objectMap.provisional", { sigma: num(map.spec.terrain.sigma, 2) })}</span> : null}
          <span>{originText}</span>
        </span>
      </details>
    </div>
  );
}

/**
 * "Uložit snímek (PNG)": the current view as an image, marked internal. The 3D canvas (when
 * shown) and the SVG over it are composed as they are on screen -- their colours resolved from
 * the page's tokens -- with a caption naming the method and fingerprint. Nothing is redrawn
 * from data and nothing is recomputed; the report's figure stays `object_map_figure.py`.
 */
/**
 * A snapshot's caption and file name carry the map's own approval -- the Sociomap register's, as
 * the chip above the map says -- never "internal" on a map the register approves for reports,
 * and never "approved" on one it does not (PC7).
 */
export function snapshotNaming(approved: boolean, methodId: string, fingerprint: string): { caption: string; file: string } {
  const args = { method: methodId, fingerprint: fingerprint.slice(0, 12) };
  return approved
    ? { caption: tv("research.exec.objectMap.snapshotLabelApproved", args), file: t("research.exec.objectMap.snapshotFileApproved") }
    : { caption: tv("research.exec.objectMap.snapshotLabel", args), file: t("research.exec.objectMap.snapshotFile") };
}

async function saveSnapshot(area: HTMLElement | null, { caption, file }: { caption: string; file: string }): Promise<void> {
  if (!area) return;
  const { width, height } = area.getBoundingClientRect();
  if (!width || !height) return;
  const ratio = 2, strip = 30;
  const out = document.createElement("canvas");
  out.width = Math.round(width * ratio); out.height = Math.round((height + strip) * ratio);
  const context = out.getContext("2d");
  if (!context) return;
  context.scale(ratio, ratio);
  const style = getComputedStyle(area);
  const token = (name: string) => style.getPropertyValue(name).trim();
  context.fillStyle = token("--viz-stage"); context.fillRect(0, 0, width, height + strip);
  const canvas = area.querySelector("canvas");
  if (canvas) context.drawImage(canvas, 0, 0, width, height);
  const svg = area.querySelector("svg");
  if (svg) {
    const copy = svg.cloneNode(true) as SVGSVGElement;
    copy.querySelectorAll('[data-export="skip"]').forEach((n) => n.remove());
    copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    copy.setAttribute("width", String(width)); copy.setAttribute("height", String(height));
    copy.setAttribute("style", `font-family: ${token("--font-sans") || "sans-serif"}`);
    // An SVG drawn as an image cannot reach the page's web fonts; embed the faces the labels
    // use, so the snapshot sets the text exactly as the labels were sized.
    const faces = await embeddedFaces();
    if (faces) copy.insertAdjacentHTML("afterbegin", `<style>${faces}</style>`);
    const markup = resolveVars(new XMLSerializer().serializeToString(copy), token);
    const image = new Image();
    await new Promise<void>((done) => { image.onload = () => done(); image.onerror = () => done(); image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`; });
    if (image.complete && image.naturalWidth) context.drawImage(image, 0, 0, width, height);
  }
  context.fillStyle = token("--viz-stage-muted"); context.font = `12px ${token("--font-sans") || "sans-serif"}`;
  context.fillText(caption, 12, height + 19);
  const link = document.createElement("a");
  link.href = out.toDataURL("image/png");
  link.download = file;
  link.click();
}

/** The page's IBM Plex Sans @font-face rules with their files inlined as data URLs. */
async function embeddedFaces(): Promise<string> {
  const rules: CSSFontFaceRule[] = [];
  for (const sheet of Array.from(document.styleSheets)) {
    let list: CSSRuleList;
    try { list = sheet.cssRules; } catch { continue; }
    for (const rule of Array.from(list)) {
      if (rule instanceof CSSFontFaceRule && rule.style.getPropertyValue("font-family").includes("IBM Plex Sans") && rule.style.getPropertyValue("font-style") !== "italic") rules.push(rule);
    }
  }
  const css = await Promise.all(rules.map(async (rule) => {
    const url = /url\(["']?([^"')]+)["']?\)/.exec(rule.style.getPropertyValue("src"))?.[1];
    if (!url) return "";
    try {
      const blob = await (await fetch(url)).blob();
      const data = await new Promise<string>((done) => { const r = new FileReader(); r.onload = () => done(String(r.result)); r.readAsDataURL(blob); });
      return `@font-face{font-family:"IBM Plex Sans";font-weight:${rule.style.getPropertyValue("font-weight") || 400};src:url(${data}) format("woff2");}`;
    } catch { return ""; }
  }));
  return css.join("");
}
