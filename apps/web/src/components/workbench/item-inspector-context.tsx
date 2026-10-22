"use client";

// How a stage screen opens an item in the workbench's item inspector (research-lead-workbench
// chunk 2, ADR 0026 D3): a person clicks a finding, a cited number or a map object, and its detail
// opens in the drawer over the artifact, the same drawer the Lead's `inspect` will open. Outside
// the workbench (the classic layout) there is no drawer: the hook answers null and the screen
// keeps its own behaviour (scrolling to the item).

import { createContext, type ReactNode, useContext } from "react";

import type { InspectorEntry } from "@/lib/inspector-stack";
import { parseAiaId } from "@/lib/workbench-artifacts";

/** An opened item's target: its kind, id and owning stage. */
export type AiaTarget = NonNullable<ReturnType<typeof parseAiaId>>;

export type ItemInspectorApi = {
  /** Open `entry` over the item on top. False, and nothing opened, for an id outside the
   *  contract's grammar (`parseAiaId`). `body`: the detail the opening screen already holds (the
   *  report's claim and its evidence), drawn instead of the kind's body (ItemInspectBody). */
  open: (entry: InspectorEntry, body?: () => ReactNode) => boolean;
  /** Drop every entry whose id starts with `prefix` (a screen whose items stopped being true: the
   *  report's claims once the person switched to the other document); the drawer shuts when none
   *  is left. */
  closeWhere: (prefix: string) => void;
};

export const ItemInspectorContext = createContext<ItemInspectorApi | null>(null);

/** The workbench's item inspector, or null where there is none. */
export const useItemInspector = (): ItemInspectorApi | null => useContext(ItemInspectorContext);

/** A drawer body for one kind of item: the stage that owns the kind draws its detail. */
export type InspectBody = (target: AiaTarget) => ReactNode;

/** The parsed target of an opened entry, or null for one outside the grammar. */
export const inspectedTarget = (entry: InspectorEntry): AiaTarget | null => parseAiaId(entry.id);
