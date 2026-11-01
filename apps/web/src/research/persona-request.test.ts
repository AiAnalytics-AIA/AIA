import { describe, expect, it } from "vitest";

import { REQUEST_IN_CATALOGUE, matchesDimensionSearch, requestProblem, searchFold } from "./persona";

const CATALOGUE = [
  { id: "duvera", label: "Důvěra", source: "Systém" },
  { id: "znacka", label: "Vztah ke značkám", source: "Systém" },
  { id: "socialni_site", label: "Sociální sítě", source: "Systém" },
  { id: "rada", label: "Rada", source: "Systém" },
];

describe("Dimenze's search and request check (artifact-dimensions DIM-F13, DIM-F14)", () => {
  it("folds case, diacritics and spaces for the search", () => {
    expect(searchFold("  Vztah   ke ZNAČKÁM ")).toBe("vztah ke znackam");
  });

  it("finds a dimension typed without diacritics, and still by its id or source", () => {
    expect(CATALOGUE.filter((d) => matchesDimensionSearch(d, " znacka")).map((d) => d.id)).toEqual(["znacka"]);
    expect(matchesDimensionSearch(CATALOGUE[0], "DŮVĚ")).toBe(true);
    expect(matchesDimensionSearch(CATALOGUE[0], "system")).toBe(true);
    expect(matchesDimensionSearch(CATALOGUE[0], "xyz")).toBe(false);
    expect(matchesDimensionSearch(CATALOGUE[0], "   ")).toBe(true);
  });

  it("refuses a name the catalogue has, by label or id, naming it as the catalogue writes it", () => {
    expect(requestProblem("  VZTAH ke  značkám", CATALOGUE)).toBe(REQUEST_IN_CATALOGUE.replace("{label}", "Vztah ke značkám"));
    expect(requestProblem("DUVERA", CATALOGUE)).toBe(REQUEST_IN_CATALOGUE.replace("{label}", "Důvěra"));
    expect(requestProblem("socialni site", CATALOGUE)).toBe(REQUEST_IN_CATALOGUE.replace("{label}", "Sociální sítě"));
  });

  it("lets through a name that differs only in diacritics, or that is only part of one", () => {
    expect(requestProblem("Řada", CATALOGUE)).toBeNull();
    expect(requestProblem("Důvěra v instituce", CATALOGUE)).toBeNull();
  });
});
