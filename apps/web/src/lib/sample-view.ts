// How Vzorek reads a readiness (plan artifact-sample SMP3): the support forecast and the question
// outlook as the server worked them out before the run. Pure. Nothing here decides: the server's
// readiness is the authority, and what it could not forecast reads as unknown, never as good.

import { verdictWords } from "@/research/audience";

import type { CheckStatus, OutlookVerdict, PersonaSourceOption, ReadinessBody } from "./api";
import { plural } from "./format";
import { outlookCounts } from "./research-execution";
import type { WorkbenchStage } from "./workbench-stages";

/** The readiness check the server adds with its support forecast (domain/support_forecast.py). */
export const SUPPORT_FORECAST_CHECK = "support_forecast";

/**
 * The support forecast as Vzorek shows it.
 * - `known`: the server counted the donors the run will draw; its check's status and words.
 * - `unknown`: nothing was counted. A panel run's donors are counted only from the sample a start
 *   would draw (run-qc-and-checkpoint RQC6b): without a drawn `sample_composition` (no population,
 *   a refused draw, a selected child, an older API) the server's forecast is unknown by rule
 *   (`forecast_support`). A readiness without the check (a fieldwork source the server does not
 *   forecast) is unknown too. The server's words, when it gave any, say why.
 */
export type SupportForecastLine =
  | { known: true; status: CheckStatus; message: string }
  | { known: false; message: string | null };

export function supportForecastOf(readiness: ReadinessBody): SupportForecastLine {
  const check = readiness.checks.find((c) => c.id === SUPPORT_FORECAST_CHECK);
  if (!check) return { known: false, message: null };
  // Counted, not just drawn: a drawn sample with a respondent without a donor stays unknown.
  const drawn = readiness.sample_composition?.refused === null && readiness.sample_composition.support_counted === true;
  if (readiness.persona_source === "panel" && !drawn) return { known: false, message: check.message };
  return { known: true, status: check.status, message: check.message };
}

/**
 * The verdict each reason gives an item (domain/question_outlook.py `_VERDICT`). An item carries
 * every reason it has, the support reason included, and its verdict is the worst of them: a tile
 * is captioned only by the reasons that give its own verdict.
 */
const REASON_VERDICT: Readonly<Record<string, OutlookVerdict>> = {
  conditional: "UNANSWERABLE",
  familiarity: "UNANSWERABLE",
  fidelity_refused: "UNANSWERABLE",
  support_suppressed: "UNANSWERABLE",
  support_analysis_excluded: "AT_RISK",
  open_ended: "AT_RISK",
  support_indicative: "AT_RISK",
  support_unknown: "UNKNOWN",
};

/** One of §02's tiles (spec vzorek V4): a verdict, how many items have it, and its commonest reason. */
export type OutlookTile = { verdict: OutlookVerdict; count: number; reason: string | null };

/**
 * §02's tiles, from the server's question outlook: answerable, at risk and unknown always, and
 * unanswerable beside them only when an item has it (the v73 board draws three). Each tile names
 * the reason most of its items share, the first met on a tie, counting only the reasons that give
 * that verdict (a code this client does not know counts, so it is named, never hidden); the
 * answerable tile has none.
 * `null` when the server sent no outlook, which reads as unknown, never as answered.
 */
export function outlookTiles(readiness: ReadinessBody): OutlookTile[] | null {
  const items = readiness.question_outlook;
  if (!items || !items.length) return null;
  const counts = outlookCounts(items);
  const shown: OutlookVerdict[] = ["ANSWERABLE", "AT_RISK", "UNKNOWN", ...(counts.UNANSWERABLE ? (["UNANSWERABLE"] as const) : [])];
  return shown.map((verdict) => {
    const tally = new Map<string, number>();
    if (verdict !== "ANSWERABLE") for (const item of items) if (item.verdict === verdict) for (const r of item.reasons) if ((REASON_VERDICT[r] ?? verdict) === verdict) tally.set(r, (tally.get(r) ?? 0) + 1);
    let reason: string | null = null;
    for (const [code, n] of tally) if (reason === null || n > (tally.get(reason) ?? 0)) reason = code;
    return { verdict, count: counts[verdict], reason };
  });
}

/**
 * The run's cost ceiling beside N (spec vzorek V2, SMP8), as the server worked it out for the n it
 * read: known with that n, or unknown with the server's reason (`cost_ceiling_unknown`), never a
 * zero. The server sends no reason when the design did not compile, for whatever cause: then the
 * reason is `null`, never one guessed for it.
 */
export type CeilingLine = { known: true; usd: number; n: number | null } | { known: false; code: string | null };

export function ceilingOf(readiness: ReadinessBody): CeilingLine {
  const usd = readiness.cost_ceiling_usd;
  if (typeof usd === "number" && Number.isFinite(usd)) return { known: true, usd, n: readiness.n };
  return { known: false, code: readiness.cost_ceiling_unknown };
}

/**
 * Who will answer (plan artifact-sample SMP5): every persona source the server lists, whether
 * this deployment offers it, why not, and which a start takes by default. Read only here: the
 * source is chosen on Spuštění, beside the start that pins it (SQ1 = Q54 b). `null` when the API
 * sent no sources (an older API), which reads as unknown, never as a default.
 */
export function personaSourcesOf(readiness: ReadinessBody): PersonaSourceOption[] | null {
  const sources = readiness.persona_sources;
  return sources && sources.length ? sources : null;
}

/**
 * Whether Spuštění offers the persona source choice for this readiness: only for a run answered
 * by AI respondents (`fieldwork_source: "ai_runtime"`) with sources listed, as Spuštění renders
 * its choice (ExecutionSteps.tsx RunStep). Anything else answers from a fixture: there is no
 * source to choose, and Vzorek must not send the person to a choice that is not there.
 */
export function sourceChosenOnRun(readiness: ReadinessBody): boolean {
  return readiness.fieldwork_source === "ai_runtime" && personaSourcesOf(readiness) !== null;
}

/**
 * Where a readiness check is fixed, by the server's check id (domain/research_design.py
 * `readiness`, support_forecast.py, research_trace.py): n and the support it gives on Vzorek itself,
 * where n is set (SMP7), the audience on Cílová skupina, the selected dimensions on Dimenze, everything the questionnaire
 * decides on Dotazník. A check this client does not know names no stage: it is shown, never sent
 * to a guessed one.
 */
const CHECK_STAGE: Readonly<Record<string, WorkbenchStage>> = {
  sample_size: "sample",
  support_forecast: "sample",
  sociomap_support: "sample",
  dimensions: "dimensions",
  audience: "audience",
  panel_sample: "audience",
  questionnaire: "questionnaire",
  conditional_questions: "questionnaire",
  battery_familiarity: "questionnaire",
  sociomap_input: "questionnaire",
  research_question_coverage: "questionnaire",
};

/** Checks the server names per item, `<prefix>:<…>`: a design that does not compile, a tracked set's size. */
const CHECK_PREFIX_STAGE: Readonly<Record<string, WorkbenchStage>> = { compile: "questionnaire", battery_size: "questionnaire", condition: "questionnaire" };

export function checkStage(checkId: string): WorkbenchStage | null {
  if (Object.hasOwn(CHECK_STAGE, checkId)) return CHECK_STAGE[checkId];
  const prefix = checkId.split(":", 1)[0];
  return checkId.includes(":") && Object.hasOwn(CHECK_PREFIX_STAGE, prefix) ? CHECK_PREFIX_STAGE[prefix] : null;
}

/** Worst first: what stops a run, then what limits it, then what passed; the server's order within each. */
const CHECK_RANK: Readonly<Record<string, number>> = { FAIL: 0, WARN: 1, PASS: 2 };

export type ReadinessSummary = {
  /** The server's verdict, the authority: false refuses a start whatever the counts say. */
  ready: boolean;
  checks: ReadinessBody["checks"];
  /** FAILs: the run cannot start. */
  blocking: number;
  /** WARNs: it can, with limits (ADR 0025). */
  warnings: number;
  /** A status this client does not know: never counted as passed. */
  unknown: number;
};

export function readinessSummary(readiness: ReadinessBody): ReadinessSummary {
  const known = (s: string) => Object.hasOwn(CHECK_RANK, s);
  const rank = (s: string) => (known(s) ? CHECK_RANK[s] : -1);
  const checks = readiness.checks.map((c, i) => [c, i] as const).sort((a, b) => rank(a[0].status) - rank(b[0].status) || a[1] - b[1]).map(([c]) => c);
  const count = (s: string) => checks.filter((c) => c.status === s).length;
  return { ready: readiness.ready, checks, blocking: count("FAIL"), warnings: count("WARN"), unknown: checks.filter((c) => !known(c.status)).length };
}

/**
 * The readiness in one line, as the v73 board's pill reads it (spec vzorek V5): whether a run can
 * start and what holds it. The server's `ready` decides; a status this client does not know is
 * said, never read as passed.
 */
export type ReadinessLine = { tone: "done" | "done-warn" | "fault" | "inert"; words: string };

export function readinessLine(s: ReadinessSummary): ReadinessLine {
  if (!s.ready) {
    return { tone: "fault", words: s.blocking ? `Nelze spustit · ${plural(s.blocking, "kontrola brání", "kontroly brání", "kontrol brání")}` : "Nelze spustit: server spuštění nepovolí" };
  }
  if (s.unknown) return { tone: "inert", words: "Stav některých kontrol je neznámý" };
  if (s.warnings) return { tone: "done-warn", words: `Lze spustit · ${s.warnings} upozornění` };
  return { tone: "done", words: "Lze spustit · nic nebrání" };
}

/** The sampler's quota fields in words; a field this client does not know keeps its name. */
const QUOTA_FIELD_WORDS: Readonly<Record<string, string>> = {
  pohlavi: "Pohlaví",
  vek_skupina: "Věk",
  kraj: "Kraj",
  vzdelani: "Vzdělání",
  zamestnani_status: "Zaměstnání",
};

/** The sampler's word for a missing value (domain/population/sampling.py MISSING). */
const MISSING = "<missing>";

/** One row of the composition: a cell with respondents, its values in words and its share of n. */
export type CompositionRow = { key: string; label: string; n: number; share: number };

/**
 * The sample a panel run would draw, as Vzorek's composition reads it (plan artifact-sample SMP2,
 * run-qc-and-checkpoint RQC6c).
 * - `roster`: fictional respondents, drawn without quotas.
 * - `drawn`: the sampler's own allotment, the cells with respondents largest first.
 * - `refused`: the sampler would not draw this design, in words.
 * - `unknown`: a panel run the server drew nothing for (no population, a selected child, an older
 *   API); never a composition.
 */
export type Composition =
  | { kind: "roster" }
  | { kind: "drawn"; fields: string[]; rows: CompositionRow[]; total: number; donors: number | null }
  | { kind: "refused"; words: string }
  | { kind: "unknown" };

export function compositionOf(readiness: ReadinessBody): Composition {
  if (readiness.persona_source !== "panel") return { kind: "roster" };
  const drawn = readiness.sample_composition;
  if (!drawn) return { kind: "unknown" };
  if (drawn.refused !== null) {
    const words =
      drawn.refused === "population_unavailable"
        ? "Populaci se teď nepodařilo načíst, vzorek nelze předem vybrat."
        : verdictWords({ reason: drawn.refused, reasons: drawn.refused_reasons });
    return { kind: "refused", words };
  }
  const total = drawn.cells.reduce((sum, c) => sum + c.n, 0);
  const rows = drawn.cells
    .filter((c) => c.n > 0)
    .map((c) => ({ key: c.key, label: c.values.map((v) => (v === MISSING ? "neuvedeno" : v)).join(" · "), n: c.n, share: total ? c.n / total : 0 }))
    .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label, "cs"));
  return { kind: "drawn", fields: drawn.quota_fields.map((f) => QUOTA_FIELD_WORDS[f] ?? f), rows, total, donors: drawn.sample_donors };
}
