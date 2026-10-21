// A short name typed where the thing will appear (input-interactions I5, I9): the pure part of
// InlineCreateRow. The rules are the server's for a folder's or a label's name
// (packages/aia_core/src/aia_core/domain/knowledge.py organizer_name / organizer_key): trimmed,
// inner whitespace collapsed, at most 80 characters, unique within the list regardless of case
// and spacing (accents count). The row says so as the person types; the server still decides
// (409 name_taken), and its refusal is said at the same row.

import { tv, t } from "@/i18n/t";

/** ORGANIZER_NAME_MAX: the longest folder or label name the server keeps. */
export const NAME_MAX = 80;

export type NameProblem = { kind: "empty" } | { kind: "tooLong"; max: number } | { kind: "taken"; name: string };

/** A name as the server stores it: trimmed, inner whitespace collapsed to one space. */
export function cleanName(raw: string): string {
  return raw.split(/\s+/).filter(Boolean).join(" ");
}

/**
 * What makes two names the same: case and spacing do not count, accents do. The server folds
 * with Python's casefold(); toLocaleLowerCase("cs") agrees for every Czech letter (it differs
 * only on letters such as "ß", which the server then refuses as name_taken, said at the row).
 */
export function nameKey(raw: string): string {
  return cleanName(raw).toLocaleLowerCase("cs");
}

/** Why `raw` cannot be created beside `existing` (`except`: the name being renamed), or null. */
export function nameProblem(raw: string, existing: readonly string[], max = NAME_MAX, except?: string): NameProblem | null {
  const name = cleanName(raw);
  if (!name) return { kind: "empty" };
  if (name.length > max) return { kind: "tooLong", max };
  const key = nameKey(name);
  const own = except === undefined ? null : nameKey(except);
  const clash = existing.find((e) => nameKey(e) === key && nameKey(e) !== own);
  if (clash !== undefined) return { kind: "taken", name: cleanName(clash) };
  return null;
}

export function nameProblemWords(problem: NameProblem): string {
  switch (problem.kind) {
    case "empty":
      return t("input.name.empty");
    case "tooLong":
      return tv("input.name.tooLong", { max: problem.max });
    case "taken":
      return tv("input.name.taken", { name: problem.name });
  }
}
