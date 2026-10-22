// A research run's spend in words, as Průběh's Náklady shows it (artifact-fieldwork FLD4b): what the
// run has spent, what it holds, the calls it could not price and what remains in the study. Totals
// only, naming nobody (Q76 (c)). A figure the API did not give is unknown, never zero; a hold is not
// spent; a call without a known price is said apart, and while the run goes on it may still be one in
// flight, so it is never called a failure then.

import { t, tv } from "@/i18n/t";
import type { RunSpend } from "@/lib/api";

export type SpendRow = { key: "spent" | "held" | "unpriced" | "remaining"; label: string; value: string; note?: string };

const usd = (v: number) => `${v.toFixed(2)} USD`;

/** The card's rows, or null when the run's spend is unknown (not read, or not given to this caller).
 *  `remaining`: the study's remainder, undefined while it is read, null when it could not be. */
export function spendRows(spend: RunSpend | null | undefined, ended: boolean, remaining: number | null | undefined): SpendRow[] | null {
  if (!spend) return null;
  const rows: SpendRow[] = [
    { key: "spent", label: t("research.exec.spend.spent"), value: usd(spend.spent_usd) },
    // Holds belong to steps that run; once the run has ended there are none to speak of.
    { key: "held", label: t("research.exec.spend.held"), value: usd(spend.reserved_usd), note: ended ? undefined : t("research.exec.spend.heldNote") },
  ];
  if (spend.uncertain_calls > 0) {
    rows.push({
      key: "unpriced",
      label: t("research.exec.spend.unpriced"),
      value: tv("research.exec.spend.unpricedCalls", { count: spend.uncertain_calls }),
      note: t(ended ? "research.exec.spend.unpricedEnded" : "research.exec.spend.unpricedRunning"),
    });
  }
  // undefined: still being read, which is not the same as not readable (null).
  const known = typeof remaining === "number" && Number.isFinite(remaining);
  rows.push({
    key: "remaining",
    label: t("research.exec.spend.remaining"),
    value: known ? usd(remaining) : t(remaining === undefined ? "research.exec.spend.remainingLoading" : "research.exec.spend.remainingUnknown"),
    note: known ? t("research.exec.spend.remainingNote") : undefined,
  });
  return rows;
}
