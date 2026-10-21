// A refused accept in words, for items named by their stable ids (WCE1) and by the text keys
// the server named them by before.
import { describe, expect, it } from "vitest";

import { withItemIds } from "./item-ids";
import { itemWords, staleMessage } from "./proposal-items";

const project = withItemIds({ research_plan: { research_questions: ["Jak cena mění zájem?", "Kdo kupuje?"], hypotheses: ["Sleva zvýší nákup"] } })[0];
const rq = ((project.research_plan as Record<string, unknown>).research_question_ids as { id: string }[])[1].id;

describe("itemWords", () => {
  it("says a plan item named by its id by its wording in the person's design", () => {
    expect(itemWords(`content:research_question:${rq}`, project)).toBe("Výzkumná otázka „Kdo kupuje?“");
  });
  it("keeps a key it cannot find, and an older text key, as written", () => {
    expect(itemWords("content:research_question:rq_gone", project)).toBe("Výzkumná otázka „rq_gone“");
    expect(itemWords("content:objective:zjistit cenu", null)).toBe("Cíl „zjistit cenu“");
  });
  it("names each conflicting item once in the refusal", () => {
    const message = staleMessage({ reason: "items_changed", conflicting_items: [`content:research_question:${rq}`, `content:research_question:${rq}`] }, project);
    expect(message.match(/Kdo kupuje\?/g)).toHaveLength(1);
  });
});
