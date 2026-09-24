import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { effective, legacyContext, statement } from "../testing/legacy";
import { type Boot, type ResearchProject, defaultsMerge } from "./model";
import {
  ANSWERS_EMPTY,
  CONFIRM_REMOVE_SET,
  PROMPT_COMMENT,
  PROMPT_OBJECT,
  PROMPT_RENAME,
  PROMPT_SET_OBJECTS,
  PROMPT_SET_TITLE,
  SET_FULL,
  SET_PURPOSE_DEFAULT,
  type TrackedSet,
  addComment,
  addObject,
  addSet,
  answerFollowUps,
  applyVariant,
  commentsToReview,
  comparableFamily,
  followUps,
  objectQuestionRows,
  planComments,
  projectVariants,
  removeComment,
  removeObject,
  removeSet,
  renameSet,
  setTitle,
  toQuestionnaire,
} from "./plan";
import type { Analysis } from "./store";

// Návrh against the classic interface's own functions, run under Node with the
// prompts, the save and the render stubbed and recorded.
const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/unit/research/fixtures/empty-project.json"), "utf8"));
const BOOT: Boot = { empty_project: EMPTY, ai_provider: "claude_code_subscription" };

const legacy = legacyContext({
  prelude: [
    "var window=globalThis;const clone=x=>JSON.parse(JSON.stringify(x));",
    "var CURRENT='plan',SAVES=[],ALERTS=[],TOASTS=[],PROMPTS=[],ASKED=[],CONFIRM=true,CONFIRMS=[],ANALYSES=[],GONE=[],ANSWERS='',ANALYSIS=null,PROJECT=null;",
    "function save(r,inv){SAVES.push([r||'autosave',inv!==false])}function renderPlan(){}function renderComments26(){}",
    "function alert(m){ALERTS.push(m)}function toast(m){TOASTS.push(m)}function go(r){GONE.push(r)}",
    "function prompt(m,d){ASKED.push([m,d===undefined?null:d]);return PROMPTS.shift()}function confirm(m){CONFIRMS.push(m);return CONFIRM}",
    "function $(s){return {value:ANSWERS}}function E(x){return String(x)}",
    "async function analyzeBrief(){ANALYSES.push('brief')}async function ensureAnalysis1776(force){ANALYSES.push(force)}",
    "function ee26(x){return String(x)}",
    statement("function comments26(){", "}\n"),
    statement("window.npcRemoveComment26=", "};"),
    statement("window.npcProcessComments26=async function(){", "}};"),
  ],
  functions: [
    "comparableFamily",
    "renderObjectSet",
    "addPlanSet",
    "addPlanObject",
    "renamePlanSet",
    "removePlanSet",
    "removePlanObject",
    "projectVariants1793",
    "applyProjectVariant1793",
    "reanalyze",
    "setQuestionnairePath",
  ],
});

const base = defaultsMerge({ goal: "Zjistit zájem" }, BOOT);
const SETS: TrackedSet[] = [
  {
    title: "Varianty nápoje",
    object_type: "varianta",
    purpose: "čtyři varianty",
    objects: ["A", "B", "C", "D", "E", "F", "G"],
    object_question: "Jak vás oslovuje {object}? A {object}?",
    scale_labels: ["vůbec", "velmi"],
  },
  { title: "Kraje", object_type: "region", objects: [] },
  { object_type: "Značky na trhu", objects: Array.from({ length: 15 }, (_, i) => `Z${i}`) },
  { objects: ["x"] },
];
const ANALYSIS: Analysis = {
  problem_summary: "Shrnutí",
  objectives: ["O1"],
  hypotheses: ["H1"],
  complexity: "standard",
  tracked_sets: SETS,
  questions_for_user: ["Q1", "", "Q2"],
  project_variants: [
    { id: "focused", title: "Úzký", n: 300, complexity: "light", objectives: ["a"], research_questions: ["rq"], hypotheses: [] },
    { id: "recommended", title: "Doporučený", n: "600", objectives: ["b"], deep_research: true },
    { id: "broad", title: "Široký", complexity: "complex" },
    { id: "fourth", title: "Navíc" },
  ],
};

type Ran = { p: ResearchProject; a: Analysis | null; saves: [string, boolean][]; alerts: string[]; asked: [string, string | null][]; toasts: string[]; confirms: string[] };
function classic(call: string, g: { p?: ResearchProject; a?: Analysis | null; prompts?: (string | null)[]; confirm?: boolean; answers?: string } = {}): Ran {
  return legacy.run<Ran>(
    `SAVES=[];ALERTS=[];TOASTS=[];ASKED=[];CONFIRMS=[];PROMPTS=__prompts;CONFIRM=__confirm;ANSWERS=__answers;PROJECT=__p;ANALYSIS=__a;
     ${call};({p:PROJECT,a:ANALYSIS,saves:SAVES,alerts:ALERTS,asked:ASKED,toasts:TOASTS,confirms:CONFIRMS})`,
    { __p: g.p ?? base, __a: g.a === undefined ? ANALYSIS : g.a, __prompts: g.prompts ?? [], __confirm: g.confirm ?? true, __answers: g.answers ?? "" },
  );
}

describe("comparable sets are edited as the classic editors do", () => {
  it("each set's family tag is comparableFamily's", () => {
    for (const x of [...SETS, { object_type: "Motivace nákupu" }, { title: "Emoce" }, { object_type: "purchase intent" }, { object_type: "Média" }, { title: "Bariéry" }, { title: "Argumenty" }]) {
      expect(comparableFamily(x)).toBe(legacy.run("comparableFamily(__s)", { __s: x }));
    }
  });

  it("the question preview is renderObjectSet's: six rows, the first {object} filled, the scale's two ends", () => {
    for (const set of SETS) {
      const html = legacy.run<string>("renderObjectSet(__s,0)", { __s: set });
      const rows = objectQuestionRows(set);
      expect(rows.length).toBe(Math.min(6, (set.objects || []).length));
      for (const r of rows) expect(html).toContain(`<b>${r.question}</b><span class="chip">1–10</span></div><small>${r.low} ← 1 2 3 4 5 6 7 8 9 10 → ${r.high}</small>`);
      expect(html).toContain(`<b>Porovnáváme mezi sebou:</b> ${set.purpose || SET_PURPOSE_DEFAULT}`);
    }
  });

  const addCases: [string, (string | null)[], Analysis | null][] = [
    ["a set with a comma list", ["  Regiony ", " Praha, Brno ,, Ostrava "], ANALYSIS],
    ["no items: the second prompt cancelled", ["Argumenty", null], ANALYSIS],
    ["more than fifteen items are cut", ["Značky", Array.from({ length: 20 }, (_, i) => `z${i}`).join(",")], ANALYSIS],
    ["no title: nothing added", ["  ", "a,b"], ANALYSIS],
    ["cancelled at the title", [null], ANALYSIS],
    ["without an analysis, one is started from the goal", ["Sada", "a"], null],
  ];
  for (const [name, prompts, a] of addCases) {
    it(`addPlanSet: ${name}`, () => {
      const ran = classic("addPlanSet()", { prompts, a });
      const got = addSet({ project: base, analysis: a }, prompts[0], prompts[1] ?? null);
      expect(got ?? a).toEqual(ran.a);
      expect(ran.saves.length).toBe(got ? 1 : 0);
      expect(ran.asked.map((x) => x[0])).toEqual(prompts[0]?.trim() ? [PROMPT_SET_TITLE, PROMPT_SET_OBJECTS] : [PROMPT_SET_TITLE]);
    });
  }

  for (const [name, si, value] of [["an object", 0, "  H "], ["into an empty set", 1, "Praha"], ["past fifteen", 2, "Z15"], ["nothing typed", 0, " "]] as const) {
    it(`addPlanObject: ${name}`, () => {
      const ran = classic(`addPlanObject(${si})`, { prompts: [value] });
      const got = addObject(ANALYSIS, si, value);
      expect(ran.asked).toEqual([[PROMPT_OBJECT, null]]);
      if (got && "error" in got) {
        expect(ran.alerts).toEqual([SET_FULL]);
        expect(ran.a).toEqual(ANALYSIS);
      } else expect(got?.analysis ?? ANALYSIS).toEqual(ran.a);
    });
  }

  for (const [si, value] of [[0, " Nové jméno "], [3, "Pojmenovaná"], [0, ""], [9, "x"]] as const) {
    it(`renamePlanSet(${si}, ${JSON.stringify(value)})`, () => {
      const ran = classic(`renamePlanSet(${si})`, { prompts: [value] });
      expect(renameSet(ANALYSIS, si, value) ?? ANALYSIS).toEqual(ran.a);
      if (SETS[si]) expect(ran.asked).toEqual([[PROMPT_RENAME, setTitle(SETS[si])]]);
    });
  }

  for (const si of [0, 3, 9]) {
    it(`removePlanSet(${si}), confirmed`, () => {
      const ran = classic(`removePlanSet(${si})`);
      expect(removeSet(ANALYSIS, si) ?? ANALYSIS).toEqual(ran.a);
      expect(ran.confirms).toEqual(SETS[si] ? [CONFIRM_REMOVE_SET] : []);
    });
  }
  it("removePlanSet, declined, keeps the set", () => {
    expect(classic("removePlanSet(0)", { confirm: false }).a).toEqual(ANALYSIS);
  });

  for (const [si, oi] of [[0, 0], [0, 6], [2, 14], [0, 40]]) {
    it(`removePlanObject(${si}, ${oi})`, () => {
      expect(removeObject(ANALYSIS, si, oi)).toEqual(classic(`removePlanObject(${si},${oi})`).a);
    });
  }
});

describe("design variants are projectVariants1793 and applyProjectVariant1793", () => {
  it("three at most, from the analysis, else the project", () => {
    expect(projectVariants({ project: base, analysis: ANALYSIS })).toEqual(legacy.run("projectVariants1793()", { PROJECT: base, ANALYSIS }));
    const kept = { ...base, design_variants: [{ id: "k" }] };
    expect(projectVariants({ project: kept, analysis: { objectives: [] } })).toEqual(legacy.run("projectVariants1793()", { PROJECT: kept, ANALYSIS: { objectives: [] } }));
  });
  for (const id of ["focused", "recommended", "broad", "fourth", "nope"]) {
    it(`applying ${id}`, () => {
      const ran = classic(`applyProjectVariant1793(${JSON.stringify(id)})`);
      const got = applyVariant({ project: base, analysis: ANALYSIS }, id);
      expect(got?.state.project ?? base).toEqual(ran.p);
      expect(got?.state.analysis ?? ANALYSIS).toEqual(ran.a);
      expect(ran.toasts).toEqual(got ? [`Použit návrh: ${got.title}`] : []);
      expect(ran.saves).toEqual(got ? [["project_variant_1793", true]] : []);
    });
  }
});

describe("follow-up questions are answered as reanalyze does", () => {
  it("empty questions are dropped", () => {
    expect(followUps(ANALYSIS)).toEqual(["Q1", "Q2"]);
    expect(effective("renderPlan")).toBeTruthy();
    expect(statement("renderPlan=function(){title('2. Návrh'", "};")).toContain("let follow=(a.questions_for_user||[]).filter(Boolean)");
  });
  for (const [name, known, answers] of [["appended to what is known", "Víme A.", "  Jen MHD. "], ["into an empty field", "", "Ano"], ["nothing written", "x", "   "]] as const) {
    it(name, async () => {
      const p = { ...base, briefing: { ...base.briefing, what_is_known: known } };
      const ran = await legacy.run<Promise<Ran & { analyses: unknown[] }>>(
        "(async()=>{SAVES=[];ALERTS=[];ANALYSES=[];PROJECT=__p;ANSWERS=__x;await reanalyze();return {p:PROJECT,alerts:ALERTS,saves:SAVES,analyses:ANALYSES}})()",
        { __p: p, __x: answers },
      );
      const got = answerFollowUps(p, answers);
      if ("error" in got) {
        expect(ran.alerts).toEqual([ANSWERS_EMPTY]);
        expect(ran.analyses).toEqual([]);
      } else {
        expect(got.project).toEqual(ran.p);
        expect(ran.saves).toEqual([["autosave", true]]);
        expect(ran.analyses).toEqual(["brief"]);
      }
    });
  }
});

describe("comments are the classic comment workflow", () => {
  const withComments = (cs: unknown[]) => ({ ...base, ui_state: { ...base.ui_state, plan_comments26: cs } }) as ResearchProject;
  it("comments26 starts an empty list", () => {
    expect(planComments(base)).toEqual(legacy.run("PROJECT=__p;comments26()", { __p: base }));
  });
  it("adding keeps the quote to 500 characters and the comment trimmed (floatButton26)", () => {
    const src = statement("float26.onclick=()=>{", "};return float26}");
    expect(src).toContain("comments26().push({quote:sel26.slice(0,500),comment:c.trim()});save('plan_comments26',false)");
    expect(src).toContain(`prompt('${PROMPT_COMMENT}','')`);
    const p = addComment(base, "q".repeat(600), "  Tohle ne. ");
    expect(planComments(p!)).toEqual([{ quote: "q".repeat(500), comment: "Tohle ne." }]);
    expect(addComment(base, "q", "  ")).toBeNull();
  });
  it("removing is npcRemoveComment26", () => {
    const p = withComments([{ quote: "a", comment: "1" }, { quote: "b", comment: "2" }]);
    const ran = classic("npcRemoveComment26(0)", { p });
    expect(removeComment(p, 0)).toEqual(ran.p);
    expect(ran.saves).toEqual([["plan_comments26", false]]);
  });
  it("processing writes the review comments, clears the list and re-analyses with force", async () => {
    const p = withComments([{ quote: "Jde o test", comment: "Není to test." }, { quote: "cena", comment: "Bez ceny." }]);
    const ran = await legacy.run<Promise<{ p: ResearchProject; saves: unknown; analyses: unknown; gone: unknown; toasts: unknown }>>(
      "(async()=>{SAVES=[];ANALYSES=[];GONE=[];TOASTS=[];PROJECT=__p;await npcProcessComments26();return {p:PROJECT,saves:SAVES,analyses:ANALYSES,gone:GONE,toasts:TOASTS}})()",
      { __p: p },
    );
    const got = commentsToReview(p)!;
    // The classic marks the plan changed once the analysis is back; the port does that after its own analysis.
    expect({ ...got, ui_state: { ...got.ui_state, plan_changed26: true } }).toEqual(ran.p);
    expect(ran.saves).toEqual([["plan_comments_applied26", false]]);
    expect(ran.analyses).toEqual([true]);
    expect(ran.toasts).toEqual(["Komentáře zapracovány"]);
    expect(ran.gone).toEqual(["plan"]);
    expect(commentsToReview(base)).toBeNull();
  });
});

describe("the way on is setQuestionnairePath('choose')", () => {
  it("and the wizard's label is the classic one", () => {
    const p = { ...base, ui_state: { ...base.ui_state, questionnaire_path: "ai" } };
    const ran = classic("setQuestionnairePath('choose')", { p });
    expect(toQuestionnaire(p)).toEqual(ran.p);
    expect(ran.saves).toEqual([["questionnaire_path", false]]);
    expect(statement("const _renderPlan1789=renderPlan;", "};")).toContain(`appendWizardNext1789("setQuestionnairePath('choose');go('questionnaire')",'Další · dotazník')`);
  });
});
