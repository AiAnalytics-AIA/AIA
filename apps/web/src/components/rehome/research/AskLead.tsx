"use client";

// Where a stage offered its own AI start, the workbench says where that work is asked for now: the
// Research Lead's conversation (plan research-lead-workbench D15). Nothing here starts anything: a
// stage may at most send the Lead a message, as the person would type it, and the Lead answers it
// with its usual approval card.

import { createContext, useContext } from "react";

import { Button } from "../ui";
import { ResearchContext } from "./context";

/**
 * Whether the Research Lead owns this layout's AI starts (ResearchContext.leadOwnsAiStarts): true in
 * the workbench, where a stage shows no start of its own; absent or false, the stage keeps its own.
 */
export function useLeadOwnsAiStarts(): boolean {
  return useContext(ResearchContext)?.leadOwnsAiStarts === true;
}

/** Send the Lead a message from a stage, as the person would type it (the workbench provides it). */
export const LeadAskContext = createContext<((text: string) => void) | null>(null);
export const useAskLead = () => useContext(LeadAskContext);

export function AskLead({ what, className = "" }: { what: string; className?: string }) {
  return (
    <p data-ask-lead className={`text-xs leading-5 text-ink-muted ${className}`}>
      {what} připraví Vedoucí výzkumu: požádejte ho v konverzaci s ním (na užší obrazovce ji otevře tlačítko Vedoucího). Spustí se až po vašem schválení na jeho kartě.
    </p>
  );
}

/**
 * What a stage says once it saved the person's own input for the Lead's next work (the owner,
 * 2026-10-21: Návrh's follow-up answers and comments go through the Lead too): it is saved, the Lead
 * updates the design from it, and one click asks the Lead in words -- the Lead's card then starts
 * the work only on the person's approval.
 */
export function SavedForLead({ saved, message }: { saved: string; message: string }) {
  const ask = useAskLead();
  return (
    <div role="status" data-saved-for-lead className="mt-3 flex flex-wrap items-center gap-3 rounded-sm border border-border bg-surface-raised p-3 text-sm">
      <span className="min-w-0 flex-1">{saved}; návrh podle nich aktualizuje Vedoucí výzkumu.</span>
      {ask ? <Button small onClick={() => ask(message)}>Požádat Vedoucího</Button> : null}
    </div>
  );
}
