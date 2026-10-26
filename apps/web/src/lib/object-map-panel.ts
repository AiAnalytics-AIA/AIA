// The signed-off map (aia-sociomap-5) drawn as the AIA panel draws it (plan sociomap-5-web,
// chunk 2): a port of the panel's own drawing in NPC_Panel/ui_app.html (`color66`, `blend66`,
// `normalizer66`, `terrainAt66`, `projection66`, `drawSlab66`, the terrain
// triangles of `draw66`, `drawContours66`, the relation curves of `relationGeometry66` and
// `relationLine66`, `topRelationPairs66` / `relationPairs66`, `drawObjects66`, `placeLabels66`, the
// camera of `socioCam66` and the pointer handlers). Each function keeps the panel's constants and
// order of operations, so the same stored map draws the same picture; the unit tests pin them to
// values the panel's own functions return.
//
// The renderer computes no methodological number and no surface. It draws the STORED map: the
// objects' ruler positions, the two stored framed terrain grids (Relativni: the relative hill
// heights; Absolutni: the 0-1 means on the declared scale) and the stored relative heights for the
// node colours. Ruler units become the panel's frame units exactly as the panel's frame does,
// frame = (ruler - centre) * 62 / half_extent, so the stored grids span the panel's +-62. What the
// browser computes is only the panel's display: the colour ramp and its normalisation, the x26
// relief, the projection, label placement and the screen size of the stored uncertainty radius.

import { panelObjects, panelRespondents } from "./object-map-signed-off";
import { PEDESTAL, drawSmoothTerrain } from "./object-map-smooth";
import { type BatteryWithMaps, type Frame, type ObjectMapArtifact, mapLinks } from "./object-map-view";

/** The panel's frame: the stored grid spans +-62 frame units (`terrain66`, `FRAME_SPAN66`). */
export const FRAME_SPAN = 62;
/** Drawn elevation of a terrain height 1 (`z = t * 26`). */
const RELIEF = 26;
/** On Relativni the lowest object keeps a hill 15 % of the top's (`REL_FLOOR66`). */
export const REL_FLOOR = 0.15;
/** The panel's map background (`draw66`). */
const BACKGROUND = "#07090c";
/** Relation colours: warm = move together, cool = opposite (`drawObjects66`). */
export const WARM = "#ffb35c";
export const COOL = "#6fa8ff";
/** A SECONDARY object's node (`drawObjects66`). */
export const SECONDARY = "#8a93a6";
/** The contour levels on the normalised height (`drawContours66`). */
const CONTOUR_LEVELS = [0.16, 0.28, 0.4, 0.52, 0.64, 0.76, 0.88];

const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

const STOPS = [[4, 14, 60], [0, 82, 159], [0, 185, 205], [20, 210, 116], [124, 231, 0], [244, 232, 27], [255, 143, 22], [232, 35, 29]];

/** The panel's colour ramp on a normalised height t in [0, 1] (`color66`). */
export function color66(t: number): string {
  t = clamp(t, 0, 1);
  const x = t * (STOPS.length - 1);
  const i = Math.min(STOPS.length - 2, Math.floor(x));
  const f = x - i;
  const a = STOPS[i], b = STOPS[i + 1];
  return `rgb(${Math.round(a[0] + (b[0] - a[0]) * f)},${Math.round(a[1] + (b[1] - a[1]) * f)},${Math.round(a[2] + (b[2] - a[2]) * f)})`;
}

/** An `rgb(...)` colour lit by a factor, each channel clamped to 0-255 (`blend66`). */
export function blend66(rgb: string, light: number): string {
  const m = (rgb.match(/\d+/g) ?? []).map(Number);
  return `rgb(${m.map((v) => Math.round(clamp(v * light, 0, 255))).join(",")})`;
}

export type Norm = "range" | "absolute";
/** `kind` names the panel's legend word for the scale: "rozsah", "absolutni" or "bez dat". */
export type Normalizer = { t: (x: number) => number; lo: number; hi: number; kind: "range" | "absolute" | "none" };

/**
 * The panel's height normalisation (`normalizer66`, its Relativni and Absolutni branches):
 * Relativni stretches the shown values from the lowest (at the 15 % floor) to the highest;
 * Absolutni reads them on the declared scale's bounds.
 */
export function normalizer(values: number[], mode: Norm, bounds?: [number, number] | null): Normalizer {
  const v = values.filter(Number.isFinite);
  if (!v.length) return { t: () => 0, lo: 0, hi: 1, kind: "none" };
  const lo = Math.min(...v), hi = Math.max(...v);
  if (mode === "absolute") {
    const a = bounds?.[0], b = bounds?.[1];
    if (a !== undefined && b !== undefined && Number.isFinite(a) && Number.isFinite(b) && b > a) return { t: (x) => clamp((x - a) / (b - a), 0, 1), lo: a, hi: b, kind: "absolute" };
    const max = Math.max(Math.abs(lo), Math.abs(hi), 1);
    return { t: (x) => clamp(x / max, 0, 1), lo: 0, hi: max, kind: "absolute" };
  }
  return { t: (x) => (hi > lo ? REL_FLOOR + (1 - REL_FLOOR) * clamp((x - lo) / (hi - lo), 0, 1) : 0.5), lo, hi, kind: "range" };
}

// ---------------------------------------------------------------- frame

/** A stored ruler position in the panel's frame units: the stored grid's square becomes +-62. */
export function toFrame(x: number, y: number, frame: Frame): { x: number; y: number } {
  return { x: ((x - frame.cx) * FRAME_SPAN) / frame.half, y: ((y - frame.cy) * FRAME_SPAN) / frame.half };
}

/** A stored length (ruler units) in frame units, the same one scale. */
export function toFrameLength(length: number, frame: Frame): number {
  return (length * FRAME_SPAN) / frame.half;
}

// ---------------------------------------------------------------- camera and projection

export type PanelCamera = { yaw: number; pitch: number; zoom: number; panX: number; panY: number };

/** The panel's opening camera (its default state, and "Vycentrovat"). */
export const INITIAL_CAMERA: PanelCamera = { yaw: -0.55, pitch: 0.72, zoom: 1, panX: 0, panY: 0 };
/** Below this pitch the view counts as from above: no slab, the 2D button lit (`drawSlab66`). */
export const TOP_PITCH = 0.08;
const ZOOM: [number, number] = [0.35, 2.8];

export type ScreenPoint = { x: number; y: number; depth: number };
export type Projection = { W: number; H: number; sc: number; project: (x: number, y: number, z?: number) => ScreenPoint };

/** The panel's orthographic camera (`projection66`): yaw about the vertical, pitch, one scale, origin at (W/2, 0.58 H). */
export function projection(camera: PanelCamera, W: number, H: number): Projection {
  const cy = Math.cos(camera.yaw), sy = Math.sin(camera.yaw), cp = Math.cos(camera.pitch), sp = Math.sin(camera.pitch);
  const sc = Math.min(W, H) * 0.0087 * camera.zoom;
  return {
    W, H, sc,
    project: (x, y, z = 0) => {
      x -= camera.panX; y -= camera.panY;
      const rx = x * cy - y * sy, ry = x * sy + y * cy, py = ry * cp - z * sp, pz = ry * sp + z * cp;
      return { x: W / 2 + rx * sc, y: H * 0.58 + py * sc, depth: pz };
    },
  };
}

/** "2D": straight from above, turned to the nearest quarter turn, centred, zoomed so the square fits (`socioCam66('top')`). */
export function topCamera(camera: PanelCamera, W: number, H: number): PanelCamera {
  const m = 24;
  return { yaw: Math.round(camera.yaw / (Math.PI / 2)) * (Math.PI / 2), pitch: 0, panX: 0, panY: 0, zoom: clamp(Math.min(W / 2 - m, 0.42 * H - m) / (FRAME_SPAN * Math.min(W, H) * 0.0087), ...ZOOM) };
}

/** "3D": the panel's tilt, everything else kept (`socioCam66('3d')`). */
export function camera3d(camera: PanelCamera): PanelCamera {
  return { ...camera, pitch: 0.72 };
}

/** The zoom buttons' and the wheel's steps, within the panel's bounds. */
export function zoomCamera(camera: PanelCamera, factor: number): PanelCamera {
  return { ...camera, zoom: clamp(camera.zoom * factor, ...ZOOM) };
}
export const ZOOM_IN = 1.13;
export const ZOOM_OUT = 0.88;
/** The wheel: away from the reader zooms out (`wheel66`). */
export function wheelCamera(camera: PanelCamera, deltaY: number): PanelCamera {
  return zoomCamera(camera, deltaY > 0 ? 0.91 : 1.1);
}

/** A drag on the map turns and tilts it (`pointerMove66`). */
export function dragCamera(camera: PanelCamera, dx: number, dy: number): PanelCamera {
  return { ...camera, yaw: camera.yaw + dx * 0.007, pitch: clamp(camera.pitch + dy * 0.004, 0.02, 1.18) };
}

/** A press that moves less than this is a click, not a turn (`pointerMove66`, `pointerUp66`). */
export const CLICK_SLOP = 5;

// ---------------------------------------------------------------- terrain

/** A square grid of normalised heights on the frame: `ht[gy][gx]` at (xs[gx], xs[gy]). */
export type PanelGrid = { N: number; span: number; xs: number[]; ht: number[][] };

/** The frame's sample positions on one axis: N + 1 from -62 to 62 (`terrain66`). */
export function gridAxis(N: number, span = FRAME_SPAN): number[] {
  return Array.from({ length: N + 1 }, (_, k) => -span + (2 * span * k) / N);
}

/** A stored grid as the panel's: the stored square is the frame, so its samples sit on the panel's
 *  axis. A cell the artifact leaves without a height draws as level ground (the envelope's 0). */
function panelGrid(N: number, height: (number | null)[][]): PanelGrid {
  return { N, span: FRAME_SPAN, xs: gridAxis(N), ht: height.map((row) => row.map((h) => h ?? 0)) };
}

/** The Relativni terrain: the stored framed envelope of the relative hill heights. */
export function storedGrid(map: ObjectMapArtifact): PanelGrid | null {
  const terrain = map.terrain;
  if (terrain.status !== "computed") return null;
  return panelGrid(terrain.parameters.grid_resolution, terrain.height);
}

/**
 * The Absolutni terrain: the stored envelope of the PRIMARY objects' 0-1 means on the same grid.
 * The panel normalises Absolutni on the declared scale's bounds, so on the stored 0-1 scale the
 * stored heights are its colour positions unchanged. Null when the map stores none.
 */
export function absoluteGrid(map: ObjectMapArtifact): PanelGrid | null {
  const terrain = map.terrain;
  if (terrain.status !== "computed" || !terrain.absolute_height) return null;
  return panelGrid(terrain.parameters.grid_resolution, terrain.absolute_height);
}

/** The drawn elevation under a frame point, bilinear between the grid's samples (`terrainAt66`). */
export function terrainAt(grid: PanelGrid, x: number, y: number): number {
  const { N, span } = grid;
  const u = ((x + span) / (2 * span)) * N, v = ((y + span) / (2 * span)) * N;
  const ix = clamp(Math.floor(u), 0, N - 1), iy = clamp(Math.floor(v), 0, N - 1);
  const fx = clamp(u - ix, 0, 1), fy = clamp(v - iy, 0, 1);
  const z = (gy: number, gx: number) => grid.ht[gy][gx] * RELIEF;
  return z(iy, ix) * (1 - fx) * (1 - fy) + z(iy, ix + 1) * fx * (1 - fy) + z(iy + 1, ix) * (1 - fx) * fy + z(iy + 1, ix + 1) * fx * fy;
}

export type TerrainTriangle = { p: [ScreenPoint, ScreenPoint, ScreenPoint]; d: number; h: number; fill: string };

/** Two triangles per grid cell, far first, each in its ramp colour lit by its height (`draw66`). */
function terrainTriangles(grid: PanelGrid, P: Projection): TerrainTriangle[] {
  const { N, xs, ht } = grid;
  const at = (gy: number, gx: number) => P.project(xs[gx], xs[gy], ht[gy][gx] * RELIEF);
  const tris: { p: [ScreenPoint, ScreenPoint, ScreenPoint]; d: number; h: number }[] = [];
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const A = at(y, x), B = at(y, x + 1), C = at(y + 1, x + 1), D = at(y + 1, x);
      const a = ht[y][x], b = ht[y][x + 1], c = ht[y + 1][x + 1], d = ht[y + 1][x];
      tris.push({ p: [A, B, C], d: (A.depth + B.depth + C.depth) / 3, h: (a + b + c) / 3 }, { p: [A, C, D], d: (A.depth + C.depth + D.depth) / 3, h: (a + c + d) / 3 });
    }
  }
  tris.sort((m, n) => m.d - n.d);
  // The object terrain colours by its own height (the panel's `ct` is `ht` on the object map).
  return tris.map((tr) => ({ ...tr, fill: blend66(color66(tr.h), 0.78 + 0.28 * tr.h) }));
}

/** One contour level's segments on the frame, cell by cell, as `drawContours66` walks them. */
function contourSegments(grid: PanelGrid, level: number): { x: number; y: number }[][] {
  const { N, xs, ht } = grid;
  const out: { x: number; y: number }[][] = [];
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const c = [[y, x], [y, x + 1], [y + 1, x + 1], [y + 1, x]].map(([gy, gx]) => ({ x: xs[gx], y: xs[gy], ht: ht[gy][gx] }));
      const pts: { x: number; y: number }[] = [];
      for (let e = 0; e < 4; e++) {
        const a = c[e], b = c[(e + 1) % 4], va = a.ht - level, vb = b.ht - level;
        if ((va <= 0 && vb > 0) || (va > 0 && vb <= 0)) {
          const f = Math.abs(vb - va) < 1e-9 ? 0.5 : (level - a.ht) / (b.ht - a.ht);
          pts.push({ x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f });
        }
      }
      if (pts.length >= 2) {
        out.push([pts[0], pts[1]]);
        if (pts.length === 4) out.push([pts[2], pts[3]]);
      }
    }
  }
  return out;
}

// ---------------------------------------------------------------- objects

export type PanelNode = {
  id: string;
  label: string;
  x: number; // frame units
  y: number;
  primary: boolean;
  value: number | null; // the stored 0-1 mean
  relative: number | null; // the stored relative hill height
};

/** The mapped objects as chunk 1 reads them (`panelObjects`), their stored positions in frame units. */
export function panelNodes(battery: BatteryWithMaps, map: ObjectMapArtifact, frame: Frame): PanelNode[] {
  return panelObjects(battery, map).map((o) => {
    const p = toFrame(o.x, o.y, frame);
    return { id: o.id, label: o.label, x: p.x, y: p.y, primary: map.roles[o.id] === "primary", value: o.height, relative: o.relative };
  });
}

/**
 * Each node's colour position t: on Relativni the stored relative height, on Absolutni the
 * stored 0-1 mean on the declared scale. An object without one takes the panel's `?? 0`
 * through its normaliser (the floor on Relativni, 0 on Absolutni).
 */
export function nodeTones(nodes: PanelNode[], norm: Norm): number[] {
  return nodes.map((n) => (norm === "absolute" ? clamp(n.value ?? 0, 0, 1) : n.relative ?? REL_FLOOR));
}

/** The node radius factor for a set of M objects: unchanged up to 30, half size at 120 (`node_scale`). */
export function nodeScale(M: number): number {
  return Math.min(1, Math.sqrt(30 / Math.max(M, 1)));
}

/** A node's disc radius before the node scale; the white ring is 2.5 px wider (`drawObjects66`). */
const nodeRadius = (selected: boolean) => (selected ? 7.5 : 5.7);
/** Where a relation line stops: just outside the disc, the node scale left out (`nodeR` in `drawObjects66`). */
const lineClearance = (selected: boolean) => nodeRadius(selected) + 4.5;

// ---------------------------------------------------------------- relations

/** Which relations the map draws: the panel's default "Nejsilnější vztahy" (its Top: 5 strongest), the selected object's, or all. */
export type RelationMode = "top" | "selected" | "all";
export type PanelPair = { i: number; j: number; r: number; v: number };

/**
 * The drawn pairs, from the one link rule of the web (`mapLinks`: reliable PRIMARY pairs, over
 * the floor where declared), in the panel's three displays: `topRelationPairs66` (nothing
 * selected: the 5 strongest; an object selected: its 5 strongest), `relationPairs66` "Vybraný"
 * (every drawn pair of the selected object; none without one) and "Vše".
 */
export function relationPairs(map: ObjectMapArtifact, mode: RelationMode, selected: number): PanelPair[] {
  const index = new Map(map.object_ids.map((id, k) => [id, k]));
  const items = mapLinks(map).map((l) => ({ i: index.get(l.a)!, j: index.get(l.b)!, r: l.r, v: Math.abs(l.r) }));
  if (mode === "all") return items;
  if (mode === "selected") return selected >= 0 ? items.filter((x) => x.i === selected || x.j === selected) : [];
  const pool = selected < 0 ? items : items.filter((x) => x.i === selected || x.j === selected);
  return [...pool].sort((a, b) => b.v - a.v).slice(0, 5);
}

/** The strongest |r| anywhere on the map, every stored pair counted: the Relativni width's top. */
export function strongestRelation(map: ObjectMapArtifact): number {
  let hi = 0;
  map.relations.r.forEach((row, i) => row.forEach((r, j) => { if (i !== j && r !== null) hi = Math.max(hi, Math.abs(r)); }));
  return hi;
}

/**
 * A line's strength k in [0, 1]: on Relativni |r| over the map's strongest relation, on
 * Absolutni |r| over 0.5 (full strength at Cohen's large), as `drawObjects66` sets `r.k`.
 */
export function relationStrength(v: number, norm: Norm, strongest: number): number {
  return norm !== "absolute" && strongest > 1e-6 ? Math.min(1, v / strongest) : Math.min(1, v / 0.5);
}

/** A line's width at strength k (`relationLine66`). */
const relationWidth = (k: number) => 1 + 5 * k;

type XY = { x: number; y: number };

function quadAt(a: XY, c: XY, b: XY, t: number): XY {
  const u = 1 - t;
  return { x: u * u * a.x + 2 * u * t * c.x + t * t * b.x, y: u * u * a.y + 2 * u * t * c.y + t * t * b.y };
}

function quadTan(a: XY, c: XY, b: XY, t: number): XY {
  return { x: 2 * (1 - t) * (c.x - a.x) + 2 * t * (b.x - c.x), y: 2 * (1 - t) * (c.y - a.y) + 2 * t * (b.y - c.y) };
}

/** The curve parameter where it leaves the disc of radius R around a (atEnd: enters the one around b), by bisection. */
export function quadClip(a: XY, c: XY, b: XY, R: number, atEnd: boolean): number {
  const P = atEnd ? b : a;
  let lo = atEnd ? 0.5 : 0, hi = atEnd ? 1 : 0.5;
  for (let k = 0; k < 30; k++) {
    const m = (lo + hi) / 2, q = quadAt(a, c, b, m), inside = Math.hypot(q.x - P.x, q.y - P.y) < R;
    if (atEnd === inside) hi = m; else lo = m;
  }
  return (lo + hi) / 2;
}

/** The end points and control point of the piece t0..t1 of the curve. */
function quadPiece(a: XY, c: XY, b: XY, t0: number, t1: number): { p0: XY; p1: XY; c: XY } {
  const p0 = quadAt(a, c, b, t0), p1 = quadAt(a, c, b, t1), d = quadTan(a, c, b, t0), h = (t1 - t0) / 2;
  return { p0, p1, c: { x: p0.x + d.x * h, y: p0.y + d.y * h } };
}

/**
 * An undirected relation's curve between two screen points: bent to one side by
 * min(34, 10 + L/10), cut where it leaves both discs; none when the discs touch
 * (`relationGeometry66`; a measured relation has no direction, so no head).
 */
export function relationGeometry(a: XY, b: XY, side: number, ra: number, rb: number): { c: XY; piece: { p0: XY; p1: XY; c: XY }; mid: XY } | null {
  const dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 1;
  const overlap = L <= ra + rb;
  const nx = -dy / L, ny = dx / L, bend = Math.min(34, 10 + L * 0.1) * side;
  const c = { x: (a.x + b.x) / 2 + nx * bend, y: (a.y + b.y) / 2 + ny * bend };
  const t0 = quadClip(a, c, b, ra, false), t1 = quadClip(a, c, b, rb, true);
  if (overlap || t1 <= t0) return null;
  return { c, piece: quadPiece(a, c, b, t0, t1), mid: quadAt(a, c, b, 0.5) };
}

// ---------------------------------------------------------------- labels

export type LabelItem = { text: string; x: number; y: number; font: string; prio: number };

/**
 * Which labels the map prints: highest priority first (the selected, the hovered, then the
 * higher PRIMARY objects), each skipped when its box would overlap one already placed
 * (`placeLabels66`). `measure` is the canvas's text width in that font.
 */
function placeLabels(items: LabelItem[], measure: (text: string, font: string) => number): LabelItem[] {
  const boxes: number[][] = [];
  const placed: LabelItem[] = [];
  for (const it of [...items].sort((a, b) => b.prio - a.prio)) {
    const w = measure(it.text, it.font);
    const b = [it.x - w / 2 - 3, it.y - 11, it.x + w / 2 + 3, it.y + 3];
    if (boxes.some((c) => b[0] < c[2] && c[0] < b[2] && b[1] < c[3] && c[1] < b[3])) continue;
    boxes.push(b);
    placed.push(it);
  }
  return placed;
}

/** A label's font: bold for the selected or hovered object (`drawObjects66`). */
const labelFont = (strong: boolean) => `${strong ? "800 " : "650 "}11px system-ui`;

// ---------------------------------------------------------------- the frame

export type MapScene = {
  width: number;
  height: number;
  camera: PanelCamera;
  grid: PanelGrid;
  nodes: PanelNode[];
  tones: number[]; // each node's colour position, `nodeTones`
  pairs: (PanelPair & { k: number })[];
  selected: number; // -1: none
  hovered: number; // -1: none
  nodeScale: number;
  statements?: MapStatements; // what the map says about itself, drawn over it
  // Present on the respondent map: its dots, and the clicked one (-1: none). The objects then draw
  // as the panel's markers and no relation is drawn.
  respondents?: { dots: PanelDot[]; selected: number };
  // The smooth terrain (object-map-smooth.ts), drawn in WebGL at this device-pixel ratio; absent: blocky.
  smooth?: { ratio: number };
};

/** What a click can land on: an object (on either map), a respondent's dot, or a drawn relation
 *  at its midpoint (`index` and `j` its two objects). */
export type Hit = { index: number; x: number; y: number; r: number; kind: "object" | "respondent" | "relation"; j?: number };
export type DrawResult = { hits: Hit[]; labels: { shown: number; wanted: number } };

/** The object under a screen point, nearest first, within its hit radius (`hit66`). */
export function hitTest(hits: Hit[], x: number, y: number): Hit | null {
  let best: Hit | null = null, bd = Infinity;
  for (const h of hits) {
    const d = Math.hypot(x - h.x, y - h.y);
    if (d <= h.r && d < bd) { best = h; bd = d; }
  }
  return best;
}

/**
 * One frame of the map, in the panel's order (`draw66`): background, the slab under the square
 * (when tilted), the terrain triangles far first, the contours, then on the object map the
 * relation lines, the nodes far first and the labels, on the respondent map the dots far first and
 * the objects' markers with their labels; last what the map says about itself. Returns where each
 * object and dot is (for clicks) and how many object labels fit. Draws in CSS pixels: the caller
 * sets the device-pixel transform.
 */
export function drawObjectMap(ctx: CanvasRenderingContext2D, scene: MapScene): DrawResult {
  const { width: W, height: H, camera, grid } = scene;
  const P = projection(camera, W, H);
  ctx.fillStyle = BACKGROUND;
  ctx.fillRect(0, 0, W, H);
  // The panel never resets the line width between frames; from its second frame on the slab is
  // stroked at the triangles' hairline, which is what a reader sees.
  if (!(scene.smooth && drawSmoothTerrain(ctx, grid, camera, W, H, scene.smooth.ratio))) drawBlockyTerrain(ctx, P, camera, grid);
  drawContours(ctx, P, grid);
  const result = scene.respondents ? drawRespondents(ctx, P, scene, scene.respondents) : drawObjects(ctx, P, scene);
  if (scene.statements) drawStatements(ctx, P, scene, result.labels);
  return result;
}

function drawBlockyTerrain(ctx: CanvasRenderingContext2D, P: Projection, camera: PanelCamera, grid: PanelGrid): void {
  // The panel never resets the line width between frames; from its second frame on the slab is
  // stroked at the triangles' hairline, which is what a reader sees.
  ctx.lineWidth = 0.28;
  drawSlab(ctx, P, camera, grid);
  ctx.lineWidth = 0.28;
  for (const tr of terrainTriangles(grid, P)) {
    ctx.beginPath();
    ctx.moveTo(tr.p[0].x, tr.p[0].y);
    ctx.lineTo(tr.p[1].x, tr.p[1].y);
    ctx.lineTo(tr.p[2].x, tr.p[2].y);
    ctx.closePath();
    ctx.fillStyle = tr.fill;
    ctx.globalAlpha = 0.94;
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.025)";
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

/**
 * The terrain's sides (the owner, 2026-10-23, as the Sociomapy app's Pedestal, without its layer
 * bands): one wall per edge segment of the grid, from the terrain's edge height down to a flat base
 * just under it, in one gradient from the terrain's colour at that edge to x0.3 at the base. From
 * above there are none; the canvas has no depth buffer, so only the walls facing the camera are drawn.
 */
function drawSlab(ctx: CanvasRenderingContext2D, P: Projection, camera: PanelCamera, grid: PanelGrid): void {
  if (camera.pitch < TOP_PITCH) return;
  const { N, xs, ht, span: s } = grid, bottom = -PEDESTAL.depth;
  ctx.beginPath();
  [P.project(-s, -s, bottom), P.project(s, -s, bottom), P.project(s, s, bottom), P.project(-s, s, bottom)].forEach((q, i) => (i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y)));
  ctx.closePath();
  ctx.fillStyle = PEDESTAL.base;
  ctx.fill();
  const rim: [number, number][] = [];
  for (let x = 0; x < N; x++) rim.push([0, x]);
  for (let y = 0; y < N; y++) rim.push([y, N]);
  for (let x = N; x > 0; x--) rim.push([N, x]);
  for (let y = N; y > 0; y--) rim.push([y, 0]);
  const rgb = (c: string) => (c.match(/\d+/g) ?? []).slice(0, 3).map(Number);
  const shade = (c: number[], f: number) => `rgb(${c.map((v) => Math.round(Math.min(255, v * f))).join(",")})`;
  for (let i = 0; i < rim.length; i++) {
    const [ay, ax] = rim[i], [by, bx] = rim[(i + 1) % rim.length], ha = ht[ay][ax], hb = ht[by][bx];
    const ta = P.project(xs[ax], xs[ay], ha * RELIEF), tb = P.project(xs[bx], xs[by], hb * RELIEF);
    const ba = P.project(xs[ax], xs[ay], bottom), bb = P.project(xs[bx], xs[by], bottom);
    if ((tb.x - ta.x) * (ba.y - ta.y) - (tb.y - ta.y) * (ba.x - ta.x) >= 0) continue;
    const ca = rgb(blend66(color66(ha), 0.78 + 0.28 * ha)), cb = rgb(blend66(color66(hb), 0.78 + 0.28 * hb)), c = ca.map((v, k) => (v + cb[k]) / 2);
    const gradient = ctx.createLinearGradient((ta.x + tb.x) / 2, (ta.y + tb.y) / 2, (ba.x + bb.x) / 2, (ba.y + bb.y) / 2);
    gradient.addColorStop(0, shade(c, 1));
    gradient.addColorStop(1, shade(c, 1 - PEDESTAL.bottomDarken));
    ctx.beginPath();
    ctx.moveTo(ta.x, ta.y);
    ctx.lineTo(tb.x, tb.y);
    ctx.lineTo(bb.x, bb.y);
    ctx.lineTo(ba.x, ba.y);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();
  }
}

function drawContours(ctx: CanvasRenderingContext2D, P: Projection, grid: PanelGrid): void {
  ctx.save();
  ctx.lineWidth = 0.75;
  ctx.strokeStyle = "rgba(5,10,12,.30)";
  for (const level of CONTOUR_LEVELS) {
    ctx.beginPath();
    for (const [a, b] of contourSegments(grid, level)) {
      const qa = P.project(a.x, a.y, level * RELIEF + 0.08), qb = P.project(b.x, b.y, level * RELIEF + 0.08);
      ctx.moveTo(qa.x, qa.y);
      ctx.lineTo(qb.x, qb.y);
    }
    ctx.stroke();
  }
  ctx.restore();
}

function drawObjects(ctx: CanvasRenderingContext2D, P: Projection, scene: MapScene): DrawResult {
  const { grid, nodes, tones, selected, hovered } = scene;
  const q = nodes.map((n) => P.project(n.x, n.y, terrainAt(grid, n.x, n.y) + 0.8));
  const hits: Hit[] = [];
  for (const pair of scene.pairs) {
    const side = pair.i < pair.j ? 1 : -1;
    const mid = relationLine(ctx, q[pair.i], q[pair.j], pair.k, pair.r >= 0 ? WARM : COOL, side, lineClearance(pair.i === selected), lineClearance(pair.j === selected));
    if (mid) hits.push({ index: pair.i, j: pair.j, x: mid.x, y: mid.y, r: 10, kind: "relation" });
  }
  const order = nodes.map((_, i) => i).sort((a, b) => q[a].depth - q[b].depth);
  const labels: LabelItem[] = [];
  for (const i of order) {
    const sel = i === selected, hov = i === hovered, sec = !nodes[i].primary;
    const rr = nodeRadius(sel) * scene.nodeScale;
    ctx.beginPath();
    ctx.arc(q[i].x, q[i].y, rr + 2.5, 0, Math.PI * 2);
    ctx.fillStyle = sel ? "#fff" : "rgba(255,255,255,.9)";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(q[i].x, q[i].y, rr, 0, Math.PI * 2);
    ctx.fillStyle = sec ? SECONDARY : color66(tones[i]);
    ctx.fill();
    // The panel's default labels ("important"): every PRIMARY object, the selected and the hovered one.
    if (sel || !sec || hov) labels.push({ text: nodes[i].label, x: q[i].x, y: q[i].y - 12, font: labelFont(sel || hov), prio: sel ? 3 : hov ? 2 : (sec ? 0 : 1) + tones[i] * 0.5 });
    hits.push({ index: i, x: q[i].x, y: q[i].y, r: 14, kind: "object" });
  }
  ctx.save();
  ctx.textAlign = "center";
  ctx.fillStyle = "#fff";
  ctx.shadowColor = "#000";
  ctx.shadowBlur = 5;
  const placed = placeLabels(labels, (text, font) => { ctx.font = font; return ctx.measureText(text).width; });
  for (const it of placed) { ctx.font = it.font; ctx.fillText(it.text, it.x, it.y); }
  ctx.restore();
  return { hits, labels: { shown: placed.length, wanted: labels.length } };
}

function relationLine(ctx: CanvasRenderingContext2D, a: XY, b: XY, k: number, color: string, side: number, ra: number, rb: number): XY | null {
  const w = relationWidth(k);
  const g = relationGeometry(a, b, side, ra, rb);
  if (!g) return null;
  const s = g.piece;
  const path = () => { ctx.beginPath(); ctx.moveTo(s.p0.x, s.p0.y); ctx.quadraticCurveTo(s.c.x, s.c.y, s.p1.x, s.p1.y); };
  ctx.save();
  // A white casing under every line so it stands out from the terrain; stronger is brighter.
  ctx.globalAlpha = 0.5 + 0.4 * k;
  ctx.lineWidth = w + 2.4;
  ctx.strokeStyle = "#fff";
  ctx.lineCap = "round";
  path();
  ctx.stroke();
  ctx.globalAlpha = 0.6 + 0.4 * k;
  ctx.lineWidth = w;
  ctx.strokeStyle = color;
  path();
  ctx.stroke();
  ctx.restore();
  return g.mid;
}

// ---------------------------------------------------------------- what the map says about itself

/** The panel's words for the map's statements, from cs.ts (the drawing takes no text of its own). */
export type StatementTexts = {
  caption: string;
  weakTitle: string;
  weakBody: (percent: number) => string;
  noStructureTitle: string;
  noStructureBody: string;
  sparse: string;
  labelled: (shown: number, total: number) => string;
};

/** The stored statements the object map draws: the uncertainty radius (in RMS inter-object
 *  distances), the weakly determined verdict with its split-half score (null under the
 *  no-reliable-pair rule), and the sparse-design flag. */
export type MapStatements = { radius: number | null; weak: boolean; splitHalf: number | null; sparse: boolean; texts: StatementTexts; respondentNote?: string | null };

/** The statements as the artifact stores them; none where it stores none. */
export function mapStatements(map: ObjectMapArtifact, texts: StatementTexts): MapStatements {
  const c = map.credibility;
  return { radius: c?.uncertainty_radius ?? null, weak: c?.weakly_determined === true, splitHalf: c?.split_half ?? null, sparse: map.sparse_design?.flag === true, texts };
}

/** The root mean square of the distances between the drawn objects (frame units), the unit the
 *  stored uncertainty radius is given in. */
function rmsDistance(points: { x: number; y: number }[]): number {
  let sum = 0, count = 0;
  for (let a = 0; a < points.length; a++) {
    for (let b = a + 1; b < points.length; b++) { sum += (points[a].x - points[b].x) ** 2 + (points[a].y - points[b].y) ** 2; count++; }
  }
  return Math.sqrt(sum / Math.max(1, count));
}

/**
 * The reference circle of the map's typical position uncertainty (`drawAiaOverlay66`): the stored
 * radius times the RMS distance of the drawn PRIMARY objects, in screen pixels along the longer
 * projected axis; top right, left of the tools. Only with three such objects or more, and only
 * when it is at least 2 px and under a quarter of the view.
 */
export function uncertaintyCircle(P: Projection, points: { x: number; y: number }[], radius: number | null): { x: number; y: number; r: number; captionX: number; captionY: number } | null {
  if (radius === null || points.length < 3) return null;
  const c0 = P.project(0, 0, 0), c1 = P.project(1, 0, 0), c2 = P.project(0, 1, 0);
  const sc = Math.max(Math.hypot(c1.x - c0.x, c1.y - c0.y), Math.hypot(c2.x - c0.x, c2.y - c0.y));
  const r = radius * rmsDistance(points) * sc;
  if (!(r >= 2 && r < Math.min(P.W, P.H) / 4)) return null;
  const x = P.W - 96 - r, y = 72 + r;
  return { x, y, r, captionX: Math.min(x, P.W - 180), captionY: y + r + 5 };
}

/** The banner's box over a weakly determined map: at most 440 px wide, 84 tall, at 38 % of the height. */
export function bannerBox(W: number, H: number): { x: number; y: number; w: number; h: number } {
  const w = Math.min(W - 40, 440);
  return { x: W / 2 - w / 2, y: H * 0.38, w, h: 84 };
}

/** The banner's body in lines as the panel wraps it: word by word, a line full past `width`. */
export function wrapWords(text: string, width: number, measure: (line: string) => number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const w of text.split(" ")) {
    const next = line ? `${line} ${w}` : w;
    if (measure(next) > width) { lines.push(line); line = w; } else line = next;
  }
  if (line) lines.push(line);
  return lines;
}

/** The notes at the bottom centre, top to bottom: the sparse design (on both maps, not under the
 *  banner, which says more); on the object map how many objects are labelled when a large map had
 *  to drop labels; on the respondent map its note below the minimum number of objects. */
export function statementNotes(st: MapStatements, labels: { shown: number; wanted: number }, objects: number, respondentMap = false): { colour: string; text: string }[] {
  const notes: { colour: string; text: string }[] = [];
  if (st.sparse && !st.weak) notes.push({ colour: "#ffd27a", text: st.texts.sparse });
  if (!respondentMap && labels.shown < labels.wanted && objects > 30) notes.push({ colour: "#8b96a3", text: st.texts.labelled(labels.shown, objects) });
  if (respondentMap && st.respondentNote) notes.push({ colour: "#ffd27a", text: st.respondentNote });
  return notes;
}

/** The panel's `drawAiaOverlay66` on the object map: the circle, the veil and banner, the notes. */
function drawStatements(ctx: CanvasRenderingContext2D, P: Projection, scene: MapScene, labels: { shown: number; wanted: number }): void {
  const st = scene.statements!;
  const { W, H } = P;
  ctx.save();
  ctx.font = "600 11px system-ui";
  ctx.textBaseline = "top";
  // The uncertainty is the objects' positions: drawn on the object map only.
  const circle = scene.respondents ? null : uncertaintyCircle(P, scene.nodes.filter((n) => n.primary), st.radius);
  if (circle) {
    ctx.setLineDash([4, 3]);
    ctx.lineWidth = 1.2;
    ctx.strokeStyle = "rgba(255,255,255,.9)";
    ctx.beginPath();
    ctx.arc(circle.x, circle.y, circle.r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(circle.x, circle.y, 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.textAlign = "center";
    ctx.fillStyle = "#cfd6de";
    ctx.fillText(st.texts.caption, circle.captionX, circle.captionY);
  }
  ctx.textAlign = "left";
  if (st.weak) {
    ctx.fillStyle = "rgba(7,9,12,.62)";
    ctx.fillRect(0, 0, W, H);
    const box = bannerBox(W, H);
    const none = st.splitHalf === null;
    ctx.fillStyle = "rgba(7,9,12,.92)";
    ctx.strokeStyle = "rgba(255,255,255,.25)";
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(box.x, box.y, box.w, box.h, 8); else ctx.rect(box.x, box.y, box.w, box.h);
    ctx.fill();
    ctx.stroke();
    ctx.textAlign = "center";
    ctx.fillStyle = "#fff";
    ctx.font = "700 15px system-ui";
    ctx.fillText(none ? st.texts.noStructureTitle : st.texts.weakTitle, W / 2, box.y + 12);
    ctx.font = "500 11.5px system-ui";
    ctx.fillStyle = "#cfd6de";
    const body = none ? st.texts.noStructureBody : st.texts.weakBody(Math.round(100 * st.splitHalf!));
    wrapWords(body, box.w - 28, (line) => ctx.measureText(line).width).forEach((line, k) => ctx.fillText(line, W / 2, box.y + 38 + 15 * k));
  }
  const notes = statementNotes(st, labels, scene.nodes.length, Boolean(scene.respondents));
  ctx.font = "600 11px system-ui";
  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  notes.forEach((note, k) => { ctx.fillStyle = note.colour; ctx.fillText(note.text, W / 2, H - 14 - 16 * (notes.length - 1 - k)); });
  ctx.restore();
}

// ---------------------------------------------------------------- the respondent map

/** A respondent's dot: its stored position in frame units with the panel's display offset. */
export type PanelDot = { id: string; x: number; y: number; faded: boolean; segmented: boolean; segment: number; coloured: boolean };

/**
 * The panel's display offset of a respondent's dot (applied as it loads the map): up to 1.1 frame
 * units in a direction, both from a hash of the respondent's id, so dots of identical answers do not
 * hide each other. Display only; the stored position is unchanged.
 */
export function dotOffset(id: string): { dx: number; dy: number } {
  let h = 0;
  for (const c of String(id)) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const a = (h % 6283) / 1000, j = (((h >>> 8) % 1000) / 1000) * 1.1;
  return { dx: Math.cos(a) * j, dy: Math.sin(a) * j };
}

/** The PLACED and FADED respondents as dots on the frame; NOT_PLACED ones have no position. */
export function panelDots(map: ObjectMapArtifact, frame: Frame): PanelDot[] {
  return panelRespondents(map).map((r) => {
    const p = toFrame(r.x, r.y, frame), o = dotOffset(r.id);
    return { id: r.id, x: p.x + o.dx, y: p.y + o.dy, faded: r.placement === "FADED", segmented: r.segmented, segment: r.segment, coloured: r.coloured };
  });
}

/** The respondent map's terrain: the stored density of the clearly placed respondents over its
 *  maximum, on the object map's frame. Null without a stored respondent map. */
export function densityGrid(map: ObjectMapArtifact): PanelGrid | null {
  const r = map.respondents;
  if (r?.status !== "computed") return null;
  return panelGrid(r.density.parameters.grid_resolution, r.density.height);
}

/** The taste segments' colours, light on the dark terrain, and the grey of a dot not clearly in one (`SEG_COLORS66`). */
export const SEGMENT_COLOURS = ["#7fd3ff", "#ffc46b", "#ff8fb1", "#b9f27c"];
export const SEGMENT_GREY = "#9aa3ad";

/**
 * A dot's colour (`segColor66`): while the set shows taste segments, a respondent the artifact
 * colours takes its segment's colour and every other dot is grey; without segments (none found,
 * or only a borderline hint) the dot has no colour of its own and is the panel's white.
 */
export function dotColour(dot: PanelDot): string | null {
  if (!dot.segmented) return null;
  return dot.coloured && dot.segment >= 0 ? SEGMENT_COLOURS[dot.segment % SEGMENT_COLOURS.length] : SEGMENT_GREY;
}

/** The panel's `drawRespondents66`: the dots far first (a weakly placed one faint), then each
 *  object as a white rotated square with its label. */
function drawRespondents(ctx: CanvasRenderingContext2D, P: Projection, scene: MapScene, people: { dots: PanelDot[]; selected: number }): DrawResult {
  const { grid, nodes, hovered } = scene;
  const hits: Hit[] = [];
  const proj = people.dots.map((d, i) => ({ i, d, q: P.project(d.x, d.y, terrainAt(grid, d.x, d.y) + 0.65) }));
  proj.sort((a, b) => a.q.depth - b.q.depth);
  for (const { i, d, q } of proj) {
    ctx.globalAlpha = d.faded ? 0.3 : 1;
    drawPerson(ctx, q.x, q.y, i === people.selected, dotColour(d));
    ctx.globalAlpha = 1;
    hits.push({ index: i, x: q.x, y: q.y, r: 8, kind: "respondent" });
  }
  const labels: LabelItem[] = [];
  nodes.forEach((n, i) => {
    const q = P.project(n.x, n.y, terrainAt(grid, n.x, n.y) + 1.8);
    ctx.save();
    ctx.translate(q.x, q.y);
    ctx.rotate(Math.PI / 4);
    ctx.fillStyle = "#fff";
    ctx.fillRect(-5.5, -5.5, 11, 11);
    ctx.fillStyle = "#15242e";
    ctx.fillRect(-3.7, -3.7, 7.4, 7.4);
    ctx.restore();
    const hov = i === hovered;
    labels.push({ text: n.label, x: q.x, y: q.y - 12, font: `${hov ? "800 " : "700 "}10px system-ui`, prio: hov ? 2 : 1 });
    hits.push({ index: i, x: q.x, y: q.y, r: 12, kind: "object" });
  });
  ctx.save();
  ctx.textAlign = "center";
  ctx.fillStyle = "#fff";
  ctx.shadowColor = "#000";
  ctx.shadowBlur = 5;
  const placed = placeLabels(labels, (text, font) => { ctx.font = font; return ctx.measureText(text).width; });
  for (const it of placed) { ctx.font = it.font; ctx.fillText(it.text, it.x, it.y); }
  ctx.restore();
  return { hits, labels: { shown: placed.length, wanted: labels.length } };
}

/** One respondent's dot (`drawPerson66`, no filter): white, the clicked one ringed. */
function drawPerson(ctx: CanvasRenderingContext2D, x: number, y: number, selected: boolean, colour: string | null): void {
  const r = 2.6;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fillStyle = colour || "rgba(255,255,255,.85)";
  ctx.fill();
  if (selected) {
    ctx.beginPath();
    ctx.arc(x, y, r + 4, 0, Math.PI * 2);
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1.7;
    ctx.stroke();
  }
}

// ---------------------------------------------------------------- the PNG snapshot's legend

/** The legend card as the page shows it under the map's bottom left corner: its title, the
 *  height ramp with its three marks, and on the respondent map the taste segments' lines. */
export type LegendCard = {
  title: string;
  marks: [string, string, string];
  segments?: { title: string | null; rows: { colour: string; text: string }[]; foot: string | null } | null;
};

const LEGEND_RAMP = ["#07134f", "#005fa8", "#00bdd1", "#14d178", "#7ce700", "#f4e81b", "#ff8f16", "#e8231d"];

/**
 * Draws the legend card into a snapshot of the map (the panel's PNG export has the canvas only;
 * the page's legend is drawn over it in HTML): 260 px wide, 17 px from the left and 14 px from
 * the bottom, in the card's colours and sizes. Draws in CSS pixels: the caller sets the transform.
 */
export function drawLegendCard(ctx: CanvasRenderingContext2D, card: LegendCard, height: number): void {
  const x = 17, width = 260, pad = 12, inner = width - 2 * pad;
  const rows: { draw: (y: number) => void; h: number }[] = [];
  const text = (s: string, y: number, font: string, colour: string, align: CanvasTextAlign = "left", at = x + pad) => {
    ctx.font = font; ctx.fillStyle = colour; ctx.textAlign = align; ctx.textBaseline = "top"; ctx.fillText(s, at, y);
  };
  rows.push({ h: 14, draw: (y) => text(card.title.toUpperCase(), y, "700 10.5px system-ui", "rgba(255,255,255,.7)") });
  rows.push({ h: 14, draw: (y) => {
    const g = ctx.createLinearGradient(x + pad, 0, x + pad + inner, 0);
    LEGEND_RAMP.forEach((c, k) => g.addColorStop(k / (LEGEND_RAMP.length - 1), c));
    ctx.fillStyle = g; ctx.fillRect(x + pad, y + 3, inner, 8);
  } });
  rows.push({ h: 14, draw: (y) => {
    const font = "9.5px system-ui", colour = "rgba(255,255,255,.56)";
    text(card.marks[0], y, font, colour);
    text(card.marks[1], y, font, colour, "center", x + width / 2);
    text(card.marks[2], y, font, colour, "right", x + pad + inner);
  } });
  const seg = card.segments;
  if (seg) {
    ctx.font = "9.5px system-ui";
    if (seg.title) rows.push({ h: 16, draw: (y) => text(seg.title!.toUpperCase(), y + 3, "700 10.5px system-ui", "rgba(255,255,255,.7)") });
    for (const row of seg.rows) {
      const lines = wrapWords(row.text, inner - 14, (l) => ctx.measureText(l).width);
      rows.push({ h: 13.3 * lines.length, draw: (y) => {
        ctx.beginPath(); ctx.arc(x + pad + 4.5, y + 6, 4.5, 0, Math.PI * 2); ctx.fillStyle = row.colour; ctx.fill();
        lines.forEach((l, k) => text(l, y + 13.3 * k, "9.5px system-ui", "rgba(255,255,255,.58)", "left", x + pad + 14));
      } });
    }
    if (seg.foot) {
      const lines = wrapWords(seg.foot, inner, (l) => ctx.measureText(l).width);
      rows.push({ h: 13.3 * lines.length, draw: (y) => lines.forEach((l, k) => text(l, y + 13.3 * k, "9.5px system-ui", "rgba(255,255,255,.58)")) });
    }
  }
  const h = rows.reduce((s, r) => s + r.h, 0) + 2 * 10;
  const top = height - 14 - h;
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(x, top, width, h, 8);
  ctx.fillStyle = "rgba(8,11,15,.75)";
  ctx.fill();
  ctx.strokeStyle = "rgba(255,255,255,.13)";
  ctx.lineWidth = 1;
  ctx.stroke();
  let y = top + 10;
  for (const r of rows) { r.draw(y); y += r.h; }
  ctx.restore();
}
