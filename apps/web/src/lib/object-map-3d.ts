// Presentation geometry only. Samples and object coordinates belong to the frozen
// contract-3 artifact; this module never evaluates a terrain kernel or a layout.
//
// Every vertex carries the stored height (`height`) and, separately, the elevation it is drawn
// at (`elevation`): the top of its display terrace (plan object-map-3d-redesign). The terraces
// are a picture of the stored grid on the absolute 0-1 scale; the stored number is what every
// label prints.
import { type Frame, type ObjectMapArtifact, type ViewSize, TERRACE_BANDS, gridOrigin, terraceBand, terraceLevel } from "./object-map-view";

export type TerrainVertex = { x: number; y: number; height: number; elevation?: number };
export type TerrainFace = { vertices: [TerrainVertex, TerrainVertex, TerrainVertex]; band: number; riser: boolean };
export type TerrainCamera = { yaw: number; elevation: number; zoom: number; relief: number };
export type ProjectedVertex = { sx: number; sy: number; depth: number };
export const TERRAIN_VIEW: ViewSize = { width: 900, height: 620 };
/** The approved design's view: from the front right, about 27 degrees above the plinth. */
export const INITIAL_CAMERA: TerrainCamera = { yaw: -0.66, elevation: 0.48, zoom: 1, relief: 1 };
/** Looking straight down: where the glide into 3D starts. */
export const TOP_CAMERA: TerrainCamera = { yaw: 0, elevation: Math.PI / 2, zoom: 1, relief: 1 };

/**
 * Triangulate adjacent stored samples. An undefined corner leaves a hole. A face whose corners
 * share a terrace is flat at that terrace; a face across terraces is a riser, coloured as the
 * upper terrace (the step's light edge is drawn on it).
 */
export function terrainMesh(map: ObjectMapArtifact): TerrainFace[] {
  if (map.terrain.status !== "computed") return [];
  const { height, parameters } = map.terrain;
  // The backend contract declares intervals, so a 64 grid has 65 samples.
  const n = parameters.grid_resolution + 1;
  if (n < 2 || height.length !== n || height.some((row) => row.length !== n)) return [];
  const { x0, y0, step } = gridOrigin(parameters);
  const vertex = (row: number, col: number): TerrainVertex | null => {
    const h = height[row][col];
    return h === null || !Number.isFinite(h) ? null : {
      x: x0 + col * step,
      y: y0 + row * step,
      height: h,
      elevation: terraceLevel(h),
    };
  };
  const faces: TerrainFace[] = [];
  const append = (a: TerrainVertex | null, b: TerrainVertex | null, c: TerrainVertex | null) => {
    if (!a || !b || !c) return;
    const bands = [a, b, c].map((v) => terraceBand(v.height));
    faces.push({ vertices: [a, b, c], band: Math.max(...bands), riser: bands.some((k) => k !== bands[0]) });
  };
  for (let row = 0; row < n - 1; row++) {
    for (let col = 0; col < n - 1; col++) {
      const a = vertex(row, col), b = vertex(row, col + 1);
      const c = vertex(row + 1, col + 1), d = vertex(row + 1, col);
      append(a, b, c);
      append(a, c, d);
    }
  }
  return faces;
}

/** Bound display controls without mutating the underlying camera or artifact. */
export function boundedCamera(camera: TerrainCamera): TerrainCamera {
  return {
    yaw: camera.yaw,
    elevation: Math.max(0.15, Math.min(Math.PI / 2, camera.elevation)),
    zoom: Math.max(0.65, Math.min(2.5, camera.zoom)),
    relief: Math.max(0.5, Math.min(2, camera.relief)),
  };
}

/**
 * The drawn height of the full 0-1 scale as a share of the frame's half-width. Display only:
 * the stored hills are narrow (sigma 0.25 on the ruler), and at the prototype's proportion
 * they read as spikes; at this one they read as terraced massifs (relief scales it).
 */
export const HEIGHT_SCALE = 0.62;

/** Where a vertex is drawn vertically: its display elevation when it has one, else its height. */
const drawnHeight = (v: TerrainVertex) => v.elevation ?? v.height;

const asFrame = (frame: Frame | number): Frame => (typeof frame === "number" ? { cx: 0, cy: 0, half: frame } : frame);

/**
 * Orthographic camera: x/y always use the same ruler; height is display-only. `frame` is the
 * square the view is centred on (a half-width alone means the whole grid around the origin);
 * `view` is the drawing's size in CSS pixels (the measured stage), so labels and hit targets
 * keep their size.
 */
export function projectTerrain(vertex: TerrainVertex, camera: TerrainCamera, frame: Frame | number, view: ViewSize = TERRAIN_VIEW): ProjectedVertex {
  const f = asFrame(frame);
  const half = Math.max(f.half, 0.01);
  const scale = 0.27 * Math.min(view.width, view.height * 1.6) / half * camera.zoom;
  const px = vertex.x - f.cx, py = vertex.y - f.cy;
  const x = px * Math.cos(camera.yaw) - py * Math.sin(camera.yaw);
  const y = px * Math.sin(camera.yaw) + py * Math.cos(camera.yaw);
  const z = drawnHeight(vertex) * half * HEIGHT_SCALE * camera.relief;
  return {
    sx: view.width / 2 + x * scale,
    sy: view.height * 0.56 - (y * Math.sin(camera.elevation) + z * Math.cos(camera.elevation)) * scale,
    depth: y * Math.cos(camera.elevation) - z * Math.sin(camera.elevation),
  };
}

/** A surface normal's light intensity, used only for reading the mesh shape. */
export function faceLight(face: TerrainFace, camera: TerrainCamera, span: number): number {
  const [a, b, c] = face.vertices;
  const ux = b.x - a.x, uy = b.y - a.y, uz = (drawnHeight(b) - drawnHeight(a)) * span * HEIGHT_SCALE * camera.relief;
  const vx = c.x - a.x, vy = c.y - a.y, vz = (drawnHeight(c) - drawnHeight(a)) * span * HEIGHT_SCALE * camera.relief;
  const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
  const length = Math.hypot(nx, ny, nz);
  return length === 0 ? 1 : 0.65 + 0.35 * Math.max(0, (-0.4 * nx - 0.3 * ny + 0.866 * nz) / length);
}

/** The display plinth under the framed square: four side walls below the ground, for depth. */
export function plinthSides(frame: Frame | number, depth = 0.1): TerrainVertex[][] {
  const f = asFrame(frame);
  const r = f.half;
  const c = [[f.cx - r, f.cy - r], [f.cx + r, f.cy - r], [f.cx + r, f.cy + r], [f.cx - r, f.cy + r]];
  // `depth` is a share of the half-width, drawn below the ground (negative elevation).
  const low = -depth / HEIGHT_SCALE;
  return c.map(([x, y], k) => {
    const [nx, ny] = c[(k + 1) % 4];
    return [
      { x, y, height: 0 }, { x: nx, y: ny, height: 0 },
      { x: nx, y: ny, height: low }, { x, y, height: low },
    ];
  });
}

export type Point = { x: number; y: number };
/** A step of a terrace: the stretch of its edge in one triangle, and which way is downhill. */
export type TerraceEdge = { a: Point; b: Point; nx: number; ny: number };
/**
 * One display terrace: the part of the stored surface at or above `band / 10`, cut out of the
 * same triangles `terrainMesh` draws. `pieces` are its flat top (counter-clockwise polygons
 * whose union is the region; a part covered by the next terrace is left out), drawn at
 * elevation `top`; `edges` are its riser, from `base` up to `top`.
 */
export type TerraceLayer = { band: number; base: number; top: number; pieces: Point[][]; edges: TerraceEdge[] };

/**
 * The stored terrain as ten flat terraces (plan object-map-3d-redesign, V18). Each layer is the
 * region where the piecewise-linear surface between stored samples -- the surface the mesh
 * already draws -- is at or above its band's lower bound, found by clipping each triangle
 * against that level. No value is invented: a piece's corners are stored samples or points
 * where an edge between two stored samples crosses the threshold, and nothing is evaluated
 * outside a triangle whose three samples are stored.
 */
export function terraceLayers(map: ObjectMapArtifact): TerraceLayer[] {
  if (map.terrain.status !== "computed") return [];
  const { height, parameters } = map.terrain;
  const n = parameters.grid_resolution + 1;
  if (n < 2 || height.length !== n || height.some((row) => row.length !== n)) return [];
  const { x0, y0, step } = gridOrigin(parameters);
  type V = Point & { h: number };
  const at = (row: number, col: number): V | null => {
    const h = height[row][col];
    return h === null || !Number.isFinite(h) ? null : { x: x0 + col * step, y: y0 + row * step, h };
  };
  const triangles: [V, V, V][] = [];
  const shared = new Map<string, number>();
  const key = (p: V, q: V) => (p.x < q.x || (p.x === q.x && p.y < q.y) ? `${p.x},${p.y}|${q.x},${q.y}` : `${q.x},${q.y}|${p.x},${p.y}`);
  for (let row = 0; row < n - 1; row++) {
    for (let col = 0; col < n - 1; col++) {
      const a = at(row, col), b = at(row, col + 1), c = at(row + 1, col + 1), d = at(row + 1, col);
      for (const t of [[a, b, c], [a, c, d]] as (V | null)[][]) {
        if (!t[0] || !t[1] || !t[2]) continue;
        triangles.push(t as [V, V, V]);
        for (let k = 0; k < 3; k++) { const e = key(t[k]!, t[(k + 1) % 3]!); shared.set(e, (shared.get(e) ?? 0) + 1); }
      }
    }
  }
  const cross = (p: V, q: V, level: number): Point => {
    const s = (level - p.h) / (q.h - p.h);
    return { x: p.x + s * (q.x - p.x), y: p.y + s * (q.y - p.y) };
  };
  const layers: TerraceLayer[] = [];
  for (let band = 0; band < TERRACE_BANDS; band++) {
    const low = band === 0 ? -Infinity : band / TERRACE_BANDS;
    const high = band === TERRACE_BANDS - 1 ? Infinity : (band + 1) / TERRACE_BANDS;
    const pieces: Point[][] = [];
    const edges: TerraceEdge[] = [];
    for (const t of triangles) {
      const above = t.map((v) => v.h >= low);
      if (!above.some(Boolean)) continue;
      if (t.every((v) => v.h >= high)) continue; // covered by the next terrace
      const piece: Point[] = [];
      const crossing: Point[] = [];
      for (let k = 0; k < 3; k++) {
        const p = t[k], q = t[(k + 1) % 3];
        if (above[k]) piece.push({ x: p.x, y: p.y });
        if (above[k] !== above[(k + 1) % 3]) { const c = cross(p, q, low); piece.push(c); crossing.push(c); }
      }
      pieces.push(piece);
      if (crossing.length === 2) {
        // Downhill is against the triangle's gradient.
        const [p, q, r] = t;
        const det = (q.x - p.x) * (r.y - p.y) - (r.x - p.x) * (q.y - p.y);
        const gx = ((q.h - p.h) * (r.y - p.y) - (r.h - p.h) * (q.y - p.y)) / det;
        const gy = ((r.h - p.h) * (q.x - p.x) - (q.h - p.h) * (r.x - p.x)) / det;
        const len = Math.hypot(gx, gy) || 1;
        edges.push({ a: crossing[0], b: crossing[1], nx: -gx / len, ny: -gy / len });
      }
      if (band === 0) {
        // The rim of the stored region: a triangle side no other stored triangle shares.
        for (let k = 0; k < 3; k++) {
          const p = t[k], q = t[(k + 1) % 3], r = t[(k + 2) % 3];
          if (shared.get(key(p, q)) !== 1) continue;
          let nx = q.y - p.y, ny = -(q.x - p.x);
          if (nx * (r.x - p.x) + ny * (r.y - p.y) > 0) { nx = -nx; ny = -ny; }
          const len = Math.hypot(nx, ny) || 1;
          edges.push({ a: { x: p.x, y: p.y }, b: { x: q.x, y: q.y }, nx: nx / len, ny: ny / len });
        }
      }
    }
    layers.push({ band, base: band === 0 ? 0 : terraceLevel((band - 1) / TERRACE_BANDS), top: terraceLevel(band / TERRACE_BANDS), pieces, edges });
  }
  return layers;
}

/** Ease-out cubic for the opening rise: a presentation curve, nothing more. */
export function easeOut(t: number): number {
  return 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);
}
