// The Lead's edit tools, applied only when a person accepts them (ADR 0026, Accepted with 2): each
// edit goes through the stages' own helpers, and one that no longer fits is refused, never bent.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  applyLeadEdit, autoAcceptIndices, commandRequest, autoAcceptPlan, describeEdit, droppedLines, editRefusalWords, editStage, isTextEdit, leadReasonWords, pendingSelfUpdate, revertTextEdit, targetLabel, textEditInverse, changesToShow, mapViewWords,
  type LeadEdit, type LeadTurn,
} from "./lead";
import type { ResearchProject } from "@/research/model";
import type { ResearchAgentJob } from "./api";
import { itemTargets } from "@/research/plan-narrative";
import type { PlanState } from "@/research/plan";

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
    expect(focusSelector("question:Q_1")).toBe('[data-aia="question:Q_1"], [id="qedit_Q_1"]');
    expect(focusSelector("brief:goal")).toBe('[id="brief-goal"]');
    expect(focusSelector("plan:research_questions")).toBe('[id="plan-understanding"]');
    expect(focusSelector("plan:sets")).toBe('[id="plan-sets"]');
    expect(focusSelector("plan:variants")).toBe('[id="plan-variants"]');
    expect(focusSelector("plan:questions")).toBe('[id="plan-questions"]');
    expect(focusSelector("section:sec_1")).toBe('[data-aia="section:sec_1"], [id="qblock_sec_1"]');
    expect(focusSelector('odd"one')).toBe('[data-aia="odd\\"one"], [id="odd\\"one"]');
  });
});

describe("targetOfElement", () => {
  it("names the nearest element the stage screens identify, from wherever the person clicked", async () => {
    const { targetOfElement } = await import("./lead");
    const { JSDOM } = await import("jsdom");
    const { document } = new JSDOM(`<div data-aia="question:Q_1" id="qedit_Q_1"><span><b id="hit">x</b></span><textarea>Jak jste spokojeni?</textarea></div>
      <section id="brief-goal"><h2>Co potřebujete zjistit</h2><p id="g">text</p></section><div id="none"><i id="n">-</i></div>`).window;
    expect(targetOfElement(document.getElementById("hit"))).toEqual({ id: "question:Q_1", label: "Otázka Q_1: Jak jste spokojeni?" });
    expect(targetOfElement(document.getElementById("g"))).toEqual({ id: "brief:goal", label: "Zadání: Co potřebujete zjistit" });
    expect(targetOfElement(document.getElementById("n"))).toBeNull();
  });

  it("names any element a screen marked with data-aia, nearest first, and ignores other marks", async () => {
    const { targetOfElement } = await import("./lead");
    const { JSDOM } = await import("jsdom");
    const { document } = new JSDOM(`<fieldset data-aia="audience:filter:kraj"><legend>Kraj</legend><input id="k"></fieldset>
      <div data-aia="finding:executive:2"><p id="f">text</p></div><div data-aia="lead-edit.x"><i id="o">-</i></div>`).window;
    expect(targetOfElement(document.getElementById("k"))).toEqual({ id: "audience:filter:kraj", label: "Filtr: kraj: Kraj" });
    expect(targetOfElement(document.getElementById("f"))).toEqual({ id: "finding:executive:2", label: "Zjištění: text" });
    expect(targetOfElement(document.getElementById("o"))).toBeNull();
  });

  it("keeps a marked question's wording and a marked section's title as their labels, whatever heading they hold", async () => {
    // Dotazník marks its cards with data-aia; a card's first legend is a part of it (the research
    // questions it answers), never what the person pointed at.
    const { focusSelector, targetOfElement } = await import("./lead");
    const { JSDOM } = await import("jsdom");
    const { document } = new JSDOM(`<div data-aia="question:Q1" id="qedit_Q1"><textarea id="t">Jak často?</textarea>
        <fieldset><legend>Odpovídá na výzkumné otázky</legend><input id="rq" type="checkbox"></fieldset></div>
      <div data-aia="section:S1" id="qset_S1"><fieldset><legend>Odpovídá na výzkumné otázky</legend></fieldset><h3>Nápoje</h3><i id="s">-</i></div>`).window;
    expect(targetOfElement(document.getElementById("t"))).toEqual({ id: "question:Q1", label: "Otázka Q1: Jak často?" });
    expect(targetOfElement(document.getElementById("rq"))?.label).toBe("Otázka Q1: Jak často?");
    expect(targetOfElement(document.getElementById("s"))).toEqual({ id: "section:S1", label: "Oddíl: Nápoje" });
    // Dotazník edits a block's or set's title in place: an input, not a heading (Codex on #599).
    const edited = new JSDOM(`<article data-aia="section:S2" id="qset_S2"><fieldset><legend>Odpovídá na výzkumné otázky</legend><input type="checkbox" checked></fieldset>
        <input aria-label="Název sady" value="Snídaně"><i id="e">-</i></article>
      <article data-aia="section:B1" id="qblock_B1"><input aria-label="Název bloku" value="Úvod"><i id="b">-</i></article>`).window.document;
    expect(targetOfElement(edited.getElementById("e"))).toEqual({ id: "section:S2", label: "Oddíl: Snídaně" });
    expect(targetOfElement(edited.getElementById("b"))).toEqual({ id: "section:B1", label: "Oddíl: Úvod" });
    // A tracked set's card is found by its mark: it has no qblock_ id.
    expect(document.querySelector(focusSelector("section:S1"))?.id).toBe("qset_S1");
  });

  it("names an item row without a heading by its own words, never its opaque id", async () => {
    const { targetOfElement } = await import("./lead");
    const { JSDOM } = await import("jsdom");
    // The Brief's objective row as it renders: its number, InlineText (the action read by a screen
    // reader, the words in a text button, a pencil icon) and the row's remove button.
    const { document } = new JSDOM(`<ul><li data-aia="objective:obj_6393c6bada"><span aria-hidden="true">1.</span>
      <span><span class="sr-only">Upravit: Cíl 1</span><button aria-labelledby="a t"><span id="o">Změřit   zájem o koncept</span><span aria-hidden="true">✎</span></button></span>
      <button aria-label="Odebrat cíl 1">×</button></li>
      <li data-aia="rq:rq_x" id="r">Kdo nakupuje?</li><div data-aia="audience:preview"><i id="p">1 234</i></div></ul>`).window;
    expect(targetOfElement(document.getElementById("o"))).toEqual({ id: "objective:obj_6393c6bada", label: "Cíl: Změřit zájem o koncept" });
    expect(targetOfElement(document.getElementById("r"))?.label).toBe("Výzkumná otázka: Kdo nakupuje?");
    // A part of a screen keeps its own words (targetLabel), not whatever text it holds.
    expect(targetOfElement(document.getElementById("p"))?.label).toBe("Cílová skupina: náhled");
  });

  it("names nothing for an unmarked duplicate of a marked card (#607 marks the first only)", async () => {
    const { targetOfElement } = await import("./lead");
    const { JSDOM } = await import("jsdom");
    const { document } = new JSDOM(`<div data-aia="question:Q1" id="qedit_Q1"><i id="a">Jak často?</i></div>
      <div id="qedit_Q1"><i id="b">Jak často znovu?</i></div>`).window;
    expect(targetOfElement(document.getElementById("a"))?.id).toBe("question:Q1");
    expect(targetOfElement(document.getElementById("b"))).toBeNull();
  });

  it("names an unmarked card by its DOM id only when the id is a stored one the contract can send", async () => {
    // Before Dotazník marks its cards (#607) a card is named by its DOM id. The ids the screen
    // invents name nothing: a question without an id is qedit_Q (questionElementId's placeholder),
    // a block without one qblock_<index>, and an id like "Q 2" is one the server refuses (Codex on
    // #607; review of #618: a stored id stays pickable whichever PR lands first).
    const { targetOfElement } = await import("./lead");
    const { JSDOM } = await import("jsdom");
    const { document } = new JSDOM(`<div id="qedit_Q"><i id="q">-</i></div><article id="qblock_0"><i id="b">-</i></article>
      <div id="qedit_Q 2"><i id="s">-</i></div>`).window;
    expect(targetOfElement(document.getElementById("q"))).toBeNull();
    expect(targetOfElement(document.getElementById("b"))).toBeNull();
    expect(targetOfElement(document.getElementById("s"))).toBeNull();
    const stored = new JSDOM(`<div id="qedit_q1"><textarea id="w">Jak často?</textarea></div>
      <article id="qblock_B1"><h3>Úvod</h3><i id="x">-</i></article>`).window.document;
    expect(targetOfElement(stored.getElementById("w"))).toEqual({ id: "question:q1", label: "Otázka q1: Jak často?" });
    expect(targetOfElement(stored.getElementById("x"))).toEqual({ id: "section:B1", label: "Oddíl: Úvod" });
  });
});

describe("composerHint", () => {
  it("says why the composer is shut, the person's own reason first, unknown as loading", async () => {
    const { composerHint } = await import("./lead");
    const at = (over: Partial<Parameters<typeof composerHint>[0]>) => composerHint({ canEdit: true, hatched: true, available: true, failed: false, ...over });
    expect(at({})).toBeNull();
    expect(at({ canEdit: false, hatched: false, available: false })).toMatch(/Jen ke čtení/);
    expect(at({ hatched: false })).toMatch(/vylíhněte/);
    expect(at({ available: false })).toMatch(/neodpovídá/);
    expect(at({ hatched: undefined, available: undefined })).toMatch(/Načítám/);
    // A refused read never reads as loading for ever (review of the audit branch).
    expect(at({ available: undefined, failed: true })).toMatch(/nepodařilo načíst/);
  });
});

describe("targetLabel for every artifact's kinds", () => {
  it("says each kind in words, and the audience's parts as the Cílová skupina screen names them", () => {
    expect(targetLabel("audience:definition")).toBe("Cílová skupina: popis");
    expect(targetLabel("audience:subpanel:young_18_29")).toBe("Podpanel: young_18_29");
    expect(targetLabel("audience:filter:kraj")).toBe("Filtr: kraj");
    // Read by Cílová skupina's own parser: a filter or subpanel with no name is no filter.
    expect(targetLabel("audience:filter:")).toBe("Cílová skupina: filter:");
    expect(targetLabel("audience:subpanel:")).toBe("Cílová skupina: subpanel:");
    expect(targetLabel("pair:set1/fio~air")).toBe("Dvojice set1/fio~air");
    expect(targetLabel("measure:q3")).toBe("Měření q3");
    expect(targetLabel("receipt:respondents")).toBe("Kdo odpovídal");
    expect(targetLabel("nonsense:q3")).toBe("nonsense:q3");
  });
});

describe("changesToShow", () => {
  const job = (run_id: string, action: string, proposal_state: string, created_at: string) => ({ run_id, action, proposal_state, created_at }) as unknown as ResearchAgentJob;
  const jobs = [
    job("RUN-old", "build_questionnaire", "pending", "2026-10-22T08:00:00Z"),
    job("RUN-new", "optimize_questionnaire", "pending", "2026-10-22T09:00:00Z"),
    job("RUN-done", "optimize_questionnaire", "accepted", "2026-10-22T10:00:00Z"),
    job("RUN-plan", "analyze_brief", "pending", "2026-10-22T11:00:00Z"),
  ];
  it("shows the Lead's waiting edits first, then the stage's newest proposal still waiting, else nothing", () => {
    expect(changesToShow("questionnaire", ["questionnaire"], jobs)).toEqual({ kind: "edits" });
    expect(changesToShow("questionnaire", ["design"], jobs)).toEqual({ kind: "proposal", job: jobs[1] });
    expect(changesToShow("design", [], jobs)).toEqual({ kind: "proposal", job: jobs[3] });
    expect(changesToShow("dimensions", ["design"], jobs)).toBeNull();
  });
});

describe("mapViewWords", () => {
  it("says what the map's picture becomes, never a filter's code", () => {
    expect(mapViewWords({ op: "filter", name: "view", value: "relief" })).toBe("Mapa: reliéf");
    expect(mapViewWords({ op: "filter", name: "view", value: "top" })).toBe("Mapa: shora");
    expect(mapViewWords({ op: "filter", name: "hide_weak", value: "on" })).toBe("Mapa: skrýt slabé vztahy");
    expect(mapViewWords({ op: "filter", name: "mode", value: "respondents" })).toBe("Mapa respondentů");
    expect(mapViewWords({ op: "select", target: "pair:set1/fio~air" })).toBe("Vybrat: Dvojice set1/fio~air");
  });
});

describe("targetLabel with the working copy (F18)", () => {
  it("names a research question or a hypothesis by its words, and by its id only when the copy does not hold it", () => {
    const project = { research_plan: { research_questions: ["Kdo kupuje?"], hypotheses: ["Mladší kupují častěji než starší, kteří zůstávají u své oblíbené značky déle."] } };
    const [rq] = itemTargets({ project, analysis: null } as unknown as PlanState).research_questions;
    const [hyp] = itemTargets({ project, analysis: null } as unknown as PlanState).hypotheses;
    expect(targetLabel(rq!, { project, analysis: null })).toBe("Výzkumná otázka: Kdo kupuje?");
    expect(targetLabel(hyp!, { project, analysis: null })).toBe("Hypotéza: Mladší kupují častěji než starší, kteří zůstávají u své o…");
    expect(targetLabel("hypothesis:hyp_none", { project, analysis: null })).toBe("Hypotéza hyp_none");
    expect(targetLabel(hyp!)).toBe(`Hypotéza ${hyp!.split(":")[1]}`);
  });
});

describe("targetLabel", () => {
  it("says a Lead target in words, never the raw code for a kind it knows", () => {
    expect(targetLabel("question:Q_1")).toBe("Otázka Q_1");
    expect(targetLabel("section:B1")).toBe("Oddíl B1");
    expect(targetLabel("plan:variants")).toBe("Návrh: varianty výzkumu");
    expect(targetLabel("plan:narrative")).toBe("Návrh: porozumění zadání");
    // Zadání's sections by the words its screen gives them (F18), an unknown one by its name.
    expect(targetLabel("brief:goal")).toBe("Zadání: Cíl");
    expect(targetLabel("brief:title")).toBe("Zadání: Název");
    expect(targetLabel("brief:briefing.situation")).toBe("Zadání: Situace");
    expect(targetLabel("brief:files")).toBe("Zadání: Podklady");
    expect(targetLabel("brief:elsewhere")).toBe("Zadání: elsewhere");
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

describe("commandRequest", () => {
  it("reads the start the server matched, the instruction after a colon as its why, and nothing it does not know", () => {
    expect(commandRequest({ command: "agent_job:build_questionnaire", text: "Navrhni dotazník: krátce, 10 otázek" })).toEqual({ kind: "agent_job", action: "build_questionnaire", why: "krátce, 10 otázek" });
    expect(commandRequest({ command: "research_run", text: "Spusť výzkum" })).toEqual({ kind: "research_run", why: "Spustí se až vaším potvrzením." });
    expect(commandRequest({ command: "analysis_retry", text: "Zopakuj analýzu" })).toEqual({ kind: "analysis_retry", why: "Spustí se až vaším potvrzením." });
    for (const command of [null, undefined, "", "agent_job:", "deep_research"]) expect(commandRequest({ command, text: "x" })).toBeNull();
  });
});

describe("leadReasonWords", () => {
  it("says who fixes a refusal of the AI route, which a researcher cannot (LO12a)", () => {
    expect(leadReasonWords("egress_route_not_approved_for_class")).toMatch(/^Tuto studii nelze poslat modelu: .* Opraví to provozovatel AIA, ne výzkumník: nastaví parametr aia_ai_route_approved_for/);
    expect(leadReasonWords("budget_exceeded")).not.toContain("provozovatel");
  });

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
