import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { chosenDimensions, undoChosen } from "./persona";

const chosen = (approved: string[]) => ({ persona_dimensions: { approved, mode: "calibrated" } }) as unknown as ResearchProject;

describe("Vrátit on Dimenze (undoChosen, DIM-F10)", () => {
  it("puts an unchanged selection back exactly, order included, keeping the rest of persona_dimensions", () => {
    const after = ["zdravi", "media"];
    const out = undoChosen(chosen(after), ["cena", "media"], after);
    expect(chosenDimensions(out.project)).toEqual(["cena", "media"]);
    expect((out.project.persona_dimensions as { mode: string }).mode).toBe("calibrated");
    expect(out.reason).toBe("dimension_restore");
  });

  it("takes back only its own change when the selection moved since", () => {
    // Removed cena from [cena, media]; then politika was added.
    expect(chosenDimensions(undoChosen(chosen(["media", "politika"]), ["cena", "media"], ["media"]).project)).toEqual(["cena", "media", "politika"]);
    // Autofill replaced [cena, media] with [zdravi, media]; then politika was added: zdravi out, cena back.
    expect(chosenDimensions(undoChosen(chosen(["zdravi", "media", "politika"]), ["cena", "media"], ["zdravi", "media"]).project)).toEqual(["cena", "media", "politika"]);
  });

  it("never doubles a dimension chosen again meanwhile, and leaves the input untouched", () => {
    const p = chosen(["media", "cena"]);
    expect(chosenDimensions(undoChosen(p, ["cena", "media"], ["media"]).project)).toEqual(["media", "cena"]);
    expect(chosenDimensions(p)).toEqual(["media", "cena"]);
  });
});
