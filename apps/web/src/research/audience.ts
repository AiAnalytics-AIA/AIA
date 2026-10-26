// Audience, the research flow's fourth step (ADR 0014, area A4): what the
// classic step does to the project, ported from the bindings that run --
// renderAudience (:374) under its three wrappers (1785 :899, 1789 :961,
// 1795 :1173), the branch and preset choosers, the factor editor, the
// readiness rule, the preview and preflight requests, the upload, and the AI
// proposal. Every function is pure and returns the next project with the
// classic save reason. audience.parity.test.ts compares each with the original
// under Node. OI-50 (an empty range bound is 0) is kept and characterised; AIA's
// own range writer (setRange) leaves an empty bound out. OI-51 is fixed by the
// product owner's decisions (2026-10-25): a preset change no longer keeps the
// previous subpanel, filters, strategy or support figures, and keeps the
// description (presetReset), a stated departure from the classic.
//
// Since ADR 0018 the product draws only what needs no 18.6.6. Since
// panel-grounded-respondents 6e the factor catalogue, the preview and the
// built-in subpanels are AIA's again, computed from its own population (the
// "live" functions at the end of this file read the API's answers); the special
// panels and the customer audience upload were the unit's audience store, and the
// step still says they are not in AIA.

import type { AudienceCatalogue, AudienceCatalogueSubpanel, AudiencePreview } from "@/lib/api";

import { type Json, PROVIDER_FORCED, type ResearchProject } from "./model";

type Obj = { [k: string]: Json };
export type Audience = ResearchProject["audience"];
export type Change = { project: ResearchProject; reason: string; invalidateCheck: boolean };

const aud = (p: ResearchProject): Audience => (p.audience || {}) as Audience;
const withAudience = (p: ResearchProject, a: Audience): ResearchProject => ({ ...p, audience: a });
const ui = (p: ResearchProject) => (p.ui_state || {}) as Obj;

export type AudienceView = "choose" | "own" | "analytics" | "cz_coming" | "special" | "cz18";

/** Which screen the base renderAudience draws. */
export function audienceView(p: ResearchProject): AudienceView {
  const entry = String(ui(p).audience_entry || "choose");
  const choice = String(ui(p).analytics_choice || "");
  if (entry === "choose") return "choose";
  if (entry === "own") return "own";
  if (!choice) return "analytics";
  if (choice === "cz_coming") return "cz_coming";
  if (choice === "special") return "special";
  return "cz18";
}

/** audienceReady1789: the wizard's condition. */
export function audienceReady(p: ResearchProject): boolean {
  const a = aud(p);
  const u = ui(p);
  if (u.audience_entry === "own") return !!a.dataset_id;
  if (u.audience_entry === "analytics") {
    if (u.analytics_choice === "cz18") return true;
    if (u.analytics_choice === "special") return !!(a.dataset_id || a.builtin_subpanel || a.special_panel_key || a.builtin_special_key);
  }
  return false;
}

/**
 * R4 (research stages v73, spec vzorek/A1): one choice of three. The source and population questions
 * are gone, so a choice made on the screen writes the one entry AIA has, ČR 18+, which keeps
 * audienceReady's rule. A study stored otherwise is read as it is until the person chooses.
 */
export function normalizeEntry(p: ResearchProject): ResearchProject {
  const u = ui(p);
  if (u.audience_entry === "analytics" && u.analytics_choice === "cz18") return p;
  return { ...p, ui_state: { ...u, audience_entry: "analytics", analytics_choice: "cz18" } };
}

/** The strategy the screen shows chosen: none until one was chosen on ČR 18+; a stored subpanel reads as Zúžit. */
export function strategyOf(p: ResearchProject): Strategy | null {
  const u = ui(p);
  if (u.audience_entry !== "analytics") return null;
  if (u.analytics_choice === "cz18") return (aud(p).strategy || "population") as Strategy;
  return u.analytics_choice === "special" && aud(p).builtin_subpanel ? "filters" : null;
}

/**
 * A choice on the one question (R4). It starts afresh as a preset change does (OI-51 (a), "Clear
 * both"): the previous subpanel, filters, strategy and support figures go, and the run check is made
 * stale only when who is sampled changed. The description stays as written (the product owner,
 * 2026-10-25); only where none is written, or the classic's own "Zúžená cílová populace" would
 * describe the whole population, does Celá ČR 18+ write the classic's "ČR 18+". Choosing what is
 * already chosen, or Najít ve výsledcích, changes nothing.
 */
export function chooseStrategy(p: ResearchProject, x: Strategy): Change | null {
  if (x === "discover" || strategyOf(p) === x) return null;
  const { audience, cleared } = presetReset(aud(p));
  const c = chooseAudience(normalizeEntry(withAudience(p, audience)), x);
  const written = aud(p).description;
  const keep = x === "population" && written && written !== "Zúžená cílová populace";
  return { ...c, project: keep ? withAudience(c.project, { ...aud(c.project), description: written }) : c.project, invalidateCheck: c.invalidateCheck || cleared };
}

/**
 * A filter edit on a chosen subpanel's filters (Zúžit shows both since R4): the audience is no
 * longer that subpanel, so its name and support figures go, as a preset change clears them (OI-51
 * (a)), and the run check is made stale. Compile records `builtin_subpanel`, so keeping it would name
 * a subpanel over filters it does not have. The description stays as written; the subpanel can be
 * chosen again. A study stored on the classic's special path is written as ČR 18+ (normalizeEntry),
 * so its filters stay Zúžit's. A change on no subpanel passes through.
 */
export function detachSubpanel(c: Change): Change {
  const a = aud(c.project);
  if (!a.builtin_subpanel) return c;
  return { ...c, project: normalizeEntry(withAudience(c.project, { ...a, builtin_subpanel: "", support_tier: "", subpanel_status: "", support_summary: {} })), invalidateCheck: true };
}

/** What a study stored on a path the screen no longer offers: kept in the design, unused by a run. */
export type Kept = { kind: "dataset" | "special"; name: string } | { kind: "discover" };

export function keptPaths(p: ResearchProject): Kept[] {
  const a = aud(p);
  const u = ui(p);
  const kept: Kept[] = [];
  if (u.audience_entry === "own" && a.dataset_id) kept.push({ kind: "dataset", name: String(a.dataset_name || a.dataset_id) });
  const special = a.special_catalog_key || a.special_panel_key || a.builtin_special_key;
  if (u.analytics_choice === "special" && !a.builtin_subpanel && special) kept.push({ kind: "special", name: String(a.dataset_name || a.description || special) });
  if (a.strategy === "discover") kept.push({ kind: "discover" });
  return kept;
}

/** The special screen's "Vybráno" card. */
export function specialSelected(p: ResearchProject): boolean {
  const a = aud(p);
  return !!(a.dataset_id || a.builtin_subpanel || a.special_panel_key || a.builtin_special_key);
}

/**
 * What a preset change clears (OI-51 (a), the product owner, 2026-10-25): the previous audience's
 * subpanel, filters and segment, its strategy and the subpanel's support figures (back to the
 * template's defaults: "population", "" and {}), and a special panel's keys, so a new preset never
 * carries who the last one sampled or what supported it. The classic kept them; this is a stated
 * departure. The description stays as it is (the product owner, 2026-10-25). Answers whether who is
 * sampled changed (the support figures alone do not), so the run check is invalidated only then.
 */
export function presetReset(a: Audience): { audience: Audience; cleared: boolean } {
  const filled = (v: unknown): boolean => (v && typeof v === "object" ? Object.keys(v).length > 0 : !!v);
  const segment = a.segment;
  const segmentMode = segment && typeof segment === "object" && !Array.isArray(segment) ? (segment as Obj).mode : undefined;
  const cleared =
    ["builtin_subpanel", "filters", "special_panel_key", "builtin_special_key"].some((k) => filled(a[k])) ||
    (filled(segmentMode) && segmentMode !== "none") ||
    (filled(a.strategy) && a.strategy !== "population");
  return {
    audience: {
      ...a,
      builtin_subpanel: "",
      filters: {},
      segment: { mode: "none" },
      strategy: "population",
      special_panel_key: "",
      builtin_special_key: "",
      support_tier: "",
      subpanel_status: "",
      support_summary: {},
    },
    cleared,
  };
}

export function setAudienceEntry(p: ResearchProject, x: "choose" | "own" | "analytics"): Change {
  let a = { ...aud(p) };
  let cleared = false;
  if (x === "own") {
    const reset = presetReset(a);
    cleared = reset.cleared;
    a = { ...reset.audience, source_mode: "customer", customer_kind: "custom", dataset_id: "", dataset_name: "" };
  }
  return {
    project: { ...withAudience(p, a), ui_state: { ...ui(p), audience_entry: x, analytics_choice: "" } },
    reason: "audience_entry",
    invalidateCheck: cleared,
  };
}

export type Strategy = "population" | "filters" | "discover";

/** chooseAudience: the ČR 18+ branch's three strategies. */
export function chooseAudience(p: ResearchProject, x: Strategy): Change {
  const a: Audience = { ...aud(p), source_mode: "population", dataset_id: "", dataset_name: "ČR 18+", builtin_subpanel: "", strategy: x };
  if (x === "population") Object.assign(a, { filters: {}, segment: { mode: "none" }, description: "ČR 18+" });
  if (x === "filters") {
    a.filters = a.filters || {};
    a.segment = { mode: "none" };
    if (!a.description || a.description === "ČR 18+") a.description = "Zúžená cílová populace";
  }
  if (x === "discover") {
    a.filters = {};
    a.segment = { mode: "none" };
    if (!a.product_description) a.product_description = p.briefing.product_description as Json;
  }
  return { project: withAudience(p, a), reason: "audience_strategy", invalidateCheck: false };
}

/** setAnalyticsChoice: ČR 18+ starts on the whole population; every choice starts afresh (OI-51). */
export function setAnalyticsChoice(p: ResearchProject, x: "cz18" | "cz_coming" | "special"): Change {
  const next: ResearchProject = { ...p, ui_state: { ...ui(p), analytics_choice: x } };
  const { audience, cleared } = presetReset(aud(next));
  if (x === "cz18") {
    // The classic's chooseAudience('population'), on the audience the reset leaves; it writes
    // "ČR 18+" as the description, which a preset change does not (the product owner, 2026-10-25).
    const c = chooseAudience(withAudience(next, audience), "population");
    return { ...c, project: withAudience(c.project, { ...aud(c.project), description: aud(next).description }), invalidateCheck: c.invalidateCheck || cleared };
  }
  if (x === "special") {
    return {
      project: withAudience(next, { ...audience, dataset_id: "", dataset_name: "", special_catalog_key: "" }),
      reason: "analytics_choice",
      invalidateCheck: cleared,
    };
  }
  return { project: withAudience(next, audience), reason: "analytics_choice", invalidateCheck: cleared };
}

/** The back button of the three analytics branches. */
export function analyticsBack(p: ResearchProject): Change {
  return { project: { ...p, ui_state: { ...ui(p), analytics_choice: "" } }, reason: "analytics_back", invalidateCheck: false };
}

export type Preset = { key: string; name: string; kind: "population" | "special" | "coming_soon"; source: string; note: string };

/** SPECIAL_AUDIENCE_PRESETS (:362). */
export const SPECIAL_AUDIENCE_PRESETS: readonly Preset[] = [
  { key: "doctors", name: "Lékaři", kind: "population", source: "medical_doctors", note: "Vestavěný profesní subpanel; nízká core podpora se zobrazí v preflightu." },
  { key: "health", name: "Zdravotníci", kind: "special", source: "healthcare_clinical_professionals", note: "Klinické profese · strukturální/profesní view." },
  { key: "young", name: "Mladí 18–29", kind: "population", source: "young_18_29", note: "Robustní vestavěný populační subpanel." },
  { key: "foreign_prague", name: "Cizinci žijící v Praze", kind: "coming_soon", source: "", note: "Pro tuto přesnou kombinaci zatím není podporovaný built-in panel; nahrajte vlastní audience." },
  { key: "seniors", name: "Senioři 66–79", kind: "population", source: "seniors_66_79", note: "Vestavěný populační subpanel." },
  { key: "health_buyers", name: "Zdravotnický materiál · ekosystém", kind: "special", source: "healthcare_material_ecosystem", note: "Strukturální ekosystém; pro ostré buyer claimy doporučena klientská measured audience." },
];

export type Subpanel = { key: string; name?: string; description?: string; filter?: Obj; status?: string; support_tier?: string; rows?: Json; weighted_population?: Json; unique_core_donors?: Json; effective_core_donors?: Json; max_core_reuse?: Json };
type SpecialPanel = { key: string; name?: string; support?: string };
export type Catalogues = { population_subpanels?: Subpanel[]; special_panels?: SpecialPanel[] };

/** usePopulationSubpanel (the classic name): the subpanel's own filters and support; unchanged if it is unknown. */
export function applyPopulationSubpanel(p: ResearchProject, key: string, c: Catalogues): ResearchProject {
  const sp = (c.population_subpanels || []).find((x) => x.key === key);
  if (!sp) return p;
  const filters: Obj = {};
  for (const [k, v] of Object.entries(sp.filter || {})) filters[k] = Array.isArray(v) ? [...v] : v;
  return withAudience(p, {
    ...aud(p),
    source_mode: "population",
    dataset_id: "",
    dataset_name: sp.name as Json,
    strategy: "filters",
    builtin_subpanel: key,
    description: (sp.description || sp.name) as Json,
    filters,
    segment: { mode: "none" },
    support_tier: sp.support_tier || "",
    subpanel_status: sp.status || "",
    // As the classic copies them: a missing count stays missing, never 0.
    support_summary: {
      rows: sp.rows as Json,
      weighted_population: sp.weighted_population as Json,
      unique_core_donors: sp.unique_core_donors as Json,
      effective_core_donors: sp.effective_core_donors as Json,
      max_core_reuse: sp.max_core_reuse as Json,
    },
  });
}

/**
 * chooseSpecialPreset. Every preset starts afresh: the subpanel and filters a preset set before it are
 * cleared (OI-51 (a)), where the classic kept them.
 */
export function chooseSpecialPreset(p: ResearchProject, key: string, c: Catalogues): Change | null {
  const x = SPECIAL_AUDIENCE_PRESETS.find((z) => z.key === key);
  if (!x) return null;
  const marked = withAudience(p, { ...presetReset(aud(p)).audience, special_catalog_key: key });
  if (x.kind === "population") {
    const next = applyPopulationSubpanel(marked, x.source, c);
    return { project: withAudience(next, { ...aud(next), description: x.name }), reason: "special_preset_population", invalidateCheck: true };
  }
  if (x.kind === "special") {
    const spec = (c.special_panels || []).find((z) => z.key === x.source);
    return {
      project: withAudience(marked, {
        ...aud(marked),
        source_mode: "special_audience",
        dataset_id: `builtin_special:${x.source}`,
        dataset_name: spec?.name || x.name,
        strategy: "special_panel",
        description: x.note,
        special_panel_key: x.source,
        support_tier: spec?.support || "",
      }),
      reason: "special_preset",
      invalidateCheck: true,
    };
  }
  return {
    project: withAudience(marked, { ...aud(marked), source_mode: "special_audience", dataset_id: "", dataset_name: x.name, description: x.note }),
    reason: "special_preset_upload",
    invalidateCheck: true,
  };
}

// ---- own audiences ----------------------------------------------------------

export type SavedAudience = { audience_id: string; name?: string; rows?: Json; type?: string; population_definition?: string; description?: string };

/** audienceDatasetEditor's list: the saved customer audiences. */
export function customerAudiences(list: unknown): SavedAudience[] {
  return (Array.isArray(list) ? (list as SavedAudience[]) : []).filter((x) => x.type === "customer");
}

/** selectAudienceDataset (save(), the run check cleared). */
export function selectAudienceDataset(p: ResearchProject, id: string, list: SavedAudience[]): ResearchProject {
  const m = list.find((x) => x.audience_id === id);
  return withAudience(p, { ...aud(p), dataset_id: id || "", dataset_name: m?.name || "", description: m?.population_definition || m?.description || m?.name || "" });
}

export const UPLOAD_NO_FILE = "Vyberte .xlsx nebo .csv soubor.";
export const UPLOAD_DONE = "Audience je uložená a vybraná";

/** uploadAudience's body: the name defaults to the file's, the type to the project's source. */
export function uploadBody(p: ResearchProject, file: { name: string; b64: string }, name: string, description: string): Record<string, unknown> {
  return {
    filename: file.name,
    data_b64: file.b64,
    audience_name: name.trim() || file.name.replace(/\.[^.]+$/, ""),
    audience_type: aud(p).source_mode || "special_audience",
    description: description.trim(),
    n: p.n,
  };
}

/** What uploadAudience keeps from the unit's answer. */
export function applyUpload(p: ResearchProject, r: { audience?: { audience_id?: string; name?: string; population_definition?: string; description?: string } }): ResearchProject {
  const x = r.audience || {};
  return withAudience(p, { ...aud(p), dataset_id: x.audience_id as Json, dataset_name: x.name as Json, description: (x.population_definition || x.description || x.name) as Json });
}

// ---- the factor editor -------------------------------------------------------

export type Factor = {
  id: string;
  label?: string;
  category?: string;
  category_label?: string;
  kind?: string;
  status?: string;
  source?: string;
  filterable?: boolean;
  min?: number;
  max?: number;
  /** Set when the catalogue states a scale's ends (`*_1_10`) instead of reading them from the data. */
  scale_hint?: string | null;
  values?: { value: string; count?: number }[];
  /** AIA's catalogue only: the version's field policy for audience filtering. */
  policy_allowed?: boolean;
  policy_reason?: string;
};
export type Catalog = {
  categories?: { id: string; label?: string; filterable_count?: number; count?: number }[];
  factors?: Factor[];
  filterable_count?: number;
};

/** The default category the classic factor editor opens on. */
export const DEFAULT_CATEGORY = "demography";

/** setAudienceDimensionSearch1793: a search is compared in Czech lower case. */
export const searchKey = (v: string) => String(v || "").toLocaleLowerCase("cs");

/** filterEditor: the filterable factors of the category that match the search; 80 are drawn. */
export function filterableFactors(cat: Catalog, category: string, query: string): { shown: Factor[]; total: number } {
  const fac = (cat.factors || []).filter(
    (x) =>
      x.filterable &&
      (category === "all" || x.category === category) &&
      (!query || `${x.id} ${x.label} ${x.category_label}`.toLocaleLowerCase("cs").includes(query)),
  );
  return { shown: fac.slice(0, 80), total: fac.length };
}

/** The categories offered as filters, and the count of research-only signals kept apart. */
export function filterCategories(cat: Catalog) {
  return {
    categories: (cat.categories || []).filter((x) => x.id !== "research_only"),
    sensitive: (cat.categories || []).find((x) => x.id === "research_only")?.count || 0,
  };
}

/** factorStatus1793 */
export function factorStatus(x: string | undefined): string {
  return ({ PANEL_EXISTING: "Panel data", DERIVED_EXISTING_SIGNALS: "Odvozeno z panelu", SIMULATED_FROM_EVIDENCE: "Evidence simulace", PANEL_EXISTING_RESEARCH_ONLY: "Research-only" } as Record<string, string>)[x || ""] || x || "";
}

const filters = (p: ResearchProject): Obj => ({ ...((aud(p).filters as Obj | undefined) || {}) });

/** factorEditor1793's current value of a numeric factor: from a {min,max} range or a [lo, hi] pair. */
export function rangeOf(p: ResearchProject, id: string): { lo: Json; hi: Json } {
  const cur = filters(p)[id] as Json | undefined;
  const isRange = !!cur && typeof cur === "object" && !Array.isArray(cur);
  return {
    lo: isRange ? ((cur as Obj).min ?? null) : Array.isArray(cur) ? (cur[0] ?? null) : null,
    hi: isRange ? ((cur as Obj).max ?? null) : Array.isArray(cur) ? (cur[1] ?? null) : null,
  };
}

/**
 * A numeric factor's stored ends as the population reads them (_interval): rangeOf's, and a bare
 * number as both ends, an exact value (`vek: 40` is age 40 alone). rangeOf stays the classic's
 * reading, which shows a bare number as no range.
 */
export function storedRange(p: ResearchProject, id: string): { lo: Json; hi: Json } {
  const cur = filters(p)[id] as Json | undefined;
  return typeof cur === "number" && Number.isFinite(cur) ? { lo: cur, hi: cur } : rangeOf(p, id);
}

/**
 * What a numeric factor's two steppers may hold (input-interactions I2, audit B6): the population's
 * own range from the catalogue, null when it states none (nothing to bound by, nothing guessed).
 * Whole numbers only when both ends are whole numbers read from the data; a scale whose ends the
 * catalogue states (`scale_hint`) says nothing of its values, and takes two decimals like any other.
 * The ends are rounded outward to those decimals, so the population's own ends can be typed.
 */
export function rangeBounds(f: Factor): { min: number; max: number; decimals: number } | null {
  const { min, max } = f;
  if (typeof min !== "number" || typeof max !== "number" || !Number.isFinite(min) || !Number.isFinite(max) || min > max) return null;
  const decimals = !f.scale_hint && Number.isInteger(min) && Number.isInteger(max) ? 0 : 2;
  const scale = 10 ** decimals;
  return { min: Math.floor(min * scale) / scale, max: Math.ceil(max * scale) / scale, decimals };
}

/**
 * A stored end as a number, the way the population reads it (float(), rangeHolds), or null: no end,
 * and an end the population cannot read (filterProblems names it, endUnreadable says so at the field).
 */
export function boundOf(v: Json): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v !== "string" || !takesFloat(v)) return null;
  const n = Number(v.trim().replace(/(\d)_(?=\d)/g, "$1"));
  return Number.isFinite(n) ? n : null;
}

/** A stored end that is there but is no number the stepper can show. */
export const endUnreadable = (v: Json): boolean => v !== null && v !== undefined && boundOf(v) === null;

/** Up to this many values, a factor's values are toggle chips alone (input-interactions I3: 6–15);
 * more, the same chips under a filter field (audit B7). */
export const VALUE_CHIPS_MAX = 15;

/** A factor's listed values matching a search, compared as the factor search compares (searchKey). */
export function matchingValues<V extends { value: string }>(values: readonly V[], query: string): V[] {
  const key = searchKey(query);
  return key ? values.filter((v) => searchKey(v.value).includes(key)) : [...values];
}

/**
 * A factor's values after a person picked among the `listed` ones (the chips on screen): the stored
 * values in their stored order and as stored, less the listed ones not picked, then the newly picked.
 * A stored value not on screen (filtered out, or one the population lacks, F3) is kept as it was,
 * never dropped, moved or turned into text by a toggle of another: the population keys a stored
 * `true` as "1" or "True", never "true" (audience.py _values).
 */
export function pickValues(stored: readonly Json[], listed: readonly string[], picked: readonly string[]): Json[] {
  const text = stored.map(String);
  const kept = stored.filter((_, i) => !listed.includes(text[i]) || picked.includes(text[i]));
  return [...kept, ...picked.filter((v) => !text.includes(v))];
}

/** A categorical factor's stored values, as stored: a list, or one value as a list of one. */
export function storedValues(p: ResearchProject, id: string): Json[] {
  const cur = filters(p)[id] as Json | undefined;
  return Array.isArray(cur) ? cur : cur != null ? [cur] : [];
}

/**
 * The built-in subpanels a search matches (input-interactions I3, audit B9: 18 is past a plain
 * list): by name or description, compared as the factor search compares (searchKey), the query
 * trimmed. The screen shows the chosen one beside them whatever they are.
 */
export function matchingSubpanels(list: readonly AudienceCatalogueSubpanel[], query: string): AudienceCatalogueSubpanel[] {
  const key = searchKey(query.trim());
  return key ? list.filter((sp) => searchKey(`${sp.name} ${sp.description}`).includes(key)) : [...list];
}

/** factorEditor1793's selected values of a categorical factor. */
export function selectedValues(p: ResearchProject, id: string): Set<string> {
  const cur = filters(p)[id] as Json | undefined;
  return new Set(Array.isArray(cur) ? cur.map(String) : cur != null ? [String(cur)] : []);
}

/** setAudienceCategory1793 (then an automatic preview). */
export function setAudienceCategory(p: ResearchProject, id: string, values: Json[]): Change {
  const f = filters(p);
  if (values.length) f[id] = values;
  else delete f[id];
  return { project: withAudience(p, { ...aud(p), filters: f }), reason: "aud_category_1793", invalidateCheck: true };
}

/**
 * setAudienceRange1793, as the classic reads its two inputs: `Number('')` is 0,
 * so an empty bound is stored as 0, not as "no bound" (OI-50). The unit then
 * orders the pair, so an empty upper bound selects from 0 to the lower one.
 */
export function setAudienceRange(p: ResearchProject, id: string, rawMin: string | undefined, rawMax: string | undefined): Change {
  const a = Number(rawMin);
  const b = Number(rawMax);
  const f = filters(p);
  if (!Number.isFinite(a) && !Number.isFinite(b)) delete f[id];
  else f[id] = { min: Number.isFinite(a) ? a : null, max: Number.isFinite(b) ? b : null };
  return { project: withAudience(p, { ...aud(p), filters: f }), reason: "aud_range_1793", invalidateCheck: true };
}

/** removeAudienceFactor1793 (no preview). */
export function removeAudienceFactor(p: ResearchProject, id: string): Change {
  const f = filters(p);
  delete f[id];
  return { project: withAudience(p, { ...aud(p), filters: f }), reason: "aud_factor_removed_1793", invalidateCheck: true };
}

/** selectedAudienceFilters1793: each filter as its factor's label and a readable value. */
export function filterChips(p: ResearchProject, cat: Catalog | null): { id: string; label: string; text: string }[] {
  const map = new Map((cat?.factors || []).map((x) => [x.id, x]));
  return Object.entries(filters(p)).map(([id, val]) => {
    const f = map.get(id);
    const text = Array.isArray(val)
      ? val.join(" OR ")
      : val && typeof val === "object"
        ? `${(val as Obj).min ?? "−∞"}–${(val as Obj).max ?? "∞"}`
        : String(val);
    return { id, label: String(f?.label || id), text };
  });
}

/**
 * How many of a factor's values the catalogue lists: its 60 most frequent
 * (domain/population/audience_catalogue.py _TOP_VALUES). A list this long may be cut, so a value
 * missing from it is unknown, never "not in the population".
 */
export const CATALOGUE_TOP_VALUES = 60;

/**
 * A stored filter the population cannot honour as stored, said before a preview or a run. `factor`,
 * `policy` and `empty` refuse the whole audience (select_audience); `values` drops the values the
 * population lacks, or refuses the audience when none is left (`noneKnown`).
 */
export type FilterProblem = { id: string; label: string; reason: "factor" | "policy" | "empty" | "range" | "values"; unknownValues: string[]; noneKnown: boolean };

/** Whether Python's float() takes `x` (a bound _interval reads): a number, a boolean, numeric text. */
const takesFloat = (x: unknown): boolean => {
  if (typeof x === "number" || typeof x === "boolean") return true;
  if (typeof x !== "string") return false;
  const s = x.trim().replace(/(\d)_(?=\d)/g, "$1");
  return s !== "" && (!Number.isNaN(Number(s)) || /^[+-]?(inf|infinity|nan)$/i.test(s));
};

/** domain/population/audience.py _interval's verdict on a numeric filter's stored value: a {min, max}
 * whose present bounds are numbers, a pair of numbers, or one number. A bound left out takes the
 * catalogue's, so it is never the problem. */
function rangeHolds(v: unknown): boolean {
  if (v && typeof v === "object" && !Array.isArray(v) && ("min" in v || "max" in v)) {
    const r = v as Record<string, unknown>;
    return (!("min" in r) || takesFloat(r.min)) && (!("max" in r) || takesFloat(r.max));
  }
  if (Array.isArray(v)) return v.length === 2 && v.every(takesFloat);
  return typeof v === "number" || typeof v === "boolean";
}

/**
 * The stored filters the catalogue shows cannot apply as stored (artifact-audience, Findings F3).
 * A numeric filter is held to _interval's rule (`range`). Only what the catalogue proves is named
 * otherwise: a value is compared as text, the way the population keys it, only when the factor's
 * value list is complete (shorter than CATALOGUE_TOP_VALUES); a number, a boolean and a cut list
 * say nothing.
 */
export function filterProblems(p: ResearchProject, cat: Catalog | null): FilterProblem[] {
  if (!cat) return [];
  const map = new Map((cat.factors || []).map((x) => [x.id, x]));
  const out: FilterProblem[] = [];
  const problem = (id: string, label: string, reason: FilterProblem["reason"], unknownValues: string[] = [], noneKnown = false) =>
    out.push({ id, label, reason, unknownValues, noneKnown });
  for (const [id, val] of Object.entries(filters(p))) {
    const f = map.get(id);
    const label = String(f?.label || id);
    if (!f) { problem(id, label, "factor"); continue; }
    if (f.policy_allowed === false) { problem(id, label, "policy"); continue; }
    if (f.kind === "numeric") { if (!rangeHolds(val)) problem(id, label, "range"); continue; }
    const asked = (Array.isArray(val) ? val : [val]).filter((v) => v != null);
    if (!asked.length) { problem(id, label, "empty"); continue; }
    if (!Array.isArray(f.values) || f.values.length >= CATALOGUE_TOP_VALUES || !asked.every((v) => typeof v === "string")) continue;
    const known = new Set(f.values.map((v) => String(v.value)));
    const unknownValues = (asked as string[]).filter((v) => !known.has(v));
    if (unknownValues.length) problem(id, label, "values", unknownValues, unknownValues.length === asked.length);
  }
  return out;
}

// ---- the readable summary (1795) --------------------------------------------

/** audienceHumanSummary1795: population, planned N (the audience's own `n`), source. */
export function humanSummary(a: Audience | undefined): [string, string][] {
  if (!a) return [];
  const out: [string, string][] = [];
  if (a.population || a.description) out.push(["Populace", String(a.population || a.description)]);
  if (a.n) out.push(["Plánované N", String(a.n)]);
  if (a.dataset_name) out.push(["Zdroj audience", String(a.dataset_name)]);
  return out;
}

/**
 * humanizeAudienceFilters1795: each filter with underscores as spaces. The
 * classic prints a range object as "[object Object]"; the rebuilt one prints
 * it the way the filter chips do, "od–do" (a listed display difference).
 */
export function humanFilters(p: ResearchProject): [string, string][] {
  const pairs: [string, string][] = [];
  for (const [k, v] of Object.entries(filters(p))) {
    if (v == null || v === "" || (Array.isArray(v) && !v.length)) continue;
    const label = String(k).replace(/_/g, " ");
    const val = Array.isArray(v)
      ? v.join(", ")
      : typeof v === "object"
        ? `${(v as Obj).min ?? "−∞"}–${(v as Obj).max ?? "∞"}`
        : String(v);
    pairs.push([label, val]);
  }
  return pairs;
}

// ---- preview, preflight and the ideal group -------------------------------------

export const PREVIEW_NO_DATASET = "Nejdřív vyberte nebo nahrajte audience.";

/** previewAudience's request: the population preview, or the dataset's preflight. */
export function previewRequest(p: ResearchProject):
  | { route: "audiencePreview"; body: Record<string, unknown> }
  | { route: "audiencesPreflight"; body: Record<string, unknown> }
  | { error: string } {
  const a = aud(p);
  const src = a.source_mode || "population";
  if (src === "population") return { route: "audiencePreview", body: { filtry: a.filters || {}, n: p.n } };
  if (!a.dataset_id) return { error: PREVIEW_NO_DATASET };
  return { route: "audiencesPreflight", body: { dataset_id: a.dataset_id, n: p.n } };
}

/** audPreviewHtml's effective binding: ready, or the first blocking problem. */
export function previewVerdict(r: Record<string, unknown>, n: Json | undefined): { ok: true; text: string } | { ok: false; text: string } {
  const problems = (r.problems || r.problemy || []) as (string | { uroven?: string; text?: string })[];
  const bad = problems.filter((x) => (typeof x === "object" && String(x?.uroven || "").toUpperCase() === "ERROR") || typeof x === "string");
  if (r.ok !== false && !bad.length) {
    return { ok: true, text: `Požadované N=${n ?? ""} bude při spuštění automaticky vybráno reprezentativně v rámci této populace.` };
  }
  const first = bad[0];
  return { ok: false, text: String((typeof first === "object" ? first?.text : first) || first || "Změňte populaci nebo velikost vzorku.") };
}

/** "Popis vlastními slovy": the audience's description as the person writes it (spec vzorek/A1). */
export function setAudienceDescription(p: ResearchProject, v: string): ResearchProject {
  return withAudience(p, { ...aud(p), description: v });
}

// ---- the AI proposal ---------------------------------------------------------

export const PROPOSE_EMPTY = "Popište cílovou populaci vlastními slovy.";
export const PROPOSE_TITLE = "AI převádí cílovku na dostupné filtry";
export const PROPOSE_WARN_MS = 40_000;
export const PROPOSE_UNCOVERED = "Část popisu nelze vyjádřit dostupnými filtry — podrobnost je v návrhu AI.";
export const PROPOSE_FAILED_SUFFIX = "\n\nPoužijte Diagnostiku, pokud se chyba opakuje.";

/** proposeAudience's text: what the person typed, else the stored description. */
export function proposeText(typed: string, p: ResearchProject): string {
  return typed.trim() || String(aud(p).description || "");
}

/** proposeAudience's body for /api/audience/propose. */
export function proposePayload(p: ResearchProject, text: string): Record<string, unknown> {
  return { popis: text, n: p.n, model: "sonnet", provider: PROVIDER_FORCED, project: p };
}

/** What proposeAudience keeps: the model's filters replace the project's. */
export function applyProposal(p: ResearchProject, text: string, r: { filtry?: Obj; feasibility?: unknown; nepokryto?: unknown }): { change: Change; preview: unknown; uncovered: boolean } {
  return {
    change: {
      project: withAudience(p, { ...aud(p), source_mode: "population", strategy: "filters", description: text, filters: r.filtry || {} }),
      reason: "audience_ai_1776",
      invalidateCheck: false,
    },
    preview: r.feasibility || null,
    uncovered: !!r.nepokryto,
  };
}

// ---- live: AIA's own catalogue, subpanels and preview (panel-grounded-respondents 6e) ----

/** Why a factor is not offered as a filter, in words; null when it is. */
export function factorRefusal(f: Factor): string | null {
  if (!f.filterable) return "Research-only signál, ne filtr cílové skupiny.";
  if (f.policy_allowed === false) return `Politika pole tento faktor k filtrování nepovoluje (${f.policy_reason || "neznámý důvod"}).`;
  return null;
}

/** The API's catalogue as the factor editor reads it; a factor keeps its policy answer. */
export function liveCatalog(api: AudienceCatalogue): Catalog {
  return {
    categories: api.categories.map((c) => ({ id: c.id, label: c.label, count: c.count, filterable_count: c.filterable_count })),
    factors: api.factors.map((f) => ({
      id: f.id,
      label: f.label,
      category: f.category,
      category_label: f.category_label,
      kind: f.kind,
      status: f.status,
      source: f.source,
      filterable: f.filterable,
      min: f.min ?? undefined,
      max: f.max ?? undefined,
      scale_hint: f.scale_hint ?? null,
      values: f.values ?? undefined,
      policy_allowed: f.policy_allowed,
      policy_reason: f.policy_reason,
    })),
    filterable_count: api.filterable_count,
  };
}

/** The API's subpanels as applyPopulationSubpanel reads them: 18.6.6's counts, as 18.6.6's. */
export function liveSubpanels(api: AudienceCatalogue): Catalogues {
  return {
    population_subpanels: api.subpanels.map((s) => ({
      key: s.key,
      name: s.name,
      description: s.description,
      filter: s.filters as Obj,
      status: s.status,
      support_tier: s.support_tier,
      rows: s.measured_by_18_6_6.rows,
      weighted_population: s.measured_by_18_6_6.weighted_population,
      unique_core_donors: s.measured_by_18_6_6.unique_core_donors,
      effective_core_donors: s.measured_by_18_6_6.effective_core_donors,
      max_core_reuse: s.measured_by_18_6_6.max_core_reuse,
    })),
    special_panels: [],
  };
}

/**
 * AIA's range filter (OI-50 does not carry over). The classic stored an empty bound as 0
 * (setAudienceRange, kept above as the classic's); a filter that now decides who is sampled
 * leaves an empty bound out, and the population's own minimum or maximum stands for it.
 */
export function setRange(p: ResearchProject, id: string, min: number | null, max: number | null): Change {
  const f = filters(p);
  const range: Obj = {};
  if (min !== null && Number.isFinite(min)) range.min = min;
  if (max !== null && Number.isFinite(max)) range.max = max;
  if (Object.keys(range).length) f[id] = range;
  else delete f[id];
  return { project: withAudience(p, { ...aud(p), filters: f }), reason: "aud_range", invalidateCheck: true };
}

/** The sampler's refusals in words, by reason code. */
const PREVIEW_REASONS: Record<string, string> = {
  sampling_filter_invalid: "Některý filtr nelze použít",
  sampling_field_refused: "Politika pole nepovoluje filtrovat podle",
  sampling_empty: "Filtry nevyberou žádného člověka z populace.",
  sampling_n_exceeds_support: "Publikum má méně různých lidí, než kolik respondentů studie chce; vzorek se vybírá bez opakování.",
  sampling_unrepresentative: "Vzorek této velikosti by z tohoto publika nebyl reprezentativní ani po kalibraci; zvětšete N nebo rozšiřte publikum.",
  sampling_n_invalid: "Studie nemá platné N.",
};

/** The two fragments above, finished when the refusal names nothing to finish them with. */
const UNNAMED_REASONS: Record<string, string> = {
  sampling_filter_invalid: "Některý filtr cílové skupiny nelze použít.",
  sampling_field_refused: "Politika pole nepovoluje filtrovat podle některého z polí výběru.",
};

/** A refusal in words: its code's sentence, completed by what it names; never a fragment. */
export function verdictWords(v: { reason?: string | null; reasons?: string[] | null }): string {
  const code = v.reason || "";
  if (!v.reasons?.length && UNNAMED_REASONS[code]) return UNNAMED_REASONS[code];
  const base = PREVIEW_REASONS[code] || `Výběr odmítnut (${v.reason || "neznámý důvod"}).`;
  return v.reasons?.length ? `${base}: ${v.reasons.join("; ")}.` : base;
}

const cs = (n: number) => n.toLocaleString("cs-CZ");

/** The preview's answer in words: what the filters select, and whether a run could draw n. */
/**
 * Each filter alone (AUD3, the API's `per_filter`), in the order the filters were applied, named
 * by the catalogue's label: which filter narrows the audience. Said only for two filters or more;
 * one filter alone selects what all of them select.
 */
export function filterCountLines(r: AudiencePreview, cat: Catalog | null): string[] {
  const counts = r.per_filter ?? {};
  const ids = Object.keys(r.filters_applied ?? {}).filter((id) => counts[id] != null);
  if (ids.length < 2) return [];
  const label = new Map((cat?.factors || []).map((f) => [f.id, String(f.label || f.id)]));
  return ids.map((id) => `Samotný filtr ${label.get(id) ?? id}: ${cs(counts[id]!)} lidí.`);
}

export function liveVerdict(r: AudiencePreview, cat: Catalog | null = null): { ok: boolean; lines: string[] } {
  if (!r.audience.ok) return { ok: false, lines: [verdictWords(r.audience)] };
  const lines = [
    `Filtry vyberou ${cs(r.selected_rows ?? 0)} z ${cs(r.population_rows)} lidí populace ${r.version_label}` +
      (r.selected_donors != null ? ` (${cs(r.selected_donors)} různých dárců).` : "."),
    ...filterCountLines(r, cat),
  ];
  if (!r.sample) return { ok: true, lines };
  if (!r.sample.ok) return { ok: false, lines: [...lines, verdictWords(r.sample)] };
  const weighted = r.sample.status === "PASS_WEIGHTED" ? " Reprezentativní až po kalibraci vah." : "";
  return { ok: true, lines: [...lines, `Vzorek N=${r.n} z tohoto publika lze vybrat.${weighted}`] };
}
