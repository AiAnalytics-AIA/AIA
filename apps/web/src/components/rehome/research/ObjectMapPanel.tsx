"use client";

// The signed-off map (aia-sociomap-5), drawn as the AIA panel draws it (plan sociomap-5-web). The
// canvas drawing is the panel's (object-map-panel.ts); the overlays around it keep the map clear
// (artifact-sociomap SOC13): one bar top left (Objekty / Respondenti, Nastavení mapy and Nástroje as
// popovers under it, the ⓘ map information with the map's quality, the display filter as a chip),
// one view rail bottom right (zoom, centre, 2D / 3D, full screen), the legend as a chip bottom left,
// and Správa objektů and the detail as the tabs of one side sheet BESIDE the map: the canvas
// re-frames to the width left, so nothing lies over it. Správa objektů also makes every object
// reachable by keyboard and screen reader. While the map is dragged, rotated or zoomed the overlays
// fade; keys O / R / L / I / F / + / − / 0 do what the controls do, Escape closes in order.
//
// The map draws the stored artifact and computes nothing methodological; camera, scale mode,
// relation display, selection, hover and the overlays are presentation state. What the map says
// about itself (the weakly determined banner, the uncertainty circle, the notes) is drawn over it
// from the stored credibility, and the objects nobody rated are named in the object list. A map
// that stores its respondent map switches to it: the stored density of the clearly placed
// respondents as the terrain, every placed respondent as a dot (a weakly placed one faint), the
// objects as markers, its own legend, note and counts, the taste segments' colours, legend and
// hint. The detail shows what the map stores (the panel's p-value, noise level and the
// respondent's answers are not stored, so not shown). Export PNG saves the map as drawn with its
// legend card.
//
// As the panel embedded in a page: the wheel zooms while the pointer is over the map and scrolls the
// page elsewhere; ⛶ opens the map in the browser's full screen (the panel's `socioFullscreen66`).

import "./object-map-windows.css";
import { type PointerEvent, type ReactNode, useEffect, useId, useMemo, useRef, useState } from "react";
import { t, tv } from "@/i18n/t";
import { objectTarget, pairTarget } from "@/lib/artifacts/sociomap";
import { LEAD_REVEAL } from "@/lib/lead";
import { MAP_REGISTERS, type MapRegister, displayChanges, stageHeight } from "@/lib/sociomap-display";
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

/** The work windows share one place (the panel's `panel27`): one open at a time. */
type WorkWindow = "settings" | "tools" | "objects";

// The map last pressed or focused: Esc with nothing focused acts on it, not on every map on the page.
let lastStage: HTMLElement | null = null;

/** The stage's height before it is measured (stageHeight then follows the pane it is read in). */
const FIRST_HEIGHT = "min(700px, max(120px, calc(100dvh - 260px)), max(360px, 110vw))";

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
      <div className="flex min-w-0 flex-[1_1_260px] flex-col gap-3">
        <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4 text-xs" data-testid="object-map-panel-list">
          <h4 className="text-xs font-semibold">{t("research.exec.objectMap.panel.listTitle")}</h4>
          <ul className="flex flex-col">
            {objects.map((o) => (
              <li key={o.id}>
                <button type="button" disabled aria-label={tv("research.exec.objectMap.selectObject", { label: o.label })}
                  className="grid w-full grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-2 rounded px-1.5 py-[5px] text-left text-xs">
                  <span aria-hidden className="h-3 w-3 rounded-full" style={{ background: color66(o.relative ?? REL_FLOOR) }} />
                  <span className="truncate">{o.label}</span>
                  <span className="tabular-nums">{panelNumber(originalRating(o.height, battery.rating_scale) ?? o.height)}</span>
                </button>
              </li>
            ))}
          </ul>
          <NotPlaced labels={objectsNotPlaced(battery, map)} />
        </div>
        <div className="flex flex-col gap-2 rounded-[10px] border border-border bg-surface-raised p-4">{facts}</div>
      </div>
    </div>
  );
}

/** The set's objects nobody rated have no place on the map; the panel names them under its list. */
function NotPlaced({ labels }: { labels: string[] }) {
  if (!labels.length) return null;
  return <p className="text-xs leading-[17px] text-ink-muted" data-testid="object-map-unplaced-objects">{tv("research.exec.objectMap.panel.notPlaced", { labels: labels.join(", ") })}</p>;
}

type ListItem = { id: string; label: string; value: number | null; colour: string };

/** Správa objektů: every object as a button, its stored mean on the declared scale. */
function ObjectList({ battery, items, selected, notPlaced, onChoose, onHover }: {
  battery: BatteryWithMaps; items: ListItem[]; selected: number; notPlaced: string[]; onChoose?: (k: number, from: HTMLElement) => void; onHover: (k: number) => void;
}) {
  return (
    <div data-testid="object-map-panel-list">
      <h4>{t("research.exec.objectMap.panel.listTitle")}</h4>
      <ul className="omw-list">
        {items.map((n, k) => (
          <li key={n.id}>
            {/* Read only without onChoose (the respondent map), yet focusable: the Lead's object target. */}
            <button type="button" data-aia={objectTarget(battery.battery_id, n.id) ?? undefined}
              aria-pressed={onChoose ? k === selected : undefined} aria-disabled={onChoose ? undefined : true}
              onClick={(e) => onChoose?.(k, e.currentTarget)} onPointerEnter={() => onHover(k)} onPointerLeave={() => onHover(-1)}
              aria-label={onChoose ? tv("research.exec.objectMap.selectObject", { label: n.label }) : undefined}>
              <span aria-hidden className="h-3 w-3 rounded-full" style={{ background: n.colour }} />
              <span className="truncate">{n.label}</span>
              <span className="tabular-nums">{panelNumber(originalRating(n.value, battery.rating_scale) ?? n.value)}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-2"><NotPlaced labels={notPlaced} /></div>
    </div>
  );
}

/** A window section's heading with its meaning behind an ⓘ (the panel's `mi1910` in Nastavení mapy). */
function SectionHead({ label, help }: { label: string; help?: string }) {
  return <h4>{help ? <Tip label={label} help={help} /> : label}</h4>;
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
  // The open work window (one at a time), whether the detail window is open, whether the ⓘ box is.
  const [work, setWork] = useState<WorkWindow | null>(null);
  const [detail, setDetail] = useState(false);
  const [info, setInfo] = useState(false);
  // The overlays' state: the bar's popovers, the side sheet's tab and whether it is folded to its edge,
  // the legend chip, and the map moving (overlays fade while it does).
  const [menu, setMenu] = useState<null | "settings" | "tools" | "more">(null);
  const [tab, setTab] = useState<"objects" | "detail">("objects");
  const [folded, setFolded] = useState(false);
  const [legendOpen, setLegendOpen] = useState(false);
  const [moving, setMoving] = useState(false);
  const movingRef = useRef(false);
  const moveStop = useRef(0);
  const startMoving = (pause?: number) => {
    if (!movingRef.current) { movingRef.current = true; setMoving(true); }
    window.clearTimeout(moveStop.current);
    if (pause) moveStop.current = window.setTimeout(() => { movingRef.current = false; setMoving(false); }, pause);
  };
  const stopMoving = () => { window.clearTimeout(moveStop.current); if (movingRef.current) { movingRef.current = false; setMoving(false); } };
  // What opened the detail (the canvas or a list button): × gives the focus back to it.
  const detailOpener = useRef<HTMLElement | null>(null);
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
  // "Top vztahy" follows the selection, in full screen as on the page: the selected object's five
  // strongest, or the map's five strongest with nothing selected (the panel's rule).
  const pairs = useMemo(() => relationPairs(map, mode, selected).map((p) => ({ ...p, k: relationStrength(p.v, norm, strongest) })), [map, mode, selected, norm, strongest]);
  // The node size follows the mapped objects; an object nobody rated is left out of the map, as the panel counts it.
  const scale = nodeScale(map.object_ids.length);
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
      startMoving(450);
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
    if (p.mode === "rotate") { setCamera((c) => dragCamera(c, dx, dy)); startMoving(); }
    p.lastX = x; p.lastY = y;
  };
  const onUp = () => {
    stopMoving();
    const p = pointer.current;
    pointer.current = null;
    if (!p || p.moved >= CLICK_SLOP) return;
    const hit = p.mode === "select" ? p.hit : null;
    // On the respondent map a click on a dot rings that respondent and shows its profile; on the
    // object map an object or a relation line shows its detail. A click on free ground clears
    // every selection, as the panel's.
    // The detail window opens on what was hit (the panel's `openDetail1877`) and closes with the selection.
    if (hit) detailOpener.current = canvas.current;
    if (hit?.kind === "respondent") { setPerson(hit.index); setSelected(-1); setRelation(null); showDetail(); }
    else if (hit?.kind === "relation" && !people) { setSelected(hit.index); setRelation([hit.index, hit.j!]); showDetail(); }
    else if (hit?.kind === "object" && !people) { setSelected(hit.index); setRelation(null); showDetail(); }
    else if (!hit) { setSelected(-1); setPerson(-1); setRelation(null); setDetail(false); }
  };

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
  // Each map opens with nothing selected: an object chosen on one is not the other's, nor a ringed
  // respondent. The respondent map has no relation display, so Nástroje closes there.
  const showMap = (next: "objects" | "respondents") => {
    if (next === view) return;
    setView(next); setSelected(-1); setRelation(null); setPerson(-1); setHovered(-1); setDetail(false);
    if (next === "respondents" && menu === "tools") setMenu(null);
  };
  // What the detail now shows comes to the front, over Správa objektů the pick was made in.
  const showDetail = () => { setDetail(true); setTab("detail"); setFolded(false); setLegendOpen(false); };
  // A popover or the sheet opening folds the legend back to its chip.
  // The ⓘ box and the bar's popovers open at one place under the bar: one at a time.
  const openMenu = (next: "settings" | "tools" | "more") => { setMenu((m) => (m === next ? null : next)); setInfo(false); setLegendOpen(false); };
  const toggleInfo = () => { setInfo((v) => !v); setMenu(null); };
  const openSheet = () => { setWork("objects"); setTab("objects"); setFolded(false); setLegendOpen(false); };
  // Choosing from the list opens the object's detail; choosing it again clears it and closes the
  // detail. Selection is the object map's: on the respondent map the list only lists (see ObjectList).
  const choose = (k: number, from: HTMLElement) => {
    const next = selected === k ? -1 : k;
    setSelected(next); setRelation(null);
    if (next >= 0) showDetail(); else setDetail(false);
    if (next >= 0) detailOpener.current = from;
  };
  /** Closes the detail; with `restore`, the focus goes back to what opened it (or the canvas). */
  const closeDetail = (restore: boolean) => {
    setDetail(false);
    if (!restore) return;
    const back = detailOpener.current?.isConnected ? detailOpener.current : canvas.current;
    back?.focus({ preventScroll: true });
  };
  // The Lead points at one of this map's objects while Správa objektů is closed: open it, so the
  // object's button (its target) is there to be shown.
  useEffect(() => {
    const on = (e: Event) => {
      const target = (e as CustomEvent<unknown>).detail;
      if (nodes.some((n) => objectTarget(battery.battery_id, n.id) === target)) openSheet();
    };
    window.addEventListener(LEAD_REVEAL, on);
    return () => window.removeEventListener(LEAD_REVEAL, on);
  }, [nodes, battery.battery_id]);
  // Nastavení mapy and Nástroje are the bar's popovers (a second press closes); Správa objektů is a tab
  // of the side sheet, beside the detail.
  const openWork = (next: WorkWindow) => {
    if (next === "objects") { openSheet(); setMenu(null); return; }
    openMenu(next);
  };
  const closeWork = () => { setWork(null); if (detail) setTab("detail"); };

  // Esc closes in order (a popover, the sheet's open tab, the ⓘ box, the legend), and the map's keys do
  // what its controls do. Only on this map: a key from inside it, in its full screen, or with nothing
  // focused after it was used; never one typed in a field.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || !stage || e.ctrlKey || e.metaKey || e.altKey) return;
      const target = e.target as Element | null;
      if (target?.closest?.("input,textarea,select,[contenteditable='true']")) return;
      const loose = !target || target === document.body || target === document.documentElement;
      if (!(target && stage.contains(target)) && document.fullscreenElement !== stage && !(loose && lastStage === stage)) return;
      if (e.key === "Escape") {
        // Escape's order: a popover, then the sheet (its open tab), then the ⓘ box, then the legend.
        if (menu) { setMenu(null); stage.querySelector<HTMLElement>(".omx-bar")?.focus(); }
        else if (work || detail) { if (tab === "detail" && detail) closeDetail(Boolean(stage.querySelector(".omx-sheet")?.contains(document.activeElement))); else closeWork(); }
        else if (info) setInfo(false);
        else if (legendOpen) setLegendOpen(false);
        else return;
        e.preventDefault();
        return;
      }
      const k = e.key.toLowerCase();
      if (k === "o") showMap("objects");
      else if (k === "r" && density) showMap("respondents");
      else if (k === "l") setLegendOpen((v) => !v);
      else if (k === "i") toggleInfo();
      else if (k === "f") toggleFull();
      else if (k === "+" || k === "=") setCamera((c) => zoomCamera(c, ZOOM_IN));
      else if (k === "-") setCamera((c) => zoomCamera(c, ZOOM_OUT));
      else if (k === "0") setCamera(INITIAL_CAMERA);
      else return;
      e.preventDefault();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  // What the bar's popovers have changed against the map's opening; its filter chip names it (SOC3).
  const changes = displayChanges({ map: people ? "respondents" : "objects", norm, relations: mode });
  // "Zrušit filtr" removes its own chip: the keyboard goes back to the bar, never to the page's top.
  const dock = useRef<HTMLDivElement>(null);
  const [resets, setResets] = useState(0);
  useEffect(() => { if (resets) dock.current?.focus({ preventScroll: true }); }, [resets]);
  const resetDisplay = () => { showMap("objects"); setNorm("range"); setMode("top"); setResets((n) => n + 1); };
  // The stage fits the pane it is read in (stageHeight): the workbench's artifact pane, else the
  // window less the page's sticky header. The bar, the rail and the legend chip are on the map, so
  // nothing of the panel sits over the stage; measured again whenever the pane or the stage moves.
  const [fit, setFit] = useState<number | null>(null);
  useEffect(() => {
    if (!stage || typeof ResizeObserver === "undefined") return;
    const pane = stage.closest<HTMLElement>(".artbody");
    const measure = () => {
      const visible = pane ? Math.min(pane.clientHeight, window.innerHeight) : window.innerHeight - stickyTop();
      setFit(stageHeight(visible, 0, stage.clientWidth));
    };
    const observer = new ResizeObserver(measure);
    for (const node of [stage, pane]) if (node) observer.observe(node);
    window.addEventListener("resize", measure);
    return () => { observer.disconnect(); window.removeEventListener("resize", measure); };
  }, [stage]);

  const p = "research.exec.objectMap.panel";
  const detailTitle = t(`${p}.${people ? "personTitle" : "objectDetailTitle"}`);
  const credibility = map.credibility;
  const pill = !credibility || people ? null
    : credibility.split_half !== null
      ? (credibility.weakly_determined ? { text: t(`${p}.pillWeak`), warn: true } : { text: tv(`${p}.pillQuality`, { percent: Math.round(100 * credibility.split_half) }), warn: false })
      : credibility.weakly_determined ? { text: t(`${p}.pillNoStructure`), warn: true } : null;

  // One bar top left, one view rail bottom right, the legend as a chip bottom left, and Správa objektů
  // and the detail as tabs of one side sheet beside the map, so the canvas re-frames to what is left.
  const narrow = size.width < 460;
  const sheetOpen = work === "objects" || detail;
  const sheetTab = tab === "detail" && detail ? "detail" : work === "objects" ? "objects" : "detail";
  const quality = credibility?.split_half != null ? `${Math.round(100 * credibility.split_half)} %` : pill?.warn ? "!" : null;
  const [lo, word, hi] = legendMarks(battery, nodes.map((n) => (n.primary ? n.value : null)), norm);
  const iconBtn = (label: string, icon: ReactNode, act: () => void, pressed?: boolean, dock?: string) => (
    <button type="button" className="omx-icon" aria-label={label} title={label} aria-pressed={pressed} onClick={act} data-dock={dock}>{icon}</button>
  );
  const settingsBody = (
    <>
      {people ? null : (
        <div role="group" aria-label={t(`${p}.norm`)}>
          <SectionHead label={t(`${p}.norm`)} help={t(`${p}.normHelp`)} />
          <div className="omw-row">
            <button type="button" className="omw-btn" aria-pressed={norm === "absolute"} disabled={!stored} title={t(`${p}.absoluteHelp`)} onClick={() => setNorm("absolute")}>{t(`${p}.absolute`)}</button>
            <button type="button" className="omw-btn" aria-pressed={norm === "range"} title={t(`${p}.rangeHelp`)} onClick={() => setNorm("range")}>{t(`${p}.range`)}</button>
          </div>
        </div>
      )}
      <SectionHead label={t(`${p}.objectsSection`)} help={t(`${p}.objectsHelp`)} />
      <div className="omw-row"><button type="button" className="omw-btn" onClick={() => openWork("objects")}>{t(`${p}.objectManager`)}</button></div>
      <SectionHead label={t(`${p}.exportSection`)} help={t(`${p}.exportHelp`)} />
      <div className="omw-row"><button type="button" className="omw-btn" title={t(`${p}.exportHelp`)} onClick={exportPng}>{t(`${p}.export`)}</button></div>
    </>
  );
  const toolsBody = (
    <div role="group" aria-label={t(`${p}.relations`)}>
      <SectionHead label={t(`${p}.relations`)} />
      <div className="omw-row">
        {RELATION_MODES.map((r) => (
          <button key={r.mode} type="button" className="omw-btn" aria-pressed={mode === r.mode} title={r.help ? t(r.help) : undefined} onClick={() => setMode(r.mode)}>{t(r.label)}</button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="flex flex-col gap-3" data-testid="object-map-panel">
      <div ref={setStage} className="omw omx relative isolate w-full min-w-0 overflow-hidden bg-[#07090c] [&:fullscreen]:h-screen [&:fullscreen]:w-screen"
        data-testid="object-map-stage" data-moving={moving || undefined} style={full ? undefined : { height: fit ?? FIRST_HEIGHT }}
        onPointerDownCapture={(e) => { lastStage = e.currentTarget; }}
        onFocusCapture={(e) => { lastStage = e.currentTarget; }}>
        <div className="omx-body">
          <div className="omx-mapbox">
            <canvas ref={canvas} tabIndex={0} className="block h-full w-full cursor-grab touch-none outline-none" role="img" data-testid="object-map-canvas"
              data-camera={JSON.stringify(camera)} data-norm={norm} data-map={people ? "respondents" : "objects"} data-person={people && person >= 0 ? dots[person].id : ""}
              data-relations={people ? "" : pairs.map((q) => `${nodes[q.i].id}|${nodes[q.j].id}`).join(" ")} data-selected={selected >= 0 ? nodes[selected].id : ""} data-relation={relation ? `${nodes[relation[0]].id}|${nodes[relation[1]].id}` : ""}
              aria-label={people ? tv(`${p}.respondentCanvas`, { title: battery.title, placed: dots.length, n: nodes.length }) : tv(`${p}.canvas`, { title: battery.title, n: nodes.length })}
              aria-describedby={people ? undefined : described}
              onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={() => { pointer.current = null; stopMoving(); }} onPointerLeave={() => { if (!pointer.current) setHovered(-1); }} />
            <p id={described} className="sr-only" aria-live="polite">{tv(`${p}.relationsShown`, { count: pairs.length })}</p>

            {/* 1. One bar, one row: the map switch, Nastavení mapy, Nástroje, ⓘ with the quality, the filter chip. */}
            <div ref={dock} tabIndex={-1} className="omx-bar omx-glass focus:outline-none" role="toolbar" aria-label={t("research.exec.objectMap.controls")}>
              {density ? (
                <div className="omx-seg" role="group" aria-label={t(`${p}.mapGroup`)}>
                  <button type="button" aria-pressed={view === "objects"} title={`${t(`${p}.mapObjects`)} (O)`} onClick={() => showMap("objects")}>{t(`${p}.mapObjects`)}</button>
                  <button type="button" aria-pressed={view === "respondents"} title={`${t(`${p}.mapRespondents`)} (R)`} onClick={() => showMap("respondents")}>{t(`${p}.mapRespondents`)}</button>
                </div>
              ) : null}
              <span className="omx-sep" aria-hidden />
              {narrow ? iconBtn(t(`${p}.more`), <Ic d="M5 12h.01M12 12h.01M19 12h.01" bold />, () => openMenu("more"), menu === "more") : (
                <>
                  {iconBtn(t(`${p}.settings`), <Ic d="M4 7h10M18 7h2M4 17h4M12 17h8M14 5v4M8 15v4" />, () => openWork("settings"), menu === "settings", "settings")}
                  {people ? null : iconBtn(t(`${p}.toolsButton`), <Ic d="M5 19c4-9 10-9 14-14M5 19l3-1M5 19l1-3M19 5l-3 1M19 5l-1 3" />, () => openWork("tools"), menu === "tools", "tools")}
                </>
              )}
              <button type="button" className={`omx-icon${pill?.warn ? " is-warn" : ""}`} aria-expanded={info} aria-controls={info ? `${described}-info` : undefined}
                aria-label={pill ? tv(`${p}.infoPill`, { pill: pill.text }) : t(`${p}.info`)} title={`${t(`${p}.info`)} (I)`} onClick={toggleInfo}>
                <Ic d="M12 8h.01M11 12h1v5h1M12 3a9 9 0 100 18 9 9 0 000-18z" />{quality ? <span className="omx-badge" aria-hidden>{quality}</span> : null}
              </button>
              {/* One live region, always there, so the chip's first appearance is announced too. */}
              <span role="status" data-testid="object-map-filter-status">
                {changes.length ? (
                  <span className="omx-filter" data-testid="object-map-filter-bar" data-aia-filters={changes.map((c) => `${c.key}:${c.value}`).join(" ")}
                    title={`${t(`${p}.filterTitle`)} ${changes.map((c) => t(CHANGE_WORDS[`${c.key}:${c.value}`]!)).join(", ")}. ${t(`${p}.filterUnchanged`)}`}>
                    <b>{t(`${p}.filterChip`)}</b> {changes.map((c) => t(CHANGE_WORDS[`${c.key}:${c.value}`]!)).join(", ")}<span className="sr-only">. {t(`${p}.filterUnchanged`)}</span>
                    <button type="button" aria-label={t(`${p}.filterReset`)} title={t(`${p}.filterReset`)} onClick={resetDisplay}>×</button>
                  </span>
                ) : null}
              </span>
            </div>

            {menu === "more" ? (
              <div className="omx-pop omx-glass-light" role="menu" aria-label={t(`${p}.more`)}>
                <button type="button" role="menuitem" className="omx-menuitem" onClick={() => openMenu("settings")}>{t(`${p}.settings`)}</button>
                {people ? null : <button type="button" role="menuitem" className="omx-menuitem" onClick={() => openMenu("tools")}>{t(`${p}.toolsButton`)}</button>}
              </div>
            ) : null}
            {menu === "settings" ? <div className="omx-pop omx-glass-light" role="dialog" aria-label={t(`${p}.settings`)}>{settingsBody}</div> : null}
            {menu === "tools" && !people ? <div className="omx-pop omx-glass-light" role="dialog" aria-label={t(`${p}.toolsTitle`)}>{toolsBody}</div> : null}
            {info ? (
              <div id={`${described}-info`} className="omx-pop omx-glass-light omx-pop--info" role="region" aria-label={t(`${p}.info`)} data-testid="object-map-info">
                <b>{battery.title}</b>
                {people ? <RespondentCounts map={map} segments={segments} /> : null}
                <QualityRows map={map} />
                <div className="omw-pop-facts">{facts}</div>
                <Registers />
              </div>
            ) : null}

            {/* 2. The view rail, bottom right: zoom, fit, 2D / 3D, full screen. */}
            <div className="omx-rail omx-glass" role="group" aria-label={t(`${p}.tools`)}>
              <button type="button" className="omx-icon" title={`${t(`${p}.zoomIn`)} (+)`} aria-label={t(`${p}.zoomIn`)} onClick={() => setCamera((c) => zoomCamera(c, ZOOM_IN))}><Ic d="M12 5v14M5 12h14" /></button>
              <button type="button" className="omx-icon" title={`${t(`${p}.zoomOut`)} (−)`} aria-label={t(`${p}.zoomOut`)} onClick={() => setCamera((c) => zoomCamera(c, ZOOM_OUT))}><Ic d="M5 12h14" /></button>
              <span className="omx-hair" aria-hidden />
              <button type="button" className="omx-icon" title={`${t(`${p}.center`)} (0)`} aria-label={t(`${p}.center`)} onClick={() => setCamera(INITIAL_CAMERA)}><Ic d="M12 12h.01M12 5a7 7 0 100 14 7 7 0 000-14zM12 2v3M12 19v3M2 12h3M19 12h3" /></button>
              <span className="omx-hair" aria-hidden />
              <div className="omx-dim" role="group" aria-label={t(`${p}.dimension`)}>
                <button type="button" aria-pressed={fromAbove} title={t(`${p}.top`)} aria-label={t(`${p}.top`)} onClick={() => setCamera((c) => topCamera(c, size.width, size.height))}>2D</button>
                <button type="button" aria-pressed={!fromAbove} title={t(`${p}.three`)} aria-label={t(`${p}.three`)} onClick={() => setCamera(camera3d)}>3D</button>
              </div>
              <span className="omx-hair" aria-hidden />
              <button type="button" className="omx-icon" title={`${t(`${p}.fullscreen`)} (F)`} aria-label={t(`${p}.fullscreen`)} aria-pressed={full} onClick={toggleFull}><Ic d={full ? "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" : "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"} /></button>
            </div>

            {/* 3. The legend: a chip, opened on demand; closed again when a sheet or a popover opens. */}
            {legendOpen ? (
              <div className="omx-legendwrap">
                {people ? <DensityLegend segments={segments} /> : <Legend battery={battery} values={nodes.map((n) => (n.primary ? n.value : null))} norm={norm} strongest={strongest} />}
                <button type="button" className="omx-legendclose" aria-label={t(`${p}.legendClose`)} title={`${t(`${p}.legendClose`)} (L)`} onClick={() => setLegendOpen(false)}>×</button>
              </div>
            ) : (
              <button type="button" className="omx-legendchip omx-glass" aria-expanded={false} title={`${t(`${p}.legend`)} (L)`} onClick={() => setLegendOpen(true)}>
                {people && segments?.decision === "SEGMENTS"
                  ? <><span className="omx-chiplabel">{t(`${p}.legendGroups`)}</span>{segments.segments.map((g, k) => <span key={k} className="omx-swatch" style={{ background: SEGMENT_COLOURS[k % SEGMENT_COLOURS.length] }} title={sharePercent(g.share)} />)}</>
                  : people ? <><span className="omx-chiplabel">{t(`${p}.legendDensity`)}</span><span className="omx-ramp" aria-hidden /></>
                    : <><span className="omx-chiplabel">{tv(`${p}.legendHeight`, { lo, hi })}</span><span className="omx-ramp" aria-hidden /><span className="sr-only">{word}</span></>}
              </button>
            )}
          </div>

          {/* 4. Správa objektů and the detail: one side sheet with two tabs, foldable to its edge. */}
          {sheetOpen ? (
            <div role="group" className={`omx-sheet${folded ? " is-folded" : ""}`} aria-label={sheetTab === "detail" ? detailTitle : t(`${p}.objectManager`)} data-testid="object-map-sheet">
              {folded ? (
                <button type="button" className="omx-handle" aria-label={t(`${p}.sheetUnfold`)} title={t(`${p}.sheetUnfold`)} onClick={() => setFolded(false)}>‹</button>
              ) : (
                <>
                  <div className="omx-sheethead">
                    <div className="omx-tabs" role="tablist" aria-label={t(`${p}.sheet`)}>
                      <button type="button" role="tab" id={`${described}-tab-objects`} aria-controls={`${described}-sheet`} aria-selected={sheetTab === "objects"} onClick={() => { setWork("objects"); setTab("objects"); }}>{t(`${p}.sheetObjects`)}</button>
                      <button type="button" role="tab" id={`${described}-tab-detail`} aria-controls={`${described}-sheet`} aria-selected={sheetTab === "detail"} disabled={!detail} onClick={() => setTab("detail")}>{t(people ? `${p}.sheetRespondent` : `${p}.sheetDetail`)}</button>
                    </div>
                    <button type="button" className="omx-icon omx-icon--sm" aria-label={t(`${p}.sheetFold`)} title={t(`${p}.sheetFold`)} onClick={() => setFolded(true)}>›</button>
                    <button type="button" className="omx-icon omx-icon--sm" aria-label={tv(`${p}.closeWindow`, { title: sheetTab === "detail" ? detailTitle : t(`${p}.objectManager`) })} title={`${t(`${p}.sheetClose`)} (Esc)`}
                      onClick={() => { if (sheetTab === "detail") { closeDetail(true); if (work !== "objects") setTab("objects"); } else closeWork(); }}>×</button>
                  </div>
                  <div className="omx-sheetbody" id={`${described}-sheet`} role="tabpanel" aria-labelledby={`${described}-tab-${sheetTab}`} data-testid={sheetTab === "detail" ? "object-map-detail" : undefined}>
                    {sheetTab === "detail" ? <h3 className="omx-sheettitle">{detailTitle}</h3> : null}
                    {sheetTab === "objects" ? (
                      <ObjectList battery={battery} selected={selected} onChoose={people ? undefined : choose} onHover={setHovered} notPlaced={notPlaced}
                        items={nodes.map((n, k) => ({ id: n.id, label: n.label, value: n.value, colour: n.primary ? color66(tones[k]) : SECONDARY }))} />
                    ) : people
                      ? <PersonCard detail={person >= 0 ? respondentDetail(map, dots[person].id) : null} />
                      : <ObjectCard battery={battery} map={map} selected={selected} relation={relation}
                        onRelation={(j) => setRelation((r) => (isPair(r, selected, j) ? null : [selected, j]))} />}
                  </div>
                </>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** A line icon on a 24 px grid. */
function Ic({ d, bold = false }: { d: string; bold?: boolean }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={bold ? 3 : 1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>;
}

/** A number as the panel's `fmt66` prints it (two decimals below 10, one below 100), in Czech. */
function panelNumber(v: number | null): string {
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
    <div className="omw-legend absolute bottom-[14px] left-[17px] z-[5] w-[260px] max-w-[calc(100%-34px)] rounded-[8px] border border-white/[.13] bg-[rgba(8,11,15,.75)] px-3 py-2.5 text-white backdrop-blur-[8px]" data-testid="object-map-legend">
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
    <div className="omw-legend absolute bottom-[14px] left-[17px] z-[5] w-[260px] max-w-[calc(100%-34px)] rounded-[8px] border border-white/[.13] bg-[rgba(8,11,15,.75)] px-3 py-2.5 text-white backdrop-blur-[8px]" data-testid="object-map-legend">
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

function segmentLines(legend: SegmentLegend): SegmentLines {
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
  // The panel singles out too few respondents and too few objects; every other reason reads as no clear segments.
  if (legend.reason === "TOO_FEW_OBJECTS") return { title: null, rows: [], foot: tv("research.exec.objectMap.panel.segmentsTooFewObjects", { n: legend.minRatings }) };
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
function segmentsRow(legend: SegmentLegend, map: ObjectMapArtifact): { value: string; help: string } {
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
  if (legend.reason === "TOO_FEW_OBJECTS") {
    return { value: tv("research.exec.objectMap.panel.countTooFewObjects", { n: legend.minRatings }), help: tv("research.exec.objectMap.panel.countTooFewObjectsHelp", { n: legend.minRatings }) };
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
    <div data-testid="object-map-respondent-counts">
      {/* Only a map whose respondents can be placed is "indicative"; otherwise the map's own note says nobody is. */}
      {note?.placeable ? row("countIndicative", tv("research.exec.objectMap.panel.countIndicativeValue", { n: note.objects, min: note.minObjects }), t("research.exec.objectMap.panel.countIndicativeHelp")) : null}
      {row("countPlaced", tv("research.exec.objectMap.panel.countPlacedValue", { share: share(c.PLACED), n: count(c.PLACED) }), t("research.exec.objectMap.panel.countPlacedHelp"))}
      {row("countFaded", tv("research.exec.objectMap.panel.countFadedValue", { share: share(c.FADED), n: count(c.FADED) }), t("research.exec.objectMap.panel.countFadedHelp"))}
      {c.NOT_PLACED ? row("countNotPlaced", count(c.NOT_PLACED), tv("research.exec.objectMap.panel.countNotPlacedHelp", { ratings })) : null}
      {segments ? (() => { const s = segmentsRow(segments, map); return <div data-testid="object-map-segments-row">{row("countSegments", s.value, s.help)}</div>; })() : null}
    </div>
  );
}

/** The map's own statements in the ⓘ box (the panel's `aiaMapLines1910`), from the stored
 *  credibility and sparse-design flag: the split-half quality and a sparse design. */
function QualityRows({ map }: { map: ObjectMapArtifact }) {
  const p = "research.exec.objectMap.panel";
  const c = map.credibility;
  const row = (key: string, value: string, help: string) => (
    <div title={help}><span className="font-semibold">{t(`${p}.${key}`)}:</span> {value}</div>
  );
  let quality: ReactNode = null;
  if (c && c.split_half !== null) {
    const percent = Math.round(100 * c.split_half);
    quality = row("quality", tv(`${p}.${c.weakly_determined ? "qualityWeakValue" : "qualityValue"}`, { percent }), tv(`${p}.qualityHelp`, { threshold: Math.round(100 * c.threshold) }));
  } else if (c?.weakly_determined) quality = row("quality", t(`${p}.qualityNoneValue`), t(`${p}.qualityNoneHelp`));
  return (
    <div data-testid="object-map-quality">
      {quality}
      {map.sparse_design?.flag ? row("sparse", t(`${p}.sparseValue`), t(`${p}.sparseHelp`)) : null}
    </div>
  );
}

/** A label with its meaning behind an ⓘ, as the panel's detail labels (`mi1910`). */
function Tip({ label, help }: { label: string; help: string }) {
  return (
    <span>
      {label}{" "}
      <details className="inline">
        <summary className="inline cursor-pointer list-none font-normal opacity-60 [&::-webkit-details-marker]:hidden" title={t("research.exec.objectMap.panel.infoTip")} aria-label={t("research.exec.objectMap.panel.infoTip")}>ⓘ</summary>
        <span className="mt-1 block text-[11px] font-normal normal-case leading-[1.4] tracking-normal">{help}</span>
      </details>
    </span>
  );
}

function Fact({ label, help, value, note }: { label: string; help?: string; value: string; note?: string }) {
  return (
    <div className="omw-fact">
      <small>{help ? <Tip label={label} help={help} /> : label}</small>
      <strong>{value}</strong>
      {note ? <small>{note}</small> : null}
    </div>
  );
}

const signed = (v: number) => (v >= 0 ? "+" : "") + num(v, 2);
/** Whether a relation is the pair of i and j, whichever end it names first (the canvas names the line's own). */
const isPair = (r: [number, number] | null, i: number, j: number) => !!r && ((r[0] === i && r[1] === j) || (r[0] === j && r[1] === i));

/** The panel's object detail (`objectDetail66`): the selected relation, then the object's numbers
 *  and its strongest reliable relations, all as the map stores them. */
function ObjectCard({ battery, map, selected, relation, onRelation }: { battery: BatteryWithMaps; map: ObjectMapArtifact; selected: number; relation: [number, number] | null; onRelation: (j: number) => void }) {
  const p = "research.exec.objectMap.panel";
  if (selected < 0) return <p className="omw-tip py-4 text-center">{t(`${p}.objectDetailEmpty`)}</p>;
  const o = objectDetail(battery, map, selected);
  // The Lead's name for the card's relation (lib/artifacts/sociomap.ts); the object's one element is its list button.
  const pair = relation ? pairTarget(battery.battery_id, map.object_ids[relation[0]], map.object_ids[relation[1]]) : null;
  return (
    <>
      {/* Announced when a relation opens from the list below: it appears above the button pressed. */}
      <div aria-live="polite">
        {relation ? <div data-aia={pair ?? undefined}><RelationBlock detail={relationDetail(battery, map, relation[0], relation[1])} /></div> : null}
      </div>
      <b className="omw-detail-label" data-testid="object-map-detail-label">{o.label}</b>
      {o.primary ? null : <p className="omw-tip mb-2">{t(`${p}.detailSecondary`)}</p>}
      <div className="omw-facts">
        <Fact label={t(`${p}.detailHeight`)} help={t(`${p}.detailHeightHelp`)} value={panelNumber(o.height === null ? null : originalRating(o.height, battery.rating_scale) ?? o.height)} />
        <Fact label={t(`${p}.detailConnectedness`)} help={t(`${p}.detailConnectednessHelp`)} value={panelNumber(o.connectedness)} />
        {o.alignment !== null ? <Fact label={t(`${p}.detailAlignment`)} help={t(`${p}.detailAlignmentHelp`)} value={(o.alignment >= 0 ? "+" : "") + panelNumber(o.alignment)} /> : null}
      </div>
      <h3 className="omw-h3 !mt-[15px]"><Tip label={t(`${p}.detailRelations`)} help={t(`${p}.detailRelationsHelp`)} /></h3>
      {o.relations.length ? (
        <div data-testid="object-map-detail-relations">
          {/* Each relation opens the pair's detail, as a click on its line does: the canvas is no keyboard's. */}
          {o.relations.map((x) => (
            <button key={x.id} type="button" className="omw-answer" aria-pressed={isPair(relation, selected, x.j)} onClick={() => onRelation(x.j)}>
              <span>{x.label}</span>{" "}<b>{signed(x.r)}</b>
              <span className="sr-only">{tv(`${p}.relationShow`, { a: o.label, b: x.label })}</span>
            </button>
          ))}
        </div>
      ) : <p className="omw-tip">{t(`${p}.detailNoRelation`)}</p>}
      {o.primary ? null : (
        <>
          <h3 className="omw-h3 !mt-[15px]">{t(`${p}.detailPlacement`)}</h3>
          <Fact label={t(`${p}.detailBasis`)} value={o.basis === null ? t(`${p}.detailBasisNone`) : num(o.basis, 2)} />
          <p className="omw-tip mt-2">{t(`${p}.detailBasisNote`)}</p>
        </>
      )}
    </>
  );
}

/** The panel's "Vybraný vztah" (`relationHtml66`) without the p-value and the noise level, which
 *  the map does not store (nor, under this estimator, an interval: "95 % —" as the panel prints a
 *  missing one); the verdict reads the stored status. "zřetelný" from the declared |r| (Metodika; 0,3 as the panel). */
function RelationBlock({ detail: d }: { detail: ReturnType<typeof relationDetail> }) {
  const p = "research.exec.objectMap.panel";
  let verdict: ReactNode;
  if (d.r === null) verdict = tv(`${p}.${d.verdict === "noSpread" ? "relationNoSpread" : "relationFewRatings"}`, { n: d.n ?? 0 });
  else {
    const word = t(`${p}.${Math.abs(d.r) >= d.clearFrom ? "relationClear" : "relationSlight"}`), sign = t(`${p}.${d.r >= 0 ? "relationPositive" : "relationNegative"}`);
    verdict = d.verdict === "reliable"
      ? (d.noiseRule ? <><b>{tv(`${p}.relationReliableNoise`, { word, sign })}</b> {t(`${p}.relationReliableNoiseText`)}</> : <><b>{t(`${p}.relationReliable`)}</b> ({word} {sign}).</>)
      : <><b>{t(`${p}.relationWeak`)}</b> {t(`${p}.${d.noiseRule ? "relationWeakNoiseText" : "relationWeakText"}`)}</>;
  }
  return (
    <div className="omw-rel" data-testid="object-map-detail-relation">
      <h3 className="omw-h3">{t(`${p}.relationTitle`)}</h3>
      <b>{d.a} – {d.b}</b>
      {d.r !== null ? (
        <div className="omw-facts">
          <Fact label={t(`${p}.relationR`)} help={t(`${p}.relationRHelp`)} value={signed(d.r)} note={d.interval ? tv(`${p}.relationInterval`, { lo: signed(d.interval[0]), hi: signed(d.interval[1]) }) : t(`${p}.relationNoInterval`)} />
          <Fact label={t(`${p}.relationN`)} help={tv(`${p}.relationNHelp`, { total: d.respondents })} value={d.n === null ? "—" : String(d.n)} />
        </div>
      ) : null}
      <p className="omw-tip" data-testid="object-map-detail-verdict">{verdict}</p>
    </div>
  );
}

/** The panel's respondent detail (`personDetail66`): where the respondent sits and why, how well
 *  the map fits them, and their taste segment. The stored map holds no profile and no answers. */
function PersonCard({ detail: d }: { detail: ReturnType<typeof respondentDetail> }) {
  const p = "research.exec.objectMap.panel";
  if (!d) return <p className="omw-tip py-4 text-center">{t(`${p}.personEmpty`)}</p>;
  return (
    <div className="flex items-center gap-[9px]">
      <div aria-hidden className="grid h-[46px] w-[46px] flex-none place-items-center rounded-full bg-[#1d2b33] font-extrabold text-white">{d.id.slice(-2)}</div>
      <div>
        <b data-testid="object-map-detail-person">{d.id}</b>
        <p className="omw-tip">
          {t(`${p}.personPosition`)}
          {d.explained !== null ? <><br />{tv(`${p}.personExplained`, { pct: d.explained })}{d.faded ? ` · ${t(`${p}.personFaded`)}` : ""}</> : null}
          {d.segment !== null ? <><br />{d.segment >= 0 ? tv(`${p}.personSegment`, { n: d.segment + 1 }) : t(`${p}.personNoSegment`)}</> : null}
        </p>
      </div>
    </div>
  );
}

const CHANGE_WORDS: Record<string, string> = {
  "map:respondents": "research.exec.objectMap.panel.filterMapRespondents",
  "norm:absolute": "research.exec.objectMap.panel.filterNormAbsolute",
  "relations:selected": "research.exec.objectMap.panel.filterRelationsSelected",
  "relations:all": "research.exec.objectMap.panel.filterRelationsAll",
};


/** The four kinds of content around a map (the V2 prototype's "Co je co"), in the map's ⓘ box: the frozen
 *  result, the display, a labelled interpretation, external context. Static words: what each may change. */
function Registers() {
  const p = "research.exec.objectMap.panel";
  const name: Record<MapRegister, string> = { computed: "Computed", display: "Display", interpretation: "Interpretation", external: "External" };
  return (
    <div className="omw-pop-facts" data-testid="object-map-registers">
      <b>{t(`${p}.registersTitle`)}</b>
      <dl className="grid gap-0.5">
        {MAP_REGISTERS.map((r) => (
          <div key={r} className="flex flex-wrap gap-x-1.5" data-register={r}>
            <dt className="font-semibold">{t(`${p}.register${name[r]}`)}</dt>
            <dd>{t(`${p}.register${name[r]}Text`)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** What the page's sticky headers cover at the window's top (the shell's header from lg up). */
function stickyTop(): number {
  let top = 0;
  for (const h of document.querySelectorAll("header")) {
    if (getComputedStyle(h).position === "sticky") top = Math.max(top, h.getBoundingClientRect().height);
  }
  return top;
}
