// The Lead's edit tools, applied only when a person accepts them (ADR 0026, Accepted with 2): each
// edit goes through the stages' own helpers, and one that no longer fits is refused, never bent.
import { describe, expect, it } from "vitest";

import { applyLeadEdit, describeEdit, editStage, type LeadEdit } from "./lead";
import type { ResearchProject } from "@/research/model";

const project = (over: Partial<ResearchProject> = {}): ResearchProject => ({
  title: "Studie",
  goal: "Zjistit, proč klienti odcházejí",
  briefing: { situation: "Odchody rostou" },
  research_plan: { research_questions: ["Proč klienti odcházejí?"], objectives: [], hypotheses: [] },
  study_config: {}, instrument_library: {}, audience: {}, discovery: {}, budget: {}, run_policy: {}, ui_state: {},
  sections: [{ id: "sec_1", type: "questions", title: "Hlavní", questions: [{ id: "Q_1", text: "Jak jste spokojeni?", typ: "vyber", kategorie: ["Ano", "Ne"] }] }],
  ...over,
});
const content = (p = project()) => ({ project: p, analysis: null });
const ok = (r: ReturnType<typeof applyLeadEdit>) => {
  if ("refused" in r) throw new Error(r.refused);
  return r.content;
};

describe("applyLeadEdit", () => {
  it("sets a brief field through editBrief, which drops the analysis as a person's edit does", () => {
    const c = ok(applyLeadEdit({ project: project(), analysis: { problem_summary: "x" } }, { op: "set_text", field: "briefing.situation", value: "Odchody rostou o čtvrtinu", why: "" }));
    expect(c.project.briefing.situation).toBe("Odchody rostou o čtvrtinu");
    expect(c.analysis).toBeNull();
  });

  it("changes a plan list in the project and the analysis together", () => {
    const c = ok(applyLeadEdit(content(), { op: "list_add", list: "plan.research_questions", value: "Kdo odchází nejdřív?", why: "" }));
    expect(c.project.research_plan.research_questions).toEqual(["Proč klienti odcházejí?", "Kdo odchází nejdřív?"]);
    expect(c.analysis?.research_questions).toEqual(["Proč klienti odcházejí?", "Kdo odchází nejdřív?"]);
    const r = ok(applyLeadEdit(c, { op: "list_replace", list: "plan.research_questions", old: "  proč klienti ODCHÁZEJÍ? ", value: "Proč odcházejí?", why: "" }));
    expect(r.project.research_plan.research_questions).toEqual(["Proč odcházejí?", "Kdo odchází nejdřív?"]);
  });

  it("refuses an edit whose item is gone or already there", () => {
    expect(applyLeadEdit(content(), { op: "list_remove", list: "plan.hypotheses", old: "Neexistuje", why: "" })).toHaveProperty("refused");
    expect(applyLeadEdit(content(), { op: "list_add", list: "plan.research_questions", value: "proč klienti odcházejí?", why: "" })).toHaveProperty("refused");
    expect(applyLeadEdit(content(), { op: "question_edit", question_id: "Q_404", text: "x", options: null, why: "" })).toHaveProperty("refused");
    expect(applyLeadEdit(content(), { op: "question_add", section_id: "sec_404", text: "x", qtype: "otevrena", options: [], why: "" })).toHaveProperty("refused");
  });

  it("adds, edits and removes a question by its id", () => {
    const added = ok(applyLeadEdit(content(), { op: "question_add", section_id: null, text: "Doporučili byste nás?", qtype: "skala", options: [], why: "" }, () => "Q_new"));
    expect(added.project.sections[0]).toMatchObject({ questions: [{ id: "Q_1" }, { id: "Q_new", typ: "skala", skala: [1, 10] }] });
    const edited = ok(applyLeadEdit(added, { op: "question_edit", question_id: "Q_1", text: "Jak jste spokojeni s bankou?", options: ["Ano", "Spíše ano", "Ne"], why: "" }));
    expect(edited.project.sections[0]).toMatchObject({ questions: [{ id: "Q_1", text: "Jak jste spokojeni s bankou?", kategorie: ["Ano", "Spíše ano", "Ne"] }, { id: "Q_new" }] });
    const removed = ok(applyLeadEdit(edited, { op: "question_remove", question_id: "Q_new", why: "" }));
    expect((removed.project.sections[0] as { questions: unknown[] }).questions).toHaveLength(1);
  });

  it("makes the first question block when there is none", () => {
    const c = ok(applyLeadEdit(content(project({ sections: [] })), { op: "question_add", section_id: null, text: "Věk?", qtype: "otevrena", options: [], why: "" }, () => "Q_x"));
    expect(c.project.sections).toMatchObject([{ type: "questions", title: "Hlavní otázky", questions: [{ id: "Q_x", typ: "otevrena" }] }]);
  });

  it("sets the sample size", () => {
    expect(ok(applyLeadEdit(content(), { op: "set_n", value: 800, why: "" })).project.n).toBe(800);
  });
});

describe("describeEdit / editStage", () => {
  it("names what changes, from what and to what, and where the change block goes", () => {
    const e: LeadEdit = { op: "question_edit", question_id: "Q_1", text: "Jak moc jste spokojeni?", options: null, why: "" };
    expect(describeEdit(content(), e)).toEqual({ where: "Dotazník · upravit otázku", before: "Jak jste spokojeni?", after: "Jak moc jste spokojeni?" });
    expect(describeEdit(content(), { op: "set_text", field: "goal", value: "Nový cíl", why: "" })).toEqual({ where: "Cíl", before: "Zjistit, proč klienti odcházejí", after: "Nový cíl" });
    expect(editStage(e)).toBe("questionnaire");
    expect(editStage({ op: "set_text", field: "plan.problem_summary", value: "", why: "" })).toBe("design");
    expect(editStage({ op: "set_n", value: 500, why: "" })).toBe("dimensions");
  });
});

describe("focusSelector", () => {
  it("names the element the stage screens already render for a target", async () => {
    const { focusSelector } = await import("./lead");
    expect(focusSelector("question:Q_1")).toBe('[id="qedit_Q_1"]');
    expect(focusSelector("brief:goal")).toBe('[id="brief-goal"]');
    expect(focusSelector("plan:research_questions")).toBe('[id="plan-understanding"]');
    expect(focusSelector("plan:sets")).toBe('[id="plan-sets"]');
    expect(focusSelector("plan:variants")).toBe('[id="plan-variants"]');
    expect(focusSelector("plan:questions")).toBe('[id="plan-questions"]');
    expect(focusSelector("section:sec_1")).toBe('[id="qblock_sec_1"]');
    expect(focusSelector('odd"one')).toBe('[data-aia="odd\\"one"], [id="odd\\"one"]');
  });
});

describe("targetOfElement", () => {
  it("names the nearest element the stage screens identify, from wherever the person clicked", async () => {
    const { targetOfElement } = await import("./lead");
    const { JSDOM } = await import("jsdom");
    const { document } = new JSDOM(`<div id="qedit_Q_1"><span><b id="hit">x</b></span><textarea>Jak jste spokojeni?</textarea></div>
      <section id="brief-goal"><h2>Co potřebujete zjistit</h2><p id="g">text</p></section><div id="none"><i id="n">-</i></div>`).window;
    expect(targetOfElement(document.getElementById("hit"))).toEqual({ id: "question:Q_1", label: "Otázka Q_1: Jak jste spokojeni?" });
    expect(targetOfElement(document.getElementById("g"))).toEqual({ id: "brief:goal", label: "Zadání: Co potřebujete zjistit" });
    expect(targetOfElement(document.getElementById("n"))).toBeNull();
  });
});
