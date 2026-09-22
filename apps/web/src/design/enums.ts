/**
 * Domain vocabularies the web client renders, as `as const` arrays.
 *
 * Every array is bound to a Python StrEnum in `packages/aia_core/src/aia_core/domain/`
 * by `tools/enum_parity_check.py` (CI: backend job, `make enum_check`). Adding a
 * value on either side without the other fails CI; the status maps in
 * `./status.ts` are `satisfies Record<…>` over these types, so a value with no
 * visual treatment fails `tsc`. This is the only place the web client may spell
 * a domain value.
 */

// pipeline.py
export const STAGE_STATUS = [
  "NOT_STARTED", "READY", "RUNNING", "WAITING_USER", "WAITING_CREDITS",
  "WAITING_CAPACITY", "DONE", "DONE_WITH_WARNINGS", "INVALIDATED", "FAILED",
] as const;
export type StageStatus = (typeof STAGE_STATUS)[number];

// project.py
export const PROJECT_STATUS = [
  "DRAFT", "READY_TO_CONTINUE", "RUNNING", "WAITING", "COMPLETED", "FAILED", "ARCHIVED", "TRASHED",
] as const;
export type ProjectStatus = (typeof PROJECT_STATUS)[number];

// workflow.py
export const WORKFLOW_RUN_STATUS = [
  "PENDING", "RUNNING", "AWAITING_GATE", "AWAITING_BUDGET", "WAITING_PROVIDER",
  "WAITING_CAPACITY", "RECOVERY_REQUIRED", "COMPLETED", "FAILED", "CANCELLED",
] as const;
export type WorkflowRunStatus = (typeof WORKFLOW_RUN_STATUS)[number];

export const STEP_RUN_STATUS = [
  "BLOCKED", "RUNNABLE", "RUNNING", "AWAITING_GATE", "AWAITING_BUDGET", "WAITING_PROVIDER",
  "WAITING_CAPACITY", "RECOVERY_REQUIRED", "SUCCEEDED", "FAILED", "CANCELLED", "SKIPPED",
] as const;
export type StepRunStatus = (typeof STEP_RUN_STATUS)[number];

export const ATTEMPT_STATUS = ["PENDING", "CLAIMED", "EXECUTING", "SUCCEEDED", "FAILED", "EXPIRED", "ABANDONED"] as const;
export type AttemptStatus = (typeof ATTEMPT_STATUS)[number];

export const RESERVATION_STATUS = ["RESERVED", "SETTLED", "RELEASED", "SETTLED_UNCERTAIN"] as const;
export type ReservationStatus = (typeof RESERVATION_STATUS)[number];

export const FAILURE_CLASS = [
  "TRANSPORT", "PROVIDER_CAPACITY", "TRANSIENT", "QUOTA", "BUDGET_EXCEEDED", "APPROVAL_REQUIRED",
  "AUTHENTICATION", "PERMISSION", "MISSING_CONFIGURATION", "MODEL_UNAVAILABLE", "SCHEMA_VIOLATION",
  "MAX_TURNS", "SDK_OUTDATED", "CANCELLED", "UNKNOWN",
] as const;
export type FailureClass = (typeof FAILURE_CLASS)[number];

// scope.py
export const STUDY_STATUS = ["DRAFT", "ACTIVE", "IN_REVIEW", "DELIVERED", "ARCHIVED", "CANCELLED"] as const;
export type StudyStatus = (typeof STUDY_STATUS)[number];

export const CLIENT_STATUS = ["ACTIVE", "DORMANT", "ARCHIVED"] as const;
export type ClientStatus = (typeof CLIENT_STATUS)[number];

export const SCOPE_ROLE = ["VIEWER", "REVIEWER", "RESEARCHER", "LEAD"] as const;
export type ScopeRole = (typeof SCOPE_ROLE)[number];

export const ORGANIZATION_ROLE = ["OWNER", "ADMIN", "MEMBER"] as const;
export type OrganizationRole = (typeof ORGANIZATION_ROLE)[number];

export const PERMISSION = [
  "VIEW_STUDY", "VIEW_RESULTS", "VIEW_COSTS", "EDIT_STUDY", "RUN_WORKFLOW", "CANCEL_WORKFLOW",
  "UPLOAD_DATA", "APPROVE_GATE", "APPROVE_BUDGET", "SIGN_OFF_DELIVERABLE", "EXPORT_DELIVERABLE",
  "MANAGE_STUDY_ACCESS", "MANAGE_STUDY_BUDGET", "DELETE_STUDY",
] as const;
export type Permission = (typeof PERMISSION)[number];

export const SELF_APPROVAL_SOURCE = ["default", "organization", "client", "study"] as const;
export type SelfApprovalSource = (typeof SELF_APPROVAL_SOURCE)[number];

// providers.py
export const PROVIDER = ["claude_code_subscription", "anthropic", "openai"] as const;
export type Provider = (typeof PROVIDER)[number];

export const PROVIDER_POLICY = ["CLAUDE_CODE_ONLY", "CLAUDE_API_ONLY", "OPENAI_ONLY", "CLAUDE_CODE_THEN_API"] as const;
export type ProviderPolicy = (typeof PROVIDER_POLICY)[number];

export const MODEL_ROLE = ["research_model", "design_model", "respondent_model", "analysis_model", "report_polish_model"] as const;
export type ModelRole = (typeof MODEL_ROLE)[number];

/** Narrow a raw API string to a domain value, or null. Never a cast. */
export function parseEnum<T extends string>(values: readonly T[], raw: unknown): T | null {
  return typeof raw === "string" && (values as readonly string[]).includes(raw) ? (raw as T) : null;
}
