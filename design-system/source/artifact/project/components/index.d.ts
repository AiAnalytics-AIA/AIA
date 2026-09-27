// AIA design system — component types (documentation; the bundle is plain JS on window.AIA).
import type { ReactNode, ReactElement } from "react";

export type StageStatus = "NOT_STARTED" | "READY" | "RUNNING" | "WAITING_USER" | "WAITING_CREDITS" | "WAITING_CAPACITY" | "DONE" | "DONE_WITH_WARNINGS" | "INVALIDATED" | "FAILED";
export type WorkflowRunStatus = "PENDING" | "RUNNING" | "AWAITING_GATE" | "AWAITING_BUDGET" | "WAITING_PROVIDER" | "WAITING_CAPACITY" | "RECOVERY_REQUIRED" | "COMPLETED" | "FAILED" | "CANCELLED";
export type StepRunStatus = "BLOCKED" | "RUNNABLE" | "RUNNING" | "AWAITING_GATE" | "AWAITING_BUDGET" | "WAITING_PROVIDER" | "WAITING_CAPACITY" | "RECOVERY_REQUIRED" | "SUCCEEDED" | "FAILED" | "CANCELLED" | "SKIPPED";
export type ReservationStatus = "RESERVED" | "SETTLED" | "RELEASED" | "SETTLED_UNCERTAIN";
export type StatusKind = "StageStatus" | "WorkflowRunStatus" | "StepRunStatus" | "AttemptStatus" | "ReservationStatus" | "StudyStatus" | "ClientStatus" | "ProjectStatus" | "FailureClass";
export type Tone = "running" | "you" | "world" | "fault" | "recovery" | "done" | "done-warn" | "ready" | "inert" | "blocked" | "invalid" | "cancelled" | "skipped";
/** Known roles; any other string renders as the unknown grade "?". */
export type EvidenceRole = "MEASURED_JOINT" | "CALIBRATED_CORE" | "MODELED_BEHAVIOR_PRIOR" | "EXTERNAL_HOLDOUT_PENDING" | (string & {});
export type ScopeRole = "VIEWER" | "REVIEWER" | "RESEARCHER" | "LEAD";
export type Provider = "claude_code_subscription" | "anthropic" | "openai";
export type ProviderPolicy = "CLAUDE_CODE_ONLY" | "CLAUDE_API_ONLY" | "OPENAI_ONLY" | "CLAUDE_CODE_THEN_API";
export type ModelRole = "research_model" | "design_model" | "respondent_model" | "analysis_model" | "report_polish_model";

export interface StatusChipProps { kind: StatusKind; value: string; small?: boolean; children?: ReactNode }
export interface StatusGlyphProps { tone: Tone; size?: number }
export interface EvidenceMarkProps { role: EvidenceRole | null | undefined; size?: number; inSvg?: boolean }
export interface ValueProps {
  value?: number | null; state?: "value" | "zero" | "na" | "suppressed" | "loading";
  format?: (v: number) => string; digits?: number; role?: EvidenceRole | null; inheritRole?: EvidenceRole;
  tag?: boolean; reason?: string; showReason?: boolean; width?: number;
}
export interface MoneyProps { value: number | null; currency?: string; digits?: number }
export interface ButtonProps { variant?: "primary" | "quiet" | "danger"; compact?: boolean; icon?: string; kbd?: string; onClick?: () => void; children?: ReactNode }
export interface ScopeBarProps {
  above?: boolean; note?: string; clientId?: string; accent?: 1 | 2 | 3 | 4 | 5 | 6; code?: string; client?: string; study?: string;
  studyStatus?: "DRAFT" | "ACTIVE" | "IN_REVIEW" | "DELIVERED" | "ARCHIVED" | "CANCELLED"; revision?: number; role?: ScopeRole; deliveredAt?: string; right?: ReactNode;
}
export interface StageRailProps { lifecycle: "research" | "simulation"; stages: { status: StageStatus; note?: string }[]; current?: number; narrow?: boolean; summary?: string; onSelect?: (i: number) => void }
export interface RunTimelineProps { status: WorkflowRunStatus; runId: string; elapsed: number; heartbeat?: number; waitingOn?: string; steps: { name: string; status: StepRunStatus; elapsed?: number; attempt?: number; detail?: string }[] }
export interface ImpactPreviewProps {
  lifecycle: "research" | "simulation"; stageIds: string[]; field: string;
  preview: { root_stage: string | null; invalidate: string[]; preserve: string[]; presentation_only: boolean };
  artifactsKept?: number; costEstimate?: [number, number] | null; costBasis?: string; timeEstimate?: string | null;
}
export interface BudgetMeterProps { limit: number; spent: number; uncertain?: number; reserved?: number; currency?: string }
export interface ParkAndAskProps { clientId: string; accent?: number; client: string; study: string; what: string; modelRole: ModelRole; provider: Provider; amount: number; basis: string; remaining: number; limit: number; currency?: string; canApprove: boolean }
export interface ProviderChoiceProps { provider: Provider; reason: string; resumeAt?: string; policy: ProviderPolicy; alternative?: Provider; alternativeCost?: number }
export interface RecoveryDecisionProps { step: string; provider: Provider; at: string; amount: number; currency?: string }
export interface UsageLedgerProps { rows: { at: string; id: string; step: string; role: ModelRole; provider: Provider; model: string; inTok: number | null; outTok: number | null; amount: number | null; status: ReservationStatus }[] }
export interface ApprovalPanelProps {
  what: string; fingerprint: string; producer: string; producerIsViewer: boolean; selfAllowed?: boolean;
  policySource?: "default" | "organization" | "client" | "study"; eligible?: string[];
  checks: { passed: number; total: number; warnings?: number; modelled?: number; pending?: boolean };
  audit?: { icon?: string; text: string; at: string }[];
}
export interface HeadlineAnswerProps { question: string; answer: string; figure: number; role: EvidenceRole; n: number; interval?: [number, number]; findings?: { text: string; role: EvidenceRole }[] }
export interface GradedBarsProps { rows: { label: string; value?: number | null; state?: "na" | "suppressed"; role?: EvidenceRole; lo?: number; hi?: number }[]; label: string; color?: string; max?: number; width?: number; id?: string }
export interface SociomapProps {
  nodes: { id: string; label: string; x: number; y: number; role?: EvidenceRole; cluster?: number; moved?: { x: number; y: number } | null; whatif?: boolean }[];
  edges: { a: string; b: string; w: number; crossBlock?: boolean }[]; clusters?: { x: number; y: number; rx: number; ry: number }[];
  selected?: string; overrideBy?: string; showOverrides?: boolean; whatif?: string; label: string;
}
export interface ReportCoverProps { client: string; title: [string, string?]; subtitle: string; date: string; revision: number; pages: number; signedBy: string }

export declare function StatusChip(p: StatusChipProps): ReactElement;
export declare function StatusGlyph(p: StatusGlyphProps): ReactElement;
export declare function EvidenceMark(p: EvidenceMarkProps): ReactElement;
export declare function Value(p: ValueProps): ReactElement;
export declare function EvidenceLegend(p: { compact?: boolean }): ReactElement;
export declare function Money(p: MoneyProps): ReactElement;
export declare function Button(p: ButtonProps): ReactElement;
export declare function Kbd(p: { children: ReactNode }): ReactElement;
export declare function Icon(p: { name: string; size?: number; label?: string }): ReactElement;
export declare function Mark(p: { size?: number; mono?: boolean }): ReactElement;
export declare function Wordmark(p: { height?: number; mono?: boolean }): ReactElement;
export declare function Lattice(p: { cols?: number; rows?: number; pitch?: number; color?: string }): ReactElement;
export declare function ScopeBar(p: ScopeBarProps): ReactElement;
export declare function ClientMonogram(p: { clientId?: string; accent?: number; code?: string; name?: string; above?: boolean }): ReactElement;
export declare function StageRail(p: StageRailProps): ReactElement;
export declare function RunTimeline(p: RunTimelineProps): ReactElement;
export declare function ImpactPreview(p: ImpactPreviewProps): ReactElement;
export declare function RevisionBanner(p: { viewing: number; current: number; when: string }): ReactElement;
export declare function RevisionHistory(p: { revisions: { n: number; change: string; by: string; at: string; reopened: number; viewing?: boolean }[] }): ReactElement;
export declare function BudgetMeter(p: BudgetMeterProps): ReactElement;
export declare function ParkAndAsk(p: ParkAndAskProps): ReactElement;
export declare function ProviderChoice(p: ProviderChoiceProps): ReactElement;
export declare function RecoveryDecision(p: RecoveryDecisionProps): ReactElement;
export declare function UsageLedger(p: UsageLedgerProps): ReactElement;
export declare function ApprovalPanel(p: ApprovalPanelProps): ReactElement;
export declare function HeadlineAnswer(p: HeadlineAnswerProps): ReactElement;
export declare function GradedBars(p: GradedBarsProps): ReactElement;
export declare function Sociomap(p: SociomapProps): ReactElement;
export declare function ReportCover(p: ReportCoverProps): ReactElement;
export declare function ReportPage(p: { tight?: boolean }): ReactElement;
/** Returns "Enum.VALUE (tone|label)" for every domain value a map lacks; [] when total. */
export declare function checkTotality(): string[];
export declare function clientAccentIndex(clientId: string): 1 | 2 | 3 | 4 | 5 | 6;
