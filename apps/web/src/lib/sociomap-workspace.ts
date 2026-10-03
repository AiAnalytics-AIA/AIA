/** Stored analytical fields. Browser code only projects them for display. */
export type MapPoint = {
  id: string;
  x: number;
  y: number;
  status: "POSITIONED" | "UNDETERMINED";
  ratings: (number | null)[];
};
export type Terrain = {
  parameters: { grid_resolution: number; half_extent: number; z_scale: number };
  height_raw: (number | null)[][];
  height_normalised: number[][];
  normalizer_lo: number;
  normalizer_hi: number;
};
export type MapWorkspace = {
  version: string;
  input_fingerprint: string;
  status: "AVAILABLE" | "UNSUPPORTED";
  reason: string | null;
  object_reason: string | null;
  weighting: "UNWEIGHTED";
  people: MapPoint[];
  anchors: MapPoint[];
  objects: MapPoint[];
  relations: (number | null)[][];
  pair_n: number[][];
  metrics: Record<string, (number | null)[]>;
  respondent_terrain: Terrain | null;
  object_terrains: Record<string, Terrain>;
};
export type Camera = { yaw: number; pitch: number; zoom: number };
export const INITIAL_CAMERA: Camera = { yaw: -0.55, pitch: 0.72, zoom: 1 };

export function project(x: number, y: number, z: number, camera: Camera) {
  const rx = x * Math.cos(camera.yaw) - y * Math.sin(camera.yaw);
  const ry = x * Math.sin(camera.yaw) + y * Math.cos(camera.yaw);
  return {
    x: 450 + rx * 3.6 * camera.zoom,
    y:
      280 +
      (ry * Math.cos(camera.pitch) - z * Math.sin(camera.pitch)) *
        3.6 *
        camera.zoom,
    depth: ry * Math.sin(camera.pitch) + z * Math.cos(camera.pitch),
  };
}

/** Drape a glyph on the stored field; no terrain or metric is recomputed. */
export function elevation(point: MapPoint, terrain: Terrain): number {
  const {
    grid_resolution: n,
    half_extent: span,
    z_scale: scale,
  } = terrain.parameters;
  const u = Math.max(0, Math.min(n, ((point.x + span) / (2 * span)) * n));
  const v = Math.max(0, Math.min(n, ((point.y + span) / (2 * span)) * n));
  const x = Math.min(n - 1, Math.floor(u)),
    y = Math.min(n - 1, Math.floor(v));
  const fx = u - x,
    fy = v - y,
    grid = terrain.height_normalised;
  return (
    (grid[y][x] * (1 - fx) * (1 - fy) +
      grid[y][x + 1] * fx * (1 - fy) +
      grid[y + 1][x] * (1 - fx) * fy +
      grid[y + 1][x + 1] * fx * fy) *
    scale
  );
}

export function surface(terrain: Terrain, camera: Camera) {
  const {
    grid_resolution: n,
    half_extent: span,
    z_scale: scale,
  } = terrain.parameters;
  const triangles: { points: string; depth: number; level: number }[] = [];
  const node = (x: number, y: number) => ({
    ...project(
      -span + (2 * span * x) / n,
      -span + (2 * span * y) / n,
      terrain.height_normalised[y][x] * scale,
      camera,
    ),
    level: terrain.height_normalised[y][x],
  });
  for (let y = 0; y < n; y++)
    for (let x = 0; x < n; x++) {
      // Missing support remains a hole, never a zero-valued hill.
      const cells = [
        [x, y],
        [x + 1, y],
        [x + 1, y + 1],
        [x, y + 1],
      ];
      for (const indices of [
        [0, 1, 2],
        [0, 2, 3],
      ]) {
        if (
          indices.some(
            (i) => terrain.height_raw[cells[i][1]][cells[i][0]] === null,
          )
        )
          continue;
        const p = indices.map((i) => node(cells[i][0], cells[i][1]));
        triangles.push({
          points: p.map((q) => `${q.x},${q.y}`).join(" "),
          depth: p.reduce((s, q) => s + q.depth, 0) / 3,
          level: p.reduce((s, q) => s + q.level, 0) / 3,
        });
      }
    }
  return triangles.sort((a, b) => a.depth - b.depth);
}
