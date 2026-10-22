// A concept-test set's price bands as chips (input-interactions chunk 3, audit A16).
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { PRICE_REFUSED, type Section, priceBandsOf, priceProblem, setPriceBandList, setPriceBands } from "./questionnaire";

describe("price bands", () => {
  it("takes a positive amount, with Kč or without, thousands spaced and a decimal comma", () => {
    for (const ok of ["199", "199 Kč", "199Kč", "1 299 Kč", "1\u00a0299,90 Kč", "12.5", "99,- ", "249 CZK"]) expect([ok, priceProblem(ok)]).toEqual([ok, null]);
  });

  it("refuses what is not one amount, at the field", () => {
    for (const bad of ["", "zdarma", "0 Kč", "-5", "199 – 249 Kč", "1,999", "19,999 Kč", "1 29 Kč", "199 €"]) expect([bad, priceProblem(bad)]).toEqual([bad, PRICE_REFUSED]);
  });

  it("stores the bands as typed, trimmed, and reads them back", () => {
    const p = { sections: [{ id: "s", type: "object_battery", metadata: { other: 1 } }] } as unknown as ResearchProject;
    const next = setPriceBandList(p, 0, [" 199 Kč ", "249 Kč", " "]);
    expect((next.sections as Section[])[0].metadata).toEqual({ other: 1, price_bands: ["199 Kč", "249 Kč"] });
    expect(priceBandsOf((next.sections as Section[])[0])).toEqual(["199 Kč", "249 Kč"]);
    expect(priceBandsOf(((setPriceBands(p, 0, "199 Kč, 249 Kč") as ResearchProject).sections as Section[])[0])).toEqual(["199 Kč", "249 Kč"]);
  });
});
