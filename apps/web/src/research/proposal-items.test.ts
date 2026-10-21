// A refused accept in words, for items named by their stable ids (WCE1) and by the text keys
// the server named them by before.
import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";

import { derivedId, withItemIds } from "./item-ids";
import { itemWords, staleDetails, staleMessage } from "./proposal-items";

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
  it("says an item the person reworded or removed by the wording the server sent", () => {
    // The conflicting id is the baseline's: the person's copy no longer has it.
    const gone = `content:research_question:${derivedId("rq_", "research_question", "Kdo kupuje?", 1)}`;
    const now = { research_plan: { research_questions: ["Jak cena mění zájem?", "Kdo nakupuje online?"] } };
    const refused = new ApiError(409, "stale_proposal", "stale", null, { reason: "items_changed", conflicting_items: [gone], conflicting_wording: { [gone]: "Kdo kupuje?" } });
    const details = staleDetails(refused);
    expect(details?.conflicting_wording).toEqual({ [gone]: "Kdo kupuje?" });
    expect(staleMessage(details!, now)).toContain("Výzkumná otázka „Kdo kupuje?“");
    expect(staleMessage(details!, now)).not.toContain("rq_");
    expect(itemWords("content:question:Q9", null, "Pijete kávu?")).toBe("Otázka „Pijete kávu?“");
  });
  it("names each conflicting item once in the refusal", () => {
    const message = staleMessage({ reason: "items_changed", conflicting_items: [`content:research_question:${rq}`, `content:research_question:${rq}`] }, project);
    expect(message.match(/Kdo kupuje\?/g)).toHaveLength(1);
  });
});
