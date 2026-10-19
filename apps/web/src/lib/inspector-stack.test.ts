// The item inspector's back stack (research-lead-workbench chunk 2): push, back, close, and a
// stack that belongs to its stage.
import { describe, expect, it } from "vitest";

import { backEntry, closeStack, emptyStack, onStage, openEntry, topEntry } from "./inspector-stack";

const q1 = { id: "question:q1", title: "Otázka 1" };
const m1 = { id: "measure:m1", title: "Měření 1", sub: "Výsledky" };

describe("the inspector's back stack", () => {
  it("opens an item over the one it was opened from, and Back returns to it", () => {
    let s = openEntry(emptyStack("questionnaire"), q1);
    s = openEntry(s, m1);
    expect(topEntry(s)).toEqual(m1);
    s = backEntry(s);
    expect(topEntry(s)).toEqual(q1);
    s = backEntry(s);
    expect(topEntry(s)).toBeNull();
  });

  it("does not open the item on top twice, and takes its newer words", () => {
    const s = openEntry(emptyStack("questionnaire"), q1);
    expect(openEntry(s, q1)).toBe(s);
    const renamed = openEntry(s, { ...q1, title: "Otázka 1 (upravená)" });
    expect(renamed.entries).toHaveLength(1);
    expect(topEntry(renamed)?.title).toBe("Otázka 1 (upravená)");
  });

  it("keeps an item opened again further down: the path is what the person walked", () => {
    let s = openEntry(emptyStack("results"), q1);
    s = openEntry(s, m1);
    s = openEntry(s, q1);
    expect(s.entries.map((e) => e.id)).toEqual(["question:q1", "measure:m1", "question:q1"]);
  });

  it("closes as one, and Back or Close on an empty stack changes nothing", () => {
    const s = openEntry(openEntry(emptyStack("plan"), q1), m1);
    expect(topEntry(closeStack(s))).toBeNull();
    const empty = emptyStack("plan");
    expect(backEntry(empty)).toBe(empty);
    expect(closeStack(empty)).toBe(empty);
  });

  it("belongs to its stage: another stage starts empty, the same stage keeps it", () => {
    const s = openEntry(emptyStack("questionnaire"), q1);
    expect(onStage(s, "questionnaire")).toBe(s);
    const moved = onStage(s, "results");
    expect(moved.stage).toBe("results");
    expect(topEntry(moved)).toBeNull();
  });
});
