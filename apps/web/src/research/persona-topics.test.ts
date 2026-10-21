import { describe, expect, it } from "vitest";

import { dimensionTarget, dimensionTopic, dimensionTopicWords } from "./persona";

describe("a chosen dimension's persona topic (artifact-dimensions DIM2)", () => {
  it("reads the server's answer: a topic, none, or not answered yet", () => {
    const topics = { ekologie: "eko", barva_obalu: null };
    expect(dimensionTopic(topics, "ekologie")).toEqual({ state: "matched", topic: "eko" });
    expect(dimensionTopic(topics, "barva_obalu")).toEqual({ state: "unmatched" });
    expect(dimensionTopic(topics, "media")).toEqual({ state: "unknown" });
    expect(dimensionTopic(null, "ekologie")).toEqual({ state: "unknown" });
  });

  it("says V2's words, and never reads an unanswered dimension as matched", () => {
    expect(dimensionTopicWords({ state: "matched", topic: "eko" })).toBe("téma persony: eko");
    expect(dimensionTopicWords({ state: "unmatched" })).toBe("bez tématu persony");
    expect(dimensionTopicWords({ state: "unknown" })).toBe("téma persony neověřeno");
  });

  it("points at a dimension only with an id the Lead's grammar takes", () => {
    expect(dimensionTarget("ekologie")).toBe("dimension:ekologie");
    expect(dimensionTarget("KNI-ai")).toBe("dimension:KNI-ai");
    expect(dimensionTarget("Úplně nová věc")).toBeNull();
    expect(dimensionTarget("x".repeat(81))).toBeNull();
  });
});
