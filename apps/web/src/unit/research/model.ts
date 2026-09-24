// The research project (ADR 0014, area A4): the shape the classic flow keeps in
// `PROJECT` and `ANALYSIS`, and the functions that normalise and fingerprint it,
// ported from the JavaScript that runs (tools/ui_functions.py effective <name>).
// model.parity.test.ts runs each original under Node and compares.
//
// A project is the unit's document, stored whole by POST /api/projects/save.
// Fields the rebuilt screens read are typed; everything else is carried through
// untouched, so a screen never drops a field it does not know.

export type Json = null | boolean | number | string | Json[] | { [k: string]: Json };
type Obj = { [k: string]: Json };

export type Attachment = {
  kind?: string;
  filename?: string;
  url?: string;
  title?: string;
  size_bytes?: number;
  text_extracted?: boolean;
  context_excerpt?: string;
  sha256?: string;
};

export type Briefing = Obj & {
  problem_type?: string;
  problem_types?: string[];
  product_description?: string;
  situation?: string;
  what_is_known?: string;
  constraints?: string;
  review_comments?: string;
  attachments?: Attachment[];
  attachments_context?: string;
};

export type ResearchProject = Obj & {
  title?: string;
  goal?: string;
  decision_use?: string;
  n?: number;
  model?: string;
  briefing: Briefing;
  research_plan: Obj;
  study_config: Obj;
  instrument_library: Obj;
  audience: Obj & { source_mode?: string; strategy?: string; filters?: Obj };
  discovery: Obj;
  budget: Obj;
  run_policy: Obj & { phase_overrides?: Obj };
  sections: Json[];
  ui_state: Obj & { problem_types?: string[] };
  panel_mode?: string;
  ai_panel_profile?: Obj;
};

/** The unit's template for a new project and its default provider (GET /api/bootstrap). */
export type Boot = { empty_project: Obj; ai_provider?: string };

const obj = (x: unknown): Obj => (x && typeof x === "object" && !Array.isArray(x) ? (x as Obj) : {});
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

/** defaultsMerge @101368: a stored project over the unit's empty template. */
export function defaultsMerge(p: unknown, boot: Boot): ResearchProject {
  const d = clone(boot.empty_project);
  const x = obj(p);
  const dd = (k: string) => obj(d[k]);
  const xx = (k: string) => obj(x[k]);
  const out: Obj = { ...d, ...x };
  out.briefing = { ...dd("briefing"), ...xx("briefing") };
  out.research_plan = { ...dd("research_plan"), ...xx("research_plan") };
  out.study_config = { ...dd("study_config"), ...xx("study_config") };
  out.instrument_library = { ...dd("instrument_library"), ...xx("instrument_library") };
  out.audience = { ...dd("audience"), ...xx("audience") };
  out.discovery = { ...dd("discovery"), ...xx("discovery") };
  out.budget = { ...(d.budget ? dd("budget") : { max_usd: null, warning_pct: 80 }), ...xx("budget") };
  const defaultPolicy: Obj = {
    provider: boot.ai_provider || "claude_code_subscription",
    allow_provider_fallback: false,
    auto_resume_capacity: true,
    cost_mode: "REFERENCE",
    phase_overrides: {},
  };
  const policy: Obj = { ...(d.run_policy ? dd("run_policy") : defaultPolicy), ...xx("run_policy") };
  policy.phase_overrides = { ...obj(dd("run_policy").phase_overrides), ...obj(xx("run_policy").phase_overrides) };
  out.run_policy = policy;
  out.sections = (x.sections as Json[] | undefined) || [];
  out.model = x.model || d.model || "sonnet";
  out.ui_state = {
    questionnaire_path: "choose",
    audience_entry: "choose",
    analytics_choice: "",
    persona_path: "choose",
    ...dd("ui_state"),
    ...xx("ui_state"),
  };
  const audience = out.audience as Obj;
  if (!audience.source_mode) audience.source_mode = "population";
  if (!audience.strategy) audience.strategy = Object.keys(obj(audience.filters)).length ? "filters" : "population";
  out.panel_mode = out.panel_mode || "standard";
  out.ai_panel_profile = out.ai_panel_profile || {};
  return out as ResearchProject;
}

/** PROBLEM_TYPES_1785 after its final splice @495760: key, label, sub, default goal. */
export const PROBLEM_TYPES: readonly (readonly [string, string, string, string])[] = [
  ["price", "Pricing / cenový test", "Cena, sleva, elasticita", "Zjistit, jak změna ceny ovlivní zájem, nákup, vnímání hodnoty a značky."],
  ["product", "Nový produkt / koncept", "Koncept, nabídka, launch", "Zjistit, zda nový produkt nebo koncept dává lidem smysl, komu a proč."],
  ["audience", "Hledání cílovky", "Segmenty, potenciál", "Najít skupiny s nejvyšším potenciálem a pochopit, čím se liší."],
  ["communication", "Komunikace / kreativa", "Message, claim, kreativa", "Zjistit, jak lidé rozumí komunikaci, co funguje a co vytváří bariéry."],
  ["brand", "Brand / positioning", "Vnímání, asociace, rebranding", "Zjistit, jak je značka vnímaná, proti komu stojí a co posiluje nebo oslabuje její pozici."],
  ["innovation", "Hledání mezery na trhu", "Whitespace, inovace, unmet needs", "Najít, kde je mezera, pro koho a jaký koncept má největší šanci."],
  ["portfolio", "Portfolio / varianty", "Feature, pack, SKU, porovnání variant", "Vybrat z více variant nejsilnější řešení a pochopit trade-offy."],
  ["campaign", "Kampaň / veřejné téma", "Kampaň, kandidát, policy", "Ověřit reakce na kandidáty, kampaně, opatření nebo veřejné scénáře."],
  ["tracking", "Tracking / health check", "Vývoj v čase, benchmark", "Sledovat, co se mění, kde se zhoršuje výkon a kde je příležitost."],
  ["other", "Jiné / vlastní zadání", "Vlastní kombinace", ""],
];

/** selectedProblemTypes1789: the selected keys, known ones only, first occurrence kept. */
export function selectedProblemTypes(p: ResearchProject): string[] {
  let a: unknown = p.briefing?.problem_types;
  if (!Array.isArray(a) || !a.length) a = p.ui_state?.problem_types || [];
  if ((!Array.isArray(a) || !a.length) && p.briefing?.problem_type) a = [p.briefing.problem_type];
  const known = new Set(PROBLEM_TYPES.map((t) => t[0]));
  return [...new Set(((a as unknown[]) || []).filter((x): x is string => typeof x === "string" && known.has(x)))];
}

/**
 * briefFingerprint1780, its last assignment @419471: what the AI analysis of a
 * brief depends on. An analysis carrying the same `_brief_signature` is reused
 * instead of asking the model again.
 */
export function briefFingerprint(p: ResearchProject): string {
  const b = p.briefing || {};
  const s = (v: unknown) => String(v || "").trim();
  return JSON.stringify({
    goal: s(p.goal),
    decision_use: s(p.decision_use),
    product_description: s(b.product_description),
    situation: s(b.situation),
    what_is_known: s(b.what_is_known),
    constraints: s(b.constraints),
    problem_types: selectedProblemTypes(p).slice().sort(),
    review_comments: String(b.review_comments || ""),
    attachments: (b.attachments || []).map((x) => x.sha256 || x.url || x.filename),
  });
}
