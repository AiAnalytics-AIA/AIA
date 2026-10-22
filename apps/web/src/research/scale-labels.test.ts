import { describe, expect, it } from "vitest";
import {
  clearedWords,
  describeEveryPoint,
  endBounds,
  endsOnly,
  labelMode,
  labelProblem,
  presetOf,
  readRange,
  repeatsAnother,
  rescaleLabels,
  SCALE_LABEL_MAX,
  shownEnds,
  withEnd,
  withPoint,
} from "./scale-labels";

const five = ["rozhodně ne", "spíše ne", "nevím", "spíše ano", "rozhodně ano"];

describe("a scale's presets", () => {
  it("names the owner's four presets and calls anything else Vlastní", () => {
    expect(presetOf([1, 5])).toEqual([1, 5]);
    expect(presetOf([0, 10])).toEqual([0, 10]);
    expect(presetOf([2, 6])).toBeNull();
  });
});

describe("labels when the range changes", () => {
  it("keeps a two-end scale's two ends", () => {
    expect(rescaleLabels(["vůbec", "zcela"], [1, 10], [1, 5])).toEqual({ labels: ["vůbec", "zcela"], cleared: 0 });
  });
  it("keeps every label when the number of points is unchanged", () => {
    expect(rescaleLabels(five, [1, 5], [0, 4])).toEqual({ labels: five, cleared: 0 });
  });
  it("keeps the ends and clears the inner labels, counted for the undo, never redistributed", () => {
    expect(rescaleLabels(five, [1, 5], [1, 7])).toEqual({ labels: ["rozhodně ne", "rozhodně ano"], cleared: 3 });
    const ten = Array.from({ length: 10 }, (_, i) => `bod ${i + 1}`);
    expect(rescaleLabels(ten, [1, 10], [1, 5]).cleared).toBe(8);
  });
});

describe("describing every point", () => {
  it("prefills the two ends and leaves the inner points to the person", () => {
    expect(describeEveryPoint(["vůbec", "zcela"], [1, 5])).toEqual(["vůbec", "", "", "", "zcela"]);
    expect(describeEveryPoint(five, [1, 5])).toEqual(five);
  });
});

describe("the server's rule at the field", () => {
  it("accepts two ends, every point, or none", () => {
    expect(labelProblem(["vůbec", "zcela"], [1, 10])).toBeNull();
    expect(labelProblem(five, [1, 5])).toBeNull();
    expect(labelProblem(["", ""], [1, 10])).toBeNull();
  });
  it("refuses another length, a blank, a repeat and an over-long label", () => {
    expect(labelProblem(["a", "b", "c"], [1, 10])).toMatch(/10 bodů/);
    expect(labelProblem(["a", "", "c", "d", "e"], [1, 5])).toMatch(/prázdný/);
    expect(labelProblem(["Ano", "ano"], [1, 10])).toMatch(/stejný/);
    expect(labelProblem(["x".repeat(SCALE_LABEL_MAX + 1), "y"], [1, 10])).toMatch(/60 znaků/);
  });
});

describe("the editor's range (3b2)", () => {
  it("reads only two whole ends within 0-100, low below high: never rounds or swaps one", () => {
    expect(readRange([1, 10])).toEqual([1, 10]);
    expect(readRange([0, 100])).toEqual([0, 100]);
    expect(readRange([2.5, 10])).toBeNull();
    expect(readRange([8, 3])).toBeNull();
    expect(readRange([5, 5])).toBeNull();
    expect(readRange([-1, 5])).toBeNull();
    expect(readRange([1, 101])).toBeNull();
    expect(readRange(["1", "10"])).toBeNull();
    expect(readRange(undefined)).toBeNull();
  });
  it("bounds each Vlastní end by the other", () => {
    expect(endBounds([1, 10])).toEqual({ low: { min: 0, max: 9 }, high: { min: 2, max: 100 } });
    expect(endBounds([0, 1])).toEqual({ low: { min: 0, max: 0 }, high: { min: 1, max: 100 } });
  });
});

describe("the editor's labels (3b2)", () => {
  it("draws every point only when every point is labelled", () => {
    expect(labelMode(five, [1, 5])).toBe("points");
    expect(labelMode(["a", "b"], [1, 5])).toBe("ends");
    expect(labelMode(["a", "b", "c"], [1, 10])).toBe("ends");
  });
  it("writes an end as exactly two ends, a point as itself", () => {
    expect(shownEnds(["a", "b", "c"])).toEqual(["a", "c"]);
    expect(withEnd(["a", "b", "c"], 1, "z")).toEqual(["a", "z"]);
    expect(withPoint(five, 2, "střed")).toEqual(["rozhodně ne", "spíše ne", "střed", "spíše ano", "rozhodně ano"]);
  });
  it("goes back to the two ends, counting the inner labels it clears", () => {
    expect(endsOnly(five, [1, 5])).toEqual({ labels: ["rozhodně ne", "rozhodně ano"], cleared: 3 });
    expect(endsOnly(["a", "", "c", "", "e"], [1, 5]).cleared).toBe(1);
    expect(endsOnly(["a", "b"], [1, 5])).toEqual({ labels: ["a", "b"], cleared: 0 });
  });
  it("finds a repeat as the server compares, case-folded, the point itself aside", () => {
    expect(repeatsAnother(five, 0, "Spíše NE")).toBe(true);
    expect(repeatsAnother(five, 1, "spíše ne")).toBe(false);
    expect(repeatsAnother(five, 1, "  ")).toBe(false);
  });
  it("counts what was cleared in Czech", () => {
    expect(clearedWords(1)).toBe("Odstraněn 1 popisek bodu");
    expect(clearedWords(3)).toBe("Odstraněny 3 popisky bodů");
    expect(clearedWords(8)).toBe("Odstraněno 8 popisků bodů");
  });
});
