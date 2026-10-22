// What the Sociomapa stage says under a map (artifact-sociomap SOC10), read from the stored fixture:
// every number is the map's own, ranked as stored, and what the map does not store stays null.
import { describe, expect, it } from "vitest";

import signedOff from "./fixtures/object-map-signed-off.json";
import { SHOWN_RELATIONS, explainMap, plural } from "./map-explained";
import { type BatteryWithMaps, mapLinks, originalRating } from "./object-map-view";

const [hudba, sum] = signedOff.batteries as unknown as BatteryWithMaps[];
const map = hudba.maps!["aia-sociomap-5"].artifact;
const weak = sum.maps!["aia-sociomap-5"].artifact;

describe("explainMap", () => {
  it("counts what the map stores: objects, the object nobody rated, respondents, pairs", () => {
    const x = explainMap(hudba, map);
    expect(x.objects).toHaveLength(map.object_ids.length);
    expect(x.unplaced).toEqual(["Reggae"]);
    expect(x.respondents).toBe(300);
    expect(x.pairs).toEqual({ reliable: 62, weak: 4, unknown: 0, total: 66 });
    expect(x.scale).toEqual([1, 10]);
    expect(x.nMin).toBe(map.spec.relation.n_min);
  });

  it("ranks the objects by their stored mean on the declared scale, highest first", () => {
    const x = explainMap(hudba, map);
    const ratings = x.objects.map((o) => o.rating!);
    expect(ratings).toEqual([...ratings].sort((a, b) => b - a));
    const k = map.object_ids.indexOf(x.objects[0].id);
    expect(x.objects[0].rating).toBe(originalRating(map.heights.values[k], [1, 10]));
    for (const o of x.objects) expect(o.connectedness).toBe(100 * map.scores!.objects.find((s) => s.id === o.id)!.connectedness!);
  });

  it("lists the strongest reliable relations by |r|, at most six, and counts the rest", () => {
    const x = explainMap(hudba, map);
    const reliable = mapLinks(map).sort((a, b) => Math.abs(b.r) - Math.abs(a.r));
    expect(x.relations).toHaveLength(SHOWN_RELATIONS);
    expect(x.relations.map((r) => r.r)).toEqual(reliable.slice(0, SHOWN_RELATIONS).map((l) => l.r));
    expect(x.moreRelations).toBe(reliable.length - SHOWN_RELATIONS);
    // "zřetelný" from the declared |r| (0,3 on a map stored before it).
    for (const r of x.relations) expect(r.clear).toBe(Math.abs(r.r) >= 0.3);
  });

  it("reads the map's reliability as stored: the halves' agreement, its threshold, the place's uncertainty", () => {
    const x = explainMap(hudba, map);
    expect(x.quality).toEqual({ value: map.credibility!.split_half, threshold: 0.59 });
    expect(x.uncertainty).toBe(map.credibility!.uncertainty_radius);
    expect(x.weaklyDetermined).toBe(false);
    expect(explainMap(sum, weak).weaklyDetermined).toBe(true);
  });

  it("reads the respondents' placement and the taste segments as stored", () => {
    const x = explainMap(hudba, map);
    expect(x.placement).toEqual({ placed: 219, faded: 75, notPlaced: 6 });
    expect(x.segments!.decision).toBe("SEGMENTS");
    expect(x.segments!.segments).toHaveLength(3);
    expect(x.colourMembership).toBe(map.spec.segments?.colour_membership ?? 0.8);
  });

  it("leaves what the map does not store null, never a neutral default", () => {
    const bare = structuredClone(map);
    delete bare.credibility;
    delete (bare as { respondents?: unknown }).respondents;
    const x = explainMap(hudba, bare);
    expect(x.quality).toBeNull();
    expect(x.uncertainty).toBeNull();
    expect(x.placement).toBeNull();
    expect(x.segments).toBeNull();
  });
});

describe("plural", () => {
  it("says the Czech word for 1, 2-4 and the rest", () => {
    expect([1, 2, 4, 5, 0, 11].map((n) => plural(n, "a", "b", "c"))).toEqual(["a", "b", "b", "c", "c", "c"]);
  });
});
