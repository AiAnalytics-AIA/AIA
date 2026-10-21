"use client";

// Where a stage offered its own AI start, the workbench says where that work is asked for now: the
// Research Lead's conversation (plan research-lead-workbench D15). Nothing here starts anything.

import { useContext } from "react";

import { ResearchContext } from "./context";

/**
 * Whether the Research Lead owns this layout's AI starts (ResearchContext.leadOwnsAiStarts): true in
 * the workbench, where a stage shows no start of its own; absent or false, the stage keeps its own.
 */
export function useLeadOwnsAiStarts(): boolean {
  return useContext(ResearchContext)?.leadOwnsAiStarts === true;
}

export function AskLead({ what, className = "" }: { what: string; className?: string }) {
  return (
    <p data-ask-lead className={`text-xs leading-5 text-ink-muted ${className}`}>
      {what} připraví Vedoucí výzkumu: požádejte ho v konverzaci vlevo. Spustí se až po vašem schválení na jeho kartě.
    </p>
  );
}
