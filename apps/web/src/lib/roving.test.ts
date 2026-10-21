import { describe, expect, it } from "vitest";

import { rovingIndex, tabStop } from "./roving";

describe("arrow keys within one group (I11, roving tabindex)", () => {
  it("moves forward and back, wrapping at the ends", () => {
    expect(rovingIndex(0, "ArrowRight", 3)).toBe(1);
    expect(rovingIndex(0, "ArrowDown", 3)).toBe(1);
    expect(rovingIndex(2, "ArrowRight", 3)).toBe(0);
    expect(rovingIndex(0, "ArrowLeft", 3)).toBe(2);
    expect(rovingIndex(1, "ArrowUp", 3)).toBe(0);
  });

  it("goes to the first and last with Home and End", () => {
    expect(rovingIndex(1, "Home", 4)).toBe(0);
    expect(rovingIndex(1, "End", 4)).toBe(3);
    expect(rovingIndex(-1, "Home", 4, (i) => i === 0)).toBe(1);
    expect(rovingIndex(4, "End", 4, (i) => i === 3)).toBe(2);
  });

  it("skips disabled controls and gives up when none is enabled", () => {
    expect(rovingIndex(0, "ArrowRight", 4, (i) => i === 1 || i === 2)).toBe(3);
    expect(rovingIndex(0, "ArrowRight", 3, () => true)).toBeNull();
  });

  it("ignores other keys, and the cross axis when one is set", () => {
    expect(rovingIndex(0, "Enter", 3)).toBeNull();
    expect(rovingIndex(0, " ", 3)).toBeNull();
    expect(rovingIndex(0, "ArrowRight", 3, undefined, "vertical")).toBeNull();
    expect(rovingIndex(0, "ArrowDown", 3, undefined, "horizontal")).toBeNull();
    expect(rovingIndex(0, "ArrowDown", 0)).toBeNull();
  });

  it("gives Tab to the chosen control, else the first enabled one", () => {
    expect(tabStop(3, 2)).toBe(2);
    expect(tabStop(3, -1)).toBe(0);
    expect(tabStop(3, -1, (i) => i === 0)).toBe(1);
    expect(tabStop(3, 1, (i) => i === 1)).toBe(0);
    expect(tabStop(2, -1, () => true)).toBe(-1);
  });
});
