/**
 * Domain vocabularies the web client renders, as `as const` arrays.
 *
 * Mirrors `packages/aia_core/src/aia_core/domain/`. Chunk 2 of
 * `.planning/plans/design-system.md` binds every array here to its Python
 * `StrEnum` with a CI parity check; until then this file is the only place the
 * web client may spell a status.
 */

export const STAGE_STATUS = [
  "NOT_STARTED", "READY", "RUNNING", "WAITING_USER", "WAITING_CREDITS",
  "WAITING_CAPACITY", "DONE", "DONE_WITH_WARNINGS", "INVALIDATED", "FAILED",
] as const;
export type StageStatus = (typeof STAGE_STATUS)[number];

export const PROJECT_STATUS = [
  "DRAFT", "READY_TO_CONTINUE", "RUNNING", "WAITING", "COMPLETED", "FAILED", "ARCHIVED", "TRASHED",
] as const;
export type ProjectStatus = (typeof PROJECT_STATUS)[number];

export const STUDY_STATUS = ["DRAFT", "ACTIVE", "IN_REVIEW", "DELIVERED", "ARCHIVED", "CANCELLED"] as const;
export type StudyStatus = (typeof STUDY_STATUS)[number];

export const CLIENT_STATUS = ["ACTIVE", "DORMANT", "ARCHIVED"] as const;
export type ClientStatus = (typeof CLIENT_STATUS)[number];

export const SCOPE_ROLE = ["VIEWER", "REVIEWER", "RESEARCHER", "LEAD"] as const;
export type ScopeRole = (typeof SCOPE_ROLE)[number];
