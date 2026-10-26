// The map's smooth terrain (the owner, 2026-10-26), beside the panel's blocky one: the same stored
// terrain (the object map's envelope of hills, the respondent map's density), refined bicubically as
// the Sociomapy app refines its surface (`refineGrid`) and shaded smoothly in WebGL with the panel's
// colours and projection, then painted into the 2D canvas, so the objects, lines, labels, hits and
// the PNG export stay the 2D canvas's. Drawing only: the heights are the method's.

import { blend66, color66, type PanelCamera, type PanelGrid } from "./object-map-panel";

export type TerrainMode = "blocky" | "smooth";

/** How far under the terrain the base lies, and how dark the sides get at it (Sociomapy's
 *  `THEME.pedestal`: depth 0.01 of its 2.2-high terrain, bottomDarken 0.7, base #0e181d). */
export const PEDESTAL = { depth: (0.01 * 26) / 2.2, bottomDarken: 0.7, base: "#0e181d" } as const;
const RELIEF = 26;
const BACKGROUND: [number, number, number] = [7, 9, 12];
const REFINE = 4;

function catmullRom(p0: number, p1: number, p2: number, p3: number, t: number): number {
  return 0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
}

/** Catmull-Rom upsampling by `f`, clamped to each cell's range so a peak does not ring; every
 *  original node is kept exactly. */
export function refine(values: number[][], f: number): number[][] {
  const n = values.length, m = (n - 1) * f + 1;
  const at = (gx: number, gy: number) => values[Math.max(0, Math.min(n - 1, gy))][Math.max(0, Math.min(n - 1, gx))];
  return Array.from({ length: m }, (_, gy) => {
    const y = gy / f, j = Math.floor(y), ty = y - j;
    return Array.from({ length: m }, (_, gx) => {
      const x = gx / f, i = Math.floor(x), tx = x - i;
      const rows = [-1, 0, 1, 2].map((k) => catmullRom(at(i - 1, j + k), at(i, j + k), at(i + 1, j + k), at(i + 2, j + k), tx));
      const h = catmullRom(rows[0], rows[1], rows[2], rows[3], ty);
      const c = [at(i, j), at(i + 1, j), at(i, j + 1), at(i + 1, j + 1)];
      return Math.min(Math.max(...c), Math.max(Math.min(...c), h));
    });
  });
}

const VERTEX = `attribute vec3 aP;attribute vec3 aC;uniform vec4 uCam;uniform vec3 uView;uniform vec2 uPan;varying vec3 vC;
void main(){vec2 q=aP.xy-uPan;float rx=q.x*uCam.x-q.y*uCam.y,ry=q.x*uCam.y+q.y*uCam.x,py=ry*uCam.z-aP.z*uCam.w,pz=ry*uCam.w+aP.z*uCam.z;
float sx=uView.x*.5+rx*uView.z,sy=uView.y*.58+py*uView.z;gl_Position=vec4(sx/uView.x*2.0-1.0,1.0-sy/uView.y*2.0,-pz/400.0,1.0);vC=aC;}`;
const FRAGMENT = "precision mediump float;varying vec3 vC;void main(){gl_FragColor=vec4(vC,1.0);}";

type Gl = {
  canvas: HTMLCanvasElement; gl: WebGLRenderingContext; program: WebGLProgram;
  aP: number; aC: number; uCam: WebGLUniformLocation | null; uView: WebGLUniformLocation | null; uPan: WebGLUniformLocation | null;
  pos: WebGLBuffer | null; col: WebGLBuffer | null; idx: WebGLBuffer | null; grid: PanelGrid | null; count: number;
};
let shared: Gl | null | undefined;

function context(): Gl | null {
  if (shared !== undefined) return shared;
  const canvas = document.createElement("canvas");
  const gl = canvas.getContext("webgl", { antialias: true, preserveDrawingBuffer: true });
  if (!gl || !gl.getExtension("OES_element_index_uint")) return (shared = null);
  const shader = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return s; };
  const program = gl.createProgram()!;
  gl.attachShader(program, shader(gl.VERTEX_SHADER, VERTEX));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FRAGMENT));
  gl.linkProgram(program);
  shared = {
    canvas, gl, program, aP: gl.getAttribLocation(program, "aP"), aC: gl.getAttribLocation(program, "aC"),
    uCam: gl.getUniformLocation(program, "uCam"), uView: gl.getUniformLocation(program, "uView"), uPan: gl.getUniformLocation(program, "uPan"),
    pos: gl.createBuffer(), col: gl.createBuffer(), idx: gl.createBuffer(), grid: null, count: 0,
  };
  return shared;
}

/** The refined surface, its sides (one smooth gradient down to x0.3 at the base) and the base, as
 *  vertex positions, colours (the panel's lit ramp at .94 over the background) and triangles. */
function mesh(grid: PanelGrid): { pos: Float32Array; col: Float32Array; idx: Uint32Array } {
  const h = refine(grid.ht, REFINE), m = h.length, span = grid.span, bottom = -PEDESTAL.depth;
  const at = (k: number) => -span + (2 * span * k) / (m - 1);
  const colour = (v: number) => (blend66(color66(v), 0.78 + 0.28 * v).match(/\d+/g) ?? []).slice(0, 3).map((c, k) => (Number(c) * 0.94 + BACKGROUND[k] * 0.06) / 255);
  const pos: number[] = [], col: number[] = [], idx: number[] = [];
  for (let gy = 0; gy < m; gy++) for (let gx = 0; gx < m; gx++) { pos.push(at(gx), at(gy), h[gy][gx] * RELIEF); col.push(...colour(h[gy][gx])); }
  for (let gy = 0; gy < m - 1; gy++) for (let gx = 0; gx < m - 1; gx++) { const a = gy * m + gx, d = a + m; idx.push(a, a + 1, d + 1, a, d + 1, d); }
  const rim: number[] = [];
  for (let x = 0; x < m - 1; x++) rim.push(x);
  for (let y = 0; y < m - 1; y++) rim.push(y * m + m - 1);
  for (let x = m - 1; x > 0; x--) rim.push((m - 1) * m + x);
  for (let y = m - 1; y > 0; y--) rim.push(y * m);
  const base = pos.length / 3;
  for (const k of rim) {
    pos.push(pos[k * 3], pos[k * 3 + 1], pos[k * 3 + 2], pos[k * 3], pos[k * 3 + 1], bottom);
    const c = col.slice(k * 3, k * 3 + 3);
    col.push(...c, ...c.map((v) => v * (1 - PEDESTAL.bottomDarken)));
  }
  for (let i = 0; i < rim.length; i++) { const a = base + i * 2, b = base + ((i + 1) % rim.length) * 2; idx.push(a, b, a + 1, b, b + 1, a + 1); }
  const floor = pos.length / 3;
  for (const [x, y] of [[-span, -span], [span, -span], [span, span], [-span, span]]) { pos.push(x, y, bottom - 0.01); col.push(14 / 255, 24 / 255, 29 / 255); }
  idx.push(floor, floor + 1, floor + 2, floor, floor + 2, floor + 3);
  return { pos: new Float32Array(pos), col: new Float32Array(col), idx: new Uint32Array(idx) };
}

/** Draws the smooth terrain into `ctx` (CSS pixels, W x H). False when the browser has no WebGL:
 *  the caller then draws the blocky terrain. */
export function drawSmoothTerrain(ctx: CanvasRenderingContext2D, grid: PanelGrid, camera: PanelCamera, W: number, H: number, ratio: number): boolean {
  const g = context();
  if (!g) return false;
  const gl = g.gl;
  if (g.grid !== grid) {
    const m = mesh(grid);
    gl.bindBuffer(gl.ARRAY_BUFFER, g.pos); gl.bufferData(gl.ARRAY_BUFFER, m.pos, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, g.col); gl.bufferData(gl.ARRAY_BUFFER, m.col, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, g.idx); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, m.idx, gl.STATIC_DRAW);
    g.count = m.idx.length;
    g.grid = grid;
  }
  const w = Math.max(1, Math.round(W * ratio)), h = Math.max(1, Math.round(H * ratio));
  if (g.canvas.width !== w || g.canvas.height !== h) { g.canvas.width = w; g.canvas.height = h; }
  gl.viewport(0, 0, w, h);
  gl.clearColor(BACKGROUND[0] / 255, BACKGROUND[1] / 255, BACKGROUND[2] / 255, 1);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST);
  gl.depthFunc(gl.LEQUAL);
  gl.useProgram(g.program);
  gl.bindBuffer(gl.ARRAY_BUFFER, g.pos); gl.enableVertexAttribArray(g.aP); gl.vertexAttribPointer(g.aP, 3, gl.FLOAT, false, 0, 0);
  gl.bindBuffer(gl.ARRAY_BUFFER, g.col); gl.enableVertexAttribArray(g.aC); gl.vertexAttribPointer(g.aC, 3, gl.FLOAT, false, 0, 0);
  gl.uniform4f(g.uCam, Math.cos(camera.yaw), Math.sin(camera.yaw), Math.cos(camera.pitch), Math.sin(camera.pitch));
  gl.uniform3f(g.uView, W, H, Math.min(W, H) * 0.0087 * camera.zoom);
  gl.uniform2f(g.uPan, camera.panX, camera.panY);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, g.idx);
  gl.drawElements(gl.TRIANGLES, g.count, gl.UNSIGNED_INT, 0);
  ctx.drawImage(g.canvas, 0, 0, W, H);
  return true;
}
