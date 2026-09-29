// Dimenze, the research flow's fifth step (ADR 0014, area A4): what the
// classic persona step does to the project, ported from the bindings that run
// -- the full reassignment of renderPersona (:979) under its 1793 wrapper
// (:1071), the catalogue, the approved dimensions, the sample size, the AI
// suggestion and the dimension requests. Every function is pure and returns the
// next project with the classic save reason. persona.parity.test.ts compares
// each with the original under Node. Two classic behaviours are kept and
// characterised, not fixed: the model's dimensions are approved without the
// catalogue check (OI-53), and an empty approval is refilled with the
// recommended set (OI-54).

import { type Json, PROVIDER_FORCED, type ResearchProject } from "./model";

type Obj = { [k: string]: Json };
export type Change = { project: ResearchProject; reason: string };

/** PERSONA_DIM_LABELS (:404): the system's own dimensions. */
export const PERSONA_DIM_LABELS: Readonly<Record<string, string>> = {
  media: "Média a informační chování",
  nakup: "Nákupní chování",
  finance: "Finance a cenová citlivost",
  cena: "Cena / value for money",
  hodnoty: "Hodnoty a postoje",
  prace: "Práce a profesní kontext",
  zdravi: "Zdraví",
  duvera: "Důvěra",
  politika: "Politické postoje",
  ekologie: "Ekologie",
  technologie: "Technologie a digital",
  znacka: "Vztah ke značkám",
  komunikace: "Komunikační styl",
  reklama: "Reakce na reklamu",
  vztahy: "Vztahy / domácnost",
  rodina: "Rodina",
  socialni_site: "Sociální sítě",
  online: "Online chování",
};

export type ActiveDimensions = Record<string, { label?: string } | null | undefined>;

/** The Data Library's active dimensions: the refreshed library's, else the bootstrap's (the classic's sources). */
export function activeDimensions(library: unknown, bootRaw: Record<string, unknown>): ActiveDimensions {
  const fromLibrary = (library as { summary?: { active_dimensions?: ActiveDimensions } } | null)?.summary?.active_dimensions;
  const fromBoot = (bootRaw.data_library as { active_dimensions?: ActiveDimensions } | undefined)?.active_dimensions;
  return fromLibrary || fromBoot || {};
}

/**
 * In AIA the library is the client's own knowledge (ADR 0015, 0018): the study's
 * inherited context, of which the approved DIMENSION items are this catalogue's
 * additions. Another client's dimensions are never in it.
 */
export function clientDimensions(items: readonly { item_id: string; kind: string; title: string }[]): ActiveDimensions {
  const out: ActiveDimensions = {};
  for (const x of items) if (x.kind === "DIMENSION" && x.item_id) out[x.item_id] = { label: x.title };
  return out;
}

/** Where a library dimension comes from, in the catalogue: the client's knowledge in AIA. */
export const CLIENT_LIBRARY_LABEL = "Znalosti klienta";

/** PERSONA_DIM_LABELS with the library's labels added, as dimensionCatalogEntries1789 adds them. */
export function dimensionLabels(active: ActiveDimensions): Record<string, string> {
  const labels: Record<string, string> = { ...PERSONA_DIM_LABELS };
  for (const [id, d] of Object.entries(active)) if (d?.label) labels[id] = d.label;
  return labels;
}

/** dimensionCatalogEntries1789: every dimension, by Czech label, marked by where it comes from. */
export function catalogEntries(active: ActiveDimensions, libraryLabel = "Data Library"): { id: string; label: string; source: string }[] {
  return Object.entries(dimensionLabels(active))
    .map(([id, label]) => ({ id, label, source: active[id] ? libraryLabel : "Systém" }))
    .sort((a, b) => a.label.localeCompare(b.label, "cs"));
}

/** A catalogue row's search text (its data-search) and filterDimPicker1789's match. */
export function dimensionSearchText(d: { id: string; label: string; source: string }): string {
  return `${d.id} ${d.label} ${d.source}`.toLocaleLowerCase("cs");
}
export function matchesDimensionSearch(d: { id: string; label: string; source: string }, q: string): boolean {
  const k = String(q || "").toLocaleLowerCase("cs");
  return !k || dimensionSearchText(d).includes(k);
}

/** canonicalPersonaDim: a topic or a model's word as a dimension id. */
export function canonicalPersonaDim(x: unknown): string {
  const t = String(x || "").trim().toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, "_");
  const rules: [string, string][] = [
    ["zdrav", "zdravi"], ["media", "media"], ["nakup", "nakup"], ["cen", "cena"], ["financ", "finance"], ["hodnot", "hodnoty"],
    ["prac", "prace"], ["duver", "duvera"], ["polit", "politika"], ["ekolog", "ekologie"], ["techn", "technologie"],
    ["digital", "technologie"], ["znack", "znacka"], ["brand", "znacka"], ["komunik", "komunikace"], ["reklam", "reklama"],
    ["kampan", "reklama"], ["vztah", "vztahy"], ["rodin", "rodina"], ["social", "socialni_site"], ["online", "online"],
  ];
  for (const [a, b] of rules) if (t.includes(a)) return b;
  return t.replace(/[^a-z0-9_]/g, "");
}

const strings = (x: unknown): unknown[] => (Array.isArray(x) ? x : []);

/** suggestedPersonaDims: from the plan's topics, the questions' topics and the study type; eight at most. */
export function suggestedPersonaDims(p: ResearchProject): string[] {
  const raw: unknown[] = [...strings((p.research_plan as Obj | undefined)?.recommended_topics)];
  for (const sec of (p.sections || []) as Obj[]) for (const q of strings(sec?.questions) as Obj[]) raw.push(...strings(q?.topics));
  const st = String(p.study_type || "");
  if (st.includes("concept") || st.includes("brand")) raw.push("nakup", "cena", "znacka", "komunikace");
  if (st.includes("employee")) raw.push("prace", "hodnoty");
  if (!raw.length) raw.push("nakup", "hodnoty", "media", "finance");
  return [...new Set(raw.map(canonicalPersonaDim).filter(Boolean))].slice(0, 8);
}

/**
 * personaApproved: the approved dimensions; an empty (or missing) approval is
 * replaced by the recommended set, so the last one can never be removed (OI-54).
 * The classic writes that refill into the project as the screen draws; the
 * port applies it in every change the screen makes, and draws it.
 */
export function withApproval(p: ResearchProject): { project: ResearchProject; approved: string[] } {
  const pd = ((p.persona_dimensions as Obj | undefined) || { approved: [] }) as Obj;
  const approved = Array.isArray(pd.approved) && pd.approved.length ? (pd.approved as string[]) : suggestedPersonaDims(p);
  return { project: { ...p, persona_dimensions: { ...pd, approved } }, approved };
}

/** addCatalogDimension1789 */
export function addDimension(p: ResearchProject, id: string): Change {
  const { project, approved } = withApproval(p);
  const a = new Set(approved);
  a.add(id);
  return { project: { ...project, persona_dimensions: { ...(project.persona_dimensions as Obj), approved: [...a] } }, reason: "dimension_catalog_add" };
}

/** removeCatalogDimension1789 (the last one comes back as the recommended set when drawn, OI-54). */
export function removeDimension(p: ResearchProject, id: string): Change {
  const { project, approved } = withApproval(p);
  const a = new Set(approved);
  a.delete(id);
  return { project: { ...project, persona_dimensions: { ...(project.persona_dimensions as Obj), approved: [...a] } }, reason: "dimension_catalog_remove" };
}

/** autofillPersonaDims */
export function autofill(p: ResearchProject): Change {
  const pd = ((p.persona_dimensions as Obj | undefined) || {}) as Obj;
  return { project: { ...p, persona_dimensions: { ...pd, approved: [...new Set(suggestedPersonaDims(p))] } }, reason: "persona_autofill" };
}

/** recommendedSample1789 */
export function recommendedSample(p: ResearchProject): { n: number; why: string } {
  let base = 300;
  const goal = String(p.goal || "").length;
  const q = ((p.sections || []) as Obj[]).reduce((n, s) => n + strings(s?.questions).length, 0);
  if (q > 30 || goal > 1200) base = 400;
  if (p.audience?.strategy === "discover") base = Math.max(base, 500);
  return {
    n: base,
    why: base >= 500 ? "Širší N pomůže bezpečněji hledat segmenty." : base >= 400 ? "Složitější dotazník / zadání: doporučuji větší standardní vzorek." : "Pro běžný celopopulační výzkum je to rozumný výchozí bod.",
  };
}

/** The sample input's change: 50–5 000, and the recommendation when it is empty or 0. */
export function setSampleSize(p: ResearchProject, raw: string): Change {
  const r = recommendedSample(p);
  return { project: { ...withApproval(p).project, n: Math.max(50, Math.min(5000, +raw || r.n)) }, reason: "sample_n_1789" };
}

/** useRecommendedSample1789 */
export function applyRecommendedSample(p: ResearchProject): Change {
  return { project: { ...withApproval(p).project, n: recommendedSample(p).n }, reason: "sample_recommended_1789" };
}

/** The wizard's way on: the calibrated persona mode, then the run step. */
export function personaDone(p: ResearchProject): Change {
  return { project: { ...withApproval(p).project, persona_mode: "calibrated" }, reason: "persona_done_1789" };
}

// ---- the AI suggestion ------------------------------------------------------

export const SUGGEST_TITLE = "AI doporučuje existující i případné nové dimenze";
export const SUGGEST_WARN_MS = 45_000;
export const SUGGEST_FAILED_SUFFIX = "\n\nPoužijte Diagnostiku, pokud se chyba opakuje.";

export type Suggestion = {
  dimensions?: unknown[];
  new_dimension_suggestions?: { label?: string; why?: string; evidence_needed?: string; suggested_predictors?: string[]; source_strategy?: string }[];
};

/** suggestPersonaAI's body for /api/persona/suggest: the project as the screen drew it. */
export function suggestPayload(p: ResearchProject, active: ActiveDimensions): Record<string, unknown> {
  return {
    project: withApproval(p).project,
    research: p.pre_research || {},
    dimension_labels: dimensionLabels(active),
    library_dimensions: active,
    provider: PROVIDER_FORCED,
    model: "sonnet",
  };
}

/** What suggestPersonaAI keeps: the model's dimensions, canonicalised, approved as they are (OI-53). */
export function applySuggestion(p: ResearchProject, r: Suggestion): Change {
  const pd = ((p.persona_dimensions as Obj | undefined) || {}) as Obj;
  return { project: { ...p, persona_dimensions: { ...pd, approved: (r.dimensions || []).map(canonicalPersonaDim).filter(Boolean) } }, reason: "persona_ai_1793" };
}

// ---- dimension requests ---------------------------------------------------------

export const REQUEST_EMPTY = "Napište název dimenze.";
export const REQUEST_DONE = "Požadavek uložen. Přidejte dokument nebo spusťte Deep Research.";
export const REQUEST_AI_DONE = "AI návrh uložen do Data Library jako evidence-gated dimenze.";
export const REQUEST_TIMEOUT_MS = 30_000;

/** requestDimension1793 trims the label; an empty one is refused with REQUEST_EMPTY. */
export function requestLabel(raw: unknown): string {
  return String(raw || "").trim();
}

export type NewDimension = NonNullable<Suggestion["new_dimension_suggestions"]>[number];

/** requestAISuggestedDimension1793's request: the model's label, its strategy or "either", origin "claude". */
export function suggestedRequest(x: NewDimension): { label: string; sourceStrategy: string; extra: { why?: string; suggested_predictors?: string[]; origin: string } } {
  return { label: requestLabel(x.label), sourceStrategy: x.source_strategy || "either", extra: { ...x, origin: "claude" } };
}

/** requestDimension1793's body for /api/library/dimension/request. */
export function requestBody(label: string, sourceStrategy: string, extra: { why?: string; suggested_predictors?: string[]; origin?: string } = {}): Record<string, unknown> {
  return {
    label,
    source_strategy: sourceStrategy,
    rationale: extra.why || `Požadavek projektu: ${label}`,
    spec: { predictors: (extra.suggested_predictors || []).map((x) => ({ column: x, direction: "positive", strength: 1 })) },
    origin: extra.origin || "user",
  };
}

/**
 * The request as the project records it, waiting for evidence. The classic
 * screen has already written the approval's refill into the project when it
 * drew, so the save carries it too.
 */
export function recordRequest(p: ResearchProject, label: string, sourceStrategy: string, r: { dimension_id?: string; proposal_id?: string }, now: Date = new Date()): Change {
  const drawn = withApproval(p).project;
  const list = strings(drawn.requested_dimensions) as Json[];
  return {
    project: {
      ...drawn,
      requested_dimensions: [
        ...list,
        { label, dimension_id: r.dimension_id as Json, proposal_id: r.proposal_id as Json, status: "needs_evidence", source_strategy: sourceStrategy, created_at: now.toISOString() },
      ],
    },
    reason: "requested_dimension_1793",
  };
}

/** The labels of the requests the project records (shown "čeká na evidenci"). */
export function requestedLabels(p: ResearchProject): string[] {
  return (strings(p.requested_dimensions) as { label?: string }[]).map((x) => String(x?.label || ""));
}

/**
 * A dimension request, as AIA takes it (ADR 0018): a proposal to the client's
 * knowledge, kind DIMENSION, carrying the classic request's content. The classic
 * interface wrote it to 18.6.6's Data Library; in AIA a person other than the
 * proposer approves it (ADR 0015), and only then is it in the catalogue.
 */
export function dimensionProposal(label: string, sourceStrategy: string, extra: Parameters<typeof requestBody>[2] = {}): {
  kind: "DIMENSION";
  title: string;
  summary: string;
  content: Record<string, unknown>;
} {
  const b = requestBody(label, sourceStrategy, extra);
  return {
    kind: "DIMENSION",
    title: label,
    summary: String(b.rationale),
    content: { source_strategy: b.source_strategy, spec: b.spec, origin: b.origin, requested_from: "research_dimensions" },
  };
}

export const PROPOSAL_DONE = "Návrh dimenze je ve Znalostech klienta. Do katalogu přibude, až ho někdo schválí.";
export const PROPOSAL_AI_DONE = "Návrh AI je ve Znalostech klienta. Do katalogu přibude, až ho někdo schválí.";

/** openDimensionResearch1793's topic, prefilled in the classic Data Library's Deep Research. */
export function dimensionResearchTopic(label: string): string {
  return `Nová dimenze: ${label}. Dohledej pro českou populaci kvantitativní prevalenci nebo průměr, přesnou definici/škálu a doložené vztahy k existujícím behaviorálním/demografickým predictorům. Bez kvantitativní populační kotvy dimenzi nedosimulovávej.`;
}
