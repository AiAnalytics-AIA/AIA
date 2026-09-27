"use client";

// Which steps have a rebuilt screen. A step listed here must also be in
// REBUILT_STEPS (src/research/steps.ts); screens.test.tsx checks both agree.

import type { ComponentType } from "react";

import type { StepKey } from "@/research/steps";
import { AudienceStep } from "./AudienceStep";
import { BriefStep } from "./BriefStep";
import { ProgressStep, ResultsStep, RunStep } from "./ExecutionSteps";
import { PersonaStep } from "./PersonaStep";
import { PlanStep } from "./PlanStep";
import { QuestionnaireStep } from "./QuestionnaireStep";

export const STEP_SCREENS: Partial<Record<StepKey, ComponentType>> = { brief: BriefStep, plan: PlanStep, questionnaire: QuestionnaireStep, audience: AudienceStep, persona: PersonaStep, run: RunStep, progress: ProgressStep, results: ResultsStep };
