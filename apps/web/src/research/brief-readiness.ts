// Zadání's readiness as the v73 board draws it (artifact-brief BRF2, spec navrh B2): one chip per
// section, in the page's order, each a way to its section. A required section the brief lacks reads
// "you" (it waits on the person); an optional one never does, filled or not. Advisory only: the
// analysis keeps its own condition (brief.ts canAnalyse), and no chip blocks anything. No percentage:
// sections are not worth a quarter each. Pure.

import { briefElementId } from "@/lib/artifacts/brief";
import { objectivesOf } from "./brief-objectives";
import { type ResearchProject, selectedProblemTypes } from "./model";
import type { Analysis } from "./store";

export type ChipState = "done" | "you" | "optional";

export type ReadinessChip = {
  /** The section's DOM id, the chip's target. */
  target: string;
  /** The chip's words (a cs.ts key). */
  label: string;
  required: boolean;
  state: ChipState;
};

const filled = (v: unknown) => typeof v === "string" && v.trim() !== "";

/** The Brief's further-context fields, as the Context section lists them. */
const CONTEXT_FIELDS = ["product_description", "situation", "what_is_known", "constraints"] as const;

export function briefReadiness(design: { project: ResearchProject; analysis: Analysis | null }): ReadinessChip[] {
  const p = design.project;
  const briefing = p.briefing as Record<string, unknown>;
  const required = (target: string, label: string, ok: boolean): ReadinessChip => ({ target, label, required: true, state: ok ? "done" : "you" });
  const optional = (target: string, label: string, ok: boolean): ReadinessChip => ({ target, label, required: false, state: ok ? "done" : "optional" });
  return [
    required(briefElementId("goal"), "research.brief.chipGoal", filled(p.goal)),
    required(briefElementId("objectives"), "research.brief.chipObjectives", objectivesOf(design).length > 0),
    required(briefElementId("decision_use"), "research.brief.chipDecision", filled(p.decision_use)),
    required(briefElementId("type"), "research.brief.chipType", selectedProblemTypes(p).length > 0),
    optional(briefElementId("context"), "research.brief.chipContext", CONTEXT_FIELDS.some((f) => filled(briefing[f]))),
    optional(briefElementId("files"), "research.brief.chipFiles", (p.briefing.attachments || []).length > 0),
  ];
}
