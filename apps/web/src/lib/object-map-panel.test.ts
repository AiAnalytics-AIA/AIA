// The port of the AIA panel's drawing (plan sociomap-5-web, chunk 2) against values the panel's OWN
// functions return. `fixtures/object-map-draw-golden.json` was written outside the repository by a
// Node script that cuts the used functions verbatim out of NPC_Panel/ui_app.html (the line numbers are
// in its `source` field), stubs the panel state and page, feeds them the stored hudba map of
// `object-map-signed-off.json` in frame units, and records what they return and paint on a recording
// context; `nodeScale` is the methodology's sociomap_3d.node_scale, which the panel reads from its
// backend. The port must match to 1e-9, colour strings exactly.
import { describe, expect, it } from "vitest";

import { t, tv } from "@/i18n/t";
import golden from "./fixtures/object-map-draw-golden.json";
import fixture from "./fixtures/object-map-signed-off.json";
import {
  FRAME_SPAN,
  absoluteGrid,
  bannerBox,
  densityGrid,
  dotColour,
  dotOffset,
  SEGMENT_COLOURS,
  SEGMENT_GREY,
  panelDots,
  gridAxis,
  mapStatements,
  statementNotes,
  uncertaintyCircle,
  wrapWords,
  blend66,
  camera3d,
  color66,
  drawLegendCard,
  drawObjectMap,
  nodeScale,
  nodeTones,
  normalizer,
  panelNodes,
  projection,
  quadClip,
  relationGeometry,
  relationPairs,
  relationStrength,
  storedGrid,
  strongestRelation,
  terrainAt,
  toFrame,
  toFrameLength,
  topCamera,
  wheelCamera,
  zoomCamera,
  ZOOM_IN,
  ZOOM_OUT,
  INITIAL_CAMERA,
  type LegendCard,
  type Norm,
  type PanelCamera,
  type RelationMode,
} from "./object-map-panel";
import { type SignedOffRespondents, respondentNote, storedFrame } from "./object-map-signed-off";
import type { BatteryWithMaps, ObjectMapArtifact } from "./object-map-view";

const battery = fixture.batteries[0] as unknown as BatteryWithMaps;
const map: ObjectMapArtifact = battery.maps!["aia-sociomap-5"].artifact;
const frame = storedFrame(map)!;
const nodes = panelNodes(battery, map, frame);

/**
 * The panel's envelope (`terrainEnvelope66`), kept in the tests only: the web never evaluates a
 * kernel (the engine stores both surfaces), but the tests hold the stored ones to the panel's and
 * build the synthetic maps with it.
 */
function terrainEnvelope(points: [number, number][], heights: number[], xs: number[], ys: number[], sigma: number): { z: number[][]; top: number[][] } {
  const z: number[][] = [], top: number[][] = [];
  for (const y of ys) {
    const zr: number[] = [], tr: number[] = [];
    for (const x of xs) {
      let best = 0, arg = -1;
      for (let j = 0; j < points.length; j++) {
        const v = heights[j] * Math.exp(-((x - points[j][0]) ** 2 + (y - points[j][1]) ** 2) / (2 * sigma * sigma));
        if (v > best) { best = v; arg = j; }
      }
      zr.push(best); tr.push(arg);
    }
    z.push(zr); top.push(tr);
  }
  return { z, top };
}

/** Deep equality with numbers to 1e-9 and everything else (colour strings, fonts) exact. */
function close(actual: unknown, expected: unknown, path = "$"): void {
  if (typeof expected === "number") {
    expect(typeof actual, path).toBe("number");
    expect(Math.abs((actual as number) - expected), path).toBeLessThanOrEqual(1e-9);
  } else if (expected !== null && typeof expected === "object") {
    expect(actual, path).toBeTypeOf("object");
    const keys = Object.keys(expected);
    expect(Object.keys(actual as object).length, `${path} keys`).toBe(keys.length);
    for (const k of keys) close((actual as Record<string, unknown>)[k], (expected as Record<string, unknown>)[k], `${path}.${k}`);
  } else {
    expect(actual, path).toBe(expected);
  }
}

describe("colour and normalisation", () => {
  it("colours a height as the panel's ramp does, exactly", () => {
    for (const [t, rgb] of golden.color66) expect(color66(t as number)).toBe(rgb);
    for (const [rgb, light, out] of golden.blend66) expect(blend66(rgb as string, light as number)).toBe(out);
  });

  it("normalises as the panel's Relativni (15 % floor) and Absolutni", () => {
    const g = golden.normalizer;
    const values = nodes.map((n) => n.value!);
    const check = (n: ReturnType<typeof normalizer>, e: (typeof g)["range"], kind: string) => {
      expect(n.kind).toBe(kind);
      close([n.lo, n.hi, g.probe.map(n.t)], [e.lo, e.hi, e.t]);
    };
    check(normalizer(values, "range"), g.range, "range");
    check(normalizer(values, "absolute", [0, 1]), g.absolute, "absolute");
    check(normalizer([-3, 2.5], "absolute", null), g.absoluteNoBounds, "absolute");
    check(normalizer([0.4, 0.4], "range"), g.flat, "range");
    check(normalizer([], "range"), g.empty, "none");
    expect([g.range.label, g.absolute.label, g.empty.label]).toEqual(["rozsah", "absolutní", "bez dat"]);
  });

  it("colours the nodes by the stored relative heights, which are the panel's Relativni of the stored means", () => {
    const relative = normalizer(nodes.map((n) => n.value!), "range");
    nodeTones(nodes, "range").forEach((t, k) => expect(Math.abs(t - relative.t(nodes[k].value!))).toBeLessThanOrEqual(1e-12));
    expect(nodeTones(nodes, "absolute")).toEqual(nodes.map((n) => n.value));
  });
});

describe("camera", () => {
  it("projects as the panel's orthographic camera", () => {
    for (const { camera, sc, points } of Object.values(golden.projection)) {
      const { W, H, ...c } = camera;
      const P = projection(c, W, H);
      expect(Math.abs(P.sc - sc)).toBeLessThanOrEqual(1e-9);
      for (const [x, y, z, sx, sy, depth] of points) { const q = P.project(x, y, z); close([q.x, q.y, q.depth], [sx, sy, depth]); }
    }
  });

  it("moves as the panel's 2D, 3D, zoom, centre and wheel", () => {
    for (const { from, top, three, zin, zout, center, wheelOut, wheelIn } of Object.values(golden.camera)) {
      const { W, H, ...c } = from;
      close(topCamera(c, W, H), top);
      close(camera3d(c), three);
      close(zoomCamera(c, ZOOM_IN), zin);
      close(zoomCamera(c, ZOOM_OUT), zout);
      close(INITIAL_CAMERA, center);
      close([wheelCamera(c, 100).zoom, wheelCamera(c, -100).zoom], [wheelOut, wheelIn]);
    }
  });
});

describe("frame and terrain", () => {
  it("puts the stored grid's square on the panel's +-62 frame", () => {
    const corner = toFrame(frame.cx - frame.half, frame.cy + frame.half, frame);
    close(corner, { x: -FRAME_SPAN, y: FRAME_SPAN });
    const grid = storedGrid(map)!;
    expect(grid.N).toBe(84);
    expect(grid.xs[0]).toBe(-62);
    expect(grid.xs[84]).toBe(62);
  });

  it("places the objects and sizes the hills as the panel's own frame fit does", () => {
    // fitToFrame66 over placedIdx66 on the ruler x 27 positions: a wrong centre sign or a flipped
    // axis in the frame conversion fails here.
    for (const { battery: id, positions, sigma } of golden.frame) {
      const b = (fixture.batteries as unknown as BatteryWithMaps[]).find((x) => x.battery_id === id)!;
      const m = b.maps!["aia-sociomap-5"].artifact, f = storedFrame(m)!;
      close(panelNodes(b, m, f).map((n) => [n.x, n.y]), positions);
      close(toFrameLength(m.terrain.status === "computed" ? m.terrain.parameters.sigma : NaN, f), sigma);
    }
  });

  it("holds the engine's stored Absolutni terrain to the panel's own envelope of the stored means", () => {
    // The panel computes this surface in the browser (`terrainEnvelope66`); here the engine stores it
    // and the web only reads it, so the stored grid must be the panel's to the last digit.
    const sigma = toFrameLength(map.terrain.status === "computed" ? map.terrain.parameters.sigma : NaN, frame);
    expect(Math.abs(sigma - golden.envelope.sigma)).toBeLessThanOrEqual(1e-9);
    const xs = storedGrid(map)!.xs;
    const env = terrainEnvelope(nodes.map((n) => [n.x, n.y]), nodes.map((n) => n.value!), xs, xs, sigma);
    const grid = absoluteGrid(map)!;
    for (const [gy, gx, z, top] of golden.envelope.cells) {
      close([env.z[gy][gx], grid.ht[gy][gx]], [z, z]);
      expect(env.top[gy][gx]).toBe(top);
    }
    for (const b of fixture.batteries as unknown as BatteryWithMaps[]) {
      const m = b.maps!["aia-sociomap-5"].artifact, f = storedFrame(m)!, ns = panelNodes(b, m, f);
      const e = terrainEnvelope(ns.map((n) => [n.x, n.y]), ns.map((n) => n.value!), xs, xs, toFrameLength(m.terrain.status === "computed" ? m.terrain.parameters.sigma : NaN, f)).z;
      close(absoluteGrid(m)!.ht, e);
    }
  });

  it("has no Absolutni terrain when the map stores none", () => {
    const terrain = map.terrain as Extract<ObjectMapArtifact["terrain"], { status: "computed" }>;
    expect(absoluteGrid({ ...map, terrain: { ...terrain, absolute_height: undefined } })).toBeNull();
    expect(absoluteGrid({ ...map, terrain: { status: "not_computed", reason: "x" } })).toBeNull();
  });

  it("reads the drawn elevation under a point as the panel does", () => {
    const relative = storedGrid(map)!, absolute = absoluteGrid(map)!;
    for (const [x, y, z] of golden.terrainAt.relative) close(terrainAt(relative, x, y), z);
    for (const [x, y, z] of golden.terrainAt.absolute) close(terrainAt(absolute, x, y), z);
  });
});

describe("relations, nodes, labels", () => {
  it("draws the panel's pairs: Top vztahy, the selected object's, all", () => {
    for (const [key, pairs] of Object.entries(golden.pairs)) {
      const [mode, selected] = key.split(":");
      close(relationPairs(map, mode as RelationMode, Number(selected)).map((p) => [p.i, p.j, p.r]), pairs);
    }
    expect(golden.pairs["top:-1"]).toHaveLength(5);
    expect(golden.pairs["selected:-1"]).toEqual([]);
  });

  it("bends and clips a relation line as the panel's curve", () => {
    for (const { a, b, side, ra, rb, out } of golden.geometry) {
      const g = relationGeometry(a, b, side, ra, rb);
      if (out === null) expect(g).toBeNull();
      else close({ c: g!.c, piece: g!.piece, mid: g!.mid }, out);
    }
    for (const [a, c, b, R, end, t] of golden.quadClip) close(quadClip(a as never, c as never, b as never, R as number, end as boolean), t);
  });

  it("sizes nodes as the methodology's node_scale", () => {
    for (const [M, s] of golden.nodeScale) close(nodeScale(M), s);
  });
});

/** A context that records the fills, strokes and texts painted; text widths as the golden run's. */
function recorder() {
  type Op = { op: string; path: unknown[][]; style?: string; alpha?: number; width?: number; dash?: string; text?: string; x?: number; y?: number; font?: string; align?: string; baseline?: string; w?: number; h?: number; fill?: string; tx?: number; ty?: number; rot?: number };
  const ops: Op[] = [];
  let path: unknown[][] = [];
  let state = { fillStyle: "#000", strokeStyle: "#000", lineWidth: 1, globalAlpha: 1, font: "10px sans-serif", dash: [] as number[], textAlign: "start", textBaseline: "alphabetic", tx: 0, ty: 0, rot: 0 };
  const stack: (typeof state)[] = [];
  const measure = (text: string, font: string) => text.length * (font.startsWith("800") ? 6.9 : 6.2);
  const ctx = {
    get fillStyle() { return state.fillStyle; }, set fillStyle(v) { state.fillStyle = v; },
    get strokeStyle() { return state.strokeStyle; }, set strokeStyle(v) { state.strokeStyle = v; },
    get lineWidth() { return state.lineWidth; }, set lineWidth(v) { state.lineWidth = v; },
    get globalAlpha() { return state.globalAlpha; }, set globalAlpha(v) { state.globalAlpha = v; },
    get font() { return state.font; }, set font(v) { state.font = v; },
    get textAlign() { return state.textAlign; }, set textAlign(v) { state.textAlign = v; },
    get textBaseline() { return state.textBaseline; }, set textBaseline(v) { state.textBaseline = v; },
    lineCap: "butt", shadowColor: "", shadowBlur: 0,
    setLineDash(d: number[]) { state.dash = [...d]; },
    translate(x: number, y: number) { state.tx += x; state.ty += y; },
    rotate(a: number) { state.rot += a; },
    roundRect(x: number, y: number, w: number, h: number, r: number) { path.push(["R", x, y, w, h, r]); },
    save() { stack.push({ ...state }); }, restore() { state = stack.pop() ?? state; },
    fillRect(x: number, y: number, w: number, h: number) { ops.push({ op: "rect", path: [], x, y, w, h, fill: state.fillStyle, tx: state.tx, ty: state.ty, rot: state.rot }); },
    beginPath() { path = []; }, closePath() { path.push(["Z"]); },
    moveTo(x: number, y: number) { path.push(["M", x, y]); }, lineTo(x: number, y: number) { path.push(["L", x, y]); },
    quadraticCurveTo(cx: number, cy: number, x: number, y: number) { path.push(["Q", cx, cy, x, y]); },
    arc(x: number, y: number, r: number) { path.push(["A", x, y, r]); },
    fill() { ops.push({ op: "fill", path, style: state.fillStyle, alpha: state.globalAlpha }); },
    stroke() { ops.push({ op: "stroke", path, style: state.strokeStyle, alpha: state.globalAlpha, width: state.lineWidth, dash: state.dash.join(",") }); },
    fillText(text: string, x: number, y: number) { ops.push({ op: "text", path: [], text, x, y, font: state.font, style: state.fillStyle, align: state.textAlign, baseline: state.textBaseline }); },
    measureText(text: string) { return { width: measure(text, state.font) }; },
    createLinearGradient(x0: number, y0: number, x1: number, y1: number) {
      const stops: [number, string][] = [];
      return { kind: "gradient", x0, y0, x1, y1, stops, addColorStop(o: number, c: string) { stops.push([o, c]); } };
    },
  };
  return { ctx: ctx as unknown as CanvasRenderingContext2D, ops };
}

/** The same summary of a frame the golden run took of the panel's `draw66`. */
function summarise(ops: ReturnType<typeof recorder>["ops"]) {
  const tri = ops.filter((o) => o.op === "fill" && o.alpha === 0.94);
  const pick = [0, 1, 777, 5000, 9999, tri.length - 1];
  const { op, x, y, w, h, fill } = ops[0];
  return {
    background: { op, x, y, w, h, fill },
    slab: ops.filter((o) => o.op === "fill" && (o.style === "#06151a" || o.style === "#071c22")).map((o) => ({ style: o.style, path: o.path })),
    slabStrokes: ops.filter((o) => o.op === "stroke" && o.style === "rgba(255,255,255,.05)").map((o) => o.width),
    triangles: { count: tri.length, samples: pick.map((k) => ({ k, style: tri[k].style, path: tri[k].path })), hairline: ops.find((o) => o.op === "stroke" && o.style === "rgba(255,255,255,.025)")?.width ?? null },
    contours: ops.filter((o) => o.op === "stroke" && o.style === "rgba(5,10,12,.30)").map((o) => ({ segments: o.path.filter((s) => s[0] === "M").length, first: o.path.slice(0, 2), last: o.path.slice(-2), width: o.width })),
    lines: ops.filter((o) => o.op === "stroke" && o.path.some((s) => s[0] === "Q")).map((o) => ({ style: o.style, alpha: o.alpha, width: o.width, path: o.path })),
    discs: ops.filter((o) => o.op === "fill" && o.path.some((s) => s[0] === "A")).map((o) => ({ style: o.style, alpha: o.alpha, path: o.path })),
    rings: ops.filter((o) => o.op === "stroke" && !o.dash && o.path.length === 1 && o.path[0][0] === "A").map((o) => ({ style: o.style, alpha: o.alpha, width: o.width, path: o.path })),
    texts: ops.filter((o) => o.op === "text").map((o) => ({ text: o.text, x: o.x, y: o.y, font: o.font, style: o.style, align: o.align, baseline: o.baseline })),
    rects: ops.filter((o) => o.op === "rect").map((o) => ({ x: o.x, y: o.y, w: o.w, h: o.h, fill: o.fill, tx: o.tx, ty: o.ty, rot: o.rot })),
    statements: ops.filter((o) => (o.op === "stroke" && (o.dash || o.path.some((p) => p[0] === "R"))) || (o.op === "fill" && o.path.some((p) => p[0] === "R")))
      .map((o) => ({ op: o.op, style: o.style, width: o.width ?? null, dash: o.dash ?? null, path: o.path })),
  };
}

describe("a whole frame", () => {
  for (const [name, scene] of Object.entries(golden.scenes)) {
    it(`paints ${name} as the panel's draw66`, () => {
      const { W, H, ...camera } = scene.camera as PanelCamera & { W: number; H: number };
      const norm = scene.norm as Norm;
      const strongest = strongestRelation(map);
      const pairs = relationPairs(map, scene.relMode as RelationMode, scene.selected).map((p) => ({ ...p, k: relationStrength(p.v, norm, strongest) }));
      const { ctx, ops } = recorder();
      const grid = norm === "absolute" ? absoluteGrid(map)! : storedGrid(map)!;
      const result = drawObjectMap(ctx, { width: W, height: H, camera, grid, nodes, tones: nodeTones(nodes, norm), pairs, selected: scene.selected, hovered: scene.hovered, nodeScale: nodeScale(map.object_ids.length) });
      close(summarise(ops), scene.summary);
      // Every hit in the panel's order: the drawn relation lines at their midpoints, then the objects.
      close(result.hits.map((h) => [h.kind, h.index, h.j ?? null, h.x, h.y, h.r]), scene.hits);
      expect(result.labels.shown).toBe(scene.summary.texts.length);
    });
  }
});

// ---------------------------------------------------------------- what the map says about itself

const TEXTS = {
  caption: t("research.exec.objectMap.panel.uncertaintyCaption"),
  weakTitle: t("research.exec.objectMap.panel.weakTitle"),
  weakBody: (percent: number) => tv("research.exec.objectMap.panel.weakBody", { percent }),
  noStructureTitle: t("research.exec.objectMap.panel.noStructureTitle"),
  noStructureBody: t("research.exec.objectMap.panel.noStructureBody"),
  sparse: t("research.exec.objectMap.panel.sparseNote"),
  labelled: (shown: number, total: number) => tv("research.exec.objectMap.panel.labelledNote", { shown, total }),
};

/** The stored hudba map with part of its artifact replaced, as another stored map would be. */
function variant(patch: Partial<ObjectMapArtifact>): BatteryWithMaps {
  const b = structuredClone(battery);
  Object.assign(b.maps!["aia-sociomap-5"].artifact, structuredClone(patch));
  return b;
}

/** 36 objects at fixed pseudo-random ruler positions, no known pair, the terrain as the stored frame's
 *  envelope: a large map whose labels cannot all fit (the golden run builds the same one). */
function bigBattery(): BatteryWithMaps {
  const ids = Array.from({ length: 36 }, (_, k) => `big-o${k}`);
  const points = ids.map((_, k) => [Math.round(900 * Math.sin(k * 1.7 + 0.3)) / 1000, Math.round(900 * Math.cos(k * 2.3)) / 1000] as [number, number]);
  const values = ids.map((_, k) => 0.4 + (0.3 * ((k * 37) % 11)) / 10);
  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2, cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const half = Math.max(...points.map((p) => Math.max(Math.abs(p[0] - cx), Math.abs(p[1] - cy)))) / 0.7;
  const rel = normalizer(values, "range");
  const relative = values.map((v) => rel.t(v));
  const f = { cx, cy, half };
  const axis = gridAxis(84);
  const framed = points.map((p) => { const q = toFrame(p[0], p[1], f); return [q.x, q.y] as [number, number]; });
  const height = terrainEnvelope(framed, relative, axis, axis, toFrameLength(0.25, f)).z;
  const absolute_height = terrainEnvelope(framed, values, axis, axis, toFrameLength(0.25, f)).z;
  const empty = () => ids.map(() => ids.map(() => null));
  const artifact: ObjectMapArtifact = {
    ...structuredClone(map),
    object_ids: ids, roles: Object.fromEntries(ids.map((id) => [id, "primary"])),
    relations: { r: empty(), n: empty(), status: empty(), n_min: 10 },
    status_counts: { reliable: 0, weak: 0, unknown: 630 },
    layout: { ...map.layout!, points },
    heights: { metric: "mean_rating_0_1", values, support_n: ids.map(() => 100), relative },
    terrain: { ...(map.terrain as Extract<ObjectMapArtifact["terrain"], { status: "computed" }>), parameters: { grid_resolution: 84, half_extent: half, sigma: 0.25, centre: [cx, cy] }, height, absolute_height },
    credibility: { rule: "split_half", split_half: 0.7, threshold: 0.59, weakly_determined: false, reliable_pairs: 0, uncertainty_radius: 0.12 },
    objects_not_placed: [], sparse_design: { flag: false, share_below_layout_floor: 0, weakly_connected: [] },
  };
  return { ...structuredClone(battery), battery_id: "big", objects: ids.map((id, k) => ({ id, label: `Žánr číslo ${k + 1}` })), maps: { "aia-sociomap-5": { ...battery.maps!["aia-sociomap-5"], artifact } } };
}

const SOURCES: Record<string, BatteryWithMaps> = {
  hudba: battery,
  sum: (fixture.batteries as unknown as BatteryWithMaps[])[1],
  noStructure: variant(golden.patches.noStructure as Partial<ObjectMapArtifact>),
  sparse: variant(golden.patches.sparse as Partial<ObjectMapArtifact>),
  big: bigBattery(),
};

describe("what the map says about itself", () => {
  for (const [name, scene] of Object.entries(golden.statementScenes)) {
    it(`draws ${name} as the panel's drawAiaOverlay66`, () => {
      const b = SOURCES[scene.source], m = b.maps!["aia-sociomap-5"].artifact, f = storedFrame(m)!, ns = panelNodes(b, m, f);
      const { W, H, ...camera } = scene.camera as PanelCamera & { W: number; H: number };
      const norm = scene.norm as Norm;
      const strongest = strongestRelation(m);
      const pairs = relationPairs(m, scene.relMode as RelationMode, scene.selected).map((p) => ({ ...p, k: relationStrength(p.v, norm, strongest) }));
      const { ctx, ops } = recorder();
      const grid = norm === "absolute" ? absoluteGrid(m)! : storedGrid(m)!;
      const result = drawObjectMap(ctx, {
        width: W, height: H, camera, grid, nodes: ns, tones: nodeTones(ns, norm), pairs, selected: scene.selected, hovered: scene.hovered,
        nodeScale: nodeScale(m.object_ids.length), statements: mapStatements(m, TEXTS),
      });
      close(summarise(ops), scene.summary);
      close({ ...result.labels, objects: ns.length }, scene.labelCount);
    });
  }

  it("reads the statements as stored, and draws none the artifact does not make", () => {
    const sum = SOURCES.sum.maps!["aia-sociomap-5"].artifact;
    expect(mapStatements(sum, TEXTS)).toMatchObject({ weak: true, splitHalf: sum.credibility!.split_half, radius: sum.credibility!.uncertainty_radius, sparse: false });
    expect(mapStatements({ ...map, credibility: undefined, sparse_design: undefined }, TEXTS)).toMatchObject({ weak: false, splitHalf: null, radius: null, sparse: false });
    // The sparse note gives way to the banner, which says more.
    const both = mapStatements({ ...sum, sparse_design: { flag: true, share_below_layout_floor: 0.5, weakly_connected: [] } }, TEXTS);
    expect(statementNotes(both, { shown: 3, wanted: 3 }, 8)).toEqual([]);
    expect(statementNotes({ ...both, weak: false }, { shown: 30, wanted: 31 }, 31).map((n) => n.text)).toEqual([TEXTS.sparse, "30 z 31 objektů popsáno"]);
    expect(statementNotes({ ...both, weak: false }, { shown: 29, wanted: 30 }, 30).map((n) => n.text)).toEqual([TEXTS.sparse]);
    // Each map's own notes: the label note on the object map only, the respondent note on the respondent
    // map only, the sparse note on both.
    const small = { ...both, weak: false, respondentNote: "jen orientační" };
    expect(statementNotes(small, { shown: 30, wanted: 31 }, 31, true).map((n) => n.text)).toEqual([TEXTS.sparse, "jen orientační"]);
    expect(statementNotes(small, { shown: 3, wanted: 3 }, 5).map((n) => n.text)).toEqual([TEXTS.sparse]);
  });

  it("wraps the banner's text as the panel does, and sizes the circle only within its bounds", () => {
    expect(wrapWords("aa bb cc dd", 5, (l) => l.length)).toEqual(["aa bb", "cc dd"]);
    expect(wrapWords("aaaaaaa bb", 5, (l) => l.length)).toEqual(["", "aaaaaaa", "bb"]);
    const P = projection(INITIAL_CAMERA, 900, 700);
    const pts = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 10 }];
    expect(uncertaintyCircle(P, pts.slice(0, 2), 1)).toBeNull(); // fewer than three objects
    expect(uncertaintyCircle(P, pts, null)).toBeNull();
    expect(uncertaintyCircle(P, pts, 0.001)).toBeNull(); // under 2 px
    expect(uncertaintyCircle(P, pts, 100)).toBeNull(); // a quarter of the view or more
    const c = uncertaintyCircle(P, pts, 1)!;
    expect(c.x).toBeCloseTo(900 - 96 - c.r, 12);
    expect(c.y).toBeCloseTo(72 + c.r, 12);
    expect(bannerBox(1000, 700)).toEqual({ x: 280, y: 266, w: 440, h: 84 });
  });
});

// ---------------------------------------------------------------- the respondent map

/** The stored hudba map cut to its first k objects, as a small set stores it (the golden run builds
 *  the same): under the declared minimum of objects the respondent map is only indicative; under the
 *  minimum ratings nobody is placed and the stored density is flat. */
function smallBattery(k: number): BatteryWithMaps {
  const b = structuredClone(battery), m = b.maps!["aia-sociomap-5"].artifact;
  const keep = m.object_ids.slice(0, k);
  const cut = <T,>(rows: T[][]) => rows.slice(0, k).map((row) => row.slice(0, k));
  m.object_ids = keep;
  m.roles = Object.fromEntries(keep.map((id) => [id, "primary"]));
  m.layout = { ...m.layout!, points: m.layout!.points.slice(0, k) };
  m.heights = { ...m.heights, values: m.heights.values.slice(0, k), support_n: m.heights.support_n.slice(0, k), relative: m.heights.relative!.slice(0, k) };
  m.relations = { ...m.relations, r: cut(m.relations.r), n: cut(m.relations.n), status: cut(m.relations.status), interval: cut(m.relations.interval!) };
  m.objects_not_placed = [];
  const r = m.respondents as SignedOffRespondents;
  r.informative = false;
  if (k < (m.spec.respondent_map?.min_ratings ?? 3)) {
    const n = m.respondent_ids!.length;
    r.x = Array(n).fill(null); r.y = Array(n).fill(null); r.placement = Array(n).fill("NOT_PLACED");
    r.counts = { PLACED: 0, FADED: 0, NOT_PLACED: n };
    r.density = { ...r.density, height: r.density.height.map((row) => row.map(() => 0)) };
  }
  return { ...b, battery_id: `${battery.battery_id}-${k}` };
}

const RSOURCES: Record<string, BatteryWithMaps> = { hudba: battery, sum: SOURCES.sum, small5: smallBattery(5), small2: smallBattery(2) };

/** The respondent map's note as the component words it (the panel's plural: 2-4 "objekty"). */
function noteOf(m: ObjectMapArtifact): string | null {
  const note = respondentNote(m);
  if (!note) return null;
  const objects = t(`research.exec.objectMap.panel.${note.objects >= 2 && note.objects <= 4 ? "objectsFew" : "objectsMany"}`);
  return tv(`research.exec.objectMap.panel.${note.placeable ? "respondentIndicative" : "respondentUnplaceable"}`, { n: note.objects, objects, min: note.minObjects, ratings: note.minRatings });
}

describe("the respondent map", () => {
  for (const [name, scene] of Object.entries(golden.respondentScenes)) {
    it(`draws ${name} as the panel's respondent scene`, () => {
      const b = RSOURCES[scene.source], m = b.maps!["aia-sociomap-5"].artifact, f = storedFrame(m)!, ns = panelNodes(b, m, f);
      const dots = panelDots(m, f);
      const { W, H, ...camera } = scene.camera as PanelCamera & { W: number; H: number };
      const { ctx, ops } = recorder();
      const result = drawObjectMap(ctx, {
        width: W, height: H, camera, grid: densityGrid(m)!, nodes: ns, tones: nodeTones(ns, "range"), pairs: [], selected: -1, hovered: scene.hovered,
        nodeScale: nodeScale(m.object_ids.length + (m.objects_not_placed?.length ?? 0)),
        statements: { ...mapStatements(m, TEXTS), respondentNote: noteOf(m) },
        respondents: { dots, selected: scene.person ?? -1 },
      });
      close(summarise(ops), scene.summary);
      close(result.hits.map((h) => [h.kind === "respondent" ? "respondent" : "respondent_object", h.kind === "respondent" ? dots[h.index].id : ns[h.index].id, h.x, h.y, h.r]), scene.hits);
    });
  }

  it("offsets each dot as the panel does, up to 1.1 frame units, and only for display", () => {
    const f = storedFrame(map)!;
    const dots = panelDots(map, f);
    const r = map.respondents as SignedOffRespondents;
    expect(dots).toHaveLength(r.counts.PLACED + r.counts.FADED);
    for (const d of dots) {
      const k = map.respondent_ids!.indexOf(d.id), p = toFrame(r.x[k]!, r.y[k]!, f);
      expect(Math.hypot(d.x - p.x, d.y - p.y)).toBeLessThanOrEqual(1.1);
      expect(d.faded).toBe(r.placement[k] === "FADED");
    }
    expect(dotOffset("hudba-r17")).toEqual(dotOffset("hudba-r17"));
  });

  it("reads the stored density on the object map's frame", () => {
    const g = densityGrid(map)!, d = (map.respondents as SignedOffRespondents).density;
    expect(g.N).toBe(d.parameters.grid_resolution);
    expect(d.parameters.centre).toEqual((map.terrain as Extract<ObjectMapArtifact["terrain"], { status: "computed" }>).parameters.centre);
    expect(Math.max(...g.ht.flat())).toBe(1);
    expect(densityGrid({ ...map, respondents: undefined })).toBeNull();
  });
});

// ---------------------------------------------------------------- taste segments

/** The stored hudba map with its taste segments replaced (the golden run builds the same). */
function segmentVariant(name: string): BatteryWithMaps {
  const b = structuredClone(battery);
  const seg = (b.maps!["aia-sociomap-5"].artifact.respondents as SignedOffRespondents).segments!;
  const patch = structuredClone((golden.segmentPatches as Record<string, object>)[name]) as Partial<NonNullable<SignedOffRespondents["segments"]>>;
  // The borderline hint names the likely split: the stored segments' first two profiles at 58 / 42 %.
  if (name === "borderline") patch.hint = { k: 2, shares: [0.58, 0.42], profiles: seg.profiles.slice(0, 2) };
  Object.assign(seg, patch);
  return { ...b, battery_id: `${battery.battery_id}-${name}` };
}
const SEGMENT_SOURCES = (): Record<string, BatteryWithMaps> => ({
  hudba: battery, sum: SOURCES.sum, ...Object.fromEntries(Object.keys(golden.segmentPatches).map((k) => [k, segmentVariant(k)])),
});

describe("taste segments on the respondent map", () => {
  const sources = SEGMENT_SOURCES();
  for (const [name, scene] of Object.entries(golden.segmentScenes)) {
    it(`colours the dots of ${name} as the panel's segColor66`, () => {
      const b = sources[name], m = b.maps!["aia-sociomap-5"].artifact, f = storedFrame(m)!, ns = panelNodes(b, m, f);
      const { ctx, ops } = recorder();
      drawObjectMap(ctx, {
        width: 900, height: 700, camera: INITIAL_CAMERA, grid: densityGrid(m)!, nodes: ns, tones: nodeTones(ns, "range"), pairs: [], selected: -1, hovered: -1,
        nodeScale: nodeScale(m.object_ids.length + (m.objects_not_placed?.length ?? 0)), respondents: { dots: panelDots(m, f), selected: -1 },
      });
      expect(summarise(ops).discs.map((d) => `${d.style}@${d.alpha}`)).toEqual(scene.dots);
    });
  }

  it("greys a respondent with a segment the artifact does not colour, and leaves every dot white without segments", () => {
    const dot = { id: "x", x: 0, y: 0, faded: false, segmented: true, segment: 2, coloured: true };
    expect(dotColour(dot)).toBe(SEGMENT_COLOURS[2]);
    expect(dotColour({ ...dot, coloured: false })).toBe(SEGMENT_GREY);
    expect(dotColour({ ...dot, segment: -1 })).toBe(SEGMENT_GREY);
    expect(dotColour({ ...dot, segment: 5 })).toBe(SEGMENT_COLOURS[1]);
    // As the panel's segColor66: the colour follows the stored flag alone, a faint dot included (drawn at 30 %).
    expect(dotColour({ ...dot, faded: true })).toBe(SEGMENT_COLOURS[2]);
    expect(dotColour({ ...dot, segmented: false })).toBeNull();
  });
});

describe("the PNG snapshot's legend card", () => {
  const card = (segments?: LegendCard["segments"]) => {
    const { ctx, ops } = recorder();
    drawLegendCard(ctx, { title: "Výška · Průměrné hodnocení", marks: ["6,19", "rozsah", "6,62"], segments }, 700);
    return ops;
  };

  it("draws the page's card in the bottom left: title, ramp and its three marks", () => {
    const ops = card();
    const box = ops.find((o) => o.op === "fill" && o.path.some((p) => p[0] === "R"))!;
    const [, x, y, w, h] = box.path.find((p) => p[0] === "R")! as number[];
    expect([x, w]).toEqual([17, 260]);
    expect(y + h).toBe(700 - 14);
    expect(box.style).toBe("rgba(8,11,15,.75)");
    const texts = ops.filter((o) => o.op === "text");
    expect(texts.map((o) => o.text)).toEqual(["VÝŠKA · PRŮMĚRNÉ HODNOCENÍ", "6,19", "rozsah", "6,62"]);
    expect(texts.map((o) => o.align)).toEqual(["left", "left", "center", "right"]);
    // The marks sit at the ramp's ends and the card's middle, inside the 12 px padding.
    expect(texts.slice(1).map((o) => o.x)).toEqual([29, 147, 265]);
    const ramp = ops.find((o) => o.op === "rect")!;
    expect([ramp.x, ramp.w, ramp.h]).toEqual([29, 236, 8]);
    const gradient = ramp.fill as unknown as { stops: [number, string][] };
    expect(gradient.stops.map(([, c]) => c)).toEqual(["#07134f", "#005fa8", "#00bdd1", "#14d178", "#7ce700", "#f4e81b", "#ff8f16", "#e8231d"]);
  });

  it("adds the taste segments' lines under the ramp, each with its colour, long ones wrapped", () => {
    const long = "Segment 1 · 47 % · výš: Opera, Klasika, Pop · níž: Country, Hip hop, Metal";
    const ops = card({ title: "Chuťové segmenty", rows: [{ colour: "#7fd3ff", text: long }, { colour: "#9aa3ad", text: "není jasně v jednom segmentu" }], foot: null });
    const texts = ops.filter((o) => o.op === "text").map((o) => o.text!);
    expect(texts.slice(4, 5)).toEqual(["CHUŤOVÉ SEGMENTY"]);
    // The first row wraps at the card's width: its words, in order, over more than one line.
    const first = texts.slice(5, -1);
    expect(first.length).toBeGreaterThan(1);
    expect(first.join(" ")).toBe(long);
    expect(texts.at(-1)).toBe("není jasně v jednom segmentu");
    const dots = ops.filter((o) => o.op === "fill" && o.path.some((p) => p[0] === "A")).map((o) => o.style);
    expect(dots).toEqual(["#7fd3ff", "#9aa3ad"]);
    // The card grows with its lines and still ends 14 px above the bottom.
    const [, , y, , h] = ops.find((o) => o.op === "fill" && o.path.some((p) => p[0] === "R"))!.path.find((p) => p[0] === "R") as number[];
    expect(y + h).toBe(686);
    expect(h).toBeGreaterThan(card().find((o) => o.op === "fill")!.path.find((p) => p[0] === "R")![4] as number);
  });
});
