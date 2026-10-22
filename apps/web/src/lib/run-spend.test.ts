import { describe, expect, it } from "vitest";
import { t, tv } from "@/i18n/t";
import { spendRows } from "./run-spend";

const SPEND = { spent_usd: 1.234, reserved_usd: 0.5, uncertain_calls: 0 };

describe("spendRows", () => {
  it("says nothing it was not given: an unread spend is unknown, never zero", () => {
    expect(spendRows(null, true, 10)).toBeNull();
    expect(spendRows(undefined, false, 10)).toBeNull();
  });

  it("reads spent, held and the study's remainder, a hold never as spent", () => {
    const rows = spendRows(SPEND, true, 98.5)!;
    expect(rows.map((r) => [r.key, r.value])).toEqual([
      ["spent", "1,23 USD"],
      ["held", "0,50 USD"],
      ["remaining", "98,50 USD"],
    ]);
    expect(rows.find((r) => r.key === "remaining")!.note).toBe(t("research.exec.spend.remainingNote"));
    // Holds are spoken of as the running steps' only while the run goes on.
    expect(rows.find((r) => r.key === "held")!.note).toBeUndefined();
    expect(spendRows(SPEND, false, 98.5)!.find((r) => r.key === "held")!.note).toBe(t("research.exec.spend.heldNote"));
  });

  it("says the study's remainder is being read, or unknown when it could not be, never zero", () => {
    expect(spendRows(SPEND, true, undefined)!.find((r) => r.key === "remaining")!.value).toBe(t("research.exec.spend.remainingLoading"));
    for (const remaining of [null, Number.NaN]) {
      const row = spendRows(SPEND, true, remaining)!.find((r) => r.key === "remaining")!;
      expect(row.value).toBe(t("research.exec.spend.remainingUnknown"));
      expect(row.note).toBeUndefined();
    }
  });

  it("says calls without a known price apart: possibly in flight while the run goes on, unpriced once it ended", () => {
    const going = spendRows({ ...SPEND, uncertain_calls: 2 }, false, 1)!.find((r) => r.key === "unpriced")!;
    expect(going.value).toBe(tv("research.exec.spend.unpricedCalls", { count: 2 }));
    expect(going.note).toBe(t("research.exec.spend.unpricedRunning"));
    const ended = spendRows({ ...SPEND, uncertain_calls: 1 }, true, 1)!.find((r) => r.key === "unpriced")!;
    expect(ended.note).toBe(t("research.exec.spend.unpricedEnded"));
    // None: no row, a known nothing.
    expect(spendRows(SPEND, true, 1)!.some((r) => r.key === "unpriced")).toBe(false);
  });
});
