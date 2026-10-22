import { describe, expect, it } from "vitest";
import { layerLines, layerName, moreOmitted, totalLine, type ManifestLayer } from "./lead-manifest";

const layer = (over: Partial<ManifestLayer>): ManifestLayer => ({
  layer: "knowledge", recorded: true, bytes: 3000, ceiling_bytes: 20480, bounded_bytes: 2048, included: ["K-1"], included_count: 1, omitted: [], omitted_count: 0, ...over,
});

describe("lead manifest in words", () => {
  it("says an unrecorded layer is unrecorded, never empty or zero", () => {
    const lines = layerLines(layer({ recorded: false, bytes: null, included_count: null, omitted_count: null }));
    expect(lines).toEqual(["Nezaznamenáno: tato odpověď vrstvu neměla."]);
  });

  it("reads a layer's bounded part against its bound and counts its items in Czech", () => {
    expect(layerLines(layer({ included_count: 3, omitted_count: 2 }))).toEqual(["2 kB z 20 kB", "Viděl 3 znalosti", "Vynecháno: 2"]);
    expect(layerLines(layer({ layer: "lead", included_count: 5 }))[1]).toBe("Viděl 5 poznámek");
    expect(layerLines(layer({ layer: "conversation", bounded_bytes: null, ceiling_bytes: null, bytes: 1024, included_count: 0, omitted_count: 4 })))
      .toEqual(["1 kB", "Starší tahy vynechány: 4"]);
  });

  it("pages left-out ids only where the layer named more than it lists", () => {
    expect(moreOmitted(layer({ omitted_count: 57 }), 50)).toBe(true);
    expect(moreOmitted(layer({ omitted_count: 50 }), 50)).toBe(false);
    expect(moreOmitted(layer({ layer: "conversation", omitted_count: 9 }), 0)).toBe(false);
  });

  it("names every layer, and the whole against its bound", () => {
    expect(layerName("memory")).toBe("Co jste spolu rozhodli");
    expect(totalLine({ turn_id: "LDT-1", recorded: true, manifest: { manifest_version: 1, total_bytes: 41_200, ceiling_bytes: 98_304, layers: [] } })).toBe("Celkem 40,2 kB z 96 kB");
    expect(totalLine({ turn_id: "LDT-1", recorded: false, manifest: null })).toBeNull();
  });
});
