import { describe, expect, it } from "vitest";

import type { MemoryHit } from "./api";
import { evidence, ofKind, sendable } from "./memory";

const hit = (over: Partial<MemoryHit> = {}): MemoryHit => ({
  study_id: "STU-1",
  name: "Ranní káva",
  kind: "RESEARCH",
  status: "ACTIVE",
  modified_at: null,
  source: "design",
  design_revision: 1,
  matches: [
    { field: "name", texts: ["Ranní káva"] },
    { field: "research_questions", texts: ["Kdo pije kávu ráno?", "Kde ji kupuje?"] },
    { field: "dimensions", texts: ["Zdraví"] },
  ],
  ...over,
});

describe("project memory search", () => {
  it("sends nothing shorter than two characters", () => {
    expect(sendable(" k ")).toBeNull();
    expect(sendable("  ká ")).toBe("ká");
  });

  it("keeps the hits of one kind, or all", () => {
    const hits = [hit(), hit({ study_id: "STU-2", kind: "SIMULATION" })];
    expect(ofKind(hits, "RESEARCH").map((h) => h.study_id)).toEqual(["STU-1"]);
    expect(ofKind(hits, null)).toHaveLength(2);
  });

  it("says what matched, without repeating the study's name", () => {
    expect(evidence(hit())).toEqual([
      { field: "research_questions", text: "Kdo pije kávu ráno?" },
      { field: "research_questions", text: "Kde ji kupuje?" },
      { field: "dimensions", text: "Zdraví" },
    ]);
    expect(evidence(hit({ matches: [{ field: "name", texts: ["Ranní káva"] }] }))).toEqual([]);
  });
});
