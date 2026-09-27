// Every URL of the client-first interface (ADR 0015), in one place. A screen
// never writes an /app path by hand: the hierarchy is Clients → one client →
// its areas → one study → its stages, and this module is where it is spelled.

import type { StudyKind } from "@/lib/api";
import { type StepKey, stepSlug } from "@/research/steps";

const e = encodeURIComponent;

export type ClientArea = "overview" | "research" | "simulations" | "knowledge" | "data";

export const appRoutes = {
  home: () => "/app/clients",
  clients: () => "/app/clients",
  client: (clientId: string) => `/app/clients/${e(clientId)}`,
  area: (clientId: string, area: ClientArea) =>
    area === "overview" ? `/app/clients/${e(clientId)}` : `/app/clients/${e(clientId)}/${area}`,
  study: (clientId: string, studyId: string, kind: StudyKind) =>
    kind === "SIMULATION"
      ? `/app/clients/${e(clientId)}/simulations/${e(studyId)}`
      : `/app/clients/${e(clientId)}/research/${e(studyId)}`,
  stage: (clientId: string, studyId: string, step: StepKey) =>
    `/app/clients/${e(clientId)}/research/${e(studyId)}/${stepSlug(step)}`,
  intelligence: () => "/app/intelligence",
  memory: () => "/app/memory",
  settings: () => "/app/settings",
  classicProjects: () => "/app/settings/classic-projects",
  classicTrash: () => "/app/settings/classic-projects/trash",
};
