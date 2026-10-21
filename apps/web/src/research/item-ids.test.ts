// The web's stable item ids against the server's (domain/item_ids.py): the same case file,
// packages/aia_core/tests/fixtures/item_ids/cases.json, is read by
// packages/aia_core/tests/test_item_ids.py. Its expectations are the server's; every id the web
// writes must be one the server reads the same.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { derivedId, entries, fnv10, fold, reconcile, sectionIds, settleItemIds, withItemIds, wordingOf } from "./item-ids";

type Obj = Record<string, unknown>;
const FILE = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/item_ids/cases.json"), "utf8")) as {
  hashes: { text: string; fnv10: string }[];
  folds: { text: string; fold: string }[];
  derived: { prefix: string; kind: string; text: string; occurrence: number; id: string }[];
  reconcile: { name: string; texts: string[]; entries: unknown; previous: [string, string][] | null; ids: string[] }[];
  sections: { name: string; sections: unknown[]; ids: (string | null)[] }[];
  designs: { name: string; content: Obj; analysis: Obj | null; expect: { content: Obj; analysis: Obj | null } }[];
  settle: { name: string; before: Obj; after: Obj; expect: Obj }[];
};

describe("the hash, the fold and a derived id are the server's", () => {
  it.each(FILE.hashes)("fnv10 $text", (c) => expect(fnv10(c.text)).toBe(c.fnv10));
  it("a lone surrogate hashes as U+FFFD, as the server reads it", () => expect(fnv10("\ud800 osamocený")).toBe(fnv10("\ufffd osamocený")));
  it.each(FILE.folds)("fold $text", (c) => expect(fold(c.text)).toBe(c.fold));
  it.each(FILE.derived)("derived $kind $text", (c) => expect(derivedId(c.prefix, c.kind, c.text, c.occurrence)).toBe(c.id));
});

describe("a list's ids are the server's", () => {
  it.each(FILE.reconcile)("$name", (c) => {
    expect(reconcile(c.texts, { prefix: "rq_", kind: "research_question", entries: entries(c.entries), previous: c.previous })).toEqual(c.ids);
  });
});

describe("a section without an id gets the compiler's", () => {
  it.each(FILE.sections)("$name", (c) => expect(sectionIds(c.sections)).toEqual(c.ids));
});

describe("a design with its ids is the server's", () => {
  it.each(FILE.designs)("$name", (c) => {
    const [content, analysis] = withItemIds(c.content, c.analysis);
    expect({ content, analysis }).toEqual(c.expect);
    expect(withItemIds(content, analysis)).toEqual([content, analysis]);
  });
  it("names a plan item's wording by its id", () => {
    const [content] = withItemIds(FILE.designs[0].content);
    const ids = ((content.research_plan as Obj).research_question_ids as { id: string }[]).map((e) => e.id);
    expect(wordingOf(content, null, "research_question", ids[1])).toBe("Kdo kupuje?");
    expect(wordingOf(content, null, "research_question", "rq_none")).toBeNull();
  });
});

describe("a change settles as the server settles it", () => {
  it.each(FILE.settle)("$name", (c) => {
    expect(settleItemIds([c.before, null], [c.after, null])[0]).toEqual(c.expect);
  });
});
