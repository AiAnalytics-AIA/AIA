import { describe, expect, it } from "vitest";
import fixture from "./fixtures/object-map.json";
import { type BatteryWithMaps, readObjectMap } from "./object-map-view";
import { boundedCamera, faceLight, INITIAL_CAMERA, projectTerrain, terrainMesh } from "./object-map-3d";

function map() {
  const read = readObjectMap(fixture.sociomap.batteries[0] as unknown as BatteryWithMaps);
  if (!read.ok) throw new Error("fixture");
  return structuredClone(read.map);
}

describe("frozen terrain geometry", () => {
  it("uses stored heights and the fixed grid ruler without changing the artifact", () => {
    const source = map();
    const before = JSON.stringify(source);
    const faces = terrainMesh(source);
    expect(faces.length).toBeGreaterThan(0);
    if (source.terrain.status !== "computed") throw new Error("fixture");
    const n = source.terrain.parameters.grid_resolution + 1;
    const extent = source.terrain.parameters.half_extent;
    for (const face of faces) for (const v of face.vertices) {
      const row = Math.round((v.y + extent) * (n - 1) / (2 * extent));
      const col = Math.round((v.x + extent) * (n - 1) / (2 * extent));
      expect(v.height).toBe(source.terrain.height[row][col]);
    }
    expect(JSON.stringify(source)).toBe(before);
  });
  it("never turns missing terrain into zero or bridges a missing sample", () => {
    const source = map();
    source.terrain = { status: "computed", method: "object_envelope", source_ids: [],
      parameters: { grid_resolution: 1, half_extent: 1, sigma: 0.25, kernel_cutoff: 0.001 },
      height: [[0.2, null], [0.4, 0.6]], governing: [[0, null], [0, 0]] };
    expect(terrainMesh(source)).toHaveLength(1);
    expect(terrainMesh(source)[0].vertices.map((v) => v.height)).toEqual([0.2, 0.6, 0.4]);
    source.terrain.height = [[null, null], [null, null]];
    expect(terrainMesh(source)).toEqual([]);
    source.terrain = { status: "not_computed", reason: "unavailable" };
    expect(terrainMesh(source)).toEqual([]);
  });
  it("rejects an incomplete grid", () => {
    const source = map();
    if (source.terrain.status !== "computed") throw new Error("fixture");
    source.terrain.height.pop();
    expect(terrainMesh(source)).toEqual([]);
  });
  it("rotates on a uniform planar ruler and gives height a separate display axis", () => {
    const camera = { ...INITIAL_CAMERA, yaw: 0, elevation: Math.PI / 2 };
    const center = projectTerrain({ x: 0, y: 0, height: 0 }, camera, 2);
    const x = projectTerrain({ x: 1, y: 0, height: 0 }, camera, 2);
    const y = projectTerrain({ x: 0, y: 1, height: 0 }, camera, 2);
    expect(x.sx - center.sx).toBeCloseTo(center.sy - y.sy);
    const rotated = projectTerrain({ x: 1, y: 0, height: 0 }, { ...camera, yaw: Math.PI / 2 }, 2);
    expect(rotated.sx).toBeCloseTo(y.sx);
    expect(rotated.sy).toBeCloseTo(y.sy);
    const low = projectTerrain({ x: 0, y: 0, height: 0 }, INITIAL_CAMERA, 2);
    const high = projectTerrain({ x: 0, y: 0, height: 1 }, INITIAL_CAMERA, 2);
    expect(high.sx).toBe(low.sx);
    expect(high.sy).toBeLessThan(low.sy);
    expect(projectTerrain({ x: 0, y: 0, height: 1 }, { ...INITIAL_CAMERA, relief: 2 }, 2).sy)
      .toBeCloseTo(low.sy - 2 * (low.sy - high.sy));
  });
  it("bounds controls and keeps lighting finite", () => {
    expect(boundedCamera({ yaw: 10, elevation: -1, zoom: 100, relief: 0 })).toEqual({ yaw: 10, elevation: 0.15, zoom: 2.5, relief: 0.5 });
    for (const face of terrainMesh(map())) {
      expect(faceLight(face, INITIAL_CAMERA, 2)).toBeGreaterThanOrEqual(0.65);
      expect(faceLight(face, INITIAL_CAMERA, 2)).toBeLessThanOrEqual(1);
    }
  });
});
