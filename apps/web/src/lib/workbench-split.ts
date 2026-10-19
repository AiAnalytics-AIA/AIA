// The research workbench's split (research-lead-workbench chunk 1, ADR 0026): the
// conversation on the left, the stage's artifact on the right. The bounds are the
// prototype's (prototypes/research-lead-v2/src/components/Split.tsx @ 9b50963f):
// the left pane between 28 and 62 %, moved 2 % per arrow key, Home, Enter or a
// double-click back to 40 %. A focus mode widens one pane for a while and never
// touches the width the person chose; that width is kept per browser, and a
// browser that keeps nothing (a private window, blocked storage) gets the default.

export const SPLIT_MIN = 28;
export const SPLIT_MAX = 62;
export const SPLIT_STEP = 2;
export const SPLIT_DEFAULT = 40;
/** The conversation's width while it has the focus: wider than a person may set it. */
export const CONVERSATION_FOCUS = 68;
export const SPLIT_STORAGE_KEY = "aia.workbench.split";

/** split: both panes at the person's width; artifact: the conversation a rail; conversation: the conversation at 68 %. */
export type FocusMode = "split" | "artifact" | "conversation";

/** A width within the bounds; anything that is not a finite number is the default, never a bound. */
export function clampSplit(value: number): number {
  if (!Number.isFinite(value)) return SPLIT_DEFAULT;
  return Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, value));
}

/** The width a pointer at `clientX` sets, to a tenth of a per cent; a box with no width moves nothing. */
export function splitFromPointer(clientX: number, box: { left: number; width: number }, current: number): number {
  if (!(box.width > 0)) return current;
  return clampSplit(Math.round(((clientX - box.left) / box.width) * 1000) / 10);
}

/** The width a key on the separator sets; null: the key is not the separator's. */
export function splitFromKey(current: number, key: string): number | null {
  if (key === "ArrowLeft") return clampSplit(current - SPLIT_STEP);
  if (key === "ArrowRight") return clampSplit(current + SPLIT_STEP);
  if (key === "Home" || key === "Enter") return SPLIT_DEFAULT;
  return null;
}

/** The conversation's width in a mode; null: it is a rail. The person's width is read, never changed. */
export function leftWidth(split: number, mode: FocusMode): number | null {
  if (mode === "artifact") return null;
  if (mode === "conversation") return CONVERSATION_FOCUS;
  return clampSplit(split);
}

type ReadStore = Pick<Storage, "getItem">;
type WriteStore = Pick<Storage, "setItem">;

/** The width this browser kept, or the default: unreadable storage and a value out of shape are the default. */
export function readSplit(storage: ReadStore | null | undefined): number {
  try {
    const raw = storage?.getItem(SPLIT_STORAGE_KEY);
    if (raw == null || raw.trim() === "") return SPLIT_DEFAULT;
    return clampSplit(Number(raw));
  } catch {
    return SPLIT_DEFAULT;
  }
}

/** Keep the width for this browser; storage that refuses keeps nothing and breaks nothing. */
export function writeSplit(storage: WriteStore | null | undefined, value: number): void {
  try {
    storage?.setItem(SPLIT_STORAGE_KEY, String(clampSplit(value)));
  } catch {
    // Nothing kept: the next visit starts at the default.
  }
}
