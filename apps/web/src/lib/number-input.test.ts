import { describe, expect, it } from "vitest";

import { canStep, formatNumber, numberProblemWords, rangeWords, readNumber, stepNumber } from "./number-input";

const N = { min: 50, max: 5000, step: 10 };

describe("readNumber: a typed value is accepted as typed or refused, never clamped (I2, IA-1)", () => {
  it("accepts a value within the bounds, with Czech spaces and a decimal comma", () => {
    expect(readNumber("400", N)).toEqual({ ok: true, value: 400 });
    expect(readNumber("4 000", N)).toEqual({ ok: true, value: 4000 });
    expect(readNumber("4 000", N)).toEqual({ ok: true, value: 4000 });
    expect(readNumber(" 50 ", N)).toEqual({ ok: true, value: 50 });
    expect(readNumber("5000", N)).toEqual({ ok: true, value: 5000 });
    expect(readNumber("12,5", { min: 0, max: 100, decimals: 2 })).toEqual({ ok: true, value: 12.5 });
  });

  it("refuses a value out of range with the value as typed: 20 is not 50 (audit IA-1)", () => {
    expect(readNumber("20", N)).toEqual({ ok: false, problem: { kind: "outOfRange", value: 20 } });
    expect(readNumber("5001", N)).toEqual({ ok: false, problem: { kind: "outOfRange", value: 5001 } });
  });

  it("refuses an empty field rather than storing a default (audit IA-1, IA-2: empty stored 0)", () => {
    expect(readNumber("", N)).toEqual({ ok: false, problem: { kind: "empty" } });
    expect(readNumber("   ", N)).toEqual({ ok: false, problem: { kind: "empty" } });
  });

  it("refuses a decimal where only whole numbers go, and more places than allowed (audit IA-2: 2.5 ran as 2)", () => {
    expect(readNumber("2,5", { min: 0, max: 10 })).toEqual({ ok: false, problem: { kind: "tooPrecise", decimals: 0 } });
    expect(readNumber("2.5", { min: 0, max: 10 })).toEqual({ ok: false, problem: { kind: "tooPrecise", decimals: 0 } });
    expect(readNumber("1,255", { min: 0, max: 10, decimals: 2 })).toEqual({ ok: false, problem: { kind: "tooPrecise", decimals: 2 } });
    // Trailing zeros add no precision.
    expect(readNumber("5,0", { min: 0, max: 10 })).toEqual({ ok: true, value: 5 });
  });

  it("reads back the minus sign it prints, and the dashes pasted for one (Codex #532)", () => {
    const B = { min: -10, max: 10, decimals: 1 };
    expect(readNumber(formatNumber(-3), B)).toEqual({ ok: true, value: -3 });
    expect(readNumber(formatNumber(-2.5, 1), B)).toEqual({ ok: true, value: -2.5 });
    for (const minus of ["-", "−", "‒", "–", "﹣", "－"]) expect(readNumber(`${minus}4`, B)).toEqual({ ok: true, value: -4 });
    // Every value formatNumber writes within the bounds reads back as itself.
    for (let v = -10; v <= 10; v += 0.5) expect(readNumber(formatNumber(v, 1), B)).toEqual({ ok: true, value: v });
  });

  it("refuses what is not a number", () => {
    expect(readNumber("abc", N)).toEqual({ ok: false, problem: { kind: "notNumber", raw: "abc" } });
    expect(readNumber("1e3", N)).toEqual({ ok: false, problem: { kind: "notNumber", raw: "1e3" } });
    expect(readNumber("1,2,3", N)).toEqual({ ok: false, problem: { kind: "notNumber", raw: "1,2,3" } });
  });
});

describe("stepNumber: − / + by one step, Shift by ten, stopping at a bound", () => {
  it("moves by the step and by ten steps", () => {
    expect(stepNumber(400, 1, N)).toBe(410);
    expect(stepNumber(400, -1, N)).toBe(390);
    expect(stepNumber(400, 1, N, true)).toBe(500);
  });

  it("stops on the bound, and has nowhere to go from it", () => {
    expect(stepNumber(4995, 1, N)).toBe(5000);
    expect(stepNumber(5000, 1, N)).toBeNull();
    expect(stepNumber(50, -1, N)).toBeNull();
    expect(canStep(5000, 1, N)).toBe(false);
    expect(canStep(5000, -1, N)).toBe(true);
  });

  it("moves a value outside the range to the nearer bound in the direction pressed", () => {
    expect(stepNumber(20, 1, N)).toBe(50);
    expect(stepNumber(20, -1, N)).toBeNull();
    expect(stepNumber(9000, -1, N)).toBe(5000);
  });

  it("starts an empty field from the bound the press points away from", () => {
    expect(stepNumber(null, 1, N)).toBe(50);
    expect(stepNumber(null, -1, N)).toBe(5000);
  });

  it("lands on the places a value may carry (0.1 + 0.2)", () => {
    expect(stepNumber(0.1, 1, { min: 0, max: 1, step: 0.2, decimals: 1 })).toBe(0.3);
  });
});

describe("Czech words for numbers and their bounds", () => {
  it("groups thousands from 1 000 with a no-break space and writes a decimal comma", () => {
    expect(formatNumber(5000)).toBe("5 000");
    expect(formatNumber(40000)).toBe("40 000");
    expect(formatNumber(999)).toBe("999");
    expect(formatNumber(1.76, 2)).toBe("1,76");
    expect(formatNumber(1250, 2)).toBe("1 250,00");
    expect(formatNumber(-3)).toBe("−3");
  });

  it("states the bounds as a range, with a unit when given", () => {
    expect(rangeWords(N)).toBe("50–5 000");
    expect(rangeWords({ min: 1, max: 60 }, "USD")).toBe("1–60 USD");
  });

  it("says why a value was not saved", () => {
    expect(numberProblemWords({ kind: "outOfRange", value: 20 }, N)).toBe("Musí být 50–5 000; neuloženo.");
    expect(numberProblemWords({ kind: "empty" }, N)).toBe("Zadejte číslo 50–5 000; neuloženo.");
    expect(numberProblemWords({ kind: "tooPrecise", decimals: 0 }, N)).toBe("Jen celé číslo; neuloženo.");
    expect(numberProblemWords({ kind: "tooPrecise", decimals: 1 }, N)).toBe("Nejvýš jedno desetinné místo; neuloženo.");
    expect(numberProblemWords({ kind: "tooPrecise", decimals: 2 }, N)).toBe("Nejvýš 2 desetinná místa; neuloženo.");
    expect(numberProblemWords({ kind: "notNumber", raw: "abc" }, N)).toBe("„abc“ není číslo; neuloženo.");
  });
});
