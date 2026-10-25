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
  /**
   * May change the study and start work on it now (the API's `can_edit`): false for a person who
   * may only read, and on a delivered, archived or cancelled study, which accepts no new work.
   */
  canEdit: boolean;
  /**
   * May read, download and approve what the study holds, and stop what runs (the API's
   * `can_review`): what a closed study still allows. Defaults to `canEdit` where a frame does
   * not say (a past study read from project memory offers neither).
   */
  canReview?: boolean;
  /** Why the study accepts no new work, when it does not: its status, and when it was delivered. */
  closed?: { status: string; deliveredAt: string | null } | null;
  /** The study's status, where it may be changed here (StudyStatusMenu); absent on a past study read
   *  from project memory, which offers no change. */
  status?: string;
  /** Reads the study again after its status changed, without leaving the stage. */
  refreshStudy?: () => Promise<void>;
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

/** What a closed study still allows: read, download, approve, stop. A frame that does not say follows `canEdit`. */
export const canReview = (frame: Pick<StudyFrame, "canEdit" | "canReview">): boolean => frame.canReview ?? frame.canEdit;
