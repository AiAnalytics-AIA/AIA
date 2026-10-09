// Presentation geometry only. Samples and object coordinates belong to the frozen
// contract-3 artifact; this module never evaluates a terrain kernel or a layout.
import { band, type ObjectMapArtifact } from "./object-map-view";

export type TerrainVertex = { x: number; y: number; height: number };
export type TerrainFace = { vertices: [TerrainVertex, TerrainVertex, TerrainVertex]; band: number };
export type TerrainCamera = { yaw: number; elevation: number; zoom: number; relief: number };
export type ProjectedVertex = { sx: number; sy: number; depth: number };
export const TERRAIN_VIEW = { width: 900, height: 620 };
export const INITIAL_CAMERA: TerrainCamera = { yaw: -0.55, elevation: 0.72, zoom: 1, relief: 1 };

/** Triangulate adjacent stored samples. An undefined corner leaves a hole. */
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
    };
  };
  const faces: TerrainFace[] = [];
  const append = (a: TerrainVertex | null, b: TerrainVertex | null, c: TerrainVertex | null) => {
    if (a && b && c) faces.push({ vertices: [a, b, c], band: band((a.height + b.height + c.height) / 3) });
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

/** Orthographic camera: x/y always use the same ruler; height is display-only. */
export function projectTerrain(vertex: TerrainVertex, camera: TerrainCamera, span: number): ProjectedVertex {
  const scale = 0.30 * TERRAIN_VIEW.width / Math.max(span, 0.01) * camera.zoom;
  const x = vertex.x * Math.cos(camera.yaw) - vertex.y * Math.sin(camera.yaw);
  const y = vertex.x * Math.sin(camera.yaw) + vertex.y * Math.cos(camera.yaw);
  const z = vertex.height * span * camera.relief;
  return {
    sx: TERRAIN_VIEW.width / 2 + x * scale,
    sy: TERRAIN_VIEW.height * 0.64 - (y * Math.sin(camera.elevation) + z * Math.cos(camera.elevation)) * scale,
    depth: y * Math.cos(camera.elevation) - z * Math.sin(camera.elevation),
  };
}

/** A surface normal's light intensity, used only for reading the mesh shape. */
export function faceLight(face: TerrainFace, camera: TerrainCamera, span: number): number {
  const [a, b, c] = face.vertices;
  const ux = b.x - a.x, uy = b.y - a.y, uz = (b.height - a.height) * span * camera.relief;
  const vx = c.x - a.x, vy = c.y - a.y, vz = (c.height - a.height) * span * camera.relief;
  const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
  const length = Math.hypot(nx, ny, nz);
  return length === 0 ? 1 : 0.65 + 0.35 * Math.max(0, (-0.4 * nx - 0.3 * ny + 0.866 * nz) / length);
}
