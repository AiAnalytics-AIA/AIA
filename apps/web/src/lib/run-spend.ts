// A research run's spend in words, as Průběh's Náklady shows it (artifact-fieldwork FLD4b; as tiles, FLD4e): what the
// run has spent, what it holds, the calls it could not price and what remains in the study. Totals
// only, naming nobody (Q76 (c)). A figure the API did not give is unknown, never zero; a hold is not
// spent; a call without a known price is said apart, and while the run goes on it may still be one in
// flight, so it is never called a failure then.

import { t, tv } from "@/i18n/t";
import type { RunCeiling, RunSpend } from "@/lib/api";
import { codedText, codeWords } from "@/lib/reason-words";
import { usd } from "@/lib/researcher-spend";

export type SpendRow = { key: "spent" | "held" | "ceiling" | "unpriced" | "remaining"; label: string; value: string; note?: string };

/** The run's ceiling as its start recorded it (FLD4d): an upper bound, its reason when it had none, or
 *  that the run recorded none at all; never a zero for any of them. */
function ceilingRow(ceiling: RunCeiling | null | undefined): SpendRow {
  const label = t("research.exec.spend.ceiling");
  if (!ceiling) return { key: "ceiling", label, value: t("research.exec.spend.ceilingUnrecorded"), note: t("research.exec.spend.ceilingUnrecordedNote") };
  if (ceiling.usd === null) {
    const why = ceiling.unknown ? codedText(codeWords("research.exec.cost.unknown", ceiling.unknown)) : undefined;
    return { key: "ceiling", label, value: t("research.exec.spend.ceilingUnknown"), note: why };
  }
  return { key: "ceiling", label, value: usd(ceiling.usd), note: t("research.exec.spend.ceilingNote") };
}

/** The card's rows, or null when the run's spend is unknown (not read, or not given to this caller).
 *  `remaining`: the study's remainder, undefined while it is read, null when it could not be. */
export function spendRows(
  spend: RunSpend | null | undefined,
  ended: boolean,
  remaining: number | null | undefined,
  // On the card it shows only beside a spend, gated as the spend is: null there means not recorded.
  ceiling: RunCeiling | null | undefined,
): SpendRow[] | null {
  if (!spend) return null;
  const rows: SpendRow[] = [
    { key: "spent", label: t("research.exec.spend.spent"), value: usd(spend.spent_usd) },
    // Holds belong to steps that run; once the run has ended there are none to speak of, so neither
    // the label nor a note says any step runs.
    {
      key: "held",
      label: t(ended ? "research.exec.spend.heldEnded" : "research.exec.spend.held"),
      value: usd(spend.reserved_usd),
      note: ended ? undefined : t("research.exec.spend.heldNote"),
    },
  ];
  rows.push(ceilingRow(ceiling));
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
