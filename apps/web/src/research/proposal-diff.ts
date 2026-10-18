// What an AI proposal would change in the design the person has now
// (research-lane-redesign chunk 5): the lists of the research narrative and the
// comparable sets, item by item. It only reads; accepting stays one decision for the
// whole proposal (ResearchAgentJobs.accept records it once per job, ADR 0019 gate 1).

import type { Analysis } from "./store";

export type ListDiff = { key: string; label: string; added: string[]; removed: string[]; kept: number };
export type SetDiff = { title: string; status: "new" | "removed" | "changed" | "same"; added: string[]; removed: string[]; size: number };
export type ProposalDiff = { summary: { before: string; after: string } | null; lists: ListDiff[]; sets: SetDiff[]; changes: number };

const LISTS: [string, string][] = [
  ["objectives", "Cíle"],
  ["research_questions", "Výzkumné otázky"],
  ["hypotheses", "Hypotézy"],
];

const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && !!x.trim()).map((x) => x.trim()) : []);
const objects = (v: unknown): Record<string, unknown>[] => (Array.isArray(v) ? v.filter((x): x is Record<string, unknown> => !!x && typeof x === "object") : []);
const key = (s: string) => s.toLocaleLowerCase("cs").replace(/\s+/g, " ");

export function diffLists(before: readonly string[], after: readonly string[]): { added: string[]; removed: string[]; kept: number } {
  const b = new Set(before.map(key));
  const a = new Set(after.map(key));
  return {
    added: after.filter((x) => !b.has(key(x))),
    removed: before.filter((x) => !a.has(key(x))),
    kept: after.filter((x) => b.has(key(x))).length,
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
    const before = new Map(objects(now.tracked_sets).map((s) => [key(String(s.title || "")), s]));
    const seen = new Set<string>();
    for (const s of objects(proposal.tracked_sets)) {
      const title = String(s.title || "Sada");
      const k = key(title);
      seen.add(k);
      const old = before.get(k);
      const objs = strings(s.objects);
      if (!old) { sets.push({ title, status: "new", added: objs, removed: [], size: objs.length }); continue; }
      const d = diffLists(strings(old.objects), objs);
      sets.push({ title, status: d.added.length || d.removed.length ? "changed" : "same", added: d.added, removed: d.removed, size: objs.length });
    }
    for (const [k, s] of before) if (!seen.has(k)) sets.push({ title: String(s.title || "Sada"), status: "removed", added: [], removed: strings(s.objects), size: 0 });
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
