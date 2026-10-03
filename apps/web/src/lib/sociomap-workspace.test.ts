import { describe, expect, it } from "vitest";
import {
  INITIAL_CAMERA,
  elevation,
  project,
  surface,
  type Terrain,
} from "./sociomap-workspace";
export const terrain: Terrain = {
  parameters: { grid_resolution: 1, half_extent: 10, z_scale: 26 },
  height_raw: [
    [1, 2],
    [3, 4],
  ],
  height_normalised: [
    [0, 1 / 3],
    [2 / 3, 1],
  ],
  normalizer_lo: 1,
  normalizer_hi: 4,
};
describe("stored map projection", () => {
  it("projects depth in 3D and shows the original x/y from above", () => {
    expect(project(0, 0, 26, INITIAL_CAMERA).y).toBeLessThan(
      project(0, 0, 0, INITIAL_CAMERA).y,
    );
    expect(project(0, 0, 26, { ...INITIAL_CAMERA, pitch: 0 })).toMatchObject({
      x: 450,
      y: 280,
    });
  });
  it("drapes points on stored cells without altering them", () => {
    const before = JSON.stringify(terrain);
    expect(
      elevation(
        { id: "p", x: 0, y: 0, status: "POSITIONED", ratings: [] },
        terrain,
      ),
    ).toBeCloseTo(13);
    expect(surface(terrain, INITIAL_CAMERA)).toHaveLength(2);
    expect(JSON.stringify(terrain)).toBe(before);
  });
  it("does not fill unsupported cells", () => {
    expect(
      surface(
        {
          ...terrain,
          height_raw: [
            [null, 2],
            [3, 4],
          ],
        },
        INITIAL_CAMERA,
      ),
    ).toEqual([]);
  });
});
