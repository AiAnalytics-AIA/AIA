// A file given to the Lead from its composer, the pure part (lead-orchestration LO18a).
import { describe, expect, it } from "vitest";

import { FILE_MAX_BYTES } from "./client-sources";
import { carried, holdsMessage, kept, refused, refusedBeforeUpload, room, uploading } from "./lead-files";

const file = (over: Partial<Parameters<typeof kept>[1]> = {}) => ({
  source_id: "SRC-0000000000000001", filename: "Zadání.pdf", family: "DOCUMENT" as const, outcome: "READ" as const,
  reason: null, segments: 2, characters: 120, ...over,
});

describe("lead files", () => {
  it("carries only the files kept, in the order chosen, and holds the message while one is kept", () => {
    const a = [kept("a", file()), refused("b", "a.exe", "unsupported_format"), uploading("c", "x.md")];
    expect(carried(a)).toEqual(["SRC-0000000000000001"]);
    expect(holdsMessage(a)).toBe(true);
    expect(holdsMessage(a.slice(0, 2))).toBe(false);
  });

  it("counts a refused file out of the three a message takes", () => {
    expect(room([kept("a", file()), refused("b", "a.exe", "unsupported_format")])).toBe(2);
    expect(room([uploading("a", "1"), uploading("b", "2"), uploading("c", "3"), uploading("d", "4")])).toBe(0);
  });

  it("says a dataset reaches the Lead as its columns only", () => {
    expect(kept("a", file({ family: "DATASET", filename: "data.csv" })).words).toMatch(/jen přehled sloupců$/);
    expect(kept("a", file()).words).not.toMatch(/sloupců/);
  });

  it("refuses an empty or oversized file before it is sent", () => {
    expect(refusedBeforeUpload({ size: 0 })).toBe("empty");
    expect(refusedBeforeUpload({ size: FILE_MAX_BYTES + 1 })).toBe("too_large");
    expect(refusedBeforeUpload({ size: FILE_MAX_BYTES })).toBeNull();
  });
});
