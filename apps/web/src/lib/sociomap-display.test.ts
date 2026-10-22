// The signed-off map's display changes against its opening (artifact-sociomap SOC3).
import { describe, expect, it } from "vitest";

import { MAP_REGISTERS, OPENING_DISPLAY, STAGE_MIN, displayChanges, stageHeight } from "./sociomap-display";

describe("what the toolbar changed", () => {
  it("names nothing at the map's opening", () => {
    expect(displayChanges(OPENING_DISPLAY)).toEqual([]);
  });

  it("names each change from the opening, in the toolbar's order", () => {
    expect(displayChanges({ map: "objects", norm: "absolute", relations: "all" })).toEqual([
      { key: "norm", value: "absolute" },
      { key: "relations", value: "all" },
    ]);
    expect(displayChanges({ map: "objects", norm: "range", relations: "selected" })).toEqual([{ key: "relations", value: "selected" }]);
  });

  it("names only the map on the respondent map, where Normalizace and Vztahy are not offered", () => {
    expect(displayChanges({ map: "respondents", norm: "absolute", relations: "all" })).toEqual([{ key: "map", value: "respondents" }]);
  });

  it("keeps the prototype's four registers in their reading order", () => {
    expect(MAP_REGISTERS).toEqual(["computed", "display", "interpretation", "external"]);
  });
});

describe("the stage's height", () => {
  it("is the panel's 700 px where the pane has room", () => {
    expect(stageHeight(1200, 90, 900)).toBe(700);
    expect(stageHeight(406, 159.4, 358)).toBe(246); // rounded down: 246.6 would sit 0.4 px over the pane
  });

  it("is what a short pane leaves under the toolbar, with no floor of its own above it (Codex, #637)", () => {
    expect(stageHeight(245, 88, 800)).toBe(157); // 844 x 390: a phone held sideways
    expect(stageHeight(406, 160, 358)).toBe(246); // 390 x 600: the toolbar wraps
  });

  it("is not much taller than wide on a narrow stage", () => {
    expect(stageHeight(2000, 160, 358)).toBe(393);
    expect(stageHeight(2000, 160, 200)).toBe(360);
  });

  it("keeps a least size where a pane leaves almost nothing", () => {
    expect(stageHeight(100, 88, 800)).toBe(STAGE_MIN);
  });
});
