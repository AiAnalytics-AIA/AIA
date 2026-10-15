// How a client's Výzkumy and Simulace tables read (client-workspace C2): which filter
// a study's status falls under, the two orders, and what a study brought into the
// client's knowledge. Pure, so the rules are tested apart from the page.

import type { WorkspaceStudy } from "@/lib/api";

/** "current" is the default: everything not archived or cancelled. */
export type StudyFilter = "current" | "open" | "review" | "delivered" | "archived";
export const STUDY_FILTERS: readonly StudyFilter[] = ["current", "open", "review", "delivered", "archived"];

export type StudySort = "modified" | "name";
export const STUDY_SORTS: readonly StudySort[] = ["modified", "name"];

const CLOSED = new Set(["ARCHIVED", "CANCELLED"]);

/** The one narrow filter a status belongs to; an unknown status is "open", never hidden. */
export function narrowFilterOf(status: string): Exclude<StudyFilter, "current"> {
  if (status === "IN_REVIEW") return "review";
  if (status === "DELIVERED") return "delivered";
  if (CLOSED.has(status)) return "archived";
  return "open";
}

export function inFilter(study: Pick<WorkspaceStudy, "status">, filter: StudyFilter): boolean {
  if (filter === "current") return !CLOSED.has(study.status);
  return narrowFilterOf(study.status) === filter;
}

export function countByFilter(studies: readonly Pick<WorkspaceStudy, "status">[]): Record<StudyFilter, number> {
  const counts: Record<StudyFilter, number> = { current: 0, open: 0, review: 0, delivered: 0, archived: 0 };
  for (const s of studies) {
    counts[narrowFilterOf(s.status)] += 1;
    if (inFilter(s, "current")) counts.current += 1;
  }
  return counts;
}

/** Newest change first (a study with no time last), or by name in Czech order. Never mutates. */
export function sortStudies<T extends Pick<WorkspaceStudy, "name" | "modified_at">>(studies: readonly T[], sort: StudySort): T[] {
  const copy = [...studies];
  if (sort === "name") return copy.sort((a, b) => a.name.localeCompare(b.name, "cs", { sensitivity: "base" }));
  const at = (s: T) => (s.modified_at ? Date.parse(s.modified_at) : Number.NEGATIVE_INFINITY);
  return copy.sort((a, b) => at(b) - at(a));
}

/**
 * What a study brought into the client's knowledge: accepted and still waiting.
 * `null` when the API did not say (the caller may not read the client's knowledge):
 * unknown is not "nothing".
 */
export function brought(study: Pick<WorkspaceStudy, "knowledge">): { accepted: number; waiting: number } | null {
  const k = study.knowledge;
  if (!k) return null;
  return { accepted: k.approved, waiting: k.proposed };
}
