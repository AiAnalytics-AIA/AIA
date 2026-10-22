import { describe, expect, it } from "vitest";

import { parseAiaId } from "../workbench-artifacts";
import { dimensionAia, ownDimensionAia } from "./dimensions";

describe("Dimenze's ids for the Lead (artifact-dimensions DIM1)", () => {
  it("marks a chosen dimension and an own dimension, each read back to Dimenze", () => {
    expect(dimensionAia("KNI-ai")).toBe("dimension:KNI-ai");
    expect(ownDimensionAia("RUN-a1")).toBe("own_dimension:RUN-a1");
    expect(parseAiaId("dimension:KNI-ai")).toMatchObject({ kind: "dimension", stage: "dimensions" });
    expect(parseAiaId("own_dimension:RUN-a1")).toMatchObject({ kind: "own_dimension", stage: "dimensions" });
  });

  it("leaves an id outside the grammar unmarked instead of breaking the screen", () => {
    for (const id of ["Úplně nová věc", "a b", "", "x".repeat(81)]) {
      expect(dimensionAia(id), id).toBeNull();
      expect(ownDimensionAia(id), id).toBeNull();
    }
  });
});
