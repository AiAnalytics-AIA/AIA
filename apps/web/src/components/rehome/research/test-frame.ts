// The study a research test renders in (ADR 0015): one client, one study. A test
// of a stage needs a frame as the real layout provides one, and asserts the
// client-first URLs it builds.

import { appRoutes } from "@/lib/app-routes";
import type { StepKey } from "@/unit/research/steps";
import type { StudyFrame } from "./frame";

export const TEST_FRAME: StudyFrame = {
  clientId: "CLI-1",
  clientName: "Klient A",
  studyId: "STU-1",
  studyName: "Výzkum A",
  unitProjectId: "PRJ-1",
  lastStage: null,
  canEdit: true,
  stepHref: (step: StepKey) => appRoutes.stage("CLI-1", "STU-1", step),
};

/** The URL of a stage of the test study. */
export const stagePath = (step: StepKey): string => TEST_FRAME.stepHref(step);
