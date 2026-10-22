// The Lead's per-artifact contract, held to the fixture domain/lead_artifacts.py is held to
// (packages/aia_core/tests/fixtures/lead_artifacts/contract.json), so the two sides cannot drift.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { ACTION_LABELS } from "./research-agent-jobs";
import { STAGE_ORDER } from "./workbench-stages";
import {
  ARTIFACTS, LIVE_TARGETS, LIVE_VIEW_OPS, TARGET_STAGE, VIEW_FILTERS, aiaId, allowsView, parseAiaId, tryAiaId,
} from "./workbench-artifacts";

const FILE = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/lead_artifacts/contract.json"), "utf8")) as {
  fields: string[];
  id_pattern: string;
  view_ops: { op: string; live: boolean }[];
  filters: Record<string, string[]>;
  targets: { kind: string; stage: string; live: boolean }[];
  artifacts: Record<string, unknown>[];
};

describe("the per-artifact contract", () => {
  it("is the fixture's, row for row and in stage order", () => {
    expect(Object.keys(ARTIFACTS)).toEqual([...STAGE_ORDER]);
    expect(Object.values(ARTIFACTS).map((a) => Object.keys(a))).toEqual(STAGE_ORDER.map(() => FILE.fields));
    expect(JSON.parse(JSON.stringify(Object.values(ARTIFACTS)))).toEqual(FILE.artifacts);
  });

  it("has the fixture's vocabularies and says which parts are live", () => {
    expect([...LIVE_VIEW_OPS].sort()).toEqual(FILE.view_ops.filter((v) => v.live).map((v) => v.op).sort());
    expect([...LIVE_TARGETS].sort()).toEqual(FILE.targets.filter((t) => t.live).map((t) => t.kind).sort());
    expect(TARGET_STAGE).toEqual(Object.fromEntries(FILE.targets.map((t) => [t.kind, t.stage])));
    expect(VIEW_FILTERS).toEqual(FILE.filters);
  });

  it("starts only workers the cards know", () => {
    const actions = new Set(Object.keys(ACTION_LABELS));
    for (const a of Object.values(ARTIFACTS))
      for (const s of a.starts) if (s.startsWith("agent_job:")) expect(actions.has(s.slice(10))).toBe(true);
  });

  it("allows only the stage's own view operations", () => {
    expect(allowsView("sociomap", "filter")).toBe(true);
    expect(allowsView("questionnaire", "filter")).toBe(false);
    expect(STAGE_ORDER.every((s) => allowsView(s, "open_stage") && allowsView(s, "focus"))).toBe(true);
  });
});

describe("aiaId / parseAiaId", () => {
  it("builds ids of the one grammar the fixture publishes, the server's", async () => {
    const { ID_SOURCE } = await import("./workbench-artifacts");
    expect(ID_SOURCE).toBe(`^${FILE.id_pattern}$`);
  });

  it("round-trips a target and names its stage", () => {
    expect(aiaId("pair", "fio~air")).toBe("pair:fio~air");
    expect(parseAiaId("pair:fio~air")).toEqual({ kind: "pair", id: "fio~air", stage: "sociomap" });
    expect(parseAiaId(aiaId("question", "q3"))).toEqual({ kind: "question", id: "q3", stage: "questionnaire" });
    expect(parseAiaId(aiaId("finding", "executive:2"))).toEqual({ kind: "finding", id: "executive:2", stage: "analysis" });
    expect(parseAiaId(aiaId("pair", "set1/fio~air"))?.stage).toBe("sociomap");
    expect(parseAiaId(aiaId("step", "analysis/executive"))).toEqual({ kind: "step", id: "analysis/executive", stage: "fieldwork" });
  });

  it("refuses what the grammar does not name", () => {
    expect(() => aiaId("measure", "a b")).toThrow(/not an identifier/);
    expect(parseAiaId("nonsense:q3")).toBeNull();
    expect(parseAiaId("question:")).toBeNull();
    expect(parseAiaId("q3")).toBeNull();
  });

  it("tryAiaId marks an identifier and leaves anything else unmarked, never throwing", () => {
    expect(tryAiaId("dimension", "eko")).toBe("dimension:eko");
    expect(tryAiaId("dimension", "eko a zdraví")).toBeNull();
    expect(tryAiaId("dimension", "")).toBeNull();
    expect(tryAiaId("finding", "executive:2")).toBe(aiaId("finding", "executive:2"));
  });

  it("lets the Lead show its changes on Dimenze, where its edits land", () => {
    expect(allowsView("dimensions", "show_diff")).toBe(true);
    expect(ARTIFACTS.dimensions.edits).toBe(true);
  });
});
