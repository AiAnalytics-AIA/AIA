// Dotazník's counts in Czech: the word follows its number (the browser audit, QF-2).
import { describe, expect, it } from "vitest";

import { countWords, countsWords } from "./questionnaire";

describe("the questionnaire's counts in words", () => {
  it("takes the Czech form for 1, for 2 to 4, and for 0 and 5 or more", () => {
    expect([0, 1, 2, 4, 5, 22].map((n) => countWords("questions", n))).toEqual(["0 otázek", "1 otázka", "2 otázky", "4 otázky", "5 otázek", "22 otázek"]);
    expect([0, 1, 3, 5].map((n) => countWords("sets", n))).toEqual(["0 sledovaných sad", "1 sledovaná sada", "3 sledované sady", "5 sledovaných sad"]);
  });

  it("joins the two counts as the outline's heading", () => {
    expect(countsWords({ questions: 4, sets: 1 })).toBe("4 otázky · 1 sledovaná sada");
  });
});
