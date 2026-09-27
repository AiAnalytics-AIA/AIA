// The inline mark against its source file, public/skin/brand/aia-mark.svg: the
// same 25 points, radii, faint opacity and apex, or the identity has drifted.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { MARK_POINTS } from "./AiaMark";

const svg = readFileSync(join(__dirname, "../../../public/skin/brand/aia-mark.svg"), "utf8");
const fromFile = [...svg.matchAll(/<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)" fill="(#[0-9a-f]+)"( fill-opacity="([\d.]+)")?\/>/g)].map(
  (m) => ({ cx: Number(m[1]), cy: Number(m[2]), r: Number(m[3]), apex: m[4] === "#006b9f", faint: m[6] === "0.35" }),
);

describe("AiaMark", () => {
  it("draws exactly the points of aia-mark.svg", () => {
    expect(fromFile).toHaveLength(25);
    expect(MARK_POINTS).toEqual(fromFile);
  });

  it("has one apex, in the signal colour", () => {
    expect(fromFile.filter((p) => p.apex)).toHaveLength(1);
    expect(MARK_POINTS.filter((p) => p.apex)).toEqual(fromFile.filter((p) => p.apex));
  });
});
