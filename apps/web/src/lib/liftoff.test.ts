// @vitest-environment jsdom
// The film plays once, after a sign-in the person started, and an abandoned one expires.
import { afterEach, describe, expect, it } from "vitest";

import { armLiftoff, LIFTOFF_WINDOW_MS, takeLiftoff } from "./liftoff";

afterEach(() => sessionStorage.clear());

describe("liftoff arming", () => {
  it("is not armed until the sign-in button arms it", () => {
    expect(takeLiftoff()).toBe(false);
  });

  it("plays once: taking it disarms it", () => {
    armLiftoff(1_000);
    expect(takeLiftoff(2_000)).toBe(true);
    expect(takeLiftoff(2_000)).toBe(false);
  });

  it("expires when the sign-in was abandoned, and is disarmed all the same", () => {
    armLiftoff(0);
    expect(takeLiftoff(LIFTOFF_WINDOW_MS)).toBe(false);
    expect(sessionStorage.length).toBe(0);
  });

  it("never plays on a value it did not write", () => {
    sessionStorage.setItem("aia.liftoff.armedAt", "soon");
    expect(takeLiftoff()).toBe(false);
  });
});
