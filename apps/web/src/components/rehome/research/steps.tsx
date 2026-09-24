"use client";

// Which steps have a rebuilt screen. A step listed here must also be in
// REBUILT_STEPS (src/unit/research/steps.ts); screens.test.tsx checks both agree.

import type { ComponentType } from "react";

import type { StepKey } from "@/unit/research/steps";
import { BriefStep } from "./BriefStep";
import { PlanStep } from "./PlanStep";
import { QuestionnaireStep } from "./QuestionnaireStep";

export const STEP_SCREENS: Partial<Record<StepKey, ComponentType>> = { brief: BriefStep, plan: PlanStep, questionnaire: QuestionnaireStep };
