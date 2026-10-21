// The Lead's per-artifact contract (plan research-lead-workbench chunks 14-16): one row per stage,
// so every screen plugs into the Research Lead the same way. A row says what the stage shows, whether
// the Lead's edits land there, the closed set of display operations the Lead may run on it, the
// elements it can name (`data-aia="<kind>:<id>"`, built with aiaId), the workers and requests its
// cards start, what it is made from and what it hands on, and the internal report sections it feeds.
// Held to packages/aia_core/tests/fixtures/lead_artifacts/contract.json, as domain/lead_artifacts.py
// is: change one and the fixture changes with it. Pure.

import type { ResearchAgentAction } from "./api";
import type { WorkbenchStage } from "./workbench-stages";

export type ArtifactKind = "working" | "run" | "draft";

export type ViewOpKind = "open_stage" | "focus" | "inspect" | "select" | "filter" | "show_diff";
/** The view operations the Lead's output carries today (lead.ts LeadView); the rest are to build. */
export const LIVE_VIEW_OPS: ReadonlySet<ViewOpKind> = new Set<ViewOpKind>(["open_stage", "focus"]);

export type TargetKind =
  | "brief" | "objective" | "material" | "plan" | "rq" | "hypothesis" | "set" | "assumption" | "section" | "question" | "audience" | "dimension" | "own_dimension" | "sample"
  | "step" | "measure" | "object" | "pair" | "module" | "finding" | "claim" | "report";
/** Every target kind: the server's FOCUS_ID takes each (research-lead-workbench 16). */
export const LIVE_TARGETS: ReadonlySet<TargetKind> = new Set<TargetKind>([
  "brief", "objective", "material", "plan", "rq", "hypothesis", "set", "assumption", "section", "question",
  "audience", "dimension", "own_dimension", "sample", "step", "measure", "object", "pair", "module", "finding",
  "claim", "report",
]);

/** What a card starts: a design worker, a Lead request, or a finished run's failed analysis asked again. */
export type LeadStart =
  | `agent_job:${ResearchAgentAction}` | "research_run" | "design_research" | "interpretation_research" | "analysis_retry";

/** The internal report's sections, by the id its composer gives each Section (ch-1 … ch-8: the modules' ordinals). */
export type ReportSection =
  | "intro" | "ch-design" | "ch-1" | "ch-2" | "literature" | "methodology" | "ch-method" | "ch-questions"
  | "ch-4" | "ch-3" | "ch-native-map" | "ch-5" | "ch-6" | "ch-7" | "ch-8"
  | "app-questionnaire" | "app-evidence" | "app-audit";

export type HandOff = { to: WorkbenchStage | null; form: string };

export type ArtifactContract = {
  stage: WorkbenchStage;
  artifact: ArtifactKind;
  edits: boolean;
  view_ops: readonly ViewOpKind[];
  targets: readonly TargetKind[];
  starts: readonly LeadStart[];
  inputs: readonly WorkbenchStage[];
  hands_off: readonly HandOff[];
  report_sections: readonly ReportSection[];
  refusals: readonly string[];
};

const MEMORY: LeadStart = "agent_job:answer_memory";

export const ARTIFACTS: Readonly<Record<WorkbenchStage, ArtifactContract>> = {
  brief: {
    stage: "brief", artifact: "working", edits: true,
    view_ops: ["open_stage", "focus"], targets: ["brief", "objective", "material"],
    starts: ["agent_job:analyze_brief", MEMORY],
    inputs: [],
    hands_off: [{ to: "design", form: "working content `briefing`, read by analyze_brief" }],
    report_sections: ["intro"],
    refusals: ["důvěrný podklad nelze poslat do veřejného vyhledávání"],
  },
  design: {
    stage: "design", artifact: "working", edits: true,
    view_ops: ["open_stage", "focus", "inspect", "show_diff"], targets: ["plan", "rq", "hypothesis", "set", "assumption"],
    starts: ["agent_job:analyze_brief", "agent_job:critique_design", "agent_job:design_copilot", MEMORY, "design_research"],
    inputs: ["brief"],
    hands_off: [
      { to: "questionnaire", form: "research_plan.research_questions, linked by items' research_questions" },
      { to: "analysis", form: "ResearchSpecification research questions (compile_design)" },
    ],
    report_sections: ["intro", "ch-design", "ch-6"],
    refusals: ["metodickou volbu neuzavírá AI"],
  },
  questionnaire: {
    stage: "questionnaire", artifact: "working", edits: true,
    view_ops: ["open_stage", "focus", "show_diff"], targets: ["section", "question"],
    starts: ["agent_job:build_questionnaire", "agent_job:optimize_questionnaire", MEMORY, "design_research"],
    inputs: ["design"],
    hands_off: [{ to: "fieldwork", form: "ResearchSpecification questions and batteries (compile_design)" }],
    report_sections: ["ch-design", "ch-questions", "app-questionnaire"],
    refusals: ["přijetí návrhu jen člověk (APPROVE_GATE)"],
  },
  audience: {
    stage: "audience", artifact: "working", edits: false,
    view_ops: ["open_stage", "focus"], targets: ["audience"],
    starts: ["agent_job:propose_audience", MEMORY],
    inputs: ["design"],
    hands_off: [{ to: "sample", form: "ResearchSpecification audience and SpecSelection filters" }],
    report_sections: ["ch-design", "ch-4"],
    refusals: ["náhled vrací jen počty, žádné řádky"],
  },
  dimensions: {
    stage: "dimensions", artifact: "working", edits: true,
    view_ops: ["open_stage", "focus"], targets: ["dimension", "own_dimension"],
    starts: ["agent_job:suggest_dimensions", MEMORY],
    inputs: ["design", "audience"],
    hands_off: [{ to: "fieldwork", form: "SpecSelection dimensions (persona_dimensions.approved)" }],
    report_sections: ["ch-design", "ch-5"],
    refusals: ["pole použije jen to, co dovolí politika pole (decide)"],
  },
  sample: {
    stage: "sample", artifact: "working", edits: false,
    view_ops: ["open_stage", "focus", "inspect"], targets: ["sample"],
    starts: [MEMORY],
    inputs: ["audience", "dimensions"],
    hands_off: [{ to: "fieldwork", form: "ResearchSpecification n" }],
    report_sections: ["ch-design", "ch-method"],
    refusals: ["kvóta nezaručuje podporu dvojic"],
  },
  fieldwork: {
    stage: "fieldwork", artifact: "run", edits: false,
    view_ops: ["open_stage", "focus", "inspect"], targets: ["step"],
    starts: ["research_run"],
    inputs: ["questionnaire", "audience", "dimensions", "sample"],
    hands_off: [
      { to: "results", form: "research_fieldwork_dataset -> research_aggregate" },
      { to: "sociomap", form: "research_fieldwork_dataset -> research_sociomap" },
      { to: "analysis", form: "research_fieldwork_dataset as admitted evidence" },
    ],
    report_sections: ["ch-method", "app-audit"],
    refusals: ["nad limit potvrzení jen člověk"],
  },
  results: {
    stage: "results", artifact: "run", edits: false,
    view_ops: ["open_stage", "focus", "inspect"], targets: ["measure"],
    starts: [MEMORY],
    inputs: ["fieldwork"],
    hands_off: [{ to: "analysis", form: "research_aggregate" }],
    report_sections: ["ch-questions"],
    refusals: ["potlačené číslo se neukáže ani AI"],
  },
  sociomap: {
    stage: "sociomap", artifact: "run", edits: false,
    view_ops: ["open_stage", "focus", "select", "filter", "inspect"], targets: ["object", "pair"],
    starts: ["interpretation_research"],
    inputs: ["fieldwork"],
    hands_off: [{ to: "report", form: "research_sociomap contract-3 maps (verified_map)" }],
    report_sections: ["ch-native-map"],
    refusals: ["filtr zobrazení nemění výpočet", "externí kontext do výpočtu nevstupuje"],
  },
  analysis: {
    stage: "analysis", artifact: "run", edits: false,
    view_ops: ["open_stage", "focus", "inspect"], targets: ["module", "finding", "claim"],
    starts: ["analysis_retry", "interpretation_research"],
    inputs: ["fieldwork", "results", "sociomap"],
    hands_off: [{ to: "report", form: "eight research_analysis modules (RunAnalysis)" }],
    report_sections: ["ch-1", "ch-2", "ch-4", "ch-3", "ch-5", "ch-6", "ch-7", "ch-8", "app-evidence"],
    refusals: ["číslo jen jako AdmittedClaim", "AI neschvaluje vlastní tvrzení"],
  },
  report: {
    stage: "report", artifact: "draft", edits: false,
    view_ops: ["open_stage", "focus", "show_diff"], targets: ["report"],
    starts: ["interpretation_research"],
    inputs: ["design", "questionnaire", "sociomap", "analysis"],
    hands_off: [{ to: null, form: "research_internal_docx, DRAFT_UNAPPROVED; approved only by a person" }],
    report_sections: ["literature"],
    refusals: ["schválení jen člověk"],
  },
};

/** The display filters a stage's `filter` operation names; a filter never changes a computation. */
export const VIEW_FILTERS: Readonly<Partial<Record<WorkbenchStage, readonly string[]>>> = {
  sociomap: ["view", "labels", "hide_weak", "mode", "battery"],
};

/** The stage each target kind belongs to: the one artifact whose screen carries it. */
export const TARGET_STAGE: Readonly<Record<TargetKind, WorkbenchStage>> = Object.fromEntries(
  Object.values(ARTIFACTS).flatMap((a) => a.targets.map((t) => [t, a.stage])),
) as Record<TargetKind, WorkbenchStage>;

/** Whether the Lead may run `op` on `stage`'s artifact. */
export const allowsView = (stage: WorkbenchStage, op: string): boolean =>
  (ARTIFACTS[stage].view_ops as readonly string[]).includes(op);

/** An id: letters, digits and _ . - ~ / and : (an id may hold parts, e.g. finding:<module>:<n>). */
const ID = /^[A-Za-z0-9_.\-~/:]{1,80}$/;

/**
 * The `data-aia` id a screen puts on an element the Lead can name: `<kind>:<id>`. One builder, so a
 * screen never spells the grammar itself; an id outside it is refused here, never sent to the server.
 */
export function aiaId(kind: TargetKind, id: string): string {
  if (!ID.test(id)) throw new Error(`aiaId: ${kind} id ${JSON.stringify(id)} is not an identifier`);
  return `${kind}:${id}`;
}

/** A `data-aia` id read back: its kind, id and stage; null for anything the contract does not name. */
export function parseAiaId(value: string): { kind: TargetKind; id: string; stage: WorkbenchStage } | null {
  const at = value.indexOf(":");
  if (at < 1) return null;
  const kind = value.slice(0, at) as TargetKind;
  const id = value.slice(at + 1);
  const stage = TARGET_STAGE[kind];
  return stage && ID.test(id) ? { kind, id, stage } : null;
}
