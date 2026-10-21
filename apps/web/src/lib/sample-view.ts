// How Vzorek reads a readiness (plan artifact-sample SMP3): the support forecast and the question
// outlook as the server worked them out before the run. Pure. Nothing here decides: the server's
// readiness is the authority, and what it could not forecast reads as unknown, never as good.

import type { CheckStatus, OutlookVerdict, Readiness } from "./api";
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
