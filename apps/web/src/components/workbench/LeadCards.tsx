"use client";

// The study's AI work as cards in the Research Lead's conversation (plan research-lead-workbench
// chunk 23, D15): a design job or a research run, how it stands, what it cost, the live step
// activity with its orb while the API reports a step RUNNING (StepActivityPanel, 64 px as
// step-activity.md sets it), and, once done, the way to what it changed. The words are
// lib/lead-cards.ts's; the cards start nothing paid -- a design job's card only follows the job a
// person approved, and the prepared run's card starts it through Spuštění's own route.

import Link from "next/link";
import { useState } from "react";

import { researchAgents, research, type Readiness, type ResearchAgentJob, type ResearchRun } from "@/lib/api";
import { activityOf } from "@/lib/step-activity";
import { budgetLine, readBudget } from "@/lib/budget-line";
import { runCard, runRequestPlan, workerCard, type RunRequestPlan } from "@/lib/lead-cards";
import { STAGES, type WorkbenchStage } from "@/lib/workbench-stages";
import { t } from "@/i18n/t";
import type { StepKey } from "@/research/steps";
import { StepActivityPanel } from "../rehome/research/StepActivityPanel";
import { useStepActivity } from "../rehome/research/useStepActivity";
import { Glyph } from "./Glyph";
import { Icon } from "./Icons";

/** A design job in the conversation: what, how it stands, its live activity, the way to its result. */
export function WorkerCardView({ job, studyId, onOpen, onStage }: {
  job: ResearchAgentJob;
  studyId: string;
  /** Open a finished job's proposal (on the stage it changes) or its advice for review. */
  onOpen?: (job: ResearchAgentJob) => void;
  onStage?: (stage: WorkbenchStage) => void;
}) {
  const c = workerCard(job);
  const live = c.orb !== null;
  const feed = useStepActivity(live || c.state === "running" ? job.run_id : null, (since) => researchAgents.events(studyId, job.run_id, since), live);
  const [resuming, setResuming] = useState(false);
  const parked = c.state === "waiting" && job.status === "WAITING_PROVIDER" && job.steps.some((s) => s.waiting_reason === "ai_runtime_unavailable");
  return (
    <div className="msg" data-aia={`activity.${job.run_id}`} data-card="worker" data-card-state={c.state}>
      <div className="act act--worker">
        <div className="act__row">
          <div className="act__toggle"><span className="act__type" title="Úloha AI"><Icon name="worker" size={13} /></span>
          <span className="act__title">{c.title}</span>
          <span className="act__sum">· {c.word} · {c.cost}</span></div>
          <span className="act__right"><Glyph tone={c.tone} size={12} title={c.word} /></span>
        </div>
        <div className="act__body">
          <StepActivityPanel orb={c.orb} activity={activityOf(feed, c.stepId)} startedAt={c.startedAt} label={c.title} />
          {c.proposal ? <p className="cap">{c.proposal}</p> : null}
          {c.problem ? <p className="cap">{c.problem}</p> : null}
          {c.state === "awaiting_budget" ? <p className="cap">Pokračuje tatáž úloha, až zvýšíte rozpočet studie v inspektoru.</p> : null}
          {c.state === "completed" || parked ? (
            <div className="links">
              {c.stage && onStage ? <button type="button" className="linkchip" onClick={() => onStage(c.stage!)}><Icon name="open" size={12} />Otevřít {STAGES[c.stage].label}</button> : null}
              {c.reviewable && onOpen ? <button type="button" className="linkchip" data-card-review onClick={() => onOpen(job)}><Icon name="next" size={12} />{c.advice ? "Otevřít odpověď" : "Zkontrolovat návrh"}</button> : null}
              {parked ? <button type="button" className="linkchip" disabled={resuming} onClick={() => { setResuming(true); void researchAgents.resume(studyId, job.run_id).finally(() => setResuming(false)); }}><Icon name="next" size={12} />Pokračovat v úloze</button> : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** A research run in the conversation, however it was started: its state, the running step's
 * activity with its orb, and Průběh and Výsledky. */
export function RunCardView({ run, studyId, stepHref }: { run: ResearchRun; studyId: string; stepHref: (step: StepKey) => string }) {
  const c = runCard(run);
  const live = !!c.running?.orb;
  const feed = useStepActivity(live ? run.run_id : null, (since) => research.events(studyId, run.run_id, since), live);
  const q = `?run=${encodeURIComponent(run.run_id)}`;
  return (
    <div className="msg" data-aia={`run.${run.run_id}`} data-card="run" data-card-state={c.reading.state}>
      <div className="act act--compute">
        <div className="act__row">
          <div className="act__toggle"><span className="act__type" title="Výzkumný běh"><Icon name="worker" size={13} /></span>
          <span className="act__title">{c.title}</span>
          <span className="act__sum">· revize {c.revision} · {c.reading.label} · {c.cost}</span></div>
          <span className="act__right"><Glyph tone={c.tone} size={12} title={c.reading.label} /></span>
        </div>
        <div className="act__body">
          {c.running ? <p className="cap">Právě: {c.running.label}{c.steps ? ` · hotovo ${c.steps.done} z ${c.steps.total} kroků` : ""}</p> : null}
          {c.running ? <StepActivityPanel orb={c.running.orb} activity={activityOf(feed, c.running.step.step_id)} startedAt={c.running.step.started_at} label={c.running.label} /> : null}
          {c.reading.reason ? <p className="cap">{c.reading.reason}</p> : null}
          <div className="links">
            <Link className="linkchip" href={`${stepHref("progress")}${q}`}><Icon name="open" size={12} />Průběh</Link>
            {c.hasResults ? <Link className="linkchip" href={`${stepHref("results")}${q}#data`}><Icon name="next" size={12} />Výsledky</Link> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

type Prepared = { readiness: Readiness; plan: RunRequestPlan; existing: ResearchRun | null; budget: string };

/**
 * The Lead's prepared research run as an approval card. "Zkontrolovat" submits the design the person
 * sees and reads its readiness, as Spuštění does on a visit; the card then starts it through the
 * same route as Spuštění's Start (POST …/research/runs: readiness, the study's spend limit with its
 * confirmation, the default persona source and LIVE), or sends the person to Spuštění for what only
 * they can decide there. A run that already exists on that revision is shown, never started again.
 */
export function RunRequestCard({ studyId, why, canEdit, prepare, start, stepHref, onStarted }: {
  studyId: string;
  why: string;
  canEdit: boolean;
  /** Submit the working design and read its readiness and the study's runs. */
  prepare: () => Promise<{ readiness: Readiness; runs: ResearchRun[] }>;
  /** Start through Spuštění's route; asks the person before a cost the limit asks about. */
  start: (readiness: Readiness, confirm: { ceiling: number; limit: number } | null) => Promise<ResearchRun | null>;
  stepHref: (step: StepKey) => string;
  onStarted: (run: ResearchRun) => void;
}) {
  const [state, setState] = useState<"open" | "reading" | "kept" | "starting" | "started">("open");
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [started, setStarted] = useState<ResearchRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const read = async () => {
    setState("reading");
    setError(null);
    try {
      const { readiness, runs } = await prepare();
      const plan = runRequestPlan(readiness);
      const existing = runs.find((r) => r.design_revision_id === readiness.design_revision_id) ?? null;
      const budget = budgetLine(await readBudget(studyId), plan.kind === "start" ? plan.ceiling : undefined);
      setPrepared({ readiness, plan, existing, budget });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    setState("open");
  };
  const go = async () => {
    if (!prepared || prepared.plan.kind !== "start") return;
    setState("starting");
    setError(null);
    try {
      const run = await start(prepared.readiness, prepared.plan.confirm);
      if (!run) return setState("open");
      setStarted(run);
      setState("started");
      onStarted(run);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setState("open");
    }
  };
  const decided = state === "started" || state === "kept" || !!prepared?.existing;
  const p = prepared?.plan;
  const toRun = <Link className="btn btn--sm" href={stepHref("run")}>Otevřít Kontrolu a spuštění</Link>;
  return (
    <div className="msg" data-card="run-request">
      <div className={`dec${decided ? " is-decided" : ""}`}>
        <div className="dec__head"><Glyph tone={state === "started" ? "done" : decided ? "inert" : "you"} size={11} />{state === "started" ? "Spuštěno" : state === "kept" ? "Ponecháno" : "Rozhodnutí patří vám"}</div>
        <div className="dec__body">
          <p className="dec__title">Spuštění výzkumu</p>
          <p className="dec__reason">{why}</p>
          {!prepared ? <p className="cap">Placený běh: spustí se až vaším potvrzením se všemi kontrolami Spuštění (připravenost, zodpověditelnost, limit útraty) a hradí se z rozpočtu studie.</p> : null}
          {prepared ? (
            <ul className="dec__impact" data-run-request-plan={p?.kind}>
              <li>Návrh, jak ho vidíte: {prepared.readiness.ready ? "připraven ke spuštění" : "zatím není připraven"}</li>
              {p?.kind === "start" ? <li>Nejvýše {p.ceiling === null ? "neznámá částka" : `${p.ceiling.toFixed(2)} USD`}. {prepared.budget}</li> : null}
              {p?.kind === "start" && p.source ? <li>Respondenti: {t(`research.exec.respondents.${p.source}`)} (výchozí zdroj); populace LIVE. Jiný zdroj nebo populaci zvolíte na Spuštění.</li> : null}
              {p?.kind === "not_ready" ? p.reasons.map((r) => <li key={r}>{r}</li>) : null}
              {p?.kind === "acknowledge" ? <li>Návrh nezodpoví všechny výzkumné otázky; mezery potvrzujete vlastními slovy na Spuštění.</li> : null}
              {p?.kind === "ceiling_unknown" ? <li>Nejvyšší cenu běhu nelze určit, a studie má limit útraty: běh nelze spustit, dokud ji nelze určit.</li> : null}
            </ul>
          ) : null}
          {prepared?.existing ? <p className="cap">Na této revizi návrhu už běh je: <Link href={`${stepHref("progress")}?run=${encodeURIComponent(prepared.existing.run_id)}`} className="linkbtn">Průběh</Link>.</p> : null}
          {started ? <p className="cap">Běh je spuštěný; jeho karta níže ukazuje, jak postupuje.</p> : null}
          {error ? <p className="cap" role="alert">{error}</p> : null}
          {!decided ? (
            <div className="dec__foot">
              <button type="button" className="btn btn--sm btn--quiet" onClick={() => setState("kept")}>Teď ne</button><span className="grow" />
              {!prepared ? <button type="button" className="btn btn--primary btn--sm" disabled={!canEdit || state !== "open"} onClick={() => void read()}>{state === "reading" ? "Kontroluji…" : "Zkontrolovat spuštění"}</button>
                : p?.kind === "start" ? <button type="button" className="btn btn--primary btn--sm" data-run-request-start disabled={!canEdit || state !== "open"} onClick={() => void go()}>{state === "starting" ? "Spouštím…" : "Spustit výzkum"}</button>
                  : toRun}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
