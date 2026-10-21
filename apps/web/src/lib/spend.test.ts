import { describe, expect, it } from "vitest";

import { MONEY_NAMES, SPEND_KINDS, afterWords, ceilingWords, lineWords, moneyName, remainingAfter, spendTitle, usdWords } from "./spend";

describe("the money modal's words (I7a, D-01)", () => {
  it("has four questions and four named sums, each with its own Czech name", () => {
    expect(SPEND_KINDS.map(spendTitle)).toEqual(["Potvrzení útraty", "Zvýšení rozpočtu studie", "Zvýšení rozpočtu klienta", "Navýšení peněženky"]);
    expect(MONEY_NAMES.map(moneyName)).toEqual(["Rozpočet klienta", "Rozpočet studie", "Peněženka", "Práh potvrzení"]);
  });

  it("prints USD the Czech way, and an unknown sum in words, never as zero", () => {
    expect(usdWords(1.76)).toBe("1,76 USD");
    expect(usdWords(1250)).toBe("1 250,00 USD");
    expect(usdWords(0)).toBe("0,00 USD");
    expect(usdWords(null)).toBe("neznámé");
    expect(usdWords(undefined)).toBe("neznámé");
    expect(usdWords(Number.NaN)).toBe("neznámé");
  });

  it("states the ceiling as an upper bound, not an estimate; an unknown one is not zero", () => {
    expect(ceilingWords(28.4)).toEqual({ value: "28,40 USD", note: "horní mez, ne odhad" });
    expect(ceilingWords(null)).toEqual({ value: "nelze předem určit", note: "neznámá cena se nikdy nepočítá jako nula" });
  });

  it("works out what is left of the paying sum at the highest price, and after a lift", () => {
    const study = { name: "study_budget" as const, usd: 80, remainingUsd: 0.9 };
    expect(remainingAfter(study, 1.76)).toBe(-0.86);
    expect(remainingAfter(study, 1.76, 85)).toBe(4.14);
    expect(remainingAfter({ name: "study_budget", usd: 80, remainingUsd: 57.8 }, 28.4)).toBe(29.4);
  });

  it("concludes nothing from a missing figure", () => {
    expect(remainingAfter(undefined, 1)).toBeNull();
    expect(remainingAfter({ name: "study_budget", usd: 80, remainingUsd: null }, 1)).toBeNull();
    expect(remainingAfter({ name: "study_budget", usd: 80, remainingUsd: 5 }, null)).toBeNull();
    expect(remainingAfter({ name: "study_budget", usd: null, remainingUsd: 5 }, 1, 85)).toBeNull();
    expect(remainingAfter({ name: "study_budget", usd: 80, remainingUsd: 5 }, 1, null)).toBeNull();
  });

  it("says what follows: left over, may stop, or unknown", () => {
    expect(afterWords(4.14)).toBe("I při nejvyšší ceně zbude 4,14 USD.");
    expect(afterWords(0)).toBe("I při nejvyšší ceně zbude 0,00 USD.");
    expect(afterWords(-0.86)).toBe("Může stát víc, než zbývá: krok se pak zastaví a počká na zvýšení.");
    expect(afterWords(null)).toBe("Kolik zbude, nelze spočítat: chybí horní mez nebo zůstatek.");
  });

  it("prints a sum with its remainder beside it", () => {
    expect(lineWords({ name: "study_budget", usd: 80, remainingUsd: 0.9 })).toBe("80,00 USD · zbývá 0,90 USD");
    expect(lineWords({ name: "threshold", usd: 25 })).toBe("25,00 USD");
    expect(lineWords({ name: "wallet", usd: null, remainingUsd: null })).toBe("neznámé · zbývá neznámé");
  });
});
