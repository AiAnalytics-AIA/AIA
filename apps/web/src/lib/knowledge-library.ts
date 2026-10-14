// How the client's knowledge library reads (client-workspace C4): which view asks the API
// for what, the "older than a year" rule, label colours, and the selection the bulk bar
// acts on. Pure, so the rules are tested apart from the page.

import { ApiError, type KnowledgeFiling, type KnowledgeItem, type LabelColour } from "@/lib/api";

/**
 * What the library shows: everything, items in no folder, items not changed for a year,
 * the proposals waiting on a person, or one folder (`folder:<id>`).
 */
export type LibraryView = "all" | "unfiled" | "old" | "review" | `folder:${string}`;

export const folderView = (folderId: string): LibraryView => `folder:${folderId}`;

export function folderOf(view: LibraryView): string | null {
  return view.startsWith("folder:") ? view.slice("folder:".length) : null;
}

/** The API's own filters for a view (and a label); "old" is decided here, "review" reads proposals. */
export function filingFor(view: LibraryView, label: string | null): KnowledgeFiling {
  const folder = folderOf(view);
  return {
    folder: folder ?? (view === "unfiled" ? "unfiled" : undefined),
    label: label ?? undefined,
  };
}

const YEAR_MS = 365 * 24 * 60 * 60 * 1000;

/**
 * Not changed for more than a year. An item with no date is not called old:
 * we do not know, and "old" would be a guess.
 */
export function olderThanAYear(item: Pick<KnowledgeItem, "modified_at">, now: number): boolean {
  if (!item.modified_at) return false;
  const at = Date.parse(item.modified_at);
  return Number.isFinite(at) && now - at > YEAR_MS;
}

export function shown<T extends Pick<KnowledgeItem, "modified_at">>(items: readonly T[], view: LibraryView, now: number): T[] {
  return view === "old" ? items.filter((i) => olderThanAYear(i, now)) : [...items];
}

/** The API returns at most this many items; a full page says so rather than looking complete. */
export const RESULT_CAP = 200;
export const atCap = (items: readonly unknown[]) => items.length >= RESULT_CAP;

/** Each label colour as a token utility: the wayfinding hues, never a status colour. */
export const LABEL_DOT: Record<LabelColour, string> = {
  BLUE: "bg-hue-blue",
  TEAL: "bg-hue-teal",
  GREEN: "bg-hue-green",
  ORANGE: "bg-hue-orange",
  VIOLET: "bg-hue-violet",
  SLATE: "bg-hue-slate",
};

/** Tick or untick one item; a new set every time. */
export function toggled(selected: ReadonlySet<string>, id: string): Set<string> {
  const next = new Set(selected);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Tick every shown item, or, when all are ticked already, none. Items not shown keep their tick. */
export function toggledAll(selected: ReadonlySet<string>, shownIds: readonly string[]): Set<string> {
  const next = new Set(selected);
  const all = shownIds.length > 0 && shownIds.every((id) => next.has(id));
  for (const id of shownIds) {
    if (all) next.delete(id);
    else next.add(id);
  }
  return next;
}

/** What the bulk bar acts on: the ticked items still shown, so nothing hidden moves unseen. */
export function actedOn(selected: ReadonlySet<string>, shownIds: readonly string[]): string[] {
  return shownIds.filter((id) => selected.has(id));
}

/** An edit refused because the item moved on (F-K1): the revision it was written from and the current one. */
export type StaleEdit = { base: number | null; current: number };

/** The API's `knowledge_proposal_stale` refusal read; anything else is not a stale edit. A missing base stays unknown. */
export function staleEdit(e: unknown): StaleEdit | null {
  if (!(e instanceof ApiError) || e.code !== "knowledge_proposal_stale") return null;
  const current = e.details.current_revision;
  if (typeof current !== "number") return null;
  const base = e.details.base_revision;
  return { base: typeof base === "number" ? base : null, current };
}
