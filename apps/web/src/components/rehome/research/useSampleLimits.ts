"use client";

// The study's valid n, read from the server once per visit (plan run-qc-and-checkpoint RQC9):
// the one range there is. Every screen that stores a sample size (Dimenze's field and presets,
// Návrh's design variants) refuses outside it through research/persona.ts sampleRefusal.

import { useEffect, useState } from "react";

import { research } from "@/lib/api";
import type { SampleLimits } from "@/research/persona";

export type Limits = { state: "loading" } | { state: "ready"; limits: SampleLimits } | { state: "failed" };

export function useSampleLimits(studyId: string): Limits {
  const [limits, setLimits] = useState<Limits>({ state: "loading" });
  useEffect(() => {
    let live = true;
    research.limits(studyId).then(
      (l) => live && setLimits({ state: "ready", limits: l.sample_size }),
      // Unread, nothing is stored: a range never seen is not presumed to admit a value.
      () => live && setLimits({ state: "failed" }),
    );
    return () => {
      live = false;
    };
  }, [studyId]);
  return limits;
}

/** The limits once read; null while loading or when they could not be read. */
export const readyLimits = (l: Limits): SampleLimits | null => (l.state === "ready" ? l.limits : null);
