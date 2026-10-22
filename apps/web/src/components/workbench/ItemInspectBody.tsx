"use client";

// What the item inspector draws for an opened item. A kind whose stage has a body of its own is
// drawn by it (BODIES); any other shows what was opened and a way to it on the page, never a
// detail it does not have. Stage owners add their kinds here.

import type { ReactNode } from "react";

import type { InspectorEntry } from "@/lib/inspector-stack";
import { focusSelector, targetLabel } from "@/lib/lead";
import type { TargetKind } from "@/lib/workbench-artifacts";
import { type InspectBody, inspectedTarget } from "./item-inspector-context";

/** The drawer bodies by kind. A `module` stays on the page: its chapter is the page itself. */
export const BODIES: Partial<Record<TargetKind, InspectBody>> = {};

/** Show the opened item on the page: scrolled to and focused, as the Lead's focus does. */
export function showOnPage(id: string, root: ParentNode = document): boolean {
  const el = (root.querySelector("#artbody") ?? root).querySelector(focusSelector(id));
  if (!(el instanceof HTMLElement)) return false;
  el.scrollIntoView({ block: "center" });
  if (!el.hasAttribute("tabindex") && el.tabIndex < 0) el.setAttribute("tabindex", "-1");
  el.focus();
  return true;
}

export function ItemInspectBody({ entry }: { entry: InspectorEntry }): ReactNode {
  const target = inspectedTarget(entry);
  const body = target ? BODIES[target.kind] : undefined;
  if (target && body) return body(target);
  return (
    <div data-inspect-fallback>
      <p>{targetLabel(entry.id)}</p>
      <p className="muted">Podrobnosti této položky se zde zatím nezobrazují.</p>
      <button type="button" className="btn btn--sm" onClick={() => showOnPage(entry.id)}>Ukázat na stránce</button>
    </div>
  );
}
