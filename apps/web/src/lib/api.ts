"use client";

// The real AIA API, same origin, bearer id token. Response shapes mirror the
// API's Pydantic models (apps/api/src/aia_api/schemas); the client renders what
// the server computed and decides nothing (ARCHITECTURE.md §2).

import { currentIdToken, loadConfig } from "@/lib/auth";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId: string | null,
  ) {
    super(message);
  }
}

export class Unauthenticated extends ApiError {}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = await currentIdToken();
  if (!token) throw new Unauthenticated(401, "unauthenticated", "Not signed in.", null);
  const config = await loadConfig();
  const response = await fetch(`${config.apiBase}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const requestId = response.headers.get("X-Request-ID");
  if (response.status === 204) return undefined as T;
  const payload = (await response.json().catch(() => ({}))) as {
    code?: string;
    message?: string;
  };
  if (!response.ok) {
    const code = payload.code ?? `http_${response.status}`;
    const message = payload.message ?? response.statusText;
    if (response.status === 401) throw new Unauthenticated(401, code, message, requestId);
    throw new ApiError(response.status, code, message, requestId);
  }
  return payload as T;
}

export type Health = {
  status: string;
  service: string;
  version: string;
  env: string;
  build: { sha: string | null; built_at: string | null };
};

export type Study = {
  study_id: string;
  client_id: string;
  slug: string;
  name: string;
  status: string;
  accepts_work: boolean;
  your_role: string | null;
  budget_usd: number | null;
  spent_usd: number | null;
  remaining_usd: number | null;
};

export type Project = {
  project_id: string;
  title: string;
  project_type: string;
  status: string;
  current_revision: number;
  current_stage: string;
  provider_label: string;
  max_api_cost_usd: number;
  modified_at: string | null;
};

export type Attempt = {
  attempt_id: string;
  attempt_number: number;
  status: string;
  worker_id: string | null;
  failure_class: string | null;
  error: Record<string, unknown>;
  actual_cost_usd: number | null;
  started_at: string | null;
  finished_at: string | null;
};

export type StepRun = {
  step_id: string;
  node_key: string;
  kind: string;
  status: string;
  stage_type: string;
  attempts_recorded: number;
  max_attempts: number;
  waiting_reason: string | null;
  output: Record<string, unknown>;
  attempts: Attempt[];
};

export type RunSummary = {
  run_id: string;
  status: string;
  needs_attention: boolean;
  is_terminal: boolean;
  workflow_type: string;
  project_id: string;
  project_revision: number;
  created_at: string | null;
  finished_at: string | null;
};

export type Run = RunSummary & { created: boolean | null; steps: StepRun[] };

export type Artifact = {
  artifact_id: string;
  artifact_type: string;
  stage_type: string;
  revision: number;
  content_type: string;
  sha256: string;
  size_bytes: number;
  status: string;
  runtime_version: string;
  produced_by_job_id: string | null;
  created_at: string | null;
  payload: unknown;
};

export const api = {
  health: () => fetch("/api/v1/health", { cache: "no-store" }).then((r) => r.json() as Promise<Health>),
  studies: () => request<Study[]>("GET", "/api/v1/studies"),
  study: (studyId: string) => request<Study>("GET", `/api/v1/studies/${studyId}`),
  projects: (studyId: string) =>
    request<{ items: Project[] }>("GET", `/api/v1/studies/${studyId}/projects`).then((r) => r.items),
  project: (studyId: string, projectId: string) =>
    request<Project & { content: Record<string, unknown> }>(
      "GET",
      `/api/v1/studies/${studyId}/projects/${projectId}`,
    ),
  createProject: (studyId: string, title: string) =>
    request<Project>("POST", `/api/v1/studies/${studyId}/projects`, {
      title,
      content: { goal: title, synthetic: true },
    }),
  runs: (studyId: string, projectId: string) =>
    request<{ items: RunSummary[] }>(
      "GET",
      `/api/v1/studies/${studyId}/projects/${projectId}/runs`,
    ).then((r) => r.items),
  run: (studyId: string, projectId: string, runId: string) =>
    request<Run>("GET", `/api/v1/studies/${studyId}/projects/${projectId}/runs/${runId}`),
  startRun: (studyId: string, projectId: string) =>
    request<Run>("POST", `/api/v1/studies/${studyId}/projects/${projectId}/runs`, {
      workflow_type: "develop_snapshot",
    }),
  artifact: (studyId: string, projectId: string, artifactId: string) =>
    request<Artifact>(
      "GET",
      `/api/v1/studies/${studyId}/projects/${projectId}/artifacts/${artifactId}`,
    ),
};
