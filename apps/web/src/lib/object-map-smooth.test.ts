// The smooth terrain's refinement (object-map-smooth.ts): the Sociomapy app's clamped bicubic
// upsampling of the stored terrain. The WebGL drawing has no canvas in jsdom; the panel then draws
// the blocky terrain (ObjectMapPanel.test.tsx).
import { describe, expect, it } from "vitest";

import { refine } from "./object-map-smooth";
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
