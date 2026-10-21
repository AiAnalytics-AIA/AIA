import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";

import {
  RESULT_CAP, actedOn, atCap, filingFor, folderOf, folderView, nextLabelColour, olderThanAYear, shown, staleEdit, toggled, toggledAll, undoable,
} from "./knowledge-library";

const NOW = Date.parse("2026-10-13T12:00:00Z");

describe("what a view asks the API for", () => {
  it("names a folder, items in none, or nothing; a label goes along with any view", () => {
    expect(filingFor("all", null)).toEqual({ folder: undefined, label: undefined });
    expect(filingFor("unfiled", null)).toEqual({ folder: "unfiled", label: undefined });
    expect(filingFor(folderView("KNF-1"), "KNL-2")).toEqual({ folder: "KNF-1", label: "KNL-2" });
    // "old" is decided here, on the dates the API returned; it asks for everything.
    expect(filingFor("old", null)).toEqual({ folder: undefined, label: undefined });
    expect(folderOf(folderView("KNF-9"))).toBe("KNF-9");
    expect(folderOf("all")).toBeNull();
  });
});

describe("older than a year", () => {
  it("is a change more than 365 days ago, and an item with no date is not called old", () => {
    expect(olderThanAYear({ modified_at: "2025-10-01T00:00:00Z" }, NOW)).toBe(true);
    expect(olderThanAYear({ modified_at: "2025-11-01T00:00:00Z" }, NOW)).toBe(false);
    expect(olderThanAYear({ modified_at: null }, NOW)).toBe(false);
    expect(olderThanAYear({ modified_at: "not a date" }, NOW)).toBe(false);
  });

  it("filters only the old view", () => {
    const items = [{ modified_at: "2024-01-01T00:00:00Z" }, { modified_at: "2026-10-01T00:00:00Z" }];
    expect(shown(items, "old", NOW)).toHaveLength(1);
    expect(shown(items, "all", NOW)).toHaveLength(2);
  });

  it("says when the API's page is full rather than looking complete", () => {
    expect(atCap(new Array(199))).toBe(false);
    expect(atCap(new Array(200))).toBe(true);
  });
});

describe("the selection the bulk bar acts on", () => {
  it("ticks and unticks one item without touching the set it was given", () => {
    const before = new Set(["a"]);
    expect([...toggled(before, "b")]).toEqual(["a", "b"]);
    expect([...toggled(before, "a")]).toEqual([]);
    expect([...before]).toEqual(["a"]);
  });

  it("ticks every shown item, or none when all are ticked, and keeps ticks on items not shown", () => {
    const some = toggledAll(new Set(["x"]), ["a", "b"]);
    expect([...some].sort()).toEqual(["a", "b", "x"]);
    expect([...toggledAll(some, ["a", "b"])]).toEqual(["x"]);
    expect([...toggledAll(new Set(), [])]).toEqual([]);
  });

  it("acts only on ticked items that are still shown, so nothing hidden moves unseen", () => {
    expect(actedOn(new Set(["a", "hidden"]), ["a", "b"])).toEqual(["a"]);
  });
});

describe("an edit refused because the item moved on (F-K1)", () => {
  it("reads the base and current revisions from the API's refusal and nothing else", () => {
    const stale = new ApiError(409, "knowledge_proposal_stale", "x", null, { item_id: "KNW-1", base_revision: 1, current_revision: 2 });
    expect(staleEdit(stale)).toEqual({ base: 1, current: 2 });
    // A base filed before it was recorded stays unknown, never assumed current.
    const unknown = new ApiError(409, "knowledge_proposal_stale", "x", null, { base_revision: null, current_revision: 4 });
    expect(staleEdit(unknown)).toEqual({ base: null, current: 4 });
    expect(staleEdit(new ApiError(409, "already_decided", "x", null))).toBeNull();
    expect(staleEdit(new ApiError(409, "knowledge_proposal_stale", "x", null, {}))).toBeNull();
    expect(staleEdit(new Error("boom"))).toBeNull();
  });
});

describe("a new label's colour (input-interactions I5)", () => {
  it("is the first colour no label uses, else the next in turn", () => {
    expect(nextLabelColour([])).toBe("BLUE");
    expect(nextLabelColour([{ colour: "BLUE" }, { colour: "GREEN" }])).toBe("TEAL");
    const six = (["BLUE", "TEAL", "GREEN", "ORANGE", "VIOLET", "SLATE"] as const).map((colour) => ({ colour }));
    expect(nextLabelColour(six)).toBe("BLUE");
    expect(nextLabelColour([...six, { colour: "BLUE" as const }])).toBe("TEAL");
  });
});

describe("whether a deletion can be taken back (input-interactions I6)", () => {
  it("only when the items read are every item the API counts as filed there", () => {
    expect(undoable(0, [])).toBe(true);
    expect(undoable(2, ["a", "b"])).toBe(true);
    // One filed meanwhile, or one the read did not return: refiling the rest would not be an undo.
    expect(undoable(3, ["a", "b"])).toBe(false);
    expect(undoable(1, ["a", "b"])).toBe(false);
    // A full page may have more behind it.
    const full = Array.from({ length: RESULT_CAP }, (_, i) => i);
    expect(undoable(RESULT_CAP, full)).toBe(false);
  });
});
