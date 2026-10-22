// What an AI proposal would change in the design the person has now
// (research-lane-redesign chunk 5): the lists of the research narrative and the
// comparable sets, item by item. It only reads; accepting stays one decision for the
// whole proposal (ResearchAgentJobs.accept records it once per job, ADR 0019 gate 1).

import type { Analysis } from "./store";

export type ListDiff = { key: string; label: string; added: string[]; removed: string[]; kept: number };
/** `key`: the set as design_items keys it -- its title, the second set of one title `<title>#2`. */
export type SetDiff = { key: string; title: string; status: "new" | "removed" | "changed" | "same"; added: string[]; removed: string[]; size: number };
export type ProposalDiff = { summary: { before: string; after: string } | null; lists: ListDiff[]; sets: SetDiff[]; changes: number };

const LISTS: [string, string][] = [
  ["objectives", "Cíle"],
  ["research_questions", "Výzkumné otázky"],
  ["hypotheses", "Hypotézy"],
];

export const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && !!x.trim()).map((x) => x.trim()) : []);
const objects = (v: unknown): Record<string, unknown>[] => (Array.isArray(v) ? v.filter((x): x is Record<string, unknown> => !!x && typeof x === "object") : []);
const key = (s: string) => s.toLocaleLowerCase("cs").replace(/\s+/g, " ");

/**
 * Each key as its list keys it: the second `a` is `a#2` (domain/design_items.py occurrence_keys).
 * Two entries of one key stay two, so neither side collapses them and loses one.
 */
export function occurrenceKeys(keys: readonly string[]): string[] {
  const used = new Set<string>();
  const counts = new Map<string, number>();
  return keys.map((k) => {
    let n = (counts.get(k) ?? 0) + 1;
    let candidate = n === 1 ? k : `${k}#${n}`;
    while (used.has(candidate)) { n += 1; candidate = `${k}#${n}`; }
    counts.set(k, n); used.add(candidate);
    return candidate;
  });
}

export function diffLists(before: readonly string[], after: readonly string[]): { added: string[]; removed: string[]; kept: number } {
  const kb = occurrenceKeys(before.map(key));
  const ka = occurrenceKeys(after.map(key));
  const b = new Set(kb);
  const a = new Set(ka);
  return {
    added: after.filter((_, i) => !b.has(ka[i])),
    removed: before.filter((_, i) => !a.has(kb[i])),
    kept: after.filter((_, i) => b.has(ka[i])).length,
  };
}

/** The proposal against the current plan; a field the proposal does not carry is not a change. */
export function proposalDiff(current: Analysis | null, proposal: Record<string, unknown>): ProposalDiff {
  const now = (current ?? {}) as Record<string, unknown>;
  const lists: ListDiff[] = [];
  for (const [k, label] of LISTS) {
    if (!Array.isArray(proposal[k])) continue;
    const d = diffLists(strings(now[k]), strings(proposal[k]));
    lists.push({ key: k, label, ...d });
  }
  const sets: SetDiff[] = [];
  if (Array.isArray(proposal.tracked_sets)) {
    // Keyed as design_items keys them: two sets of one title stay two (`<title>#2`), never one.
    const keyed = (list: Record<string, unknown>[]) => {
      const keys = occurrenceKeys(list.map((s) => key(String(s.title || ""))));
      return list.map((s, i) => [keys[i], s] as const);
    };
    const before = new Map(keyed(objects(now.tracked_sets)));
    const seen = new Set<string>();
    for (const [k, s] of keyed(objects(proposal.tracked_sets))) {
      const title = String(s.title || "Sada");
      seen.add(k);
      const old = before.get(k);
      const objs = strings(s.objects);
      if (!old) { sets.push({ key: k, title, status: "new", added: objs, removed: [], size: objs.length }); continue; }
      const d = diffLists(strings(old.objects), objs);
      sets.push({ key: k, title, status: d.added.length || d.removed.length ? "changed" : "same", added: d.added, removed: d.removed, size: objs.length });
    }
    for (const [k, s] of before) if (!seen.has(k)) sets.push({ key: k, title: String(s.title || "Sada"), status: "removed", added: [], removed: strings(s.objects), size: 0 });
  }
  const after = typeof proposal.problem_summary === "string" ? proposal.problem_summary.trim() : "";
  const before = typeof now.problem_summary === "string" ? now.problem_summary.trim() : "";
  const summary = after && after !== before ? { before, after } : null;
  const changes = (summary ? 1 : 0)
    + lists.reduce((n, l) => n + l.added.length + l.removed.length, 0)
    + sets.reduce((n, s) => n + (s.status === "new" || s.status === "removed" ? 1 : s.added.length + s.removed.length), 0);
  return { summary, lists, sets, changes };
}

/**
 * What accepting a questionnaire proposal does to the questionnaire the person has now
 * (productization PC6). The agent keeps every section that is not a question block or object
 * battery, and every library instrument, and replaces all the rest -- the person's own blocks --
 * with its own (domain/research_agents.py proposal_result). Accepting is one decision for the
 * whole proposal, so the review says before it what goes: each own question or battery item that
 * the proposal does not carry again (by its wording), what is new, and what is kept.
 */
export type QuestionnaireReplacement = { replaced: number; preserved: number; removed: string[]; added: string[]; kept: number };

const OWN = new Set(["questions", "object_battery"]);
const isOwn = (s: Record<string, unknown>): boolean => {
  const meta = (s.metadata && typeof s.metadata === "object" ? s.metadata : {}) as Record<string, unknown>;
  return OWN.has(String(s.type)) && !meta.standard_instrument && !meta.instrument_id;
};
const texts = (sections: Record<string, unknown>[]): string[] =>
  sections.flatMap((s) => [
    ...objects(s.questions).map((q) => String(q.text ?? "").trim()),
    ...strings(s.objects),
  ]).filter(Boolean);

export function questionnaireReplacement(current: { sections?: unknown }, proposed: { sections?: unknown }): QuestionnaireReplacement {
  const before = objects(current.sections);
  const own = before.filter(isOwn);
  const after = objects(proposed.sections).filter(isOwn);
  const d = diffLists(texts(own), texts(after));
  return { replaced: own.length, preserved: before.length - own.length, removed: d.removed, added: d.added, kept: d.kept };
}
