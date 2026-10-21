// The signed-off map's reading, against stored aia-sociomap-5 artifacts
// (repo_port/fixture_generators/make_web_fixture.py: simulated ratings mapped by compute_object_map).
// Nothing here computes a methodological number.
import { describe, expect, it } from "vitest";

import fixture from "./fixtures/object-map-signed-off.json";
import legacy from "./fixtures/object-map.json";
import {
  isSignedOffMap,
  objectDetail,
  objectsNotPlaced,
  panelObjects,
  panelRespondents,
  relationDetail,
  respondentDetail,
  respondentNote,
  segmentLegend,
  storedFrame,
  storedRespondents,
} from "./object-map-signed-off";
import { type BatteryWithMaps, type ObjectMapArtifact, readObjectMap } from "./object-map-view";

const [clear, noise] = fixture.batteries as unknown as BatteryWithMaps[];
const mapOf = (b: BatteryWithMaps): ObjectMapArtifact => b.maps!["aia-sociomap-5"].artifact;
const CLEAR = mapOf(clear);
const NOISE = mapOf(noise);
const legacyBattery = legacy.sociomap.batteries[0] as unknown as BatteryWithMaps;
const LEGACY = legacyBattery.maps!["aia-sociomap-3"].artifact;

describe("which maps the panel renderer draws", () => {
  it("knows a signed-off map by its stored estimator, not by its name", () => {
    expect(isSignedOffMap(CLEAR)).toBe(true);
    expect(isSignedOffMap(LEGACY)).toBe(false);
    const edited = { ...CLEAR, spec: { ...CLEAR.spec, methodology_version: "aia-sociomap-5+e1" } };
    expect(isSignedOffMap(edited)).toBe(true);
  });

  it("reads a signed-off map before the earlier methods, under whatever name it is stored", () => {
    const legacy = legacyBattery.maps!["aia-sociomap-3"];
    const stored = clear.maps!["aia-sociomap-5"];
    const both = { ...clear, maps: { "aia-sociomap-3": legacy, "aia-sociomap-5+e2": stored } };
    const read = readObjectMap(both);
    expect(read.ok && read.methodId).toBe("aia-sociomap-5+e2");
    expect(read.ok && read.map).toBe(stored.artifact);
    // Without one, the known methods are read as before.
    const only = readObjectMap({ ...clear, maps: { "aia-sociomap-3": legacy } });
    expect(only.ok && only.methodId).toBe("aia-sociomap-3");
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

describe("what a click shows", () => {
  const labelOf = (id: string) => clear.objects.find((o) => o.id === id)!.label;

  it("reads an object's stored numbers and its 5 strongest reliable relations, by |r| with sign", () => {
    for (let k = 0; k < CLEAR.object_ids.length; k++) {
      const o = objectDetail(clear, CLEAR, k);
      const score = CLEAR.scores!.objects.find((s) => s.id === CLEAR.object_ids[k])!;
      expect(o).toMatchObject({ id: CLEAR.object_ids[k], label: labelOf(CLEAR.object_ids[k]), primary: true, height: CLEAR.heights.values[k], basis: null });
      expect(o.connectedness).toBeCloseTo(100 * score.connectedness!, 12);
      const reliable = CLEAR.object_ids.flatMap((id, j) => (j !== k && CLEAR.relations.status[k][j] === "reliable" ? [{ id, r: CLEAR.relations.r[k][j]! }] : []));
      reliable.sort((x, y) => Math.abs(y.r) - Math.abs(x.r));
      expect(o.relations.map((x) => [x.id, x.r])).toEqual(reliable.slice(0, 5).map((x) => [x.id, x.r]));
    }
    // A weak pair is never listed, however strong: object 0's strongest pair marked weak drops out.
    const strongest = objectDetail(clear, CLEAR, 0).relations[0].id, j = CLEAR.object_ids.indexOf(strongest);
    const status = CLEAR.relations.status.map((row, a) => row.map((x, b) => ((a === 0 && b === j) || (a === j && b === 0) ? "weak" : x)));
    expect(objectDetail(clear, { ...CLEAR, relations: { ...CLEAR.relations, status } }, 0).relations.map((x) => x.id)).not.toContain(strongest);
  });

  it("leaves the alignment out when it says nothing, and shows it with a secondary object", () => {
    // Each respondent's mean removed and every object PRIMARY: the alignment is ~0 by construction.
    expect(CLEAR.spec.ratings?.person_normalization).toBe("person_mean_centring");
    expect(objectDetail(clear, CLEAR, 0).alignment).toBeNull();
    const id = CLEAR.object_ids[3];
    const secondary = { ...CLEAR, roles: { ...CLEAR.roles, [id]: "secondary" } };
    const o = objectDetail(clear, secondary, 3);
    expect(o.primary).toBe(false);
    expect(o.alignment).toBe(CLEAR.scores!.objects[3].alignment);
    // The secondary's basis: its strongest reliable |r| to a PRIMARY object.
    const toPrimary = CLEAR.object_ids.flatMap((_, j) => (j !== 3 && CLEAR.relations.status[3][j] === "reliable" ? [Math.abs(CLEAR.relations.r[3][j]!)] : []));
    expect(o.basis).toBe(Math.max(...toPrimary));
    expect(objectDetail(clear, { ...CLEAR, spec: { ...CLEAR.spec, ratings: {} } }, 0).alignment).toBe(CLEAR.scores!.objects[0].alignment);
    // Only PRIMARY partners count: with its strongest partner secondary too, the basis is the next one.
    const top = objectDetail(clear, CLEAR, 3).relations[0].id;
    const two = { ...CLEAR, roles: { ...CLEAR.roles, [id]: "secondary", [top]: "secondary" } };
    const primaries = CLEAR.object_ids.flatMap((other, j) => (j !== 3 && other !== top && CLEAR.relations.status[3][j] === "reliable" ? [Math.abs(CLEAR.relations.r[3][j]!)] : []));
    expect(objectDetail(clear, two, 3).basis).toBe(Math.max(...primaries));
    expect(objectDetail(clear, two, 3).basis).toBeLessThan(Math.abs(objectDetail(clear, CLEAR, 3).relations[0].r));
  });

  it("reads a relation's stored r, interval and N, and its verdict from the stored status", () => {
    const [i, j] = [0, 2];
    expect(CLEAR.relations.status[i][j]).toBe("reliable");
    expect(relationDetail(clear, CLEAR, i, j)).toEqual({
      a: labelOf(CLEAR.object_ids[i]), b: labelOf(CLEAR.object_ids[j]), r: CLEAR.relations.r[i][j], interval: CLEAR.relations.interval![i][j],
      n: CLEAR.relations.n[i][j], respondents: 300, verdict: "reliable", noiseRule: true, clearFrom: 0.3,
    });
    // An edited version declares its own threshold for "zřetelný".
    const edited = { ...CLEAR, spec: { ...CLEAR.spec, relation: { ...CLEAR.spec.relation, clear_effect: 0.45 } } };
    expect(relationDetail(clear, edited, i, j).clearFrom).toBe(0.45);
    expect(relationDetail(clear, CLEAR, 0, 1).verdict).toBe("weak");
    const off = { ...CLEAR, spec: { ...CLEAR.spec, relation: { ...CLEAR.spec.relation, noise_rule: { enabled: false } } } };
    expect(relationDetail(clear, off, i, j).noiseRule).toBe(false);
  });

  it("says why a relation is unknown: too few rated both, or one object was rated alike by all", () => {
    const unknown = (n: number) => {
      const cell = <T,>(m: T[][], v: T) => m.map((row, a) => row.map((x, b) => (a === 0 && b === 2 ? v : x)));
      const rel = CLEAR.relations;
      return { ...CLEAR, relations: { ...rel, r: cell(rel.r, null), status: cell(rel.status, null), n: cell(rel.n, n) } };
    };
    expect(relationDetail(clear, unknown(CLEAR.relations.n_min - 1), 0, 2)).toMatchObject({ r: null, verdict: "fewRatings" });
    expect(relationDetail(clear, unknown(CLEAR.relations.n_min), 0, 2)).toMatchObject({ r: null, verdict: "noSpread" });
  });

  it("reads a respondent's fit and segment: coloured in one, grey, or faded", () => {
    expect(respondentDetail(CLEAR, "r0006")).toEqual({ id: "r0006", faded: false, explained: Math.round(100 * (1 - 0.25558)), segment: 0 });
    // Clearly placed but not certain of one segment: grey, "not clearly in one".
    expect(respondentDetail(CLEAR, "r0016")).toMatchObject({ faded: false, segment: -1 });
    // A weakly placed respondent is never coloured, whatever its likeliest segment.
    expect(respondentDetail(CLEAR, "r0008")).toMatchObject({ faded: true, explained: 6, segment: -1 });
    expect(respondentDetail(CLEAR, "nobody")).toBeNull();
    // A set that shows no segments says nothing about them.
    expect(respondentDetail(NOISE, NOISE.respondent_ids![10])!.segment).toBeNull();
  });

  it("rounds the share explained as the panel's payload rounds the misfit: 4 decimals first", () => {
    const r = storedRespondents(CLEAR)!;
    const misfit = r.misfit.map((m, k) => (k === 6 ? 0.03505 : m));
    expect(respondentDetail({ ...CLEAR, respondents: { ...r, misfit } }, "r0006")!.explained).toBe(97);
  });
});
