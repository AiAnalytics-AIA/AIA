import { describe, expect, it } from "vitest";

import { ShapeError, filterOptions, parseDashboardCounts, parseProjectRow, parseProjectRows } from "./projects";

describe("parseProjectRow", () => {
  it("keeps the fields the screen reads, typed", () => {
    const row = parseProjectRow({
      project_id: "PRJ-1", title: "Alfa", progress_pct: 40, is_demo: false, tags: ["a", 3, "b"],
      job_summary: { running: 1, failed: "x" }, unexpected: { deep: true },
    });
    expect(row).toEqual({ project_id: "PRJ-1", title: "Alfa", progress_pct: 40, is_demo: false, tags: ["a", "b"], job_summary: { running: 1 } });
  });

  it("drops a field of the wrong type rather than coercing it", () => {
    expect(parseProjectRow({ project_id: "PRJ-1", progress_pct: "40", pinned: "yes", title: 7 })).toEqual({ project_id: "PRJ-1" });
  });

  it("refuses a row without an id", () => {
    expect(() => parseProjectRow({ title: "x" })).toThrow(ShapeError);
    expect(() => parseProjectRows({})).toThrow(ShapeError);
  });
});

describe("parseDashboardCounts", () => {
  it("reads the counts and nothing else", () => {
    expect(parseDashboardCounts({ counts: { all: 3, demo: 30, bad: "x" }, demos: [] })).toEqual({ all: 3, demo: 30 });
    expect(() => parseDashboardCounts({ demos: [] })).toThrow(ShapeError);
  });
});

describe("filterOptions", () => {
  it("offers only what non-DEMO rows carry, sorted", () => {
    const rows = [
      { project_id: "a", status: "DRAFT", current_stage: "BRIEF", preferred_provider: "anthropic" },
      { project_id: "b", status: "COMPLETED", current_stage: "BRIEF" },
      { project_id: "c", status: "ZZZ", is_demo: true, preferred_provider: "x" },
    ];
    expect(filterOptions(rows)).toEqual({ statuses: ["COMPLETED", "DRAFT"], providers: ["anthropic"], stages: ["BRIEF"] });
  });
});
