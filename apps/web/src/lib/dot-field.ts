// The front door's dot field, as pure functions (components/brand/DotField.tsx
// draws it). 144 dots -- a Fibonacci number -- sit on a Halton (2, 3) sequence:
// low-discrepancy sampling, so the field looks random but covers the panel
// evenly and is the same on every load. Dots with a prime index are the larger
// "individuals"; every other per-dot parameter comes from a further Halton base,
// so nothing here is random. Each drift pairs a frequency f with f / phi, so no
// dot ever retraces its path.
//
// On a sign-in, 25 of the primes fly into the AIA mark where the launch film's
// first frame has it (markTargets), so the cut from this canvas to the film
// cannot be seen.

export const PHI = (1 + Math.sqrt(5)) / 2;
export const DOT_COUNT = 144;
export const MARK_FORMED_EVENT = "aia:mark-formed";

/** Cursor reach in CSS px; inside it a dot is pushed with force ∝ (1 − d / R)². */
export const PUSH_RADIUS = 120;

/**
 * The handoff's clock, in seconds. Under reduced motion the move is 0.45 s with no
 * stagger, the other dots and the ground fade in 0.25 s, and the mark is formed at 0.5 s.
 */
export const HANDOFF = {
  othersFade: 0.55,
  groundFade: 0.6,
  move: 1.25,
  formed: 1.75,
  reducedMove: 0.45,
  reducedFade: 0.25,
  reducedFormed: 0.5,
} as const;

export function halton(i: number, base: number): number {
  let f = 1;
  let r = 0;
  let n = i;
  while (n > 0) {
    f /= base;
    r += f * (n % base);
    n = Math.floor(n / base);
  }
  return r;
}

export function isPrime(n: number): boolean {
  if (n < 2) return false;
  for (let k = 2; k * k <= n; k++) if (n % k === 0) return false;
  return true;
}

export type Dot = {
  n: number;
  prime: boolean;
  /** Home inside the panel, as fractions of its width and height. */
  u: number;
  v: number;
  r: number;
  a: number;
  ax: number;
  ay: number;
  fx: number;
  fy: number;
  px: number;
  py: number;
};

export function makeDots(): Dot[] {
  const dots: Dot[] = [];
  for (let n = 1; n <= DOT_COUNT; n++) {
    const prime = isPrime(n);
    const f = 0.09 + halton(n, 5) * 0.16;
    dots.push({
      n,
      prime,
      u: 0.06 + halton(n, 2) * 0.88,
      v: 0.14 + halton(n, 3) * 0.72,
      r: prime ? 4.2 + halton(n, 7) * 3 : 1.8 + halton(n, 7) * 1.6,
      a: prime ? 0.7 + halton(n, 11) * 0.25 : 0.2 + halton(n, 11) * 0.25,
      // Amplitudes within 6..28 px.
      ax: 8 + halton(n, 13) * 20,
      ay: 6 + halton(n, 17) * 16,
      fx: f,
      fy: f / PHI,
      px: halton(n, 19) * 2 * Math.PI,
      py: halton(n, 23) * 2 * Math.PI,
    });
  }
  return dots;
}

export type Rect = { x: number; y: number; w: number; h: number };
export type Point = { x: number; y: number };

/** Where a dot's drift has it at time t (s), before the cursor's push; still: no drift. */
export function drift(d: Dot, panel: Rect, t: number, still: boolean): Point {
  const m = still ? 0 : 1;
  return {
    x: panel.x + d.u * panel.w + m * d.ax * Math.sin(t * d.fx * 2 * Math.PI + d.px),
    y: panel.y + d.v * panel.h + m * d.ay * Math.sin(t * d.fy * 2 * Math.PI + d.py),
  };
}

/** Each dot's offset from its drift and that offset's velocity: the cursor's push and the spring home. */
export type Springs = { ox: Float64Array; oy: Float64Array; vx: Float64Array; vy: Float64Array };

export function makeSprings(count: number = DOT_COUNT): Springs {
  return { ox: new Float64Array(count), oy: new Float64Array(count), vx: new Float64Array(count), vy: new Float64Array(count) };
}

/**
 * One step of the cursor's push (dt in s): within PUSH_RADIUS a dot is pushed away
 * with force ∝ (1 − d / R)², a prime more heavily weighted (it moves less); every
 * dot springs back home, damped. A pointer of null pushes nothing.
 */
export function pushStep(dots: Dot[], springs: Springs, panel: Rect, pointer: Point | null, t: number, dt: number, still: boolean): void {
  if (still) return;
  const { ox, oy, vx, vy } = springs;
  const damp = Math.pow(0.02, dt);
  for (let i = 0; i < dots.length; i++) {
    const d = dots[i];
    let fx = -16 * ox[i];
    let fy = -16 * oy[i];
    if (pointer) {
      const home = drift(d, panel, t, false);
      const dx = home.x + ox[i] - pointer.x;
      const dy = home.y + oy[i] - pointer.y;
      const dist = Math.hypot(dx, dy);
      if (dist < PUSH_RADIUS && dist > 0.01) {
        const k = (Math.pow(1 - dist / PUSH_RADIUS, 2) * 5200) / (d.prime ? 1.6 : 1);
        fx += (dx / dist) * k;
        fy += (dy / dist) * k;
      }
    }
    vx[i] = (vx[i] + fx * dt) * damp;
    vy[i] = (vy[i] + fy * dt) * damp;
    ox[i] += vx[i] * dt;
    oy[i] += vy[i] * dt;
  }
}

/** The launch film's frame (public/skin/brand/aia-liftoff.*), which it shows with object-fit: contain. */
export const FILM_W = 1920;
export const FILM_H = 1080;
/**
 * The mark as the film's first frame draws it, in film px: lattice coordinates
 * 8..32 step 6, LATTICE_PITCH px per unit from (20, 20) at the film's centre, the
 * A's points (BOLD, the apex first) r 34.5, the rest r 13.5.
 * tools/film_frame0.py checks a film against this before it ships.
 */
const LATTICE = [8, 14, 20, 26, 32] as const;
const LATTICE_PITCH = 15;
const BOLD_R = 34.5;
const FAINT_R = 13.5;
export const BOLD: readonly (readonly [number, number])[] = [[20, 8], [14, 14], [26, 14], [14, 20], [20, 20], [26, 20], [8, 26], [32, 26], [8, 32], [32, 32]];

export type Target = { x: number; y: number; r: number; a: number; apex: boolean; row: number; col: number };

/**
 * The 25 places of the mark in a W × H viewport, row by row: where the film,
 * shown with object-fit: contain (scale s = min(W / 1920, H / 1080), centred), has
 * its frame-0 dots. The A's points are ink at full alpha, the apex the brand apex
 * colour, the rest ink at 0.35.
 */
export function markTargets(W: number, H: number): Target[] {
  const s = Math.min(W / FILM_W, H / FILM_H);
  const targets: Target[] = [];
  for (const gy of LATTICE) {
    for (const gx of LATTICE) {
      const bold = BOLD.some(([bx, by]) => bx === gx && by === gy);
      targets.push({
        x: W / 2 + (gx - 20) * LATTICE_PITCH * s,
        y: H / 2 + (gy - 20) * LATTICE_PITCH * s,
        r: (bold ? BOLD_R : FAINT_R) * s,
        a: bold ? 1 : 0.35,
        apex: gx === 20 && gy === 8,
        row: (gy - 8) / 6,
        col: (gx - 8) / 6,
      });
    }
  }
  return targets;
}

/**
 * Which dot becomes which point of the mark: 25 primes spread evenly by their
 * vertical position, cut into 5 rows by y, each row sorted by x and mapped to the
 * lattice row by row, so no two paths cross. Returns, per dot, its target index
 * or −1 for a dot that fades out.
 */
export function assignMark(dots: Dot[], starts: Point[]): Int16Array {
  const order = dots
    .map((_, i) => i)
    .filter((i) => dots[i].prime)
    .sort((a, b) => starts[a].y - starts[b].y);
  const picked: number[] = [];
  for (let k = 0; k < 25; k++) picked.push(order[Math.round((k * (order.length - 1)) / 24)]);
  const assign = new Int16Array(dots.length).fill(-1);
  for (let row = 0; row < 5; row++) {
    picked
      .slice(row * 5, row * 5 + 5)
      .sort((a, b) => starts[a].x - starts[b].x)
      .forEach((di, col) => {
        assign[di] = row * 5 + col;
      });
  }
  return assign;
}

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
/** Progress of h through [a, b], clamped to 0..1. */
const seg = (h: number, a: number, b: number) => clamp01((h - a) / (b - a));
const easeInOut = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const easeOut = (x: number) => 1 - Math.pow(1 - x, 3);
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

/** A dot as drawn: where, how big, how opaque, and how far its colour has gone from ink to the apex colour. */
export type Drawn = { x: number; y: number; r: number; a: number; apex: number };

/**
 * A dot h seconds into the handoff. `start` is where it was when the handoff
 * began, `now` where its drift has it at this moment. A dot with no target fades
 * out while still drifting; a dot with one travels on a gentle arc, eased in and
 * out, lagged by its row and column, its size, alpha and colour interpolated.
 */
export function handoffDot(d: Dot, index: number, start: Point, now: Point, target: Target | null, h: number, reduced: boolean): Drawn {
  if (!target) {
    return { x: now.x, y: now.y, r: d.r, a: d.a * (1 - easeOut(seg(h, 0, reduced ? HANDOFF.reducedFade : HANDOFF.othersFade))), apex: 0 };
  }
  const lag = reduced ? 0 : 0.05 + target.row * 0.06 + target.col * 0.035;
  const q = easeInOut(seg(h, lag, lag + (reduced ? HANDOFF.reducedMove : HANDOFF.move)));
  // The start keeps drifting until the dot leaves, so it never stalls before moving.
  const sx = lerp(start.x, now.x, 1 - q);
  const sy = lerp(start.y, now.y, 1 - q);
  const dx = target.x - sx;
  const dy = target.y - sy;
  const len = Math.hypot(dx, dy) || 1;
  const bow = Math.sin(q * Math.PI) * len * 0.12 * (index % 2 ? 1 : -1);
  return {
    x: lerp(sx, target.x, q) - (dy / len) * bow,
    y: lerp(sy, target.y, q) + (dx / len) * bow,
    r: lerp(d.r, target.r, q),
    a: lerp(d.a, target.a, q),
    apex: target.apex ? q : 0,
  };
}

/** Seconds from the handoff's start until the mark has formed. */
export const formedAt = (reduced: boolean) => (reduced ? HANDOFF.reducedFormed : HANDOFF.formed);

/** How opaque the canvas paints the film's ground under its dots, h seconds in: opaque before the mark forms. */
export const groundAlpha = (h: number, reduced: boolean) => easeOut(seg(h, 0, reduced ? HANDOFF.reducedFade : HANDOFF.groundFade));

/** "#rrggbb" or "#rgb" to [r, g, b]; null for anything else. */
export function parseHex(value: string): [number, number, number] | null {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value.trim());
  if (!m) return null;
  const hex = m[1].length === 3 ? [...m[1]].map((c) => c + c).join("") : m[1];
  return [0, 2, 4].map((k) => parseInt(hex.slice(k, k + 2), 16)) as [number, number, number];
}
