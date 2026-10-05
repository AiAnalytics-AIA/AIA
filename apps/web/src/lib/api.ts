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
    /** The error contract's `details`, when the API gave any. */
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export class Unauthenticated extends ApiError {}

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const token = await currentIdToken();
  if (!token) throw new Unauthenticated(401, "unauthenticated", "Not signed in.", null);
  const config = await loadConfig();
  return fetch(`${config.apiBase}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
}

async function refusal(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("X-Request-ID");
  const payload = (await response.json().catch(() => ({}))) as {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
  const code = payload.code ?? `http_${response.status}`;
  const message = payload.message ?? response.statusText;
  if (response.status === 401) return new Unauthenticated(401, code, message, requestId);
  return new ApiError(response.status, code, message, requestId, payload.details ?? {});
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await send(method, path, body);
  if (response.status === 204) return undefined as T;
  if (!response.ok) throw await refusal(response);
  return (await response.json().catch(() => ({}))) as T;
}

/** A file the API serves as bytes (an attachment): same authentication, same errors. */
async function requestBlob(path: string): Promise<Blob> {
  const response = await send("GET", path);
  if (!response.ok) throw await refusal(response);
  return response.blob();
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
  /** The cost at or above which starting a run asks for confirmation; `null`: it never asks. */
  spend_confirm_usd?: number | null;
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
  content_state: ContentState;
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
  content_state: ContentState;
};

/**
 * Where a research study's working content stands (ADR 0018). Never guessed from
 * an empty document: a study bound to 18.6.6 whose content is not migrated yet
 * is AWAITING_MIGRATION, one whose 18.6.6 content was lost is UNRECOVERABLE.
 */
export type ContentState = "EMPTY" | "NATIVE" | "MIGRATED" | "RECOVERED" | "UNRECOVERABLE" | "AWAITING_MIGRATION";

/** GET /api/v1/studies/{id}/workspace/content */
export type WorkingContent = {
  study_id: string;
  state: ContentState;
  revision: number | null;
  revision_id: string | null;
  content: Record<string, unknown> | null;
  analysis: Record<string, unknown> | null;
  template: Record<string, unknown>;
  saved_at: string | null;
  saved_by: string | null;
  can_edit: boolean;
  lineage: Record<string, unknown>;
};

export type WorkingSave = { study_id: string; state: ContentState; revision: number; revision_id: string; deduplicated: boolean };

/** A filled-in questionnaire template, read by AIA (QuestionnaireImportResponse). */
export type QuestionnaireImport = {
  sections: Record<string, unknown>[];
  summary: { question_count: number; tracked_sets: number; sections: number };
  filename: string;
};

/** What the brief keeps of an attached file (AttachmentResponse): never where it is stored. */
export type AttachmentRecord = {
  kind: "file";
  attachment_id: string;
  filename: string;
  extension: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  text_extracted: boolean;
  context_excerpt: string;
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
  content: (studyId: string) => request<WorkingContent>("GET", `/api/v1/studies/${enc(studyId)}/workspace/content`),
  saveContent: (
    studyId: string,
    body: { content: unknown; analysis: unknown; base_revision: number | null; reason: string },
  ) => request<WorkingSave>("PUT", `/api/v1/studies/${enc(studyId)}/workspace/content`, body),
  recordStage: (studyId: string, stage: string) =>
    request<void>("PUT", `/api/v1/studies/${enc(studyId)}/workspace/stage`, { stage }),
  attach: (studyId: string, body: { filename: string; data_b64: string }) =>
    request<AttachmentRecord>("POST", `/api/v1/studies/${enc(studyId)}/workspace/attachments`, body),
  attachment: (studyId: string, attachmentId: string) =>
    requestBlob(`/api/v1/studies/${enc(studyId)}/workspace/attachments/${enc(attachmentId)}`),
  importQuestionnaire: (studyId: string, body: { filename: string; data_b64: string }) =>
    request<QuestionnaireImport>("POST", `/api/v1/studies/${enc(studyId)}/workspace/questionnaire-import`, body),
  questionnaireTemplate: (studyId: string) => requestBlob(`/api/v1/studies/${enc(studyId)}/workspace/questionnaire-template`),
  /** What the study inherits: its own client's approved knowledge (ADR 0015 decision 7). */
  studyContext: (studyId: string) =>
    request<{ client_id: string; shared: Record<string, unknown>; client: KnowledgeItem[] }>("GET", `/api/v1/studies/${enc(studyId)}/context`),
  /** The study proposes; a person approves; nothing else changes the client's knowledge. */
  proposeFromStudy: (studyId: string, body: { kind: string; title: string; summary?: string; content?: Record<string, unknown> }) =>
    request<Proposal>("POST", `/api/v1/studies/${enc(studyId)}/knowledge-proposals`, body),
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
  /** The most the run can cost: an upper bound, not a forecast. `null` when it cannot be worked out. */
  cost_ceiling_usd: number | null;
  /** Why the ceiling is unknown; never shown as a zero. */
  cost_ceiling_unknown: string | null;
  fieldwork_requests: number;
  analysis_calls: number;
  /** The study's limit, and whether starting this run will ask for confirmation against it. */
  spend_confirm_usd: number | null;
  confirmation_required: boolean;
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
/** A run as the Study's list gives it: its state, without its steps or artifacts. */
export type ResearchRunSummary = Omit<ResearchRun, "steps" | "artifact_ids">;

export type ResearchAnalysis = {
  run_id: string;
  complete: boolean;
  internal_only: true;
  synthetic: boolean;
  pending: Record<string, string>;
  modules: Record<string, {
    outcome: "COMPLETED" | "BLOCKED";
    artifact_id: string;
    summary: string | null;
    research_question_answers: { question: string; answer: string; claim_ids: string[] }[];
    key_findings: { text: string; claim_ids: string[] }[];
    claims: { claim_id: string; evidence_ref: string; value: number; indicative: boolean; data_origin: string | null }[];
    violations: { code: string; subject: string; detail: string }[];
  }>;
};

export type ResearchReport = {
  run_id: string;
  state: "NOT_IN_RUN" | "READY" | string;
  internal_only: true;
  reason?: string | null;
  review_state?: "DRAFT_UNAPPROVED" | "APPROVED_INTERNAL";
  artifact_id?: string;
  sha256?: string;
  size_bytes?: number;
  synthetic?: boolean;
};

const studyPath = (studyId: string) => `/api/v1/studies/${enc(studyId)}`;

export const research = {
  submitDesign: (studyId: string, content: unknown, sourceStage: string) =>
    request<DesignRevision>("POST", `${studyPath(studyId)}/design/revisions`, { content, source_stage: sourceStage }),
  revisions: (studyId: string) =>
    request<{ items: DesignRevision[] }>("GET", `${studyPath(studyId)}/design/revisions`).then((r) => r.items),
  readiness: (studyId: string, revisionId: string) =>
    request<Readiness>("GET", `${studyPath(studyId)}/research/readiness${query({ design_revision_id: revisionId })}`),
  /** `confirmCostUsd` is the person's yes to the ceiling the server showed, when the study's limit asks for one. */
  start: (studyId: string, revisionId: string, confirmCostUsd?: number) =>
    request<ResearchRun>(
      "POST",
      `${studyPath(studyId)}/research/runs`,
      confirmCostUsd === undefined
        ? { design_revision_id: revisionId }
        : { design_revision_id: revisionId, confirm_cost_usd: confirmCostUsd },
    ),
  /** Set, or with `null` clear, the cost at which starting a run asks for confirmation. */
  setSpendConfirm: (studyId: string, limitUsd: number | null) =>
    request<Study>("PUT", `${studyPath(studyId)}/spend-confirm`, { limit_usd: limitUsd }),
  runs: (studyId: string) =>
    request<{ items: ResearchRunSummary[] }>("GET", `${studyPath(studyId)}/research/runs`).then((r) => r.items),
  run: (studyId: string, runId: string) => request<ResearchRun>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}`),
  cancel: (studyId: string, runId: string) =>
    request<ResearchRun>("POST", `${studyPath(studyId)}/research/runs/${enc(runId)}/cancel`),
  retry: (studyId: string, runId: string, confirmCostUsd?: number) =>
    request<ResearchRun>(
      "POST",
      `${studyPath(studyId)}/research/runs/${enc(runId)}/retry`,
      confirmCostUsd === undefined ? undefined : { confirm_cost_usd: confirmCostUsd },
    ),
  /** Raise the Study's budget to `budgetUsd` (never below the current one) and let the waiting step go on. */
  liftBudget: (studyId: string, runId: string, nodeKey: string, budgetUsd: number, note: string) =>
    request<ResearchRun>("POST", `${studyPath(studyId)}/research/runs/${enc(runId)}/steps/${enc(nodeKey)}/budget`, {
      budget_usd: budgetUsd,
      note,
    }),
  artifact: (studyId: string, runId: string, artifactId: string) =>
    request<Artifact>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}/artifacts/${enc(artifactId)}`),
  analysis: (studyId: string, runId: string) =>
    request<ResearchAnalysis>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}/analysis`),
  report: (studyId: string, runId: string) =>
    request<ResearchReport>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}/report`),
  downloadReport: (studyId: string, runId: string) =>
    requestBlob(`${studyPath(studyId)}/research/runs/${enc(runId)}/report/download`),
  /** The experimental Sociomapping's internal draft: status, then the DOCX (plan sociomapping-engine I3). */
  sociomappingReport: (studyId: string, runId: string) =>
    request<ResearchReport>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}/sociomapping/report`),
  downloadSociomappingReport: (studyId: string, runId: string) =>
    requestBlob(`${studyPath(studyId)}/research/runs/${enc(runId)}/sociomapping/report/download`),
};

export type DeepResearchRun = {
  run_id: string; design_revision_id: string; preset: string; channels: string[];
  status: string; phase: ResearchPhase; is_terminal: boolean; needs_attention: boolean;
  retryable: boolean; created_at: string | null;
  steps: { node_key: string; status: string; waiting_reason: string | null; error_message: string | null }[];
  actual_cost_usd: number | null;
};
export type DeepResearchBundle = {
  quality_status: string; fictional_client: boolean; client_facing: false;
  accepted: { evidence: { claim: string; quote: string; source_ref: string }; score: { score: number; source_class: string } }[];
  quarantined: { reason: string; detail?: string }[];
  snapshots: { snapshot_id: string; url: string; title: string; retrieval_mode: string }[];
  counts: Record<string, number>; sha256: string;
};
const deepPath = (studyId: string) => `${studyPath(studyId)}/deep-research/runs`;
export const deepResearch = {
  start: (studyId: string, revisionId: string) =>
    request<DeepResearchRun>("POST", deepPath(studyId), { design_revision_id: revisionId, preset_name: "QUICK", channels: ["WEB"] }),
  runs: (studyId: string) => request<DeepResearchRun[]>("GET", deepPath(studyId)),
  run: (studyId: string, runId: string) => request<DeepResearchRun>("GET", `${deepPath(studyId)}/${enc(runId)}`),
  bundle: (studyId: string, runId: string) => request<DeepResearchBundle>("GET", `${deepPath(studyId)}/${enc(runId)}/bundle`),
  cancel: (studyId: string, runId: string) => request<DeepResearchRun>("POST", `${deepPath(studyId)}/${enc(runId)}/cancel`),
  retry: (studyId: string, runId: string) => request<DeepResearchRun>("POST", `${deepPath(studyId)}/${enc(runId)}/retry`),
};

export type ResearchAgentAction = "analyze_brief" | "build_questionnaire" | "optimize_questionnaire" | "propose_audience" | "suggest_dimensions" | "critique_design" | "design_copilot" | "answer_memory";
export type ResearchAgentJob = {
  run_id: string; design_revision_id: string; action: ResearchAgentAction;
  status: string; is_terminal: boolean; needs_attention: boolean;
  context_sha256: string; harness_version: string; created_at: string | null;
  /** The prompt the job was queued with: "1" (the code's wording) or "e<n>" (an edit). Null: queued before prompts were editable. */
  prompt_version?: string | null; prompt_origin?: "baseline" | "stored" | null;
  steps: ResearchStep[]; actual_cost_usd: number | null;
};
export type ResearchAgentResult = {
  result: { project: Record<string, unknown>; proposal: Record<string, unknown>; analysis?: unknown } & Record<string, unknown>;
  provenance: { agent_id: string; design_revision_id: string; context_sha256: string; status: string } & Record<string, unknown>;
};
const agentsPath = (studyId: string) => `${studyPath(studyId)}/research/agent-jobs`;
export const researchAgents = {
  design: (studyId: string, revisionId: string) => request<DesignRevision & { content: Record<string, unknown> }>("GET", `${studyPath(studyId)}/design/revisions/${enc(revisionId)}`),
  /** `promptVersion` runs a stored prompt version instead of the active one (organization administrators; ADR 0020). */
  start: (studyId: string, revisionId: string, action: ResearchAgentAction, instruction = "", promptVersion?: number) =>
    request<ResearchAgentJob>("POST", agentsPath(studyId), {
      design_revision_id: revisionId, action, instruction, ...(promptVersion === undefined ? {} : { prompt_version: promptVersion }),
    }),
  jobs: async (studyId: string) => {
    const jobs = await request<unknown>("GET", agentsPath(studyId));
    if (!Array.isArray(jobs) || jobs.some((j) => !j || typeof j.run_id !== "string" || typeof j.status !== "string" || !Array.isArray(j.steps))) {
      throw new Error("Seznam AI kroků má neplatný formát. Zkuste jej načíst znovu.");
    }
    return jobs as ResearchAgentJob[];
  },
  job: (studyId: string, jobId: string) => request<ResearchAgentJob>("GET", `${agentsPath(studyId)}/${enc(jobId)}`),
  cancel: (studyId: string, jobId: string) => request<ResearchAgentJob>("POST", `${agentsPath(studyId)}/${enc(jobId)}/cancel`),
  resume: (studyId: string, jobId: string) => request<ResearchAgentJob>("POST", `${agentsPath(studyId)}/${enc(jobId)}/resume`),
  result: (studyId: string, jobId: string) => request<ResearchAgentResult>("GET", `${agentsPath(studyId)}/${enc(jobId)}/result`),
  accept: (studyId: string, jobId: string, revisionId: string) => request<DesignRevision>("POST", `${agentsPath(studyId)}/${enc(jobId)}/accept`, { expected_revision_id: revisionId }),
};

// ---- the settings page: every control and how it is set -------------------
// Mirrors apps/api/src/aia_api/schemas/settings.py and the administrative routes
// in routers/scope.py. Enum values are never listed here: they arrive in
// `vocabularies`, so a domain change cannot leave a stale copy in the browser.

export type SettingControl = "API" | "DEPLOYMENT" | "CODE" | "INVARIANT";

/** `null` means "not configured" -- never zero, never false. */
export type SettingValue = string | number | boolean | string[] | null;

export type SettingItem = { key: string; value: SettingValue; control: SettingControl; source: string; unit: string | null };
export type SettingGroup = { key: string; items: SettingItem[] };

/** NATIVE: AIA's runtime calls it. HISTORICAL: only read from records, never offered. */
export type ProviderUse = "NATIVE" | "HISTORICAL";
export type ProviderEntry = { id: string; label: string; paid: boolean; use: ProviderUse };

/** One thing AIA's runtime does with a model, from code (schemas/settings.py NativeActivity). */
export type NativeActivity = {
  key: string;
  step_kind: string;
  capabilities: string[];
  versions: { name: string; value: string }[];
  switches: string[];
  actions: string[];
};

/** What powers AIA's model calls, from code: never a connection or health claim. */
export type NativeRuntime = {
  providers: ProviderEntry[];
  credential: "INSTANCE_ROLE";
  switch: string;
  activities: NativeActivity[];
  unused_capabilities: string[];
};

export type Vocabularies = {
  organization_roles: string[];
  scope_roles: { role: string; permissions: string[] }[];
  permissions: string[];
  client_statuses: string[];
  study_statuses: string[];
  providers: ProviderEntry[];
  /** Every one historical: the prototype's per-project rule. */
  provider_policies: string[];
  model_capabilities: string[];
  data_classes: string[];
  research_stages: { id: string; label: string | null }[];
  simulation_stages: { id: string; label: string | null }[];
};

export type SettingsDocument = {
  organization_id: string;
  your_role: string;
  may_administer: boolean;
  groups: SettingGroup[];
  ai_runtime: NativeRuntime;
  vocabularies: Vocabularies;
};

export type Member = { user_id: string; email: string; display_name: string; is_active: boolean; organization_role: string };

export type AdminClient = {
  client_id: string; slug: string; name: string; status: string; reference: string; study_count: number; created_at: string | null;
};

export type SelfApprovalLevels = {
  organization: boolean | null;
  clients: { client_id: string; allowed: boolean }[];
  studies: { study_id: string; client_id: string; allowed: boolean }[];
};

export type SelfApprovalPolicy = { allowed: boolean; source: "default" | "organization" | "client" | "study" };

export type AuditEntry = {
  event_id: number; action: string; client_id: string | null; study_id: string | null; subject_user_id: string | null;
  actor_id: string | null; role: string | null; reason: string; payload: Record<string, unknown>; created_at: string | null;
};

// ---- system prompts (routers/system_prompts.py, ADR 0020) -------------------

/** What runs for a prompt: "baseline" is the wording shipped in code, "stored" an administrator's edit. */
export type PromptActive = {
  version_number: number | null; label: string; origin: "baseline" | "stored"; text_sha256: string;
  activated_by: string | null; activated_at: string | null; reason: string;
};
export type PromptSlotSummary = {
  prompt_id: string; family: string;
  /** Wired: a running step reads it, so an edit takes effect. Otherwise `unwired_reason` says why not. */
  wired: boolean; unwired_reason: string | null;
  baseline_version: string; baseline_chars: number;
  active: PromptActive; version_count: number; latest_number: number | null;
};
export type PromptVersion = {
  version_number: number; label: string; text: string; text_sha256: string;
  /** The hash an operator lists in AIA_AI_MATERIAL_CLASSIFICATIONS to classify this exact text more strictly. */
  material_sha256: string;
  /** The author's recorded declaration that the text holds no client data; null on a version saved before declarations existed. */
  declared_class: string | null; declared_by: string | null; declared_at: string | null;
  based_on: string; note: string; created_by: string; created_at: string;
};
export type PromptActivation = {
  activation_id: number; version_number: number | null; label: string | null;
  activated_by: string; reason: string; activated_at: string;
};
export type PromptSlotDetail = PromptSlotSummary & {
  /** The code-owned text placed before the instruction. Shown, never editable. */
  fixed_prefix: string;
  /** The wording this code ships: the editable part's baseline. */
  baseline_text: string;
  required_literals: string[]; max_chars: number;
  /** The clients a draft may be tried on (the deployment's fictional list); empty means none. */
  draft_test_client_ids: string[];
  versions: PromptVersion[]; history: PromptActivation[];
};

export const admin = {
  prompts: () => request<PromptSlotSummary[]>("GET", "/api/v1/system-prompts"),
  prompt: (promptId: string) => request<PromptSlotDetail>("GET", `/api/v1/system-prompts/${enc(promptId)}`),
  // Saving is the author's declaration that the text holds no client data (ADR 0020 decision 8): the
  // editor says so next to the button, and the API requires the field and records who sent it.
  savePrompt: (promptId: string, body: { text: string; note: string; based_on: string | null }) =>
    request<PromptVersion>("POST", `/api/v1/system-prompts/${enc(promptId)}/versions`, { ...body, declares_no_client_data: true }),
  /** `versionNumber` null returns to the wording shipped in code. */
  activatePrompt: (promptId: string, versionNumber: number | null, reason: string) =>
    request<PromptActive>("PUT", `/api/v1/system-prompts/${enc(promptId)}/active`, { version_number: versionNumber, reason }),
  settings: () => request<SettingsDocument>("GET", "/api/v1/settings"),
  members: () => request<Member[]>("GET", "/api/v1/members"),
  addMember: (body: { email: string; role: string; display_name: string }) => request<Member>("POST", "/api/v1/members", body),
  clients: () => request<AdminClient[]>("GET", "/api/v1/clients?include_archived=true"),
  setClientStatus: (clientId: string, status: string) =>
    request<AdminClient>("PUT", `/api/v1/clients/${enc(clientId)}/status`, { status }),
  studies: () => request<Study[]>("GET", "/api/v1/studies?include_archived=true"),
  study: (studyId: string) => request<Study>("GET", `/api/v1/studies/${enc(studyId)}`),
  setStudyStatus: (studyId: string, status: string) => request<Study>("PUT", `/api/v1/studies/${enc(studyId)}/status`, { status }),
  setStudyBudget: (studyId: string, budgetUsd: number) =>
    request<Study>("PUT", `/api/v1/studies/${enc(studyId)}/budget`, { budget_usd: budgetUsd }),
  selfApproval: () => request<SelfApprovalLevels>("GET", "/api/v1/self-approval"),
  setSelfApproval: (body: { allowed: boolean | null; client_id?: string; study_id?: string }) =>
    request<SelfApprovalPolicy>("PUT", "/api/v1/self-approval", body),
  audit: (limit = 50) => request<AuditEntry[]>("GET", `/api/v1/access-audit?limit=${limit}`),
};
