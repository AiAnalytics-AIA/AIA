import { describe, expect, it } from "vitest";
import { t, tv } from "@/i18n/t";
import { spendRows } from "./run-spend";

const SPEND = { spent_usd: 1.234, reserved_usd: 0.5, uncertain_calls: 0 };

describe("spendRows", () => {
  it("says nothing it was not given: an unread spend is unknown, never zero", () => {
    expect(spendRows(null, true, 10, null)).toBeNull();
    expect(spendRows(undefined, false, 10, null)).toBeNull();
  });

  it("reads spent, held and the study's remainder, a hold never as spent", () => {
    const rows = spendRows(SPEND, true, 98.5, null)!;
    expect(rows.map((r) => [r.key, r.value])).toEqual([
      ["spent", "1,23 USD"],
      ["held", "0,50 USD"],
      ["ceiling", t("research.exec.spend.ceilingUnrecorded")],
      ["remaining", "98,50 USD"],
    ]);
    expect(rows.find((r) => r.key === "remaining")!.note).toBe(t("research.exec.spend.remainingNote"));
    // Holds are spoken of as the running steps' only while the run goes on.
    expect(rows.find((r) => r.key === "held")!.note).toBeUndefined();
    expect(spendRows(SPEND, false, 98.5, null)!.find((r) => r.key === "held")!.note).toBe(t("research.exec.spend.heldNote"));
  });

  it("says the study's remainder is being read, or unknown when it could not be, never zero", () => {
    expect(spendRows(SPEND, true, undefined, null)!.find((r) => r.key === "remaining")!.value).toBe(t("research.exec.spend.remainingLoading"));
    for (const remaining of [null, Number.NaN]) {
      const row = spendRows(SPEND, true, remaining, null)!.find((r) => r.key === "remaining")!;
      expect(row.value).toBe(t("research.exec.spend.remainingUnknown"));
      expect(row.note).toBeUndefined();
    }
  });

  it("says calls without a known price apart: possibly in flight while the run goes on, unpriced once it ended", () => {
    const going = spendRows({ ...SPEND, uncertain_calls: 2 }, false, 1, null)!.find((r) => r.key === "unpriced")!;
    expect(going.value).toBe(tv("research.exec.spend.unpricedCalls", { count: 2 }));
    expect(going.note).toBe(t("research.exec.spend.unpricedRunning"));
    const ended = spendRows({ ...SPEND, uncertain_calls: 1 }, true, 1, null)!.find((r) => r.key === "unpriced")!;
    expect(ended.note).toBe(t("research.exec.spend.unpricedEnded"));
    // None: no row, a known nothing.
    expect(spendRows(SPEND, true, 1, null)!.some((r) => r.key === "unpriced")).toBe(false);
  });

  it("reads the ceiling the run started under, why it had none, or that it recorded none, never zero", () => {
    const of = (ceiling: Parameters<typeof spendRows>[3]) => spendRows(SPEND, true, 1, ceiling)!.find((r) => r.key === "ceiling")!;
    expect([of({ usd: 2.5, unknown: null }).value, of({ usd: 2.5, unknown: null }).note]).toEqual(["2,50 USD", t("research.exec.spend.ceilingNote")]);
    const unknown = of({ usd: null, unknown: "fieldwork_reservation_missing" });
    expect(unknown.value).toBe(t("research.exec.spend.ceilingUnknown"));
    expect(unknown.note).toBe(t("research.exec.cost.unknown.fieldwork_reservation_missing"));
    expect(of(null).value).toBe(t("research.exec.spend.ceilingUnrecorded"));
    expect(of(undefined).note).toBe(t("research.exec.spend.ceilingUnrecordedNote"));
    // A ceiling with no reason given names no empty code.
    expect(of({ usd: null, unknown: null }).note).toBeUndefined();
  });
});
