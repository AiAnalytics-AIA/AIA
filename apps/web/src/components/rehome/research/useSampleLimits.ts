"use client";

// The study's valid n, read from the server once per visit (plan run-qc-and-checkpoint RQC9):
// the one range there is. Every screen that stores a sample size (Dimenze's field and presets,
// Návrh's design variants) refuses outside it through research/persona.ts sampleRefusal.

import { createContext, useEffect, useState } from "react";

import { research } from "@/lib/api";
import type { SampleLimits } from "@/research/persona";
import { SET_PRESET, type SetLimits } from "@/research/questionnaire";

export type Limits = { state: "loading" } | { state: "ready"; limits: SampleLimits; set: SetLimits } | { state: "failed" };

export function useSampleLimits(studyId: string): Limits {
  const [limits, setLimits] = useState<Limits>({ state: "loading" });
  useEffect(() => {
    let live = true;
    research.limits(studyId).then(
      (l) => live && setLimits({ state: "ready", limits: l.sample_size, set: l.tracked_set ?? SET_PRESET }),
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

/**
 * A tracked set's limits in force once read; the code's preset while they load or when they could
 * not be read. A set's size is checked again by compile and readiness, so the preset here only
 * decides what the screen offers until the server's answer arrives.
 */
export const readySetLimits = (l: Limits): SetLimits => (l.state === "ready" ? l.set : SET_PRESET);

/** The set limits Dotazník's parts read, provided once by the stage (QuestionnaireStep). */
export const SetLimitsContext = createContext<SetLimits>(SET_PRESET);
