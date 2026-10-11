import { describe, expect, it } from "vitest";
import fixture from "./fixtures/object-map.json";
import { type BatteryWithMaps, mapFrame, mapObjects, readObjectMap, terraceBand, terraceLevel } from "./object-map-view";
import { boundedCamera, easeOut, faceLight, INITIAL_CAMERA, plinthSides, projectTerrain, TERRAIN_VIEW, terraceLayers, terrainMesh } from "./object-map-3d";

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
    expect(terrainMesh(source)[0].vertices.map((v) => v.elevation)).toEqual([0.3, 0.7, 0.5]);
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
    expect(projectTerrain({ x: 1, y: 1, height: 0.3 }, INITIAL_CAMERA, 2, TERRAIN_VIEW)).toEqual(projectTerrain({ x: 1, y: 1, height: 0.3 }, INITIAL_CAMERA, 2));
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
  it("draws terraces: elevation is the stored height's display band, the stored height stays on the vertex", () => {
    const faces = terrainMesh(map());
    let risers = 0;
    for (const face of faces) {
      for (const v of face.vertices) expect(v.elevation).toBe(terraceLevel(v.height));
      const bands = face.vertices.map((v) => terraceBand(v.height));
      expect(face.band).toBe(Math.max(...bands));
      expect(face.riser).toBe(new Set(bands).size > 1);
      if (face.riser) risers++;
    }
    expect(risers).toBeGreaterThan(0);
    expect(risers).toBeLessThan(faces.length);
  });
  it("projects the drawn elevation, so relief and the opening rise change pixels only", () => {
    const v = { x: 0.5, y: -0.5, height: 0.63, elevation: 0.7 };
    const drawn = projectTerrain(v, INITIAL_CAMERA, 2);
    expect(drawn).toEqual(projectTerrain({ x: 0.5, y: -0.5, height: 0.7 }, INITIAL_CAMERA, 2));
    expect(v).toEqual({ x: 0.5, y: -0.5, height: 0.63, elevation: 0.7 });
    const flat = projectTerrain(v, { ...INITIAL_CAMERA, relief: 0 }, 2);
    expect(flat).toEqual(projectTerrain({ x: 0.5, y: -0.5, height: 0 }, INITIAL_CAMERA, 2));
    expect([easeOut(-1), easeOut(0), easeOut(1), easeOut(2)]).toEqual([0, 0, 1, 1]);
    expect(easeOut(0.5)).toBeGreaterThan(0.5);
  });
  it("keeps the ruler square in any measured view and builds a plinth below the ground", () => {
    const view = { width: 360, height: 480 };
    const camera = { ...INITIAL_CAMERA, yaw: 0, elevation: Math.PI / 2 };
    const c = projectTerrain({ x: 0, y: 0, height: 0 }, camera, 2, view);
    const x = projectTerrain({ x: 1, y: 0, height: 0 }, camera, 2, view);
    const y = projectTerrain({ x: 0, y: 1, height: 0 }, camera, 2, view);
    expect(x.sx - c.sx).toBeCloseTo(c.sy - y.sy);
    expect(c.sx).toBe(view.width / 2);
    const sides = plinthSides(2);
    expect(sides).toHaveLength(4);
    for (const side of sides) expect(Math.min(...side.map((v) => v.height))).toBeLessThan(0);
  });
  it("projects a framed square the same way as the whole grid around its centre", () => {
    const frame = { cx: 0.5, cy: -0.25, half: 2 };
    const shifted = projectTerrain({ x: 1.5, y: 0.75, height: 0.4 }, INITIAL_CAMERA, frame);
    expect(shifted).toEqual(projectTerrain({ x: 1, y: 1, height: 0.4 }, INITIAL_CAMERA, 2));
  });
});

describe("terraces cut from the stored mesh", () => {
  const source = map();
  if (source.terrain.status !== "computed") throw new Error("fixture");
  const terrain = source.terrain;
  const layers = terraceLayers(source);
  const n = terrain.parameters.grid_resolution + 1;
  const span = terrain.parameters.half_extent;
  const step = (2 * span) / (n - 1);
  const stored = (x: number, y: number) => terrain.height[Math.round((y + span) / step)]?.[Math.round((x + span) / step)];

  it("makes ten layers, each drawn at its band's top and rising from the one below", () => {
    expect(layers.map((l) => l.band)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    for (const l of layers) {
      expect(l.base).toBeCloseTo(l.band / 10);
      expect(l.top).toBeCloseTo((l.band + 1) / 10);
    }
  });

  it("invents no value: every corner is a stored sample at or above the level, or an edge crossing exactly at it", () => {
    for (const l of layers) {
      const level = l.band / 10;
      for (const piece of l.pieces) for (const v of piece) {
        const onGrid = Math.abs((v.x + span) / step - Math.round((v.x + span) / step)) < 1e-9 && Math.abs((v.y + span) / step - Math.round((v.y + span) / step)) < 1e-9;
        if (onGrid) {
          const h = stored(v.x, v.y);
          expect(h).not.toBeNull();
          if (l.band > 0) expect(h!).toBeGreaterThanOrEqual(level - 1e-12);
        } else {
          // On a grid edge (one coordinate on the grid), between two stored samples whose
          // linear interpolation there is the level.
          const gx = (v.x + span) / step, gy = (v.y + span) / step;
          const alongX = Math.abs(gy - Math.round(gy)) < 1e-9;
          const diagonal = !alongX && Math.abs(gx - Math.round(gx)) > 1e-9;
          if (diagonal) continue; // the triangles' shared diagonal: checked by the sampling test
          const [a, b, s] = alongX
            ? [stored(-span + Math.floor(gx) * step, v.y), stored(-span + Math.ceil(gx) * step, v.y), gx - Math.floor(gx)]
            : [stored(v.x, -span + Math.floor(gy) * step), stored(v.x, -span + Math.ceil(gy) * step), gy - Math.floor(gy)];
          expect(a! + s * (b! - a!)).toBeCloseTo(level, 9);
        }
      }
    }
  });

  it("puts every point of the drawn surface in its own band's terrace and no higher one", () => {
    const inside = (p: { x: number; y: number }, poly: { x: number; y: number }[]) => {
      let sign = 0;
      for (let k = 0; k < poly.length; k++) {
        const a = poly[k], b = poly[(k + 1) % poly.length];
        const c = (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x);
        if (Math.abs(c) < 1e-12) continue;
        if (sign === 0) sign = Math.sign(c); else if (Math.sign(c) !== sign) return false;
      }
      return true;
    };
    let checked = 0;
    for (const face of terrainMesh(source)) {
      const [a, b, c] = face.vertices;
      for (const [u, v] of [[0.2, 0.3], [0.6, 0.25], [0.15, 0.7]]) {
        const p = { x: a.x + u * (b.x - a.x) + v * (c.x - a.x), y: a.y + u * (b.y - a.y) + v * (c.y - a.y) };
        const h = a.height + u * (b.height - a.height) + v * (c.height - a.height);
        const band = terraceBand(h);
        if (Math.abs(h * 10 - Math.round(h * 10)) < 1e-6) continue; // on a step
        expect(layers[band].pieces.some((piece) => inside(p, piece))).toBe(true);
        if (band < 9) expect(layers[band + 1].pieces.some((piece) => inside(p, piece))).toBe(false);
        checked++;
      }
    }
    expect(checked).toBeGreaterThan(1000);
  });

  it("draws nothing where the stored grid has a hole, and nothing at all without a terrain", () => {
    const small = map();
    small.terrain = { status: "computed", method: "object_envelope", source_ids: [], parameters: { grid_resolution: 1, half_extent: 1, sigma: 0.25, kernel_cutoff: 0.001 },
      height: [[0.2, null], [0.4, 0.6]], governing: [[0, null], [0, 0]] };
    // Only the triangle (-1,-1), (1,1), (-1,1) has three stored samples (the region y >= x);
    // the one with the null corner draws nothing in any terrace.
    const cut = terraceLayers(small);
    const points = cut.flatMap((l) => l.pieces.flat());
    expect(points.length).toBeGreaterThan(0);
    for (const v of points) expect(v.y).toBeGreaterThanOrEqual(v.x - 1e-12);
    expect(cut[0].pieces).toHaveLength(0); // all three samples >= 0.1: covered by higher terraces
    expect(cut[2].pieces.length).toBeGreaterThan(0);
    small.terrain = { status: "not_computed", reason: "x" };
    expect(terraceLayers(small)).toEqual([]);
    expect(JSON.stringify(map())).toBe(JSON.stringify(source));
  });

  it("frames the stored terrain and every object, never beyond the grid", () => {
    const battery = fixture.sociomap.batteries[0] as unknown as BatteryWithMaps;
    const objects = mapObjects(battery, source);
    const frame = mapFrame(source, objects);
    expect(frame.half).toBeLessThanOrEqual(span);
    for (const o of objects) {
      expect(Math.abs(o.x - frame.cx)).toBeLessThanOrEqual(frame.half);
      expect(Math.abs(o.y - frame.cy)).toBeLessThanOrEqual(frame.half);
    }
    terrain.height.forEach((row, gy) => row.forEach((h, gx) => {
      if (h === null) return;
      expect(Math.abs(-span + gx * step - frame.cx)).toBeLessThanOrEqual(frame.half + 1e-9);
      expect(Math.abs(-span + gy * step - frame.cy)).toBeLessThanOrEqual(frame.half + 1e-9);
    }));
  });
});

