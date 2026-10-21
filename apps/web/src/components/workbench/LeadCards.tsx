"use client";

// The study's AI work as cards in the Research Lead's conversation (plan research-lead-workbench
// chunk 23, D15): a design job or a research run, how it stands, what it cost, the live step
// activity with its orb while the API reports a step RUNNING (StepActivityPanel, 64 px as
// step-activity.md sets it), and, once done, the way to what it changed. Every card reads the same,
// after the prototype's decision card: title and state pill, key facts as label/value rows, then
// its actions on the right. The words are lib/lead-cards.ts's; the cards start nothing paid -- a
// design job's card only follows the job a person approved, and the prepared run's card starts it
// through Spuštění's own route.

import Link from "next/link";
import { type ReactNode, useState } from "react";

import { researchAgents, research, type Readiness, type ResearchAgentJob, type ResearchRun } from "@/lib/api";
import { activityOf } from "@/lib/step-activity";
import { readBudget } from "@/lib/budget-line";
import { budgetFacts, ceilingWords, pillClass, runCard, runRequestPill, runRequestPlan, workerCard, type CardTone, type RunRequestPlan } from "@/lib/lead-cards";
import { STAGES, type WorkbenchStage } from "@/lib/workbench-stages";
import { t } from "@/i18n/t";
import type { StepKey } from "@/research/steps";
import { StepActivityPanel } from "../rehome/research/StepActivityPanel";
import { useStepActivity } from "../rehome/research/useStepActivity";
import { Glyph } from "./Glyph";
import { Icon } from "./Icons";

/** One fact of a card: its label, its value, and a smaller muted line under it. */
export type Fact = { label: string; value: ReactNode; key?: boolean; sub?: ReactNode };

export function Pill({ word, tone }: { word: string; tone: CardTone }) {
  return <span className={pillClass(tone)} data-card-pill><Glyph tone={tone} size={10} />{word}</span>;
}

/** A card's key facts as label/value rows (the prototype's kvgrid). */
export function Facts({ facts }: { facts: Fact[] }) {
  if (!facts.length) return null;
  return (
    <dl className="kvgrid wide card__facts">
      {facts.map((f) => (
        <div key={f.label} style={{ display: "contents" }}>
          <dt>{f.label}</dt>
          <dd>{f.key ? <span className="card__key">{f.value}</span> : f.value}{f.sub ? <span className="card__sub">{f.sub}</span> : null}</dd>
        </div>
      ))}
    </dl>
  );
}

/** A design job in the conversation: what, how it stands, its live activity, the way to its result. */
export function WorkerCardView({ job, studyId, onOpen, onStage, onChanged }: {
  job: ResearchAgentJob;
  studyId: string;
  /** Open a finished job's proposal (on the stage it changes) or its advice for review. */
  onOpen?: (job: ResearchAgentJob) => void;
  onStage?: (stage: WorkbenchStage) => void;
  /** Read the jobs again after this card acted on its job. */
  onChanged?: () => void;
}) {
  const c = workerCard(job);
  const live = c.orb !== null;
  const feed = useStepActivity(live || c.state === "running" ? job.run_id : null, (since) => researchAgents.events(studyId, job.run_id, since), live);
  const [resuming, setResuming] = useState(false);
  const parked = c.state === "waiting" && job.status === "WAITING_PROVIDER" && job.steps.some((s) => s.waiting_reason === "ai_runtime_unavailable");
  const facts: Fact[] = [
    { label: "Náklady", value: c.cost },
    ...(c.proposal ? [{ label: "Návrh", value: c.proposal }] : []),
    ...(c.problem ? [{ label: "Proč stojí", value: c.problem }] : []),
    ...(c.state === "awaiting_budget" ? [{ label: "Pokračuje", value: "Tatáž úloha, až zvýšíte rozpočet studie v inspektoru." }] : []),
  ];
  const actions = (c.state === "completed" || parked) && (onOpen || onStage);
  return (
    <div className="msg" data-aia={`activity.${job.run_id}`} data-card="worker" data-card-state={c.state}>
      <div className="act act--worker act__card">
        <div className="card__titlerow">
          <span className="act__type" title="Úloha AI"><Icon name="worker" size={13} /></span>
          <span className="act__title">{c.title}</span>
          <Pill word={c.word} tone={c.tone} />
        </div>
        <StepActivityPanel orb={c.orb} activity={activityOf(feed, c.stepId)} startedAt={c.startedAt} label={c.title} />
        <Facts facts={facts} />
        {actions ? (
          <div className="card__actions">
            {c.stage && onStage ? <button type="button" className="btn btn--sm btn--quiet" onClick={() => onStage(c.stage!)}><Icon name="open" size={12} />Otevřít {STAGES[c.stage].label}</button> : null}
            {parked ? <button type="button" className="btn btn--sm" disabled={resuming} onClick={() => { setResuming(true); void researchAgents.resume(studyId, job.run_id).finally(() => { setResuming(false); onChanged?.(); }); }}>Pokračovat v úloze</button> : null}
            {c.reviewable && onOpen ? <button type="button" className="btn btn--sm btn--primary" data-card-review onClick={() => onOpen(job)}>{c.advice ? "Otevřít odpověď" : "Zkontrolovat návrh"}</button> : null}
          </div>
        ) : null}
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
  const facts: Fact[] = [
    { label: "Návrh", value: `revize ${c.revision}` },
    ...(c.steps ? [{ label: "Kroky", value: `hotovo ${c.steps.done} z ${c.steps.total}` }] : []),
    ...(c.running ? [{ label: "Právě", value: c.running.label }] : []),
    { label: "Náklady", value: c.cost },
    ...(c.reading.reason ? [{ label: "Proč", value: c.reading.reason }] : []),
  ];
  return (
    <div className="msg" data-aia={`run.${run.run_id}`} data-card="run" data-card-state={c.reading.state}>
      <div className="act act--compute act__card">
        <div className="card__titlerow">
          <span className="act__type" title="Výzkumný běh"><Icon name="worker" size={13} /></span>
          <span className="act__title">{c.title}</span>
          <Pill word={c.reading.label} tone={c.tone} />
        </div>
        {c.running ? <StepActivityPanel orb={c.running.orb} activity={activityOf(feed, c.running.step.step_id)} startedAt={c.running.step.started_at} label={c.running.label} /> : null}
        <Facts facts={facts} />
        <div className="card__actions">
          <Link className="btn btn--sm btn--quiet" href={`${stepHref("progress")}${q}`}><Icon name="open" size={12} />Průběh</Link>
          {c.hasResults ? <Link className="btn btn--sm btn--primary" href={`${stepHref("results")}${q}#data`}>Výsledky<Icon name="next" size={12} /></Link> : null}
        </div>
      </div>
    </div>
  );
}

type Prepared = { readiness: Readiness; plan: RunRequestPlan; existing: ResearchRun | null; budget: { value: string; note: string | null } };

/**
 * The Lead's prepared research run as an approval card. "Zkontrolovat spuštění" submits the design the
 * person sees and reads its readiness, as Spuštění does on a visit; "Spustit výzkum" checks the working
 * copy again -- a design that changed since the check is checked anew and shown, never started -- and
 * starts it through the same route as Spuštění's Start (POST …/research/runs: readiness, the study's
 * spend limit with its confirmation, the default persona source and LIVE), or sends the person to
 * Spuštění for what only they can decide there. A run that already exists on that revision is shown,
 * never started again.
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
  const [error, setError] = useState<string | null>(null);
  const check = async (): Promise<Prepared> => {
    const { readiness, runs } = await prepare();
    const plan = runRequestPlan(readiness);
    const existing = runs.find((r) => r.design_revision_id === readiness.design_revision_id) ?? null;
    return { readiness, plan, existing, budget: budgetFacts(await readBudget(studyId), plan.kind === "start" ? plan.ceiling : null) };
  };
  const read = async () => {
    setState("reading");
    setError(null);
    try {
      setPrepared(await check());
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
      // The working copy is checked again at the click: what was checked may have changed since.
      const now = await check();
      if (now.readiness.design_revision_id !== prepared.readiness.design_revision_id || now.plan.kind !== "start" || now.existing) {
        setPrepared(now);
        setError("Návrh se od kontroly změnil. Zkontrolovali jsme ho znovu; spusťte ho, až údaje výše odpovídají.");
        return setState("open");
      }
      const run = await start(now.readiness, now.plan.confirm);
      if (!run) return setState("open");
      setState("started");
      onStarted(run);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setState("open");
    }
  };
  const p = prepared?.plan ?? null;
  const pill = runRequestPill(p, state === "started" ? "started" : prepared?.existing ? "existing" : state === "kept" ? "kept" : "open");
  const decided = state === "started" || state === "kept" || !!prepared?.existing;
  const facts: Fact[] = !prepared ? [
    { label: "Návrh", value: "Zatím nezkontrolováno" },
    { label: "Cena nejvýše", value: "Zjistí kontrola", sub: "Placený běh: hradí se z rozpočtu studie a spustí se až vaším potvrzením." },
  ] : [
    { label: "Návrh", value: <><Glyph tone={prepared.readiness.ready ? "done" : "fault"} size={10} /> {prepared.readiness.ready ? "připraven ke spuštění" : "zatím není připraven"}</>,
      sub: p?.kind === "not_ready" && p.reasons.length ? p.reasons.join(" · ") : p?.kind === "acknowledge" ? "Návrh nezodpoví všechny výzkumné otázky; mezery potvrzujete vlastními slovy na Spuštění." : undefined },
    { label: "Cena nejvýše", key: true, value: ceilingWords(p?.kind === "start" ? p.ceiling : null),
      sub: p?.kind === "ceiling_unknown" ? "Studie má limit útraty, takže běh nelze spustit, dokud cenu nelze určit." : p?.kind === "start" && p.confirm ? "Dosahuje prahu potvrzení studie: před spuštěním se zeptáme." : undefined },
    { label: "Rozpočet studie", value: prepared.budget.value, sub: prepared.budget.note ?? undefined },
    ...(p?.kind === "start" && p.source ? [{ label: "Respondenti", value: `${t(`research.exec.respondents.${p.source}`)} · populace LIVE`,
      sub: <Link href={stepHref("run")} className="linkbtn">Jiný zdroj nebo populaci zvolíte na Spuštění</Link> }] : []),
  ];
  return (
    <div className="msg" data-card="run-request" data-card-state={pill.word}>
      <div className={`dec${decided ? " is-decided" : ""}`}>
        <div className="dec__body">
          {decided ? null : <p className="card__eyebrow">Rozhodnutí patří vám</p>}
          <div className="card__titlerow"><p className="dec__title">Spuštění výzkumu</p><Pill word={pill.word} tone={pill.tone} /></div>
          <p className="dec__reason">{why}</p>
          <Facts facts={facts} />
          {prepared?.existing ? <p className="cap">Na této revizi návrhu už běh je: <Link href={`${stepHref("progress")}?run=${encodeURIComponent(prepared.existing.run_id)}`} className="linkbtn">Průběh</Link>.</p> : null}
          {state === "started" ? <p className="cap">Běh je spuštěný; jeho karta níže ukazuje, jak postupuje.</p> : null}
          {error ? <p className="cap" role="alert">{error}</p> : null}
          {!decided ? (
            <div className="card__actions">
              <button type="button" className="btn btn--sm btn--quiet" onClick={() => setState("kept")}>Teď ne</button>
              {!prepared ? <button type="button" className="btn btn--primary btn--sm" disabled={!canEdit || state !== "open"} onClick={() => void read()}>{state === "reading" ? "Kontroluji…" : "Zkontrolovat spuštění"}</button>
                : p?.kind === "start" ? <button type="button" className="btn btn--primary btn--sm" data-run-request-start disabled={!canEdit || state !== "open"} onClick={() => void go()}>{state === "starting" ? "Spouštím…" : "Spustit výzkum"}</button>
                  : <Link className="btn btn--primary btn--sm" href={stepHref("run")}>Otevřít Kontrolu a spuštění</Link>}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
