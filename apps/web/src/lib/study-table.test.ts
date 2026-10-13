import { describe, expect, it } from "vitest";

import { brought, countByFilter, inFilter, narrowFilterOf, sortStudies } from "./study-table";

const s = (name: string, status: string, modified_at: string | null = null) => ({ name, status, modified_at });

describe("which filter a study falls under", () => {
  it("puts each status under one narrow filter, an unknown one under open rather than nowhere", () => {
    expect(["DRAFT", "ACTIVE", "SOMETHING_NEW"].map(narrowFilterOf)).toEqual(["open", "open", "open"]);
    expect(narrowFilterOf("IN_REVIEW")).toBe("review");
    expect(narrowFilterOf("DELIVERED")).toBe("delivered");
    expect(["ARCHIVED", "CANCELLED"].map(narrowFilterOf)).toEqual(["archived", "archived"]);
  });

  it("shows everything but the archived and the cancelled by default", () => {
    expect(["DRAFT", "ACTIVE", "IN_REVIEW", "DELIVERED"].every((st) => inFilter(s("x", st), "current"))).toBe(true);
    expect(inFilter(s("x", "ARCHIVED"), "current")).toBe(false);
    expect(inFilter(s("x", "CANCELLED"), "current")).toBe(false);
  });

  it("counts every filter, the default one included", () => {
    const list = [s("a", "ACTIVE"), s("b", "DRAFT"), s("c", "IN_REVIEW"), s("d", "DELIVERED"), s("e", "ARCHIVED")];
    expect(countByFilter(list)).toEqual({ current: 4, open: 2, review: 1, delivered: 1, archived: 1 });
  });
});

describe("the order of a client's studies", () => {
  it("puts the newest change first and a study with no time last, without touching the list", () => {
    const list = [s("old", "ACTIVE", "2026-01-01T00:00:00Z"), s("none", "ACTIVE"), s("new", "ACTIVE", "2026-10-01T00:00:00Z")];
    expect(sortStudies(list, "modified").map((x) => x.name)).toEqual(["new", "old", "none"]);
    expect(list.map((x) => x.name)).toEqual(["old", "none", "new"]);
  });

  it("orders names the Czech way: č after c, ch after h", () => {
    const list = [s("Chování", "ACTIVE"), s("Čeština", "ACTIVE"), s("Cena", "ACTIVE"), s("Hypotéky", "ACTIVE")];
    expect(sortStudies(list, "name").map((x) => x.name)).toEqual(["Cena", "Čeština", "Hypotéky", "Chování"]);
  });
});

describe("what a study brought into the client's knowledge", () => {
  it("is what was accepted and what still waits; what was turned down is not counted", () => {
    expect(brought({ knowledge: { approved: 2, proposed: 1, rejected: 4 } })).toEqual({ accepted: 2, waiting: 1 });
  });

  it("is unknown, not nothing, when the API did not say", () => {
    expect(brought({ knowledge: null })).toBeNull();
    expect(brought({})).toBeNull();
  });
});
