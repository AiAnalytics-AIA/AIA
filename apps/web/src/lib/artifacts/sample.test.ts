import { describe, expect, it } from "vitest";

import { ARTIFACTS, parseAiaId } from "../workbench-artifacts";
import { FORECAST_ITEMS, SAMPLE_SECTIONS, sampleAia } from "./sample";

describe("sampleAia", () => {
  const every = [
    ...SAMPLE_SECTIONS.map(sampleAia.section),
    sampleAia.n(),
    sampleAia.quota("muz_18-29_praha"),
    ...FORECAST_ITEMS.map(sampleAia.forecast),
    sampleAia.ready("support_forecast"),
    sampleAia.respondents("fictional_roster"),
  ];

  it("names only targets the contract gives Vzorek, each read back to its stage", () => {
    expect(ARTIFACTS.sample.targets).toContain("sample");
    for (const id of every) expect(parseAiaId(id)).toMatchObject({ kind: "sample", stage: "sample" });
  });

  it("keeps V2's section order: size, forecast, readiness, who answers", () => {
    expect(SAMPLE_SECTIONS).toEqual(["size", "forecast", "ready", "respondents"]);
  });

  it("spells the plan's grammar (artifact-sample §4)", () => {
    expect(sampleAia.n()).toBe("sample:n");
    expect(sampleAia.quota("a")).toBe("sample:quota:a");
    expect(sampleAia.forecast("support")).toBe("sample:forecast:support");
    expect(sampleAia.ready("sample_size")).toBe("sample:ready:sample_size");
  });

  it("refuses an id outside the grammar rather than send it", () => {
    expect(() => sampleAia.ready("a b")).toThrow();
  });
});
