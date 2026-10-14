"use client";

// The real AIA API, same origin, bearer id token. Response shapes mirror the
// API's Pydantic models (apps/api/src/aia_api/schemas); the client renders what
// the server computed and decides nothing (ARCHITECTURE.md §2).

import type { RegisterEntry } from "@/lib/object-map-view";
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

/** A stored report's bytes and the artifact they are (X-AIA-Artifact-Id), for its approval. */
export type StoredDownload = { blob: Blob; artifactId: string | null; reviewState: string | null };

async function requestStored(path: string): Promise<StoredDownload> {
  const response = await send("GET", path);
  if (!response.ok) throw await refusal(response);
  return {
    blob: await response.blob(),
    artifactId: response.headers.get("X-AIA-Artifact-Id"),
    reviewState: response.headers.get("X-AIA-Review-State"),
  };
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
  /** On the studies list, for a caller who may read the client's knowledge: what this study proposed to it. */
  knowledge?: { approved: number; proposed: number; rejected: number } | null;
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

/** What a client's tabs count; the knowledge counts are null when the caller may not read them. */
export type ClientCounts = {
  research: number;
  simulations: number;
  pending_proposals: number | null;
  datasets: number | null;
};

export type ClientWorkspace = {
  client_id: string;
  name: string;
  slug: string;
  status: string;
  your_role: string | null;
  permissions: string[];
  /** Present on GET /clients/{id}; the overview's copy of the client carries none. */
  counts?: ClientCounts | null;
  /** Whether a proposer may accept their own proposal here, and which level decided it. */
  self_approval_allowed?: boolean | null;
  self_approval_source?: string | null;
};

/** The client's profile (client-workspace C5): on its record, read by no model. Empty is not filled in. */
export type ClientProfileFields = { short_code: string; industry: string; market: string; description: string };
export type ClientContact = { contact_id: string; name: string; role: string; email: string; receives_reports: boolean };
export type ContactWrite = Omit<ClientContact, "contact_id">;
export type ProfileChange = { action: string; at: string | null; fields: string[]; contact_name: string | null };
export type ClientProfile = ClientProfileFields & { contacts: ClientContact[]; history: ProfileChange[] };

export type KnowledgeSection = "sources" | "knowledge" | "dimensions" | "audiences" | "data";

export type KnowledgeItem = {
  item_id: string;
  kind: string;
  title: string;
  summary: string;
  content: Record<string, unknown>;
  revision: number;
  modified_at: string | null;
  /** Where people filed it: organization, not knowledge (no model sees it). */
  folder_id?: string | null;
  label_ids?: string[];
};

export type LabelColour = "BLUE" | "TEAL" | "GREEN" | "ORANGE" | "VIOLET" | "SLATE";
export const LABEL_COLOURS: readonly LabelColour[] = ["BLUE", "TEAL", "GREEN", "ORANGE", "VIOLET", "SLATE"];
export type KnowledgeFolder = { folder_id: string; name: string; item_count: number };
export type KnowledgeLabel = { label_id: string; name: string; colour: LabelColour; item_count: number };
/** Which items to show: a folder ("unfiled": in none) and a label, beside section and search. */
export type KnowledgeFiling = { folder?: string; label?: string };
/** `folder_id` left out keeps each item's folder; null takes the items out of any. */
export type Placement = { item_ids: string[]; folder_id?: string | null; add_labels?: string[]; remove_labels?: string[] };

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
  /** The item revision an edit was written from; null for a new item, or unknown. */
  base_revision: number | null;
  yours: boolean;
};

export type KnowledgeSummary = {
  context_revision: number;
  items_by_kind: Record<string, number>;
  pending_proposals: number;
  last_approved_at: string | null;
  /** Active items unchanged for over a year, and active items in no folder. */
  stale_items?: number;
  unfiled_items?: number;
};

/** One recent revision of the client's knowledge: a study's finding, a person's writing, or a decided proposal. */
export type KnowledgeChange = { item_id: string; title: string; revision: number; origin: "STUDY" | "PERSON" | "PROPOSAL"; at: string | null };

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
  recent_changes?: KnowledgeChange[];
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

// GET /api/v1/population: the shared population's registry, read-only (population-operations P2).
export type PopulationVersionStatus = "REGISTERED" | "STATIC_REFERENCE" | "LIVE_CURRENT" | "SUPERSEDED";
export type PopulationVersion = {
  version_id: string;
  label: string;
  content_sha256: string;
  row_count: number;
  column_count: number;
  parent_version_id: string | null;
  status: PopulationVersionStatus;
  runtime_eligible: boolean;
  companions_attached: boolean;
  imported_at: string;
  imported_by: string;
  provenance: string;
  /** null on a shared version; on an owned child, the client it was materialized for. */
  owner_client_id: string | null;
  /** null on a shared version; on an owned child, the hash of the fields it adds. */
  extension_sha256: string | null;
  /** null on a shared version (or a child whose record carries none); on an owned child, its outcome. */
  materialized?: PopulationMaterialized | null;
};
/** What an owned child adds and what its derivation reached (P4d4): target beside achieved. */
export type PopulationMaterialized = {
  dimension_id: string;
  kind: "binary" | "scale_1_10";
  definition_sha256: string;
  method: string;
  target: number;
  achieved: number;
  /** Within the kind's tolerance; never presumed. */
  target_met: boolean;
  usable_predictors: string[];
};
export type PopulationRecord = {
  population_id: string;
  kind: "STATIC" | "LIVE";
  current_version_id: string;
  established_at: string;
  established_by: string;
};
export type PopulationPromotion = {
  population_id: string;
  from_version_id: string | null;
  to_version_id: string;
  actor_id: string;
  reason: string;
  promoted_at: string;
};
export type PopulationRegistry = {
  dataset_id: string;
  contract_id: string;
  versions: PopulationVersion[];
  populations: PopulationRecord[];
  history: PopulationPromotion[];
};

// GET /api/v1/clients/{id}/memory/search (project memory M1).
export type MemoryField =
  | "name"
  | "title"
  | "goal"
  | "decision_use"
  | "research_questions"
  | "objectives"
  | "sections"
  | "dimensions";
export type MemoryHit = {
  study_id: string;
  name: string;
  kind: StudyKind;
  status: string;
  modified_at: string | null;
  /** design: its latest Design Revision; draft: its working content (no Design Revision); name: its name alone. */
  source: "design" | "draft" | "name";
  design_revision: number | null;
  matches: { field: MemoryField; texts: string[] }[];
};

// GET /api/v1/population/versions/{id}/characteristics (population-operations P7c): what a
// version is made of, from the dictionary it keeps; no respondent row.
export type PopulationFieldUse =
  | "AUDIENCE_FILTERING"
  | "PERSONA_CONSTRUCTION"
  | "AGGREGATE_ANALYSIS"
  | "SIMULATION"
  | "CLIENT_MEASURED_CLAIM"
  | "CLIENT_MODELLED_CLAIM"
  | "WEIGHTING";
export type PopulationUseAnswer = { use: PopulationFieldUse; allowed: boolean; reason: string; obligations: string[] };
export type PopulationField = {
  field: string;
  block: string;
  source: string;
  evidence_status: string;
  provenance_class: string;
  production_grade: string;
  recommended_use: string;
  description: string;
  persona_eligible: boolean;
  is_weight: boolean;
  derived: boolean;
  uses: PopulationUseAnswer[];
  /** A field an owned child adds: modelled values, its uses fixed. */
  materialized: boolean;
};
export type PopulationWeight = {
  role: string;
  column: string;
  is_default: boolean;
  expected_total: number | null;
  tolerance: number | null;
};
export type PopulationSubpanel = {
  key: string;
  name: string;
  description: string;
  filter: { field: string; minimum: number | null; maximum: number | null; equals: number | null };
  focus_domains: string[];
  status: string;
  support_tier: string;
  /** 18.6.6's own counts, on `subpanels_measured_on`; never AIA's measurement. */
  measured_by_18_6_6: {
    rows: number;
    weighted_population: number;
    unique_core_donors: number;
    effective_core_donors: number;
    max_core_reuse: number;
  };
  /** null while the version's dictionary is not kept: unknown, never usable. */
  usable: boolean | null;
  reason: string | null;
};
export type PopulationCharacteristics = {
  version_id: string;
  label: string;
  dictionary_sha256: string;
  dictionary_kept: boolean;
  weights: PopulationWeight[];
  blocks: { block: string; fields: number }[];
  fields: PopulationField[];
  subpanels: PopulationSubpanel[];
  subpanels_measured_on: string;
  subpanels_measured_under_weight: string;
  subpanel_note: string;
  owner_client_id: string | null;
  extension_sha256: string | null;
};

// GET /api/v1/studies/{id}/design/source, POST /api/v1/clients/{id}/memory/reuse (project memory M3).
export type DesignSourceLabels = {
  synthetic: boolean;
  draft: boolean;
  never_run: boolean;
  unlabelled_data: boolean;
  run_ids: string[];
  report_artifact_ids: string[];
  /** Some run answered AI respondents built from its population (ADR 0024); absent from an older API. */
  modelled?: boolean;
};
export type DesignSource = {
  study_id: string;
  revision_id: string;
  source_study_id: string;
  source_revision_id: string;
  source_revision: number;
  source_content_sha256: string;
  labels: DesignSourceLabels;
  created_by: string;
  created_at: string;
};
export type MemoryReuse = {
  source_study_id: string;
  source_revision_id: string;
  target_study_id?: string;
  new_study_name?: string;
};
export type MemoryReused = { study_id: string; created_study: boolean; revision: DesignRevision; source: DesignSource };

export type Me = { user_id: string; email: string | null; organization_role: string; may_administer: boolean };

const enc = encodeURIComponent;
const query = (q: Record<string, string | undefined>) => {
  const p = new URLSearchParams(Object.entries(q).filter((e): e is [string, string] => !!e[1]));
  const s = p.toString();
  return s ? `?${s}` : "";
};

// GET /api/v1/population/audience-catalogue (panel-grounded-respondents 6b): what a study's
// audience may be filtered by -- LIVE's kept factor catalogue (the research-only factors not
// sent) and the 18 built-in subpanels as filters. Counts are rows, unweighted, as 18.6.6 counted.
export type AudienceCatalogueFactor = {
  id: string;
  column: string;
  label: string;
  category: string;
  category_label: string;
  kind: "numeric" | "binary" | "category";
  status: string;
  filterable: boolean;
  sensitive: boolean;
  source: string;
  non_null: number;
  min?: number | null;
  max?: number | null;
  p10?: number | null;
  p90?: number | null;
  scale_hint?: string | null;
  values?: { value: string; count: number }[] | null;
  /** The version's field policy for audience filtering; a refused factor is not a filter. */
  policy_allowed: boolean;
  policy_reason: string;
};
export type AudienceCatalogueSubpanel = {
  key: string;
  name: string;
  description: string;
  filters: Record<string, unknown>;
  status: string;
  support_tier: string;
  measured_by_18_6_6: { rows: number; weighted_population: number; unique_core_donors: number; effective_core_donors: number; max_core_reuse: number };
  /** null while the version's dictionary is not kept: unknown, never usable. */
  usable: boolean | null;
  reason: string | null;
};
export type AudienceCatalogue = {
  version_id: string;
  version_label: string;
  catalogue_version: string;
  categories: { id: string; label: string; description: string; count: number; filterable_count: number }[];
  factors: AudienceCatalogueFactor[];
  filterable_count: number;
  factor_count: number;
  logic: string;
  subpanels: AudienceCatalogueSubpanel[];
  subpanels_measured_on: string;
  subpanel_note: string;
};

// POST /api/v1/population/audience-preview (6c): counted by the API over LIVE through the
// run's own functions; counts and the sampler's verdict, never a row.
export type AudiencePreviewVerdict = {
  ok: boolean;
  reason?: string | null;
  message?: string | null;
  reasons?: string[] | null;
  status?: string | null;
  sample_donors?: number | null;
  effective_n?: number | null;
};
export type AudiencePreview = {
  version_id: string;
  version_label: string;
  population_rows: number;
  selected_rows: number | null;
  selected_donors: number | null;
  filters_applied: Record<string, unknown> | null;
  audience: AudiencePreviewVerdict;
  n: number | null;
  sample: AudiencePreviewVerdict | null;
  seed: number;
};

export const population = {
  registry: () => request<PopulationRegistry>("GET", "/api/v1/population"),
  characteristics: (versionId: string) =>
    request<PopulationCharacteristics>("GET", `/api/v1/population/versions/${enc(versionId)}/characteristics`),
  audienceCatalogue: () => request<AudienceCatalogue>("GET", "/api/v1/population/audience-catalogue"),
  audiencePreview: (filters: Record<string, unknown>, n: number | null) =>
    request<AudiencePreview>("POST", "/api/v1/population/audience-preview", { filters, n }),
};

export const workspace = {
  me: () => request<Me>("GET", "/api/v1/workspace/me"),
  clients: () => request<ClientCard[]>("GET", "/api/v1/workspace/clients"),
  startClient: (name: string) => request<ClientWorkspace>("POST", "/api/v1/workspace/clients", { name }),
  client: (clientId: string) => request<ClientWorkspace>("GET", `/api/v1/clients/${enc(clientId)}`),
  overview: (clientId: string) => request<ClientOverview>("GET", `/api/v1/clients/${enc(clientId)}/overview`),
  studies: (clientId: string, kind?: StudyKind) =>
    request<WorkspaceStudy[]>("GET", `/api/v1/clients/${enc(clientId)}/studies${query({ kind })}`),
  /** Project memory M1: this client's past studies whose name or design holds every word of q. */
  memorySearch: (clientId: string, q: string) =>
    request<MemoryHit[]>("GET", `/api/v1/clients/${enc(clientId)}/memory/search${query({ q })}`),
  /** Project memory M3: start a new or empty research study of this client from a past design. */
  memoryReuse: (clientId: string, body: MemoryReuse) =>
    request<MemoryReused>("POST", `/api/v1/clients/${enc(clientId)}/memory/reuse`, body),
  startStudy: (clientId: string, name: string, kind: StudyKind) =>
    request<WorkspaceStudy>("POST", `/api/v1/clients/${enc(clientId)}/studies`, { name, kind }),
  knowledge: (clientId: string, section?: KnowledgeSection, q?: string, filing: KnowledgeFiling = {}) =>
    request<KnowledgeItem[]>("GET", `/api/v1/clients/${enc(clientId)}/knowledge${query({ section, q, folder: filing.folder, label: filing.label })}`),
  profile: (clientId: string) => request<ClientProfile>("GET", `/api/v1/clients/${enc(clientId)}/profile`),
  saveProfile: (clientId: string, fields: ClientProfileFields) =>
    request<ClientProfile>("PUT", `/api/v1/clients/${enc(clientId)}/profile`, fields),
  addContact: (clientId: string, contact: ContactWrite) =>
    request<ClientContact>("POST", `/api/v1/clients/${enc(clientId)}/contacts`, contact),
  changeContact: (clientId: string, contactId: string, contact: ContactWrite) =>
    request<ClientContact>("PUT", `/api/v1/clients/${enc(clientId)}/contacts/${enc(contactId)}`, contact),
  removeContact: (clientId: string, contactId: string) =>
    request<void>("DELETE", `/api/v1/clients/${enc(clientId)}/contacts/${enc(contactId)}`),
  folders: (clientId: string) => request<KnowledgeFolder[]>("GET", `/api/v1/clients/${enc(clientId)}/knowledge/folders`),
  createFolder: (clientId: string, name: string) =>
    request<KnowledgeFolder>("POST", `/api/v1/clients/${enc(clientId)}/knowledge/folders`, { name }),
  renameFolder: (clientId: string, folderId: string, name: string) =>
    request<KnowledgeFolder>("PUT", `/api/v1/clients/${enc(clientId)}/knowledge/folders/${enc(folderId)}`, { name }),
  deleteFolder: (clientId: string, folderId: string) =>
    request<void>("DELETE", `/api/v1/clients/${enc(clientId)}/knowledge/folders/${enc(folderId)}`),
  labels: (clientId: string) => request<KnowledgeLabel[]>("GET", `/api/v1/clients/${enc(clientId)}/knowledge/labels`),
  createLabel: (clientId: string, name: string, colour: LabelColour) =>
    request<KnowledgeLabel>("POST", `/api/v1/clients/${enc(clientId)}/knowledge/labels`, { name, colour }),
  changeLabel: (clientId: string, labelId: string, change: { name?: string; colour?: LabelColour }) =>
    request<KnowledgeLabel>("PUT", `/api/v1/clients/${enc(clientId)}/knowledge/labels/${enc(labelId)}`, change),
  deleteLabel: (clientId: string, labelId: string) =>
    request<void>("DELETE", `/api/v1/clients/${enc(clientId)}/knowledge/labels/${enc(labelId)}`),
  place: (clientId: string, placement: Placement) =>
    request<KnowledgeItem[]>("PUT", `/api/v1/clients/${enc(clientId)}/knowledge/placement`, placement),
  revisions: (clientId: string, itemId: string) =>
    request<KnowledgeRevision[]>("GET", `/api/v1/clients/${enc(clientId)}/knowledge/items/${enc(itemId)}/revisions`),
  proposals: (clientId: string, status?: Proposal["status"]) =>
    request<Proposal[]>("GET", `/api/v1/clients/${enc(clientId)}/knowledge/proposals${query({ status })}`),
  /** Add knowledge, or (with `item_id`) edit an item: a new revision, or a proposal where self-approval is off. */
  propose: (
    clientId: string,
    body: { kind: string; title: string; summary?: string; item_id?: string; base_revision?: number; content?: Record<string, unknown> },
  ) =>
    request<Proposal>("POST", `/api/v1/clients/${enc(clientId)}/knowledge/proposals`, body),
  /** `reviewedRevision`: the item's current revision, read by the reviewer, to approve an edit of an older one over it. */
  decide: (clientId: string, proposalId: string, approve: boolean, note = "", reviewedRevision?: number) =>
    request<Proposal>("POST", `/api/v1/clients/${enc(clientId)}/knowledge/proposals/${enc(proposalId)}/decision`, {
      approve,
      note,
      ...(reviewedRevision === undefined ? {} : { reviewed_revision: reviewedRevision }),
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
/** One entry of a run's event feed, read after a cursor (lib/step-activity.ts folds them). */
export type RunEvent = {
  event_id: number;
  step_id: string | null;
  attempt_id: string | null;
  event_type: string;
  level: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string | null;
};
const eventsQuery = (since: number) => `?since=${encodeURIComponent(String(since))}`;
export type ResearchStep = {
  /** The id the run's events name. */
  step_id: string;
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
  /** An analysis step's stored outcome: its step SUCCEEDED either way. `null` for other steps. */
  analysis_outcome?: "COMPLETED" | "BLOCKED" | null;
  /** How the API reads `data_origin`: SIMULATED, MODELLED or UNKNOWN; absent from an older API. */
  data_origin_kind?: string | null;
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
  /** The population the run recorded (population-operations P3); absent or null: none. */
  population?: ResearchRunPopulation | null;
  /** The methods the run pinned when it started (methodology-tab Z1); absent from an older API. */
  methodology?: ResearchRunMethodology;
};
/** One pinned method: its name, and whether it is a version stored on the Metodika tab. */
/** `name: null`: the run recorded a pin that cannot be read as a name; never a guess. */
export type ResearchRunMethod = { name: string | null; stored: boolean };
export type ResearchRunMethodology = {
  sociomap: ResearchRunMethod; support: ResearchRunMethod; aggregation: ResearchRunMethod;
  /** How AI respondents' answers were drawn (methodology-tab R1d); absent from an older API. */
  response?: ResearchRunMethod;
  /** `true`: not 18.6.6's response process; `null`: its pin cannot be read, never guessed. */
  response_deviates?: boolean | null;
};
/** What a run recorded about its population, and whether fieldwork read it (never, today). */
export type ResearchRunPopulation = {
  population_id: string | null;
  version_id: string;
  version_label: string;
  read_by_fieldwork: boolean;
};
/** A run as the Study's list gives it: its state, without its steps or artifacts. */
export type ResearchRunSummary = Omit<ResearchRun, "steps" | "artifact_ids">;

export type ResearchAnalysis = {
  run_id: string;
  complete: boolean;
  internal_only: true;
  synthetic: boolean;
  modelled?: boolean;
  data_origin_kind?: string | null;
  /** The aggregate the modules read is no longer 18.6.6's port (methodology-tab G3c);
   *  `null` (or absent, from an API before it) when it is the port. */
  aggregation_deviation?: Record<string, unknown> | null;
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
  modelled?: boolean;
  data_origin_kind?: string | null;
  /** The stored DOCX rendered as PDF; null when this run's worker made none (B3). */
  pdf?: { state: "READY"; artifact_id: string; size_bytes: number } | { state: string; reason?: string | null } | null;
};

const studyPath = (studyId: string) => `/api/v1/studies/${enc(studyId)}`;

export const research = {
  submitDesign: (studyId: string, content: unknown, sourceStage: string) =>
    request<DesignRevision>("POST", `${studyPath(studyId)}/design/revisions`, { content, source_stage: sourceStage }),
  revisions: (studyId: string) =>
    request<{ items: DesignRevision[] }>("GET", `${studyPath(studyId)}/design/revisions`).then((r) => r.items),
  /** Where the study's design came from, when it was reused (404: it was not). */
  designSource: (studyId: string) => request<DesignSource>("GET", `${studyPath(studyId)}/design/source`),
  /** One Design Revision with its content (project memory M2c reads a past study's). */
  revision: (studyId: string, revisionId: string) =>
    request<DesignRevision & { content: Record<string, unknown> }>("GET", `${studyPath(studyId)}/design/revisions/${enc(revisionId)}`),
  readiness: (studyId: string, revisionId: string) =>
    request<Readiness>("GET", `${studyPath(studyId)}/research/readiness${query({ design_revision_id: revisionId })}`),
  /**
   * `confirmCostUsd` is the person's yes to the ceiling the server showed, when the study's limit asks for one.
   * `populationVersionId` runs over one of the study's client's materialized children instead of LIVE (P4d4c).
   */
  start: (studyId: string, revisionId: string, confirmCostUsd?: number, populationVersionId?: string) =>
    request<ResearchRun>("POST", `${studyPath(studyId)}/research/runs`, {
      design_revision_id: revisionId,
      ...(confirmCostUsd === undefined ? {} : { confirm_cost_usd: confirmCostUsd }),
      ...(populationVersionId === undefined ? {} : { population_version_id: populationVersionId }),
    }),
  /** Set, or with `null` clear, the cost at which starting a run asks for confirmation. */
  setSpendConfirm: (studyId: string, limitUsd: number | null) =>
    request<Study>("PUT", `${studyPath(studyId)}/spend-confirm`, { limit_usd: limitUsd }),
  runs: (studyId: string) =>
    request<{ items: ResearchRunSummary[] }>("GET", `${studyPath(studyId)}/research/runs`).then((r) => r.items),
  run: (studyId: string, runId: string) => request<ResearchRun>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}`),
  events: (studyId: string, runId: string, since = 0) =>
    request<RunEvent[]>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}/events${eventsQuery(since)}`),
  cancel: (studyId: string, runId: string) =>
    request<ResearchRun>("POST", `${studyPath(studyId)}/research/runs/${enc(runId)}/cancel`),
  retry: (studyId: string, runId: string, confirmCostUsd?: number) =>
    request<ResearchRun>(
      "POST",
      `${studyPath(studyId)}/research/runs/${enc(runId)}/retry`,
      confirmCostUsd === undefined ? undefined : { confirm_cost_usd: confirmCostUsd },
    ),
  /** The modules a finished run may ask again (`retryAnalysis`), read from its stored outcomes. */
  retryableModules: (studyId: string, runId: string) =>
    request<{ run_id: string; modules: string[] }>("GET", `${studyPath(studyId)}/research/runs/${enc(runId)}/analysis/retryable`).then((r) => r.modules),
  /** Ask a finished run's failed analysis modules again: a new run over the same dataset, no new fieldwork. */
  retryAnalysis: (studyId: string, runId: string, confirmCostUsd?: number) =>
    request<ResearchRun>(
      "POST",
      `${studyPath(studyId)}/research/runs/${enc(runId)}/analysis/retry`,
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
  /** Which Sociomap methods are approved, by exact spec (complete-study-report B4). */
  sociomapRegister: (studyId: string) =>
    request<{ entries: RegisterEntry[] }>("GET", `${studyPath(studyId)}/research/sociomap-register`),
  /** The client report of a modelled run (complete-study-report B5c); 409 names why a run has none. */
  downloadClientReport: (studyId: string, runId: string) =>
    requestStored(`${studyPath(studyId)}/research/runs/${enc(runId)}/report/client/download`),
  downloadReportPdf: (studyId: string, runId: string) =>
    requestBlob(`${studyPath(studyId)}/research/runs/${enc(runId)}/report/pdf/download`),
  /** A person approves a stored report of the run (internal only; recorded in the ledger). */
  approveReport: (studyId: string, runId: string, artifactId: string, note = "") =>
    request<{ run_id: string; artifact_id: string; review_state: "APPROVED_INTERNAL"; internal_only: true }>(
      "POST", `${studyPath(studyId)}/research/runs/${enc(runId)}/report/approve`, { artifact_id: artifactId, note },
    ),
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
  steps: { step_id: string; node_key: string; status: string; waiting_reason: string | null; error_message: string | null; started_at?: string | null }[];
  actual_cost_usd: number | null;
  purpose?: string | null;
  target?: { kind: string; research_run_id?: string } | null;
  title?: string | null;
};
export type DeepResearchBundle = {
  quality_status: string; fictional_client: boolean; client_facing: false;
  accepted: { evidence: { claim: string; quote: string; source_ref: string }; score: { score: number; source_class: string } }[];
  quarantined: { reason: string; detail?: string }[];
  snapshots: { snapshot_id: string; url: string; title: string; retrieval_mode: string }[];
  counts: Record<string, number>; sha256: string;
  synthesis?: { check: { summary: string | null; findings: { subject_key: string; text: string; evidence_ids: string[] }[]; gaps: string[]; limitations: string[]; status: string }; brief?: { gaps: { need: string; reason: string }[] } | null } | null;
  origins?: string[];
};
const deepPath = (studyId: string) => `${studyPath(studyId)}/deep-research/runs`;
export const deepResearch = {
  interpret: (studyId: string, runId: string, analysisArtifactId: string, preset: "QUICK" | "STANDARD", confirmCostUsd?: number) =>
    request<DeepResearchRun>("POST", `${deepPath(studyId)}/interpretation`, {
      target: { kind: "ANALYSIS_MODULE", research_run_id: runId, analysis_artifact_id: analysisArtifactId, module_id: "research_questions" },
      preset_name: preset, channels: ["WEB"], title: "Literární rešerše pro interpretaci studie",
      ...(confirmCostUsd === undefined ? {} : { confirm_cost_usd: confirmCostUsd }),
    }),
  downloadContextReport: (studyId: string, runId: string, deepRunId: string) =>
    requestStored(`${studyPath(studyId)}/research/runs/${enc(runId)}/report/context/download${query({ deep_research_run_id: deepRunId })}`),
  start: (studyId: string, revisionId: string) =>
    request<DeepResearchRun>("POST", deepPath(studyId), { design_revision_id: revisionId, preset_name: "QUICK", channels: ["WEB"] }),
  runs: (studyId: string) => request<DeepResearchRun[]>("GET", deepPath(studyId)),
  events: (studyId: string, runId: string, since = 0) =>
    request<RunEvent[]>("GET", `${deepPath(studyId)}/${enc(runId)}/events${eventsQuery(since)}`),
  bundle: (studyId: string, runId: string) => request<DeepResearchBundle>("GET", `${deepPath(studyId)}/${enc(runId)}/bundle`),
  cancel: (studyId: string, runId: string) => request<DeepResearchRun>("POST", `${deepPath(studyId)}/${enc(runId)}/cancel`),
  retry: (studyId: string, runId: string, confirmCostUsd?: number) => request<DeepResearchRun>("POST", `${deepPath(studyId)}/${enc(runId)}/retry`, confirmCostUsd === undefined ? undefined : { confirm_cost_usd: confirmCostUsd }),
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
  events: (studyId: string, jobId: string, since = 0) =>
    request<RunEvent[]>("GET", `${agentsPath(studyId)}/${enc(jobId)}/events${eventsQuery(since)}`),
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
  /** Read whatever `switch` says; on without a switch named before it, the worker does not start. */
  strict_switches: string[];
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

// ---- Deep Research settings (routers/deep_research_settings.py, ADR 0022) ---------------

/** A JSON value a setting holds: a number, text, yes/no, a list of text, or null (unknown). */
export type DrSettingValue = number | string | boolean | string[] | null;

/** One policy value: what it is, its bounds, and what a run enqueued now would use. */
export type DrSetting = {
  key: string; group: string; type: string; label: string; unit: string;
  minimum: number | null; maximum: number | null;
  /** A cap: an approved value may lower the code's default and never raise it. */
  lower_only: boolean; required_for_live: boolean;
  /** The value shapes a run's result, so runs made under different values share no work. */
  method: boolean;
  /** The code's proposed default; null where the code holds nothing (unknown, never zero). */
  default: DrSettingValue; default_source: string;
  value: DrSettingValue; origin: "approved" | "proposed_default"; version: number | null;
  approved_by: string | null; approved_at: string | null;
  version_count: number; latest_number: number | null;
};
export type DrSettingsOverview = {
  catalogue_version: string; may_administer: boolean;
  /** Every setting live still needs approved (a status counts only as "approved"). */
  missing_for_live: string[];
  settings: DrSetting[];
};
export type DrSettingVersion = {
  version_number: number; value: DrSettingValue; value_sha256: string; source_url: string; note: string;
  created_by: string; created_at: string;
};
/** `version_number` null: the approval was withdrawn and the code's default came back into force. */
export type DrSettingApproval = { approval_id: number; version_number: number | null; approved_by: string; reason: string; approved_at: string };
export type DrSettingDetail = DrSetting & { versions: DrSettingVersion[]; history: DrSettingApproval[] };

const DR_SETTINGS = "/api/v1/deep-research/settings";

/** Read by any member; proposing and approving are an administrator's (the API decides). */
export const deepResearchSettings = {
  list: () => request<DrSettingsOverview>("GET", DR_SETTINGS),
  get: (key: string) => request<DrSettingDetail>("GET", `${DR_SETTINGS}/${enc(key)}`),
  propose: (key: string, body: { value: DrSettingValue; source_url: string; note: string }) =>
    request<DrSettingVersion>("POST", `${DR_SETTINGS}/${enc(key)}/versions`, body),
  /** `versionNumber` null returns the setting to the code's proposed default. */
  approve: (key: string, versionNumber: number | null, reason: string) =>
    request<DrSetting>("PUT", `${DR_SETTINGS}/${enc(key)}/approval`, { version_number: versionNumber, reason }),
};

// ---------------------------------------------------------------- the Metodika tab (ADR 0023)

/** A step's value: where it lives, and where it comes from. `absent`: the preset omits the
 *  part; `value` is then null and is not a zero. */
export type MethodValue = {
  reference: string; label_cs: string; unit: string; origin: "specification" | "code_constant";
  value: unknown; absent: boolean;
};
/** A step's editable formula: its slot, the expression the engine computes today, and the
 *  LaTeX the domain writes from that expression (the page shows what runs). */
export type MethodFormula = {
  slot_id: string; title_cs: string; expression: string; latex: string; note_cs: string;
  variables: { name: string; latex: string; meaning_cs: string; unit: string; vector: boolean }[];
  properties: { kind: string; variable: string | null; description_cs: string }[];
};
export type MethodStepOut = {
  id: string; title_cs: string; formula_latex: string; implements: string; source_sha256: string;
  symbols: { latex: string; meaning_cs: string; unit: string }[];
  evidence: { kind: string; ref: string; note_cs: string }[];
  tests: string[]; note_cs: string; values: MethodValue[]; formulas: MethodFormula[];
};
export type MethodGroup = { id: string; title_cs: string; step_ids: string[]; note_cs: string };
export type MethodModuleSummary = {
  id: string; title_cs: string; note_cs: string; presets: string[]; in_force: string | null;
  editable: boolean; steps: number; groups: MethodGroup[];
};
export type MethodModuleDetail = MethodModuleSummary & { preset: string | null; step_details: MethodStepOut[] };

/** A stored methodology version: immutable, named by the store `<base>+e<n>`. */
export type MethodVersion = {
  version_number: number; name: string; base_preset: string; spec: Record<string, unknown>;
  formulas: Record<string, string>; payload_sha256: string; note: string; created_by: string; created_at: string;
};
export type MethodActivation = {
  activation_id: number; version_number: number | null; activated_by: string; reason: string; activated_at: string;
};
/** What a run started now pins: a stored version, or the code's preset. */
export type MethodInForce = { origin: "stored" | "code"; preset: string | null; version_number: number | null; name: string };
export type MethodVersions = {
  in_force: MethodInForce; may_administer: boolean; presets: Record<string, Record<string, unknown>>;
  versions: MethodVersion[]; history: MethodActivation[];
};
/** An edit: the whole specification and the formulas it replaces (by slot). */
export type MethodEdit = { base_preset: string; spec: Record<string, unknown>; formulas: Record<string, string>; note?: string };
export type MethodCheck = { valid: boolean; problems: Record<string, string>; not_computed: string[]; formulas_latex: Record<string, string> };
/** One map of a check panel. */
export type MethodMapSummary = {
  outcome: string; not_mappable: string | null; stress_1: number | null; quality: string | null;
  status_counts: Record<string, number>; effective_n: number | null;
};
/** An edit beside the methodology in force on one fixed fictional panel (plan S4b). Pairs are
 *  `[in force, draft]`; `null` where an object has none. */
export type MethodPanel = {
  panel: string; label_cs: string; respondents: number; objects: string[];
  in_force: MethodMapSummary; draft: MethodMapSummary;
  status_changes: { a: string; b: string; in_force: string; draft: string }[];
  shifts: Record<string, number>; alignment_rmsd: number | null;
  heights: Record<string, [number | null, number | null]>; k100: Record<string, [number | null, number | null]>;
  terrain_max_change: number | null; terrain_note: string | null; notes: string[];
};
/** One fixed fictional cell of the support draft check (plan G1d). Statuses are
 *  `[in force, draft]`; `changes` names each surface whose status moved. */
export type MethodSupportCell = {
  cell: string; label_cs: string; n: number; effective_n: number; donors: number;
  results: [string, string]; analysis: [string, string];
  changes: Partial<Record<"results" | "analysis", "reported" | "suppressed" | "changed">>;
};
export type MethodSupportCompare = {
  draft: string; cells: MethodSupportCell[];
  newly_reported: [string, "results" | "analysis"][]; newly_suppressed: [string, "results" | "analysis"][];
};
/** One estimate of the aggregation draft check (plan G3b): `[value, low, high]` in force
 *  and in the draft, `null` where the aggregate reports none. */
export type MethodEstimate = {
  question: string; measure: string; moved: boolean;
  in_force: [number | null, number | null, number | null]; draft: [number | null, number | null, number | null];
};
export type MethodAggregationPanel = {
  panel: string; label_cs: string; respondents: number; rows: MethodEstimate[];
  status_changes: { question: string; in_force: string; draft: string }[];
  effective_n: Record<string, [number, number]>;
};
export type MethodAggregationCompare = { draft: string; panels: MethodAggregationPanel[] };
/** One fictional question of the response-process draft check (plan R1c): each option's share
 *  in percent under the model's vector, the process in force and the draft. */
export type MethodResponseQuestion = {
  question: string; label_cs: string; labels: string[];
  model: number[]; in_force: number[]; draft: number[];
  moved_pp: number; shift_in_force: number; shift_draft: number;
};
export type MethodResponseCompare = {
  draft: string; respondents: number; questions: MethodResponseQuestion[];
  described_in_force: number; described_draft: number;
};
/** Panels for an object map; `support` for the support rules, `aggregation` for the
 *  aggregation (then `panels` is empty). */
export type MethodCompare = {
  valid: boolean; problems: Record<string, string>; in_force: string; panels: MethodPanel[];
  support?: MethodSupportCompare | null;
  aggregation?: MethodAggregationCompare | null;
  response?: MethodResponseCompare | null;
};

const METHODOLOGY = "/api/v1/methodology";

/** Any member reads and checks; storing a version and changing what is in force need an
 *  organization OWNER or ADMIN (the API refuses anyone else). */
export const methodology = {
  list: () => request<MethodModuleSummary[]>("GET", METHODOLOGY),
  get: (moduleId: string, preset?: string) =>
    request<MethodModuleDetail>("GET", `${METHODOLOGY}/${enc(moduleId)}${preset ? `?preset=${enc(preset)}` : ""}`),
  versions: (moduleId: string) => request<MethodVersions>("GET", `${METHODOLOGY}/${enc(moduleId)}/versions`),
  check: (moduleId: string, edit: MethodEdit) => request<MethodCheck>("POST", `${METHODOLOGY}/${enc(moduleId)}/check`, edit),
  /** The edit beside what is in force, on fictional panels; nothing stored. */
  compare: (moduleId: string, edit: MethodEdit) => request<MethodCompare>("POST", `${METHODOLOGY}/${enc(moduleId)}/compare`, edit),
  propose: (moduleId: string, edit: MethodEdit) => request<MethodVersion>("POST", `${METHODOLOGY}/${enc(moduleId)}/versions`, edit),
  /** `versionNumber` null returns the module to the code's preset. */
  activate: (moduleId: string, versionNumber: number | null, reason: string) =>
    request<MethodInForce>("PUT", `${METHODOLOGY}/${enc(moduleId)}/activation`, { version_number: versionNumber, reason }),
};
