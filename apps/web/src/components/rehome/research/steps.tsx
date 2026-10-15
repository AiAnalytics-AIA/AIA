"use client";

// Which steps have a rebuilt screen. A step listed here must also be in
// REBUILT_STEPS (src/research/steps.ts); screens.test.tsx checks both agree.

import type { ComponentType } from "react";
import dynamic from "next/dynamic";

import type { StepKey } from "@/research/steps";
import { PlanStep } from "./PlanStep";

function LoadingStage() {
  return <p role="status" className="py-6 text-sm text-ink-muted">Načítám pracovní část výzkumu…</p>;
}
// Opening the brief/proposal should not parse all map renderers and execution views.
const AudienceStep = dynamic(() => import("./AudienceStep").then((module) => module.AudienceStep), { loading: LoadingStage });
const BriefStep = dynamic(() => import("./BriefStep").then((module) => module.BriefStep), { loading: LoadingStage });
const PersonaStep = dynamic(() => import("./PersonaStep").then((module) => module.PersonaStep), { loading: LoadingStage });
const QuestionnaireStep = dynamic(() => import("./QuestionnaireStep").then((module) => module.QuestionnaireStep), { loading: LoadingStage });
const RunStep = dynamic(() => import("./ExecutionSteps").then((module) => module.RunStep), { loading: LoadingStage });
const ProgressStep = dynamic(() => import("./ExecutionSteps").then((module) => module.ProgressStep), { loading: LoadingStage });
const ResultsStep = dynamic(() => import("./ExecutionSteps").then((module) => module.ResultsStep), { loading: LoadingStage });

export const STEP_SCREENS: Partial<Record<StepKey, ComponentType>> = { brief: BriefStep, plan: PlanStep, questionnaire: QuestionnaireStep, audience: AudienceStep, persona: PersonaStep, run: RunStep, progress: ProgressStep, results: ResultsStep };
