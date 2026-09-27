// Audience, the research flow's fourth step (ADR 0014, area A4): what the
// classic step does to the project, ported from the bindings that run --
// renderAudience (:374) under its three wrappers (1785 :899, 1789 :961,
// 1795 :1173), the branch and preset choosers, the factor editor, the
// readiness rule, the preview and preflight requests, the upload, and the AI
// proposal. Every function is pure and returns the next project with the
// classic save reason. audience.parity.test.ts compares each with the original
// under Node. Two classic behaviours that change who is sampled are kept and
// characterised, not fixed: OI-50 (an empty range bound is 0) and OI-51 (a
// special preset keeps the previous subpanel and filters).

import { unit } from "@/unit/client";
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

/** The special screen's "Vybráno" card. */
export function specialSelected(p: ResearchProject): boolean {
  const a = aud(p);
  return !!(a.dataset_id || a.builtin_subpanel || a.special_panel_key || a.builtin_special_key);
}

/** setAudienceEntry (the preview is cleared by the screen). */
export function setAudienceEntry(p: ResearchProject, x: "choose" | "own" | "analytics"): Change {
  let a = { ...aud(p) };
  if (x === "own") a = { ...a, source_mode: "customer", customer_kind: "custom", dataset_id: "", dataset_name: "" };
  return {
    project: { ...withAudience(p, a), ui_state: { ...ui(p), audience_entry: x, analytics_choice: "" } },
    reason: "audience_entry",
    invalidateCheck: false,
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

/** setAnalyticsChoice: ČR 18+ starts on the whole population; special clears the source, not the filters (OI-51). */
export function setAnalyticsChoice(p: ResearchProject, x: "cz18" | "cz_coming" | "special"): Change {
  const next: ResearchProject = { ...p, ui_state: { ...ui(p), analytics_choice: x } };
  if (x === "cz18") return chooseAudience(next, "population");
  if (x === "special") {
    return {
      project: withAudience(next, { ...aud(next), dataset_id: "", dataset_name: "", builtin_subpanel: "", special_panel_key: "", special_catalog_key: "" }),
      reason: "analytics_choice",
      invalidateCheck: false,
    };
  }
  return { project: next, reason: "analytics_choice", invalidateCheck: false };
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

type Subpanel = { key: string; name?: string; description?: string; filter?: Obj; status?: string; support_tier?: string; rows?: Json; weighted_population?: Json; unique_core_donors?: Json; effective_core_donors?: Json; max_core_reuse?: Json };
type SpecialPanel = { key: string; name?: string; support?: string };
export type Catalogues = { population_subpanels?: Subpanel[]; special_panels?: SpecialPanel[] };

/** The bootstrap's subpanels and special panels, as the presets read them. */
export function catalogues(raw: Record<string, unknown>): Catalogues {
  return {
    population_subpanels: Array.isArray(raw.population_subpanels) ? (raw.population_subpanels as Subpanel[]) : [],
    special_panels: Array.isArray(raw.special_panels) ? (raw.special_panels as SpecialPanel[]) : [],
  };
}

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
 * chooseSpecialPreset. A special or coming-soon preset does not clear the
 * subpanel or the filters a population preset set before it (OI-51).
 */
export function chooseSpecialPreset(p: ResearchProject, key: string, c: Catalogues): Change | null {
  const x = SPECIAL_AUDIENCE_PRESETS.find((z) => z.key === key);
  if (!x) return null;
  const marked = withAudience(p, { ...aud(p), special_catalog_key: key });
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
export const UPLOAD_TIMEOUT_MS = 180_000;

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
  values?: { value: string; count?: number }[];
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

/** factorEditor1793's selected values of a categorical factor. */
export function selectedValues(p: ResearchProject, id: string): Set<string> {
  const cur = filters(p)[id] as Json | undefined;
  return new Set(Array.isArray(cur) ? cur.map(String) : cur != null ? [String(cur)] : []);
}

/** setAudienceCategory1793 (then an automatic preview). */
export function setAudienceCategory(p: ResearchProject, id: string, values: string[]): Change {
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

/** discoverEditor: the product description shown falls back to the brief's. */
export function discoverText(p: ResearchProject): { product: string; success: string } {
  const a = aud(p);
  return { product: String(a.product_description || p.briefing.product_description || ""), success: String(a.success_definition || "") };
}

export function setDiscoverField(p: ResearchProject, field: "product_description" | "success_definition", v: string): ResearchProject {
  return withAudience(p, { ...aud(p), [field]: v });
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

// ---- the factor catalogue, once per page -------------------------------------------

let catalog: Promise<Catalog> | null = null;

/** ensureAudienceDimensionCatalog1793: GET /api/audience/dimensions, cached per page; a failure is not. */
export function loadAudienceCatalog(fetchImpl?: typeof fetch): Promise<Catalog> {
  catalog ??= unit("audienceDimensions", { fetchImpl }).then(
    (r) => r as Catalog,
    (e: unknown) => {
      catalog = null;
      throw e;
    },
  );
  return catalog;
}

/** Tests only. */
export function resetAudienceCatalog(): void {
  catalog = null;
}
