// The experimental Sociomapping's view logic, against the fixture the real builder wrote
// (tools/sociomapping_web_fixture.py). Nothing here computes a methodological number.
import { describe, expect, it } from "vitest";

import fixture from "./fixtures/sociomapping.json";
import {
  DEFAULT_3D,
  TOP_VIEW,
  VIEW,
  clampCamera,
  heightBand,
  labelOffsets,
  limitationText,
  mapPoints,
  num,
  objectsWord,
  project,
  readResult,
  relationsOf,
} from "./sociomapping-view";

const read = readResult(fixture);
if (!read.ok) throw new Error("fixture unreadable");
const battery = read.result.batteries[0];

describe("reading the stored result", () => {
  it("accepts only the known version, marked experimental and not client-facing", () => {
    expect(read.result.method.name).toBe("aia_hmodel_candidate_v1");
    expect(readResult(null)).toEqual({ ok: false, reason: "missing" });
    expect(readResult({ sociomapping: { ...fixture.sociomapping, sociomapping_version: "x" } })).toEqual({ ok: false, reason: "version" });
    expect(readResult({ sociomapping: { ...fixture.sociomapping, client_facing: true } })).toEqual({ ok: false, reason: "status" });
    expect(readResult({ sociomapping: { ...fixture.sociomapping, method_status: "CLIENT_FACING" } })).toEqual({ ok: false, reason: "status" });
  });

  it("draws placed objects at their stored positions and heights, and only those", () => {
    const points = mapPoints(battery);
    expect(points.map((p) => p.id)).toEqual(battery.layout!.element_ids);
    expect(points.map((p) => p.id)).not.toContain("echo"); // constant: unplaced, not drawn
    for (const [k, p] of points.entries()) {
      expect([p.x, p.y]).toEqual(battery.layout!.positions[k]);
      const i = battery.objects.findIndex((o) => o.id === p.id);
      expect(p.height).toBe(battery.heights!.on_scale[i]);
      expect(p.fit).toBe(battery.layout!.accuracy.per_point[k]);
    }
  });

  it("keeps negative and undefined relations as stored", () => {
    const delta = relationsOf(battery, "delta");
    expect(delta.find((r) => r.id === "altair")!.r).toBeLessThan(0);
    const echo = delta.find((r) => r.id === "echo")!;
    expect(echo.r).toBeNull();
    expect(echo.why).toBe("every answer equal for echo");
  });
});

describe("the camera", () => {
  it("shows the stored layout itself from above, y up", () => {
    const a = project(0.2, 0.3, 1, TOP_VIEW);
    expect(a.sx).toBeCloseTo(VIEW.cx + VIEW.scale * (0.2 - 0.5));
    expect(a.sy).toBeCloseTo(VIEW.cy - VIEW.scale * (0.3 - 0.5));
    expect(project(0.2, 0.3, 0, TOP_VIEW)).toEqual(a); // height does not move a point seen from above
  });

  it("raises higher objects when tilted and orders far before near", () => {
    const low = project(0.5, 0.5, 0, DEFAULT_3D);
    const high = project(0.5, 0.5, 1, DEFAULT_3D);
    expect(high.sy).toBeLessThan(low.sy);
    expect(project(0.5, 0.9, 0, { yaw: 0, pitch: 0.9, zoom: 1 }).depth).toBeGreaterThan(project(0.5, 0.1, 0, { yaw: 0, pitch: 0.9, zoom: 1 }).depth);
  });

  it("keeps rotation, tilt and zoom within bounds", () => {
    expect(clampCamera({ yaw: -Math.PI / 2, pitch: 5, zoom: 9 })).toEqual({ yaw: 1.5 * Math.PI, pitch: 1.35, zoom: 2.5 });
    expect(clampCamera({ yaw: 0, pitch: -1, zoom: 0.1 }).pitch).toBe(0);
  });
});

describe("words and numbers", () => {
  it("bands heights on the set's scale and says undefined rather than zero", () => {
    expect(heightBand(1, 1, 10)).toBe(0);
    expect(heightBand(10, 1, 10)).toBe(6);
    expect(num(null)).toBe("nedefinováno");
    expect(num(0.8594)).toBe("0,859");
  });

  it("names the open question behind each limitation", () => {
    const text = battery.limitations.map(limitationText);
    expect(text.some((t) => t.includes("experimentální H-Model AIA") && t.includes("M2"))).toBe(true);
    expect(text.some((t) => t.includes("záporně") && t.includes("M12"))).toBe(true);
  });
});

describe("labels", () => {
  it("never stack two labels on one line and leave a lone label where it was", () => {
    const offsets = labelOffsets([
      { id: "a", sx: 100, sy: 100 },
      { id: "b", sx: 120, sy: 104 },
      { id: "c", sx: 400, sy: 102 },
    ]);
    expect(offsets.get("a")).toBe(-8);
    expect(offsets.get("c")).toBe(-8); // far away horizontally: no conflict
    expect(104 + offsets.get("b")!).toBeGreaterThanOrEqual(100 - 8 + 15);
  });

  it("agrees the count with its noun", () => {
    expect([1, 3, 4, 5, 22].map(objectsWord)).toEqual(["1 objekt", "3 objekty", "4 objekty", "5 objektů", "22 objektů"]);
  });
});
