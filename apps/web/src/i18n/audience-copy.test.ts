// Cílová skupina's copy, as a person reads it (artifact-audience, Findings F1): no name of the old
// product's panel, no untranslated English label, and no promise of a capability AIA does not have.
import { describe, expect, it } from "vitest";

import { cs } from "./cs";

const strings = (o: unknown): string[] =>
  typeof o === "string" ? [o] : o && typeof o === "object" ? Object.values(o).flatMap(strings) : [];

describe("Cílová skupina's copy", () => {
  const audience = strings(cs.research.audience);

  it("is read as a whole", () => {
    expect(audience.length).toBeGreaterThan(40);
  });

  it("names no panel of the old product and no English term", () => {
    // "Audience AI Analytics" is the product's name for AIA's own populations; renaming it is the
    // product owner's call, so it is the one English name kept.
    for (const s of audience) {
      const text = s.replace(/audience ai analytics/gi, "");
      expect(text, s).not.toMatch(/NPC Panel|COMING SOON|Special Audience|respondent-level|outcome|over-index|preflight|sampling|research-only|\bworkflow\b|\brun\b/i);
    }
  });

  it("promises no capability AIA lacks: a segment found in the results, a stored own dataset used", () => {
    expect(cs.research.audience.strategyDiscoverText).toMatch(/neumí/);
    expect(cs.research.audience.storedNotUsed).toMatch(/nepoužije/);
  });
});
