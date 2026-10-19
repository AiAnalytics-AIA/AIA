// The item inspector's back stack (research-lead-workbench chunk 2, ADR 0026 D3): an
// item opened in the artifact -- a question, a measure, a map object -- opens its
// detail in a drawer; opening another item from there pushes it, Back returns, Close
// empties the stack. The stack belongs to the stage it was opened on: moving to
// another stage starts it empty. It is display state only and changes nothing stored.
// The stage's readiness (InspectorSlot) is not part of it.

/** One opened item: its `data-aia` id and the words its drawer is headed with. */
export type InspectorEntry = { id: string; title: string; sub?: string };
export type InspectorStack = { stage: string; entries: readonly InspectorEntry[] };

export const emptyStack = (stage: string): InspectorStack => ({ stage, entries: [] });

/** The item the drawer shows; null: closed. */
export function topEntry(stack: InspectorStack): InspectorEntry | null {
  return stack.entries[stack.entries.length - 1] ?? null;
}

/** Open an item over the current one; the item already on top is not opened twice. */
export function openEntry(stack: InspectorStack, entry: InspectorEntry): InspectorStack {
  const top = topEntry(stack);
  if (top && top.id === entry.id) return top.title === entry.title && top.sub === entry.sub ? stack : { ...stack, entries: [...stack.entries.slice(0, -1), entry] };
  return { ...stack, entries: [...stack.entries, entry] };
}

/** Back to the item it was opened from; from the first item, the drawer closes. */
export function backEntry(stack: InspectorStack): InspectorStack {
  return stack.entries.length ? { ...stack, entries: stack.entries.slice(0, -1) } : stack;
}

export function closeStack(stack: InspectorStack): InspectorStack {
  return stack.entries.length ? { ...stack, entries: [] } : stack;
}

/** The stack on `stage`: the same one while the stage stays, empty on another. */
export function onStage(stack: InspectorStack, stage: string): InspectorStack {
  return stack.stage === stage ? stack : emptyStack(stage);
}
