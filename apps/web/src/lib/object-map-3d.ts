// Presentation geometry only. Samples and object coordinates belong to the frozen
// contract-3 artifact; this module never evaluates a terrain kernel or a layout.
//
// Every vertex carries the stored height (`height`) and, separately, the elevation it is drawn
// at (`elevation`): the top of its display terrace (plan object-map-3d-redesign). The terraces
// are a picture of the stored grid on the absolute 0-1 scale; the stored number is what every
// label prints.
import { type ObjectMapArtifact, type ViewSize, terraceBand, terraceLevel } from "./object-map-view";

export type TerrainVertex = { x: number; y: number; height: number; elevation?: number };
export type TerrainFace = { vertices: [TerrainVertex, TerrainVertex, TerrainVertex]; band: number; riser: boolean };
export type TerrainCamera = { yaw: number; elevation: number; zoom: number; relief: number };
export type ProjectedVertex = { sx: number; sy: number; depth: number };
export const TERRAIN_VIEW: ViewSize = { width: 900, height: 620 };
export const INITIAL_CAMERA: TerrainCamera = { yaw: -0.55, elevation: 0.66, zoom: 1.3, relief: 1 };

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
  const step = 2 * parameters.half_extent / (n - 1);
  const vertex = (row: number, col: number): TerrainVertex | null => {
    const h = height[row][col];
    return h === null || !Number.isFinite(h) ? null : {
      x: -parameters.half_extent + col * step,
      y: -parameters.half_extent + row * step,
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
 * The drawn height of the full 0-1 scale as a share of the half-ruler. Display only: at 0.55
 * the narrow stored hills read as low terraced massifs rather than spikes (relief scales it).
 */
export const HEIGHT_SCALE = 0.55;

/** Where a vertex is drawn vertically: its display elevation when it has one, else its height. */
const drawnHeight = (v: TerrainVertex) => v.elevation ?? v.height;

/**
 * Orthographic camera: x/y always use the same ruler; height is display-only. `view` is the
 * drawing's size in CSS pixels (the measured stage), so labels and hit targets keep their size.
 */
export function projectTerrain(vertex: TerrainVertex, camera: TerrainCamera, span: number, view: ViewSize = TERRAIN_VIEW): ProjectedVertex {
  const scale = 0.30 * Math.min(view.width, view.height * 1.5) / Math.max(span, 0.01) * camera.zoom;
  const x = vertex.x * Math.cos(camera.yaw) - vertex.y * Math.sin(camera.yaw);
  const y = vertex.x * Math.sin(camera.yaw) + vertex.y * Math.cos(camera.yaw);
  const z = drawnHeight(vertex) * span * HEIGHT_SCALE * camera.relief;
  return {
    sx: view.width / 2 + x * scale,
    sy: view.height * 0.52 - (y * Math.sin(camera.elevation) + z * Math.cos(camera.elevation)) * scale,
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

/** The display plinth under the map square: four side walls below the ground, for depth. */
export function plinthSides(span: number, depth = 0.06): TerrainVertex[][] {
  const c = [[-span, -span], [span, -span], [span, span], [-span, span]];
  return c.map(([x, y], k) => {
    const [nx, ny] = c[(k + 1) % 4];
    return [
      { x, y, height: 0 }, { x: nx, y: ny, height: 0 },
      { x: nx, y: ny, height: -depth }, { x, y, height: -depth },
    ];
  });
}

/** Ease-out cubic for the opening rise: a presentation curve, nothing more. */
export function easeOut(t: number): number {
  return 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);
}
