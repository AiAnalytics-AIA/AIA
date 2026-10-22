"use client";

// The signed-off map (aia-sociomap-5) on the Results page, drawn as the AIA panel draws it
// (plan sociomap-5-web, chunk 2). Inside the map everything is the panel's: the canvas drawing
// (object-map-panel.ts), the camera tools in the top right corner, the legend in the bottom left
// with its fold-out key. Around the map the page stays the web's: the Normalizace and Vztahy
// switches, the object list (which also makes every object reachable by keyboard and screen
// reader) and the facts.
//
// The map draws the stored artifact and computes nothing methodological; camera, scale mode,
// relation display, selection and hover are presentation state. What the map says about itself
// (the weakly determined banner, the uncertainty circle, the notes) is drawn over it from the
// stored credibility, and the objects nobody rated are listed beside it. A map that stores its
// respondent map switches to it (the panel's Mapa: Respondenti / Objekty): the stored density of
// the clearly placed respondents as the terrain, every placed respondent as a dot (a weakly placed
// one faint), the objects as markers, its own legend, note and counts, the taste segments'
// colours, legend and hint. A clicked object, relation or respondent shows its detail above the
// list, from what the map stores (the panel's p-value, noise level and the respondent's answers
// are not stored, so not shown). Export PNG saves the map as drawn with its legend card.
//
// As the panel embedded in a page: the wheel zooms while the pointer is over the map and scrolls the
// page elsewhere; ⛶ opens the map in the browser's full screen (the panel's `socioFullscreen66`).

import { type PointerEvent, type ReactNode, useEffect, useId, useMemo, useRef, useState } from "react";
import { t, tv } from "@/i18n/t";
import { objectTarget, pairTarget } from "@/lib/artifacts/sociomap";
import { num } from "@/lib/sociomapping-view";
import { type BatteryWithMaps, type ObjectMapArtifact, originalRating } from "@/lib/object-map-view";
import {
  type SegmentLegend, objectDetail, objectsNotPlaced, panelObjects, relationDetail, respondentDetail, respondentNote, segmentLegend, storedFrame, storedRespondents,
} from "@/lib/object-map-signed-off";
import {
  CLICK_SLOP, COOL, drawLegendCard, INITIAL_CAMERA, SECONDARY, SEGMENT_COLOURS, SEGMENT_GREY, TOP_PITCH, WARM, ZOOM_IN, ZOOM_OUT,
  type Hit, type Norm, type PanelCamera, type RelationMode,
  REL_FLOOR, absoluteGrid, densityGrid, mapStatements, panelDots, camera3d, color66, dragCamera, drawObjectMap, hitTest, nodeScale, nodeTones, normalizer,
  panelNodes, relationPairs, relationStrength, storedGrid, strongestRelation, topCamera, wheelCamera, zoomCamera,
} from "@/lib/object-map-panel";

/** The canvas's size before it is measured (and in tests): the panel's own fallback. */
const DEFAULT_SIZE = { width: 900, height: 700 };

const RELATION_MODES: { mode: RelationMode; label: string; help?: string }[] = [
  { mode: "top", label: "research.exec.objectMap.panel.relTop", help: "research.exec.objectMap.panel.relTopHelp" },
  { mode: "selected", label: "research.exec.objectMap.panel.relSelected" },
  { mode: "all", label: "research.exec.objectMap.panel.relAll" },
];

const PRESSED = "aria-pressed:!border-signal aria-pressed:!bg-signal-wash aria-pressed:font-semibold aria-pressed:text-signal";
const SWITCH = `inline-flex min-h-7 items-center disabled:cursor-not-allowed disabled:opacity-50 rounded-sm border border-border-strong bg-surface-raised px-2 text-xs text-ink hover:border-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${PRESSED}`;

export function ObjectMapPanel({ battery, map, facts }: { battery: BatteryWithMaps; map: ObjectMapArtifact; facts: ReactNode }) {
  if (storedFrame(map) && map.terrain.status === "computed") return <PanelView battery={battery} map={map} facts={facts} />;
  // Without a stored terrain there is no frame to draw on: say so where the map would be, and keep
  // the objects and the facts.
  const objects = panelObjects(battery, map);
  return (
    <div className="flex flex-wrap items-start gap-4" data-testid="object-map-panel">
      <p className="min-w-0 flex-[999_1_560px] text-xs text-ink-muted" data-testid="object-map-no-terrain">
        {tv("research.exec.objectMap.noTerrain", { reason: map.terrain.status === "not_computed" ? map.terrain.reason : "—" })}
      </p>
      <Aside battery={battery} facts={facts} items={objects.map((o) => ({ id: o.id, label: o.label, value: o.height, colour: color66(o.relative ?? REL_FLOOR) }))} selected={-1}
        notPlaced={objectsNotPlaced(battery, map)} />
    </div>
  );
}

type ListItem = { id: string; label: string; value: number | null; colour: string };

/** Beside the map: every object as a button (keyboard and screen-reader access to the map), then the facts. */
function Aside({ battery, facts, items, selected, notPlaced, counts = null, detail = null, onChoose, onHover }: {
  battery: BatteryWithMaps; facts: ReactNode; items: ListItem[]; selected: number; notPlaced: string[]; counts?: ReactNode; detail?: ReactNode; onChoose?: (k: number) => void; onHover?: (k: number) => void;
}) {
  return (
    <aside className="flex min-w-0 flex-[1_1_260px] flex-col gap-3">
      {detail}
      {counts}
      <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4" data-testid="object-map-panel-list">
        <h4 className="text-xs font-semibold">{t("research.exec.objectMap.panel.listTitle")}</h4>
        <ul className="flex flex-col">
          {items.map((n, k) => (
            <li key={n.id}>
              <button type="button" data-aia={objectTarget(battery.battery_id, n.id) ?? undefined} aria-pressed={onChoose ? k === selected : undefined} aria-disabled={onChoose ? undefined : true} onClick={() => onChoose?.(k)} onPointerEnter={() => onHover?.(k)} onPointerLeave={() => onHover?.(-1)}
                aria-label={onChoose ? tv("research.exec.objectMap.selectObject", { label: n.label }) : undefined}
                className={`grid w-full grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-2 rounded px-1.5 py-[5px] text-left text-xs [&:not([aria-disabled])]:hover:bg-surface aria-disabled:cursor-default ${k === selected ? "bg-signal-wash font-semibold" : ""}`}>
                <span aria-hidden className="h-3 w-3 rounded-full" style={{ background: n.colour }} />
                <span className="truncate">{n.label}</span>
                <span className="tabular-nums">{panelNumber(originalRating(n.value, battery.rating_scale) ?? n.value)}</span>
              </button>
            </li>
          ))}
        </ul>
        {/* The set's objects nobody rated have no place on the map; the panel names them under it. */}
        {notPlaced.length ? (
          <p className="text-xs leading-[17px] text-ink-muted" data-testid="object-map-unplaced-objects">{tv("research.exec.objectMap.panel.notPlaced", { labels: notPlaced.join(", ") })}</p>
        ) : null}
      </div>
      <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4">{facts}</div>
    </aside>
  );
}

function PanelView({ battery, map, facts }: { battery: BatteryWithMaps; map: ObjectMapArtifact; facts: ReactNode }) {
  const frame = useMemo(() => storedFrame(map)!, [map]);
  const nodes = useMemo(() => panelNodes(battery, map, frame), [battery, map, frame]);
  const relativeGrid = useMemo(() => storedGrid(map)!, [map]);
  const strongest = useMemo(() => strongestRelation(map), [map]);
  const [norm, setNorm] = useState<Norm>("range");
  const [mode, setMode] = useState<RelationMode>("top");
  const [camera, setCamera] = useState<PanelCamera>(INITIAL_CAMERA);
  const [selected, setSelected] = useState(-1);
  // The clicked relation line's two objects (the first is also the selected object), or null.
  const [relation, setRelation] = useState<[number, number] | null>(null);
  // Which map the canvas shows, and the clicked respondent's dot on the respondent map (-1: none).
  const [view, setView] = useState<"objects" | "respondents">("objects");
  const [person, setPerson] = useState(-1);
  const density = useMemo(() => densityGrid(map), [map]);
  const dots = useMemo(() => panelDots(map, frame), [map, frame]);
  const segments = useMemo(() => segmentLegend(battery, map), [battery, map]);
  const people = useMemo(() => (view === "respondents" && density ? { dots, selected: person } : undefined), [view, density, dots, person]);
  const [hovered, setHovered] = useState(-1);
  const [size, setSize] = useState(DEFAULT_SIZE);
  const [ratio, setRatio] = useState(() => (typeof window === "undefined" ? 1 : Math.min(2, window.devicePixelRatio || 1)));
  // Absolutni draws the stored envelope of the absolute means; a map that stores none offers only Relativni.
  const stored = useMemo(() => absoluteGrid(map), [map]);
  const absolute = norm === "absolute" ? stored : null;
  const grid = people ? density! : absolute ?? relativeGrid;
  const tones = useMemo(() => nodeTones(nodes, norm), [nodes, norm]);
  // Full screen shows the stage alone (the canvas follows its new box through the resize observer).
  const [stage, setStage] = useState<HTMLDivElement | null>(null);
  const [full, setFull] = useState(false);
  // In full screen the detail card that names the selection is out of sight, so "Top vztahy" is the
  // map's five strongest whatever is selected; on the page, the selection's five, as the panel's.
  const topOf = mode === "top" && full ? -1 : selected;
  const pairs = useMemo(() => relationPairs(map, mode, topOf).map((p) => ({ ...p, k: relationStrength(p.v, norm, strongest) })), [map, mode, topOf, norm, strongest]);
  // The node size follows the whole set, an object nobody rated included, as the panel's backend counts it.
  const scale = nodeScale(map.object_ids.length + (map.objects_not_placed?.length ?? 0));
  const statements = useMemo(() => mapStatements(map, {
    caption: t("research.exec.objectMap.panel.uncertaintyCaption"),
    weakTitle: t("research.exec.objectMap.panel.weakTitle"),
    weakBody: (percent) => tv("research.exec.objectMap.panel.weakBody", { percent }),
    noStructureTitle: t("research.exec.objectMap.panel.noStructureTitle"),
    noStructureBody: t("research.exec.objectMap.panel.noStructureBody"),
    sparse: t("research.exec.objectMap.panel.sparseNote"),
    labelled: (shown, total) => tv("research.exec.objectMap.panel.labelledNote", { shown, total }),
  }), [map]);
  // The respondent map's note: below the declared minimum of objects only indicative, below the
  // declared minimum of ratings nobody placed. The panel's plural: 2-4 "objekty", else "objektů".
  const statementsHere = useMemo(() => {
    const note = respondentNote(map);
    const objects = (n: number) => t(`research.exec.objectMap.panel.${n >= 2 && n <= 4 ? "objectsFew" : "objectsMany"}`);
    const text = note ? tv(`research.exec.objectMap.panel.${note.placeable ? "respondentIndicative" : "respondentUnplaceable"}`, { n: note.objects, objects: objects(note.objects), min: note.minObjects, ratings: note.minRatings }) : null;
    return { ...statements, respondentNote: text };
  }, [map, statements]);
  const canvas = useRef<HTMLCanvasElement>(null);
  const hits = useRef<Hit[]>([]);
  const pointer = useRef<{ lastX: number; lastY: number; mode: "select" | "rotate"; hit: Hit | null; moved: number } | null>(null);
  const described = useId();

  // The canvas follows its box; the drawing is in CSS pixels at up to twice the device's density.
  useEffect(() => {
    const node = canvas.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setSize((s) => (s.width === Math.round(width) && s.height === Math.round(height) ? s : { width: Math.round(width), height: Math.round(height) }));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  // A moved window can change the device's density without a resize: redraw at the new one.
  useEffect(() => {
    const query = window.matchMedia?.(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
    if (!query) return;
    const change = () => setRatio(Math.min(2, window.devicePixelRatio || 1));
    query.addEventListener("change", change);
    return () => query.removeEventListener("change", change);
  }, [ratio]);

  // One draw per animation frame, however many pointer moves and state changes came before it.
  const latest = useRef<Parameters<typeof drawObjectMap>[1] | null>(null);
  const pending = useRef(0);
  useEffect(() => {
    latest.current = { width: size.width, height: size.height, camera, grid, nodes, tones, pairs, selected, hovered, nodeScale: scale, statements: statementsHere, respondents: people };
    const draw = () => {
      pending.current = 0;
      const node = canvas.current;
      const context = node?.getContext("2d");
      const s = latest.current;
      if (!node || !context || !s) return;
      const width = Math.max(1, Math.round(s.width * ratio)), height = Math.max(1, Math.round(s.height * ratio));
      if (node.width !== width) node.width = width;
      if (node.height !== height) node.height = height;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      hits.current = drawObjectMap(context, s).hits;
    };
    if (typeof window.requestAnimationFrame !== "function") { draw(); return; }
    if (!pending.current) pending.current = window.requestAnimationFrame(draw);
  }, [size, camera, grid, nodes, tones, pairs, selected, hovered, scale, statementsHere, people, ratio]);
  // Cleared on unmount, so a remount (React's development double mount included) schedules again.
  useEffect(() => () => { if (pending.current) window.cancelAnimationFrame(pending.current); pending.current = 0; }, []);

  // The wheel over the map zooms it, as the panel's `wheel66`; outside the map the page scrolls.
  useEffect(() => {
    const node = canvas.current;
    if (!node) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      setCamera((c) => wheelCamera(c, e.deltaY));
    };
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    const change = () => setFull(stage !== null && document.fullscreenElement === stage);
    document.addEventListener("fullscreenchange", change);
    return () => document.removeEventListener("fullscreenchange", change);
  }, [stage]);
  const toggleFull = () => {
    if (document.fullscreenElement) void document.exitFullscreen?.();
    else void stage?.requestFullscreen?.();
  };

  const local = (e: PointerEvent<HTMLCanvasElement>) => { const r = e.currentTarget.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  // A press on an object selects it on release; held and dragged, it turns the map like a press on
  // free ground. A click on free ground clears the selection (the panel's pointer handlers).
  const onDown = (e: PointerEvent<HTMLCanvasElement>) => {
    const { x, y } = local(e);
    const hit = hitTest(hits.current, x, y);
    e.currentTarget.setPointerCapture?.(e.pointerId);
    pointer.current = { lastX: x, lastY: y, mode: hit ? "select" : "rotate", hit, moved: 0 };
  };
  const onMove = (e: PointerEvent<HTMLCanvasElement>) => {
    const { x, y } = local(e);
    const p = pointer.current;
    if (!p) {
      const hit = hitTest(hits.current, x, y);
      e.currentTarget.style.cursor = hit ? "pointer" : "";
      // Hovering brings up an object's label on either map; a dot has none.
      setHovered(hit?.kind === "object" ? hit.index : -1);
      return;
    }
    const dx = x - p.lastX, dy = y - p.lastY;
    p.moved += Math.hypot(dx, dy);
    if (p.mode === "select" && p.moved >= CLICK_SLOP) p.mode = "rotate";
    if (p.mode === "rotate") setCamera((c) => dragCamera(c, dx, dy));
    p.lastX = x; p.lastY = y;
  };
  const onUp = () => {
    const p = pointer.current;
    pointer.current = null;
    if (!p || p.moved >= CLICK_SLOP) return;
    const hit = p.mode === "select" ? p.hit : null;
    // On the respondent map a click on a dot rings that respondent and shows its profile; on the
    // object map an object or a relation line shows its detail. A click on free ground clears
    // every selection, as the panel's.
    if (hit?.kind === "respondent") { setPerson(hit.index); setSelected(-1); setRelation(null); }
    else if (hit?.kind === "relation" && !people) { setSelected(hit.index); setRelation([hit.index, hit.j!]); }
    else if (hit?.kind === "object" && !people) { setSelected(hit.index); setRelation(null); }
    else if (!hit) { setSelected(-1); setPerson(-1); setRelation(null); }
  };

  const tool = (label: string, short: string, act: () => void, pressed?: boolean) => (
    <button type="button" title={label} aria-label={label} aria-pressed={pressed} onClick={act}
      className={`h-[29px] w-[29px] cursor-pointer rounded-[5px] border-0 text-[13px] text-[#e8edf0] hover:bg-white/[.14] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#e8edf0] ${pressed ? "bg-white/[.14]" : "bg-transparent"}`}>{short}</button>
  );
  const fromAbove = camera.pitch < TOP_PITCH;
  const notPlaced = objectsNotPlaced(battery, map);
  // The panel's Export PNG (`socioExport66`): the canvas as drawn, here with the legend card
  // drawn in, since the page's legend is HTML over the canvas and would be missing.
  const exportPng = () => {
    const node = canvas.current;
    if (!node) return;
    const out = document.createElement("canvas");
    out.width = node.width;
    out.height = node.height;
    const context = out.getContext("2d");
    if (!context) return;
    context.drawImage(node, 0, 0);
    context.setTransform(node.width / size.width, 0, 0, node.height / size.height, 0, 0);
    const panel = "research.exec.objectMap.panel";
    drawLegendCard(context, people
      ? { title: t(`${panel}.legendTitleRespondents`), marks: [panelNumber(0), t(`${panel}.scaleDensity`), panelNumber(1)], segments: segments ? segmentLines(segments) : null }
      : { title: t(`${panel}.legendTitle`), marks: legendMarks(battery, nodes.map((n) => (n.primary ? n.value : null)), norm) }, size.height);
    const link = document.createElement("a");
    link.download = `Sociomapa_${people ? "respondenti" : "objekty"}.png`;
    link.href = out.toDataURL("image/png");
    link.click();
  };
  // Each map opens with nothing selected: an object chosen on one is not the other's, nor a ringed respondent.
  const showMap = (next: "objects" | "respondents") => {
    if (next === view) return;
    setView(next); setSelected(-1); setRelation(null); setPerson(-1); setHovered(-1);
  };
  const choose = (k: number) => { setSelected((s) => (s === k ? -1 : k)); setRelation(null); };
  const detail = people
    ? <PersonCard detail={person >= 0 ? respondentDetail(map, dots[person].id) : null} />
    : <ObjectCard battery={battery} map={map} selected={selected} relation={relation}
      onRelation={(j) => setRelation((r) => (isPair(r, selected, j) ? null : [selected, j]))} />;

  return (
    <div className="flex flex-col gap-3" data-testid="object-map-panel">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2" role="toolbar" aria-label={t("research.exec.objectMap.controls")}>
        {density ? (
          <div className="flex items-center gap-1.5" role="group" aria-label={t("research.exec.objectMap.panel.mapGroup")}>
            <span className="text-[10px] uppercase tracking-[.06em] text-ink-muted">{t("research.exec.objectMap.panel.mapGroup")}</span>
            <button type="button" className={SWITCH} aria-pressed={view === "respondents"} onClick={() => showMap("respondents")}>{t("research.exec.objectMap.panel.mapRespondents")}</button>
            <button type="button" className={SWITCH} aria-pressed={view === "objects"} onClick={() => showMap("objects")}>{t("research.exec.objectMap.panel.mapObjects")}</button>
          </div>
        ) : null}
        {/* The respondent map's height is a density: the panel offers neither Normalizace nor Vztahy there. */}
        {people ? null : (
          <div className="flex items-center gap-1.5" role="group" aria-label={t("research.exec.objectMap.panel.norm")}>
            <span className="text-[10px] uppercase tracking-[.06em] text-ink-muted">{t("research.exec.objectMap.panel.norm")}</span>
            <button type="button" className={SWITCH} aria-pressed={norm === "absolute"} disabled={!stored} title={t("research.exec.objectMap.panel.absoluteHelp")} onClick={() => setNorm("absolute")}>{t("research.exec.objectMap.panel.absolute")}</button>
            <button type="button" className={SWITCH} aria-pressed={norm === "range"} title={t("research.exec.objectMap.panel.rangeHelp")} onClick={() => setNorm("range")}>{t("research.exec.objectMap.panel.range")}</button>
          </div>
        )}
        {people ? null : (
          <div className="flex items-center gap-1.5" role="group" aria-label={t("research.exec.objectMap.panel.relations")}>
            <span className="text-[10px] uppercase tracking-[.06em] text-ink-muted">{t("research.exec.objectMap.panel.relations")}</span>
            {RELATION_MODES.map((r) => (
              <button key={r.mode} type="button" className={SWITCH} aria-pressed={mode === r.mode} title={r.help ? t(r.help) : undefined} onClick={() => setMode(r.mode)}>{t(r.label)}</button>
            ))}
          </div>
        )}
        <button type="button" className={SWITCH} title={t("research.exec.objectMap.panel.exportHelp")} onClick={exportPng}>{t("research.exec.objectMap.panel.export")}</button>
      </div>
      <div className="flex flex-wrap items-start gap-4">
        <div ref={setStage} className="relative h-[700px] min-w-0 flex-[999_1_560px] overflow-hidden rounded-[10px] bg-[#07090c] [min-width:min(100%,560px)] [&:fullscreen]:h-screen [&:fullscreen]:w-screen [&:fullscreen]:rounded-none" data-testid="object-map-stage">
          <canvas ref={canvas} className="block h-full w-full cursor-grab touch-none" role="img" data-testid="object-map-canvas"
            data-camera={JSON.stringify(camera)} data-norm={norm} data-map={people ? "respondents" : "objects"} data-person={people && person >= 0 ? dots[person].id : ""}
            data-relations={people ? "" : pairs.map((p) => `${nodes[p.i].id}|${nodes[p.j].id}`).join(" ")} data-selected={selected >= 0 ? nodes[selected].id : ""} data-relation={relation ? `${nodes[relation[0]].id}|${nodes[relation[1]].id}` : ""}
            aria-label={people ? tv("research.exec.objectMap.panel.respondentCanvas", { title: battery.title, placed: dots.length, n: nodes.length }) : tv("research.exec.objectMap.panel.canvas", { title: battery.title, n: nodes.length })}
            aria-describedby={people ? undefined : described}
            onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={() => { pointer.current = null; }} onPointerLeave={() => { if (!pointer.current) setHovered(-1); }} />
          <p id={described} className="sr-only" aria-live="polite">{tv("research.exec.objectMap.panel.relationsShown", { count: pairs.length })}</p>
          <div role="group" aria-label={t("research.exec.objectMap.panel.tools")}
            className="absolute right-[13px] top-[13px] z-[5] flex flex-col gap-[3px] rounded-[7px] border border-white/[.14] bg-[rgba(8,11,15,.7)] p-1 backdrop-blur-[8px]">
            {tool(t("research.exec.objectMap.panel.zoomIn"), "＋", () => setCamera((c) => zoomCamera(c, ZOOM_IN)))}
            {tool(t("research.exec.objectMap.panel.zoomOut"), "−", () => setCamera((c) => zoomCamera(c, ZOOM_OUT)))}
            {tool(t("research.exec.objectMap.panel.top"), "2D", () => setCamera((c) => topCamera(c, size.width, size.height)), fromAbove)}
            {tool(t("research.exec.objectMap.panel.three"), "3D", () => setCamera(camera3d), !fromAbove)}
            {tool(t("research.exec.objectMap.panel.center"), "◎", () => setCamera(INITIAL_CAMERA))}
            {tool(t("research.exec.objectMap.panel.fullscreen"), "⛶", toggleFull, full)}
          </div>
          {people ? <DensityLegend segments={segments} /> : <Legend battery={battery} values={nodes.map((n) => (n.primary ? n.value : null))} norm={norm} strongest={strongest} />}
        </div>
        {/* Selection is the object map's: on the respondent map the list only lists (a click there showed nothing). */}
        <Aside battery={battery} facts={facts} selected={selected} onChoose={people ? undefined : choose} onHover={setHovered} notPlaced={notPlaced} detail={detail}
          counts={people ? <RespondentCounts map={map} segments={segments} /> : null}
          items={nodes.map((n, k) => ({ id: n.id, label: n.label, value: n.value, colour: n.primary ? color66(tones[k]) : SECONDARY }))} />
      </div>
    </div>
  );
}

/** A number as the panel's `fmt66` prints it (two decimals below 10, one below 100), in Czech. */
export function panelNumber(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "—";
  return Math.abs(v) >= 100 ? num(v, 0) : num(v, Math.abs(v) < 10 ? 2 : 1);
}

/** The legend's three marks under the ramp: the lowest and highest PRIMARY mean on the declared
 *  scale and the scale's word (rozsah, absolutní, bez dat). */
function legendMarks(battery: BatteryWithMaps, stored: (number | null)[], norm: Norm): [string, string, string] {
  const scale = normalizer(stored.filter((v): v is number => v !== null), norm, [0, 1]);
  const shown = (v: number) => (scale.kind === "none" ? "—" : panelNumber(originalRating(v, battery.rating_scale) ?? v));
  const kind = { range: "scaleRange", absolute: "scaleAbsolute", none: "scaleNone" }[scale.kind];
  return [shown(scale.lo), t(`research.exec.objectMap.panel.${kind}`), shown(scale.hi)];
}

/** The panel's legend (`updateLegend66`, `relationKeyHtml66`): the height scale at a glance, its
 *  meaning behind an ⓘ, and what the lines mean folded out. */
function Legend({ battery, values: stored, norm, strongest }: { battery: BatteryWithMaps; values: (number | null)[]; norm: Norm; strongest: number }) {
  const [open, setOpen] = useState(false);
  // The scale reads the PRIMARY objects' stored means; the numbers print on the declared scale.
  const [lo, word, hi] = legendMarks(battery, stored, norm);
  const relative = norm !== "absolute" && strongest > 1e-6;
  const row = (k: string, v: string) => <div><span className="font-semibold">{t(`research.exec.objectMap.panel.${k}`)}</span> {t(`research.exec.objectMap.panel.${v}`)}</div>;
  return (
    <div className="absolute bottom-[14px] left-[17px] z-[5] w-[260px] max-w-[calc(100%-34px)] rounded-[8px] border border-white/[.13] bg-[rgba(8,11,15,.75)] px-3 py-2.5 text-white backdrop-blur-[8px]" data-testid="object-map-legend">
      <b className="text-[10.5px] uppercase tracking-[.05em] text-white/70">
        {t("research.exec.objectMap.panel.legendTitle")}{" "}
        <details className="inline">
          <summary className="inline cursor-pointer list-none font-normal normal-case opacity-60 [&::-webkit-details-marker]:hidden" title={t("research.exec.objectMap.panel.legendInfo")} aria-label={t("research.exec.objectMap.panel.legendInfo")}>ⓘ</summary>
          <div className="my-1 block text-[11px] font-normal normal-case leading-[1.4] tracking-normal opacity-85" data-testid="object-map-legend-info">
            {row("infoHeight", "infoHeightText")}
            {row("infoBetween", "infoBetweenText")}
            {row("infoScale", norm === "absolute" ? "infoScaleAbsolute" : "infoScaleRange")}
          </div>
        </details>
      </b>
      <div aria-hidden className="my-1.5 h-2 rounded-[2px] bg-[linear-gradient(90deg,#07134f,#005fa8,#00bdd1,#14d178,#7ce700,#f4e81b,#ff8f16,#e8231d)]" />
      <div className="flex justify-between text-[9.5px] text-white/[.56]" data-testid="object-map-legend-scale">
        <span>{lo}</span><span>{word}</span><span>{hi}</span>
      </div>
      {open ? (
        <div data-testid="object-map-legend-key">
          <div className="mt-1.5 text-[9.5px] leading-[1.4] text-white/[.58]">{t("research.exec.objectMap.panel.colourNote")}</div>
          <b className="mt-2 block text-[10.5px] uppercase tracking-[.05em] text-white/70">{t("research.exec.objectMap.panel.keyTitle")}</b>
          <KeyRow lines={[[1, 14, 0.1, WARM], [19, 33, 0.5, WARM]]} text={relative ? tv("research.exec.objectMap.panel.keyStrengthRelative", { hi: num(strongest, 2) }) : t("research.exec.objectMap.panel.keyStrengthAbsolute")} />
          <KeyRow lines={[[1, 14, 0.5, WARM], [19, 33, 0.5, COOL]]} text={t("research.exec.objectMap.panel.keySign")} />
        </div>
      ) : null}
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="mt-1.5 cursor-pointer border-0 bg-transparent p-0 text-[10px] text-[#9cc7da] underline">
        {t(open ? "research.exec.objectMap.panel.legendLess" : "research.exec.objectMap.panel.legendMore")}
      </button>
    </div>
  );
}

/** One row of the line key, its sample lines drawn as the map draws them at |r| = v on Absolutni. */
function KeyRow({ lines, text }: { lines: [number, number, number, string][]; text: string }) {
  return (
    <div className="mt-[3px] flex items-center gap-1.5 text-[9.5px] text-white/[.72]">
      <svg width="34" height="12" viewBox="0 0 34 12" aria-hidden className="flex-none">
        {lines.map(([x1, x2, v, colour]) => {
          const k = Math.min(1, v / 0.5);
          return (
            <g key={`${x1}${colour}`}>
              <line x1={x1} y1="6" x2={x2} y2="6" stroke="#fff" strokeLinecap="round" strokeWidth={1 + 5 * k + 2.4} strokeOpacity={0.5 + 0.4 * k} />
              <line x1={x1} y1="6" x2={x2} y2="6" stroke={colour} strokeWidth={1 + 5 * k} strokeOpacity={0.6 + 0.4 * k} />
            </g>
          );
        })}
      </svg>
      <span>{text}</span>
    </div>
  );
}

/** The respondent map's legend (`updateLegend66` on Respondenti): the density scale, its meaning
 *  behind an ⓘ, and the colour note folded out. */
function DensityLegend({ segments }: { segments: SegmentLegend | null }) {
  const [open, setOpen] = useState(false);
  const row = (k: string, v: string) => <div><span className="font-semibold">{t(`research.exec.objectMap.panel.${k}`)}</span> {t(`research.exec.objectMap.panel.${v}`)}</div>;
  return (
    <div className="absolute bottom-[14px] left-[17px] z-[5] w-[260px] max-w-[calc(100%-34px)] rounded-[8px] border border-white/[.13] bg-[rgba(8,11,15,.75)] px-3 py-2.5 text-white backdrop-blur-[8px]" data-testid="object-map-legend">
      <b className="text-[10.5px] uppercase tracking-[.05em] text-white/70">
        {t("research.exec.objectMap.panel.legendTitleRespondents")}{" "}
        <details className="inline">
          <summary className="inline cursor-pointer list-none font-normal normal-case opacity-60 [&::-webkit-details-marker]:hidden" title={t("research.exec.objectMap.panel.legendInfo")} aria-label={t("research.exec.objectMap.panel.legendInfo")}>ⓘ</summary>
          <div className="my-1 block text-[11px] font-normal normal-case leading-[1.4] tracking-normal opacity-85" data-testid="object-map-legend-info">
            {row("infoHeight", "infoHeightRespondentsText")}
            {row("infoFaint", "infoFaintText")}
          </div>
        </details>
      </b>
      <div aria-hidden className="my-1.5 h-2 rounded-[2px] bg-[linear-gradient(90deg,#07134f,#005fa8,#00bdd1,#14d178,#7ce700,#f4e81b,#ff8f16,#e8231d)]" />
      {/* The stored density is over its maximum: the scale runs from none to the densest place. */}
      <div className="flex justify-between text-[9.5px] text-white/[.56]" data-testid="object-map-legend-scale">
        <span>{panelNumber(0)}</span><span>{t("research.exec.objectMap.panel.scaleDensity")}</span><span>{panelNumber(1)}</span>
      </div>
      {open ? (
        <div data-testid="object-map-legend-key">
          <div className="mt-1.5 text-[9.5px] leading-[1.4] text-white/[.58]">{t("research.exec.objectMap.panel.colourNoteRespondents")}</div>
          {/* The taste segments' legend joins here (plan sociomap-5-web, chunk 5). */}
        </div>
      ) : null}
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="mt-1.5 cursor-pointer border-0 bg-transparent p-0 text-[10px] text-[#9cc7da] underline">
        {t(open ? "research.exec.objectMap.panel.legendLess" : "research.exec.objectMap.panel.legendMoreRespondents")}
      </button>
      {/* The taste segments stay in view under the key, as the panel's legend shows them. */}
      {segments ? <SegmentNote lines={segmentLines(segments)} /> : null}
    </div>
  );
}

export type SegmentLines = { title: string | null; rows: { colour: string; text: string }[]; foot: string | null };

/**
 * What the panel's legend says about the taste segments (`updateLegend66` on Respondenti): with
 * segments, each one's colour, share and the objects its people rate above and below the rest,
 * the overlap when they are not distinct, and the grey of a dot not clearly in one; with a
 * borderline split, the likely groups in grey and that nobody is coloured; otherwise why none is shown.
 */
/** A segment's share as the panel prints it: the panel rounds a share to 4 decimals before it prints
 *  the percentage (its payload does), so 23/107 reads 22 %, not 21 %. */
export function sharePercent(x: number): string {
  return `${Math.round(100 * Number(x.toFixed(4)))} %`;
}

export function segmentLines(legend: SegmentLegend): SegmentLines {
  const pct = sharePercent;
  const named = (g: SegmentLegend["segments"][number]) =>
    (g.likes.length ? ` · ${tv("research.exec.objectMap.panel.segmentLikes", { labels: g.likes.join(", ") })}` : "")
    + (g.dislikes.length ? ` · ${tv("research.exec.objectMap.panel.segmentDislikes", { labels: g.dislikes.join(", ") })}` : "");
  if (legend.decision === "SEGMENTS") {
    return {
      title: t("research.exec.objectMap.panel.segmentsTitle") + (legend.distinct ? "" : ` · ${t("research.exec.objectMap.panel.segmentsOverlap")}`),
      rows: [
        ...legend.segments.map((g, j) => ({ colour: SEGMENT_COLOURS[j % SEGMENT_COLOURS.length], text: tv("research.exec.objectMap.panel.segmentRow", { n: j + 1, share: pct(g.share) }) + named(g) })),
        { colour: SEGMENT_GREY, text: t("research.exec.objectMap.panel.segmentGrey") },
      ],
      foot: null,
    };
  }
  if (legend.decision === "BORDERLINE") {
    return {
      title: tv("research.exec.objectMap.panel.hintTitle", { k: legend.segments.length }),
      rows: legend.segments.map((g) => ({ colour: SEGMENT_GREY, text: pct(g.share) + named(g) })),
      foot: t("research.exec.objectMap.panel.hintNote"),
    };
  }
  // The panel singles out too few respondents; every other reason reads as no clear segments.
  return { title: null, rows: [], foot: t(`research.exec.objectMap.panel.${legend.reason === "TOO_FEW_RESPONDENTS" ? "segmentsTooFew" : "segmentsNone"}`) };
}

function SegmentNote({ lines }: { lines: SegmentLines }) {
  return (
    <div className="mt-1.5 text-[9.5px] leading-[1.4] text-white/[.58]" data-testid="object-map-segments">
      {lines.title ? <b className="text-[10.5px] uppercase tracking-[.05em] text-white/70">{lines.title}</b> : null}
      {lines.rows.map((row, j) => (
        <div key={j}><span aria-hidden className="mr-[5px] inline-block h-[9px] w-[9px] rounded-full" style={{ background: row.colour }} />{row.text}</div>
      ))}
      {lines.foot ? <div>{lines.foot}</div> : null}
    </div>
  );
}

/** The map info's „Segmenty“ row: how many, their shares and overlap; the borderline hint; or why none.
 *  The thresholds it quotes are the declared ones. */
export function segmentsRow(legend: SegmentLegend, map: ObjectMapArtifact): { value: string; help: string } {
  const rules = map.spec.segments ?? {};
  const pct = sharePercent;
  const shares = legend.segments.map((g) => pct(g.share)).join(" / ");
  if (legend.decision === "BORDERLINE") {
    return { value: tv("research.exec.objectMap.panel.countHint", { k: legend.segments.length, shares }), help: t("research.exec.objectMap.panel.countHintHelp") };
  }
  if (legend.decision === "SEGMENTS") {
    return {
      value: `${legend.segments.length} · ${shares}${legend.distinct ? "" : ` · ${t("research.exec.objectMap.panel.segmentsOverlap")}`}`,
      help: tv("research.exec.objectMap.panel.countSegmentsHelp", { membership: Math.round(100 * (rules.colour_membership ?? 0.8)) }),
    };
  }
  return legend.reason === "TOO_FEW_RESPONDENTS"
    ? { value: t("research.exec.objectMap.panel.countTooFew"), help: tv("research.exec.objectMap.panel.countTooFewHelp", { people: rules.min_respondents ?? 30, ratings: rules.min_ratings ?? 5 }) }
    : { value: t("research.exec.objectMap.panel.countNone"), help: t("research.exec.objectMap.panel.countNoneHelp") };
}

/** How the set's respondents sit on the map, as the panel's map info on Respondenti: the share
 *  and number clearly placed (they build the terrain), weakly placed (faint dots) and not placed. */
function RespondentCounts({ map, segments }: { map: ObjectMapArtifact; segments: SegmentLegend | null }) {
  const r = storedRespondents(map);
  if (!r) return null;
  const c = r.counts, all = Math.max(c.PLACED + c.FADED + c.NOT_PLACED, 1);
  const share = (n: number) => `${Math.round((100 * n) / all)} %`;
  const count = (n: number) => n.toLocaleString("cs-CZ");
  const note = respondentNote(map);
  const ratings = map.spec.respondent_map?.min_ratings ?? 3;
  const row = (key: string, value: string, help: string) => (
    <div title={help}><span className="font-semibold">{t(`research.exec.objectMap.panel.${key}`)}:</span> {value}</div>
  );
  return (
    <div className="flex flex-col gap-1 rounded-[10px] border border-border bg-surface-raised p-4 text-xs" data-testid="object-map-respondent-counts">
      <h4 className="font-semibold">{t("research.exec.objectMap.panel.mapRespondents")}</h4>
      {/* Only a map whose respondents can be placed is "indicative"; otherwise the map's own note says nobody is. */}
      {note?.placeable ? row("countIndicative", tv("research.exec.objectMap.panel.countIndicativeValue", { n: note.objects, min: note.minObjects }), t("research.exec.objectMap.panel.countIndicativeHelp")) : null}
      {row("countPlaced", tv("research.exec.objectMap.panel.countPlacedValue", { share: share(c.PLACED), n: count(c.PLACED) }), t("research.exec.objectMap.panel.countPlacedHelp"))}
      {row("countFaded", tv("research.exec.objectMap.panel.countFadedValue", { share: share(c.FADED), n: count(c.FADED) }), t("research.exec.objectMap.panel.countFadedHelp"))}
      {c.NOT_PLACED ? row("countNotPlaced", count(c.NOT_PLACED), tv("research.exec.objectMap.panel.countNotPlacedHelp", { ratings })) : null}
      {segments ? (() => { const s = segmentsRow(segments, map); return <div data-testid="object-map-segments-row">{row("countSegments", s.value, s.help)}</div>; })() : null}
    </div>
  );
}

/** A label with its meaning behind an ⓘ, as the panel's detail labels (`mi1910`). */
function Tip({ label, help }: { label: string; help: string }) {
  return (
    <span>
      {label}{" "}
      <details className="inline">
        <summary className="inline cursor-pointer list-none opacity-60 [&::-webkit-details-marker]:hidden" title={t("research.exec.objectMap.panel.infoTip")} aria-label={t("research.exec.objectMap.panel.infoTip")}>ⓘ</summary>
        <span className="mt-1 block text-[11px] font-normal leading-[1.4]">{help}</span>
      </details>
    </span>
  );
}

function Fact({ label, help, value, note }: { label: string; help?: string; value: string; note?: string }) {
  return (
    <div className="rounded-[6px] border border-border bg-surface p-[7px]">
      <small className="mb-0.5 block text-[9.5px] text-ink-muted">{help ? <Tip label={label} help={help} /> : label}</small>
      <strong className="text-[15px] tabular-nums">{value}</strong>
      {note ? <small className="block text-[9.5px] text-ink-muted">{note}</small> : null}
    </div>
  );
}

function DetailCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4 text-xs" data-testid="object-map-detail">
      <h4 className="font-semibold">{title}</h4>
      {children}
    </div>
  );
}

const DETAIL_HEAD = "mt-1 text-xs font-semibold";
const signed = (v: number) => (v >= 0 ? "+" : "") + num(v, 2);
/** Whether a relation is the pair of i and j, whichever end it names first (the canvas names the line's own). */
const isPair = (r: [number, number] | null, i: number, j: number) => !!r && ((r[0] === i && r[1] === j) || (r[0] === j && r[1] === i));

/** The panel's object detail (`objectDetail66`): the selected relation, then the object's numbers
 *  and its strongest reliable relations, all as the map stores them. */
function ObjectCard({ battery, map, selected, relation, onRelation }: { battery: BatteryWithMaps; map: ObjectMapArtifact; selected: number; relation: [number, number] | null; onRelation: (j: number) => void }) {
  const p = "research.exec.objectMap.panel";
  if (selected < 0) {
    return <DetailCard title={t(`${p}.objectDetailTitle`)}><p className="py-4 text-center text-ink-muted">{t(`${p}.objectDetailEmpty`)}</p></DetailCard>;
  }
  const o = objectDetail(battery, map, selected);
  // The Lead's name for the card's relation (lib/artifacts/sociomap.ts); the object's one element is its list button.
  const pair = relation ? pairTarget(battery.battery_id, map.object_ids[relation[0]], map.object_ids[relation[1]]) : null;
  return (
    <DetailCard title={t(`${p}.objectDetailTitle`)}>
      {/* Announced when a relation opens from the list below: it appears above the button pressed. */}
      <div aria-live="polite">
        {relation ? <div data-aia={pair ?? undefined}><RelationBlock detail={relationDetail(battery, map, relation[0], relation[1])} /></div> : null}
      </div>
      <b className="text-sm" data-testid="object-map-detail-label">{o.label}</b>
      {o.primary ? null : <p className="text-[10.5px] text-ink-muted">{t(`${p}.detailSecondary`)}</p>}
      <div className="grid grid-cols-2 gap-1.5">
        <Fact label={t(`${p}.detailHeight`)} help={t(`${p}.detailHeightHelp`)} value={panelNumber(o.height === null ? null : originalRating(o.height, battery.rating_scale) ?? o.height)} />
        <Fact label={t(`${p}.detailConnectedness`)} help={t(`${p}.detailConnectednessHelp`)} value={panelNumber(o.connectedness)} />
        {o.alignment !== null ? <Fact label={t(`${p}.detailAlignment`)} help={t(`${p}.detailAlignmentHelp`)} value={(o.alignment >= 0 ? "+" : "") + panelNumber(o.alignment)} /> : null}
      </div>
      <h5 className={DETAIL_HEAD}><Tip label={t(`${p}.detailRelations`)} help={t(`${p}.detailRelationsHelp`)} /></h5>
      {o.relations.length ? (
        <div className="grid gap-[3px]" data-testid="object-map-detail-relations">
          {/* Each relation opens the pair's detail, as a click on its line does: the canvas is no keyboard's. */}
          {o.relations.map((x) => (
            <button key={x.id} type="button" aria-pressed={isPair(relation, selected, x.j)} onClick={() => onRelation(x.j)}
              className="flex w-full justify-between gap-2.5 border-b border-border py-[5px] text-left text-[10.5px] hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring aria-pressed:font-semibold">
              <span className="min-w-0 text-ink-muted">{x.label}</span>{" "}<b className="tabular-nums">{signed(x.r)}</b>
              <span className="sr-only">{tv(`${p}.relationShow`, { a: o.label, b: x.label })}</span>
            </button>
          ))}
        </div>
      ) : <p className="text-[10.5px] text-ink-muted">{t(`${p}.detailNoRelation`)}</p>}
      {o.primary ? null : (
        <>
          <h5 className={DETAIL_HEAD}>{t(`${p}.detailPlacement`)}</h5>
          <Fact label={t(`${p}.detailBasis`)} value={o.basis === null ? t(`${p}.detailBasisNone`) : num(o.basis, 2)} />
          <p className="text-[10.5px] text-ink-muted">{t(`${p}.detailBasisNote`)}</p>
        </>
      )}
    </DetailCard>
  );
}

/** The panel's "Vybraný vztah" (`relationHtml66`) without the p-value and the noise level, which
 *  the map does not store (nor, under this estimator, an interval: "95 % —" as the panel prints a
 *  missing one); the verdict reads the stored status. "zřetelný" from |r| 0,3, as the panel words it. */
function RelationBlock({ detail: d }: { detail: ReturnType<typeof relationDetail> }) {
  const p = "research.exec.objectMap.panel";
  let verdict: ReactNode;
  if (d.r === null) verdict = tv(`${p}.${d.verdict === "noSpread" ? "relationNoSpread" : "relationFewRatings"}`, { n: d.n ?? 0 });
  else {
    const word = t(`${p}.${Math.abs(d.r) >= 0.3 ? "relationClear" : "relationSlight"}`), sign = t(`${p}.${d.r >= 0 ? "relationPositive" : "relationNegative"}`);
    verdict = d.verdict === "reliable"
      ? (d.noiseRule ? <><b>{tv(`${p}.relationReliableNoise`, { word, sign })}</b> {t(`${p}.relationReliableNoiseText`)}</> : <><b>{t(`${p}.relationReliable`)}</b> ({word} {sign}).</>)
      : <><b>{t(`${p}.relationWeak`)}</b> {t(`${p}.${d.noiseRule ? "relationWeakNoiseText" : "relationWeakText"}`)}</>;
  }
  return (
    <div className="flex flex-col gap-1.5 rounded-[7px] border border-border bg-surface p-2" data-testid="object-map-detail-relation">
      <h5 className="text-xs font-semibold">{t(`${p}.relationTitle`)}</h5>
      <b>{d.a} – {d.b}</b>
      {d.r !== null ? (
        <div className="grid grid-cols-2 gap-1.5">
          <Fact label={t(`${p}.relationR`)} help={t(`${p}.relationRHelp`)} value={signed(d.r)} note={d.interval ? tv(`${p}.relationInterval`, { lo: signed(d.interval[0]), hi: signed(d.interval[1]) }) : t(`${p}.relationNoInterval`)} />
          <Fact label={t(`${p}.relationN`)} help={tv(`${p}.relationNHelp`, { total: d.respondents })} value={d.n === null ? "—" : String(d.n)} />
        </div>
      ) : null}
      <p className="text-[10.5px] leading-[1.45] text-ink-muted" data-testid="object-map-detail-verdict">{verdict}</p>
    </div>
  );
}

/** The panel's respondent detail (`personDetail66`): where the respondent sits and why, how well
 *  the map fits them, and their taste segment. The stored map holds no profile and no answers. */
function PersonCard({ detail: d }: { detail: ReturnType<typeof respondentDetail> }) {
  const p = "research.exec.objectMap.panel";
  if (!d) return <DetailCard title={t(`${p}.personTitle`)}><p className="py-4 text-center text-ink-muted">{t(`${p}.personEmpty`)}</p></DetailCard>;
  return (
    <DetailCard title={t(`${p}.personTitle`)}>
      <div className="flex items-center gap-[9px]">
        <div aria-hidden className="grid h-[46px] w-[46px] flex-none place-items-center rounded-full bg-[#1d2b33] font-extrabold text-white">{d.id.slice(-2)}</div>
        <div>
          <b data-testid="object-map-detail-person">{d.id}</b>
          <p className="text-[10.5px] leading-[1.45] text-ink-muted">
            {t(`${p}.personPosition`)}
            {d.explained !== null ? <><br />{tv(`${p}.personExplained`, { pct: d.explained })}{d.faded ? ` · ${t(`${p}.personFaded`)}` : ""}</> : null}
            {d.segment !== null ? <><br />{d.segment >= 0 ? tv(`${p}.personSegment`, { n: d.segment + 1 }) : t(`${p}.personNoSegment`)}</> : null}
          </p>
        </div>
      </div>
    </DetailCard>
  );
}
