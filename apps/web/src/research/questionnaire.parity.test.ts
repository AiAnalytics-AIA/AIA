import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { declaration, effective, legacyContext, statement } from "@/testing/legacy";
import { type Template, type ResearchProject, defaultsMerge } from "./model";
import {
  BUILD_FAILED_SUFFIX,
  BUILD_TITLE,
  BUILD_WARN_MS,
  CONFIRM_REMOVE_SECTION,
  DEEP_TITLE,
  GUIDED_PROMPT,
  type GuidedKind,
  OPTIMIZE_DONE,
  OPTIMIZE_TITLE,
  PROMPT_CHOICES,
  PROMPT_SET_ITEMS,
  PROMPT_SET_TYPE,
  SET_SIZE,
  SET_TOO_SMALL,
  type Section,
  UPLOAD_NO_FILE,
  addGuidedQuestion,
  addQuestion,
  addQuestionSection,
  addTrackedSet,
  applyBuilt,
  applyDeep,
  applyImport,
  applyOptimized,
  buildPayload,
  changeQType,
  deepPayload,
  optimizePayload,
  questionnaireCounts,
  questionnaireHasQuestions,
  questionnaireView,
  removeQuestion,
  removeSection,
  respondentPreview,
  setObjectFamily,
  setObjectLabel,
  setPriceBands,
  setQuestionOptions,
  setQuestionText,
  setScaleEnd,
  setScaleLabel,
  setSectionField,
  toAudience,
  updateObjects,
} from "./questionnaire";

// Dotazník against the classic interface's own functions, run under Node with
// the prompts, the save, the render and the network stubbed and recorded. Time
// and randomness are fixed so the classic ids and the port's agree.
const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const BOOT: Template = { empty_project: EMPTY, ai_provider: "claude_code_subscription" };
const NOW = 1_790_000_000_000;
const RANDOM = 0.5731209;
const IDS = { now: () => NOW, random: () => RANDOM };

const legacy = legacyContext({
  now: NOW,
  prelude: [
    `Math.random=()=>${RANDOM};const clone=x=>JSON.parse(JSON.stringify(x));var CURRENT='questionnaire';`,
    "var SAVES=[],ALERTS=[],TOASTS=[],PROMPTS=[],ASKED=[],CONFIRM=true,CONFIRMS=[],GONE=[],JOBS=[],POSTS=[],RESULT=null,VIEW='',PAGE_TITLE='';",
    "var PROJECT=null,ANALYSIS=null,LAST_CHECK=1,FINAL_AI_REVIEW=1,FILE=null,ANALYSED=0,READY=true;",
    "function save(r,inv){SAVES.push([r||'autosave',inv!==false])}function renderQuestionnaire(){}function alert(m){ALERTS.push(m)}function toast(m){TOASTS.push(m)}function go(r){GONE.push(r)}",
    "function prompt(m,d){ASKED.push([m,d===undefined?null:d]);return PROMPTS.shift()}function confirm(m){CONFIRMS.push(m);return CONFIRM}",
    "function progress(){}function setTimeout(){}function E(x){return String(x??'')}function title(t){PAGE_TITLE=t}",
    "function $(s){return s==='#view'?{set innerHTML(v){VIEW=v},get innerHTML(){return VIEW}}:s==='#qUploadFile'?{files:FILE?[FILE]:[]}:null}",
    "async function fileToB64(){return 'QUJD'}async function jpost(ep,b,t){POSTS.push({ep,b,t});return RESULT}",
    "async function job(ep,payload,title,opts){JOBS.push({ep,payload:clone(payload),title,opts:opts||null});return RESULT}",
    "async function ensureAnalysis1776(){ANALYSED++;return ANALYSIS}async function ensureClaudeReady1776(){return READY}function storeAIError1776(stage,e){return String(e?.message||'AI krok se nepodařilo dokončit.')}",
    "function aiActionBar(label){return '<AI>'+label+'</AI>'}function questionnaireEditorHtml(){return 'GUIDED EDITOR'}",
    "function aiProvider(){return 'claude_code_subscription'}function aiProviderLabel(){return 'AI partner'}",
  ],
  functions: [
    "defaultsMerge",
    "questionnaireHasQuestions1789",
    "questionnaireRespondentPreview1780",
    "previewQuestion1780",
    "previewObjectBattery1780",
    "secId",
    "qId",
    "addGuidedQuestion",
    "addQuestion",
    "removeQuestion",
    "changeQType",
    "setScaleLabel",
    "addQuestionSection",
    "addTrackedSet",
    "removeSection",
    "updateObjects",
    "setObjLabel",
    "setPriceBands",
    "uploadQuestionnaireFile",
    "buildQuestionnaire",
    "optimizeQuestionnaireAI",
    "runProjectDeepResearch",
    "continueQuestionnaireToAudience",
  ],
});
// The base renderer (the wizard wrapper only appends its button), and the three
// editor templates whose inline handlers the rebuilt fields must match.
legacy.run(`${declaration("renderQuestionnaire").replace("function renderQuestionnaire(", "function renderQuestionnaireBase(")}`);
legacy.run(`${effective("questionSection")};${effective("objectSection")};${effective("questionCard")}`);

const base = defaultsMerge({ goal: "Zjistit zájem", model: "sonnet" }, BOOT);
const QUESTIONS: Section = {
  id: "sec_a",
  type: "questions",
  title: "Hlavní otázky",
  purpose: "",
  questions: [
    { id: "Q1", text: "Jak často?", typ: "vyber", kategorie: ["Denně", "Týdně", "Měsíčně", "Nikdy", "Jinak", "Nevím", "Občas", "Vzácně", "Devátá"] },
    { id: "Q2", text: "Jak moc?", typ: "skala", skala: [0, 7], popisky_skaly: ["", "hodně"] },
    { id: "Q3", text: "", typ: "otevrena" },
    { id: "Q4", text: "Které?", typ: "multi", volby: ["A", "B"] },
    { id: "Q5", typ: "skala" },
  ],
};
const BATTERY: Section = {
  id: "sec_b",
  type: "object_battery",
  title: "Sledovaná sada — média",
  object_type: "média",
  objects: ["TV", "Rádio", "Web", "Tisk", "Podcast", "Video", "Sociální sítě", "Billboard", "Kino"],
  object_question: "Jak často používáte {object}? A {object}?",
  scale_labels: ["nikdy", "denně"],
  output_type: "test_konceptu",
  metadata: { price_bands: ["199 Kč"] },
};
const withSections = (xs: Section[], ui: Record<string, unknown> = {}) =>
  ({ ...base, sections: xs, ui_state: { ...base.ui_state, ...ui } }) as ResearchProject;
const FULL = withSections([QUESTIONS, BATTERY]);
const MANY = withSections([QUESTIONS, BATTERY, { ...QUESTIONS, id: "sec_c", questions: Array.from({ length: 12 }, (_, i) => ({ id: `R${i}`, text: `R${i}?`, typ: "vyber", kategorie: ["x"] })) }, BATTERY]);

type Ran = { p: ResearchProject; a: unknown; saves: [string, boolean][]; alerts: string[]; toasts: string[]; asked: [string, string | null][]; confirms: string[]; gone: string[]; jobs: { ep: string; payload: unknown; title: string; opts: unknown }[]; posts: { ep: string; b: unknown; t: unknown }[]; view: string; analysed: number };
const RESET = "SAVES=[];ALERTS=[];TOASTS=[];ASKED=[];CONFIRMS=[];GONE=[];JOBS=[];POSTS=[];VIEW='';ANALYSED=0;";
const OUT = "({p:PROJECT,a:ANALYSIS,saves:SAVES,alerts:ALERTS,toasts:TOASTS,asked:ASKED,confirms:CONFIRMS,gone:GONE,jobs:JOBS,posts:POSTS,view:VIEW,analysed:ANALYSED})";
type G = { p?: ResearchProject; a?: unknown; prompts?: (string | null)[]; confirm?: boolean; result?: unknown; file?: unknown; ready?: boolean };
const globals = (g: G) => ({ __p: g.p ?? FULL, __a: g.a ?? null, __pr: g.prompts ?? [], __c: g.confirm ?? true, __r: g.result ?? null, __f: g.file ?? null, __ready: g.ready ?? true, BOOT });
const SET = "PROJECT=__p;ANALYSIS=__a;PROMPTS=__pr;CONFIRM=__c;RESULT=__r;FILE=__f;READY=__ready;";
const classic = (call: string, g: G = {}): Ran => legacy.run<Ran>(`${RESET}${SET}${call};${OUT}`, globals(g));
const classicAsync = (call: string, g: G = {}): Promise<Ran> =>
  legacy.run<Promise<Ran>>(`(async()=>{${RESET}${SET}await ${call};return ${OUT}})()`, globals(g));

describe("what the questionnaire counts, and which screen it draws", () => {
  const projects: [string, ResearchProject][] = [
    ["empty", base],
    ["questions and a set", FULL],
    ["tracked sets only (OI-52)", withSections([BATTERY])],
    ["an empty question block", withSections([{ ...QUESTIONS, questions: [] }])],
  ];
  for (const [name, p] of projects) {
    it(`${name}: has questions, and the two counts`, () => {
      expect(questionnaireHasQuestions(p)).toBe(legacy.run("questionnaireHasQuestions1789()", { PROJECT: p }));
      const heading = legacy.run<string>("PROJECT=__p;(()=>{let sets=(PROJECT.sections||[]).filter(x=>x.type==='object_battery').length,qs=(PROJECT.sections||[]).reduce((n,x)=>n+(x.type==='questions'?(x.questions||[]).length:0),0);return qs+' otázek · '+sets+' sledovaných sad'})()", { __p: p });
      const c = questionnaireCounts(p);
      expect(`${c.questions} otázek · ${c.sets} sledovaných sad`).toBe(heading);
      // The heading's own statement, so a change to it is seen here.
      expect(effective("questionnaireEditorHtml")).toContain("${qs} otázek · ${sets} sledovaných sad");
    });
  }
  it("a questionnaire of tracked sets only has no questions, as the classic counts (OI-52)", () => {
    expect(questionnaireHasQuestions(withSections([BATTERY]))).toBe(false);
    expect(questionnaireCounts(withSections([BATTERY])).sets).toBe(1);
  });

  const markers: Record<string, string> = { choose: "Jak chcete dotazník vytvořit?", upload: "<h2>Nahrát dotazník</h2>", ai: "<h2>Dotazník s AI</h2>", editor: "GUIDED EDITOR" };
  for (const path of [undefined, "choose", "upload", "manual", "ai", "unknown"]) {
    for (const [name, xs] of [["no sections", []], ["sections", [QUESTIONS]]] as const) {
      it(`path ${path ?? "(none)"} with ${name}`, () => {
        const p = withSections([...xs], { questionnaire_path: path });
        const ran = classic("renderQuestionnaireBase()", { p });
        const view = questionnaireView(p);
        expect(ran.view).toContain(markers[view]);
        for (const [k, m] of Object.entries(markers)) if (k !== view && !(k === "editor" && view === "upload")) expect(ran.view).not.toContain(m);
      });
    }
  }
  it("the AI tile names the provider and the model as the classic does", () => {
    const ran = classic("renderQuestionnaireBase()", { p: withSections([], { questionnaire_path: "choose" }) });
    expect(ran.view).toContain('<span class="chip">AI partner · sonnet</span>');
  });
});

describe("the respondent preview is questionnaireRespondentPreview1780", () => {
  for (const [name, p] of [["mixed", FULL], ["more than fourteen items", MANY], ["empty", base]] as const) {
    it(name, () => {
      const html = legacy.run<string>("questionnaireRespondentPreview1780()", { PROJECT: p });
      const items = respondentPreview(p);
      expect(items.length).toBe((html.match(/class="previewQ"/g) || []).length);
      for (const it of items) {
        if (it.kind === "question") {
          expect(html).toContain(`<div class="tiny mut">Otázka ${it.index}</div><b>${it.text}</b>`);
          for (const o of it.options) expect(html).toContain(`<span class="previewOption">○ ${o}</span>`);
          if (it.scale) expect(html).toContain(`<span class="tiny">${it.scale[0]}</span><div class="previewScaleLine"></div><span class="tiny">${it.scale[1]}</span>`);
        } else {
          expect(html).toContain(`Sledovaná sada ${it.index} · ${it.title}`);
          expect((html.match(/class="objectQuestionRow"/g) || []).length).toBeGreaterThanOrEqual(it.rows.length);
          for (const r of it.rows) expect(html).toContain(`<span>${r}</span><span class="chip">1–10</span></div><small>${it.low} ← 1 2 3 4 5 6 7 8 9 10 → ${it.high}</small>`);
        }
      }
    });
  }
  it("options stop at eight and object rows at eight", () => {
    const [q1] = respondentPreview(FULL);
    expect(q1.kind === "question" && q1.options.length).toBe(8);
    const battery = respondentPreview(FULL).find((x) => x.kind === "battery");
    expect(battery?.kind === "battery" && battery.rows.length).toBe(8);
  });
});

describe("the guided editor is the classic editor", () => {
  const guided: [string, GuidedKind, (string | null)[], ResearchProject][] = [
    ["a scale", "scale", ["  Jak moc?  "], FULL],
    ["an open question", "open", ["Proč?"], FULL],
    ["a choice with its answers", "choice", ["Jaká?", " A, B ,, C "], FULL],
    ["a choice, answers cancelled", "choice", ["Jaká?", null], FULL],
    ["into a project with no question block", "scale", ["Kolik?"], withSections([BATTERY])],
    ["cancelled", "open", [null], FULL],
    ["blank", "scale", ["   "], FULL],
  ];
  for (const [name, kind, prompts, p] of guided) {
    it(`addGuidedQuestion: ${name}`, () => {
      const ran = classic(`addGuidedQuestion(${JSON.stringify(kind)})`, { p, prompts: [...prompts] });
      const got = addGuidedQuestion(p, kind, prompts[0], prompts[1] ?? null, IDS);
      expect(got?.project ?? p).toEqual(ran.p);
      expect(ran.asked[0][0]).toBe(GUIDED_PROMPT[kind]);
      if (got && kind === "choice") expect(ran.asked[1]).toEqual([PROMPT_CHOICES, "Ano, Ne"]);
      expect(ran.saves).toEqual(got ? [["guided_question", true]] : []);
    });
  }

  it("addQuestion, removeQuestion and addQuestionSection", () => {
    expect(addQuestion(FULL, 0, IDS)).toEqual(classic("addQuestion(0)").p);
    expect(removeQuestion(FULL, 0, 1)).toEqual(classic("removeQuestion(0,1)").p);
    expect(addQuestionSection(FULL, IDS)).toEqual(classic("addQuestionSection()").p);
  });

  for (const [qi, t] of [[0, "skala"], [1, "vyber"], [2, "multi"], [2, "skala"], [0, "otevrena"], [4, "skala"]] as const) {
    it(`changeQType(${qi}, ${t})`, () => {
      expect(changeQType(FULL, 0, qi, t)).toEqual(classic(`changeQType(0,${qi},${JSON.stringify(t)})`).p);
    });
  }

  it("setScaleLabel", () => {
    expect(setScaleLabel(FULL, 0, 1, 0, "málo")).toEqual(classic("setScaleLabel(0,1,0,'málo')").p);
    expect(setScaleLabel(FULL, 0, 4, 1, "moc")).toEqual(classic("setScaleLabel(0,4,1,'moc')").p);
  });

  const sets: [string, (string | null)[]][] = [
    ["four items", ["značky", "A, B, C, D"]],
    ["fifteen items", ["značky", Array.from({ length: 15 }, (_, i) => `z${i}`).join(",")]],
    ["three items", ["značky", "A, B, C"]],
    ["sixteen items", ["značky", Array.from({ length: 16 }, (_, i) => `z${i}`).join(",")]],
    ["cancelled at the type", [null]],
    ["cancelled at the items", ["značky", null]],
  ];
  for (const [name, prompts] of sets) {
    it(`addTrackedSet: ${name}`, () => {
      const ran = classic("addTrackedSet()", { prompts: [...prompts] });
      const got = addTrackedSet(FULL, prompts[0], prompts[1] ?? null, IDS);
      expect(ran.asked.map((x) => x[0])).toEqual([PROMPT_SET_TYPE, PROMPT_SET_ITEMS].slice(0, prompts.length));
      if (got && "error" in got) {
        expect(ran.alerts).toEqual([SET_SIZE]);
        expect(ran.p).toEqual(FULL);
      } else expect(got?.project ?? FULL).toEqual(ran.p);
    });
  }

  it("removeSection only when confirmed", () => {
    const yes = classic("removeSection(0)");
    expect(yes.confirms).toEqual([CONFIRM_REMOVE_SECTION]);
    expect(removeSection(FULL, 0)).toEqual(yes.p);
    expect(classic("removeSection(0)", { confirm: false }).p).toEqual(FULL);
  });

  for (const [name, v] of [["twenty lines, cut at fifteen", Array.from({ length: 20 }, (_, i) => ` o${i} `).join("\n")], ["two lines, noted", "A\n\nB"], ["empty", ""]] as const) {
    it(`updateObjects: ${name}`, () => {
      const ran = classic(`updateObjects(1,${JSON.stringify(v)})`);
      const got = updateObjects(FULL, 1, v);
      expect(got.project).toEqual(ran.p);
      expect(ran.toasts).toEqual(got.note ? [SET_TOO_SMALL] : []);
    });
  }

  it("setObjLabel and setPriceBands", () => {
    expect(setObjectLabel(FULL, 1, 1, "často")).toEqual(classic("setObjLabel(1,1,'často')").p);
    expect(setPriceBands(FULL, 1, "199 Kč, 249 Kč\n299 Kč,")).toEqual(classic("setPriceBands(1,'199 Kč, 249 Kč\\n299 Kč,')").p);
  });
});

/** The inline handlers of the classic editor templates, run with a stand-in element. */
function handlers(template: string, globalsFor: Record<string, unknown>): { attr: string; code: string }[] {
  const html = legacy.run<string>(template, globalsFor);
  return [...html.matchAll(/(on(?:input|change))="([^"]*)"/g)].map((m) => ({ attr: m[1], code: m[2] }));
}
function runHandler(code: string, p: ResearchProject, el: Record<string, unknown>): Ran {
  return legacy.run<Ran>(`${RESET}PROJECT=__p;(function(){${code}}).call(__el);${OUT}`, { __p: p, __el: el, BOOT });
}

describe("the editor's inline fields write what the classic handlers write", () => {
  it("a tracked set's title, purpose, object type, question and familiarity", () => {
    const hs = handlers("PROJECT=__p;objectSection(PROJECT.sections[1],1)", { __p: FULL });
    const find = (s: string) => hs.find((h) => h.code.includes(s))!.code;
    expect(runHandler(find("].title=this.value"), FULL, { value: "Média" }).p).toEqual(setSectionField(FULL, 1, "title", "Média"));
    expect(runHandler(find("].purpose=this.value"), FULL, { value: "Proč" }).p).toEqual(setSectionField(FULL, 1, "purpose", "Proč"));
    expect(runHandler(find("].object_family=this.value"), FULL, { value: "značky" }).p).toEqual(setObjectFamily(FULL, 1, "značky"));
    expect(runHandler(find("].object_question=this.value"), FULL, { value: "Jak {object}?" }).p).toEqual(setSectionField(FULL, 1, "object_question", "Jak {object}?"));
    expect(runHandler(find("].familiarity_required=this.checked"), FULL, { checked: true }).p).toEqual(setSectionField(FULL, 1, "familiarity_required", true));
    // The object list, the scale ends and the price bands go through the functions compared above.
    expect(hs.map((h) => h.code).join("\n")).toMatch(/updateObjects\(1,this\.value\)[\s\S]*setObjLabel\(1,0,this\.value\)[\s\S]*setObjLabel\(1,1,this\.value\)[\s\S]*setPriceBands\(1,this\.value\)/);
  });

  it("a question block's title and purpose", () => {
    const hs = handlers("PROJECT=__p;questionSection(PROJECT.sections[0],0)", { __p: FULL });
    expect(runHandler(hs.find((h) => h.code.includes("].title=this.value"))!.code, FULL, { value: "Blok" }).p).toEqual(setSectionField(FULL, 0, "title", "Blok"));
    expect(runHandler(hs.find((h) => h.code.includes("].purpose=this.value"))!.code, FULL, { value: "Účel" }).p).toEqual(setSectionField(FULL, 0, "purpose", "Účel"));
  });

  it("a question's text, options and scale ends", () => {
    const choice = handlers("PROJECT=__p;questionCard(PROJECT.sections[0].questions[0],0,0)", { __p: FULL });
    expect(runHandler(choice.find((h) => h.code.includes(".text=this.value"))!.code, FULL, { value: "Nové znění?" }).p).toEqual(setQuestionText(FULL, 0, 0, "Nové znění?"));
    expect(runHandler(choice.find((h) => h.code.includes(".kategorie="))!.code, FULL, { value: " A \n\nB\n" }).p).toEqual(setQuestionOptions(FULL, 0, 0, " A \n\nB\n"));
    const scale = handlers("PROJECT=__p;questionCard(PROJECT.sections[0].questions[1],0,1)", { __p: FULL });
    const [min, max] = scale.filter((h) => h.code.includes(".skala="));
    for (const v of ["3", "0", "", "-2"]) {
      expect(runHandler(min.code, FULL, { value: v }).p).toEqual(setScaleEnd(FULL, 0, 1, 0, v));
      expect(runHandler(max.code, FULL, { value: v }).p).toEqual(setScaleEnd(FULL, 0, 1, 1, v));
    }
    // An end of 0 is replaced by the default when the other end changes, as `||` does.
    const zero = withSections([{ ...QUESTIONS, questions: [{ id: "Z", typ: "skala", skala: [0, 0] }] }]);
    const zs = handlers("PROJECT=__p;questionCard(PROJECT.sections[0].questions[0],0,0)", { __p: zero }).filter((h) => h.code.includes(".skala="));
    expect(runHandler(zs[0].code, zero, { value: "2" }).p).toEqual(setScaleEnd(zero, 0, 0, 0, "2"));
    expect(runHandler(zs[1].code, zero, { value: "9" }).p).toEqual(setScaleEnd(zero, 0, 0, 1, "9"));
    // A scale with no stored scale: the other end is defaulted.
    const bare = handlers("PROJECT=__p;questionCard(PROJECT.sections[0].questions[4],0,4)", { __p: FULL }).filter((h) => h.code.includes(".skala="));
    expect(runHandler(bare[1].code, FULL, { value: "5" }).p).toEqual(setScaleEnd(FULL, 0, 4, 1, "5"));
  });
});

describe("import and the AI steps take what the classic ones take", () => {
  const IMPORTED = { project: { ...EMPTY, sections: [QUESTIONS], title: "Z Excelu" }, summary: { question_count: 5, tracked_sets: 0, sections: 1 } };

  it("uploadQuestionnaireFile: the unit's project, on the editor", async () => {
    const ran = await classicAsync("uploadQuestionnaireFile()", { result: IMPORTED, file: { name: "d.xlsx" } });
    const got = applyImport(IMPORTED, BOOT);
    expect(got.project).toEqual(ran.p);
    expect(ran.toasts).toEqual([got.toast]);
    expect(ran.saves).toEqual([["questionnaire_import", true]]);
    expect(ran.posts).toEqual([{ ep: "/api/questionnaire/upload", b: { filename: "d.xlsx", data_b64: "QUJD", project: FULL }, t: 180000 }]);
  });
  it("uploadQuestionnaireFile without a file", async () => {
    expect((await classicAsync("uploadQuestionnaireFile()")).alerts).toEqual([UPLOAD_NO_FILE]);
  });

  const BUILT = { project: { ...EMPTY, sections: [QUESTIONS, BATTERY], run_policy: { provider: "anthropic" }, ui_state: { questionnaire_path: "ai", x: 1 } } };
  it("buildQuestionnaire: analysis first, then the job, then the AI's project on the editor", async () => {
    const analysis = { objectives: ["O"] };
    const ran = await classicAsync("buildQuestionnaire()", { result: BUILT, a: analysis });
    expect(ran.analysed).toBe(1);
    expect(ran.jobs).toEqual([{ ep: "/api/research/build_questionnaire", payload: buildPayload(FULL, analysis), title: BUILD_TITLE, opts: { warnMs: BUILD_WARN_MS } }]);
    expect(applyBuilt(BUILT, BOOT)).toEqual(ran.p);
    expect(ran.saves).toEqual([["questionnaire_ai_1776", true]]);
    expect(ran.gone).toEqual(["questionnaire"]);
  });
  it("buildQuestionnaire stops before the job when the provider is not ready", async () => {
    const ran = await classicAsync("buildQuestionnaire()", { result: BUILT, ready: false });
    expect(ran.jobs).toEqual([]);
    expect(ran.p).toEqual(FULL);
  });
  it("buildQuestionnaire's failure message", async () => {
    const ran = await legacy.run<Promise<Ran>>(
      `(async()=>{${RESET}PROJECT=__p;READY=true;const real=job;job=async()=>{throw Error('MODEL_TIMEOUT')};try{await buildQuestionnaire()}finally{job=real}return ${OUT}})()`,
      { __p: FULL, BOOT },
    );
    expect(ran.alerts).toEqual([`MODEL_TIMEOUT${BUILD_FAILED_SUFFIX}`]);
  });

  const OPTIMIZED = { project: { ...EMPTY, sections: [BATTERY] }, research: { accepted: [1, 2] }, analysis: { objectives: ["nové"] } };
  for (const [name, r] of [["with research and analysis", OPTIMIZED], ["without either", { project: OPTIMIZED.project }]] as const) {
    it(`optimizeQuestionnaireAI, ${name}: no provider check, as the classic (OI-55)`, async () => {
      const kept = { objectives: ["staré"] };
      const ran = await classicAsync("optimizeQuestionnaireAI()", { result: r, a: kept, ready: false });
      expect(ran.jobs).toEqual([{ ep: "/api/questionnaire/optimize", payload: optimizePayload(FULL), title: OPTIMIZE_TITLE, opts: null }]);
      const got = applyOptimized(r, kept, BOOT);
      expect(got.project).toEqual(ran.p);
      expect(got.analysis).toEqual(ran.a);
      expect(ran.toasts).toEqual([OPTIMIZE_DONE]);
      expect(ran.saves).toEqual([["questionnaire_optimized", true]]);
    });
  }

  it("runProjectDeepResearch: the research replaced, the counts said", async () => {
    const r = { research: { accepted: [1] }, accepted_count: 1, quarantined_count: 3 };
    const ran = await classicAsync("runProjectDeepResearch(true,'questionnaire')", { result: r });
    expect(ran.jobs).toEqual([{ ep: "/api/research/deep", payload: deepPayload(FULL), title: DEEP_TITLE, opts: null }]);
    const got = applyDeep(FULL, r);
    expect(got.project).toEqual(ran.p);
    expect(ran.toasts).toEqual([got.toast]);
    expect(ran.saves).toEqual([["deep_research", true]]);
  });

  for (const entry of [undefined, "own"]) {
    it(`continueQuestionnaireToAudience with audience_entry ${entry ?? "(none)"}`, () => {
      const p = withSections([QUESTIONS], { audience_entry: entry });
      const ran = classic("continueQuestionnaireToAudience()", { p });
      expect(toAudience(p)).toEqual(ran.p);
      expect(ran.saves).toEqual([["questionnaire_done", false]]);
      expect(ran.gone).toEqual(["audience"]);
      expect(legacy.run("[LAST_CHECK,FINAL_AI_REVIEW]")).toEqual([null, null]);
    });
  }

  it("the wizard's way on and its hint are the classic ones", () => {
    expect(statement("const _renderQuestionnaire1789=renderQuestionnaire;", "};")).toContain(
      "appendWizardNext1789('continueQuestionnaireToAudience()','Další · cílová skupina',!questionnaireHasQuestions1789(),questionnaireHasQuestions1789()?'':'Nejdřív vytvořte nebo nahrajte dotazník.')",
    );
  });
});
