// A stored code in words (run-recovery-and-truth 6b). The API and the engine store codes: a
// waiting reason, a quarantine reason, a check's status. A person reads words. Where this
// client has words for a code it says them; where it has none it says so plainly and keeps
// the code for the technical details, so the screen never prints a code as if it were a
// sentence and never hides that something was recorded.

import { t } from "@/i18n/t";
import type { ResearchStep } from "@/lib/api";
import { waitingDetail } from "@/lib/research-execution";

/** Words for a code; `code` is set only when the client has no words for it. */
export type Coded = { words: string; code: string | null };

/** The words `t()` has for a key, or null: `t()` itself answers a missing key with the key. */
export function known(key: string): string | null {
  const words = t(key);
  return words === key ? null : words;
}

/**
 * A stored code in words, or the plain "no words for this" (or `fallbackKey`'s words) with the
 * code kept aside: a caller shows it (CodedWords, codedText), never drops it.
 */
export function codeWords(prefix: string, code: string, fallbackKey = "research.exec.code.unknown"): Coded {
  const words = known(`${prefix}.${code}`);
  return words === null ? { words: t(fallbackKey), code } : { words, code: null };
}

/** A coded value as one line of text, for a place that takes a string: the code named after the words. */
export const codedText = (coded: Coded): string =>
  coded.code === null ? coded.words : `${coded.words} (${t("research.exec.code.technical")}: ${coded.code})`;

/** How well a Deep Research bundle is covered by evidence; a status this client does not know is undetermined. */
export const coverageWords = (status: string): string =>
  ({ GROUNDED: "Doložené podklady", PARTIAL: "Částečné pokrytí", INSUFFICIENT: "Nedostatek podkladů", NO_EVIDENCE: "Bez ověřených zjištění" })[status] ??
  "Pokrytí nelze určit";

/** A Deep Research step by name; an investigate track (`investigate/<track>`) names its track. */
export function deepStepLabel(nodeKey: string): string {
  const [base = "", track] = nodeKey.split("/");
  const name = known(`research.deep.steps.${base}`) ?? t("research.deep.steps.other");
  return track ? `${name} (${track})` : name;
}

/**
 * What a Deep Research step recorded against itself, in words, or null when it recorded nothing:
 * the wait's own detail first (`waitingDetail`: a recorded message, then a known reason), then a
 * failed attempt's message, then the bare waiting reason, worded where this client can.
 */
export function stepProblem(step: Pick<ResearchStep, "status" | "waiting_reason" | "error_message">): Coded | null {
  const waiting = waitingDetail(step);
  if (waiting !== null) return { words: waiting, code: null };
  if (step.error_message) return { words: step.error_message, code: null };
  if (step.waiting_reason) return codeWords("research.exec.wait", step.waiting_reason);
  return null;
}
