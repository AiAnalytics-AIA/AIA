// A Design Research proposal reviewed by a person (research-lead-workbench 7b, F-DRL-1).
import { describe, expect, it } from "vitest";

import { ApiError, type DesignProposal } from "@/lib/api";
import { CONFLICT_MESSAGE } from "@/research/store";

import {
  acceptBody, acceptedFrom, DESIGN_PROPOSAL_CONTRACT, INADMISSIBLE, itemsWord, readProposal, refusalWords, subjectWords,
} from "./design-research-review";

const finding = (id: string) => ({ evidence_id: id, claim: `Tvrzení ${id}`, quote: "citace", source_title: "Zdroj", source: "https://example.org", source_class: "B", confidence: 0.7 });
const A = "DRP-aaaaaaaaaaaaaaaaaaaaaaaa";
const B = "DRP-bbbbbbbbbbbbbbbbbbbbbbbb";
const G = "DRP-cccccccccccccccccccccccc";
const proposal = (over: Partial<DesignProposal> = {}): DesignProposal => ({
  run_id: "DR-1", design_revision_id: "REV-7", design_revision: 7, admissible: true, refusal: null,
  items: [
    { item_id: A, kind: "EVIDENCE", subject_key: "q-a", subject_kind: "QUESTION", subject_text: "Jak často?", subject_origin: "research_plan.research_questions[0]", findings: [finding("EV-1")] },
    { item_id: B, kind: "EVIDENCE", subject_key: "o-b", subject_kind: "OBJECT", subject_text: "Značka B", subject_origin: "tracked_sets[0]", findings: [finding("EV-2")] },
    { item_id: G, kind: "GAP", subject_key: "q-g", subject_kind: "QUESTION", subject_text: "Proč?", subject_origin: "research_plan.research_questions[1]", findings: [] },
  ],
  ...over,
});
const withBlock = (items: Record<string, unknown>, contract = DESIGN_PROPOSAL_CONTRACT) => ({ title: "Studie", design_research: { contract_version: contract, items } });
const entry = (runId: string) => ({ kind: "EVIDENCE", provenance: { run_id: runId } });

describe("reading a Design Research proposal against the working copy", () => {
  it("offers every EVIDENCE item and no GAP item while nothing is taken", () => {
    const r = readProposal(proposal(), { title: "Studie" });
    expect(r.spent).toBe(false);
    expect(r.items.map((i) => [i.itemId, i.selectable, i.accepted])).toEqual([[A, true, false], [B, true, false], [G, false, false]]);
  });

  it("marks what the working copy already took from this run, and offers nothing more from it", () => {
    const r = readProposal(proposal(), withBlock({ [A]: entry("DR-1") }));
    expect(r.spent).toBe(true);
    expect(r.items.find((i) => i.itemId === A)).toMatchObject({ accepted: true, selectable: false });
    // The accept wrote a new revision this run did not research: the server refuses another (design_moved).
    expect(r.items.find((i) => i.itemId === B)).toMatchObject({ accepted: false, selectable: false });
  });

  it("reads only this run's entries, and never a block of another contract", () => {
    expect([...acceptedFrom(withBlock({ [A]: entry("DR-1"), [B]: entry("DR-OTHER") }), "DR-1")]).toEqual([A]);
    expect(acceptedFrom(withBlock({ [A]: entry("DR-1") }, "something-else"), "DR-1").size).toBe(0);
    expect(acceptedFrom(null, "DR-1").size).toBe(0);
    expect(readProposal(proposal(), withBlock({ [A]: entry("DR-OTHER") })).spent).toBe(false);
  });

  it("offers nothing from an inadmissible proposal", () => {
    const r = readProposal(proposal({ admissible: false, refusal: "recorded fixtures" }), null);
    expect(r.admissible).toBe(false);
    expect(r.items.every((i) => !i.selectable)).toBe(true);
  });
});

describe("the accept's body", () => {
  it("has exactly the ticked items, once and sorted, on both baselines", () => {
    const p = proposal();
    const body = acceptBody(p, readProposal(p, null), [B, A, B], 12);
    expect(body).toEqual({ item_ids: [A, B], expected_revision_id: "REV-7", expected_workspace_revision: 12 });
  });

  it("never sends a GAP, an unknown id or an item already taken", () => {
    const p = proposal();
    expect(acceptBody(p, readProposal(p, null), [A, G, "DRP-000000000000000000000000"], 3)?.item_ids).toEqual([A]);
    expect(acceptBody(p, readProposal(p, null), [G], 3)).toBeNull();
    expect(acceptBody(p, readProposal(p, withBlock({ [A]: entry("DR-1") })), [A, B], 3)).toBeNull();
  });

  it("sends nothing before the working copy is saved", () => {
    const p = proposal();
    expect(acceptBody(p, readProposal(p, null), [A], null)).toBeNull();
  });
});

describe("a refused accept, in words", () => {
  it("says a stale proposal through proposal-items.ts, naming the items both changed", () => {
    const e = new ApiError(409, "stale_proposal", "stale", null, { reason: "items_changed", conflicting_items: ["content:field:design_research", "content:brief:goal"] });
    expect(refusalWords(e)).toBe("Návrh nejde použít: mezitím se změnilo, co návrh mění – Podklady z hloubkového výzkumu, Cíl studie. Vaše úpravy zůstávají; návrh připravte znovu nad současným zadáním.");
  });

  it("says a newer Design Revision and a moved lineage", () => {
    expect(refusalWords(new ApiError(409, "stale_proposal", "x", null, { reason: "design_moved" }))).toContain("mezitím vznikla novější revize návrhu");
    expect(refusalWords(new ApiError(409, "stale_proposal", "x", null, { reason: "lineage_changed" }))).toContain("podkladů, které se mezitím změnily");
  });

  it("says the route's other refusals, and leaves an unknown error to its message", () => {
    expect(refusalWords(new ApiError(409, "stale_revision", "x", null))).toBe(CONFLICT_MESSAGE);
    expect(refusalWords(new ApiError(422, "inadmissible", "x", null))).toBe(INADMISSIBLE);
    expect(refusalWords(new ApiError(422, "block_too_large", "x", null))).toContain("Vyberte jich méně");
    expect(refusalWords(new ApiError(500, "internal", "x", null))).toBeNull();
    expect(refusalWords(new Error("boom"))).toBeNull();
  });
});

describe("words", () => {
  it("names the subject kinds and counts items in Czech", () => {
    expect(subjectWords("QUESTION")).toBe("Výzkumná otázka");
    expect(subjectWords("CROSS")).toBe("Otázka k objektu");
    expect(subjectWords("NEW_KIND")).toBe("NEW_KIND");
    expect([1, 2, 4, 5, 0].map(itemsWord)).toEqual(["1 položka", "2 položky", "4 položky", "5 položek", "0 položek"]);
  });
});
