"use client";

import { useContext } from "react";

import { ResearchContext } from "./context";
import { type StudyFrame, useStudyFrame } from "./frame";

/**
 * The study these views are in: the research session's frame on a stage, the frame alone where
 * there is no session (project memory's read-only page, plans/project-memory-reuse.md M2a). The
 * result views below read nothing else, so they draw a run outside a study's working content.
 */
export function useFrame(): StudyFrame {
  const session = useContext(ResearchContext);
  const own = useStudyFrame();
  const frame = session?.frame ?? own;
  if (!frame) throw new Error("a research view outside a study frame");
  return frame;
}
