"use client";

// The research flow's shared state for one screen tree: the working-content store,
// the research template, and the one AI job that may run at a time (ADR 0014,
// area A4; ADR 0018).

import { createContext, useCallback, useContext, useState, useSyncExternalStore } from "react";

import type { ResearchJobKey } from "@/lib/research-agent-jobs";
import type { JobUpdate } from "@/research/jobs";
import type { Template } from "@/research/model";
import type { ResearchState, ResearchStore } from "@/research/store";
import type { StepKey } from "@/research/steps";
import type { StudyFrame } from "./frame";
import type { AdviceAction } from "./ResearchAssistance";

export type RunJob = (
  endpoint: ResearchJobKey,
  payload: Record<string, unknown>,
  opts: { title: string; warnMs?: number; model?: string },
) => Promise<unknown>;

export type ResearchContextValue = {
  store: ResearchStore;
  /** The research template: what a new study starts from, and what a stored one is completed with. */
  template: Template;
  runJob: RunJob;
  /** Go on with the same job once a person lifted the study's budget for it (CR-2): never a new job. */
  continueJob: (jobId: string) => Promise<unknown>;
  /**
   * A stage's own budget wait shown in place claims its job, so the screen's list of waiting jobs
   * does not offer a second lift for it; the returned function releases the claim.
   */
  claimWait: (jobId: string) => () => void;
  job: JobUpdate | null;
  toast: (message: string) => void;
  /** confirm() and prompt(), with the classic words, as the rebuilt interface's dialog. */
  confirm: (message: string) => Promise<boolean>;
  prompt: (message: string, initial?: string) => Promise<string | null>;
  /**
   * The one predicate every stage reads for its own AI starts ("Navrhnout", the brief's analysis):
   * true where the Research Lead owns them (the workbench layout, plan research-lead-workbench D15),
   * so no stage shows one. Absent or false: the stage keeps its own (the classic layout, which has
   * no Lead until chunk 26; that chunk removes this predicate). Spuštění's Start shows either way.
   */
  leadOwnsAiStarts?: boolean;
  /** Contextual help opens an editor; prefilling a question never sends it. */
  askAssistance?: (action: AdviceAction, question?: string) => void;
  /** The project session's page memory: what the classic interface keeps in globals, never saved. */
  memory: Map<string, unknown>;
  /** The URL of one of this study's stages (ADR 0015): steps never build one themselves. */
  stepHref: (step: StepKey) => string;
  /** The AIA study this screen is in: its id, and whether the person may edit it (ADR 0016). */
  frame: StudyFrame;
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
