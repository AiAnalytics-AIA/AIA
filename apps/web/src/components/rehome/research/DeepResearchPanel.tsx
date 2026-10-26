"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, deepResearch, type DeepResearchBundle, type DeepResearchRun } from "@/lib/api";
import { submitWorkingDesign } from "@/research/store";
import { withBudget } from "@/lib/budget-line";
import { deepResearchRunningStep } from "@/lib/activity-orb";
import { activityOf } from "@/lib/step-activity";
import { StepActivityPanel } from "./StepActivityPanel";
import { useStepActivity } from "./useStepActivity";
import { AiButton, Button } from "../ui";
import { phaseLabel } from "@/lib/research-execution";
import { coverageWords, deepStepLabel, stepProblem } from "@/lib/reason-words";
import { CodedWords } from "./CodedWords";
import { DeepResearchWaits } from "./DeepResearchWaits";
import { DesignResearchReview } from "./DesignResearchReview";
import { SearchedNothing } from "./SearchedNothing";
import { VerifiedSourceButton } from "./VerifiedSourceButton";
import { isDesignRun } from "@/lib/design-evidence";
import { onDeepResearchStarted } from "@/lib/deep-research-started";
import { useResearch } from "./context";
import { canReview } from "./frame";

const POLL_MS = 2500;
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

/** A persistent, review-only evidence surface. A bundle is never copied into the working design. */
/** The ceiling the API worked out when the study's limit asks first, or null for any other refusal. */
function askedCeiling(e: unknown): number | null {
  if (!(e instanceof ApiError) || e.code !== "cost_confirmation_required") return null;
  const ceiling = (e.details as { ceiling_usd?: unknown }).ceiling_usd;
  return typeof ceiling === "number" && Number.isFinite(ceiling) ? ceiling : null;
}

export function DeepResearchPanel() {
  const { frame, store, confirm, state } = useResearch();
  // Reading a finished review, choosing it for the report and stopping one: a closed study allows them.
  const mayReview = canReview(frame);
  const [runs, setRuns] = useState<DeepResearchRun[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [bundle, setBundle] = useState<DeepResearchBundle | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The design checkpoint's runs only (ADR 0021): an Interpretation Research run belongs to a
  // run's results, where it is read and used; here it was the newest and preselected (PC18).
  const refresh = useCallback(async () => {
    const jobs = (await deepResearch.runs(frame.studyId)).filter(isDesignRun);
    setRuns(jobs);
    setSelected((old) => old ?? jobs[0]?.run_id ?? null);
  }, [frame.studyId]);

  useEffect(() => {
    let live = true;
    deepResearch.runs(frame.studyId).then((all) => {
      if (!live) return;
      const jobs = all.filter(isDesignRun);
      setRuns(jobs);
      setSelected(jobs[0]?.run_id ?? null);
    }).catch((e: unknown) => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [frame.studyId]);

  // A run a Lead card started while this panel is open is read and shown at once.
  useEffect(() => onDeepResearchStarted(({ runId, purpose }) => {
    if (purpose !== "DESIGN_RESEARCH") return;
    setSelected(runId);
    void refresh().catch((e: unknown) => setError(message(e)));
  }), [refresh]);

  const current = runs.find((job) => job.run_id === selected) ?? null;
  const running = current ? deepResearchRunningStep(current.steps) : null;
  // The run's feed, read live while one of its steps runs (lib/step-activity.ts).
  const feed = useStepActivity(current?.run_id ?? null, (since) => deepResearch.events(frame.studyId, current!.run_id, since), !!running);
  useEffect(() => {
    if (!current || current.is_terminal) return;
    const id = setInterval(() => { void refresh().catch((e: unknown) => setError(message(e))); }, POLL_MS);
    return () => clearInterval(id);
  }, [current, refresh]);

  useEffect(() => {
    let live = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- another run's bundle is cleared before this one is read
    setBundle(null);
    if (mayReview && current?.phase === "COMPLETED") {
      deepResearch.bundle(frame.studyId, current.run_id).then((result) => {
        if (live) setBundle(result);
      }).catch((e: unknown) => { if (live) setError(message(e)); });
    }
    return () => { live = false; };
  }, [frame.studyId, mayReview, current?.run_id, current?.phase]);

  const start = async () => {
    setBusy(true); setError(null);
    try {
      await store.flush("questionnaire");
      const revision = await submitWorkingDesign(store, frame.studyId, "questionnaire");
      let job: DeepResearchRun;
      try {
        job = await deepResearch.start(frame.studyId, revision.revision_id);
      } catch (e) {
        // The study's limit asks first (6d): the ceiling the API worked out, beside what remains.
        const ceiling = askedCeiling(e);
        if (ceiling === null) throw e;
        if (!await confirm(await withBudget(frame.studyId, `Výzkum může stát nejvýše ${ceiling.toFixed(2)} USD. Čerpá rozpočet této studie. Spustit?`, ceiling))) return;
        job = await deepResearch.start(frame.studyId, revision.revision_id, ceiling);
      }
      await refresh();
      setSelected(job.run_id);
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };

  const retry = async (runId: string) => {
    try {
      try {
        await deepResearch.retry(frame.studyId, runId);
      } catch (e) {
        const ceiling = askedCeiling(e);
        if (ceiling === null) throw e;
        if (!await confirm(await withBudget(frame.studyId, `Opakování výzkumu může stát nejvýše ${ceiling.toFixed(2)} USD. Čerpá rozpočet této studie. Pokračovat?`, ceiling))) return;
        await deepResearch.retry(frame.studyId, runId, ceiling);
      }
      await refresh();
    } catch (e) { setError(message(e)); }
  };

  return (
    <section className="rounded-md border border-border bg-surface-raised p-5" aria-labelledby="deep-research-title">
      <h2 id="deep-research-title" className="text-base font-semibold">Veřejný hloubkový výzkum</h2>
      <p className="mt-1 text-sm text-ink-muted">Vyhledávání veřejných zdrojů podle schváleného nastavení rešerše. Nálezy jsou podklady k interní revizi; nejde o hotový výstup pro klienta.</p>
      {frame.canEdit ? <AiButton className="mt-3" small disabled={busy} onClick={() => void start()}>{busy ? "Spouštím…" : "Spustit veřejný výzkum"}</AiButton> : null}
      {error ? <p role="alert" className="mt-3 text-sm text-status-fault">{error}</p> : null}
      {runs.length ? (
        <div className="mt-4 flex flex-wrap gap-2" aria-label="Uložené běhy výzkumu">
          {runs.map((job) => <Button key={job.run_id} small variant={selected === job.run_id ? "primary" : "quiet"} onClick={() => setSelected(job.run_id)}>{job.created_at ? new Date(job.created_at).toLocaleString("cs-CZ") : "Nový běh"}</Button>)}
        </div>
      ) : <p className="mt-3 text-sm text-ink-muted">Zatím bez běhů.</p>}
      {current ? (
        <div className="mt-4 space-y-2 text-sm">
          <p role="status">Stav: {phaseLabel(current.phase)}</p>
          <StepActivityPanel orb={running?.orb ?? null} activity={activityOf(feed, running?.step.step_id)} startedAt={running?.step.started_at} label={running ? deepStepLabel(running.step.node_key) : "Veřejný hloubkový výzkum"} />
          {current.steps.map((step) => ({ step, problem: stepProblem(step) })).filter((x) => x.problem !== null).map(({ step, problem }) => (
            <div key={step.node_key} className="text-status-fault">{deepStepLabel(step.node_key)}: <CodedWords coded={problem!} /></div>
          ))}
          <DeepResearchWaits run={current} studyId={frame.studyId} canEdit={frame.canEdit} onChanged={() => void refresh().catch((e: unknown) => setError(message(e)))} onError={(e) => setError(message(e))} />
          {current.retryable && frame.canEdit ? <Button small variant="quiet" onClick={() => void retry(current.run_id)}>Opakovat běh</Button> : null}
          {!current.is_terminal && mayReview ? <Button small variant="quiet" onClick={() => void deepResearch.cancel(frame.studyId, current.run_id).then(refresh).catch((e: unknown) => setError(message(e)))}>Zrušit běh</Button> : null}
        </div>
      ) : null}
      {bundle ? (
        <div className="mt-4 space-y-4 text-sm">
          <p className="font-semibold">Výsledek: {coverageWords(bundle.quality_status)} · přijaté podklady {bundle.accepted.length} · odmítnuté {bundle.quarantined.length}</p>
          {current ? <SearchedNothing studyId={frame.studyId} runId={current.run_id} /> : null}
          {bundle.accepted.map((item, index) => {
            const source = bundle.snapshots.find((snapshot) => snapshot.snapshot_id === item.evidence.source_ref);
            return <article key={`${item.evidence.source_ref}-${index}`} className="rounded-sm border border-border p-3">
              <p className="font-medium">{item.evidence.claim}</p>
              <blockquote className="mt-2 border-l-2 border-border-strong pl-3 text-ink-muted">{item.evidence.quote}</blockquote>
              <p className="mt-2 text-xs text-ink-muted">Zdroj: {source ? <a href={source.url} target="_blank" rel="noopener noreferrer" className="underline">{source.title}</a> : item.evidence.source_ref} · hodnocení {item.score.score}</p>
              {source && current && item.evidence.evidence_id && mayReview ? <div className="mt-2"><VerifiedSourceButton studyId={frame.studyId} clientId={frame.clientId} runId={current.run_id} snapshotId={source.snapshot_id} evidenceId={item.evidence.evidence_id} /></div> : null}
            </article>;
          })}
          <p className="text-xs text-ink-muted">Důkazy jsou zapečetěné otiskem {bundle.sha256.slice(0, 12)}. Před použitím mimo AIA je zkontrolujte.</p>
          {/* ADR 0021 checkpoint 1: the run proposes, a person takes what they choose into the design. */}
          {current?.purpose === "DESIGN_RESEARCH" ? <DesignResearchReview key={current.run_id} studyId={frame.studyId} runId={current.run_id} store={store} project={state.project as unknown as Record<string, unknown>} canApply={frame.canEdit} /> : null}
        </div>
      ) : null}
    </section>
  );
}
