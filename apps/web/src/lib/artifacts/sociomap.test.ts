// Sociomapa's part of the Lead contract (artifact-sociomap SOC1): its targets name their battery, its
// display operations are the registry row's and only change the picture, and anything that would
// write to the frozen map is refused by name.
import { describe, expect, it } from "vitest";

import { ARTIFACTS, VIEW_FILTERS, parseAiaId } from "@/lib/workbench-artifacts";
import { FILTER_VALUES, SOCIOMAP, SOCIOMAP_INTERACTION, isRefusal, objectTarget, pairTarget, readMapOp, readTarget, targetWords } from "./sociomap";

const BATTERIES = [
  { battery_id: "set_1", title: "Fiktivní značky", objects: [{ id: "halo", label: "Halo" }, { id: "iris", label: "Iris" }, { id: "gale", label: "Gale" }] },
  { battery_id: "set_2", title: "Varianty", objects: [{ id: "halo", label: "Jemná" }] },
];

describe("the map's row", () => {
  it("is the registry's own, a frozen run the Lead never edits", () => {
    expect(SOCIOMAP).toBe(ARTIFACTS.sociomap);
    expect(SOCIOMAP.artifact).toBe("run");
    expect(SOCIOMAP.edits).toBe(false);
    expect(SOCIOMAP_INTERACTION.refusals).toEqual(["filtr zobrazení nemění výpočet", "externí kontext do výpočtu nevstupuje"]);
  });

  it("gives every filter the registry names its values, and no other", () => {
    expect(Object.keys(FILTER_VALUES).sort()).toEqual([...(VIEW_FILTERS.sociomap ?? [])].sort());
  });
});

describe("targets", () => {
  it("names an object by its battery, as the registry parses it", () => {
    const t = objectTarget("set_1", "halo")!;
    expect(t).toBe("object:set_1/halo");
    expect(parseAiaId(t)).toEqual({ kind: "object", id: "set_1/halo", stage: "sociomap" });
    expect(readTarget(t)).toEqual({ kind: "object", battery: "set_1", object: "halo" });
  });

  it("gives a pair one id whichever end comes first", () => {
    expect(pairTarget("set_1", "iris", "halo")).toBe("pair:set_1/halo~iris");
    expect(pairTarget("set_1", "halo", "iris")).toBe("pair:set_1/halo~iris");
    expect(readTarget("pair:set_1/iris~halo")).toEqual({ kind: "pair", battery: "set_1", a: "halo", b: "iris" });
  });

  it("puts no id on an element whose ids leave the grammar, and reads none back", () => {
    expect(objectTarget("set 1", "halo")).toBeNull();
    expect(objectTarget("set_1", "a/b")).toBeNull();
    expect(pairTarget("set_1", "halo", "halo")).toBeNull();
    expect(pairTarget("set_1", "x~y", "halo")).toBeNull();
    expect(objectTarget("set_1", "o".repeat(80))).toBeNull(); // over the registry's 80 characters
    for (const bad of ["object:halo", "pair:set_1/halo", "pair:set_1/halo~halo", "pair:set_1/a~b~c", "question:q1", "rubbish"]) {
      expect(readTarget(bad)).toBeNull();
    }
  });

  it("says a target in words from the run's maps, and nothing for an element the run lacks", () => {
    expect(targetWords("object:set_1/halo", BATTERIES)).toBe("Fiktivní značky: Halo");
    expect(targetWords("object:set_2/halo", BATTERIES)).toBe("Varianty: Jemná");
    expect(targetWords("pair:set_1/halo~iris", BATTERIES)).toBe("Fiktivní značky: Halo – Iris");
    expect(targetWords("object:set_1/nobody", BATTERIES)).toBeNull();
    expect(targetWords("object:set_9/halo", BATTERIES)).toBeNull();
  });
});

describe("what the Lead may do on the map", () => {
  it("refuses a move_object request by name, pointing to Metodika", () => {
    const r = readMapOp({ op: "move_object", target: "object:set_1/halo", x: 1, y: 2 }, BATTERIES);
    expect(isRefusal(r) && r.refused).toBe("writes_the_map");
    expect(isRefusal(r) && r.words).toContain("„move_object“ není operace zobrazení mapy");
    expect(isRefusal(r) && r.words).toContain("Nastavení → Metodika");
  });

  it("refuses every write to the map, and any operation the row does not list", () => {
    for (const op of ["set_threshold", "recompute", "drag", "edit_height", "approve_map", "delete_pair"]) {
      expect(readMapOp({ op }, BATTERIES)).toMatchObject({ refused: "writes_the_map", op });
    }
    for (const op of ["show_diff", "say_hello", "", undefined]) {
      expect(readMapOp({ op }, BATTERIES)).toMatchObject({ refused: "not_a_map_op" });
    }
    expect(readMapOp(null, BATTERIES)).toMatchObject({ refused: "not_a_map_op" });
  });

  it("takes each display filter at its values, and refuses an unknown filter or value", () => {
    expect(readMapOp({ op: "filter", name: "view", value: "relief" }, BATTERIES)).toEqual({ op: "filter", name: "view", value: "relief" });
    expect(readMapOp({ op: "filter", name: "hide_weak", value: "on" }, BATTERIES)).toEqual({ op: "filter", name: "hide_weak", value: "on" });
    expect(readMapOp({ op: "filter", name: "mode", value: "respondents" }, BATTERIES)).toEqual({ op: "filter", name: "mode", value: "respondents" });
    expect(readMapOp({ op: "filter", name: "battery", value: "set_2" }, BATTERIES)).toEqual({ op: "filter", name: "battery", value: "set_2" });
    expect(readMapOp({ op: "filter", name: "battery", value: "set_9" }, BATTERIES)).toMatchObject({ refused: "unknown_value" });
    expect(readMapOp({ op: "filter", name: "view", value: "spin" }, BATTERIES)).toMatchObject({ refused: "unknown_value" });
    expect(readMapOp({ op: "filter", name: "n_min", value: "5" }, BATTERIES)).toMatchObject({ refused: "unknown_filter" });
  });

  it("selects, focuses and inspects only an element of this run's maps", () => {
    expect(readMapOp({ op: "select", target: "pair:set_1/iris~halo" }, BATTERIES)).toEqual({ op: "select", target: { kind: "pair", battery: "set_1", a: "halo", b: "iris" } });
    expect(readMapOp({ op: "inspect", target: "object:set_2/halo" }, BATTERIES)).toEqual({ op: "inspect", target: { kind: "object", battery: "set_2", object: "halo" } });
    expect(readMapOp({ op: "focus", target: "object:set_1/gale" }, BATTERIES)).toMatchObject({ op: "focus" });
    expect(readMapOp({ op: "select", target: "object:set_9/halo" }, BATTERIES)).toMatchObject({ refused: "unknown_target" });
    // The battery is the run's, the element is not (Codex, #601): an object it lacks, or a pair with one end or both.
    expect(readMapOp({ op: "select", target: "object:set_1/nobody" }, BATTERIES)).toMatchObject({ refused: "unknown_target" });
    expect(readMapOp({ op: "inspect", target: "pair:set_1/halo~nobody" }, BATTERIES)).toMatchObject({ refused: "unknown_target" });
    expect(readMapOp({ op: "focus", target: "pair:set_1/ghost~nobody" }, BATTERIES)).toMatchObject({ refused: "unknown_target" });
    expect(readMapOp({ op: "select", target: "object:set_2/iris" }, BATTERIES)).toMatchObject({ refused: "unknown_target" }); // iris is set_1's
    expect(readMapOp({ op: "select", target: "question:q1" }, BATTERIES)).toMatchObject({ refused: "unknown_target" });
    expect(readMapOp({ op: "open_stage" }, BATTERIES)).toEqual({ op: "open_stage" });
  });
});
