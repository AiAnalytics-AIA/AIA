"use client";

// The research flow's shared state for one screen tree: the project store, the
// bootstrap, and the one AI job that may run at a time (ADR 0014, area A4).

import { createContext, useCallback, useContext, useState, useSyncExternalStore } from "react";

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
  /** confirm() and prompt(), with the classic words, as the rebuilt interface's dialog. */
  confirm: (message: string) => Promise<boolean>;
  prompt: (message: string, initial?: string) => Promise<string | null>;
  /** The project session's page memory: what the classic interface keeps in globals, never saved. */
  memory: Map<string, unknown>;
};

export const ResearchContext = createContext<ResearchContextValue | null>(null);

export function useResearch(): ResearchContextValue & { state: ResearchState } {
  const ctx = useContext(ResearchContext);
  if (!ctx) throw new Error("useResearch outside a research screen");
  const state = useSyncExternalStore(ctx.store.subscribe, ctx.store.get, ctx.store.get);
  return { ...ctx, state };
}

/**
 * A value kept for the project session, as the classic interface keeps a page
 * global (AUDIENCE_PREVIEW, PERSONA_AI_SUGGESTION): it survives moving between
 * steps, is never saved, and is gone on reload.
 */
export function useSessionState<T>(key: string, initial: T): [T, (v: T) => void] {
  const { memory } = useResearch();
  const [value, setValue] = useState<T>(() => (memory.has(key) ? (memory.get(key) as T) : initial));
  const set = useCallback(
    (v: T) => {
      memory.set(key, v);
      setValue(v);
    },
    [memory, key],
  );
  return [value, set];
}
