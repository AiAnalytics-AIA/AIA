import { describe, expect, it } from "vitest";

import { diffLines, differs, summarise } from "./text-diff";

const kinds = (ops: ReturnType<typeof diffLines>) => ops.map((o) => `${o.kind}:${o.text}`);

describe("diffLines", () => {
  it("marks nothing for identical text", () => {
    expect(kinds(diffLines("a\nb", "a\nb"))).toEqual(["same:a", "same:b"]);
    expect(summarise(diffLines("a\nb", "a\nb"))).toEqual({ added: 0, removed: 0 });
  });

  it("shows an inserted, a removed and a changed line", () => {
    expect(kinds(diffLines("a\nb\nc", "a\nB\nc\nd"))).toEqual(["same:a", "del:b", "add:B", "same:c", "add:d"]);
    expect(summarise(diffLines("a\nb\nc", "a\nB\nc\nd"))).toEqual({ added: 2, removed: 1 });
  });

  it("keeps a common line in place when one is removed from the middle", () => {
    expect(kinds(diffLines("a\nb\nc", "a\nc"))).toEqual(["same:a", "del:b", "same:c"]);
  });

  it("treats a whole-text replacement as all removed then all added", () => {
    expect(kinds(diffLines("x\ny", "p\nq"))).toEqual(["del:x", "del:y", "add:p", "add:q"]);
  });

  it("does not see a change in line endings", () => {
    expect(kinds(diffLines("a\r\nb", "a\nb"))).toEqual(["same:a", "same:b"]);
    expect(differs("a\r\nb", "a\nb")).toBe(false);
    expect(differs("a", "a ")).toBe(true);
  });

  it("is exact, so rebuilding either side from the script gives the original", () => {
    const before = "Jsi výzkumný pracovník.\nPiš česky.\n\nNevymýšlej fakta.";
    const after = "Jsi výzkumný pracovník AIA.\n\nNevymýšlej fakta.\nCituj zdroje.";
    const ops = diffLines(before, after);
    expect(ops.filter((o) => o.kind !== "add").map((o) => o.text).join("\n")).toBe(before);
    expect(ops.filter((o) => o.kind !== "del").map((o) => o.text).join("\n")).toBe(after);
  });
});
