// The one modal for money (input-interactions I7a; the approval cards' anatomy, D-01): the pure
// part of SpendDialog. Four kinds of question share it, and four sums keep their own names --
// Rozpočet klienta, Rozpočet studie, Peněženka, Práh potvrzení -- so a person never reads one as
// another. What an action costs is the API's upper bound ("horní mez, ne odhad"); a sum the API
// did not give is unknown and said so, never printed as zero (CLAUDE.md §8).

import { t, tv } from "@/i18n/t";
import { formatNumber } from "./number-input";

export type SpendKind = "spend_confirm" | "study_budget_lift" | "client_budget_lift" | "wallet_lift";
export const SPEND_KINDS: readonly SpendKind[] = ["spend_confirm", "study_budget_lift", "client_budget_lift", "wallet_lift"];

export type MoneyName = "client_budget" | "study_budget" | "wallet" | "threshold";
export const MONEY_NAMES: readonly MoneyName[] = ["client_budget", "study_budget", "wallet", "threshold"];

/** One named sum: its amount and, for a budget or the wallet, what remains of it. Null: unknown. */
export type MoneyLine = { name: MoneyName; usd: number | null; remainingUsd?: number | null; note?: string };

const known = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

/** USD as Czech prints it: "1,76 USD", "1 250,00 USD"; unknown in words, never "0,00". */
export function usdWords(usd: number | null | undefined): string {
  return known(usd) ? `${formatNumber(usd, 2)} USD` : t("input.spend.unknown");
}

export function spendTitle(kind: SpendKind): string {
  return t(`input.spend.kinds.${kind}`);
}

export function moneyName(name: MoneyName): string {
  return t(`input.spend.names.${name}`);
}

/** The ceiling as the dialog states it: the sum and "horní mez, ne odhad", or that it is unknown. */
export function ceilingWords(ceilingUsd: number | null): { value: string; note: string } {
  return known(ceilingUsd)
    ? { value: usdWords(ceilingUsd), note: t("input.spend.ceilingNote") }
    : { value: t("input.spend.ceilingUnknown"), note: t("input.spend.ceilingUnknownNote") };
}

/**
 * What remains of the pot that pays once the action has cost its ceiling, after a lift to
 * `newBudgetUsd` when one is being set (the remainder grows by what the budget grows). Null when
 * either side is unknown: nothing follows from a missing figure.
 */
export function remainingAfter(line: MoneyLine | undefined, ceilingUsd: number | null, newBudgetUsd?: number | null): number | null {
  if (!line || !known(line.remainingUsd) || !known(ceilingUsd)) return null;
  let remaining = line.remainingUsd;
  if (newBudgetUsd !== undefined) {
    if (!known(newBudgetUsd) || !known(line.usd)) return null;
    remaining += newBudgetUsd - line.usd;
  }
  // The sign is decided before rounding: an overrun under half a cent is still an overrun, never
  // "zbude 0,00 USD" (review of #532). Only binary noise (1e-9) counts as exactly enough.
  const raw = remaining - ceilingUsd;
  if (raw < -1e-9) return Math.min(Number(raw.toFixed(2)), -0.01);
  return Math.max(Number(raw.toFixed(2)), 0);
}

/** The after-line in words: what is left at the highest price, that it may stop, or unknown. */
export function afterWords(after: number | null): string {
  if (after === null) return t("input.spend.afterUnknown");
  return after >= 0 ? tv("input.spend.after", { usd: usdWords(after) }) : t("input.spend.beyond");
}

/** A line's amount with its remainder beside it: "80,00 USD · zbývá 0,90 USD". */
export function lineWords(line: MoneyLine): string {
  const parts = [usdWords(line.usd)];
  if (line.remainingUsd !== undefined) parts.push(tv("input.spend.remaining", { usd: usdWords(line.remainingUsd) }));
  return parts.join(" · ");
}
