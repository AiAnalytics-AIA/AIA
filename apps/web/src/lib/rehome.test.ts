import { describe, expect, it } from "vitest";

import { rehomeEnabledFrom } from "./rehome";

describe("rehomeEnabledFrom", () => {
  it.each([["true"], ["TRUE"], [" 1 "]])("is on for %j", (v) => expect(rehomeEnabledFrom(v)).toBe(true));
  it.each([[undefined], [""], ["false"], ["0"], ["yes"], ["on"]])("is off for %j", (v) =>
    expect(rehomeEnabledFrom(v)).toBe(false),
  );
});
