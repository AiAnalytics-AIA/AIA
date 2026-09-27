import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { declaration, effective, legacyContext, statement } from "@/testing/legacy";
import {
  type Catalog,
  type Catalogues,
  PREVIEW_NO_DATASET,
  PROPOSE_EMPTY,
  PROPOSE_FAILED_SUFFIX,
  PROPOSE_TITLE,
  PROPOSE_UNCOVERED,
  PROPOSE_WARN_MS,
  SPECIAL_AUDIENCE_PRESETS,
  UPLOAD_DONE,
  UPLOAD_NO_FILE,
  analyticsBack,
  applyProposal,
  applyUpload,
  audienceReady,
  audienceView,
  chooseAudience,
  chooseSpecialPreset,
  customerAudiences,
  factorStatus,
  filterCategories,
  filterChips,
  filterableFactors,
  humanFilters,
  humanSummary,
  previewRequest,
  previewVerdict,
  proposePayload,
  proposeText,
  rangeOf,
  removeAudienceFactor,
  selectAudienceDataset,
  selectedValues,
  setAnalyticsChoice,
  setAudienceCategory,
  setAudienceEntry,
  setAudienceRange,
  specialSelected,
  uploadBody,
} from "./audience";
import { type Template, type ResearchProject, defaultsMerge } from "./model";

// Audience against the classic interface's own functions, run under Node with
// the inputs, the save, the render and the network stubbed and recorded.
const EMPTY = JSON.parse(readFileSync(join(process.cwd(), "src/research/fixtures/empty-project.json"), "utf8"));
const BOOT: Template = { empty_project: EMPTY, ai_provider: "claude_code_subscription" };
const CATALOGUES: Catalogues = {
  population_subpanels: [
    { key: "medical_doctors", name: "Lékaři", description: "Profesní subpanel", filter: { profese: ["lékař"], vek: [25, 70] }, status: "ready", support_tier: "LOW", rows: 120 },
    { key: "young_18_29", name: "Mladí 18–29", filter: { vek: [18, 29] }, status: "ready", support_tier: "ROBUST" },
  ],
  special_panels: [{ key: "healthcare_clinical_professionals", name: "Klinické profese", support: "STRUCTURAL_ONLY" }],
};
const CATALOG: Catalog = {
  filterable_count: 5,
  categories: [
    { id: "demography", label: "Demografie", filterable_count: 3, count: 3 },
    { id: "media", label: "Média", filterable_count: 2, count: 2 },
    { id: "research_only", label: "Research-only", filterable_count: 0, count: 4 },
  ],
  factors: [
    { id: "vek", label: "Věk", category: "demography", category_label: "Demografie", kind: "numeric", status: "PANEL_EXISTING", filterable: true, min: 18, max: 77 },
    { id: "kraj", label: "Kraj", category: "demography", category_label: "Demografie", kind: "category", status: "PANEL_EXISTING", filterable: true, values: [{ value: "A", count: 20 }, { value: "B", count: 40 }] },
    { id: "pohlavi", label: "Pohlaví", category: "demography", category_label: "Demografie", kind: "category", status: "DERIVED_EXISTING_SIGNALS", filterable: true, values: [{ value: "muž", count: 30 }] },
    { id: "tiktok", label: "TikTok", category: "media", category_label: "Média", kind: "binary", status: "SIMULATED_FROM_EVIDENCE", filterable: true, values: [{ value: "1", count: 9 }] },
    { id: "zdravi_x", label: "Zdraví", category: "media", category_label: "Média", kind: "category", status: "PANEL_EXISTING_RESEARCH_ONLY", filterable: false },
  ],
};

const legacy = legacyContext({
  host: { btoa },
  prelude: [
    "var CURRENT='audience',SAVES=[],ALERTS=[],TOASTS=[],POSTS=[],GETS=[],JOBS=[],RESULT=null,GET_RESULT=[],VIEW='',INPUTS={},FILE=null,READY=true;",
    "var PROJECT=null,AUDIENCE_PREVIEW=null,AUDIENCE_DIM_CATALOG_1793=null,AUDIENCE_DIM_CATEGORY_1793='demography',AUDIENCE_DIM_SEARCH_1793='',BOOT={};",
    "const clone=x=>JSON.parse(JSON.stringify(x));",
    "function save(r,inv){SAVES.push([r||'autosave',inv!==false])}function renderAudience(){}function alert(m){ALERTS.push(m)}function toast(m){TOASTS.push(m)}",
    "function progress(){}function setTimeout(){}function E(x){return String(x??'')}function title(){}var document={getElementById(){return null}};",
    "function $(s){if(s==='#view')return {set innerHTML(v){VIEW=v},get innerHTML(){return VIEW}};if(s==='#audFile')return {files:FILE?[FILE]:[]};if(s.startsWith('#'))return s.slice(1) in INPUTS?{value:INPUTS[s.slice(1)]}:null;return null}",
    "async function jpost(ep,b,t){POSTS.push({ep,b:clone(b),t:t??null});return RESULT}async function jget(ep){GETS.push(ep);return GET_RESULT}",
    "async function job(ep,payload,title,opts){JOBS.push({ep,payload:clone(payload),title,opts});return RESULT}",
    "async function ensureClaudeReady1776(){return READY}function storeAIError1776(stage,e){return String(e?.message||'AI krok se nepodařilo dokončit.')}",
    "function audienceDatasetEditor(){return 'DATASET EDITOR'}function filterEditor(){return 'FILTER EDITOR'}function discoverEditor(){return 'DISCOVER EDITOR'}",
    statement("SPECIAL_AUDIENCE_PRESETS=[", "];").replace(/^/, "var "),
  ],
  functions: [
    "defaultsMerge",
    "audienceReady1789",
    "setAudienceEntry",
    "setAnalyticsChoice",
    "chooseAudience",
    "chooseSpecialPreset",
    "usePopulationSubpanel",
    "selectAudienceDataset",
    "setAudienceCategory1793",
    "setAudienceRange1793",
    "removeAudienceFactor1793",
    "selectedAudienceFilters1793",
    "humanizeAudienceFilters1795",
    "audienceHumanSummary1795",
    "previewAudience",
    "audPreviewHtml",
    "factorEditor1793",
    "factorStatus1793",
    "specialPresetHtml",
    "proposeAudience",
    "uploadAudience",
  ],
});
legacy.run(declaration("renderAudience").replace("function renderAudience(", "function renderAudienceBase("));
// The factor editor, with the three globals it reads.
legacy.run(effective("filterEditor").replace("var filterEditor=function", "var filterEditorReal=function"));

const base = defaultsMerge({ goal: "Zjistit zájem", n: 600, briefing: { product_description: "Nápoj" } }, BOOT);
const withA = (a: Record<string, unknown>, u: Record<string, unknown> = {}): ResearchProject =>
  ({ ...base, audience: { ...base.audience, ...a }, ui_state: { ...base.ui_state, ...u } }) as ResearchProject;

type Ran = { p: ResearchProject; saves: [string, boolean][]; alerts: string[]; toasts: string[]; posts: { ep: string; b: unknown; t: unknown }[]; gets: string[]; jobs: { ep: string; payload: unknown; title: string; opts: unknown }[]; view: string; preview: unknown };
const RESET = "SAVES=[];ALERTS=[];TOASTS=[];POSTS=[];GETS=[];JOBS=[];VIEW='';FILE=null;AUDIENCE_PREVIEW='kept';";
const OUT = "({p:PROJECT,saves:SAVES,alerts:ALERTS,toasts:TOASTS,posts:POSTS,gets:GETS,jobs:JOBS,view:VIEW,preview:AUDIENCE_PREVIEW})";
type G = { p?: ResearchProject; inputs?: Record<string, string>; result?: unknown; getResult?: unknown; ready?: boolean; catalog?: Catalog | null };
const globals = (g: G) => ({
  __p: g.p ?? base, __i: g.inputs ?? {}, __r: g.result ?? null, __g: g.getResult ?? [], __ready: g.ready ?? true,
  __cat: g.catalog === undefined ? CATALOG : g.catalog, BOOT: { ...CATALOGUES, audiences: [] },
});
const SET = "PROJECT=__p;INPUTS=__i;RESULT=__r;GET_RESULT=__g;READY=__ready;AUDIENCE_DIM_CATALOG_1793=__cat;";
const classic = (call: string, g: G = {}): Ran => legacy.run<Ran>(`${RESET}${SET}${call};${OUT}`, globals(g));
const classicAsync = (call: string, g: G = {}, before = ""): Promise<Ran> =>
  legacy.run<Promise<Ran>>(`(async()=>{${RESET}${SET}${before}await ${call};return ${OUT}})()`, globals(g));

describe("which screen the audience step draws, and when it is ready", () => {
  const cases: [string, ResearchProject][] = [
    ["nothing chosen", base],
    ["own, no dataset", withA({}, { audience_entry: "own" })],
    ["own, a dataset", withA({ dataset_id: "AUD-1" }, { audience_entry: "own" })],
    ["analytics, no branch", withA({}, { audience_entry: "analytics" })],
    ["analytics, coming soon", withA({}, { audience_entry: "analytics", analytics_choice: "cz_coming" })],
    ["analytics, special, nothing", withA({}, { audience_entry: "analytics", analytics_choice: "special" })],
    ["analytics, special, a subpanel", withA({ builtin_subpanel: "x" }, { audience_entry: "analytics", analytics_choice: "special" })],
    ["analytics, special, a panel key", withA({ special_panel_key: "x" }, { audience_entry: "analytics", analytics_choice: "special" })],
    ["analytics, ČR 18+", withA({}, { audience_entry: "analytics", analytics_choice: "cz18" })],
    ["analytics, ČR 18+ narrowed", withA({ strategy: "filters" }, { audience_entry: "analytics", analytics_choice: "cz18" })],
    ["analytics, ČR 18+ ideal group", withA({ strategy: "discover" }, { audience_entry: "analytics", analytics_choice: "cz18" })],
  ];
  const markers: Record<string, string> = {
    choose: "Odkud mají respondenti pocházet?",
    own: "DATASET EDITOR",
    analytics: '<div class="flowChoice" onclick="setAnalyticsChoice(\'cz18\')">',
    cz_coming: "Česká populace · COMING SOON",
    special: "<h2>Special Audience</h2>",
    cz18: '<div class="sectiontitle">Česká populace (+18)</div>',
  };
  for (const [name, p] of cases) {
    it(name, () => {
      const ran = classic("renderAudienceBase()", { p });
      const v = audienceView(p);
      expect(ran.view).toContain(markers[v]);
      for (const [k, m] of Object.entries(markers)) if (k !== v) expect(ran.view).not.toContain(m);
      expect(audienceReady(p)).toBe(legacy.run("PROJECT=__p;audienceReady1789()", { __p: p }));
      if (v === "special") expect(ran.view.includes("<b>Vybráno:</b>")).toBe(specialSelected(p));
      if (v === "cz18") {
        expect(ran.view.includes("FILTER EDITOR")).toBe(p.audience.strategy === "filters");
        expect(ran.view.includes("DISCOVER EDITOR")).toBe(p.audience.strategy === "discover");
      }
    });
  }
});

describe("the branch and strategy choosers are the classic ones", () => {
  for (const x of ["choose", "own", "analytics"] as const) {
    it(`setAudienceEntry(${x})`, () => {
      const p = withA({ source_mode: "population", dataset_id: "D", dataset_name: "N", filters: { vek: [1, 2] } }, { analytics_choice: "cz18" });
      const ran = classic(`setAudienceEntry(${JSON.stringify(x)})`, { p });
      const got = setAudienceEntry(p, x);
      expect(got.project).toEqual(ran.p);
      expect(ran.saves).toEqual([[got.reason, got.invalidateCheck]]);
      expect(ran.preview).toBeNull();
    });
  }
  for (const x of ["population", "filters", "discover"] as const) {
    for (const [name, a] of [["from scratch", {}], ["with a description and filters", { description: "Pražané", filters: { kraj: ["A"] }, builtin_subpanel: "s" }], ["the default description", { description: "ČR 18+", product_description: "Vlastní" }]] as const) {
      it(`chooseAudience(${x}), ${name}`, () => {
        const p = withA(a);
        const ran = classic(`chooseAudience(${JSON.stringify(x)})`, { p });
        const got = chooseAudience(p, x);
        expect(got.project).toEqual(ran.p);
        expect(ran.saves).toEqual([[got.reason, got.invalidateCheck]]);
      });
    }
  }
  for (const x of ["cz18", "cz_coming", "special"] as const) {
    it(`setAnalyticsChoice(${x})`, () => {
      const p = withA({ dataset_id: "D", builtin_subpanel: "s", special_panel_key: "k", special_catalog_key: "c", filters: { kraj: ["A"] } });
      const ran = classic(`setAnalyticsChoice(${JSON.stringify(x)})`, { p });
      const got = setAnalyticsChoice(p, x);
      expect(got.project).toEqual(ran.p);
      expect(ran.saves).toEqual([[got.reason, got.invalidateCheck]]);
    });
  }
  it("the analytics branches' back button", () => {
    const p = withA({}, { analytics_choice: "special" });
    const code = legacy.run<string>("PROJECT=__p;renderAudienceBase();VIEW", { __p: withA({}, { audience_entry: "analytics", analytics_choice: "special" }) });
    const handler = code.match(/onclick="(PROJECT\.ui_state\.analytics_choice='';[^"]*)"/)![1];
    const ran = classic(handler, { p });
    const got = analyticsBack(p);
    expect(got.project).toEqual(ran.p);
    expect(ran.saves).toEqual([[got.reason, got.invalidateCheck]]);
  });
});

describe("the special presets are SPECIAL_AUDIENCE_PRESETS and chooseSpecialPreset", () => {
  it("the six presets, in order", () => {
    expect(legacy.run("SPECIAL_AUDIENCE_PRESETS")).toEqual(SPECIAL_AUDIENCE_PRESETS.map((x) => ({ ...x })));
  });
  for (const x of [...SPECIAL_AUDIENCE_PRESETS.map((z) => z.key), "nope"]) {
    it(`choosing ${x} on a clean project`, () => {
      const ran = classic(`chooseSpecialPreset(${JSON.stringify(x)})`);
      const got = chooseSpecialPreset(base, x, CATALOGUES);
      expect(got?.project ?? base).toEqual(ran.p);
      expect(ran.saves.at(-1) ?? null).toEqual(got ? [got.reason, got.invalidateCheck] : null);
    });
  }
  it("a special preset keeps the previous subpanel and filters, as the classic does (OI-51)", () => {
    const ran = classic("chooseSpecialPreset('doctors');chooseSpecialPreset('foreign_prague')", { p: withA({}, { audience_entry: "analytics", analytics_choice: "special" }) });
    const first = chooseSpecialPreset(withA({}, { audience_entry: "analytics", analytics_choice: "special" }), "doctors", CATALOGUES)!;
    const got = chooseSpecialPreset(first.project, "foreign_prague", CATALOGUES)!;
    expect(got.project).toEqual(ran.p);
    expect(got.project.audience).toMatchObject({ dataset_name: "Cizinci žijící v Praze", builtin_subpanel: "medical_doctors", filters: { profese: ["lékař"], vek: [25, 70] } });
    expect(audienceReady(got.project)).toBe(true);
  });
  it("a special panel after a subpanel also keeps it (OI-51)", () => {
    const first = chooseSpecialPreset(base, "young", CATALOGUES)!;
    const got = chooseSpecialPreset(first.project, "health", CATALOGUES)!;
    expect(got.project).toEqual(classic("chooseSpecialPreset('young');chooseSpecialPreset('health')").p);
    expect(got.project.audience.builtin_subpanel).toBe("young_18_29");
  });
  it("the preset list marks the chosen one and the ones needing own data", () => {
    const p = withA({ special_catalog_key: "health" });
    const html = legacy.run<string>("PROJECT=__p;specialPresetHtml()", { __p: p });
    expect((html.match(/audiencePreset selected/g) || []).length).toBe(1);
    expect((html.match(/VLASTNÍ DATA/g) || []).length).toBe(SPECIAL_AUDIENCE_PRESETS.filter((x) => x.kind === "coming_soon").length);
  });
});

describe("the factor editor is filterEditor and its handlers", () => {
  for (const [category, query] of [["demography", ""], ["all", ""], ["media", ""], ["all", "kr"], ["all", "média"], ["all", "zdraví"]] as const) {
    it(`factors of ${category}, search ${JSON.stringify(query)}`, () => {
      const html = legacy.run<string>(`AUDIENCE_DIM_CATALOG_1793=__cat;AUDIENCE_DIM_CATEGORY_1793=__c;AUDIENCE_DIM_SEARCH_1793=__q;PROJECT=__p;filterEditorReal()`, { __cat: CATALOG, __c: category, __q: query, __p: base });
      const { shown } = filterableFactors(CATALOG, category, query);
      const drawn = [...html.matchAll(/<div class="dimRow1789[^"]*"><div style="flex:1"><b>([^<]*)<\/b>/g)].map((m) => m[1]);
      expect(drawn).toEqual(shown.map((f) => f.label));
      const { categories, sensitive } = filterCategories(CATALOG);
      for (const c of categories) expect(html).toContain(`${c.label} · ${c.filterable_count}`);
      expect(html).toContain(`${sensitive} research-only signálů`);
    });
  }
  it("each factor's status label", () => {
    for (const s of ["PANEL_EXISTING", "DERIVED_EXISTING_SIGNALS", "SIMULATED_FROM_EVIDENCE", "PANEL_EXISTING_RESEARCH_ONLY", "OTHER", undefined]) {
      expect(factorStatus(s)).toBe(legacy.run("factorStatus1793(__s)", { __s: s }));
    }
  });
  it("a factor's current value, as factorEditor1793 reads it", () => {
    const p = withA({ filters: { vek: { min: 25, max: null }, kraj: ["A"], pohlavi: "muž", tiktok: [18, 30] } });
    for (const f of CATALOG.factors!.filter((x) => x.filterable)) {
      const html = legacy.run<string>("PROJECT=__p;factorEditor1793(__f)", { __p: p, __f: f });
      if (f.kind === "numeric") {
        const { lo, hi } = rangeOf(p, f.id);
        expect(html).toContain(`value="${lo ?? ""}"`);
        expect(html).toContain(`value="${hi ?? ""}"`);
      } else {
        const sel = selectedValues(p, f.id);
        for (const v of f.values || []) expect(html.includes(`<option value="${v.value}" selected>`)).toBe(sel.has(v.value));
      }
    }
    expect(rangeOf(p, "tiktok")).toEqual({ lo: 18, hi: 30 });
  });
  for (const values of [["A", "B"], []]) {
    it(`setAudienceCategory1793 with ${values.length} value(s), then a preview`, async () => {
      const p = withA({ filters: { kraj: ["B"], vek: [1, 2] } });
      const ran = await classicAsync(`setAudienceCategory1793('kraj',{selectedOptions:${JSON.stringify(values.map((value) => ({ value })))}})`, { p, result: { ok: true } });
      const got = setAudienceCategory(p, "kraj", values);
      expect(got.project).toEqual(ran.p);
      expect(ran.saves).toEqual([[got.reason, got.invalidateCheck]]);
      expect(ran.posts.map((x) => x.ep)).toEqual(["/api/audience"]);
    });
  }
  const ranges: [string, string | undefined, string | undefined][] = [
    ["both bounds", "25", "44"],
    ["only the lower bound", "25", ""],
    ["only the upper bound", "", "44"],
    ["both empty", "", ""],
    ["no inputs at all", undefined, undefined],
    ["decimals", "1.5", "2.25"],
  ];
  for (const [name, lo, hi] of ranges) {
    it(`setAudienceRange1793, ${name}`, () => {
      const inputs: Record<string, string> = {};
      if (lo !== undefined) inputs.afMin_vek = lo;
      if (hi !== undefined) inputs.afMax_vek = hi;
      const ran = classic("setAudienceRange1793('vek','afMin_vek','afMax_vek')", { inputs, result: { ok: true } });
      const got = setAudienceRange(base, "vek", lo, hi);
      expect(got.project).toEqual(ran.p);
      expect(ran.saves).toEqual([[got.reason, got.invalidateCheck]]);
    });
  }
  it("an empty bound is stored as 0, as the classic does (OI-50)", () => {
    expect(setAudienceRange(base, "vek", "25", "").project.audience.filters).toEqual({ vek: { min: 25, max: 0 } });
    expect(setAudienceRange(base, "vek", "", "").project.audience.filters).toEqual({ vek: { min: 0, max: 0 } });
  });
  it("removeAudienceFactor1793, and the chips of what is selected", () => {
    const p = withA({ filters: { vek: { min: 25, max: null }, kraj: ["A", "B"], neznamy: "x", tiktok: [18, 30] } });
    const ran = classic("removeAudienceFactor1793('kraj')", { p });
    const got = removeAudienceFactor(p, "kraj");
    expect(got.project).toEqual(ran.p);
    expect(ran.saves).toEqual([[got.reason, got.invalidateCheck]]);
    const html = legacy.run<string>("PROJECT=__p;AUDIENCE_DIM_CATALOG_1793=__cat;selectedAudienceFilters1793()", { __p: p, __cat: CATALOG });
    for (const c of filterChips(p, CATALOG)) expect(html).toContain(`<b>${c.label}</b>: ${c.text} <button`);
  });
});

describe("the readable summary is audienceHumanSummary1795 and humanizeAudienceFilters1795", () => {
  it("population, planned N and source", () => {
    for (const a of [base.audience, { ...base.audience, population: "Pražané", n: 300, dataset_name: "Vlastní" }, undefined]) {
      const html = legacy.run<string>("audienceHumanSummary1795(__a)", { __a: a });
      const pairs = humanSummary(a as ResearchProject["audience"]);
      expect((html.match(/class="chip ok"/g) || []).length).toBe(pairs.length);
      for (const [k, v] of pairs) expect(html).toContain(`<b>${k}:</b>&nbsp;${v}`);
    }
  });
  it("filters with underscores as spaces; a range is od–do where the classic prints [object Object]", () => {
    const p = withA({ filters: { cilova_skupina: ["A", "B"], kraj: "Praha", prazdny: [], nic: "", vek: { min: 25, max: 44 } } });
    const html = legacy.run<string>("PROJECT=__p;humanizeAudienceFilters1795()", { __p: p });
    const pairs = humanFilters(p);
    expect(pairs).toEqual([["cilova skupina", "A, B"], ["kraj", "Praha"], ["vek", "25–44"]]);
    for (const [k, v] of pairs.slice(0, 2)) expect(html).toContain(`<b>${k}:</b>&nbsp;${v}`);
    expect(html).toContain("<b>vek:</b>&nbsp;[object Object]");
  });
});

describe("preview, preflight, own audiences, and the AI proposal", () => {
  for (const [name, p] of [
    ["the population", withA({ source_mode: "population", filters: { kraj: ["A"] } })],
    ["a dataset", withA({ source_mode: "special_audience", dataset_id: "builtin_special:x" })],
    ["no dataset", withA({ source_mode: "customer", dataset_id: "" })],
  ] as const) {
    it(`previewAudience: ${name}`, async () => {
      const ran = await classicAsync("previewAudience()", { p, result: { ok: true, support: 20 } });
      const req = previewRequest(p);
      if ("error" in req) {
        expect(ran.alerts).toEqual([PREVIEW_NO_DATASET]);
        expect(ran.posts).toEqual([]);
      } else {
        expect(ran.posts).toEqual([{ ep: req.route === "audiencePreview" ? "/api/audience" : "/api/audiences/preflight", b: req.body, t: null }]);
        expect(ran.preview).toEqual({ ok: true, support: 20 });
      }
    });
  }
  for (const r of [{ ok: true }, { ok: false }, { problems: [{ uroven: "error", text: "Málo lidí" }] }, { problemy: ["Chyba A"] }, { problems: [{ uroven: "WARN", text: "x" }] }]) {
    it(`the preview verdict for ${JSON.stringify(r)}`, () => {
      const html = legacy.run<string>("PROJECT=__p;audPreviewHtml(__r)", { __p: base, __r: r });
      const v = previewVerdict(r, base.n);
      expect(html.includes("okbox")).toBe(v.ok);
      expect(html).toContain(v.text);
    });
  }
  it("the saved customer audiences, and choosing one", () => {
    const list = [{ audience_id: "A1", name: "Lékaři ČR", rows: 120, type: "customer", population_definition: "Lékaři v praxi" }, { audience_id: "S1", name: "Speciální", type: "special_audience" }];
    expect(customerAudiences(list).map((x) => x.audience_id)).toEqual(["A1"]);
    for (const id of ["A1", "S1", ""]) {
      const ran = legacy.run<Ran>(`${RESET}PROJECT=__p;BOOT={audiences:__l};selectAudienceDataset(__id);${OUT}`, { __p: base, __l: list, __id: id });
      expect(selectAudienceDataset(base, id, list)).toEqual(ran.p);
      expect(ran.saves).toEqual([["autosave", true]]);
    }
  });
  it("uploadAudience: the body, the refreshed list, the dataset chosen", async () => {
    const r = { audience: { audience_id: "A9", name: "Moje", description: "Popis" }, preflight: { ok: true } };
    const ran = await classicAsync("uploadAudience()", { result: r, getResult: [{ audience_id: "A9" }], inputs: { audName: "  ", audDesc: " Kdo " } }, "FILE={name:'data.xlsx',arrayBuffer:async()=>new Uint8Array([65,66,67]).buffer};");
    expect(ran.posts).toEqual([{ ep: "/api/audiences/upload", b: uploadBody(base, { name: "data.xlsx", b64: btoa("ABC") }, "  ", " Kdo "), t: 180000 }]);
    expect(ran.gets).toEqual(["/api/audiences"]);
    expect(applyUpload(base, r)).toEqual(ran.p);
    expect(ran.preview).toEqual({ ok: true });
    expect(ran.saves).toEqual([["audience_upload", true]]);
    expect(ran.toasts).toEqual([UPLOAD_DONE]);
    expect((await classicAsync("uploadAudience()")).alerts).toEqual([UPLOAD_NO_FILE]);
  });
  for (const [name, typed, stored] of [["typed", " 25–44 v Praze ", ""], ["the stored description", "", "Zúžená cílová populace"], ["nothing", "", ""]] as const) {
    it(`proposeAudience: ${name}`, async () => {
      const p = withA({ description: stored, filters: { kraj: ["B"] } });
      const r = { filtry: { vek: [25, 44] }, feasibility: { ok: true }, nepokryto: "část" };
      const ran = await classicAsync("proposeAudience()", { p, result: r, inputs: { audText: typed } });
      const text = proposeText(typed, p);
      if (!text) {
        expect(ran.alerts).toEqual([PROPOSE_EMPTY]);
        return;
      }
      expect(ran.jobs).toEqual([{ ep: "/api/audience/propose", payload: proposePayload(p, text), title: PROPOSE_TITLE, opts: { maxMs: 240000, warnMs: PROPOSE_WARN_MS } }]);
      const got = applyProposal(p, text, r);
      expect(got.change.project).toEqual(ran.p);
      expect(ran.preview).toEqual(got.preview);
      expect(ran.saves).toEqual([[got.change.reason, got.change.invalidateCheck]]);
      expect(ran.toasts).toEqual(got.uncovered ? [PROPOSE_UNCOVERED] : []);
    });
  }
  it("proposeAudience stops when the provider is not ready, and words its failure", async () => {
    expect((await classicAsync("proposeAudience()", { inputs: { audText: "x" }, ready: false })).jobs).toEqual([]);
    const ran = await legacy.run<Promise<Ran>>(
      `(async()=>{${RESET}PROJECT=__p;INPUTS={audText:'x'};READY=true;const real=job;job=async()=>{throw Error('BOOM')};try{await proposeAudience()}finally{job=real}return ${OUT}})()`,
      { __p: base },
    );
    expect(ran.alerts).toEqual([`BOOM${PROPOSE_FAILED_SUFFIX}`]);
  });
});
