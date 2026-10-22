import { describe, expect, it } from "vitest";

import { plural } from "./format";

describe("plural", () => {
  it("takes Czech's one / few / many: 1, 2-4, everything else, with no 21/22 exception", () => {
    expect([0, 1, 2, 4, 5, 11, 21, 22, 25].map((n) => plural(n, "položka", "položky", "položek"))).toEqual([
      "0 položek", "1 položka", "2 položky", "4 položky", "5 položek", "11 položek", "21 položek", "22 položek", "25 položek",
    ]);
  });
});
