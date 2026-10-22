// Dotazník's counts in Czech: the word follows its number (the browser audit, QF-2).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import type { Template } from "./model";
import { applyImport, countWords, countsWords } from "./questionnaire";

const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const BOOT: Template = { empty_project: EMPTY, ai_provider: "claude_code_subscription" };

describe("the questionnaire's counts in words", () => {
  it("takes the Czech form for 1, for 2 to 4, and for 0 and 5 or more", () => {
    expect([0, 1, 2, 4, 5, 22].map((n) => countWords("questions", n))).toEqual(["0 otázek", "1 otázka", "2 otázky", "4 otázky", "5 otázek", "22 otázek"]);
    expect([0, 1, 3, 5].map((n) => countWords("sets", n))).toEqual(["0 sledovaných sad", "1 sledovaná sada", "3 sledované sady", "5 sledovaných sad"]);
  });

  it("joins the two counts as the outline's heading", () => {
    expect(countsWords({ questions: 4, sets: 1 })).toBe("4 otázky · 1 sledovaná sada");
  });
});

describe("the import's note", () => {
  const sections = [
    { type: "questions", title: "B1", questions: [{ text: "A?", typ: "vyber" }, { text: "B?", typ: "skala" }] },
    { type: "object_battery", title: "S1", objects: ["a", "b", "c", "d"] },
  ];

  it("counts what was loaded in Czech", () => {
    const got = applyImport(EMPTY, { sections, summary: { question_count: 2, tracked_sets: 1 } }, BOOT);
    expect(got.toast).toBe("Načteno: 2 otázky · 1 sledovaná sada");
  });

  it("never prints undefined when the answer carries no summary", () => {
    expect(applyImport(EMPTY, { sections }, BOOT).toast).toBe("Načteno: 2 otázky · 1 sledovaná sada");
  });
});
