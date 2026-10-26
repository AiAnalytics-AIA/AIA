// The smooth terrain's heights and refinement (object-map-smooth.ts): Sociomapy's inverse-distance
// weighting through the PRIMARY objects, and its clamped bicubic upsampling. The WebGL drawing has
// no canvas in jsdom; the panel then draws the blocky terrain (ObjectMapPanel.test.tsx).
import { describe, expect, it } from "vitest";

import { type PanelNode, gridAxis } from "./object-map-panel";
import { idwGrid, refine } from "./object-map-smooth";

const node = (id: string, x: number, y: number, primary = true): PanelNode => ({ id, label: id, x, y, primary, value: null, relative: null });

describe("idwGrid", () => {
  it("passes exactly through each object on a grid point and weighs by 1 / d^3 between them", () => {
    const xs = gridAxis(4); // -62, -31, 0, 31, 62
    const grid = idwGrid([node("a", xs[1], xs[2]), node("b", xs[3], xs[2])], [0.2, 0.8], 4)!;
    expect(grid.ht[2][1]).toBe(0.2);
    expect(grid.ht[2][3]).toBe(0.8);
    // Halfway between the two, both weigh the same: their mean.
    expect(grid.ht[2][2]).toBeCloseTo(0.5, 12);
    // Nearer to b (31 away) than to a (93 away): (0.2 / 93^3 + 0.8 / 31^3) / (1 / 93^3 + 1 / 31^3).
    const wa = 1 / 93 ** 3, wb = 1 / 31 ** 3;
    expect(grid.ht[2][4]).toBeCloseTo((0.2 * wa + 0.8 * wb) / (wa + wb), 12);
    expect(grid.N).toBe(4);
    expect(grid.xs).toEqual(xs);
  });

  it("reads only the PRIMARY objects, and has nothing to draw without one", () => {
    const xs = gridAxis(4);
    const grid = idwGrid([node("a", xs[0], xs[0]), node("context", xs[4], xs[4], false)], [0.6, 0.1], 4)!;
    expect(grid.ht.flat().every((h) => h === 0.6)).toBe(true);
    expect(idwGrid([node("context", 0, 0, false)], [0.4], 4)).toBeNull();
  });
});

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
