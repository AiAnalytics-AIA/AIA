// The map's contour lines (the owner, 2026-10-26), as the AIA panel draws them (`contourRuns66`,
// `drawContours66`), which follow the Sociomapy app (lib/contours.ts computeSmoothContours,
// lib/settledArtifacts.ts paintContours): nine levels 0.1..0.9 traced by marching squares and
// stitched into runs, Chaikin x2 and Taubin x12; each line in the terrain's colour at its level
// x tone, shaded by one in-map light (the shadow side toward black), thinner where lines crowd, a
// two-pass glow widening toward the corners, fading toward them and dissolving on steep shadowed
// ground. Each pass is stroked opaque on a layer and laid over the map at the pass's alpha, so the
// joints of a line blend once. Presentation only.

import { color66, type PanelGrid, type Projection } from "./object-map-panel";

const CONTOUR = {
  levels: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
  tone: 0.72,
  opacity: 0.5,
  width: 6,
  glow: 3,
  smoothing: 2,
  emboss: 1.5,
  embossLight: 0,
  embossDark: 0.6,
  groundShade: 0.2,
  rotation: 210,
  densityThin: 1,
  focusFade: 2,
  dissolve: 0.9,
  tex: 1536,
  focusBlur: 14,
} as const;
const RELIEF = 26;

type Pt = { x: number; y: number };
/** One drawn piece of a contour, in grid fractions (0..1 across the frame). */
type Segment = { a: Pt; b: Pt; level: number; lit: number; mag: number; focus: number; r: number; density: number };

const runs = new WeakMap<PanelGrid, Segment[]>();

/** The contour segments of a grid, computed once per grid (`contourRuns66`). */
function contourSegments(grid: PanelGrid): Segment[] {
  const cached = runs.get(grid);
  if (cached) return cached;
  const C = CONTOUR, N = grid.N, r = N + 1;
  const v = (gx: number, gy: number) => grid.ht[Math.max(0, Math.min(N, gy))][Math.max(0, Math.min(N, gx))];
  const kl = Math.hypot(6, 3), L0 = { x: 6 / kl, y: 3 / kl }, rad = (C.rotation * Math.PI) / 180;
  const light = { x: L0.x * Math.cos(rad) - L0.y * Math.sin(rad), y: L0.x * Math.sin(rad) + L0.y * Math.cos(rad) };
  const slope = (x: number, y: number) => {
    const fx = Math.min(r - 2, Math.max(1, x * (r - 1))), fy = Math.min(r - 2, Math.max(1, y * (r - 1)));
    const i = Math.floor(fx), j = Math.floor(fy), tx = fx - i, ty = fy - j;
    const cl = (q: number) => Math.min(r - 2, Math.max(1, q));
    const gx = (a: number, b: number) => v(cl(a) + 1, cl(b)) - v(cl(a) - 1, cl(b));
    const gy = (a: number, b: number) => v(cl(a), cl(b) + 1) - v(cl(a), cl(b) - 1);
    const l2 = (f: (a: number, b: number) => number) => (f(i, j) * (1 - tx) + f(i + 1, j) * tx) * (1 - ty) + (f(i, j + 1) * (1 - tx) + f(i + 1, j + 1) * tx) * ty;
    const dx = l2(gx), dy = l2(gy), len = Math.hypot(dx, dy);
    return len < 1e-9 ? { lit: 0, mag: 0 } : { lit: (-dx * light.x - dy * light.y) / len, mag: len };
  };
  const key = (x: number, y: number) => Math.round(x * 1e6) + "|" + Math.round(y * 1e6);
  const step = 1 / N;
  const segs: Segment[] = [];
  for (const level of C.levels) {
    // Marching squares, each cell's crossings as the Sociomapy app's cases emit them.
    const ls: [Pt, Pt][] = [];
    for (let gy = 0; gy < N; gy++) {
      for (let gx = 0; gx < N; gx++) {
        const x0 = gx * step, y0 = gy * step, x1 = x0 + step, y1 = y0 + step;
        const TL = v(gx, gy), TR = v(gx + 1, gy), BR = v(gx + 1, gy + 1), BL = v(gx, gy + 1);
        let c = 0;
        if (TL > level) c |= 1;
        if (TR > level) c |= 2;
        if (BR > level) c |= 4;
        if (BL > level) c |= 8;
        if (c === 0 || c === 15) continue;
        const e = (a: number, b: number, va: number, vb: number) => (va === vb ? a : a + (b - a) * ((level - va) / (vb - va)));
        const T = { x: e(x0, x1, TL, TR), y: y0 }, R = { x: x1, y: e(y0, y1, TR, BR) }, B = { x: e(x0, x1, BL, BR), y: y1 }, Lf = { x: x0, y: e(y0, y1, TL, BL) };
        const p = (a: Pt, b: Pt) => ls.push([a, b]);
        const cases: Record<number, () => void> = {
          1: () => p(Lf, T), 2: () => p(T, R), 3: () => p(Lf, R), 4: () => p(R, B), 5: () => { p(Lf, T); p(R, B); }, 6: () => p(T, B), 7: () => p(Lf, B),
          8: () => p(B, Lf), 9: () => p(T, B), 10: () => { p(T, R); p(B, Lf); }, 11: () => p(R, B), 12: () => p(Lf, R), 13: () => p(T, R), 14: () => p(Lf, T),
        };
        cases[c]();
      }
    }
    // Stitched into runs by their shared end points.
    const ends = new Map<string, number[]>(), used = new Array<boolean>(ls.length).fill(false);
    const reg = (k: string, i: number) => { const a = ends.get(k); if (a) a.push(i); else ends.set(k, [i]); };
    ls.forEach((sg, i) => { reg(key(sg[0].x, sg[0].y), i); reg(key(sg[1].x, sg[1].y), i); });
    const free = (k: string) => { for (const i of ends.get(k) ?? []) if (!used[i]) return i; return -1; };
    const far = (i: number, k: string) => (key(ls[i][0].x, ls[i][0].y) === k ? ls[i][1] : ls[i][0]);
    for (let i = 0; i < ls.length; i++) {
      if (used[i]) continue;
      used[i] = true;
      let pts: Pt[] = [ls[i][0], ls[i][1]];
      for (;;) {
        const tl = pts[pts.length - 1], k = key(tl.x, tl.y), j = free(k);
        if (j < 0) break;
        used[j] = true;
        pts.push(far(j, k));
        const z = pts[pts.length - 1];
        if (key(z.x, z.y) === key(pts[0].x, pts[0].y)) break;
      }
      for (;;) {
        const h = pts[0], k = key(h.x, h.y), j = free(k);
        if (j < 0) break;
        used[j] = true;
        pts.unshift(far(j, k));
      }
      const closed = pts.length > 2 && key(pts[0].x, pts[0].y) === key(pts[pts.length - 1].x, pts[pts.length - 1].y);
      if (closed) pts.pop();
      // Chaikin x2.
      for (let it = 0; it < (C.smoothing > 0 ? 2 : 0); it++) {
        const n = pts.length;
        if (n < 3) break;
        const o: Pt[] = [];
        if (!closed) o.push(pts[0]);
        for (let q = 0; q < (closed ? n : n - 1); q++) {
          const A = pts[q], Bq = pts[(q + 1) % n];
          o.push({ x: A.x * 0.75 + Bq.x * 0.25, y: A.y * 0.75 + Bq.y * 0.25 }, { x: A.x * 0.25 + Bq.x * 0.75, y: A.y * 0.25 + Bq.y * 0.75 });
        }
        if (!closed) o.push(pts[n - 1]);
        pts = o;
      }
      // Taubin (lambda .5, mu -.53): the meander goes, a ring does not shrink.
      const relax = (src: Pt[], f: number) => src.map((P0, q) => {
        const n = src.length;
        if (!closed && (q === 0 || q === n - 1)) return P0;
        const A = src[(q - 1 + n) % n], Bq = src[(q + 1) % n];
        return { x: P0.x + f * ((A.x + Bq.x) / 2 - P0.x), y: P0.y + f * ((A.y + Bq.y) / 2 - P0.y) };
      });
      if (pts.length >= 4) for (let q = 0; q < Math.round(C.smoothing * 6); q++) { pts = relax(pts, 0.5); pts = relax(pts, -0.53); }
      // Shading per point, low-passed along the run: one light and one shadow side per ring.
      const n = pts.length;
      if (n < 2) continue;
      const lit = new Float32Array(n), mag = new Float32Array(n);
      pts.forEach((q, k) => { const o = slope(q.x, q.y); lit[k] = o.lit; mag[k] = o.mag; });
      const along = (w: Float32Array) => {
        if (n < 5) return;
        const half = Math.min(Math.floor((n - 1) / 2), Math.max(2, Math.round((n * 0.25) / 2))), out = new Float32Array(n);
        for (let ps = 0; ps < 2; ps++) {
          for (let q = 0; q < n; q++) {
            let sum = 0, cnt = 0;
            for (let d = -half; d <= half; d++) {
              let k = q + d;
              if (closed) k = ((k % n) + n) % n;
              else if (k < 0 || k >= n) continue;
              sum += w[k];
              cnt++;
            }
            out[q] = sum / cnt;
          }
          w.set(out);
        }
      };
      along(lit);
      along(mag);
      for (let q = 0; q < (closed ? n : n - 1); q++) {
        const k = (q + 1) % n, A = pts[q], Bq = pts[k], mx = (A.x + Bq.x) / 2, my = (A.y + Bq.y) / 2, rr = Math.hypot(mx - 0.5, my - 0.5) / Math.SQRT1_2;
        const sm = (x: number) => { x = Math.min(1, Math.max(0, (x - 0.35) / 0.65)); return x * x * (3 - 2 * x); };
        segs.push({ a: A, b: Bq, level, lit: (lit[q] + lit[k]) / 2, mag: (mag[q] + mag[k]) / 2, focus: Math.min(1, C.focusFade * sm(rr)), r: rr, density: 0 });
      }
    }
  }
  const ms = segs.map((q) => q.mag).filter((m) => m > 0).sort((x, y) => x - y);
  const ref = ms.length ? ms[Math.floor(ms.length * 0.85)] || 1 : 1;
  for (const q of segs) q.density = Math.min(1, q.mag / ref);
  runs.set(grid, segs);
  return segs;
}

/** A layer as large as the map's canvas, from its own document; null where the canvas has none. */
function layerOf(ctx: CanvasRenderingContext2D): CanvasRenderingContext2D | null {
  const canvas = ctx.canvas as (HTMLCanvasElement & { contourLayer?: HTMLCanvasElement }) | undefined;
  if (!canvas?.ownerDocument) return null;
  const layer = canvas.contourLayer ?? (canvas.contourLayer = canvas.ownerDocument.createElement("canvas"));
  if (layer.width !== canvas.width || layer.height !== canvas.height) { layer.width = canvas.width; layer.height = canvas.height; }
  return layer.getContext("2d");
}

/** The contour lines over the terrain (`drawContours66`): two glow passes, then the line cores. */
export function drawContours(ctx: CanvasRenderingContext2D, P: Projection, grid: PanelGrid): void {
  const C = CONTOUR, segs = contourSegments(grid), s = grid.span;
  if (!segs.length) return;
  const lc = layerOf(ctx);
  if (!lc) return;
  const W = ctx.canvas.width, H = ctx.canvas.height, dpr = ctx.getTransform().a || 1;
  const px = (P.sc * 2 * s) / C.tex; // screen px per texture px
  const at = (q: Pt): [number, number] => [-s + 2 * s * q.x, -s + 2 * s * q.y];
  const colour = (q: Segment) => {
    let c = (color66(q.level).match(/\d+/g) ?? []).map(Number).map((x) => x * C.tone);
    if (C.groundShade > 0) { const sh = Math.min(1.8, Math.max(0.15, 1 + C.groundShade * 0.55 * q.lit)); c = c.map((x) => x * sh); }
    if (C.emboss > 0) {
      if (q.lit >= 0) { const f = Math.min(1, C.emboss * C.embossLight * q.lit); c = c.map((x) => x + (255 - x) * f); }
      else { const f = Math.min(1, C.emboss * C.embossDark * -q.lit); c = c.map((x) => x * (1 - f)); }
    }
    return c.map((x) => Math.max(0, Math.min(252, Math.round(x / 6) * 6)));
  };
  const widthOf = (q: Segment) => Math.max(1, C.width * Math.max(0.12, 1 + Math.min(1, C.densityThin) * (1.2 - 2.6 * q.density)));
  const fadeOf = (q: Segment) => { const f = Math.min(0.85, 0.7 * C.focusFade), x = Math.min(1, Math.max(0, (q.r - 0.35) / 0.65)); return x < 0.5 ? f * x : f * (0.5 + (x - 0.5)); };
  const keepOf = (q: Segment) => Math.max(0, 1 - fadeOf(q)) * Math.max(0, 1 - Math.min(1, C.dissolve) * Math.max(0, -q.lit) * q.density * 2.5);
  const pass = (alpha: number, widthFor: (q: Segment) => number | null) => {
    lc.setTransform(1, 0, 0, 1, 0, 0);
    lc.clearRect(0, 0, W, H);
    lc.setTransform(dpr, 0, 0, dpr, 0, 0);
    lc.lineCap = "round";
    lc.lineJoin = "round";
    const buckets = new Map<string, { css: string; w: number; segs: Segment[] }>();
    for (const q of segs) {
      const w = widthFor(q);
      if (w === null) continue;
      const c = colour(q), k = Math.round(keepOf(q) * 20) / 20;
      if (k <= 0) continue;
      const ww = Math.max(0.6, Math.round(w * px * 4) / 4), key = c.join(",") + "|" + k + "|" + ww;
      let b = buckets.get(key);
      if (!b) { b = { css: `rgba(${c.join(",")},${k})`, w: ww, segs: [] }; buckets.set(key, b); }
      b.segs.push(q);
    }
    for (const b of buckets.values()) {
      lc.strokeStyle = b.css;
      lc.lineWidth = b.w;
      lc.beginPath();
      for (const q of b.segs) {
        const [ax, ay] = at(q.a), [bx, by] = at(q.b), z = q.level * RELIEF + 0.08, A = P.project(ax, ay, z), B = P.project(bx, by, z);
        lc.moveTo(A.x, A.y);
        lc.lineTo(B.x, B.y);
      }
      lc.stroke();
    }
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = alpha;
    ctx.drawImage(lc.canvas, 0, 0);
    ctx.restore();
  };
  for (const g of [{ widen: 2, a: 0.16 }, { widen: 1, a: 0.3 }]) {
    pass(C.opacity * g.a, (q) => { const blur = C.glow + q.focus * C.focusBlur; return blur <= 0 ? null : widthOf(q) + blur * g.widen; });
  }
  pass(C.opacity, (q) => widthOf(q));
}
