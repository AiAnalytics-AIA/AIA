/**
 * Response shapes of the AIA API, mirrored by hand from the Pydantic schemas.
 *
 * Sources: `apps/api/src/aia_api/routers/scope.py` (ClientResponse, StudyResponse)
 * and `apps/api/src/aia_api/schemas/projects.py` (projects, stages, impact).
 * Status fields arrive as strings; they are narrowed to the domain unions in
 * `@/design/enums` only after validation, never by cast.
 */

export type ClientResponse = {
  client_id: string;
  slug: string;
  name: string;
  status: string;
  reference: string;
  study_count: number;
  created_at: string | null;
};

/** Budget fields are omitted — not zeroed — when the caller lacks VIEW_COSTS. */
export type StudyResponse = {
  study_id: string;
  client_id: string;
  slug: string;
  name: string;
  status: string;
  accepts_work: boolean;
  your_role: string | null;
  budget_usd?: number | null;
  spent_usd?: number | null;
  remaining_usd?: number | null;
  created_at: string | null;
  modified_at: string | null;
  delivered_at: string | null;
};

export type StageResponse = {
  stage_type: string;
  ordinal: number;
  status: string;
  label: string;
  provider: string | null;
  provider_label: string | null;
  model: string;
  artifact_count: number;
  waiting_reason: string | null;
  quota_reset_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  fingerprint_prefix: string;
  is_complete: boolean;
};

export type ImpactResponse = {
  root_stage: string | null;
  invalidate: string[];
  preserve: string[];
  presentation_only: boolean;
};

export type ProjectResponse = {
  project_id: string;
  title: string;
  project_type: string;
  status: string;
  current_revision: number;
  current_stage: string;
  last_completed_stage: string | null;
  parent_project_id: string | null;
  preferred_provider: string;
  provider_label: string;
  provider_policy: string;
  max_api_cost_usd: number;
  tags: string[];
  pinned: boolean;
  archived: boolean;
  created_at: string | null;
  modified_at: string | null;
};

export type ProjectDetailResponse = ProjectResponse & {
  stages: StageResponse[];
  content: Record<string, unknown>;
};

export type ErrorResponse = {
  code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string | null;
};

export type EventResponse = {
  event_id: number;
  event_type: string;
  level: string;
  message: string;
  revision: number;
  stage_type: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

/** The paginated envelope of list routes (`ProjectListResponse`). */
export type Page<T> = {
  items: T[];
  page: { total: number; limit: number; offset: number; has_more: boolean };
};
