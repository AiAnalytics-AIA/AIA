import { describe, expect, it } from "vitest";

import { briefReadiness } from "./brief-readiness";
import type { ResearchProject } from "./model";

const project = (over: Partial<ResearchProject> = {}) =>
  ({ goal: "", decision_use: "", briefing: {}, research_plan: {}, ...over }) as unknown as ResearchProject;

describe("briefReadiness", () => {
  it("a chip per section in page order; optional never waits; no percentage", () => {
    const chips = briefReadiness({ project: project(), analysis: null });
    expect(chips.map((c) => c.target)).toEqual(["brief-goal", "brief-objectives", "brief-decision_use", "brief-type", "brief-context", "brief-files"]);
    expect(chips.map((c) => c.state)).toEqual(["you", "you", "you", "you", "optional", "optional"]);
    expect(chips.filter((c) => !c.required).every((c) => c.state !== "you")).toBe(true);
    expect(JSON.stringify(chips)).not.toMatch(/%|score/);
  });

  it("an objectives list the page cannot read is unknown, never waiting and never done (stand-in review on #938)", () => {
    const chips = briefReadiness({ project: project({ research_plan: { objectives: [{ text: "Změřit zájem" }] } } as unknown as Partial<ResearchProject>), analysis: null });
    expect(chips.find((c) => c.target === "brief-objectives")!.state).toBe("unknown");
  });

  it("a section the brief answers is done, a whitespace-only one is not", () => {
    const chips = briefReadiness({
      project: project({
        goal: "Zjistit zájem.",
        decision_use: "   ",
        briefing: { problem_types: ["campaign"], situation: "Trh roste", attachments: [{ kind: "url", url: "https://example.invalid" }] },
        research_plan: { objectives: ["Změřit zájem"] },
      } as Partial<ResearchProject>),
      analysis: null,
    });
    expect(Object.fromEntries(chips.map((c) => [c.target, c.state]))).toEqual({
      "brief-goal": "done",
      "brief-objectives": "done",
      "brief-decision_use": "you",
      "brief-type": "done",
      "brief-context": "done",
      "brief-files": "done",
    });
  });
});
