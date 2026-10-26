// A removed Návrh comment taken back (artifact-design DSN14).
import { describe, expect, it } from "vitest";

import type { ResearchProject } from "./model";
import { planComments, removeComment, restoreComment } from "./plan";

const a = { quote: "cíl", comment: "zúžit na Prahu" };
const b = { quote: "test", comment: "upřesnit" };
const project = (comments: unknown[]) => ({ ui_state: { plan_comments26: comments } }) as unknown as ResearchProject;

describe("restoreComment", () => {
  it("puts a removed comment back where it stood", () => {
    const removed = removeComment(project([a, b]), 0);
    expect(planComments(restoreComment(removed, a, 0))).toEqual([a, b]);
  });

  it("never adds a second copy of a comment the list still holds", () => {
    const p = project([a, b]);
    expect(restoreComment(p, a, 0)).toBe(p);
  });
});
