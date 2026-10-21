// How a person's spend reads (develop-spend-attribution 7): unknown is never 0, a positive
// amount under a cent is not rounded away, the unattributed row is named, parts leave out
// only a known zero.
import { describe, expect, it } from "vitest";

import type { ActivitySpend, PersonSpend, ResearcherSpend } from "./api";
import { isSpendReport, overall, parts, personLabel, reservedLine, studyCount, totalLine, usd } from "./researcher-spend";

const fig = (total: number, uncertain = 0, reserved = 0) => ({
  model_usd: total, outside_ledger_usd: 0, total_usd: total, reserved_usd: reserved, uncertain_calls: uncertain,
});
const nbsp = (s: string) => s.replace(/[  ]/g, " ");

describe("amounts", () => {
  it("prints Czech USD and keeps a sub-cent spend visible", () => {
    expect(nbsp(usd(1234.5))).toBe("1 234,50 USD");
    expect(usd(0)).toBe("0,00 USD");
    expect(usd(0.003)).toBe("< 0,01 USD");
    expect(usd(Number.NaN)).toBe("neznámá");
  });

  it("says a total with an unknown bill is not exact, and an all-unknown one is unknown, not 0", () => {
    expect(totalLine(fig(0.4))).toEqual({ text: "0,40 USD", exact: true, note: null });
    const uncertain = totalLine(fig(0.4, 2));
    expect(uncertain.exact).toBe(false);
    expect(uncertain.note).toMatch(/^2 nejistá volání/);
    const unknown = totalLine(fig(0, 1));
    expect(unknown.text).toBe("neznámá");
    expect(unknown.note).toMatch(/^1 nejisté volání/);
    expect(totalLine(fig(0, 5)).note).toMatch(/^5 nejistých volání/);
  });

  it("names open holds apart and nothing when none are open", () => {
    expect(reservedLine(fig(0, 0, 2))).toBe("2,00 USD drženo v běžící práci");
    expect(reservedLine(fig(3))).toBeNull();
  });
});

describe("people and parts", () => {
  it("labels a person by name, else e-mail, else id, and the unattributed row by name", () => {
    expect(personLabel({ user_id: "USR-1", display_name: "Jana", email: "j@x" })).toBe("Jana");
    expect(personLabel({ user_id: "USR-1", display_name: " ", email: "j@x" })).toBe("j@x");
    expect(personLabel({ user_id: "USR-1", display_name: null, email: null })).toBe("USR-1");
    expect(personLabel({ user_id: null, display_name: null, email: null })).toBe("Nepřiřazeno");
  });

  it("leaves out only an activity that is a known zero, in the API's order", () => {
    const acts: ActivitySpend[] = [
      { activity: "lead", ...fig(0.1) },
      { activity: "fieldwork", ...fig(0) },
      { activity: "analysis_report", ...fig(0, 1) },
      { activity: "deep_research", ...fig(0, 0, 1) },
      { activity: "other", ...fig(0) },
    ];
    expect(parts(acts).map((p) => [p.activity, p.label, p.line.text])).toEqual([
      ["lead", "Vedoucí výzkumu", "0,10 USD"],
      ["analysis_report", "Analýza a zpráva", "neznámá"],
      ["deep_research", "Deep Research", "0,00 USD"],
    ]);
  });

  it("counts studies in Czech", () => {
    expect([1, 2, 4, 5, 0].map(studyCount)).toEqual(["1 studie", "2 studie", "4 studie", "5 studií", "0 studií"]);
  });
});

describe("the report", () => {
  const person = (user_id: string | null, total: number, uncertain = 0): PersonSpend => ({
    user_id, email: null, display_name: null, is_member: user_id ? true : null, study_count: 1,
    by_activity: [], studies: [], ...fig(total, uncertain),
  });
  const report: ResearcherSpend = {
    period: "this_month", start: "", end: "", everyone: true, currency: "USD",
    people: [person("A", 0.4), person("B", 0.25, 1), person(null, 0.3)],
  };

  it("sums what the caller may see, its uncertainty with it", () => {
    const sum = overall(report);
    expect(sum.total_usd).toBeCloseTo(0.95);
    expect(sum.uncertain_calls).toBe(1);
  });

  it("refuses an answer that is not a spend report rather than read it as nobody spent", () => {
    expect(isSpendReport(report)).toBe(true);
    expect(isSpendReport({})).toBe(false);
    expect(isSpendReport({ people: [], everyone: "yes", period: "this_month" })).toBe(false);
    expect(isSpendReport(null)).toBe(false);
  });
});
