// What remains of a study's budget beside what an action can cost (run-recovery-and-truth 6d):
// unknown is never zero, and a ceiling above what remains says the step may stop for a person;
// remaining_usd is the budget less recorded spend, so what is held by running steps is named, not counted.
import { describe, expect, it } from "vitest";

import { budgetLine, holdsNote } from "./budget-line";

const study = (remaining_usd: number | null) => ({ budget_usd: 10, spent_usd: remaining_usd === null ? null : 10 - remaining_usd, remaining_usd });

describe("budgetLine", () => {
  it("says what remains, and what an action at its ceiling would leave, holds of running steps aside", () => {
    expect(budgetLine(study(6.5))).toBe("Z rozpočtu studie zbývá 6.50 USD.");
    expect(budgetLine(study(6.5), 2.25)).toBe("Z rozpočtu studie zbývá 6.50 USD. I při nejvyšší ceně by zbylo 4.25 USD, bez částek, které právě drží běžící kroky.");
  });

  it("says an action that can cost more than remains may stop for a person to lift the budget", () => {
    expect(budgetLine(study(1), 2.25)).toBe("Z rozpočtu studie zbývá 1.00 USD. To je víc, než nyní zbývá: přesáhne-li skutečná cena zbytek, krok se zastaví, dokud rozpočet nezvýšíte.");
  });

  it("never reads an unread budget or an unknown ceiling as zero", () => {
    expect(budgetLine(null, 2.25)).toBe("Kolik z rozpočtu studie zbývá, AIA nyní neví.");
    expect(budgetLine(study(null))).toBe("Kolik z rozpočtu studie zbývá, AIA nyní neví.");
    expect(budgetLine(study(6.5), null)).toBe("Z rozpočtu studie zbývá 6.50 USD. Kolik může stát, AIA předem neví.");
  });
});

describe("holdsNote", () => {
  it("says beside a lift that open holds are not in the remainder, and says nothing of an unknown one", () => {
    expect(holdsNote(study(0.5))).toBe("Zbytek nezahrnuje částky, které právě drží běžící kroky.");
    expect(holdsNote(study(0))).toBe("Zbytek nezahrnuje částky, které právě drží běžící kroky.");
    expect(holdsNote(study(null))).toBeNull();
    expect(holdsNote(null)).toBeNull();
  });
});
