import { describe, expect, it } from "vitest";
import { ARTIFACTS } from "../workbench-artifacts";
import { AUDIENCE_PARTS, AUDIENCE_VIEW_OPS, parseAudienceId, audienceFilterAia, audiencePartAia, audienceSubpanelAia, audienceTarget, audienceTargets, storedFilterFactors } from "./audience";
import type { ResearchProject } from "@/research/model";

const project = (filters: unknown) => ({ audience: { filters } }) as unknown as ResearchProject;
const SUBPANELS = ["young_18_29", "students"];

describe("Cílová skupina's contract", () => {
  it("takes its view operations and target kind from the registry's row", () => {
    expect(AUDIENCE_VIEW_OPS).toBe(ARTIFACTS.audience.view_ops);
    expect(ARTIFACTS.audience.targets).toEqual(["audience"]);
  });

  it("marks the parts, a filter and a subpanel in the registry's grammar", () => {
    expect(AUDIENCE_PARTS.map(audiencePartAia)).toEqual(["audience:definition", "audience:filters", "audience:preview"]);
    expect(audienceFilterAia("kraj")).toBe("audience:filter:kraj");
    expect(audienceSubpanelAia("young_18_29")).toBe("audience:subpanel:young_18_29");
  });

  it("leaves an id outside the grammar unmarked instead of breaking the screen", () => {
    expect(audienceFilterAia("věk")).toBeNull();
    expect(audienceFilterAia("a b")).toBeNull();
    expect(audienceFilterAia("")).toBeNull();
    expect(audienceSubpanelAia("x".repeat(80))).toBeNull(); // with its prefix, past the grammar's 80
  });

  it("reads a part, a stored filter and an offered subpanel", () => {
    const p = project({ kraj: ["Zlínský kraj"], vek: { min: 30 } });
    expect(audienceTarget("audience:definition", p, SUBPANELS)).toEqual({ kind: "part", part: "definition" });
    expect(audienceTarget("audience:filter:vek", p, SUBPANELS)).toEqual({ kind: "filter", factor: "vek" });
    expect(audienceTarget("audience:subpanel:students", p, SUBPANELS)).toEqual({ kind: "subpanel", key: "students" });
  });

  it("reads an id without the study, for a label", () => {
    expect(parseAudienceId("audience:preview")).toEqual({ kind: "part", part: "preview" });
    expect(parseAudienceId("audience:filter:prijem")).toEqual({ kind: "filter", factor: "prijem" }); // stored or not
    expect(parseAudienceId("audience:subpanel:seniors")).toEqual({ kind: "subpanel", key: "seniors" });
    for (const t of ["audience:filter:", "audience:subpanel:", "audience:kraj", "question:q1", "audience"]) expect(parseAudienceId(t), t).toBeNull();
  });

  it("refuses a target it does not name, never mapping it to something near", () => {
    const p = project({ kraj: ["Zlínský kraj"] });
    expect(audienceTarget("audience:filter:prijem", p, SUBPANELS)).toBeNull(); // no stored filter, no element
    expect(audienceTarget("audience:filter:", p, SUBPANELS)).toBeNull();
    expect(audienceTarget("audience:kraj", p, SUBPANELS)).toBeNull(); // the draft's form, before the plan
    expect(audienceTarget("audience:subpanel:seniors", p, SUBPANELS)).toBeNull();
    expect(audienceTarget("audience:assumption:A1", p, SUBPANELS)).toBeNull();
    expect(audienceTarget("question:q1", p, SUBPANELS)).toBeNull();
    expect(audienceTarget("Cílová skupina", p, SUBPANELS)).toBeNull();
  });

  it("lists what the screen draws: the parts, each stored filter, the preview and subpanels when drawn", () => {
    const p = project({ kraj: ["Zlínský kraj"], "věk": { min: 30 }, vek: { min: 30 } });
    expect(storedFilterFactors(p)).toEqual(["kraj", "věk", "vek"]);
    expect(audienceTargets(p, { preview: true, subpanels: SUBPANELS })).toEqual([
      "audience:definition", "audience:filters", "audience:preview",
      "audience:filter:kraj", "audience:filter:vek",
      "audience:subpanel:young_18_29", "audience:subpanel:students",
    ]);
    // Without the population's catalogue: no preview, and no subpanel outside their view.
    expect(audienceTargets(project(undefined), { preview: false, subpanels: [] })).toEqual(["audience:definition", "audience:filters"]);
  });

  it("reads stored filters as the screen's chips read them, so the two never disagree", () => {
    expect(storedFilterFactors(project(["kraj"]))).toEqual(["0"]); // the chip the screen draws for it
    expect(audienceTarget("audience:filter:0", project(["kraj"]), SUBPANELS)).toEqual({ kind: "filter", factor: "0" });
  });
});
