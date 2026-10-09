// The audit's object map (contract 3, `aia-sociomap-3`) as a person reads it on Results
// (plan sociomap-formula-corrections chunk 5a).
//
// The worker computed everything: positions on the fixed ruler, Stress-1 and its band, each
// pair's signed r with its evidence state and practical floor, the mean-rating heights and
// the envelope terrain. This module only decides how the stored artifact is shown -- which
// cells, which links, in which colour -- and never computes or adjusts a methodological
// number. What the artifact leaves undefined stays undefined: a cell no hill reaches is not
// drawn, and an unknown pair draws no link.

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
  band: number | null; // 0..6 for the sequential palette, null without a height
  primary: boolean;
};

/** A share of the 0-1 scale as a step of the seven-step sequential palette. */
export function band(share: number): number {
  return Math.min(6, Math.max(0, Math.floor(share * 7)));
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
      band: height === null ? null : band(height),
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
      cells.push({ x: -span + gx * step, y: -span + gy * step, size: step, band: band(h), owner: owner === null ? "" : terrain.source_ids[owner] });
    }),
  );
  return cells;
}

export const MAP_VIEW = { size: 520, pad: 16 };

/** Map coordinates (the fixed ruler, centred) to the square view, y up. */
export function toScreen(x: number, y: number, span: number): { sx: number; sy: number } {
  const scale = (MAP_VIEW.size - 2 * MAP_VIEW.pad) / (2 * span);
  return { sx: MAP_VIEW.pad + (x + span) * scale, sy: MAP_VIEW.pad + (span - y) * scale };
}

/** The half-width the view spans: the terrain's grid when there is one, else the ruler. */
export function viewSpan(map: ObjectMapArtifact): number {
  return map.terrain.status === "computed" ? map.terrain.parameters.half_extent : (map.layout?.extent ?? 2);
}

/** The relations of one object, strongest first, each with its state and whether it is drawn. */
export function relationsOf(battery: BatteryWithMaps, map: ObjectMapArtifact, id: string): { id: string; label: string; r: number | null; state: PairState | null; drawn: boolean }[] {
  const i = map.object_ids.indexOf(id);
  if (i < 0) return [];
  const drawn = new Set(mapLinks(map).map((l) => [l.a, l.b].sort().join("|")));
  const label = new Map(battery.objects.map((o) => [o.id, o.label]));
  return map.object_ids
    .map((other, j) => ({
      id: other,
      label: label.get(other) ?? other,
      r: map.relations.r[i][j],
      state: map.relations.status[i][j],
      drawn: drawn.has([id, other].sort().join("|")),
    }))
    .filter((e) => e.id !== id)
    .sort((a, b) => Math.abs(b.r ?? -1) - Math.abs(a.r ?? -1));
}
