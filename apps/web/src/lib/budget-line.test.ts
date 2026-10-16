// What remains of a study's budget beside what an action can cost (run-recovery-and-truth 6d):
// unknown is never zero, and a ceiling above what remains says the step would stop for a person.
import { describe, expect, it } from "vitest";

import { budgetLine } from "./budget-line";

const study = (remaining_usd: number | null) => ({ budget_usd: 10, spent_usd: remaining_usd === null ? null : 10 - remaining_usd, remaining_usd });

describe("budgetLine", () => {
  it("says what remains, and what is left after an action at the least", () => {
    expect(budgetLine(study(6.5))).toBe("Z rozpočtu studie zbývá 6.50 USD.");
    expect(budgetLine(study(6.5), 2.25)).toBe("Z rozpočtu studie zbývá 6.50 USD. Poté zbude nejméně 4.25 USD.");
  });

  it("says an action that can cost more than remains would stop for a person to lift the budget", () => {
    expect(budgetLine(study(1), 2.25)).toBe("Z rozpočtu studie zbývá 1.00 USD. To je víc, než zbývá: krok se zastaví, dokud rozpočet nezvýšíte.");
  });

  it("never reads an unread budget or an unknown ceiling as zero", () => {
    expect(budgetLine(null, 2.25)).toBe("Kolik z rozpočtu studie zbývá, AIA nyní neví.");
    expect(budgetLine(study(null))).toBe("Kolik z rozpočtu studie zbývá, AIA nyní neví.");
    expect(budgetLine(study(6.5), null)).toBe("Z rozpočtu studie zbývá 6.50 USD. Kolik může stát, AIA předem neví.");
  });
});
