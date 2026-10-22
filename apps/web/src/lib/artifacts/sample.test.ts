import { readFileSync } from "node:fs";
import { join } from "node:path";

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
  ].map((id) => id!);

  // The contract's id grammar for Vzorek (packages/aia_core/tests/fixtures/lead_artifacts/contract.json),
  // e.g. "n|size|quota:<cell>|…": a literal alternative, or a prefix with a placeholder after it.
  const FILE = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/lead_artifacts/contract.json"), "utf8")) as {
    targets: { kind: string; id: string }[];
  };
  const grammar = FILE.targets.find((t) => t.kind === "sample")!.id.split("|");
  const inContract = (aia: string) => {
    const id = aia.slice("sample:".length);
    return grammar.some((alt) => (alt.includes("<") ? id.startsWith(alt.slice(0, alt.indexOf("<"))) && id.length > alt.indexOf("<") : id === alt));
  };
  it("names only ids the contract's grammar for Vzorek has, each read back to its stage", () => {
    expect(ARTIFACTS.sample.targets).toContain("sample");
    for (const id of every) {
      expect(parseAiaId(id)).toMatchObject({ kind: "sample", stage: "sample" });
      expect([id, inContract(id)]).toEqual([id, true]);
    }
    expect(inContract("sample:anything")).toBe(false);
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

  it("names no element for a server's name outside the grammar, never throwing during a render", () => {
    // domain/research_design.py names a question's compile problem `compile:<code>:<section>#<n>`.
    expect(sampleAia.ready("compile:question_without_text:S1#1")).toBeNull();
    expect(sampleAia.ready("compile:empty_questionnaire:sections")).toBe("sample:ready:compile:empty_questionnaire:sections");
    expect(sampleAia.ready("x".repeat(80))).toBeNull();
    expect(sampleAia.respondents("a b")).toBeNull();
    expect(sampleAia.quota("a b")).toBeNull();
  });
});
