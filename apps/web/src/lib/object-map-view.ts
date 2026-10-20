// The audit's object map (contract 3, `aia-sociomap-3`) as a person reads it on Results
// (plan sociomap-formula-corrections chunk 5a).
//
// The worker computed everything: positions on the fixed ruler, Stress-1 and its band, each
// pair's signed r with its evidence state and practical floor, the mean-rating heights and
// the envelope terrain. This module only decides how the stored artifact is shown -- which
// cells, which links, in which colour -- and never computes or adjusts a methodological
// number. What the artifact leaves undefined stays undefined: a cell no hill reaches is not
// drawn, and an unknown pair draws no link.
//
// The redesign (plan object-map-3d-redesign) adds display-only helpers: ten terrace bands on
// the absolute stored 0-1 scale, the band-step edges of the top view, the ranked list, one
// pair's stored evidence explained, and screen-space label placement. None of them changes a
// stored number, a position or which pairs are drawn.

import { type SignedOffRespondents, type SignedOffRespondentSpec, isSignedOffMap } from "./object-map-signed-off";

/** The code's object maps, newest first; a run that pinned `aia-sociomap-2` reads it. A run
 *  started under an edited methodology (ADR 0023) pins its map under the version's own name,
 *  `aia-sociomap-3+e<n>`, and is read as well: the map is whichever contract-3 map the run
 *  stored, a known name first. */
export const OBJECT_MAP_METHODS = ["aia-sociomap-4", "aia-sociomap-3", "aia-sociomap-2"] as const;

export type PairState = "reliable" | "weak" | "unknown";

export type ObjectMapArtifact = {
  contract_version: "3";
  // `estimator` and the respondent sections: the signed-off methodology's (aia-sociomap-5 and the
  // versions edited from it), read by object-map-signed-off.ts.
  spec: { methodology_version: string; relation: { basis: string; n_min: number; confidence: number; effect_floor?: number; estimator?: string }; terrain: { sigma: number; sigma_basis: string; method?: string } | null; respondent_map?: SignedOffRespondentSpec };
  respondent_ids?: string[];
  object_ids: string[];
  roles: Record<string, string>;
  not_placed: Record<string, string>;
  relations: {
    r: (number | null)[][];
    n: (number | null)[][];
    status: (PairState | null)[][];
    n_min: number;
    basis?: string;
    n_effective?: (number | null)[][];
    effect_floor?: number;
    meets_effect_floor?: (boolean | null)[][];
    confidence?: number;
    interval?: ([number, number] | null)[][];
  };
  status_counts: Record<PairState, number>;
  outcome: "MAPPED" | "NOT_MAPPABLE";
  not_mappable: { reason: string; message: string; objects: string[] } | null;
  layout: { points: [number, number][]; extent: number; stress_1?: number; quality?: string; converged: boolean; method?: string } | null;
  // `relative`: each PRIMARY object's hill height under the framed envelope (aia-sociomap-5).
  heights: { metric: string; values: (number | null)[]; support_n: number[]; relative?: (number | null)[] };
  support: { respondents: number; placed: number; not_placed: number; effective_n: number | null; donors: number; weighting: string };
  terrain:
    | { status: "not_computed"; reason: string }
    | {
        status: "computed";
        method: string;
        // `centre`: the framed envelope's grid is centred on the map (aia-sociomap-5), not on 0.
        parameters: { grid_resolution: number; half_extent: number; sigma: number; kernel_cutoff?: number; centre?: [number, number] };
        source_ids: string[];
        height: (number | null)[][];
        governing: (number | null)[][];
      };
  // aia-sociomap-5, a MAPPED map only: the split-half check (null without a score, when the
  // no-reliable-pair rule decides) and the uncertainty radius in units of the map's RMS
  // inter-object distance (null when the bootstrap maps cannot be computed). Drawn on the map by
  // object-map-panel.ts as the panel does (the banner, the uncertainty circle).
  credibility?: {
    rule: "split_half" | "no_reliable_pair";
    split_half: number | null;
    threshold: number;
    weakly_determined: boolean;
    reliable_pairs: number;
    uncertainty_radius: number | null;
  };
  // aia-sociomap-5: the set's objects nobody rated (left out of `object_ids`), the sparse-design
  // note and the respondent map with its taste segments.
  objects_not_placed?: string[];
  sparse_design?: { flag: boolean; share_below_layout_floor: number; weakly_connected: string[] };
  respondents?: { status: "not_computed"; reason: string } | SignedOffRespondents;
};

type StoredMap = { artifact: ObjectMapArtifact; artifact_fingerprint: string; spec_fingerprint: string };

export type BatteryWithMaps = {
  battery_id: string;
  title: string;
  rating_scale?: [number, number];
  objects: { id: string; label: string }[];
  maps?: Record<string, StoredMap>;
};

export type ReadMap =
  | { ok: true; methodId: string; map: ObjectMapArtifact; fingerprint: string }
  | { ok: false; reason: "none" | "contract" };

/** The battery's object map under the newest pinned method; another contract is refused. */
/** One entry of the Sociomap register (complete-study-report B4): a method approved at its exact spec. */
export type RegisterEntry = {
  method_id: string;
  spec_fingerprint: string;
  status: string;
  decided_on: string;
  reader_note: string;
};

export type RecordedMethod = { method_id: string; spec_fingerprint: string; formulas?: Record<string, string> };

/**
 * The register's approval of the map stored under `methodId`: the method the run recorded with
 * that id must match an entry's id and spec fingerprint exactly, and carry no replaced formulas.
 * Anything else, a register not read included, is null: internal, never presumed approved.
 */
export function mapApproval(
  methods: RecordedMethod[] | undefined,
  register: RegisterEntry[] | null,
  methodId: string,
): RegisterEntry | null {
  const recorded = (methods ?? []).find((m) => m.method_id === methodId);
  if (!recorded || !register || (recorded.formulas && Object.keys(recorded.formulas).length > 0)) return null;
  return register.find((e) => e.method_id === methodId && e.spec_fingerprint === recorded.spec_fingerprint
    && e.status === "CLIENT_FACING") ?? null;
}

export function readObjectMap(battery: BatteryWithMaps): ReadMap {
  const maps = battery.maps ?? {};
  const known: string[] = [...OBJECT_MAP_METHODS];
  // A signed-off map is read first, known by its stored estimator, not its name: an edited
  // version stores it under its own name (plan sociomap-5-web, chunk 2).
  const signedOff = Object.keys(maps).find((m) => maps[m]?.artifact?.contract_version === "3" && isSignedOffMap(maps[m].artifact));
  const methodId = signedOff ?? known.find((m) => m in maps) ?? Object.keys(maps).find((m) => !known.includes(m));
  if (!methodId) return { ok: false, reason: "none" };
  const stored = maps[methodId];
  if (stored?.artifact?.contract_version !== "3") return { ok: false, reason: "contract" };
  return { ok: true, methodId, map: stored.artifact, fingerprint: stored.artifact_fingerprint };
}

export type MapObject = {
  id: string;
  label: string;
  x: number;
  y: number;
  height: number | null; // the mean rating on the declared 0-1 scale, as stored
  band: number | null; // 0..9, the display terrace of the stored height; null without one
  primary: boolean;
};

/** How many display terraces the stored 0-1 height is drawn in. */
export const TERRACE_BANDS = 10;

/**
 * The display terrace of a stored 0-1 height: [0, 0.1) is 0 ... [0.9, 1] is 9, on the absolute
 * scale every map shares, never this map's own range. Colour and drawn elevation only; every
 * label prints the stored number, never the band.
 */
export function terraceBand(height: number): number {
  return Math.min(TERRACE_BANDS - 1, Math.max(0, Math.floor(height * TERRACE_BANDS)));
}

/** How high the lowest terrace is drawn: a thin sheet, so a hill never sits on the ground that
 * means "bez dat", yet the lowest band does not read as a slab (the approved design's base). */
export const TERRACE_BASE = 0.03;

/** The display elevation of a stored height: the top of its terrace, `TERRACE_BASE` plus a
 * tenth per band above the lowest. Presentation only; labels print the stored number. */
export function terraceLevel(height: number): number {
  return TERRACE_BASE + terraceBand(height) / TERRACE_BANDS;
}

/** A stored 0-1 height read on the battery's declared rating scale, when it declares one. */
export function originalRating(height: number | null, scale?: [number, number]): number | null {
  if (height === null || !scale) return null;
  return scale[0] + height * (scale[1] - scale[0]);
}

/** The placed objects in the artifact's order, labelled from the battery. */
export function mapObjects(battery: BatteryWithMaps, map: ObjectMapArtifact): MapObject[] {
  if (!map.layout) return [];
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  return map.object_ids.map((id, k) => {
    const height = map.heights.values[k];
    return {
      id,
      label: label.get(id) ?? id,
      x: map.layout!.points[k][0],
      y: map.layout!.points[k][1],
      height,
      band: height === null ? null : terraceBand(height),
      primary: map.roles[id] === "primary",
    };
  });
}

export type MapLink = { a: string; b: string; r: number; strength: number; sign: "positive" | "negative" };

/**
 * The relations the map draws: PRIMARY pairs whose evidence is RELIABLE and, where the method
 * declares a practical floor, that meet it (Q6's two gates). WEAK and UNKNOWN pairs, and a
 * reliable pair below the floor, draw nothing. Strength is |r| for the line's opacity; the
 * sign is its colour.
 */
export function mapLinks(map: ObjectMapArtifact): MapLink[] {
  const ids = map.object_ids;
  const floor = map.relations.meets_effect_floor;
  const out: MapLink[] = [];
  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      const r = map.relations.r[i][j];
      if (r === null || map.relations.status[i][j] !== "reliable") continue;
      if (floor && floor[i][j] !== true) continue;
      if (map.roles[ids[i]] !== "primary" || map.roles[ids[j]] !== "primary") continue;
      out.push({ a: ids[i], b: ids[j], r, strength: Math.abs(r), sign: r < 0 ? "negative" : "positive" });
    }
  }
  return out;
}

/** How many PRIMARY pairs the floor alone keeps off the map: reliable, but precisely small. */
export function belowFloor(map: ObjectMapArtifact): number {
  const floor = map.relations.meets_effect_floor;
  if (!floor) return 0;
  let count = 0;
  for (let i = 0; i < map.object_ids.length; i++) {
    for (let j = i + 1; j < map.object_ids.length; j++) {
      const primary = map.roles[map.object_ids[i]] === "primary" && map.roles[map.object_ids[j]] === "primary";
      if (primary && map.relations.status[i][j] === "reliable" && floor[i][j] === false) count++;
    }
  }
  return count;
}

export type TerrainCell = { x: number; y: number; size: number; band: number; owner: string };

/** The stored grid's first sample on each axis and its spacing: the grid spans its half-width
 * about the stored centre, 0 unless the grid is framed on the map. */
export function gridOrigin(parameters: { grid_resolution: number; half_extent: number; centre?: [number, number] }): { x0: number; y0: number; step: number } {
  const [cx, cy] = parameters.centre ?? [0, 0];
  return { x0: cx - parameters.half_extent, y0: cy - parameters.half_extent, step: (2 * parameters.half_extent) / parameters.grid_resolution };
}

/** The stored envelope's cells that have a height, at their map coordinates; none without one. */
export function terrainCells(map: ObjectMapArtifact): TerrainCell[] {
  const terrain = map.terrain;
  if (terrain.status !== "computed") return [];
  const { x0, y0, step } = gridOrigin(terrain.parameters);
  const cells: TerrainCell[] = [];
  terrain.height.forEach((row, gy) =>
    row.forEach((h, gx) => {
      if (h === null) return;
      const owner = terrain.governing[gy][gx];
      cells.push({ x: x0 + gx * step, y: y0 + gy * step, size: step, band: terraceBand(h), owner: owner === null ? "" : terrain.source_ids[owner] });
    }),
  );
  return cells;
}

export const MAP_VIEW = { size: 520, pad: 16 };

export type ViewSize = { width: number; height: number };

/**
 * Map coordinates (the fixed ruler, centred) to the view, y up. Both axes share one scale, so
 * distances read the same in every direction; a wide view centres the square map.
 */
export function toScreen(x: number, y: number, span: number, view: ViewSize = { width: MAP_VIEW.size, height: MAP_VIEW.size }): { sx: number; sy: number } {
  const side = Math.min(view.width, view.height) - 2 * MAP_VIEW.pad;
  const scale = side / (2 * span);
  const left = (view.width - side) / 2;
  const top = (view.height - side) / 2;
  return { sx: left + (x + span) * scale, sy: top + (span - y) * scale };
}

/** The screen size of one map unit in a view (the same on both axes). */
export function screenScale(span: number, view: ViewSize): number {
  return (Math.min(view.width, view.height) - 2 * MAP_VIEW.pad) / (2 * span);
}

/** A square of the map the view is centred on: its centre and half-width, in ruler units. */
export type Frame = { cx: number; cy: number; half: number };

/**
 * The square the view frames (plan object-map-3d-redesign, V3): every stored terrain sample
 * that has a height and every placed object, padded, and never larger than the stored grid.
 * A display zoom only: both axes keep one scale, and every number stays where it is stored.
 */
export function mapFrame(map: ObjectMapArtifact, objects: { x: number; y: number }[], pad = 0.06): Frame {
  const xs: number[] = objects.map((o) => o.x);
  const ys: number[] = objects.map((o) => o.y);
  const t = map.terrain;
  if (t.status === "computed") {
    const { x0, y0, step } = gridOrigin(t.parameters);
    t.height.forEach((row, gy) => row.forEach((h, gx) => { if (h !== null) { xs.push(x0 + gx * step); ys.push(y0 + gy * step); } }));
  }
  const limit = viewSpan(map);
  if (!xs.length) return { cx: 0, cy: 0, half: limit };
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const half = Math.min(limit, Math.max(0.5, Math.max(x1 - x0, y1 - y0) / 2) * (1 + pad));
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, half };
}

/**
 * The top view's mapping: the framed square, centred, its side the approved design's share of
 * the stage (about three quarters of its height), y up, one scale on both axes.
 */
export function frameToScreen(x: number, y: number, frame: Frame, view: ViewSize): { sx: number; sy: number } {
  const k = frameScale(frame, view);
  return { sx: view.width / 2 + (x - frame.cx) * k, sy: view.height / 2 - (y - frame.cy) * k };
}

export function frameScale(frame: Frame, view: ViewSize): number {
  return Math.min(view.width * 0.9, view.height * 0.72) / (2 * frame.half);
}

/**
 * A rendered SVG's markup with every `var(--token)` replaced by its resolved value, so the
 * snapshot keeps its colours outside the page. Nothing but colour references changes.
 */
export function resolveVars(markup: string, value: (token: string) => string): string {
  return markup.replace(/var\((--[\w-]+)\)/g, (whole, token: string) => value(token) || whole);
}

export type Segment = { x1: number; y1: number; x2: number; y2: number };

/**
 * The top view's terrace steps: the shared border of two neighbouring stored cells whose
 * display bands differ, in map coordinates. A null cell has no band and draws no step; the
 * stored heights are only read.
 */
export function terraceEdges(map: ObjectMapArtifact): Segment[] {
  const terrain = map.terrain;
  if (terrain.status !== "computed") return [];
  const { x0, y0, step } = gridOrigin(terrain.parameters);
  const half = step / 2;
  const at = (gy: number, gx: number) => {
    const h = terrain.height[gy]?.[gx];
    return h === null || h === undefined ? null : terraceBand(h);
  };
  const out: Segment[] = [];
  terrain.height.forEach((row, gy) =>
    row.forEach((_, gx) => {
      const here = at(gy, gx);
      if (here === null) return;
      const x = x0 + gx * step;
      const y = y0 + gy * step;
      const right = at(gy, gx + 1);
      if (right !== null && right !== here) out.push({ x1: x + half, y1: y - half, x2: x + half, y2: y + half });
      const up = at(gy + 1, gx);
      if (up !== null && up !== here) out.push({ x1: x - half, y1: y + half, x2: x + half, y2: y + half });
    }),
  );
  return out;
}

/** The stored terrain sample nearest a map point, or null where the stored grid has none. */
export function terrainAt(map: ObjectMapArtifact, x: number, y: number): number | null {
  const terrain = map.terrain;
  if (terrain.status !== "computed") return null;
  const { x0, y0, step } = gridOrigin(terrain.parameters);
  const gx = Math.round((x - x0) / step);
  const gy = Math.round((y - y0) / step);
  return terrain.height[gy]?.[gx] ?? null;
}

/** The half-width the view spans: the terrain's grid when there is one, else the ruler. */
export function viewSpan(map: ObjectMapArtifact): number {
  return map.terrain.status === "computed" ? map.terrain.parameters.half_extent : (map.layout?.extent ?? 2);
}

/** Why a pair is, or is not, drawn -- read from what the artifact stored, in this order. */
export type PairWhy = "drawn" | "undefined" | "unknown" | "weak" | "context" | "below_floor";

export type PairDetail = {
  id: string;
  label: string;
  r: number | null;
  n: number | null;
  nEffective: number | null;
  interval: [number, number] | null;
  confidence: number | null;
  state: PairState | null;
  floor: number | null;
  meetsFloor: boolean | null;
  drawn: boolean;
  why: PairWhy;
};

/**
 * One pair's stored evidence, for the pair card. `drawn` is membership of `mapLinks` -- the one
 * link rule -- and `why` only explains it: an undefined r ("could not be computed") is told
 * apart from an UNKNOWN status with an r ("not enough evidence to read the estimate"), and both
 * from WEAK, a context object and a reliable pair below the floor.
 */
export function pairDetail(battery: BatteryWithMaps, map: ObjectMapArtifact, a: string, b: string, drawnKeys?: Set<string>): PairDetail | null {
  const i = map.object_ids.indexOf(a);
  const j = map.object_ids.indexOf(b);
  if (i < 0 || j < 0 || i === j) return null;
  const rel = map.relations;
  const drawn = (drawnKeys ?? new Set(mapLinks(map).map(linkKey))).has(pairKey(a, b));
  const r = rel.r[i][j];
  const state = rel.status[i][j];
  const meetsFloor = rel.meets_effect_floor?.[i][j] ?? null;
  const context = map.roles[a] !== "primary" || map.roles[b] !== "primary";
  const why: PairWhy = drawn ? "drawn"
    : r === null ? "undefined"
    : state === "weak" ? "weak"
    : state !== "reliable" ? "unknown"
    : context ? "context"
    : meetsFloor === false ? "below_floor"
    : "unknown";
  return {
    id: b,
    label: battery.objects.find((o) => o.id === b)?.label ?? b,
    r,
    n: rel.n[i][j],
    nEffective: rel.n_effective?.[i][j] ?? null,
    interval: rel.interval?.[i][j] ?? null,
    confidence: rel.confidence ?? null,
    state,
    floor: rel.effect_floor ?? null,
    meetsFloor,
    drawn,
    why,
  };
}

/** An unordered pair's key, the same for (a, b) and (b, a). */
export function pairKey(a: string, b: string): string {
  return [a, b].sort().join("|");
}

export function linkKey(link: MapLink): string {
  return pairKey(link.a, link.b);
}

/** The relations of one object, strongest first, each with its state and whether it is drawn;
 * a pair without an r goes last, never first. */
export function relationsOf(battery: BatteryWithMaps, map: ObjectMapArtifact, id: string): PairDetail[] {
  if (map.object_ids.indexOf(id) < 0) return [];
  const drawn = new Set(mapLinks(map).map(linkKey));
  return map.object_ids
    .filter((other) => other !== id)
    .map((other) => pairDetail(battery, map, id, other, drawn)!)
    .sort((a, b) => (b.r === null ? -1 : Math.abs(b.r)) - (a.r === null ? -1 : Math.abs(a.r)));
}

/** The objects by stored height, highest first; an object without a height goes last. Ties
 * keep the artifact's order. */
export function rankedByHeight(objects: MapObject[]): MapObject[] {
  return [...objects].sort((a, b) => (b.height ?? -Infinity) - (a.height ?? -Infinity));
}

export type Rect = { x: number; y: number; w: number; h: number };
export type LabelBox = { id: string; ax: number; ay: number; w: number; h: number };

const overlaps = (a: Rect, b: Rect) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

/**
 * Where each label goes on screen: just above its pin if that is free, else the nearest free
 * slot beside or below it, never over another label, a panel (`obstacles`) or any pin --
 * its own included -- and inside `bounds`. Earlier items win (put the selected object first). Only
 * the annotation moves: the anchors -- the stored positions on screen -- are inputs and are
 * returned untouched by construction. When nothing is free the label keeps its first choice.
 */
export function placeLabels(items: LabelBox[], obstacles: Rect[], bounds: ViewSize, gap = 4): Map<string, Rect> {
  const margin = 4;
  const pin = 9;
  const taken: Rect[] = obstacles.filter((o) => o.w > 0 && o.h > 0);
  const pins = new Map(items.map((it) => [it.id, { x: it.ax - pin, y: it.ay - pin, w: 2 * pin, h: 2 * pin }]));
  const clamp = (r: Rect): Rect => ({
    ...r,
    x: Math.max(margin, Math.min(bounds.width - r.w - margin, r.x)),
    y: Math.max(margin, Math.min(bounds.height - r.h - margin, r.y)),
  });
  const out = new Map<string, Rect>();
  for (const it of items) {
    const ax = it.ax - it.w / 2;
    const ay = it.ay - pin - gap - it.h;
    const blocked = (r: Rect) => taken.some((t) => overlaps(r, t)) || [...pins.values()].some((p) => overlaps(r, p));
    let best: Rect | null = null;
    let distance = Infinity;
    for (const dx of [0, -it.w / 4, it.w / 4, -(it.w / 2 - 12), it.w / 2 - 12, -(it.w / 2 + 16), it.w / 2 + 16]) {
      for (let k = -6; k <= 6; k++) {
        const r = clamp({ x: ax + dx, y: ay + k * (it.h + 4), w: it.w, h: it.h });
        if (blocked(r)) continue;
        // How far the label is from its pin as the eye reads it: the gap from the pin to the
        // nearest point of the label, a little dearer below the pin than above it.
        const gx = Math.max(r.x - it.ax, 0, it.ax - (r.x + r.w));
        const gy = Math.max(r.y - it.ay, 0, it.ay - (r.y + r.h));
        const d = Math.hypot(gx, gy) + (r.y > it.ay ? 6 : 0) + Math.abs(r.x + r.w / 2 - it.ax) * 0.02;
        if (d < distance) { distance = d; best = r; }
      }
    }
    const chosen = best ?? clamp({ x: ax, y: ay, w: it.w, h: it.h });
    taken.push(chosen);
    out.set(it.id, chosen);
  }
  return out;
}

/** A label's width on screen, estimated from its text (IBM Plex Sans runs about 0.56 em). */
export function labelWidth(lines: string[], fontSize: number, padding: number): number {
  return Math.ceil(Math.max(...lines.map((l) => l.length), 1) * fontSize * 0.56) + 2 * padding;
}
