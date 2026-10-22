import { describe, expect, it } from "vitest";

import { whoFixes, withFixer } from "./route-refusal";

describe("whoFixes", () => {
  it("names the operator, the parameter and the runbook for each refusal of the AI route's settings", () => {
    for (const [code, fixedBy] of [
      ["egress_route_not_approved_for_class", "aia_ai_route_approved_for"],
      ["egress_retention_unspecified", "aia_ai_route_retention_days"],
      ["egress_residency_violation", "aia_ai_route_eu_processing_approved"],
      ["egress_training_exclusion_missing", "aia_ai_route_excluded_from_training"],
      ["egress_no_approved_route", "trasu k modelu"],
      ["egress_route_provider_mismatch", "trasu k modelu"],
    ]) {
      const line = whoFixes(code);
      expect(line, code).toMatch(/^Opraví to provozovatel AIA, ne výzkumník/);
      expect(line, code).toContain(fixedBy);
      expect(line, code).toContain("deploy/develop/README.md");
    }
  });

  it("says nothing of a refusal a researcher or another owner resolves, or of none", () => {
    for (const code of ["egress_unclassified_material", "licence_undetermined", "budget_exceeded", "egress_", "", null, undefined]) expect(whoFixes(code)).toBeNull();
  });

  it("puts the line after the words, and leaves other words as they are", () => {
    expect(withFixer("Čeká.", "egress_retention_unspecified")).toBe(`Čeká. ${whoFixes("egress_retention_unspecified")}`);
    expect(withFixer("Čeká.", "reading_changed")).toBe("Čeká.");
  });
});
