// The smooth terrain's refinement (object-map-smooth.ts): the Sociomapy app's clamped bicubic
// upsampling of the stored terrain. The WebGL drawing has no canvas in jsdom; the panel then draws
// the terrain as flat triangles (ObjectMapPanel.test.tsx).
import { describe, expect, it } from "vitest";

import { storedTerrains, terrainGrid } from "./object-map-panel";
import { refine } from "./object-map-smooth";
import type { ObjectMapArtifact } from "./object-map-view";
describe("refine", () => {
  it("keeps every original node and fills between them", () => {
    const values = [[0, 0.2, 0.4], [0.2, 0.4, 0.6], [0.4, 0.6, 0.8]];
    const out = refine(values, 4);
    expect(out).toHaveLength(9);
    for (let y = 0; y < 3; y++) for (let x = 0; x < 3; x++) expect(out[y * 4][x * 4]).toBeCloseTo(values[y][x], 12);
    // Inside the grid (the edges repeat their outermost value), a plane stays a plane.
    const plane = Array.from({ length: 5 }, (_, y) => Array.from({ length: 5 }, (_, x) => 0.1 * (x + y)));
    expect(refine(plane, 4)[10][10]).toBeCloseTo(0.5, 12);
    expect(refine(values, 1)).toEqual(values);
  });

  it("never leaves a cell's range, so a peak does not ring into a moat", () => {
    const spike = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 1, 0], [0, 0, 0, 0]];
    const out = refine(spike, 4);
    expect(Math.min(...out.flat())).toBe(0);
    expect(Math.max(...out.flat())).toBe(1);
  });
});

describe("terrainGrid", () => {
  const terrain = (extra: object) => ({ terrain: { status: "computed", method: "framed_relative_idw", source_ids: ["a"], parameters: { grid_resolution: 1, half_extent: 1, sigma: 0.25, centre: [0, 0] }, height: [[0.5, 0.5], [0.5, 0.5]], absolute_height: [[0.9, 0.9], [0.9, 0.9]], governing: [[0, 0], [0, 0]], ...extra } }) as unknown as ObjectMapArtifact;

  it("reads either inverse-distance terrain the map stored, its own or the one beside it", () => {
    const map = terrain({ alternate_method: "framed_relative_idw_falloff", alternate_height: [[0.1, 0.2], [0.3, 0.4]], alternate_absolute_height: [[0.5, 0.6], [0.7, 0.8]] });
    expect(storedTerrains(map)).toEqual(["framed_relative_idw", "framed_relative_idw_falloff"]);
    expect(terrainGrid(map, "framed_relative_idw", false)?.ht).toEqual([[0.5, 0.5], [0.5, 0.5]]);
    expect(terrainGrid(map, "framed_relative_idw", true)?.ht).toEqual([[0.9, 0.9], [0.9, 0.9]]);
    expect(terrainGrid(map, "framed_relative_idw_falloff", false)?.ht).toEqual([[0.1, 0.2], [0.3, 0.4]]);
    expect(terrainGrid(map, "framed_relative_idw_falloff", true)?.ht).toEqual([[0.5, 0.6], [0.7, 0.8]]);
  });

  it("offers only what the map stored: a terrain it lacks is none, not ground at 0", () => {
    expect(storedTerrains(terrain({}))).toEqual(["framed_relative_idw"]);
    expect(terrainGrid(terrain({}), "framed_relative_idw_falloff", false)).toBeNull();
    const envelope = terrain({ method: "framed_relative_envelope" });
    expect(storedTerrains(envelope)).toEqual([]);
    expect(terrainGrid(envelope, "framed_relative_idw", false)).toBeNull();
    expect(storedTerrains({ terrain: { status: "not_computed", reason: "x" } } as unknown as ObjectMapArtifact)).toEqual([]);
  });
});
