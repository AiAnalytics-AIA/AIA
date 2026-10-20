// The port of the AIA panel's drawing (plan sociomap-5-web, chunk 2) against values the panel's OWN
// functions return. `fixtures/object-map-panel-golden.json` was written outside the repository by a
// Node script that cuts the used functions verbatim out of NPC_Panel/ui_app.html (the line numbers are
// in its `source` field), stubs the panel state and page, feeds them the stored hudba map of
// `object-map-signed-off.json` in frame units, and records what they return and paint on a recording
// context; `nodeScale` is the methodology's sociomap_3d.node_scale, which the panel reads from its
// backend. The port must match to 1e-9, colour strings exactly.
import { describe, expect, it } from "vitest";

import golden from "./fixtures/object-map-panel-golden.json";
import fixture from "./fixtures/object-map-signed-off.json";
import {
  FRAME_SPAN,
  absoluteGrid,
  blend66,
  camera3d,
  color66,
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
  terrainEnvelope,
  toFrame,
  toFrameLength,
  topCamera,
  wheelCamera,
  zoomCamera,
  ZOOM_IN,
  ZOOM_OUT,
  INITIAL_CAMERA,
  type Norm,
  type PanelCamera,
  type RelationMode,
} from "./object-map-panel";
import { storedFrame } from "./object-map-signed-off";
import type { BatteryWithMaps, ObjectMapArtifact } from "./object-map-view";

const battery = fixture.batteries[0] as unknown as BatteryWithMaps;
const map: ObjectMapArtifact = battery.maps!["aia-sociomap-5"].artifact;
const frame = storedFrame(map)!;
const nodes = panelNodes(battery, map, frame);

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

  it("draws Absolutni as the panel's envelope of the stored means, with the stored kernel width", () => {
    const sigma = toFrameLength(map.terrain.status === "computed" ? map.terrain.parameters.sigma : NaN, frame);
    expect(Math.abs(sigma - golden.envelope.sigma)).toBeLessThanOrEqual(1e-9);
    const xs = storedGrid(map)!.xs;
    const env = terrainEnvelope(nodes.map((n) => [n.x, n.y]), nodes.map((n) => n.value!), xs, xs, sigma);
    const grid = absoluteGrid(map, nodes)!;
    for (const [gy, gx, z, top] of golden.envelope.cells) {
      close([env.z[gy][gx], grid.ht[gy][gx]], [z, z]);
      expect(env.top[gy][gx]).toBe(top);
    }
  });

  it("reads the drawn elevation under a point as the panel does", () => {
    const relative = storedGrid(map)!, absolute = absoluteGrid(map, nodes)!;
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
  type Op = { op: string; path: unknown[][]; style?: string; alpha?: number; width?: number; text?: string; x?: number; y?: number; font?: string; w?: number; h?: number; fill?: string };
  const ops: Op[] = [];
  let path: unknown[][] = [];
  let state = { fillStyle: "#000", strokeStyle: "#000", lineWidth: 1, globalAlpha: 1, font: "10px sans-serif" };
  const stack: (typeof state)[] = [];
  const measure = (text: string, font: string) => text.length * (font.startsWith("800") ? 6.9 : 6.2);
  const ctx = {
    get fillStyle() { return state.fillStyle; }, set fillStyle(v) { state.fillStyle = v; },
    get strokeStyle() { return state.strokeStyle; }, set strokeStyle(v) { state.strokeStyle = v; },
    get lineWidth() { return state.lineWidth; }, set lineWidth(v) { state.lineWidth = v; },
    get globalAlpha() { return state.globalAlpha; }, set globalAlpha(v) { state.globalAlpha = v; },
    get font() { return state.font; }, set font(v) { state.font = v; },
    lineCap: "butt", textAlign: "start", shadowColor: "", shadowBlur: 0,
    save() { stack.push({ ...state }); }, restore() { state = stack.pop() ?? state; },
    fillRect(x: number, y: number, w: number, h: number) { ops.push({ op: "rect", path: [], x, y, w, h, fill: state.fillStyle }); },
    beginPath() { path = []; }, closePath() { path.push(["Z"]); },
    moveTo(x: number, y: number) { path.push(["M", x, y]); }, lineTo(x: number, y: number) { path.push(["L", x, y]); },
    quadraticCurveTo(cx: number, cy: number, x: number, y: number) { path.push(["Q", cx, cy, x, y]); },
    arc(x: number, y: number, r: number) { path.push(["A", x, y, r]); },
    fill() { ops.push({ op: "fill", path, style: state.fillStyle, alpha: state.globalAlpha }); },
    stroke() { ops.push({ op: "stroke", path, style: state.strokeStyle, alpha: state.globalAlpha, width: state.lineWidth }); },
    fillText(text: string, x: number, y: number) { ops.push({ op: "text", path: [], text, x, y, font: state.font }); },
    measureText(text: string) { return { width: measure(text, state.font) }; },
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
    discs: ops.filter((o) => o.op === "fill" && o.path.some((s) => s[0] === "A")).map((o) => ({ style: o.style, path: o.path })),
    texts: ops.filter((o) => o.op === "text").map((o) => ({ text: o.text, x: o.x, y: o.y, font: o.font })),
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
      const grid = norm === "absolute" ? absoluteGrid(map, nodes)! : storedGrid(map)!;
      const result = drawObjectMap(ctx, { width: W, height: H, camera, grid, nodes, tones: nodeTones(nodes, norm), pairs, selected: scene.selected, hovered: scene.hovered, nodeScale: nodeScale(13) });
      close(summarise(ops), scene.summary);
      close(result.hits.map((h) => [h.index, h.x, h.y, h.r]), scene.hits);
      expect(result.labels.shown).toBe(scene.summary.texts.length);
    });
  }
});
