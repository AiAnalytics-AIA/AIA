// The AI work of a study as cards in the Lead's conversation (research-lead-workbench chunk 23):
// which job is which card, its state in words, its orb only while a step runs, where its result
// opens; a research run's card the same; what a prepared run's card may do; which layout keeps
// the stages' own AI starts.
import { describe, expect, it } from "vitest";

import type { Readiness, ResearchAgentAction, ResearchAgentJob, ResearchRun, ResearchStep } from "./api";
import { ACTION_LABELS } from "./research-agent-jobs";
import { JOB_STAGE, budgetFacts, ceilingWords, conversationTimeline, costWords, jobMovesByItself, leadOwnsAiStarts, pillClass, runCard, runRequestPill, runRequestPlan, workerCard } from "./lead-cards";

const step = (over: Partial<ResearchStep> = {}): ResearchStep => ({
  step_id: "STEP-1", node_key: "agent", kind: "research_agent", stage_type: "x", status: "RUNNING", waiting_reason: null,
  attempts_recorded: 1, max_attempts: 3, started_at: "2026-10-21T08:00:00Z", finished_at: null, failure_class: null,
  error_message: null, artifact_id: null, data_origin: null, ...over,
});
const job = (over: Partial<ResearchAgentJob> = {}): ResearchAgentJob => ({
  run_id: "JOB-1", design_revision_id: "REV-1", action: "build_questionnaire", status: "RUNNING", is_terminal: false,
  needs_attention: false, context_sha256: "x", harness_version: "3", created_at: "2026-10-21T08:00:00Z",
  steps: [step()], actual_cost_usd: null, ...over,
});
const run = (over: Partial<ResearchRun> = {}): ResearchRun => ({
  run_id: "RUN-1", study_id: "STU-1", design_revision_id: "REV-1", design_revision: 4, status: "RUNNING", phase: "RUNNING",
  needs_attention: false, is_terminal: false, retryable: false, cancel_requested: false, fieldwork_source: "ai_runtime",
  retry_of: null, created: true, created_at: "2026-10-21T08:05:00Z", started_at: null, finished_at: null,
  steps: [], artifact_ids: [], actual_cost_usd: 0.42, ...over,
});

describe("a design job's card", () => {
  it("maps every one of the eight actions to the stage its proposal changes, advice to none", () => {
    const actions = Object.keys(ACTION_LABELS) as ResearchAgentAction[];
    expect(actions).toHaveLength(8);
    expect(Object.keys(JOB_STAGE).sort()).toEqual([...actions].sort());
    expect(JOB_STAGE).toEqual({
      analyze_brief: "design", build_questionnaire: "questionnaire", optimize_questionnaire: "questionnaire",
      propose_audience: "audience", suggest_dimensions: "dimensions", critique_design: null, design_copilot: null, answer_memory: null,
    });
    for (const a of actions) expect(workerCard(job({ action: a })).title).toBe(ACTION_LABELS[a]);
  });

  it("shows the action's orb while its step runs, and the live feed's step", () => {
    const c = workerCard(job());
    expect(c).toMatchObject({ state: "running", word: "běží", tone: "running", stepId: "STEP-1", orb: { state: "composing", ink: "ai" } });
  });

  it("tells queued from running, and shows no orb before the step runs", () => {
    const c = workerCard(job({ status: "QUEUED", steps: [step({ status: "RUNNABLE" })] }));
    expect(c).toMatchObject({ state: "queued", word: "ve frontě", orb: null });
  });

  it("reads a budget stop as a wait, never a failure", () => {
    const c = workerCard(job({ status: "AWAITING_BUDGET", steps: [step({ status: "AWAITING_BUDGET" })] }));
    expect(c).toMatchObject({ state: "awaiting_budget", word: "čeká na rozpočet studie", tone: "world", orb: null });
  });

  it("says what stopped a failed job, as its step recorded it", () => {
    const c = workerCard(job({ status: "FAILED", is_terminal: true, steps: [step({ status: "FAILED", error_message: "Model odmítl." })] }));
    expect(c).toMatchObject({ state: "failed", word: "selhalo", tone: "fault", problem: "Model odmítl.", reviewable: false });
  });

  it("offers a finished proposal's review while it is pending, and only then", () => {
    const done = { status: "COMPLETED", is_terminal: true, steps: [step({ status: "SUCCEEDED" })], actual_cost_usd: 0.0042 };
    expect(workerCard(job({ ...done, proposal_state: "pending" }))).toMatchObject({ state: "completed", reviewable: true, stage: "questionnaire", proposal: "návrh čeká na vaše rozhodnutí", cost: "0,0042 USD", orb: null });
    expect(workerCard(job({ ...done, proposal_state: "accepted" }))).toMatchObject({ reviewable: false, proposal: "návrh přijat" });
    expect(workerCard(job({ ...done, proposal_state: "superseded" })).reviewable).toBe(false);
    expect(workerCard(job({ ...done, action: "answer_memory", proposal_state: null }))).toMatchObject({ advice: true, reviewable: true, stage: null, proposal: null });
  });

  it("never prints an unreported cost as zero", () => {
    expect(workerCard(job()).cost).toBe("náklady nevykázány");
    expect(costWords(0)).toBe("0 USD");
  });
});

describe("a research run's card", () => {
  it("shows the running step that thinks, with its orb, and the run's state in run-state.ts's words", () => {
    const c = runCard(run({ steps: [step({ step_id: "S-c", node_key: "compile", status: "SUCCEEDED" }), step({ step_id: "S-r", node_key: "run", status: "RUNNING" }), step({ step_id: "S-a", node_key: "aggregate", status: "RUNNABLE" })] }));
    expect(c.reading.state).toBe("RUNNING");
    expect(c.running).toMatchObject({ step: { step_id: "S-r" }, orb: { state: "listening", ink: "ai" } });
    expect(c.steps).toEqual({ done: 1, total: 3 });
    expect(c.hasResults).toBe(false);
    expect(c.cost).toBe("0,42 USD");
  });

  it("offers Výsledky once its data exists, and no orb when nothing runs", () => {
    const c = runCard(run({ phase: "COMPLETED", is_terminal: true, steps: [step({ node_key: "aggregate", status: "SUCCEEDED", artifact_id: "ART-1" }), step({ node_key: "report", kind: "research_report", status: "SUCCEEDED" })] }));
    expect(c.reading.state).toBe("REPORT_READY");
    expect(c.tone).toBe("done");
    expect(c.running).toBeNull();
    expect(c.hasResults).toBe(true);
  });

  it("reads an ended run listed without its steps as unknown, never as ready", () => {
    const c = runCard(run({ phase: "COMPLETED", is_terminal: true, steps: [] }));
    expect(c.reading.state).toBe("UNKNOWN");
    expect(c.steps).toBeNull();
    expect(c.hasResults).toBe(false);
  });
});

describe("the conversation's order", () => {
  const turn = (id: string, at: string, approved?: string) => ({ turn_id: id, created_at: at, request_decision: approved ? { run_id: approved } : null });
  it("puts a job with the turn that approved it, a run with the turn whose card started it, and every other card at its time", () => {
    const turns = [turn("T1", "2026-10-21T08:00:00Z", "JOB-A"), turn("T2", "2026-10-21T09:00:00Z")];
    const jobs = [job({ run_id: "JOB-A", created_at: "2026-10-21T08:01:00Z" }), job({ run_id: "JOB-B", created_at: "2026-10-21T08:30:00Z" })];
    const runs = [run({ run_id: "RUN-A", created_at: "2026-10-21T09:01:00Z" }), run({ run_id: "RUN-B", created_at: "2026-10-21T07:00:00Z" })];
    const order = conversationTimeline(turns, jobs, runs, new Map([["T2", "RUN-A"]])).map((x) => (x.kind === "turn" ? x.turn.turn_id : x.kind === "job" ? x.job.run_id : x.run.run_id));
    expect(order).toEqual(["RUN-B", "T1", "JOB-B", "T2"]);
  });

  it("leaves a run a typed start found already started where it is: on its own when no card started it (review of #682)", () => {
    // A run started on Spuštění, then "Spusť výzkum" typed on the same revision: the reused card
    // names the run, but the run is still shown, once, at its own time.
    const turns = [{ turn_id: "T1", created_at: "2026-10-21T09:00:00Z", request_decision: { run_id: "RUN-A", reused: true } }];
    const runs = [run({ run_id: "RUN-A", created_at: "2026-10-21T08:00:00Z" })];
    const order = conversationTimeline(turns, [], runs).map((x) => (x.kind === "turn" ? x.turn.turn_id : x.kind === "job" ? x.job.run_id : x.run.run_id));
    expect(order).toEqual(["RUN-A", "T1"]);
    // Placed by the card that started it, it stays there: still once.
    const both = [{ turn_id: "T0", created_at: "2026-10-21T07:59:00Z", request_decision: { run_id: "RUN-A" } }, ...turns];
    expect(conversationTimeline(both, [], runs).map((x) => (x.kind === "turn" ? x.turn.turn_id : x.kind))).toEqual(["T0", "T1"]);
  });
});

describe("a prepared research run's card", () => {
  const ready = (over: Partial<Readiness> = {}): Readiness => ({
    design_revision_id: "REV-9", rules: "r", ready: true, checks: [], questions: 3, batteries: 0, objects: 0, n: 300,
    fieldwork_source: "ai_runtime", cost_ceiling_usd: 4.2, cost_ceiling_unknown: null, fieldwork_requests: 300, analysis_calls: 8,
    spend_confirm_usd: null, confirmation_required: false, persona_source: "fictional_roster", ...over,
  });
  it("starts a ready design, asking first where the study's limit asks", () => {
    expect(runRequestPlan(ready())).toEqual({ kind: "start", ceiling: 4.2, confirm: null, source: "fictional_roster" });
    expect(runRequestPlan(ready({ spend_confirm_usd: 2, confirmation_required: true }))).toEqual({ kind: "start", ceiling: 4.2, confirm: { ceiling: 4.2, limit: 2 }, source: "fictional_roster" });
  });
  it("sends the person to Spuštění for what only they decide there", () => {
    expect(runRequestPlan(ready({ ready: false, checks: [{ id: "q", status: "FAIL", message: "Dotazník je prázdný." }, { id: "w", status: "WARN", message: "Malý vzorek." }] }))).toEqual({ kind: "not_ready", reasons: ["Dotazník je prázdný."] });
    expect(runRequestPlan(ready({ answerability: { capable: false, acknowledgement_required: true, digest: "d", gaps: [] } as unknown as Readiness["answerability"] })).kind).toBe("acknowledge");
    expect(runRequestPlan(ready({ cost_ceiling_usd: null, spend_confirm_usd: 2 })).kind).toBe("ceiling_unknown");
  });
});

describe("which layout keeps the stages' own AI starts", () => {
  it("gives them to the Lead in the workbench, and leaves them in the classic layout until it has a Lead", () => {
    expect(leadOwnsAiStarts("workbench")).toBe(true);
    expect(leadOwnsAiStarts("classic")).toBe(false);
  });
});

describe("what a card's facts and pill say", () => {
  it("names the ceiling as a figure, or unknown, never zero for unknown", () => {
    expect(ceilingWords(4.2)).toBe("4,2 USD");
    expect(ceilingWords(null)).toMatch(/^Neznámá/);
  });

  it("reads the budget before and at least after the run, or says it may cost more, or that it is unknown", () => {
    expect(budgetFacts({ remaining_usd: 10 }, 4)).toEqual({ value: "zbývá 10 USD → nejméně 6 USD", note: "Bez částek, které právě drží běžící kroky." });
    expect(budgetFacts({ remaining_usd: 2 }, 4).value).toBe("zbývá 2 USD → běh může stát víc");
    expect(budgetFacts({ remaining_usd: 2 }, null).value).toBe("zbývá 2 USD → po běhu neznámo");
    expect(budgetFacts(null, 4)).toEqual({ value: "Kolik zbývá, AIA nyní neví", note: null });
  });

  it("gives the prepared run's card its pill from the check and the decision", () => {
    expect(runRequestPill(null, "open")).toEqual({ word: "Ke kontrole", tone: "you" });
    expect(runRequestPill({ kind: "start", ceiling: 1, confirm: null, source: null }, "open").word).toBe("Připraveno");
    expect(runRequestPill({ kind: "not_ready", reasons: [] }, "open")).toEqual({ word: "Blokuje: připravenost", tone: "fault" });
    expect(runRequestPill({ kind: "start", ceiling: 1, confirm: null, source: null }, "started").word).toBe("Spuštěno");
    expect(pillClass("fault")).toBe("statepill statepill--fault");
    expect(pillClass("inert")).toBe("statepill");
  });
});

describe("which jobs are read again on a timer", () => {
  it("polls a queued or running job, and never one that waits for a person, budget or the AI runtime", () => {
    expect(jobMovesByItself(job())).toBe(true);
    expect(jobMovesByItself(job({ status: "QUEUED", steps: [step({ status: "RUNNABLE" })] }))).toBe(true);
    expect(jobMovesByItself(job({ status: "AWAITING_BUDGET", steps: [step({ status: "AWAITING_BUDGET" })] }))).toBe(false);
    expect(jobMovesByItself(job({ status: "RECOVERY_REQUIRED", needs_attention: true }))).toBe(false);
    expect(jobMovesByItself(job({ status: "WAITING_PROVIDER", steps: [step({ status: "WAITING_PROVIDER", waiting_reason: "ai_runtime_unavailable" })] }))).toBe(false);
    expect(jobMovesByItself(job({ status: "COMPLETED", is_terminal: true }))).toBe(false);
  });
});
