"use client";

// Proveditelnost recomputed as the audience changes (artifact-audience AUD9, spec vzorek/A5): the
// preview is asked PREVIEW_DEBOUNCE_MS after the last change of the filters or n, never on a button.
// An answer to an older question is dropped, so what is shown always counts what is stored; while a
// newer one is asked, the last answer stays (busy) rather than blanking. Every change costs one POST
// /population/audience-preview, a count over a population the API holds loaded.

import { useEffect, useRef, useState } from "react";

import type { AudiencePreview } from "@/lib/api";

export const PREVIEW_DEBOUNCE_MS = 400;

type Read = (filters: Record<string, unknown>, n: number | null) => Promise<AudiencePreview>;
type Answered = { key: string; answer: AudiencePreview | null; error: unknown };

export type PreviewState = { answer: AudiencePreview | null; error: unknown; busy: boolean };

export function useAudiencePreview(filters: Record<string, unknown>, n: number | null, read: Read): PreviewState {
  const key = JSON.stringify([filters, n]);
  const [answered, setAnswered] = useState<Answered | null>(null);
  const asked = useRef(0);
  useEffect(() => {
    const id = ++asked.current;
    const timer = setTimeout(() => {
      const [f, size] = JSON.parse(key) as [Record<string, unknown>, number | null];
      read(f, size).then(
        (answer) => id === asked.current && setAnswered({ key, answer, error: null }),
        // A failure counts nothing: the last answer was for other filters, so it goes too.
        (error: unknown) => id === asked.current && setAnswered({ key, answer: null, error }),
      );
    }, PREVIEW_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [key, read]);
  return { answer: answered?.answer ?? null, error: answered?.error ?? null, busy: answered?.key !== key };
}
