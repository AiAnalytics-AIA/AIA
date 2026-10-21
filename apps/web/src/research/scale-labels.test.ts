import { describe, expect, it } from "vitest";
import { describeEveryPoint, labelProblem, presetOf, rescaleLabels, SCALE_LABEL_MAX } from "./scale-labels";

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
