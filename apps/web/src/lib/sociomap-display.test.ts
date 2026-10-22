// The signed-off map's display changes against its opening (artifact-sociomap SOC3).
import { describe, expect, it } from "vitest";

import { MAP_REGISTERS, OPENING_DISPLAY, displayChanges } from "./sociomap-display";

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
