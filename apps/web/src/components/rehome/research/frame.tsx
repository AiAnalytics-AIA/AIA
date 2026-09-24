"use client";

// The study a research frame is in (ADR 0015): resolved by the
// /app/clients/<client>/research/<study> layout through AIA's scope, then handed
// to the research screens. They never build a URL themselves -- `stepHref` does --
// and never decide which unit project to load: that comes from the study's AIA
// binding (OI-58), not from the browser.

import { type ReactNode, createContext, useContext } from "react";

import type { StepKey } from "@/unit/research/steps";

export type StudyFrame = {
  clientId: string;
  clientName: string;
  studyId: string;
  studyName: string;
  /** The unit project holding the working content, from the study's AIA binding; null until the first save. */
  unitProjectId: string | null;
  /** The stage the study was last opened on. */
  lastStage: StepKey | null;
  /** EDIT_STUDY on this study: a person who may only read never starts working content. */
  canEdit: boolean;
  /** The URL of one of this study's stages. */
  stepHref: (step: StepKey) => string;
  /** A new study's first save gave the unit project its id: bind it to the study, once. */
  onIdAssigned?: (unitProjectId: string) => void;
  /** Remember the stage opened, for "continue where you left off". */
  onStage?: (step: StepKey) => void;
  /** Something the frame must say, e.g. that the binding failed. */
  notice?: string | null;
};

const Ctx = createContext<StudyFrame | null>(null);

export function StudyFrameProvider({ frame, children }: { frame: StudyFrame; children: ReactNode }) {
  return <Ctx.Provider value={frame}>{children}</Ctx.Provider>;
}

export function useStudyFrame(): StudyFrame | null {
  return useContext(Ctx);
}
