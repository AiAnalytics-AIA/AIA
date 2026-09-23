/**
 * DEVELOPMENT FIXTURES — not production data.
 *
 * Shaped exactly like the API responses in `@/lib/api/types` so a screen can move
 * from fixture to endpoint without changing shape. Every capability rendered from
 * here is listed in `./registry.ts`. Names and numbers are invented.
 */
import type { ClientResponse, ProjectDetailResponse, StageResponse, StudyResponse } from "@/lib/api/types";
import { stagesFor, type ProjectType } from "@/design/lifecycle";
import type { StageStatus } from "@/design/enums";

export const IS_FIXTURE = true as const;

export const fixtureClients: ClientResponse[] = [
  { client_id: "CLI-0a1b", slug: "banka-horizont", name: "Banka Horizont", status: "ACTIVE", reference: "", study_count: 1, created_at: "2026-08-01T09:00:00Z" },
  { client_id: "CLI-0c2d", slug: "energie-morava", name: "Energie Morava", status: "ACTIVE", reference: "", study_count: 1, created_at: "2026-08-12T09:00:00Z" },
];

export const fixtureStudies: StudyResponse[] = [
  {
    study_id: "STU-0a1b01", client_id: "CLI-0a1b", slug: "duvera-2026", name: "Důvěra v digitální bankovnictví 2026",
    status: "ACTIVE", accepts_work: true, your_role: "LEAD", budget_usd: 12000, spent_usd: 7420.5, remaining_usd: 4579.5,
    created_at: "2026-09-01T08:00:00Z", modified_at: "2026-09-20T11:02:00Z", delivered_at: null,
  },
  {
    study_id: "STU-0c2d01", client_id: "CLI-0c2d", slug: "tarif-domacnosti", name: "Tarif pro domácnosti — cenová citlivost",
    status: "ACTIVE", accepts_work: true, your_role: "RESEARCHER", budget_usd: null, spent_usd: null, remaining_usd: null,
    created_at: "2026-09-05T08:00:00Z", modified_at: "2026-09-21T14:22:00Z", delivered_at: null,
  },
];

function stages(projectType: ProjectType, statuses: StageStatus[], waiting?: Record<number, string>): StageResponse[] {
  return stagesFor(projectType).map(([id, label], i) => ({
    stage_type: id, ordinal: i, status: statuses[i] ?? "NOT_STARTED", label,
    provider: null, provider_label: null, model: "", artifact_count: 0,
    waiting_reason: waiting?.[i] ?? null, quota_reset_at: null, started_at: null, finished_at: null,
    fingerprint_prefix: "", is_complete: statuses[i] === "DONE" || statuses[i] === "DONE_WITH_WARNINGS",
  }));
}

const base = {
  parent_project_id: null, preferred_provider: "claude_code_subscription", provider_label: "Claude Code",
  provider_policy: "CLAUDE_CODE_THEN_API", max_api_cost_usd: 0, tags: [], pinned: false, archived: false, content: {},
};

export const fixtureProjects: Record<string, ProjectDetailResponse[]> = {
  "STU-0a1b01": [{
    ...base, project_id: "PRJ-00a1", title: "Hlavní vlna", project_type: "research", status: "WAITING",
    current_revision: 14, current_stage: "SAMPLE_PLAN", last_completed_stage: "DIMENSIONS",
    created_at: "2026-09-01T08:10:00Z", modified_at: "2026-09-20T11:41:00Z",
    stages: stages("research", ["DONE", "DONE", "DONE", "DONE_WITH_WARNINGS", "DONE", "DONE", "WAITING_CREDITS"], { 6: "budget" }),
  }],
  "STU-0c2d01": [{
    ...base, project_id: "PRJ-00c2", title: "Dynamický tarif", project_type: "simulation", status: "FAILED",
    current_revision: 6, current_stage: "WORLDS", last_completed_stage: "VARIANTS",
    created_at: "2026-09-05T08:10:00Z", modified_at: "2026-09-21T14:22:00Z",
    stages: stages("simulation", ["DONE", "DONE", "DONE", "DONE", "DONE", "DONE", "DONE", "FAILED"]),
  }],
};

export function fixtureStudy(studyId: string) {
  return fixtureStudies.find((s) => s.study_id === studyId) ?? null;
}
export function fixtureClient(clientId: string) {
  return fixtureClients.find((c) => c.client_id === clientId) ?? null;
}
export function fixtureProject(studyId: string, projectId: string) {
  return (fixtureProjects[studyId] ?? []).find((p) => p.project_id === projectId) ?? null;
}
