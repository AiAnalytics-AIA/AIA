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

/** The object map a run pins, newest first; a run that pinned `aia-sociomap-2` reads it. */
export const OBJECT_MAP_METHODS = ["aia-sociomap-3", "aia-sociomap-2"] as const;

export type PairState = "reliable" | "weak" | "unknown";

export type ObjectMapArtifact = {
  contract_version: "3";
  spec: { methodology_version: string; relation: { basis: string; n_min: number; confidence: number; effect_floor?: number }; terrain: { sigma: number; sigma_basis: string } | null };
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
  layout: { points: [number, number][]; extent: number; stress_1: number; quality: string; converged: boolean } | null;
  heights: { metric: string; values: (number | null)[]; support_n: number[] };
  support: { respondents: number; placed: number; not_placed: number; effective_n: number | null; donors: number; weighting: string };
  terrain:
    | { status: "not_computed"; reason: string }
    | {
        status: "computed";
        method: string;
        parameters: { grid_resolution: number; half_extent: number; sigma: number; kernel_cutoff: number };
        source_ids: string[];
        height: (number | null)[][];
        governing: (number | null)[][];
      };
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
export function readObjectMap(battery: BatteryWithMaps): ReadMap {
  const maps = battery.maps ?? {};
  const methodId = OBJECT_MAP_METHODS.find((m) => m in maps);
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

/** The display elevation of a stored height: the top of its terrace, so a hill never sits on
 * the ground that means "bez dat". Presentation only. */
export function terraceLevel(height: number): number {
  return (terraceBand(height) + 1) / TERRACE_BANDS;
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

/** The stored envelope's cells that have a height, at their map coordinates; none without one. */
export function terrainCells(map: ObjectMapArtifact): TerrainCell[] {
  const terrain = map.terrain;
  if (terrain.status !== "computed") return [];
  const { grid_resolution: n, half_extent: span } = terrain.parameters;
  const step = (2 * span) / n;
  const cells: TerrainCell[] = [];
  terrain.height.forEach((row, gy) =>
    row.forEach((h, gx) => {
      if (h === null) return;
      const owner = terrain.governing[gy][gx];
      cells.push({ x: -span + gx * step, y: -span + gy * step, size: step, band: terraceBand(h), owner: owner === null ? "" : terrain.source_ids[owner] });
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

export type Segment = { x1: number; y1: number; x2: number; y2: number };

/**
 * The top view's terrace steps: the shared border of two neighbouring stored cells whose
 * display bands differ, in map coordinates. A null cell has no band and draws no step; the
 * stored heights are only read.
 */
export function terraceEdges(map: ObjectMapArtifact): Segment[] {
  const terrain = map.terrain;
  if (terrain.status !== "computed") return [];
  const { grid_resolution: n, half_extent: span } = terrain.parameters;
  const step = (2 * span) / n;
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
      const x = -span + gx * step;
      const y = -span + gy * step;
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
  const { grid_resolution: n, half_extent: span } = terrain.parameters;
  const gx = Math.round(((x + span) * n) / (2 * span));
  const gy = Math.round(((y + span) * n) / (2 * span));
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
 * Where each label goes on screen: above its anchor if that is free, else the nearest free
 * slot beside or below it, never over another label, a panel (`obstacles`) or another
 * object's pin, and inside `bounds`. Earlier items win (put the selected object first). Only
 * the annotation moves: the anchors -- the stored positions on screen -- are inputs and are
 * returned untouched by construction. When nothing is free the label keeps its first choice.
 */
export function placeLabels(items: LabelBox[], obstacles: Rect[], bounds: ViewSize, gap = 6): Map<string, Rect> {
  const margin = 4;
  const pin = 7;
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
    const ay = it.ay - it.h - gap;
    const blocked = (r: Rect) => taken.some((t) => overlaps(r, t)) || [...pins].some(([id, p]) => id !== it.id && overlaps(r, p));
    let best: Rect | null = null;
    let distance = Infinity;
    for (const dx of [0, -(it.w / 2 + 16), it.w / 2 + 16]) {
      for (let k = -6; k <= 6; k++) {
        const r = clamp({ x: ax + dx, y: ay + k * (it.h + 4), w: it.w, h: it.h });
        if (blocked(r)) continue;
        const d = Math.hypot(r.x - ax, (r.y - ay) * 1.2);
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
