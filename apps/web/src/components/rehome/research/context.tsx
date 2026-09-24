"use client";

// The research flow's shared state for one screen tree: the project store, the
// bootstrap, and the one AI job that may run at a time (ADR 0014, area A4).

import { createContext, useContext, useSyncExternalStore } from "react";

import type { BootInfo } from "@/unit/boot";
import type { JobUpdate } from "@/unit/research/jobs";
import type { ResearchState, ResearchStore } from "@/unit/research/store";
import type { UnitRouteKey } from "@/unit/routes";

export type RunJob = (
  endpoint: UnitRouteKey,
  payload: Record<string, unknown>,
  opts: { title: string; warnMs?: number; model?: string },
) => Promise<unknown>;

export type ResearchContextValue = {
  store: ResearchStore;
  boot: BootInfo;
  runJob: RunJob;
  job: JobUpdate | null;
  toast: (message: string) => void;
};

export const ResearchContext = createContext<ResearchContextValue | null>(null);

export function useResearch(): ResearchContextValue & { state: ResearchState } {
  const ctx = useContext(ResearchContext);
  if (!ctx) throw new Error("useResearch outside a research screen");
  const state = useSyncExternalStore(ctx.store.subscribe, ctx.store.get, ctx.store.get);
  return { ...ctx, state };
}
