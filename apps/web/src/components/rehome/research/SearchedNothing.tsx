"use client";

// A finished Deep Research run that sent no query -- every web track blocked, as on a deployment
// with no search route -- completes with an empty bundle. Read as a search, that is "searched and
// found nothing", which it is not (PC18). Its coverage says how many queries left; when none did,
// this says so beside the bundle. Coverage not read says nothing: unknown is never "nothing".

import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { deepResearch, type DeepResearchCoverage } from "@/lib/api";
import { searchedNothing } from "@/lib/reason-words";

/** The run's coverage when it sent no query; ``null`` when it searched, when its coverage was not
 * read, or for no run. A panel that says "searched and found nothing" reads this first, so the two
 * never stand side by side (review, Codex on #479). */
export function useSearchedNothing(studyId: string, runId: string | null): DeepResearchCoverage | null {
  const [coverage, setCoverage] = useState<{ runId: string; value: DeepResearchCoverage } | null>(null);
  useEffect(() => {
    if (!runId) return;
    let live = true;
    deepResearch.coverage(studyId, runId).then(
      (value) => live && setCoverage({ runId, value }),
      () => live && setCoverage(null),
    );
    return () => { live = false; };
  }, [studyId, runId]);
  const read = coverage && coverage.runId === runId ? coverage.value : null;
  return searchedNothing(read) ? read : null;
}

export function SearchedNothingNote({ coverage }: { coverage: DeepResearchCoverage }) {
  return (
    <p role="note" data-searched-nothing className="rounded-control border border-status-you-ink/40 bg-status-you-wash p-3 text-sm leading-6">
      {tv("research.deep.searchedNothing", { blocked: coverage.blocked_tracks, tracks: coverage.tracks })} {t("research.deep.searchedNothingWhy")}
    </p>
  );
}

export function SearchedNothing({ studyId, runId }: { studyId: string; runId: string }) {
  const nothing = useSearchedNothing(studyId, runId);
  return nothing ? <SearchedNothingNote coverage={nothing} /> : null;
}
