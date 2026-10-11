// The object map's view logic, against the fixture the real builder wrote
// (tools/object_map_web_fixture.py). Nothing here computes a methodological number.
import { describe, expect, it } from "vitest";

import fixture from "./fixtures/object-map.json";
import {
  type BatteryWithMaps,
  type ObjectMapArtifact,
  MAP_VIEW,
  TERRACE_BANDS,
  belowFloor,
  labelWidth,
  mapLinks,
  mapObjects,
  originalRating,
  pairDetail,
  placeLabels,
  rankedByHeight,
  frameToScreen,
  readObjectMap,
  relationsOf,
  resolveVars,
  terraceBand,
  terraceEdges,
  terraceLevel,
  terrainAt,
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

  it("reads the map a run pinned under an edited methodology's own name", () => {
    const stored = battery.maps!["aia-sociomap-3"];
    const edited = { "aia-sociomap-3+e2": { ...stored, artifact: { ...map, spec: { ...map.spec, methodology_version: "aia-sociomap-3+e2" } } } };
    expect(readObjectMap({ ...battery, maps: edited })).toMatchObject({ ok: true, methodId: "aia-sociomap-3+e2" });
    const otherContract = { "aia-sociomap-3+e2": { ...stored, artifact: { ...map, contract_version: "2" } } };
    expect(readObjectMap({ ...battery, maps: otherContract as never })).toEqual({ ok: false, reason: "contract" });
  });
});

describe("the objects", () => {
  it("places every object where the layout stored it, labelled, with its stored height", () => {
    const objects = mapObjects(battery, map);
    expect(objects.map((o) => o.label)).toEqual(["Altair", "Borealis", "Cirrus", "Deneb", "Elara", "Fomalhaut"]);
    objects.forEach((o, k) => {
      expect([o.x, o.y]).toEqual(map.layout!.points[k]);
      expect(o.height).toBe(map.heights.values[k]);
      expect(o.band).toBe(terraceBand(o.height!));
    });
  });

  it("draws nothing for an unmappable family", () => {
    expect(mapObjects(battery, edited((m) => (m.layout = null)))).toEqual([]);
  });

  it("quantizes a stored 0-1 height into ten display terraces on the absolute scale", () => {
    expect(TERRACE_BANDS).toBe(10);
    expect([0, 0.0999, 0.1, 0.35, 0.5, 0.7, 0.8999, 0.9, 1].map(terraceBand)).toEqual([0, 0, 1, 3, 5, 7, 8, 9, 9]);
    // Every k/10 lands on its own band despite floating point (0.7 * 10 = 7.000000000000001).
    for (let k = 0; k < 10; k++) expect(terraceBand(k / 10)).toBe(k);
    // Never on the ground: the lowest terrace is a thin sheet above it; a tenth per band above.
    expect(terraceLevel(0)).toBe(0.03);
    expect(terraceLevel(1)).toBeCloseTo(0.93);
    expect(terraceLevel(0.55)).toBeGreaterThan(terraceLevel(0.45));
  });

  it("does not rescale the bands to one map's range", () => {
    // A map whose heights all sit in [0.40, 0.49] is one band, not ten.
    const flat = edited((m) => { m.heights.values = m.heights.values.map((_, k) => 0.4 + k * 0.015); });
    expect(new Set(mapObjects(battery, flat).map((o) => o.band))).toEqual(new Set([4]));
  });

  it("keeps the stored height: the band is derived, never written back", () => {
    const before = JSON.stringify(map);
    const objects = mapObjects(battery, map);
    objects.forEach((o, k) => expect(o.height).toBe(map.heights.values[k]));
    expect(JSON.stringify(map)).toBe(before);
    expect(originalRating(0.5, [1, 10])).toBe(5.5);
    expect(originalRating(null, [1, 10])).toBeNull();
    expect(originalRating(0.5)).toBeNull();
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

describe("the terrace steps of the top view", () => {
  it("draws a step only between two stored neighbours in different bands", () => {
    const t = map.terrain;
    if (t.status !== "computed") throw new Error("fixture has a terrain");
    const edges = terraceEdges(map);
    expect(edges.length).toBeGreaterThan(0);
    const step = (2 * t.parameters.half_extent) / t.parameters.grid_resolution;
    for (const e of edges) expect(Math.hypot(e.x2 - e.x1, e.y2 - e.y1)).toBeCloseTo(step);
    const one = edited((m) => {
      m.terrain = { status: "computed", method: "object_envelope", source_ids: ["a"], parameters: { grid_resolution: 2, half_extent: 1, sigma: 0.25, kernel_cutoff: 0.001 },
        height: [[0.15, 0.19, null], [0.15, 0.25, 0.25], [null, null, null]], governing: [[0, 0, null], [0, 0, 0], [null, null, null]] };
    });
    // Same band (0.15|0.19, 0.15 over 0.15, 0.25|0.25) or a null neighbour: nothing. Bands
    // differ at 0.15|0.25 (side by side) and 0.19 under 0.25: two steps.
    expect(terraceEdges(one)).toHaveLength(2);
    expect(terraceEdges(edited((m) => (m.terrain = { status: "not_computed", reason: "x" })))).toEqual([]);
  });

  it("reads a pin's ground from the stored grid, null where it has none", () => {
    const t = map.terrain;
    if (t.status !== "computed") throw new Error("fixture has a terrain");
    expect(terrainAt(map, -t.parameters.half_extent, -t.parameters.half_extent)).toBe(t.height[0][0]);
    expect(terrainAt(map, 0, 0)).toBe(t.height[t.parameters.grid_resolution / 2][t.parameters.grid_resolution / 2]);
    expect(terrainAt(edited((m) => (m.terrain = { status: "not_computed", reason: "x" })), 0, 0)).toBeNull();
  });
});

describe("the ranked list", () => {
  it("orders by stored height, highest first, an object without a height last", () => {
    const objects = mapObjects(battery, map);
    expect(rankedByHeight(objects).map((o) => o.height)).toEqual([...map.heights.values].sort((a, b) => b! - a!));
    const holed = mapObjects(battery, edited((m) => (m.heights.values[0] = null)));
    expect(rankedByHeight(holed).at(-1)?.id).toBe("altair");
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

describe("the pair card's evidence", () => {
  it("reads every field from the artifact and draws exactly what mapLinks draws", () => {
    const drawn = new Set(mapLinks(map).map((l) => [l.a, l.b].sort().join("|")));
    for (const a of map.object_ids) for (const b of map.object_ids) {
      if (a === b) continue;
      const d = pairDetail(battery, map, a, b)!;
      const i = map.object_ids.indexOf(a), j = map.object_ids.indexOf(b);
      expect(d.r).toBe(map.relations.r[i][j]);
      expect(d.n).toBe(map.relations.n[i][j]);
      expect(d.nEffective).toBe(map.relations.n_effective![i][j]);
      expect(d.interval).toEqual(map.relations.interval![i][j]);
      expect(d.meetsFloor).toBe(map.relations.meets_effect_floor![i][j]);
      expect(d.drawn).toBe(drawn.has([a, b].sort().join("|")));
      expect(d.why === "drawn").toBe(d.drawn);
    }
    expect(pairDetail(battery, map, "altair", "altair")).toBeNull();
    expect(pairDetail(battery, map, "altair", "nobody")).toBeNull();
  });

  it("tells UNKNOWN with an r apart from an r that was never computed", () => {
    const m = edited((x) => {
      x.relations.status[0][1] = x.relations.status[1][0] = "unknown";
      x.relations.r[0][2] = x.relations.r[2][0] = null;
      x.relations.status[0][2] = x.relations.status[2][0] = "unknown";
    });
    const estimate = pairDetail(battery, m, "altair", "borealis")!;
    expect(estimate.r).toBe(map.relations.r[0][1]);
    expect(estimate.state).toBe("unknown");
    expect(estimate.why).toBe("unknown");
    const none = pairDetail(battery, m, "altair", "cirrus")!;
    expect(none.r).toBeNull();
    expect(none.state).toBe("unknown");
    expect(none.why).toBe("undefined");
    expect(estimate.drawn || none.drawn).toBe(false);
  });

  it("explains every other undrawn pair from its stored fields", () => {
    expect(pairDetail(battery, map, "deneb", "fomalhaut")!.why).toBe("weak");
    const floor = edited((x) => { x.relations.meets_effect_floor![0][1] = x.relations.meets_effect_floor![1][0] = false; });
    expect(pairDetail(battery, floor, "altair", "borealis")!.why).toBe("below_floor");
    const context = edited((x) => (x.roles.altair = "secondary"));
    expect(pairDetail(battery, context, "altair", "borealis")!.why).toBe("context");
  });
});

describe("label placement on screen", () => {
  const view = { width: 400, height: 300 };

  it("moves labels apart and never moves an anchor", () => {
    const items = ["a", "b", "c", "d"].map((id, k) => ({ id, ax: 200 + k, ay: 150 + k, w: 80, h: 20 }));
    const anchors = JSON.stringify(items);
    const placed = placeLabels(items, [], view);
    expect(JSON.stringify(items)).toBe(anchors);
    const rects = [...placed.values()];
    for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) {
      const a = rects[i], b = rects[j];
      expect(a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y).toBe(false);
    }
    for (const r of rects) {
      expect(r.x).toBeGreaterThanOrEqual(0);
      expect(r.y).toBeGreaterThanOrEqual(0);
      expect(r.x + r.w).toBeLessThanOrEqual(view.width);
      expect(r.y + r.h).toBeLessThanOrEqual(view.height);
    }
  });

  it("keeps clear of a panel and of other pins, and puts a free label right above its anchor", () => {
    const free = placeLabels([{ id: "a", ax: 200, ay: 150, w: 60, h: 20 }], [], view).get("a")!;
    expect(free).toEqual({ x: 170, y: 117, w: 60, h: 20 }); // clear of the pin's 9 px, 4 px gap
    const panel = { x: 150, y: 100, w: 120, h: 50 };
    const moved = placeLabels([{ id: "a", ax: 200, ay: 150, w: 60, h: 20 }], [panel], view).get("a")!;
    expect(moved.x < panel.x + panel.w && moved.x + moved.w > panel.x && moved.y < panel.y + panel.h && moved.y + moved.h > panel.y).toBe(false);
    const pins = placeLabels([{ id: "a", ax: 200, ay: 150, w: 60, h: 20 }, { id: "b", ax: 200, ay: 130, w: 60, h: 20 }], [], view);
    const a = pins.get("a")!;
    expect(a.x < 209 && a.x + a.w > 191 && a.y < 139 && a.y + a.h > 121).toBe(false);
  });

  it("never covers its own pin, even in a crowd", () => {
    const items = Array.from({ length: 12 }, (_, k) => ({ id: `o${k}`, ax: 180 + (k % 4) * 14, ay: 120 + Math.floor(k / 4) * 14, w: 70, h: 20 }));
    const placed = placeLabels(items, [], view);
    for (const it of items) {
      const r = placed.get(it.id)!;
      expect(r.x < it.ax + 9 && r.x + r.w > it.ax - 9 && r.y < it.ay + 9 && r.y + r.h > it.ay - 9).toBe(false);
    }
  });

  it("is deterministic and sizes a label from its longest line", () => {
    const items = [{ id: "a", ax: 10, ay: 10, w: 50, h: 20 }, { id: "b", ax: 12, ay: 12, w: 50, h: 20 }];
    expect(placeLabels(items, [], view)).toEqual(placeLabels(items, [], view));
    expect(labelWidth(["ab", "abcd"], 10, 5)).toBe(Math.ceil(4 * 10 * 0.56) + 10);
  });
});

describe("the top view's frame and the snapshot's colours", () => {
  it("maps a framed square centred in the view, one scale on both axes, y up", () => {
    const frame = { cx: 1, cy: -1, half: 2 };
    const view = { width: 900, height: 600 };
    expect(frameToScreen(1, -1, frame, view)).toEqual({ sx: 450, sy: 300 });
    const right = frameToScreen(3, -1, frame, view), up = frameToScreen(1, 1, frame, view);
    expect(right.sx - 450).toBeCloseTo(300 - up.sy);
    expect(right.sx - 450).toBeCloseTo(600 * 0.72 / 2);
  });

  it("resolves token colours in a snapshot's markup and touches nothing else", () => {
    const markup = '<rect fill="var(--viz-terrace-3)" stroke="white" data-n="0,52"/><text fill="var(--missing)">0,52</text>';
    const tokens: Record<string, string> = { "--viz-terrace-3": "#2aa3d8" };
    expect(resolveVars(markup, (t) => tokens[t] ?? "")).toBe('<rect fill="#2aa3d8" stroke="white" data-n="0,52"/><text fill="var(--missing)">0,52</text>');
  });
});
