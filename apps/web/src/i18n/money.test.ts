// The four money names, written once (D-01; ADR 0028): the copy module's `money` block against the
// case file the server's domain/money.py is held to, packages/aia_core/tests/fixtures/money/
// vocabulary.json. A screen names an amount through `cs.money`, so this is the one place a name
// can drift from the server's.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { cs, money } from "./cs";

type Amount = { amount: string; czech: string | null; web_key: string | null };
const FILE = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/money/vocabulary.json"), "utf8")) as {
  amounts: Amount[];
  retired_names: string[];
};

describe("money names", () => {
  it("are the server's, each under its key", () => {
    const named = FILE.amounts.filter((a) => a.web_key !== null);
    expect(Object.keys(money).sort()).toEqual(named.map((a) => a.web_key).sort());
    for (const a of named) expect(money[a.web_key as keyof typeof money]).toBe(a.czech);
    expect(cs.money).toBe(money);
  });

  it("leave no retired name on any screen", () => {
    const all = JSON.stringify(cs);
    for (const name of FILE.retired_names) expect(all).not.toContain(name);
  });

  it("are what Settings and the run's cost panel label the amounts", () => {
    expect(cs.aia.settings.panel.studies.ceiling).toBe(money.studyBudget);
    expect(cs.aia.settings.panel.items.study_budget).toBe(money.studyBudget);
    expect(cs.aia.profile.budget.title).toBe(money.clientBudget);
    expect(cs.research.exec.cost.limit).toBe(money.confirmThreshold);
    expect(cs.research.exec.cost.legendLimit).toBe(money.confirmThreshold);
  });
});
