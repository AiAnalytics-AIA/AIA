// The workbench at every width (research-lead-workbench chunk 26a): the breakpoints, the drawer's
// states and the one Escape order.
import { describe, expect, it } from "vitest";

import {
  CLOSED,
  DRAWER_LAYOUT_MIN_PX,
  SPLIT_LAYOUT_MIN_PX,
  conversationShown,
  drawerForLayout,
  isModal,
  layoutFor,
  nextDrawer,
  onEscape,
  type DrawerState,
  type WorkbenchLayout,
} from "./workbench-layout";

const OPEN: DrawerState = { kind: "open" };
const PICKING: DrawerState = { kind: "picking" };
const PEEK: DrawerState = { kind: "peek", target: "qedit_q1" };
const COMPACT: WorkbenchLayout[] = ["drawer", "sheet"];

describe("layoutFor", () => {
  it("serves the split from 1100 px, the drawer from 768, the sheet below", () => {
    expect(SPLIT_LAYOUT_MIN_PX).toBe(1100);
    expect(DRAWER_LAYOUT_MIN_PX).toBe(768);
    expect(layoutFor(1440)).toBe("split");
    expect(layoutFor(1100)).toBe("split");
    expect(layoutFor(1099)).toBe("drawer");
    expect(layoutFor(768)).toBe("drawer");
    expect(layoutFor(767)).toBe("sheet");
    expect(layoutFor(390)).toBe("sheet");
    expect(layoutFor(0)).toBe("sheet");
  });

  it("reads a width not known as the split, as the server renders it", () => {
    expect(layoutFor(null)).toBe("split");
    expect(layoutFor(undefined)).toBe("split");
    expect(layoutFor(Number.NaN)).toBe("split");
  });
});

describe("visibility", () => {
  it("always shows the conversation in the split, pointing included", () => {
    for (const s of [CLOSED, OPEN, PEEK, PICKING]) {
      expect(conversationShown("split", s)).toBe(true);
      expect(isModal("split", s)).toBe(false);
    }
  });

  it("shows it in a compact layout only when open, and then as a modal dialog", () => {
    for (const layout of COMPACT) {
      expect(conversationShown(layout, OPEN)).toBe(true);
      expect(isModal(layout, OPEN)).toBe(true);
      for (const s of [CLOSED, PEEK, PICKING]) {
        expect(conversationShown(layout, s)).toBe(false);
        expect(isModal(layout, s)).toBe(false);
      }
    }
  });
});

describe("nextDrawer", () => {
  it("opens from the launcher at the composer and closes back to the launcher", () => {
    for (const layout of COMPACT) {
      expect(nextDrawer(CLOSED, { type: "open" }, layout)).toEqual({ state: OPEN, focus: { to: "composer" } });
      expect(nextDrawer(OPEN, { type: "close" }, layout)).toEqual({ state: CLOSED, focus: { to: "launcher" } });
    }
  });

  it("steps aside to the artifact a Lead view op targets, focus on the target, and comes back on Zpět", () => {
    for (const layout of COMPACT) {
      const peek = nextDrawer(OPEN, { type: "view", target: "qedit_q1" }, layout);
      expect(peek).toEqual({ state: PEEK, focus: { to: "target", target: "qedit_q1" } });
      expect(nextDrawer(peek.state, { type: "back" }, layout)).toEqual({ state: OPEN, focus: { to: "composer" } });
    }
  });

  it("in the split, a view op only moves focus to the target", () => {
    expect(nextDrawer(CLOSED, { type: "view", target: "brief" }, "split")).toEqual({ state: CLOSED, focus: { to: "target", target: "brief" } });
  });

  it("hides the conversation while @ is armed and reopens it at the composer once an element is chosen", () => {
    for (const layout of COMPACT) {
      const armed = nextDrawer(OPEN, { type: "pick" }, layout);
      expect(armed).toEqual({ state: PICKING, focus: null });
      expect(nextDrawer(armed.state, { type: "picked" }, layout)).toEqual({ state: OPEN, focus: { to: "composer" } });
    }
    expect(nextDrawer(PICKING, { type: "picked" }, "split")).toEqual({ state: CLOSED, focus: { to: "composer" } });
  });

  it("ignores Zpět outside a peek and a choice outside pointing", () => {
    for (const s of [CLOSED, OPEN, PICKING]) expect(nextDrawer(s, { type: "back" }, "drawer")).toEqual({ state: s, focus: null });
    for (const s of [CLOSED, OPEN, PEEK]) expect(nextDrawer(s, { type: "picked" }, "drawer")).toEqual({ state: s, focus: null });
  });
});

describe("onEscape", () => {
  const states = [CLOSED, OPEN, PEEK, PICKING];
  const layouts: WorkbenchLayout[] = ["split", "drawer", "sheet"];

  it("leaves a key a handler already took alone, whatever is open", () => {
    for (const layout of layouts) for (const s of states) {
      expect(onEscape(s, { handled: true, askDialogOpen: true, inspectorOpen: true }, layout)).toEqual({ action: "none", state: s, focus: null });
    }
  });

  it("closes an open AskDialog first, leaving the drawer as it is", () => {
    for (const layout of layouts) for (const s of states) {
      expect(onEscape(s, { askDialogOpen: true, inspectorOpen: true }, layout)).toEqual({ action: "ask_dialog", state: s, focus: null });
    }
  });

  it("then disarms pointing, before the inspector, reopening the conversation at the composer", () => {
    for (const layout of COMPACT) {
      expect(onEscape(PICKING, { inspectorOpen: true }, layout)).toEqual({ action: "disarm_picking", state: OPEN, focus: { to: "composer" } });
    }
    expect(onEscape(PICKING, {}, "split")).toEqual({ action: "disarm_picking", state: CLOSED, focus: { to: "composer" } });
  });

  it("then closes the inspector, before the drawer", () => {
    for (const layout of layouts) for (const s of [CLOSED, OPEN, PEEK]) {
      expect(onEscape(s, { inspectorOpen: true }, layout)).toEqual({ action: "inspector", state: s, focus: null });
    }
  });

  it("then closes the drawer and returns focus to the launcher", () => {
    for (const layout of COMPACT) {
      expect(onEscape(OPEN, {}, layout)).toEqual({ action: "drawer", state: CLOSED, focus: { to: "launcher" } });
    }
  });

  it("does nothing with nothing open: a closed drawer, a peek, the split", () => {
    for (const layout of COMPACT) for (const s of [CLOSED, PEEK]) expect(onEscape(s, {}, layout)).toEqual({ action: "none", state: s, focus: null });
    for (const s of [CLOSED, OPEN, PEEK]) expect(onEscape(s, {}, "split").action).toBe("none");
  });
});

describe("drawerForLayout", () => {
  it("closes an open drawer or a peek on entering the split, and keeps @ armed", () => {
    expect(drawerForLayout(OPEN, "split")).toEqual(CLOSED);
    expect(drawerForLayout(PEEK, "split")).toEqual(CLOSED);
    expect(drawerForLayout(PICKING, "split")).toEqual(PICKING);
  });

  it("keeps the state between compact layouts and on entering one", () => {
    for (const s of [CLOSED, OPEN, PEEK, PICKING]) {
      expect(drawerForLayout(s, "drawer")).toEqual(s);
      expect(drawerForLayout(s, "sheet")).toEqual(s);
    }
  });
});
