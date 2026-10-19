// The prototype's state model. One Study owns its conversation, artifacts,
// proposals, accepted revisions, decisions, runs, workers, evidence and
// deliverables. Static fixture content lives in fixture.ts; everything that
// changes lives in AppState and is changed only through store actions.

export type StageId =
  | 'brief' | 'design' | 'questionnaire' | 'audience' | 'dimensions' | 'sample'
  | 'fieldwork' | 'results' | 'sociomap' | 'analysis' | 'report';

export type PhaseId = 'design' | 'sample' | 'execution' | 'evidence' | 'interpretation' | 'delivery';

export type Tone =
  | 'done' | 'done-warn' | 'running' | 'you' | 'world' | 'fault' | 'recovery'
  | 'reopened' | 'working' | 'ready' | 'blocked' | 'cancelled' | 'inert';

// What a stage shows on the navigator. The kind is derived from domain state by
// stageStatus(); it is never stored independently of that state.
export type StageStatusKind =
  | 'accepted' | 'working' | 'proposal' | 'decision' | 'running' | 'waiting'
  | 'reopened' | 'ready' | 'blocked' | 'notstarted' | 'complete' | 'failed' | 'frozen';

export interface StageStatus { kind: StageStatusKind; note: string }

// An edit to an artifact's element model: the same operations a person makes in
// the editor and the Research Lead requests through a typed command.
export type Op =
  | { op: 'set'; sec: string; item?: string; field: string; value: string | boolean | number }
  | { op: 'add'; sec: string; after?: string | null; item: Record<string, unknown> & { id: string } }
  | { op: 'remove'; sec: string; item: string }
  | { op: 'move'; sec: string; item: string; dir: -1 | 1 };

export interface AppliedOp { id: string; actor: 'you' | 'lead' | 'worker'; at: string; op: Op; note?: string }

export type ArtifactState = 'working' | 'proposed' | 'accepted' | 'frozen' | 'empty';

export interface Change {
  id: string;
  target: string;          // element path, e.g. "b2.Q8.t"
  label: string;           // human label of the element
  kind: 'modify' | 'remove' | 'add' | 'route' | 'merge' | 'keep';
  from?: string;
  to?: string;
  why: string;
  op?: Op;
}

export type ProposalStatus = 'pending' | 'accepted' | 'rejected' | 'stale' | 'superseded';

export interface Proposal {
  id: string;
  stage: StageId;
  title: string;
  author: string;            // the worker/action that produced it
  activityId?: string;
  baseRev: number;           // the revision it was built against
  baseLabel: string;
  changes: Change[];
  implications: string[];    // research and methodology implications
  coverage?: { gained: string[]; lost: string[]; kept: string[] };
  impact: { stage: StageId; effect: string }[];
  recompute: string;         // whether recomputation is needed, in words
  cost?: string;
  status: ProposalStatus;
  createdAt: string;
  rebuiltFrom?: string;
  kind: 'design' | 'presentation' | 'annotation';
}

export type ActivityType = 'lead' | 'worker' | 'research' | 'compute' | 'decision' | 'lookup';
export type ActivityStatus = 'running' | 'done' | 'waiting' | 'failed' | 'refused' | 'stopped';

export interface ActivityStep { text: string; tone: Tone }

export interface Activity {
  id: string;
  type: ActivityType;
  title: string;             // "Questionnaire reviewed"
  summary: string;           // "7 changes proposed"
  status: ActivityStatus;
  startedAt: number;         // demo clock seconds
  endedAt?: number;
  steps: ActivityStep[];
  link?: { stage: StageId; focus?: string; label: string };
  details: [string, string][];   // worker/action, baseline, inputs, runtime, route, classification, calls, cost, repairs, ids, provenance
  progress?: { done: number; total: number; unit: string };
}

export type MessageKind = 'user' | 'lead' | 'activity' | 'decision' | 'divider' | 'notice' | 'return';

export interface Block { t: 'p' | 'ul' | 'kv' | 'h'; x?: string; items?: string[]; rows?: [string, string][] }

export interface LinkRef { stage: StageId; focus?: string; label: string }

export interface Message {
  id: string;
  kind: MessageKind;
  at: string;                 // display time
  day: string;                // display day, for dividers and return summaries
  rev: number;                // study revision when the message was written
  runRev?: number;            // run revision it speaks about, when it does
  text?: string;              // user / notice / divider text
  ref?: { stage: StageId; path: string; label: string };
  blocks?: Block[];           // lead
  shown?: number;             // lead streaming: characters revealed
  streaming?: boolean;
  links?: LinkRef[];
  sources?: string[];         // evidence ids the message cites
  activityId?: string;        // activity
  decisionId?: string;        // decision
  tone?: Tone;                // notice
  returnSummary?: { changed: string[]; finished: string[]; attention: string[]; next: string };
  historical?: string;        // set when the message describes a state that has since moved on
  follow?: string[];          // suggested follow-ups (Open WebUI follow-ups pattern)
  stopped?: boolean;          // the person stopped this answer
}

export interface Decision {
  id: string;
  title: string;             // proposed action
  reason: string;
  alternatives: { id: string; label: string; detail: string; recommended?: boolean }[];
  impact: string[];
  cost?: string;
  status: 'open' | 'decided' | 'withdrawn';
  chosen?: string;
  kind: 'scope' | 'authorise-run' | 'budget' | 'data' | 'method' | 'research';
  stage?: StageId;
}

export type InspectorTarget =
  | { type: 'source'; id: string }
  | { type: 'finding'; id: string }
  | { type: 'claim'; id: string }
  | { type: 'pair'; a: string; b: string }
  | { type: 'object'; id: string }
  | { type: 'history'; stage: StageId }
  | { type: 'details'; stage: StageId }
  | { type: 'impact'; proposalId: string }
  | { type: 'activity'; id: string }
  | { type: 'methodology' }
  | { type: 'contract'; stage: StageId }
  | { type: 'context' }
  | { type: 'envelope' }
  | { type: 'budget' }
  | { type: 'lifecycle' }
  | { type: 'synthetic' }
  | { type: 'research'; id: string };

export interface Run {
  id: string;
  revision: number;          // the frozen Design Revision this run executes
  status: 'none' | 'ready' | 'running' | 'waiting_provider' | 'awaiting_budget' | 'awaiting_decision' | 'completed' | 'cancelled';
  done: number;
  target: number;
  inFlight: number;
  constantResponders: number;
  spent: number;             // USD settled
  reserved: number;          // USD reserved
  ceiling: number;
  elapsed: number;           // seconds
  waits: number;
  decisionOnConstant?: 'keep' | 'review';
}

export interface ResearchRun {
  id: string;
  purpose: 'DESIGN_RESEARCH' | 'INTERPRETATION_RESEARCH';
  target: string;            // the frozen target in words
  targetRef: string;         // e.g. "audience.assumptions.A1" or "sociomap.pair.fio~e"
  status: 'running' | 'done' | 'stopped' | 'refused';
  step: number;              // 0..6 of plan → publish
  sources: number;
  admitted: number;
  quarantined: number;
  noEvidence: number;
  spent: number;
  findings: string[];        // evidence ids
}

export type Mode = 'normal' | 'artifact' | 'conversation';

export interface AppState {
  view: 'entry' | 'study' | 'docs';
  scenario: string;
  clock: number;             // demo seconds since the scenario started
  day: string;               // the demo's "today"
  revision: number;          // current accepted Design Revision of the Study
  stage: StageId;
  mode: Mode;
  split: number;             // persisted conversation width in percent
  // per-stage element-model state
  accepted: Partial<Record<StageId, AppliedOp[]>>;
  working: Partial<Record<StageId, AppliedOp[]>>;
  workingSince: Partial<Record<StageId, number>>;  // revision a working copy was started from
  leadSeen: Partial<Record<StageId, number>>;      // working-op count the Lead has acknowledged
  reopened: StageId[];
  proposals: Proposal[];
  activities: Activity[];
  decisions: Decision[];
  messages: Message[];
  run: Run;
  research: ResearchRun[];
  evidenceAttached: Record<string, string[]>;      // artifact anchor -> evidence ids
  budget: { studyLimit: number; studySpent: number; studyReserved: number; researchLimit: number; researchSpent: number; spendConfirm: number };
  viewFilters: { sociomapHideWeak: boolean; sociomapLabels: boolean; sociomapView: 'top' | 'relief' };
  inspector: InspectorTarget[];                     // a back stack; last is shown
  focusPath: string | null;                         // element briefly highlighted
  selection: Partial<Record<StageId, string>>;      // last selection per artifact
  composer: { draft: string; ref: { stage: StageId; path: string; label: string } | null; queue: { id: string; text: string }[] };
  busy: boolean;
  autopilot: boolean;
  unreadBelow: number;
  analysisState: 'none' | 'running' | 'complete' | 'blocked_module';
  reportState: { draft: number; reviewed: boolean; changes: 'none' | 'proposed' | 'accepted' };
  failures: { provider: boolean; budgetLimit: boolean; missingEvidence: boolean; analysisValidation: boolean };
  returnFrom?: string;
  log: CommandLog[];                                // every application command, from the UI or the Lead
  codingAccepted: boolean;                          // proposed open-answer coding accepted (proposed capability)
  pmPaused?: string;                                // why "continue" stopped
  lastSeenMsg?: string;                             // the conversation position before leaving
}

export interface CommandLog { id: string; cmd: string; by: 'ui' | 'lead' | 'worker' | 'system'; ok: boolean; reason?: string; at: string; stage?: StageId }
