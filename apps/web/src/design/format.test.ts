import { describe, expect, it } from "vitest";
import { formatDateTime, formatMoney } from "./format";

describe("formatDateTime", () => {
  it("renders an API timestamp in Prague time", () => {
    expect(formatDateTime("2026-09-22T22:37:41Z")?.replace(/\s/g, " ")).toBe("23.09.26 0:37");
  });
  it("returns null for absent or unparseable input — never a made-up date", () => {
    expect(formatDateTime(null)).toBeNull();
    expect(formatDateTime("")).toBeNull();
    expect(formatDateTime("not a date")).toBeNull();
  });
});

describe("formatMoney", () => {
  it("always carries the currency", () => {
    expect(formatMoney(250, "USD").replace(/\s/g, " ")).toBe("250,00 USD");
  });
});
