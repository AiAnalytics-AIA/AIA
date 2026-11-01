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
    expect(planComments(restoreComment(removed, a, 0, 1))).toEqual([a, b]);
  });

  it("never adds a copy the list still holds, and takes back one of two equal comments", () => {
    const p = project([a, b]);
    expect(restoreComment(p, a, 0, 1)).toBe(p);
    const twice = removeComment(project([a, a, b]), 1);
    expect(planComments(restoreComment(twice, a, 1, 2))).toEqual([a, a, b]);
  });
});
