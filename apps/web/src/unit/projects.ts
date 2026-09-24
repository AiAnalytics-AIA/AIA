// Projects — *Správa projektů* (ADR 0014, area A2): what the unit answers, and
// the classic screen's logic, ported from its JavaScript. Each port names the
// function it comes from; projects.parity.test.ts runs the original, extracted
// verbatim from ui_app.html, on the same rows and compares.

export type JobSummary = { running?: number; waiting_user?: number; waiting_ai?: number; failed?: number; queued?: number };

export type ProjectRow = {
  project_id: string;
  title?: string;
  project_type?: string;
  status?: string;
  current_stage?: string;
  preferred_provider?: string;
  is_demo?: boolean;
  archived?: boolean;
  pinned?: boolean;
  tags?: string[];
  goal?: string;
  research_question?: string;
  takeaway?: string;
  study_result?: string;
  population?: string;
  sample?: number;
  client?: string;
  domain?: string;
  study_type?: string;
  progress_pct?: number;
  revision?: number;
  modified_at?: string;
  created_at?: string;
  last_checkpoint?: string;
  last_completed_stage?: string;
  last_completed_artifact?: string;
  job_summary?: JobSummary;
  collection?: string;
};

export type DashboardCounts = Partial<
  Record<
    | "all"
    | "research"
    | "simulation"
    | "running"
    | "waiting_user"
    | "waiting_ai"
    | "failed"
    | "ready"
    | "completed"
    | "archived"
    | "pinned"
    | "demo",
    number
  >
>;

export class ShapeError extends Error {
  constructor(what: string) {
    super(`Neočekávaná odpověď backendu: ${what}`);
    this.name = "ShapeError";
  }
}

const STRING_FIELDS = [
  "title", "project_type", "status", "current_stage", "preferred_provider", "goal", "research_question",
  "takeaway", "study_result", "population", "client", "domain", "study_type", "modified_at", "created_at",
  "last_checkpoint", "last_completed_stage", "last_completed_artifact", "collection",
] as const;
const NUMBER_FIELDS = ["sample", "progress_pct", "revision"] as const;
const BOOLEAN_FIELDS = ["is_demo", "archived", "pinned"] as const;

const isRecord = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);

/** A row keeps only fields of the type the screen reads; a wrong type is dropped, never coerced. */
export function parseProjectRow(x: unknown, where = "projekt"): ProjectRow {
  if (!isRecord(x) || typeof x.project_id !== "string" || !x.project_id) throw new ShapeError(`${where} bez project_id`);
  const row: ProjectRow = { project_id: x.project_id };
  const out = row as Record<string, unknown>;
  for (const k of STRING_FIELDS) if (typeof x[k] === "string") out[k] = x[k];
  for (const k of NUMBER_FIELDS) if (typeof x[k] === "number" && Number.isFinite(x[k])) out[k] = x[k];
  for (const k of BOOLEAN_FIELDS) if (typeof x[k] === "boolean") out[k] = x[k];
  if (Array.isArray(x.tags)) row.tags = x.tags.filter((t): t is string => typeof t === "string");
  if (isRecord(x.job_summary)) {
    const j: JobSummary = {};
    for (const k of ["running", "waiting_user", "waiting_ai", "failed", "queued"] as const) {
      const v = x.job_summary[k];
      if (typeof v === "number" && Number.isFinite(v)) j[k] = v;
    }
    row.job_summary = j;
  }
  return row;
}

export function parseProjectRows(x: unknown): ProjectRow[] {
  if (!Array.isArray(x)) throw new ShapeError("seznam projektů není pole");
  return x.map((r, i) => parseProjectRow(r, `projekt ${i + 1}`));
}

export function parseDashboardCounts(x: unknown): DashboardCounts {
  if (!isRecord(x) || !isRecord(x.counts)) throw new ShapeError("dashboard bez counts");
  const counts: Record<string, number> = {};
  for (const [k, v] of Object.entries(x.counts)) if (typeof v === "number" && Number.isFinite(v)) counts[k] = v;
  return counts as DashboardCounts;
}

// ---- the classic screen's state -------------------------------------------

export type View =
  | "all" | "research" | "simulation" | "running" | "waiting_user" | "waiting_ai"
  | "failed" | "completed" | "pinned" | "archived" | "demo" | "ready";
export type Sort = "modified_desc" | "created_desc" | "title" | "progress_desc";
export type DateWindow = "all" | "7" | "30" | "90";

export type Filters = {
  view: View;
  q: string;
  status: string; // "all" or a status
  provider: string; // "all" or a provider
  stage: string; // "all" or a stage
  date: DateWindow;
  sort: Sort;
};

/** pmReset1810 */
export const DEFAULT_FILTERS: Filters = {
  view: "all", q: "", status: "all", provider: "all", stage: "all", date: "all", sort: "modified_desc",
};

/** pmViewsHtml1810: the view tabs, in order, with the count each shows. */
export const VIEWS: readonly { id: View; label: string; count: (c: DashboardCounts) => number }[] = [
  { id: "all", label: "Aktivní", count: (c) => Math.max(0, (c.all ?? 0) - (c.archived ?? 0)) },
  { id: "research", label: "Výzkumy", count: (c) => c.research ?? 0 },
  { id: "simulation", label: "Simulace", count: (c) => c.simulation ?? 0 },
  { id: "running", label: "Probíhá", count: (c) => c.running ?? 0 },
  { id: "waiting_user", label: "Čeká na mě", count: (c) => c.waiting_user ?? 0 },
  { id: "waiting_ai", label: "Čeká na AI", count: (c) => c.waiting_ai ?? 0 },
  { id: "failed", label: "Vyžaduje zásah", count: (c) => c.failed ?? 0 },
  { id: "completed", label: "Dokončeno", count: (c) => c.completed ?? 0 },
  { id: "pinned", label: "Připnuté", count: (c) => c.pinned ?? 0 },
  { id: "archived", label: "Archiv", count: (c) => c.archived ?? 0 },
  { id: "demo", label: "DEMO", count: (c) => c.demo ?? 0 },
];

/** pmMatchesView1810 */
export function matchesView(x: ProjectRow, view: View): boolean {
  const j = x.job_summary ?? {};
  const live = !x.is_demo;
  switch (view) {
    case "research": return live && x.project_type !== "simulation" && !x.archived;
    case "simulation": return live && x.project_type === "simulation" && !x.archived;
    case "demo": return !!x.is_demo;
    case "waiting_user": return live && (x.status === "WAITING_USER" || (j.waiting_user ?? 0) > 0);
    case "waiting_ai": return live && (x.status === "WAITING_CREDITS" || x.status === "WAITING_CAPACITY" || (j.waiting_ai ?? 0) > 0);
    case "running": return live && (x.status === "IN_PROGRESS" || (j.running ?? 0) > 0);
    case "failed": return live && (j.failed ?? 0) > 0;
    case "completed": return live && String(x.status ?? "").startsWith("COMPLETED");
    case "archived": return live && !!x.archived;
    case "pinned": return live && !!x.pinned;
    case "ready": return live && ["DRAFT", "READY_TO_CONTINUE"].includes(x.status ?? "");
    default: return !x.archived;
  }
}

/** pmText1810 */
export function searchText(x: ProjectRow): string {
  return [
    x.title, x.project_id, x.goal, x.research_question, x.population, x.client, x.study_result,
    x.current_stage, x.domain, x.study_type, ...(x.tags ?? []),
  ].filter(Boolean).join(" ").toLowerCase();
}

/** pmDateOk1810 */
export function dateOk(x: ProjectRow, date: DateWindow, now: number): boolean {
  if (date === "all" || x.is_demo) return true;
  const d = new Date(x.modified_at || x.created_at || 0).getTime();
  return !!d && d >= now - Number(date) * 86_400_000;
}

/** pmFiltered1810 */
export function filterProjects(rows: readonly ProjectRow[], f: Filters, now: number): ProjectRow[] {
  const q = f.q.trim().toLowerCase();
  const out = rows
    .filter((x) => matchesView(x, f.view))
    .filter((x) => !q || searchText(x).includes(q))
    .filter((x) => f.status === "all" || x.status === f.status)
    .filter((x) => f.provider === "all" || x.preferred_provider === f.provider)
    .filter((x) => f.stage === "all" || x.current_stage === f.stage)
    .filter((x) => dateOk(x, f.date, now));
  out.sort((a, b) =>
    f.sort === "title" ? String(a.title ?? "").localeCompare(String(b.title ?? ""), "cs")
    : f.sort === "progress_desc" ? Number(b.progress_pct ?? 0) - Number(a.progress_pct ?? 0)
    : f.sort === "created_desc" ? String(b.created_at ?? "").localeCompare(String(a.created_at ?? ""))
    : String(b.modified_at ?? "").localeCompare(String(a.modified_at ?? "")),
  );
  return out;
}

/** renderProjects1785 (1810): the options each filter offers, from non-DEMO rows only. */
export function filterOptions(rows: readonly ProjectRow[]): { statuses: string[]; providers: string[]; stages: string[] } {
  const live = rows.filter((x) => !x.is_demo);
  const uniq = (xs: (string | undefined)[]) => [...new Set(xs.filter((v): v is string => !!v))].sort();
  return {
    statuses: uniq(live.map((x) => x.status)),
    providers: uniq(live.map((x) => x.preferred_provider)),
    stages: uniq(live.map((x) => x.current_stage)),
  };
}

// ---- labels ---------------------------------------------------------------

const STATUS_CS: Record<string, string> = {
  DRAFT: "Koncept", IN_PROGRESS: "Probíhá", WAITING_USER: "Čeká na vás", WAITING_CREDITS: "Čeká na limit/kredit",
  WAITING_CAPACITY: "Čeká na kapacitu", READY_TO_CONTINUE: "Připraven pokračovat", COMPLETED: "Hotovo",
  COMPLETED_WITH_WARNINGS: "Hotovo s upozorněním", ARCHIVED: "Archiv",
};

/** statusCzech1790 */
export function statusLabel(s: string | undefined): string {
  return (s && STATUS_CS[s]) || s || "—";
}

const STAGE_CS: Record<string, string> = {
  BRIEF: "zadání", DEEP_RESEARCH: "doplnění kontextu", RESEARCH_DESIGN: "návrh výzkumu", QUESTIONNAIRE: "dotazník",
  AUDIENCE: "cílová populace", DIMENSIONS: "dimenze", SAMPLE_PLAN: "vzorek", FIELDWORK: "sběr odpovědí",
  AGGREGATION: "zpracování výsledků", VALIDATION: "validace", ANALYSIS: "analýza", REPORT: "report", DELIVERY: "hotovo",
  BASELINE: "baseline", SCENARIO_CONTRACT: "scénář", VARIANTS: "varianty", WORLDS: "simulace světů",
  FROZEN_RESULTS: "uzamčené výsledky", COMPARISON: "porovnání", INTERPRETATION: "interpretace",
};

/** stageHuman1797 */
export function stageLabel(x: string | undefined): string {
  const s = String(x ?? "");
  return STAGE_CS[s.toUpperCase()] || s.replaceAll("_", " ").toLowerCase() || "začátek";
}

/** providerLabel1790 */
export function providerLabel(p: string | undefined): string {
  return p === "anthropic" ? "Claude API" : "Claude Code";
}

/** humanStatusSentence1797 */
export function statusSentence(x: ProjectRow): string {
  const s = String(x.status || "DRAFT").toUpperCase();
  if (s === "COMPLETED" || s === "COMPLETED_WITH_WARNINGS") return "Projekt je hotový a má finální výstup.";
  if (s === "IN_PROGRESS" || s === "RUNNING") return `Projekt se právě zpracovává — aktuálně ${stageLabel(x.current_stage)}.`;
  if (s === "WAITING_CREDITS") return "Projekt čeká na obnovení Claude Code kreditů. Hotová práce zůstala uložená.";
  if (s === "WAITING_USER") return "Projekt čeká na vaše rozhodnutí.";
  if (s === "WAITING_CAPACITY") return "Projekt čeká na dostupnou AI kapacitu.";
  if (s === "READY_TO_CONTINUE") return `Projekt je uložený a připravený pokračovat od ${stageLabel(x.current_stage)}.`;
  return `Projekt je rozpracovaný — další krok je ${stageLabel(x.current_stage)}.`;
}

/** pmAgo1810 */
export function ago(s: string | undefined, now: number): string {
  if (!s) return "—";
  const d = Math.floor((now - new Date(s).getTime()) / 86_400_000);
  return d <= 0 ? "dnes" : d === 1 ? "včera" : d < 31 ? `před ${d} dny` : String(s).slice(0, 10);
}

export type Tone = "done" | "you" | "fault" | "neutral";

/** statusChip1796: which family the status chip belongs to (ok / warn / bad in 18.6.6). */
export function statusTone(x: string | undefined): Tone {
  const s = String(x ?? "").toUpperCase();
  if (s === "COMPLETED") return "done";
  if (s.includes("WAITING") || s === "RUNNING" || s === "IN_PROGRESS") return "you";
  if (s === "FAILED") return "fault";
  return "neutral";
}

/** pmJobBadges1810, as data: label and tone, in the classic order. */
export function jobBadges(x: ProjectRow): { label: string; tone: Tone }[] {
  const j = x.job_summary ?? {};
  const out: { label: string; tone: Tone }[] = [];
  if (j.running) out.push({ label: `${j.running} běží`, tone: "done" });
  if (j.waiting_user) out.push({ label: `${j.waiting_user} čeká na vás`, tone: "you" });
  if (j.waiting_ai) out.push({ label: `${j.waiting_ai} čeká na AI`, tone: "you" });
  if (j.failed) out.push({ label: `${j.failed} selhalo`, tone: "fault" });
  if (j.queued) out.push({ label: `${j.queued} ve frontě`, tone: "neutral" });
  return out;
}

/** pmCard1810: the texts a card shows, derived exactly as the classic card derives them. */
export function cardText(x: ProjectRow) {
  const demo = !!x.is_demo;
  const sim = x.project_type === "simulation";
  return {
    kind: `${demo ? "DEMO · " : ""}${sim ? "SIMULACE" : "VÝZKUM"}`,
    title: x.title || "Bez názvu",
    questionLabel: sim ? "Co simulace řeší" : "Výzkumná otázka",
    question: x.research_question || x.goal || x.takeaway || "zatím není vyplněno",
    resultLabel: demo || String(x.status ?? "").startsWith("COMPLETED") ? "Výsledek" : "Aktuální stav",
    result: x.study_result || x.takeaway || statusSentence(x),
    population: x.population || (x.sample ? `N=${x.sample}` : "viz detail"),
    client: x.client || x.domain || x.study_type || "—",
    safePoint: stageLabel(x.last_checkpoint || x.last_completed_stage || x.last_completed_artifact || "zatím bez checkpointu"),
    progress: Math.max(2, Number(x.progress_pct ?? 0)),
  };
}
