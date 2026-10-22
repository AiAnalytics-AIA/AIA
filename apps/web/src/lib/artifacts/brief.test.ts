import { describe, expect, it } from "vitest";
import { ARTIFACTS } from "../workbench-artifacts";
import { BRIEF_FIELDS, BRIEF_VIEW_OPS, briefElementId, briefTarget, briefTargets, contextField } from "./brief";
import type { ResearchProject } from "@/research/model";

const project = (attachments: unknown[]) => ({ briefing: { attachments } }) as unknown as ResearchProject;

describe("the Brief's contract", () => {
  it("takes its view operations and target kinds from the registry's row", () => {
    expect(BRIEF_VIEW_OPS).toBe(ARTIFACTS.brief.view_ops);
    expect(ARTIFACTS.brief.targets).toEqual(expect.arrayContaining(["brief", "material"]));
  });

  it("names a field as the Lead's edits do", () => {
    expect(contextField("situation")).toBe("briefing.situation");
    expect(contextField("decision_use")).toBe("decision_use");
    expect(briefElementId("briefing.situation")).toBe("brief-briefing.situation");
    for (const f of BRIEF_FIELDS) expect(briefTarget(`brief:${f}`)).toEqual({ kind: "brief", field: f });
  });

  it("refuses a target it does not name, never mapping it to something near", () => {
    expect(briefTarget("brief:situation")).toBeNull();
    expect(briefTarget("brief:nonsense")).toBeNull();
    expect(briefTarget("brief:")).toBeNull();
    expect(briefTarget("question:q1")).toBeNull();
    expect(briefTarget("material:a b")).toBeNull();
    expect(briefTarget("Zadání")).toBeNull();
  });

  it("reads a material, and lists every field and each file kept in AIA once", () => {
    expect(briefTarget("material:ART-01")).toEqual({ kind: "material", id: "ART-01" });
    const targets = briefTargets(
      project([
        { kind: "file", attachment_id: "ART-0a" },
        { kind: "url", url: "https://example.org/a" },
        { kind: "file", attachment_id: "ATT-legacy" },
        { kind: "file", attachment_id: "ART-0a" },
      ]),
    );
    expect(targets).toEqual([...BRIEF_FIELDS.map((f) => `brief:${f}`), "material:ART-0a"]);
    expect(briefTargets({} as ResearchProject)).toHaveLength(BRIEF_FIELDS.length);
  });
});
