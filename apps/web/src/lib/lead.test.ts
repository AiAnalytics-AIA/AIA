// The Lead's edit tools, applied only when a person accepts them (ADR 0026, Accepted with 2): each
// edit goes through the stages' own helpers, and one that no longer fits is refused, never bent.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  applyLeadEdit, autoAcceptIndices, autoAcceptPlan, describeEdit, droppedLines, editRefusalWords, editStage, isTextEdit, leadReasonWords, pendingSelfUpdate, revertTextEdit, targetLabel, textEditInverse,
  type LeadEdit, type LeadTurn,
} from "./lead";
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
const ok = (r: ReturnType<typeof applyLeadEdit> | ReturnType<typeof revertTextEdit>) => {
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

describe("targetLabel", () => {
  it("says a Lead target in words, never the raw code for a kind it knows", () => {
    expect(targetLabel("question:Q_1")).toBe("Otázka Q_1");
    expect(targetLabel("section:B1")).toBe("Oddíl B1");
    expect(targetLabel("plan:variants")).toBe("Návrh: varianty výzkumu");
    expect(targetLabel("plan:narrative")).toBe("Návrh: porozumění zadání");
    expect(targetLabel("brief:goal")).toBe("Zadání: goal");
    expect(targetLabel("somewhere")).toBe("somewhere");
  });
});

describe("pendingSelfUpdate", () => {
  it("lists what waits as the server split it: personal notes kept and forgotten, and files", () => {
    expect(pendingSelfUpdate({ name: "Bára", soul: null, user: "U", remember: ["P"], forget: [{ memory_id: "LMM-1", text: "Stará osobní" }, { memory_id: "LMM-2", text: null }] })).toEqual({
      notes: ["P"],
      forget: ["Stará osobní", "poznámka LMM-2"],
      files: [{ file: "Jméno", text: "Bára" }, { file: "USER", text: "U" }],
    });
    expect(pendingSelfUpdate(null)).toEqual({ notes: [], forget: [], files: [] });
  });
});

describe("automatic text edits (inline-decisions 2)", () => {
  const text: LeadEdit[] = [
    { op: "set_text", field: "title", value: "Nový název", why: "" },
    { op: "list_replace", list: "plan.hypotheses", old: "Odcházejí kvůli cenám", value: "Odcházejí kvůli poplatkům", why: "" },
    { op: "question_edit", question_id: "Q_1", text: "Jak jste spokojeni se službou?", options: null, why: "" },
  ];
  const structure: LeadEdit[] = [
    // A brief field's edit drops the analysis; a research question is named by its text.
    { op: "set_text", field: "goal", value: "Nový cíl", why: "" },
    { op: "set_text", field: "briefing.situation", value: "Jinak", why: "" },
    { op: "list_replace", list: "plan.research_questions", old: "Proč klienti odcházejí?", value: "Proč odcházejí?", why: "" },
    // Objectives are read as the research questions where a plan states none.
    { op: "list_replace", list: "plan.objectives", old: "Snížit odchody", value: "Snížit odchody klientů", why: "" },
    { op: "list_add", list: "plan.objectives", value: "Cíl", why: "" },
    { op: "list_remove", list: "plan.hypotheses", old: "H", why: "" },
    { op: "question_add", section_id: null, text: "Kolik?", qtype: "otevrena", options: [], why: "" },
    { op: "question_edit", question_id: "Q_1", text: null, options: ["A", "B"], why: "" },
    { op: "question_edit", question_id: "Q_1", text: "Jinak", options: ["A", "B"], why: "" },
    { op: "question_remove", question_id: "Q_1", why: "" },
    { op: "set_n", value: 400, why: "" },
  ];
  const turn = (over: Partial<LeadTurn> = {}): LeadTurn => ({
    turn_id: "LDT-1", sequence_no: 1, actor: "lead", kind: "message", stage: "brief", text: null, focus: null, status: "COMPLETED",
    reason: null, output: { reply: "", edits: [...text, ...structure] }, run_id: "RUN-1", workspace_revision: 1, created_at: "", created_by: null, ...over,
  });

  it("names wording edits as the server's TEXT_EDIT_OPS do, and nothing structural", () => {
    expect(text.map(isTextEdit)).toEqual([true, true, true]);
    expect(structure.map(isTextEdit)).toEqual(structure.map(() => false));
  });

  it("asks only for a finished turn's undecided text edits", () => {
    expect(autoAcceptIndices(turn())).toEqual([0, 1, 2]);
    expect(autoAcceptIndices(turn({ edit_decisions: { "1": { status: "dismissed", reason: null } } }))).toEqual([0, 2]);
    expect(autoAcceptIndices(turn({ status: "RUNNING" }))).toEqual([]);
  });

  it("is off unless chosen, and never replays a turn that had finished when the screen opened", () => {
    const turns = [turn(), turn({ turn_id: "LDT-2" })];
    expect(autoAcceptPlan(turns, false, new Set(), new Set())).toEqual([]);
    expect(autoAcceptPlan(turns, true, new Set(["LDT-1"]), new Set())).toEqual([{ turnId: "LDT-2", indices: [0, 1, 2] }]);
    expect(autoAcceptPlan(turns, true, new Set(["LDT-1"]), new Set(["LDT-2"]))).toEqual([]);
  });

  it("puts the replaced wording back, and refuses when the text changed since", () => {
    const before = content(project({ research_plan: { research_questions: ["Proč klienti odcházejí?"], objectives: [], hypotheses: ["Odcházejí kvůli cenám"] } }));
    for (const e of text) {
      const inverse = textEditInverse(before, e)!;
      const after = ok(applyLeadEdit(before, e));
      const back = ok(revertTextEdit(after, e, inverse));
      expect(describeEdit(back, e).before ?? "").toBe(describeEdit(before, e).before ?? "");
    }
    const e = text[2]!;
    const inverse = textEditInverse(before, e)!;
    const edited = ok(applyLeadEdit(before, { op: "question_edit", question_id: "Q_1", text: "Přepsáno výzkumníkem", options: null, why: "" }));
    expect(revertTextEdit(edited, e, inverse)).toHaveProperty("refused");
  });
});

describe("a refused or dropped edit says why in words (RQC9)", () => {
  it("names a sample size outside the valid range and unknown limits, never the code", () => {
    expect(editRefusalWords("sample_size_out_of_range")).toContain("mimo platný rozsah");
    expect(editRefusalWords("sample_size_limits_unknown")).toContain("nepodařilo zjistit");
    expect(editRefusalWords("unknown_question")).toBe("Otázka, kterou návrh mění, už v dotazníku není.");
    expect(editRefusalWords(null)).toBe("Úpravu už nelze použít.");
    expect(editRefusalWords("something_new")).toBe("something_new"); // kept, never guessed
  });
  it("has words for every refusal the server's vocabulary names", () => {
    const file = JSON.parse(readFileSync(join(process.cwd(), "../../packages/aia_core/tests/fixtures/edit_ops/cases.json"), "utf8")) as { refusals: string[] };
    for (const code of file.refusals) expect(editRefusalWords(code)).not.toBe(code);
  });
  it("a dropped sample size is its own line; the rest are counted as before", () => {
    expect(droppedLines([{ reason: "sample_size_out_of_range" }, { reason: "unknown_question" }])).toEqual([
      editRefusalWords("sample_size_out_of_range"),
      "1 navržená změna se netýkala ničeho v pracovní kopii a byla vynechána.",
    ]);
    expect(droppedLines([{ reason: "unknown_item" }, { reason: "unknown_question" }])).toEqual([
      "2 navržené změny se netýkaly ničeho v pracovní kopii a byly vynechány.",
    ]);
  });
});

describe("leadReasonWords", () => {
  it("says what to do about a turn parked on the study's budget, by the code the server sends", () => {
    // The server's waiting reason is budget_exceeded; AWAITING_BUDGET is a step status it never sends.
    expect(leadReasonWords("budget_exceeded")).toContain("Nastavení → Studie");
    // Setting the budget sends the message by itself (the product owner, 2026-10-21, Q39).
    expect(leadReasonWords("budget_exceeded")).toContain("odešle sama");
    expect(leadReasonWords("budget_exceeded")).not.toContain("budget_exceeded");
  });
  it("says a superseded turn's message was read with the next one", () => {
    expect(leadReasonWords("CANCELLED")).toContain("další zprávou");
  });
  it("names an unknown code rather than guessing", () => {
    expect(leadReasonWords("something_new")).toBe("Vedoucí se zastavil (something_new).");
    expect(leadReasonWords(null)).toBe("Vedoucí se zastavil.");
  });
});
