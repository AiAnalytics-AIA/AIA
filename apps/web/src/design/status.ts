/**
 * Domain status → visual treatment. Nothing else.
 *
 * Every map is `satisfies Record<Enum, …>`, so a domain value without a
 * treatment is a `tsc` error; `tools/enum_parity_check.py` catches a value that
 * reaches Python but not `enums.ts`. The UI never decides what a status *is* or
 * *who* must act — it renders what the server says.
 */
import { cs } from "@/i18n/cs";
import {
  ATTEMPT_STATUS, CLIENT_STATUS, FAILURE_CLASS, PROJECT_STATUS, RESERVATION_STATUS, STAGE_STATUS,
  STEP_RUN_STATUS, STUDY_STATUS, WORKFLOW_RUN_STATUS, parseEnum,
  type AttemptStatus, type ClientStatus, type FailureClass, type ProjectStatus, type ReservationStatus,
  type StageStatus, type StepRunStatus, type StudyStatus, type WorkflowRunStatus,
} from "./enums";

/**
 * Visual tones. The five that must be told apart across a room:
 *   running — the machine is working, nothing is needed
 *   person  — parked until a person acts (the enum says a person; not which one)
 *   you     — the same, and the API says THIS viewer can resolve it (personal amber)
 *   world   — parked on provider capacity or quota; clears on its own
 *   fault   — over; needs diagnosis
 *   recovery — a metered call may have been billed with an unknown outcome
 * plus quiet tones for finished, ready and inert states.
 */
export type Tone =
  | "running" | "person" | "you" | "world" | "fault" | "recovery"
  | "done" | "done-warn" | "ready" | "inert" | "blocked" | "invalid" | "cancelled" | "skipped";

/** Base tones: never "you" — that needs the viewer-actionability contract (OI-11). */
type BaseTone = Exclude<Tone, "you">;

export const STAGE_TONE = {
  NOT_STARTED: "inert", READY: "ready", RUNNING: "running", WAITING_USER: "person", WAITING_CREDITS: "person",
  WAITING_CAPACITY: "world", DONE: "done", DONE_WITH_WARNINGS: "done-warn", INVALIDATED: "invalid", FAILED: "fault",
} as const satisfies Record<StageStatus, BaseTone>;

export const RUN_TONE = {
  PENDING: "ready", RUNNING: "running", AWAITING_GATE: "person", AWAITING_BUDGET: "person",
  WAITING_PROVIDER: "world", WAITING_CAPACITY: "world", RECOVERY_REQUIRED: "recovery",
  COMPLETED: "done", FAILED: "fault", CANCELLED: "cancelled",
} as const satisfies Record<WorkflowRunStatus, BaseTone>;

export const STEP_TONE = {
  BLOCKED: "blocked", RUNNABLE: "ready", RUNNING: "running", AWAITING_GATE: "person", AWAITING_BUDGET: "person",
  WAITING_PROVIDER: "world", WAITING_CAPACITY: "world", RECOVERY_REQUIRED: "recovery", SUCCEEDED: "done",
  FAILED: "fault", CANCELLED: "cancelled", SKIPPED: "skipped",
} as const satisfies Record<StepRunStatus, BaseTone>;

export const ATTEMPT_TONE = {
  PENDING: "ready", CLAIMED: "running", EXECUTING: "running", SUCCEEDED: "done", FAILED: "fault", EXPIRED: "fault", ABANDONED: "cancelled",
} as const satisfies Record<AttemptStatus, BaseTone>;

export const RESERVATION_TONE = {
  RESERVED: "running", SETTLED: "done", RELEASED: "cancelled", SETTLED_UNCERTAIN: "recovery",
} as const satisfies Record<ReservationStatus, BaseTone>;

export const STUDY_TONE = {
  DRAFT: "inert", ACTIVE: "ready", IN_REVIEW: "person", DELIVERED: "done", ARCHIVED: "cancelled", CANCELLED: "cancelled",
} as const satisfies Record<StudyStatus, BaseTone>;

export const CLIENT_TONE = { ACTIVE: "ready", DORMANT: "inert", ARCHIVED: "cancelled" } as const satisfies Record<ClientStatus, BaseTone>;

export const PROJECT_TONE = {
  DRAFT: "inert", READY_TO_CONTINUE: "ready", RUNNING: "running", WAITING: "person", COMPLETED: "done",
  FAILED: "fault", ARCHIVED: "cancelled", TRASHED: "cancelled",
} as const satisfies Record<ProjectStatus, BaseTone>;

export const FAILURE_TONE = {
  TRANSPORT: "world", PROVIDER_CAPACITY: "world", TRANSIENT: "world", QUOTA: "world",
  BUDGET_EXCEEDED: "person", APPROVAL_REQUIRED: "person",
  AUTHENTICATION: "fault", PERMISSION: "fault", MISSING_CONFIGURATION: "fault", MODEL_UNAVAILABLE: "fault",
  SCHEMA_VIOLATION: "fault", MAX_TURNS: "fault", SDK_OUTDATED: "fault", CANCELLED: "cancelled", UNKNOWN: "fault",
} as const satisfies Record<FailureClass, BaseTone>;

const KINDS = {
  StageStatus: { values: STAGE_STATUS, tone: STAGE_TONE, label: cs.status.stage satisfies Record<StageStatus, string> },
  WorkflowRunStatus: { values: WORKFLOW_RUN_STATUS, tone: RUN_TONE, label: cs.status.run satisfies Record<WorkflowRunStatus, string> },
  StepRunStatus: { values: STEP_RUN_STATUS, tone: STEP_TONE, label: cs.status.step satisfies Record<StepRunStatus, string> },
  AttemptStatus: { values: ATTEMPT_STATUS, tone: ATTEMPT_TONE, label: cs.status.attempt satisfies Record<AttemptStatus, string> },
  ReservationStatus: { values: RESERVATION_STATUS, tone: RESERVATION_TONE, label: cs.status.reservation satisfies Record<ReservationStatus, string> },
  StudyStatus: { values: STUDY_STATUS, tone: STUDY_TONE, label: cs.status.study satisfies Record<StudyStatus, string> },
  ClientStatus: { values: CLIENT_STATUS, tone: CLIENT_TONE, label: cs.status.client satisfies Record<ClientStatus, string> },
  ProjectStatus: { values: PROJECT_STATUS, tone: PROJECT_TONE, label: cs.status.project satisfies Record<ProjectStatus, string> },
  FailureClass: { values: FAILURE_CLASS, tone: FAILURE_TONE, label: cs.status.failure satisfies Record<FailureClass, string> },
} as const;
export type StatusKind = keyof typeof KINDS;

export type Appearance = {
  tone: Tone;
  label: string;
  /** Who the parked item waits on, in words. Present for person / you / world. */
  audience: string | null;
  /** The raw value was not a known domain value. */
  unknown: boolean;
};

/**
 * What the API states about the authenticated viewer and this parked item
 * (OI-11). Absent ⇒ unknown ⇒ the item is NOT shown as the viewer's.
 */
export type ViewerActionability = { viewerCanResolve: boolean };

export function audienceFor(tone: Tone): string | null {
  if (tone === "you") return cs.audience.you;
  if (tone === "person") return cs.audience.person;
  if (tone === "world") return cs.audience.world;
  return null;
}

/**
 * The appearance of a raw status string. An unknown value renders as a fault
 * with the raw value visible — never as a neutral or a finished state.
 */
export function appearance(kind: StatusKind, raw: string, viewer?: ViewerActionability): Appearance {
  const k = KINDS[kind];
  const value = parseEnum(k.values as readonly string[], raw);
  if (value === null) return { tone: "fault", label: `${cs.status.unknownPrefix} ${raw}`, audience: null, unknown: true };
  const base = (k.tone as Record<string, BaseTone>)[value];
  const tone: Tone = base === "person" && viewer?.viewerCanResolve === true ? "you" : base;
  return { tone, label: (k.label as Record<string, string>)[value], audience: audienceFor(tone), unknown: false };
}
