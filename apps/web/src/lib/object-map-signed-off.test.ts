// The signed-off map's reading, against stored aia-sociomap-5 artifacts
// (repo_port/fixture_generators/make_web_fixture.py: simulated ratings mapped by compute_object_map).
// Nothing here computes a methodological number.
import { describe, expect, it } from "vitest";

import fixture from "./fixtures/object-map-signed-off.json";
import legacy from "./fixtures/object-map.json";
import {
  isSignedOffMap,
  objectsNotPlaced,
  panelObjects,
  panelRespondents,
  respondentNote,
  segmentLegend,
  storedFrame,
  storedRespondents,
} from "./object-map-signed-off";
import type { BatteryWithMaps, ObjectMapArtifact } from "./object-map-view";

const [clear, noise] = fixture.batteries as unknown as BatteryWithMaps[];
const mapOf = (b: BatteryWithMaps): ObjectMapArtifact => b.maps!["aia-sociomap-5"].artifact;
const CLEAR = mapOf(clear);
const NOISE = mapOf(noise);
const LEGACY = (legacy.sociomap.batteries[0] as unknown as BatteryWithMaps).maps!["aia-sociomap-3"].artifact;

describe("which maps the panel renderer draws", () => {
  it("knows a signed-off map by its stored estimator, not by its name", () => {
    expect(isSignedOffMap(CLEAR)).toBe(true);
    expect(isSignedOffMap(LEGACY)).toBe(false);
    const edited = { ...CLEAR, spec: { ...CLEAR.spec, methodology_version: "aia-sociomap-5+e1" } };
    expect(isSignedOffMap(edited)).toBe(true);
  });
});

describe("the object map", () => {
  it("places the mapped objects at their stored ruler positions with their stored heights", () => {
    const objects = panelObjects(clear, CLEAR);
    expect(objects.map((o) => o.id)).toEqual(CLEAR.object_ids);
    objects.forEach((o, k) => {
      expect([o.x, o.y]).toEqual(CLEAR.layout!.points[k]);
      expect(o.height).toBe(CLEAR.heights.values[k]);
      expect(o.relative).toBe(CLEAR.heights.relative![k]);
    });
    expect(objects[0].label).toBe("Pop");
    expect(Math.min(...objects.map((o) => o.relative!))).toBe(0.15);
    expect(Math.max(...objects.map((o) => o.relative!))).toBeCloseTo(1, 12);
  });

  it("lists an object nobody rated beside the map instead of drawing it", () => {
    expect(CLEAR.object_ids).not.toContain("hudba-o12");
    expect(objectsNotPlaced(clear, CLEAR)).toEqual(["Reggae"]);
    expect(objectsNotPlaced(noise, NOISE)).toEqual([]);
  });

  it("frames the map on the stored grid's own square", () => {
    const frame = storedFrame(CLEAR)!;
    const p = (CLEAR.terrain as Extract<ObjectMapArtifact["terrain"], { status: "computed" }>).parameters;
    expect(frame).toEqual({ cx: p.centre![0], cy: p.centre![1], half: p.half_extent });
    expect(storedFrame({ ...CLEAR, terrain: { status: "not_computed", reason: "x" } })).toBeNull();
  });
});

describe("the respondent map", () => {
  it("draws every placed and faded respondent at their stored position, never one not placed", () => {
    const r = storedRespondents(CLEAR)!;
    const drawn = panelRespondents(CLEAR);
    expect(drawn).toHaveLength(r.counts.PLACED + r.counts.FADED);
    expect(r.counts.NOT_PLACED).toBe(6);
    const k = CLEAR.respondent_ids!.indexOf(drawn[0].id);
    expect([drawn[0].x, drawn[0].y]).toEqual([r.x[k], r.y[k]]);
    expect(drawn.every((p) => p.placement !== ("NOT_PLACED" as string))).toBe(true);
  });

  it("colours a respondent only by a shown segment, and only a clearly placed one", () => {
    const drawn = panelRespondents(CLEAR);
    expect(new Set(drawn.filter((p) => p.coloured).map((p) => p.segment))).toEqual(new Set([0, 1, 2]));
    expect(drawn.filter((p) => p.coloured).every((p) => p.placement === "PLACED")).toBe(true);
    expect(drawn.every((p) => p.segmented)).toBe(true);
    expect(panelRespondents(NOISE).every((p) => !p.segmented && p.segment === -1 && !p.coloured)).toBe(true);
  });

  it("keeps a respondent without a segment apart from a set without segments: grey, not white", () => {
    const r = storedRespondents(CLEAR)!;
    const label = [...r.segments!.label!];
    const k = label.findIndex((g, i) => g >= 0 && r.placement[i] !== "NOT_PLACED");
    label[k] = -1;
    const coloured = [...r.segments!.coloured!];
    coloured[k] = false;
    const fewer = { ...CLEAR, respondents: { ...r, segments: { ...r.segments!, label, coloured } } };
    const p = panelRespondents(fewer).find((q) => q.id === CLEAR.respondent_ids![k])!;
    expect(p).toMatchObject({ segmented: true, segment: -1, coloured: false });
  });

  it("names each segment's liked objects by the battery's labels", () => {
    const legend = segmentLegend(clear, CLEAR)!;
    expect(legend.decision).toBe("SEGMENTS");
    expect(legend.segments).toHaveLength(3);
    expect(legend.segments.reduce((s, g) => s + g.share, 0)).toBeCloseTo(1, 12);
    expect(legend.segments.flatMap((g) => g.likes).every((l) => !l.startsWith("hudba-"))).toBe(true);
    expect(segmentLegend(noise, NOISE)).toMatchObject({ decision: "NONE", reason: "NO_CLEAR_SEGMENTS", segments: [] });
  });

  it("names a borderline set's likely split from its hint, with nobody coloured", () => {
    const r = storedRespondents(CLEAR)!;
    const s = r.segments!;
    const hint = { k: 2, shares: [0.6, 0.4], profiles: s.profiles.slice(0, 2) };
    const borderline = { ...s, decision: "BORDERLINE" as const, k: 0, shares: [], profiles: [], label: null, membership: null, coloured: null, hint };
    const map = { ...CLEAR, respondents: { ...r, segments: borderline } };
    const legend = segmentLegend(clear, map)!;
    expect(legend.decision).toBe("BORDERLINE");
    expect(legend.segments.map((g) => g.share)).toEqual([0.6, 0.4]);
    expect(legend.segments[0].likes.length).toBeGreaterThan(0);
    expect(panelRespondents(map).every((p) => !p.segmented && !p.coloured)).toBe(true);
  });

  it("says nothing under an informative map, and the panel's note under a small one", () => {
    expect(respondentNote(CLEAR)).toBeNull();
    const r = storedRespondents(CLEAR)!;
    const small = { ...CLEAR, object_ids: CLEAR.object_ids.slice(0, 4), respondents: { ...r, informative: false } };
    expect(respondentNote(small)).toEqual({ objects: 4, minObjects: 6, minRatings: 3, placeable: true });
    const three = { ...small, object_ids: CLEAR.object_ids.slice(0, 3) };
    expect(respondentNote(three)).toMatchObject({ objects: 3, placeable: true });
    const two = { ...small, object_ids: CLEAR.object_ids.slice(0, 2) };
    expect(respondentNote(two)).toMatchObject({ objects: 2, placeable: false });
    // An edited version may ask more ratings than the set has objects: the note shows though informative.
    const strict = { ...CLEAR, spec: { ...CLEAR.spec, respondent_map: { ...CLEAR.spec.respondent_map!, min_ratings: 13 } } };
    expect(respondentNote(strict)).toMatchObject({ objects: 12, placeable: false });
  });

  it("reads no respondent map from a map that has none", () => {
    expect(storedRespondents(LEGACY)).toBeNull();
    expect(panelRespondents(LEGACY)).toEqual([]);
    expect(segmentLegend(clear, LEGACY)).toBeNull();
  });
});
