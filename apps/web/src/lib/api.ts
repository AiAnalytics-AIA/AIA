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
  kind: StudyKind;
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

// ---- the client workspace (ADR 0015) --------------------------------------

export type StudyKind = "RESEARCH" | "SIMULATION";

export type WorkspaceStudy = {
  study_id: string;
  client_id: string;
  name: string;
  slug: string;
  kind: StudyKind;
  status: string;
  accepts_work: boolean;
  last_stage: string | null;
  has_working_content: boolean;
  created_at: string | null;
  modified_at: string | null;
};

export type ClientCard = {
  client_id: string;
  name: string;
  slug: string;
  your_role: string | null;
  active_count: number;
  study_count: number;
  recent: WorkspaceStudy[];
  modified_at: string | null;
};

export type ClientWorkspace = {
  client_id: string;
  name: string;
  slug: string;
  status: string;
  your_role: string | null;
  permissions: string[];
};

export type KnowledgeSection = "sources" | "knowledge" | "dimensions" | "audiences" | "data";

export type KnowledgeItem = {
  item_id: string;
  kind: string;
  title: string;
  summary: string;
  content: Record<string, unknown>;
  revision: number;
  modified_at: string | null;
};

export type KnowledgeRevision = {
  revision: number;
  context_revision: number;
  title: string;
  summary: string;
  provenance: Record<string, unknown>;
  approved_by: string;
  approved_at: string | null;
};

export type Proposal = {
  proposal_id: string;
  origin: "STUDY" | "CLIENT";
  study_id: string | null;
  study_name: string | null;
  item_id: string | null;
  kind: string;
  title: string;
  summary: string;
  status: "PROPOSED" | "APPROVED" | "REJECTED";
  proposed_by: string;
  proposed_at: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string;
  revision: number | null;
  yours: boolean;
};

export type KnowledgeSummary = {
  context_revision: number;
  items_by_kind: Record<string, number>;
  pending_proposals: number;
  last_approved_at: string | null;
};

export type OutputItem = {
  artifact_id: string;
  artifact_type: string;
  stage_type: string;
  status: string;
  study_id: string;
  study_name: string;
  created_at: string | null;
};

export type ClientOverview = {
  client: ClientWorkspace;
  active: WorkspaceStudy[];
  previous_count: number;
  recent_outputs: OutputItem[];
  knowledge: KnowledgeSummary | null;
  pending: Proposal[];
};

export type StudyWorkspace = {
  study: WorkspaceStudy;
  client_name: string;
  your_role: string;
  can_edit: boolean;
  unit_project_id: string | null;
};

export type Me = { user_id: string; email: string | null; organization_role: string; may_administer: boolean };

const enc = encodeURIComponent;
const query = (q: Record<string, string | undefined>) => {
  const p = new URLSearchParams(Object.entries(q).filter((e): e is [string, string] => !!e[1]));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const workspace = {
  me: () => request<Me>("GET", "/api/v1/workspace/me"),
  clients: () => request<ClientCard[]>("GET", "/api/v1/workspace/clients"),
  startClient: (name: string) => request<ClientWorkspace>("POST", "/api/v1/workspace/clients", { name }),
  client: (clientId: string) => request<ClientWorkspace>("GET", `/api/v1/clients/${enc(clientId)}`),
  overview: (clientId: string) => request<ClientOverview>("GET", `/api/v1/clients/${enc(clientId)}/overview`),
  studies: (clientId: string, kind?: StudyKind) =>
    request<WorkspaceStudy[]>("GET", `/api/v1/clients/${enc(clientId)}/studies${query({ kind })}`),
  startStudy: (clientId: string, name: string, kind: StudyKind) =>
    request<WorkspaceStudy>("POST", `/api/v1/clients/${enc(clientId)}/studies`, { name, kind }),
  knowledge: (clientId: string, section?: KnowledgeSection, q?: string) =>
    request<KnowledgeItem[]>("GET", `/api/v1/clients/${enc(clientId)}/knowledge${query({ section, q })}`),
  revisions: (clientId: string, itemId: string) =>
    request<KnowledgeRevision[]>("GET", `/api/v1/clients/${enc(clientId)}/knowledge/items/${enc(itemId)}/revisions`),
  proposals: (clientId: string, status?: Proposal["status"]) =>
    request<Proposal[]>("GET", `/api/v1/clients/${enc(clientId)}/knowledge/proposals${query({ status })}`),
  propose: (clientId: string, body: { kind: string; title: string; summary?: string }) =>
    request<Proposal>("POST", `/api/v1/clients/${enc(clientId)}/knowledge/proposals`, body),
  decide: (clientId: string, proposalId: string, approve: boolean, note = "") =>
    request<Proposal>("POST", `/api/v1/clients/${enc(clientId)}/knowledge/proposals/${enc(proposalId)}/decision`, {
      approve,
      note,
    }),
  study: (studyId: string) => request<StudyWorkspace>("GET", `/api/v1/studies/${enc(studyId)}/workspace`),
  bind: (studyId: string, unitProjectId: string) =>
    request<StudyWorkspace>("PUT", `/api/v1/studies/${enc(studyId)}/workspace`, { unit_project_id: unitProjectId }),
  recordStage: (studyId: string, stage: string) =>
    request<void>("PUT", `/api/v1/studies/${enc(studyId)}/workspace/stage`, { stage }),
};

// ---- research execution (ADR 0016) -----------------------------------------
// Every route is under the study: the browser supplies the design's content and
// the ids the API gave it, never a client, organization or unit project id.

export type DesignRevision = {
  revision_id: string;
  study_id: string;
  revision: number;
  content_sha256: string;
  parent_revision: number | null;
  source_stage: string;
  created_by: string;
  created_at: string;
  created?: boolean;
};

export type CheckStatus = "PASS" | "WARN" | "FAIL";
export type Readiness = {
  design_revision_id: string;
  rules: string;
  ready: boolean;
  checks: { id: string; status: CheckStatus; message: string }[];
  questions: number;
  batteries: number;
  objects: number;
  n: number | null;
  /** The deployment's: `ai_runtime` stops at fieldwork until the AI runtime exists. */
  fieldwork_source: string;
};

export type ResearchPhase = "QUEUED" | "RUNNING" | "WAITING" | "COMPLETED" | "FAILED" | "CANCELLED";
export type ResearchStep = {
  node_key: "compile" | "preflight" | "run" | "aggregate" | "sociomap" | string;
  kind: string;
  stage_type: string;
  status: string;
  waiting_reason: string | null;
  attempts_recorded: number;
  max_attempts: number;
  started_at: string | null;
  finished_at: string | null;
  failure_class: string | null;
  error_message: string | null;
  artifact_id: string | null;
  data_origin: string | null;
};
export type ResearchRun = {
  run_id: string;
  study_id: string;
  design_revision_id: string;
  design_revision: number;
  status: string;
  phase: ResearchPhase;
  needs_attention: boolean;
  is_terminal: boolean;
  retryable: boolean;
  cancel_requested: boolean;
  fieldwork_source: string;
  retry_of: string | null;
  created: boolean | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  steps: ResearchStep[];
  artifact_ids: string[];
  actual_cost_usd: number | null;
};

const studyPath = (studyId: string) => `/api/v1/studies/${enc(studyId)}`;

export const research = {
  submitDesign: (studyId: string, content: unknown, sourceStage: string) =>
    request<DesignRevision>("POST", `${studyPath(studyId)}/design/revisions`, { content, source_stage: sourceStage }),
  revisions: (studyId: string) =>
    request<{ items: DesignRevision[] }>("GET", `${studyPath(studyId)}/design/revisions`).then((r) => r.items),
  readiness: (studyId: string, revisionId: string) =>
    request<Readiness>("GET", `${studyPath(studyId)}/research/readiness${query({ design_revision_id: revisionId })}`),
  start: (studyId: string, revisionId: string) =>
    request<ResearchRun>("POST", `${studyPath(studyId)}/research/runs`, { design_revision_id: revisionId }),
  runs: (studyId: string) =>
    request<{ items: ResearchRun[] }>("GET", `${studyPath(studyId)}/research/runs`).then((r) => r.items),
  run: (studyId: string, runId: string) => request<ResearchRun>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}`),
  cancel: (studyId: string, runId: string) =>
    request<ResearchRun>("POST", `${studyPath(studyId)}/research/runs/${enc(runId)}/cancel`),
  retry: (studyId: string, runId: string) =>
    request<ResearchRun>("POST", `${studyPath(studyId)}/research/runs/${enc(runId)}/retry`),
  artifact: (studyId: string, runId: string, artifactId: string) =>
    request<Artifact>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}/artifacts/${enc(artifactId)}`),
};
