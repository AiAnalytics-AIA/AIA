// How Vzorek reads a readiness (plan artifact-sample SMP3): the support forecast and the question
// outlook as the server worked them out before the run. Pure. Nothing here decides: the server's
// readiness is the authority, and what it could not forecast reads as unknown, never as good.

import type { CheckStatus, OutlookVerdict, PersonaSourceOption, Readiness } from "./api";
import { outlookCounts } from "./research-execution";

/** The readiness check the server adds with its support forecast (domain/support_forecast.py). */
export const SUPPORT_FORECAST_CHECK = "support_forecast";

/**
 * The support forecast as Vzorek shows it.
 * - `known`: the server counted the donors the run will draw; its check's status and words.
 * - `unknown`: nothing was counted. A panel run draws its donors at fieldwork, so the server's
 *   forecast for it is unknown by rule (`forecast_support`, `SupportForecast.known`); a readiness
 *   without the check (a fieldwork source the server does not forecast, or an older API) is
 *   unknown too. The server's words, when it gave any, say why.
 */
export type SupportForecastLine =
  | { known: true; status: CheckStatus; message: string }
  | { known: false; message: string | null };

export function supportForecastOf(readiness: Readiness): SupportForecastLine {
  const check = readiness.checks.find((c) => c.id === SUPPORT_FORECAST_CHECK);
  if (!check) return { known: false, message: null };
  if (readiness.persona_source === "panel") return { known: false, message: check.message };
  return { known: true, status: check.status, message: check.message };
}

/**
 * The question outlook in counts, every verdict present; `null` when the API sent none (an
 * older API, or a design that does not compile), which reads as unknown, never as "all answered".
 */
export function outlookSummary(readiness: Readiness): Record<OutlookVerdict, number> | null {
  const items = readiness.question_outlook;
  if (!items || !items.length) return null;
  return outlookCounts(items);
}

/**
 * Who will answer (plan artifact-sample SMP5): every persona source the server lists, whether
 * this deployment offers it, why not, and which a start takes by default. Read only here: the
 * source is chosen on Spuštění, beside the start that pins it (SQ1 = Q54 b). `null` when the API
 * sent no sources (an older API), which reads as unknown, never as a default.
 */
export function personaSourcesOf(readiness: Readiness): PersonaSourceOption[] | null {
  const sources = readiness.persona_sources;
  return sources && sources.length ? sources : null;
}

/**
 * Whether Spuštění offers the persona source choice for this readiness: only for a run answered
 * by AI respondents (`fieldwork_source: "ai_runtime"`) with sources listed, as Spuštění renders
 * its choice (ExecutionSteps.tsx RunStep). Anything else answers from a fixture: there is no
 * source to choose, and Vzorek must not send the person to a choice that is not there.
 */
export function sourceChosenOnRun(readiness: Readiness): boolean {
  return readiness.fieldwork_source === "ai_runtime" && personaSourcesOf(readiness) !== null;
}
