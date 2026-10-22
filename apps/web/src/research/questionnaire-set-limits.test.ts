import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { SET_HARD_MAX, SET_HARD_MIN, SET_MAX, SET_MIN, setAboveRecommended, setSizeRefused } from "./questionnaire";

// The web's set sizes are the server's: TRACKED_SET_LIMITS = ((hard min, hard max), (recommended
// min, recommended max)), which the compiler (battery_size) and readiness read.
const DESIGN = new URL("../../../../packages/aia_core/src/aia_core/domain/research_design.py", import.meta.url);

describe("a tracked set's size limits", () => {
  it("are research_design.py's TRACKED_SET_LIMITS", () => {
    const m = /^TRACKED_SET_LIMITS: Final = \(\((\d+), (\d+)\), \((\d+), (\d+)\)\)$/m.exec(readFileSync(DESIGN, "utf8"));
    expect(m, "TRACKED_SET_LIMITS no longer reads as two pairs").not.toBeNull();
    expect(m!.slice(1).map(Number)).toEqual([SET_HARD_MIN, SET_HARD_MAX, SET_MIN, SET_MAX]);
  });

  it("allow 16 to 40 with a warning and stop only under four or past forty (Q75 (a))", () => {
    expect([3, 4, 15, 16, 40, 41].map((n) => setSizeRefused(n))).toEqual([true, false, false, false, false, true]);
    expect([4, 15, 16, 40, 41].map((n) => setAboveRecommended(n))).toEqual([false, false, true, true, false]);
  });

  it("follow a stored methodology's limits, not the preset's", () => {
    const stored = { min: 3, max: 30, recommended_min: 5, recommended_max: 12 };
    expect([4, 5, 30, 31].map((n) => setSizeRefused(n, stored))).toEqual([true, false, false, true]);
    expect([12, 13, 30, 31].map((n) => setAboveRecommended(n, stored))).toEqual([false, true, true, false]);
  });
});
