// A Deep Research run started away from its own panel (a Lead card, LO5a.2), told to the panel
// already on screen: Dotazník's design panel and Výsledky's Interpretation panel read their runs
// when they mount and poll only a run they already know is moving, so without this a run started
// while either is open stays out of sight until the page is reloaded (review of #1006).

/** `researchRunId`: an Interpretation run's research run, the result it is shown under. */
export type DeepResearchStarted = { runId: string; purpose: string | null; researchRunId?: string | null };

const EVENT = "aia:deep-research-started";

/** Tell every mounted Deep Research panel that a run started. */
export function announceDeepResearchStarted(started: DeepResearchStarted): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<DeepResearchStarted>(EVENT, { detail: started }));
}

/** Follow runs started elsewhere; returns the unsubscribe a React effect cleans up with. */
export function onDeepResearchStarted(listener: (started: DeepResearchStarted) => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handle = (e: Event) => listener((e as CustomEvent<DeepResearchStarted>).detail);
  window.addEventListener(EVENT, handle);
  return () => window.removeEventListener(EVENT, handle);
}
