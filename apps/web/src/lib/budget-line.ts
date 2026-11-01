// What remains of a study's budget, beside what an action can cost at most (run-recovery-and-truth
// 6d). Said beside every start, retry and budget lift, in the same words, from the study as the API
// reads it at that moment. A figure the API did not give is unknown, never zero; what an action can
// cost is the API's upper bound, never a forecast.

import { t, tv } from "@/i18n/t";
import { api, type Study } from "@/lib/api";

export type StudyBudget = Pick<Study, "budget_usd" | "spent_usd" | "remaining_usd">;

const usd = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/**
 * The study's remaining budget in words and, when `ceiling` is given (a number, or null for "cannot
 * be worked out"), what follows from it: what the action at its ceiling would leave, or that it can
 * cost more than remains and may stop for a person to lift the budget. The API's remainder is the
 * budget less recorded spend; what running steps hold is not in it, so the line says so and promises
 * nothing it cannot see. The question it is added to
 * names the ceiling itself; with the remainder unknown, nothing follows and nothing is said.
 */
export function budgetLine(study: StudyBudget | null | undefined, ceiling?: number | null): string {
  const remaining = usd(study?.remaining_usd);
  const parts = [remaining === null ? t("research.exec.budgetLine.unknown") : tv("research.exec.budgetLine.remaining", { remaining: remaining.toFixed(2) })];
  if (ceiling === null) parts.push(t("research.exec.budgetLine.ceilingUnknown"));
  else if (ceiling !== undefined) {
    if (remaining !== null && ceiling <= remaining) parts.push(tv("research.exec.budgetLine.within", { after: (remaining - ceiling).toFixed(2) }));
    else if (remaining !== null) parts.push(t("research.exec.budgetLine.beyond"));
  }
  return parts.join(" ");
}

/**
 * What a remainder read beside a budget lift leaves out: the amounts open holds keep for steps that
 * run now. Said only when there is a remainder to qualify; an unknown one says nothing more.
 */
export function holdsNote(study: StudyBudget | null | undefined): string | null {
  return usd(study?.remaining_usd) === null ? null : t("research.exec.budgetLine.holdsNotCounted");
}

/** The study's budget read now, or null when it cannot be read: the line then says it is unknown. */
export async function readBudget(studyId: string): Promise<StudyBudget | null> {
  try {
    return await api.study(studyId);
  } catch {
    return null;
  }
}
