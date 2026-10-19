// The workbench split's rules (research-lead-workbench chunk 1): the prototype's bounds, focus
// modes that never change the person's width, and a browser that keeps nothing.
import { describe, expect, it } from "vitest";

import {
  CONVERSATION_FOCUS,
  SPLIT_DEFAULT,
  SPLIT_MAX,
  SPLIT_MIN,
  SPLIT_STORAGE_KEY,
  clampSplit,
  leftWidth,
  readSplit,
  splitFromKey,
  splitFromPointer,
  writeSplit,
} from "./workbench-split";

describe("clampSplit", () => {
  it("keeps the left pane between 28 and 62 %", () => {
    expect(SPLIT_MIN).toBe(28);
    expect(SPLIT_MAX).toBe(62);
    expect(clampSplit(10)).toBe(28);
    expect(clampSplit(90)).toBe(62);
    expect(clampSplit(45.5)).toBe(45.5);
  });

  it("reads a value that is not a number as the default, never as a bound", () => {
    expect(clampSplit(Number.NaN)).toBe(SPLIT_DEFAULT);
    expect(clampSplit(Number.POSITIVE_INFINITY)).toBe(SPLIT_DEFAULT);
  });
});

describe("splitFromPointer", () => {
  const box = { left: 100, width: 1000 };

  it("sets the width where the pointer is, to a tenth of a per cent", () => {
    expect(splitFromPointer(550, box, 40)).toBe(45);
    expect(splitFromPointer(553.37, box, 40)).toBe(45.3);
  });

  it("stops at the bounds", () => {
    expect(splitFromPointer(120, box, 40)).toBe(28);
    expect(splitFromPointer(1090, box, 40)).toBe(62);
  });

  it("moves nothing in a box with no width", () => {
    expect(splitFromPointer(550, { left: 0, width: 0 }, 43)).toBe(43);
  });
});

describe("splitFromKey", () => {
  it("moves 2 % per arrow, within the bounds", () => {
    expect(splitFromKey(40, "ArrowLeft")).toBe(38);
    expect(splitFromKey(40, "ArrowRight")).toBe(42);
    expect(splitFromKey(29, "ArrowLeft")).toBe(28);
    expect(splitFromKey(61, "ArrowRight")).toBe(62);
  });

  it("goes back to 40 % on Home and Enter", () => {
    expect(splitFromKey(55, "Home")).toBe(40);
    expect(splitFromKey(30, "Enter")).toBe(40);
  });

  it("leaves every other key to the page", () => {
    expect(splitFromKey(40, "ArrowUp")).toBeNull();
    expect(splitFromKey(40, "Tab")).toBeNull();
  });
});

describe("leftWidth", () => {
  it("is the person's width in the split, a rail with the artifact in focus, 68 % with the conversation", () => {
    expect(leftWidth(46, "split")).toBe(46);
    expect(leftWidth(46, "artifact")).toBeNull();
    expect(leftWidth(46, "conversation")).toBe(CONVERSATION_FOCUS);
    expect(CONVERSATION_FOCUS).toBe(68);
  });

  it("returns to the person's width when the focus ends", () => {
    const split = 52;
    leftWidth(split, "conversation");
    expect(leftWidth(split, "split")).toBe(52);
  });
});

describe("readSplit / writeSplit", () => {
  const memory = () => {
    const kept = new Map<string, string>();
    return { getItem: (k: string) => kept.get(k) ?? null, setItem: (k: string, v: string) => void kept.set(k, v), kept };
  };

  it("keeps the width per browser, within the bounds", () => {
    const s = memory();
    writeSplit(s, 47);
    expect(s.kept.get(SPLIT_STORAGE_KEY)).toBe("47");
    expect(readSplit(s)).toBe(47);
    writeSplit(s, 80);
    expect(readSplit(s)).toBe(62);
  });

  it("starts at the default with nothing kept, no storage, or a value out of shape", () => {
    expect(readSplit(memory())).toBe(SPLIT_DEFAULT);
    expect(readSplit(null)).toBe(SPLIT_DEFAULT);
    const s = memory();
    s.setItem(SPLIT_STORAGE_KEY, "wide");
    expect(readSplit(s)).toBe(SPLIT_DEFAULT);
    s.setItem(SPLIT_STORAGE_KEY, " ");
    expect(readSplit(s)).toBe(SPLIT_DEFAULT);
  });

  it("breaks nothing when the browser refuses its storage", () => {
    const refusing = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    };
    expect(readSplit(refusing)).toBe(SPLIT_DEFAULT);
    expect(() => writeSplit(refusing, 50)).not.toThrow();
  });
});
