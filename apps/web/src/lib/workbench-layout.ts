// The research workbench at every width (research-lead-workbench chunk 26a, D20, D21): the pure
// rules, no component reads them yet. From 1100 px the split serves, as the prototype draws it
// (prototypes/research-lead-v2/src/styles/app.css:500-504 @ 095a3e68). Between 768 and 1099 px
// the artifact takes the width and the conversation opens as a side drawer over it; under 768 px
// it opens as a full-screen sheet. The drawer and the sheet are the same LeadPane, kept mounted
// and hidden, so only these states change, never what is mounted.
//
// Escape has one order, fixed here so no two handlers both act on one key: an open AskDialog
// first, then pointing ("@"), then the item inspector or the readiness overlay, then the drawer.
// A key a handler already took (a busy turn's stop in the composer, chunk 29) is never re-read.

/** The narrowest width the split serves at: the prototype's rule. */
export const SPLIT_LAYOUT_MIN_PX = 1100;
/** The narrowest width the side drawer serves at; below it, the full-screen sheet. */
export const DRAWER_LAYOUT_MIN_PX = 768;

/** split: conversation and artifact side by side; drawer: a side drawer over the artifact; sheet: a full-screen sheet. */
export type WorkbenchLayout = "split" | "drawer" | "sheet";

/**
 * The layout a viewport width takes. A width not known (the server's render, a missing measure)
 * is the split, as the workbench renders on the server today, until the browser measures.
 */
export function layoutFor(width: number | null | undefined): WorkbenchLayout {
  if (width == null || !Number.isFinite(width)) return "split";
  if (width >= SPLIT_LAYOUT_MIN_PX) return "split";
  if (width >= DRAWER_LAYOUT_MIN_PX) return "drawer";
  return "sheet";
}

/** The drawer and the sheet open over the artifact; the split has no overlay. */
export const isCompact = (layout: WorkbenchLayout): boolean => layout !== "split";

/**
 * Where the conversation stands.
 * - closed: hidden (compact) or simply shown (split, where it is always beside the artifact);
 * - open: shown over the artifact (compact);
 * - peek: hidden while the person looks at the artifact a Lead view op targeted ("Zpět k Vedoucímu");
 * - picking: "@" armed, the conversation hidden until an element is chosen or Escape disarms it.
 */
export type DrawerState =
  | { kind: "closed" }
  | { kind: "open" }
  | { kind: "peek"; target: string }
  | { kind: "picking" };

export const CLOSED: DrawerState = { kind: "closed" };

/** Where focus goes after a change: the launcher, the composer, an artifact element, or nowhere new. */
export type FocusTarget = { to: "launcher" } | { to: "composer" } | { to: "target"; target: string } | null;

export type DrawerEvent =
  | { type: "open" } // the launcher
  | { type: "close" } // Zavřít
  | { type: "view"; target: string } // a finished turn's open_stage or focus
  | { type: "back" } // "Zpět k Vedoucímu" from a peek
  | { type: "pick" } // "@" armed
  | { type: "picked" }; // an element chosen while armed

export type DrawerStep = { state: DrawerState; focus: FocusTarget };

/** Whether the conversation is visible: always in the split, pointing included; only when open in a compact layout. */
export function conversationShown(layout: WorkbenchLayout, state: DrawerState): boolean {
  return !isCompact(layout) || state.kind === "open";
}

/** Whether the conversation is a modal dialog now: open over the artifact in a compact layout. */
export function isModal(layout: WorkbenchLayout, state: DrawerState): boolean {
  return isCompact(layout) && state.kind === "open";
}

/** The next state for an event. In the split the conversation never hides, so only pointing and focus move. */
export function nextDrawer(state: DrawerState, event: DrawerEvent, layout: WorkbenchLayout): DrawerStep {
  const compact = isCompact(layout);
  switch (event.type) {
    case "open":
      return { state: compact ? { kind: "open" } : CLOSED, focus: { to: "composer" } };
    case "close":
      return { state: CLOSED, focus: compact ? { to: "launcher" } : null };
    case "view":
      // The drawer steps aside so the person sees what the Lead pointed at, and focus goes there.
      return { state: compact ? { kind: "peek", target: event.target } : CLOSED, focus: { to: "target", target: event.target } };
    case "back":
      if (state.kind !== "peek") return { state, focus: null };
      return { state: compact ? { kind: "open" } : CLOSED, focus: { to: "composer" } };
    case "pick":
      return { state: { kind: "picking" }, focus: null };
    case "picked":
      if (state.kind !== "picking") return { state, focus: null };
      return { state: compact ? { kind: "open" } : CLOSED, focus: { to: "composer" } };
  }
}

/** What else is open when Escape is pressed. `handled`: a handler already took the key (defaultPrevented). */
export type EscapeContext = { handled?: boolean; askDialogOpen?: boolean; inspectorOpen?: boolean };

/** Which layer an Escape closes, in the fixed order; none: the key is not the workbench's and is left alone. */
export type EscapeAction = "none" | "ask_dialog" | "disarm_picking" | "inspector" | "drawer";

export type EscapeStep = DrawerStep & { action: EscapeAction };

/**
 * One Escape. The AskDialog and the inspector close themselves and return focus to what opened
 * them, so the drawer's state is left as it is; disarming "@" reopens the conversation at the
 * composer; closing the drawer returns focus to the launcher. A peek has nothing open to close.
 */
export function onEscape(state: DrawerState, context: EscapeContext, layout: WorkbenchLayout): EscapeStep {
  if (context.handled) return { action: "none", state, focus: null };
  if (context.askDialogOpen) return { action: "ask_dialog", state, focus: null };
  if (state.kind === "picking") {
    return { action: "disarm_picking", state: isCompact(layout) ? { kind: "open" } : CLOSED, focus: { to: "composer" } };
  }
  if (context.inspectorOpen) return { action: "inspector", state, focus: null };
  if (isCompact(layout) && state.kind === "open") return { action: "drawer", state: CLOSED, focus: { to: "launcher" } };
  return { action: "none", state, focus: null };
}

/**
 * The state after the layout changes. The split has no drawer and no "Zpět k Vedoucímu", so an
 * open drawer or a peek is closed there; "@" stays armed in every layout. Entering a compact
 * layout keeps the state: from the split it is closed, the artifact taking the width (D21).
 */
export function drawerForLayout(state: DrawerState, layout: WorkbenchLayout): DrawerState {
  if (!isCompact(layout) && (state.kind === "open" || state.kind === "peek")) return CLOSED;
  return state;
}
