import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { effective, legacyContext, statement } from "@/testing/legacy";
import { type Template, type ResearchProject, defaultsMerge } from "./model";
import {
  PERSONA_DIM_LABELS,
  REQUEST_AI_DONE,
  REQUEST_DONE,
  REQUEST_EMPTY,
  SUGGEST_FAILED_SUFFIX,
  SUGGEST_TITLE,
  SUGGEST_WARN_MS,
  addDimension,
  applySuggestion,
  autofill,
  canonicalPersonaDim,
  catalogEntries,
  dimensionLabels,
  dimensionResearchTopic,
  dimensionSearchText,
  matchesDimensionSearch,
  personaDone,
  recommendedSample,
  recordRequest,
  removeDimension,
  requestBody,
  requestLabel,
  setSampleSize,
  suggestPayload,
  suggestedRequest,
  suggestedPersonaDims,
  applyRecommendedSample,
  withApproval,
} from "./persona";

// Dimenze against the classic interface's own functions, run under Node with
// the prompts, the save, the render and the network stubbed and recorded.
const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const BOOT: Template = { empty_project: EMPTY, ai_provider: "claude_code_subscription" };
const NOW = 1_790_000_000_000;
const ACTIVE = { vztah_k_ai: { label: "Vztah k AI" }, media: { label: "Média (knihovna)" }, prazdna: {}, zdravi: null };

const legacy = legacyContext({
  now: NOW,
  prelude: [
    "var CURRENT='persona',SAVES=[],ALERTS=[],TOASTS=[],POSTS=[],GETS=[],JOBS=[],GONE=[],RESULT=null,INPUTS={},READY=true,VIEW='';",
    "var PROJECT=null,LIBRARY_STATE=null,BOOT={},PERSONA_AI_SUGGESTION=null,AUDIENCE_DIM_CATALOG_1793=null,LIBRARY_TAB='';",
    "const clone=x=>JSON.parse(JSON.stringify(x));",
    "function save(r,inv){SAVES.push([r||'autosave',inv!==false])}function renderPersona(){}function renderData(){}function alert(m){ALERTS.push(m)}function toast(m){TOASTS.push(m)}function go(r){GONE.push(r)}",
    "function E(x){return String(x??'')}function title(){}function renderSteps(){}function setTimeout(f){f()}",
    "function $(s){if(s==='#view')return {set innerHTML(v){VIEW=v},get innerHTML(){return VIEW},insertAdjacentHTML(){}};if(s.startsWith('#'))return s.slice(1) in INPUTS?INPUTS[s.slice(1)]:null;return null}",
    "async function jpost(ep,b,t){POSTS.push({ep,b:clone(b),t:t??null});return RESULT}async function jget(ep){GETS.push(ep);return ep==='/api/library'?{summary:{active_dimensions:{nova:{label:'Nová'}}}}:{}}",
    "async function job(ep,payload,title,opts){JOBS.push({ep,payload:clone(payload),title,opts});return RESULT}",
    "async function ensureClaudeReady1776(){return READY}function storeAIError1776(stage,e){return String(e?.message||'AI krok se nepodařilo dokončit.')}",
    "function appendWizardNext1789(action,label){VIEW+='<WIZARD '+action+'|'+label+'>'}",
    statement("PERSONA_DIM_LABELS={", "};").replace(/^/, "var "),
  ],
  functions: [
    "canonicalPersonaDim",
    "suggestedPersonaDims",
    "personaApproved",
    "dimensionCatalogEntries1789",
    "addCatalogDimension1789",
    "removeCatalogDimension1789",
    "autofillPersonaDims",
    "recommendedSample1789",
    "useRecommendedSample1789",
    "requestDimension1793",
    "refreshLibraryState",
    "addCustomDimension1789",
    "suggestPersonaAI",
    "openDimensionResearch1793",
    "requestAISuggestedDimension1793",
  ],
});
// The full reassignment @979 (the base the 1793 wrapper wraps).
legacy.run(statement("renderPersona=function(){APP_MODE='production';PRODUCT_PATH='research';CURRENT='persona';renderSteps();title('5. Dimenze'", "'Další · kontrola')};").replace(/^/, "var APP_MODE,PRODUCT_PATH;var renderPersonaBase;").replace("renderPersona=function", "renderPersonaBase=function"));

const base = defaultsMerge({ goal: "Zjistit zájem", n: 300 }, BOOT);
const make = (x: Record<string, unknown>): ResearchProject => defaultsMerge({ goal: "Zjistit zájem", ...x }, BOOT);

type Ran = { p: ResearchProject; saves: [string, boolean][]; alerts: string[]; toasts: string[]; posts: { ep: string; b: unknown; t: unknown }[]; gets: string[]; jobs: { ep: string; payload: unknown; title: string; opts: unknown }[]; gone: string[]; view: string; suggestion: unknown; library: unknown };
const RESET = "SAVES=[];ALERTS=[];TOASTS=[];POSTS=[];GETS=[];JOBS=[];GONE=[];VIEW='';";
const OUT = "({p:PROJECT,saves:SAVES,alerts:ALERTS,toasts:TOASTS,posts:POSTS,gets:GETS,jobs:JOBS,gone:GONE,view:VIEW,suggestion:PERSONA_AI_SUGGESTION,library:LIBRARY_STATE})";
type G = { p?: ResearchProject; inputs?: Record<string, unknown>; result?: unknown; ready?: boolean; library?: unknown };
const globals = (g: G) => ({ __p: g.p ?? base, __i: g.inputs ?? {}, __r: g.result ?? null, __ready: g.ready ?? true, __lib: g.library ?? null, __boot: { data_library: { active_dimensions: ACTIVE } } });
const SET = "PROJECT=__p;INPUTS=__i;RESULT=__r;READY=__ready;LIBRARY_STATE=__lib;BOOT=__boot;";
const classic = (call: string, g: G = {}): Ran => legacy.run<Ran>(`${RESET}${SET}${call};${OUT}`, globals(g));
const classicAsync = (call: string, g: G = {}): Promise<Ran> =>
  legacy.run<Promise<Ran>>(`(async()=>{${RESET}${SET}await ${call};return ${OUT}})()`, globals(g));

describe("the dimension catalogue is PERSONA_DIM_LABELS and dimensionCatalogEntries1789", () => {
  it("the system's own labels", () => {
    expect(legacy.run("PERSONA_DIM_LABELS")).toMatchObject(PERSONA_DIM_LABELS);
    expect(Object.keys(PERSONA_DIM_LABELS).length).toBe(18);
  });
  it("with the library's labels added, sorted in Czech, marked by source", () => {
    const got = catalogEntries(ACTIVE);
    const ran = legacy.run("LIBRARY_STATE=null;BOOT=__b;dimensionCatalogEntries1789()", { __b: { data_library: { active_dimensions: ACTIVE } } });
    expect(got).toEqual(ran);
    expect(dimensionLabels(ACTIVE).vztah_k_ai).toBe("Vztah k AI");
  });
  it("each row's search text, as the classic draws it, and the picker's match", () => {
    const view = classic("LIBRARY_STATE=null;renderPersonaBase()").view;
    const drawn = [...view.matchAll(/data-search="([^"]*)"/g)].map((m) => m[1].replace(/&amp;/g, "&"));
    expect(catalogEntries(ACTIVE).map(dimensionSearchText)).toEqual(drawn);
    const d = catalogEntries(ACTIVE).find((x) => x.id === "vztah_k_ai")!;
    const matches = (q: string) => legacy.run<boolean>(`(function(q){q=String(q||'').toLocaleLowerCase('cs');return !q||__t.includes(q)})(__q)`, { __t: dimensionSearchText(d), __q: q });
    expect(effective("filterDimPicker1789")).toContain("q=String(q||'').toLocaleLowerCase('cs');document.querySelectorAll('.dimRow1789').forEach(el=>el.style.display=(!q||String(el.dataset.search||'').includes(q))?'flex':'none')");
    for (const q of ["", "AI", "knihovna", "DATA library", "xyz"]) expect(matchesDimensionSearch(d, q)).toBe(matches(q));
  });
  for (const x of ["Zdravotní stav", "Média", "nákupní zvyky", "CENA", "Digitální", "Brand love", "Kampaně", "sociální sítě", "Něco jiného!", "  Něco jiného  ", "", null, 42]) {
    it(`canonicalPersonaDim(${JSON.stringify(x)})`, () => expect(canonicalPersonaDim(x)).toBe(legacy.run("canonicalPersonaDim(__x)", { __x: x })));
  }
});

describe("the recommended and approved dimensions are the classic ones", () => {
  const cases: [string, ResearchProject][] = [
    ["nothing to go on", base],
    ["the plan's topics", make({ research_plan: { recommended_topics: ["Zdraví", "média", "cena", "Rodina"] } })],
    ["questions with topics", make({ sections: [{ type: "questions", questions: [{ topics: ["značka", "online"] }, { topics: ["kampaň"] }] }] })],
    ["a concept study", make({ study_type: "concept_test" })],
    ["an employee study", make({ study_type: "employee_climate" })],
    ["more than eight", make({ research_plan: { recommended_topics: ["zdravi", "media", "nakup", "cena", "finance", "hodnoty", "prace", "duvera", "politika", "ekologie"] } })],
  ];
  for (const [name, p] of cases) {
    it(`suggestedPersonaDims: ${name}`, () => expect(suggestedPersonaDims(p)).toEqual(legacy.run("PROJECT=__p;suggestedPersonaDims()", { __p: p })));
  }
  for (const [name, pd] of [["none", undefined], ["an empty list", { approved: [] }], ["a list", { approved: ["media", "cena"] }], ["not a list", { approved: "media" }]] as const) {
    it(`personaApproved with ${name}`, () => {
      const p = make({ persona_dimensions: pd, research_plan: { recommended_topics: ["zdraví"] } });
      const ran = legacy.run<{ a: string[]; p: ResearchProject }>("PROJECT=__p;({a:personaApproved(),p:PROJECT})", { __p: p });
      const got = withApproval(p);
      expect(got.approved).toEqual(ran.a);
      expect(got.project).toEqual(ran.p);
    });
  }
  it("removing the last dimension brings the recommended ones back, as the classic does (OI-54)", () => {
    const p = make({ persona_dimensions: { approved: ["media"] }, research_plan: { recommended_topics: ["zdraví", "cena"] } });
    const ran = classic("removeCatalogDimension1789('media');personaApproved()", { p });
    const removed = removeDimension(p, "media");
    expect(removed.project).toEqual(classic("removeCatalogDimension1789('media')", { p }).p);
    expect(withApproval(removed.project).approved).toEqual(["zdravi", "cena"]);
    expect(withApproval(removed.project).project).toEqual(ran.p);
  });
  for (const [name, fn, call] of [
    ["add", (p: ResearchProject) => addDimension(p, "politika"), "addCatalogDimension1789('politika')"],
    ["add one already there", (p: ResearchProject) => addDimension(p, "media"), "addCatalogDimension1789('media')"],
    ["remove", (p: ResearchProject) => removeDimension(p, "cena"), "removeCatalogDimension1789('cena')"],
    ["autofill", (p: ResearchProject) => autofill(p), "autofillPersonaDims()"],
  ] as const) {
    it(`${name}, from an approval and from none`, () => {
      for (const p of [make({ persona_dimensions: { approved: ["media", "cena"] } }), make({ research_plan: { recommended_topics: ["cena", "rodina"] } })]) {
        const ran = classic(call, { p });
        const got = fn(p);
        expect(got.project).toEqual(ran.p);
        expect(ran.saves).toEqual([[got.reason, true]]);
      }
    });
  }
});

describe("the sample size is recommendedSample1789 and its input", () => {
  const big = Array.from({ length: 31 }, (_, i) => ({ text: `Q${i}` }));
  const cases: [string, ResearchProject][] = [
    ["a plain study", base],
    ["over thirty questions", make({ sections: [{ type: "questions", questions: big }] })],
    ["a long goal", make({ goal: "x".repeat(1201) })],
    ["the ideal-group strategy", make({ audience: { strategy: "discover" } })],
    ["both", make({ goal: "x".repeat(1201), audience: { strategy: "discover" } })],
  ];
  for (const [name, p] of cases) {
    it(`recommendedSample: ${name}`, () => expect(recommendedSample(p)).toEqual(legacy.run("PROJECT=__p;recommendedSample1789()", { __p: p })));
  }
  it("the input: clamped to 50–5 000, empty or 0 is the recommendation", () => {
    const html = classic("renderPersonaBase()").view;
    const handler = html.match(/onchange="(PROJECT\.n=Math\.max[^"]*)"/)![1];
    for (const v of ["800", "10", "99999", "", "0", "abc", "250.5"]) {
      const ran = legacy.run<Ran>(`${RESET}PROJECT=__p;(function(){${handler}}).call({value:__v});${OUT}`, { __p: withApproval(base).project, __v: v });
      const got = setSampleSize(base, v);
      expect(got.project).toEqual(ran.p);
      expect(ran.saves).toEqual([[got.reason, true]]);
    }
  });
  it("useRecommendedSample1789", () => {
    const p = withApproval(make({ n: 1234 })).project;
    const ran = classic("useRecommendedSample1789()", { p });
    expect(applyRecommendedSample(p).project).toEqual(ran.p);
  });
  it("the wizard's way on: calibrated, saved, to the run step", () => {
    const html = classic("renderPersonaBase()").view;
    const [, action, label] = html.match(/<WIZARD ([^|]*)\|([^>]*)>/)!;
    expect(label).toBe("Další · kontrola");
    const p = withApproval(base).project;
    const ran = classic(action, { p });
    const got = personaDone(p);
    expect(got.project).toEqual(ran.p);
    expect(ran.saves).toEqual([[got.reason, true]]);
    expect(ran.gone).toEqual(["run"]);
  });
});

describe("the AI suggestion and the dimension requests are the classic ones", () => {
  it("the model's dimensions are approved without the catalogue check, as the classic does (OI-53)", async () => {
    const r = { dimensions: ["Zdraví", "vztah k AI", "Úplně nová věc", ""], new_dimension_suggestions: [{ label: "Důvěra v AI" }] };
    const p = make({ pre_research: { accepted: [1] } });
    const ran = await classicAsync("(renderPersonaBase(),suggestPersonaAI())", { p, result: r });
    expect(ran.jobs).toEqual([{ ep: "/api/persona/suggest", payload: suggestPayload(p, ACTIVE), title: SUGGEST_TITLE, opts: { maxMs: 300000, warnMs: SUGGEST_WARN_MS } }]);
    const got = applySuggestion(p, r);
    expect(got.project).toEqual(ran.p);
    expect(ran.saves).toEqual([[got.reason, true]]);
    expect(ran.suggestion).toEqual(r);
    // Not in the catalogue, still approved; and "vztah k AI" is read as "vztahy" (Vztahy / domácnost) by its substring.
    expect(got.project.persona_dimensions).toMatchObject({ approved: ["zdravi", "vztahy", "uplne_nova_vec"] });
    expect(Object.keys(dimensionLabels(ACTIVE))).not.toContain("uplne_nova_vec");
  });
  it("suggestPersonaAI stops when the provider is not ready, and words its failure", async () => {
    expect((await classicAsync("suggestPersonaAI()", { ready: false })).jobs).toEqual([]);
    const ran = await legacy.run<Promise<Ran>>(
      `(async()=>{${RESET}PROJECT=__p;READY=true;const real=job;job=async()=>{throw Error('BOOM')};try{await suggestPersonaAI()}finally{job=real}return ${OUT}})()`,
      { __p: base },
    );
    expect(ran.alerts).toEqual([`BOOM${SUGGEST_FAILED_SUFFIX}`]);
  });
  it("addCustomDimension1789: the request, the record, the library refreshed", async () => {
    const r = { dimension_id: "DIM-1", proposal_id: "PROP-1" };
    const ran = await classicAsync("(renderPersonaBase(),addCustomDimension1789())", { result: r, inputs: { customDim1789: { value: "  Vztah k AI ve zdravotnictví " } } });
    expect(requestLabel("  Vztah k AI ve zdravotnictví ")).toBe("Vztah k AI ve zdravotnictví");
    expect(ran.posts).toEqual([{ ep: "/api/library/dimension/request", b: requestBody("Vztah k AI ve zdravotnictví", "document_or_research"), t: 30000 }]);
    expect(ran.gets.sort()).toEqual(["/api/library", "/api/library/system-catalog", "/api/populations", "/api/results-registry?sync=1"].sort());
    expect(recordRequest(base, "Vztah k AI ve zdravotnictví", "document_or_research", r, new Date(NOW)).project).toEqual(ran.p);
    expect(ran.saves).toEqual([["requested_dimension_1793", true]]);
    expect(ran.toasts).toEqual([REQUEST_DONE]);
    expect((await classicAsync("addCustomDimension1789()", { inputs: { customDim1789: { value: "  " } } })).alerts).toEqual([REQUEST_EMPTY]);
  });
  it("an AI-proposed dimension is requested with its reasons and predictors, as from the model", async () => {
    const x = { label: "Důvěra v AI", why: "Mění ochotu", suggested_predictors: ["vek", "vzdelani"], source_strategy: "either" };
    const r = { dimension_id: "D2" };
    const run = (s: unknown) =>
      legacy.run<Promise<Ran>>(`(async()=>{${RESET}PROJECT=__p;RESULT=__r;PERSONA_AI_SUGGESTION={new_dimension_suggestions:[__x]};renderPersonaBase();await requestAISuggestedDimension1793(0);return ${OUT}})()`, { __p: base, __r: r, __x: s });
    const ran = await run(x);
    const q = suggestedRequest(x);
    expect(ran.posts).toEqual([{ ep: "/api/library/dimension/request", b: requestBody(q.label, q.sourceStrategy, q.extra), t: 30000 }]);
    expect(ran.posts[0].b).toMatchObject({ rationale: "Mění ochotu", origin: "claude", spec: { predictors: [{ column: "vek", direction: "positive", strength: 1 }, { column: "vzdelani", direction: "positive", strength: 1 }] } });
    expect(recordRequest(base, q.label, q.sourceStrategy, r, new Date(NOW)).project).toEqual(ran.p);
    expect(ran.toasts).toEqual([REQUEST_AI_DONE]);
    // No strategy from the model: "either".
    const b = suggestedRequest({ label: " Bez strategie " });
    expect((await run({ label: " Bez strategie " })).posts[0].b).toEqual(requestBody(b.label, b.sourceStrategy, b.extra));
    expect(b.sourceStrategy).toBe("either");
  });
  it("openDimensionResearch1793's topic", () => {
    const ran = legacy.run<{ topic: string; tab: string; gone: string[] }>(
      "GONE=[];var __el={value:''};INPUTS={libResearchTopic:__el};openDimensionResearch1793('Důvěra v AI');({topic:__el.value,tab:LIBRARY_TAB,gone:GONE})",
    );
    expect(ran).toEqual({ topic: dimensionResearchTopic("Důvěra v AI"), tab: "research", gone: ["data"] });
  });
});

describe("the society-factor card waits for the audience catalogue", () => {
  it("a catalogue that fails to load is asked for again on every draw, with no limit, as the classic does (OI-57)", async () => {
    // The 1793 wrapper draws the card only once AUDIENCE_DIM_CATALOG_1793 is
    // set; until then every draw asks for it and draws again when it settles.
    // A failed load leaves it unset, so the next draw asks again at once. The
    // stub fails nineteen times and answers the twentieth, so the run ends.
    const l = legacyContext({
      prelude: [
        "var CURRENT='persona',AUDIENCE_DIM_CATALOG_1793=null,PERSONA_AI_SUGGESTION=null,ASKED=0,DRAWN='',DONE;const WHEN=new Promise(r=>DONE=r);",
        "function _renderPersona1793(){}function $(){return {insertAdjacentHTML(p,h){DRAWN=h;DONE(ASKED)}}}function E(x){return String(x??'')}function renderAudience(){}",
        "const console={error(){}};async function jget(ep){ASKED++;if(ASKED<20)throw Error('down');return {filterable_count:3,categories:[]}}",
      ],
      functions: ["ensureAudienceDimensionCatalog1793", "renderPersona"],
    });
    const asked = await l.run<Promise<number>>("renderPersona();WHEN");
    expect(asked).toBe(20);
    expect(l.run<string>("DRAWN")).toContain("FAKTORY SPOLEČNOSTI");
  });
});
