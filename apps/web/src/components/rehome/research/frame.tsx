"use client";

// The study a research frame is in (ADR 0015): resolved by the
// /app/clients/<client>/research/<study> layout through AIA's scope, then handed
// to the research screens. They never build a URL themselves -- `stepHref` does --
// and load and save the study's working content by the study's id alone, in AIA
// (ADR 0018): nothing the browser holds says where the content lives.

import { type ReactNode, createContext, useContext } from "react";

import type { StepKey } from "@/research/steps";

export type StudyFrame = {
  clientId: string;
  clientName: string;
  studyId: string;
  studyName: string;
  /** The stage the study was last opened on. */
  lastStage: StepKey | null;
  /** EDIT_STUDY on this study: a person who may only read never starts working content. */
  canEdit: boolean;
  /** The URL of one of this study's stages. */
  stepHref: (step: StepKey) => string;
  /** Remember the stage opened, for "continue where you left off". */
  onStage?: (step: StepKey) => void;
  /** Something the frame must say about the study as a whole. */
  notice?: string | null;
};

const Ctx = createContext<StudyFrame | null>(null);

export function StudyFrameProvider({ frame, children }: { frame: StudyFrame; children: ReactNode }) {
  return <Ctx.Provider value={frame}>{children}</Ctx.Provider>;
}

export function useStudyFrame(): StudyFrame | null {
  return useContext(Ctx);
}
