// The object map's view logic, against the fixture the real builder wrote
// (tools/object_map_web_fixture.py). Nothing here computes a methodological number.
import { describe, expect, it } from "vitest";

import fixture from "./fixtures/object-map.json";
import {
  type BatteryWithMaps,
  type ObjectMapArtifact,
  MAP_VIEW,
  band,
  belowFloor,
  mapLinks,
  mapObjects,
  readObjectMap,
  relationsOf,
  terrainCells,
  toScreen,
  viewSpan,
} from "./object-map-view";

const battery = fixture.sociomap.batteries[0] as unknown as BatteryWithMaps;
const read = readObjectMap(battery);
if (!read.ok) throw new Error("fixture unreadable");
const map = read.map;

function edited(change: (m: ObjectMapArtifact) => void): ObjectMapArtifact {
  const copy = structuredClone(map);
  change(copy);
  return copy;
}

describe("reading the stored map", () => {
  it("takes the newest pinned object map and refuses another contract", () => {
    expect(read.methodId).toBe("aia-sociomap-3");
    expect(readObjectMap({ ...battery, maps: {} })).toEqual({ ok: false, reason: "none" });
    expect(readObjectMap({ ...battery, maps: undefined })).toEqual({ ok: false, reason: "none" });
    const older = { "aia-sociomap-2": battery.maps!["aia-sociomap-3"] };
    expect(readObjectMap({ ...battery, maps: older })).toMatchObject({ ok: true, methodId: "aia-sociomap-2" });
    const wrong = { "aia-sociomap-3": { ...battery.maps!["aia-sociomap-3"], artifact: { ...map, contract_version: "2" } } };
    expect(readObjectMap({ ...battery, maps: wrong as never })).toEqual({ ok: false, reason: "contract" });
  });
});

describe("the objects", () => {
  it("places every object where the layout stored it, labelled, with its stored height", () => {
    const objects = mapObjects(battery, map);
    expect(objects.map((o) => o.label)).toEqual(["Altair", "Borealis", "Cirrus", "Deneb", "Elara", "Fomalhaut"]);
    objects.forEach((o, k) => {
      expect([o.x, o.y]).toEqual(map.layout!.points[k]);
      expect(o.height).toBe(map.heights.values[k]);
      expect(o.band).toBe(band(o.height!));
    });
  });

  it("draws nothing for an unmappable family", () => {
    expect(mapObjects(battery, edited((m) => (m.layout = null)))).toEqual([]);
  });

  it("bands a 0-1 share into the seven palette steps", () => {
    expect([band(0), band(0.14), band(0.15), band(0.5), band(0.99), band(1)]).toEqual([0, 0, 1, 3, 6, 6]);
  });
});

describe("the links: both gates", () => {
  it("draws reliable PRIMARY pairs that meet the floor, nothing weak or unknown", () => {
    const links = mapLinks(map);
    const ids = map.object_ids;
    for (const l of links) {
      const i = ids.indexOf(l.a);
      const j = ids.indexOf(l.b);
      expect(map.relations.status[i][j]).toBe("reliable");
      expect(map.relations.meets_effect_floor![i][j]).toBe(true);
      expect(l.strength).toBe(Math.abs(l.r));
      expect(l.sign).toBe(l.r < 0 ? "negative" : "positive");
    }
    expect(links.length).toBe(map.status_counts.reliable);
  });

  it("keeps a reliable pair below the floor off the map, and counts it", () => {
    const m = edited((x) => {
      x.relations.meets_effect_floor![0][1] = false;
      x.relations.meets_effect_floor![1][0] = false;
    });
    expect(mapLinks(m).some((l) => l.a === "altair" && l.b === "borealis")).toBe(false);
    expect(belowFloor(m)).toBe(1);
    expect(belowFloor(map)).toBe(0);
  });

  it("without a declared floor (aia-sociomap-2) reads the evidence state alone", () => {
    const m = edited((x) => delete x.relations.meets_effect_floor);
    expect(mapLinks(m).length).toBe(map.status_counts.reliable);
    expect(belowFloor(m)).toBe(0);
  });

  it("never links a SECONDARY object", () => {
    const m = edited((x) => (x.roles.altair = "secondary"));
    expect(mapLinks(m).some((l) => l.a === "altair" || l.b === "altair")).toBe(false);
  });
});

describe("the terrain", () => {
  it("draws only the cells the envelope reached, at their grid coordinates", () => {
    const cells = terrainCells(map);
    const t = map.terrain;
    if (t.status !== "computed") throw new Error("fixture has a terrain");
    const filled = t.height.flat().filter((h) => h !== null).length;
    expect(cells.length).toBe(filled);
    expect(cells.length).toBeLessThan((t.parameters.grid_resolution + 1) ** 2);
    expect(cells[0].size).toBeCloseTo((2 * t.parameters.half_extent) / t.parameters.grid_resolution);
    expect(new Set(cells.map((c) => c.owner))).toEqual(new Set(t.source_ids));
  });

  it("has no cells when the method computed no terrain", () => {
    expect(terrainCells(edited((m) => (m.terrain = { status: "not_computed", reason: "x" })))).toEqual([]);
  });

  it("maps the ruler onto the square view, y up", () => {
    const span = viewSpan(map);
    expect(span).toBe(2.75);
    expect(toScreen(-span, span, span)).toEqual({ sx: MAP_VIEW.pad, sy: MAP_VIEW.pad });
    const far = toScreen(span, -span, span);
    expect(far.sx).toBeCloseTo(MAP_VIEW.size - MAP_VIEW.pad);
    expect(far.sy).toBeCloseTo(MAP_VIEW.size - MAP_VIEW.pad);
  });
});

describe("one object's relations", () => {
  it("lists the others strongest first, each with its state and whether it is drawn", () => {
    const rows = relationsOf(battery, map, "deneb");
    expect(rows).toHaveLength(5);
    expect(rows.map((r) => Math.abs(r.r ?? 0))).toEqual([...rows.map((r) => Math.abs(r.r ?? 0))].sort((a, b) => b - a));
    const weak = rows.find((r) => r.id === "fomalhaut")!;
    expect(weak.state).toBe("weak");
    expect(weak.drawn).toBe(false);
    expect(relationsOf(battery, map, "nobody")).toEqual([]);
  });
});


describe("undefined pair ordering", () => {
  it("keeps unknown pairs after defined ones, rather than making them strongest", () => {
    const copy = edited((m) => { m.relations.r[0][1] = null; m.relations.status[0][1] = "unknown"; });
    expect(relationsOf(battery, copy, copy.object_ids[0]).at(-1)?.id).toBe(copy.object_ids[1]);
  });
});
