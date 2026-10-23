// @vitest-environment jsdom
// What the Sociomapa stage says under a map (artifact-sociomap SOC10): only what the stored map says.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import signedOff from "@/lib/fixtures/object-map-signed-off.json";
import { explainMap } from "@/lib/map-explained";
import type { BatteryWithMaps } from "@/lib/object-map-view";
import { MapExplained } from "./MapExplained";

const [hudba] = signedOff.batteries as unknown as BatteryWithMaps[];
const map = hudba.maps!["aia-sociomap-5"].artifact;
const tech = { methodId: "aia-sociomap-5", fingerprint: "f", estimator: null, layout: null, terrain: null, run: "RUN-1", revision: 1, artifact: "ART-1", sha256: "s" };
const halves = () => screen.getByText("Shoda dvou polovin respondentů").closest("[data-gauge]")!.textContent!;

afterEach(cleanup);

describe("how reliable the map is, in words", () => {
  it("says the two halves agree as stored", () => {
    render(<MapExplained x={explainMap(hudba, map)} approved={false} tech={tech} />);
    expect(halves()).toContain("78 %");
  });

  // engine_v2's credibility: no split-half score is not "no reliable pair" unless the map is weakly
  // determined by that rule.
  it("names no missing reliable pair when the halves could not be compared on a map that has some", () => {
    const stored = structuredClone(map);
    stored.credibility = { rule: "no_reliable_pair", split_half: null, threshold: 0.59, weakly_determined: false, reliable_pairs: 3, uncertainty_radius: null };
    render(<MapExplained x={explainMap(hudba, stored)} approved={false} tech={tech} />);
    expect(halves()).not.toContain("nemá spolehlivý pár");
    expect(halves()).toContain("Shodu dvou polovin respondentů nešlo změřit.");
  });

  it("says the map has no reliable pair when it is weakly determined by that rule", () => {
    const stored = structuredClone(map);
    stored.credibility = { rule: "no_reliable_pair", split_half: null, threshold: 0.59, weakly_determined: true, reliable_pairs: 0, uncertainty_radius: null };
    render(<MapExplained x={explainMap(hudba, stored)} approved={false} tech={tech} />);
    expect(halves()).toContain("Shodu nelze změřit: mapa nemá spolehlivý pár.");
  });
});
