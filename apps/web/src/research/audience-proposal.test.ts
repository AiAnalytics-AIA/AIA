import { describe, expect, it } from "vitest";
import { audienceProposalDiff } from "./audience-proposal";
import type { ResearchProject } from "./model";

const project = (audience: Record<string, unknown>) => ({ audience }) as unknown as Pick<ResearchProject, "audience">;

describe("an audience proposal against the audience there is now", () => {
  it("names a new description, every criterion of a first proposal, and what it leaves uncovered", () => {
    const d = audienceProposalDiff(project({ description: "Mladí" }), { description: "Lidé 18–35", inclusion_criteria: ["Věk 18–35"], exclusion_criteria: ["Zaměstnanci bank"], limitations: ["Bez dat o klientech"], questions_for_user: ["Studenti?"] });
    expect(d.description).toEqual({ before: "Mladí", after: "Lidé 18–35" });
    expect(d.inclusion).toEqual({ added: ["Věk 18–35"], removed: [], kept: 0 });
    expect(d.exclusion.added).toEqual(["Zaměstnanci bank"]);
    expect(d.notes).toEqual(["Bez dat o klientech", "Studenti?"]);
    expect(d.changes).toBe(3);
  });

  it("against an earlier accepted proposal names only what moved; spacing alone is no change", () => {
    const now = project({ description: "Lidé 18–35", ai_proposal: { inclusion_criteria: ["Věk 18–35", "Má účet"], exclusion_criteria: [] } });
    const d = audienceProposalDiff(now, { description: " Lidé 18–35 ", inclusion_criteria: ["věk 18–35", "Má účet ", "Žije v ČR"], exclusion_criteria: [] });
    expect(d.description).toBeNull();
    expect(d.inclusion).toEqual({ added: ["Žije v ČR"], removed: [], kept: 2 });
    expect(d.changes).toBe(1);
  });

  it("reads a missing description or list as nothing, never as a change", () => {
    expect(audienceProposalDiff(project({}), { description: "", inclusion_criteria: "x", exclusion_criteria: [null, " "] })).toMatchObject({ description: null, changes: 0, notes: [] });
  });
});
