// The dot field's maths: deterministic, the brief's numbers, and a mark that
// lands where the launch film's first frame has it.
import { describe, expect, it } from "vitest";

import {
  assignMark,
  BOLD,
  DOT_COUNT,
  drift,
  FILM_H,
  FILM_W,
  formedAt,
  groundAlpha,
  halton,
  handoffDot,
  HANDOFF,
  isPrime,
  makeDots,
  makeSprings,
  markTargets,
  parseHex,
  PHI,
  pushStep,
  PUSH_RADIUS,
  type Point,
} from "./dot-field";

const panel = { x: 0, y: 0, w: 500, h: 900 };

describe("the field", () => {
  it("is 144 dots on Halton (2, 3), the same on every load", () => {
    const dots = makeDots();
    expect(dots).toHaveLength(DOT_COUNT);
    expect(makeDots()).toEqual(dots);
    expect(halton(1, 2)).toBe(0.5);
    expect(halton(3, 3)).toBeCloseTo(1 / 9);
    dots.forEach((d, i) => {
      expect(d.n).toBe(i + 1);
      expect(d.u).toBeCloseTo(0.06 + halton(d.n, 2) * 0.88, 12);
      expect(d.v).toBeCloseTo(0.14 + halton(d.n, 3) * 0.72, 12);
      expect(d.fy).toBeCloseTo(d.fx / PHI, 12);
    });
  });

  it("makes the primes the large individuals and keeps every parameter inside the brief", () => {
    const dots = makeDots();
    const primes = dots.filter((d) => d.prime);
    expect(primes.map((d) => d.n).slice(0, 5)).toEqual([2, 3, 5, 7, 11]);
    expect(primes).toHaveLength(34);
    expect(isPrime(1)).toBe(false);
    expect(isPrime(143)).toBe(false);
    for (const d of dots) {
      const [rLo, rHi, aLo, aHi] = d.prime ? [4.2, 7.2, 0.7, 0.95] : [1.8, 3.4, 0.2, 0.45];
      expect(d.r).toBeGreaterThanOrEqual(rLo);
      expect(d.r).toBeLessThanOrEqual(rHi);
      expect(d.a).toBeGreaterThanOrEqual(aLo);
      expect(d.a).toBeLessThanOrEqual(aHi);
      for (const amp of [d.ax, d.ay]) {
        expect(amp).toBeGreaterThanOrEqual(6);
        expect(amp).toBeLessThanOrEqual(28);
      }
      expect(d.u).toBeGreaterThanOrEqual(0.06);
      expect(d.u).toBeLessThanOrEqual(0.94);
      expect(d.v).toBeGreaterThanOrEqual(0.14);
      expect(d.v).toBeLessThanOrEqual(0.86);
    }
  });

  it("does not drift under reduced motion", () => {
    const [d] = makeDots();
    expect(drift(d, panel, 0, true)).toEqual(drift(d, panel, 37.5, true));
    expect(drift(d, panel, 0, false)).not.toEqual(drift(d, panel, 1, false));
  });
});

describe("the cursor", () => {
  const dots = makeDots();
  const step = (pointer: Point | null, still = false, frames = 30) => {
    const springs = makeSprings();
    for (let f = 0; f < frames; f++) pushStep(dots, springs, panel, pointer, f / 60, 1 / 60, still);
    return springs;
  };

  it("pushes the dots near it away and leaves the far ones alone", () => {
    const home = drift(dots[0], panel, 0, false);
    const springs = step({ x: home.x - 30, y: home.y });
    expect(springs.ox[0]).toBeGreaterThan(0);
    const far = dots.findIndex((d) => {
      const p = drift(d, panel, 0, false);
      return Math.hypot(p.x - (home.x - 30), p.y - home.y) > PUSH_RADIUS + 60;
    });
    expect(springs.ox[far]).toBe(0);
    expect(springs.oy[far]).toBe(0);
  });

  it("moves a prime less than a small dot at the same distance", () => {
    const prime = dots.findIndex((d) => d.prime);
    const small = dots.findIndex((d) => !d.prime);
    const at = (i: number) => {
      const p = drift(dots[i], panel, 0, false);
      const s = makeSprings();
      pushStep(dots, s, panel, { x: p.x - 40, y: p.y }, 0, 1 / 60, false);
      return Math.hypot(s.vx[i], s.vy[i]);
    };
    expect(at(prime)).toBeLessThan(at(small));
  });

  it("springs every dot home once the cursor leaves, and does nothing under reduced motion", () => {
    const home = drift(dots[0], panel, 0, false);
    const springs = makeSprings();
    for (let f = 0; f < 30; f++) pushStep(dots, springs, panel, { x: home.x - 30, y: home.y }, f / 60, 1 / 60, false);
    for (let f = 30; f < 600; f++) pushStep(dots, springs, panel, null, f / 60, 1 / 60, false);
    expect(Math.abs(springs.ox[0])).toBeLessThan(0.05);
    const still = step({ x: home.x - 30, y: home.y }, true);
    expect([...still.ox, ...still.oy].every((v) => v === 0)).toBe(true);
  });
});

describe("the mark", () => {
  it("is the brief's lattice in film px: 15 px a unit from the centre, the A bold, the rest faint", () => {
    const t = markTargets(FILM_W, FILM_H);
    expect(t).toHaveLength(25);
    expect(t[0]).toMatchObject({ x: 780, y: 360, r: 13.5, a: 0.35, row: 0, col: 0 });
    expect(t[2]).toMatchObject({ x: 960, y: 360, r: 34.5, a: 1, apex: true });
    expect(t[24]).toMatchObject({ x: 1140, y: 720, r: 34.5, a: 1, row: 4, col: 4 });
    expect(t.filter((x) => x.r === 34.5).map((x) => [x.col * 6 + 8, x.row * 6 + 8])).toEqual(BOLD.map((b) => [...b]).sort((p, q) => p[1] - q[1] || p[0] - q[0]));
  });

  it("scales with object-fit: contain about the viewport's centre", () => {
    for (const [W, H] of [[1920, 1080], [1440, 900], [390, 844]]) {
      const s = Math.min(W / FILM_W, H / FILM_H);
      const film = markTargets(FILM_W, FILM_H);
      markTargets(W, H).forEach((tg, k) => {
        expect(tg.x).toBeCloseTo(W / 2 + (film[k].x - 960) * s, 9);
        expect(tg.y).toBeCloseTo(H / 2 + (film[k].y - 540) * s, 9);
        expect(tg.r).toBeCloseTo(film[k].r * s, 9);
      });
    }
    const t = markTargets(1920, 1080);
    expect(t.filter((x) => x.apex)).toHaveLength(1);
    expect(t.find((x) => x.apex)).toMatchObject({ row: 0, col: 2, a: 1 });
    expect(t.filter((x) => x.a === 1)).toHaveLength(10);
    expect(t.filter((x) => x.a === 0.35)).toHaveLength(15);
  });

  it("takes 25 primes, five per row by height, each row left to right, so no paths cross", () => {
    const dots = makeDots();
    const starts = dots.map((d) => drift(d, panel, 3.2, false));
    const assign = assignMark(dots, starts);
    const chosen = [...assign.keys()].filter((i) => assign[i] >= 0);
    expect(chosen).toHaveLength(25);
    expect(chosen.every((i) => dots[i].prime)).toBe(true);
    expect(new Set(chosen.map((i) => assign[i])).size).toBe(25);
    const byTarget = Array.from({ length: 25 }, (_, k) => starts[chosen.find((i) => assign[i] === k)!]);
    for (let row = 0; row < 5; row++) {
      const xs = byTarget.slice(row * 5, row * 5 + 5).map((p) => p.x);
      expect([...xs].sort((a, b) => a - b)).toEqual(xs);
      if (row < 4) {
        const lowest = Math.max(...byTarget.slice(row * 5, row * 5 + 5).map((p) => p.y));
        const nextHighest = Math.min(...byTarget.slice(row * 5 + 5, row * 5 + 10).map((p) => p.y));
        expect(lowest).toBeLessThanOrEqual(nextHighest);
      }
    }
  });
});

describe("the handoff", () => {
  const dots = makeDots();
  const target = markTargets(1440, 900)[2];
  const start = { x: 100, y: 500 };
  const now = { x: 110, y: 505 };

  it("lands a chosen dot exactly on its target, with its size, alpha and the apex colour", () => {
    const d = handoffDot(dots[1], 1, start, now, target, HANDOFF.formed, false);
    expect(d.x).toBeCloseTo(target.x, 9);
    expect(d.y).toBeCloseTo(target.y, 9);
    expect(d.r).toBeCloseTo(target.r, 9);
    expect(d.a).toBe(1);
    expect(d.apex).toBe(1);
  });

  it("starts from where the dot was, lagged by row and column", () => {
    const tg = { ...target, row: 4, col: 4 };
    const d = handoffDot(dots[1], 1, start, now, tg, 0.05 + 4 * 0.06 + 4 * 0.035, false);
    expect(d).toMatchObject({ x: now.x, y: now.y, r: dots[1].r, a: dots[1].a });
    // The last dot to leave still arrives before the mark is called formed.
    expect(0.05 + 4 * 0.06 + 4 * 0.035 + HANDOFF.move).toBeLessThan(HANDOFF.formed);
  });

  it("fades every other dot out over 0.55 s while it keeps drifting", () => {
    expect(handoffDot(dots[0], 0, start, now, null, 0, false)).toMatchObject({ x: now.x, y: now.y, a: dots[0].a });
    expect(handoffDot(dots[0], 0, start, now, null, 0.3, false).a).toBeLessThan(dots[0].a);
    expect(handoffDot(dots[0], 0, start, now, null, 0.55, false).a).toBe(0);
  });

  it("is a 0.45 s move with no stagger under reduced motion, formed at 0.5 s", () => {
    const tg = { ...target, row: 4, col: 4 };
    const d = handoffDot(dots[1], 1, start, now, tg, 0.45, true);
    expect(d.x).toBeCloseTo(tg.x, 9);
    expect(formedAt(true)).toBe(0.5);
    expect(formedAt(false)).toBe(1.75);
  });

  it("paints the film's ground opaquely before the mark forms", () => {
    expect(groundAlpha(0, false)).toBe(0);
    expect(groundAlpha(HANDOFF.groundFade, false)).toBe(1);
    expect(groundAlpha(HANDOFF.reducedFade, true)).toBe(1);
  });
});

it("reads a token's hex colour", () => {
  expect(parseHex(" #6ac5e8")).toEqual([106, 197, 232]);
  expect(parseHex("#fff")).toEqual([255, 255, 255]);
  expect(parseHex("rgb(1,2,3)")).toBeNull();
});
