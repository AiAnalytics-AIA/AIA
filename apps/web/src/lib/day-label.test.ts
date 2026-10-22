import { describe, expect, it } from "vitest";
import { dayKey, dayLabel, isDayBreak, withDayBreaks } from "./day-label";

// Local-time constructors throughout: the rule is the viewer's day, so the tests are too.
const now = new Date(2026, 9, 21, 9, 30); // středa 21. října 2026

describe("dayLabel", () => {
  it("says Dnes and Včera across midnight, by the local calendar", () => {
    expect(dayLabel(new Date(2026, 9, 21, 0, 0), now)).toBe("Dnes");
    expect(dayLabel(new Date(2026, 9, 20, 23, 59), now)).toBe("Včera");
    expect(dayLabel(new Date(2026, 9, 20, 0, 0), new Date(2026, 9, 21, 0, 1))).toBe("Včera");
  });

  it("names the weekday within the past week, then the date alone", () => {
    expect(dayLabel(new Date(2026, 9, 19, 14, 0), now)).toBe("pondělí 19. října 2026");
    expect(dayLabel(new Date(2026, 9, 14, 14, 0), now)).toBe("14. října 2026");
  });

  it("counts calendar days, not 24-hour spans, over a DST change", () => {
    // Europe/Prague leaves summer time on 25 October 2026: that Sunday has 25 hours.
    const monday = new Date(2026, 9, 26, 0, 30);
    expect(dayLabel(new Date(2026, 9, 25, 23, 30), monday)).toBe("Včera");
    expect(dayLabel(new Date(2026, 9, 24, 0, 30), monday)).toBe("sobota 24. října 2026");
    // And entering summer time, 29 March 2026, a 23-hour day.
    expect(dayLabel(new Date(2026, 2, 28, 23, 30), new Date(2026, 2, 30, 0, 15))).toBe("sobota 28. března 2026");
  });

  it("gives an unknown or invalid moment no day, never Dnes", () => {
    for (const bad of [null, undefined, "", "not a date", Number.NaN]) {
      expect(dayLabel(bad, now)).toBeNull();
      expect(dayKey(bad)).toBeNull();
    }
  });

  it("names a moment after now by its date", () => {
    expect(dayLabel(new Date(2026, 9, 22, 8, 0), now)).toBe("22. října 2026");
  });
});

describe("withDayBreaks", () => {
  type Item = { id: string; at: string | null };
  const iso = (d: Date) => d.toISOString();

  it("puts one divider before the first item of each local day", () => {
    const items: Item[] = [
      { id: "a", at: iso(new Date(2026, 9, 20, 22, 0)) },
      { id: "b", at: iso(new Date(2026, 9, 20, 23, 59)) },
      { id: "c", at: iso(new Date(2026, 9, 21, 0, 1)) },
    ];
    const out = withDayBreaks(items, (i) => i.at, now);
    expect(out.map((x) => (isDayBreak(x) ? `[${x.label}]` : x.id))).toEqual(["[Včera]", "a", "b", "[Dnes]", "c"]);
  });

  it("keeps an item with no day in place and breaks nothing for it", () => {
    const items: Item[] = [
      { id: "a", at: iso(new Date(2026, 9, 21, 8, 0)) },
      { id: "x", at: null },
      { id: "b", at: iso(new Date(2026, 9, 21, 9, 0)) },
    ];
    const out = withDayBreaks(items, (i) => i.at, now);
    expect(out.map((x) => (isDayBreak(x) ? `[${x.label}]` : x.id))).toEqual(["[Dnes]", "a", "x", "b"]);
  });
});
