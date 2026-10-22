// The object map's browser code renders the frozen contract-3 artifact and computes no
// methodology (plan object-map-3d-redesign). Behaviour tests show what is drawn; this one
// guards the source itself: no kernel (exp), no Fisher transform (atanh, tanh, log), no
// correlation or distance root (sqrt), and no read of a terrain parameter that a kernel would
// need. Drawing maths (cos, sin, hypot for lighting and label distance, pow for easing) stays.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = join(__dirname, "..");
const FILES = [
  "lib/object-map-view.ts",
  "lib/object-map-3d.ts",
  "components/rehome/research/ObjectMapView.tsx",
  "components/rehome/research/ObjectMapTerrain.tsx",
  "components/rehome/research/ObjectMapMarks.tsx",
  "components/rehome/research/ObjectMapPanel.tsx",
  "components/rehome/research/ObjectMapWindows.tsx",
];

/** The source without comments, so a comment that names a formula does not trip the guard. */
const code = (file: string) => readFileSync(join(root, file), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");

describe("the object map's browser code computes no methodology", () => {
  for (const file of FILES) {
    it(`${file}: no kernel, Fisher or correlation maths`, () => {
      const source = code(file);
      expect(source).not.toMatch(/Math\.(exp|expm1|log|log1p|log2|log10|atanh|tanh|sqrt|cbrt)\b/);
      expect(source).not.toMatch(/\bsmacof|\bpearson|\bfisher|\bkish/i);
    });

    it(`${file}: reads no terrain parameter a kernel would need`, () => {
      const source = code(file);
      expect(source).not.toMatch(/parameters\.(sigma|kernel_cutoff)|\.kernel_cutoff\b/);
      // The one sigma read is the provisional notice printing the pinned value.
      const sigma = source.match(/\.sigma\b/g) ?? [];
      expect(sigma.length).toBe(file.endsWith("ObjectMapView.tsx") ? 1 : 0);
    });
  }
});

// The signed-off map's port of the AIA panel's drawing (plan sociomap-5-web, chunks 2 and 3) evaluates
// no kernel and reads no kernel width: the engine stores both its surfaces (Relativni and Absolutni).
// It may take a square root twice, both the panel's display: the node size for large sets (`nodeScale`)
// and the RMS distance of the drawn objects, the screen unit of the stored uncertainty radius
// (`rmsDistance`, as `drawAiaOverlay66`). Everything else stays out, as above.
describe("the panel port computes only the panel's display", () => {
  const source = code("lib/object-map-panel.ts");
  /** The body of one top-level function: from its declaration to the next top-level one. */
  const body = (name: string) => {
    const start = source.search(new RegExp(`^(export )?function ${name}\\(`, "m"));
    if (start < 0) throw new Error(`no top-level function ${name} in lib/object-map-panel.ts`);
    const next = source.slice(start + 1).search(/\n(export )?(function|const|type) /);
    return source.slice(start, next < 0 ? undefined : start + 1 + next);
  };

  it("evaluates no kernel, and takes a square root only for the node size and the drawn RMS distance", () => {
    expect(source).not.toMatch(/Math\.(exp|expm1|log|log1p|log2|log10|atanh|tanh|cbrt)\b/);
    expect(source.match(/Math\.sqrt\b/g)).toHaveLength(2);
    expect(body("nodeScale")).toMatch(/Math\.sqrt\b/);
    expect(body("rmsDistance")).toMatch(/Math\.sqrt\b/);
    expect(source).not.toMatch(/\bsmacof|\bpearson|\bfisher|\bkish/i);
  });

  it("reads no kernel width", () => {
    expect(source).not.toMatch(/\.sigma\b|kernel_cutoff/);
  });
});
