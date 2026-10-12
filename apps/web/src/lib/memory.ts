// How a project-memory search reads (plans/project-memory-reuse.md M1d). The server decides
// what matches (one client, every word, accent-folded); this says when a query is worth
// sending and how a hit explains itself.

import type { MemoryHit, StudyKind } from "./api";

/** The server refuses a shorter query (MIN_QUERY_LENGTH); the page does not send one. */
export const MIN_QUERY = 2;

/** The query to send, or null while it is too short to say anything. */
export function sendable(q: string): string | null {
  const trimmed = q.trim();
  return trimmed.length >= MIN_QUERY ? trimmed : null;
}

/** The hits of one kind: Výzkumy shows research, the memory page shows every kind. */
export function ofKind(hits: MemoryHit[], kind: StudyKind | null): MemoryHit[] {
  return kind ? hits.filter((h) => h.kind === kind) : hits;
}

/** What a hit says matched, field by field, without repeating the study's own name. */
export function evidence(hit: MemoryHit): { field: MemoryHit["matches"][number]["field"]; text: string }[] {
  return hit.matches.filter((m) => m.field !== "name").flatMap((m) => m.texts.map((text) => ({ field: m.field, text })));
}
