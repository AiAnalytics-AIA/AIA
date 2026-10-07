"use client";

import { useCallback, useEffect, useState } from "react";

import { deepResearch, research, type DeepResearchBundle, type DeepResearchRun } from "@/lib/api";
import { ActivityOrb } from "@/components/brand/ActivityOrb";
import { deepResearchRunOrb } from "@/lib/activity-orb";
import { AiButton, Button } from "../ui";
import { useResearch } from "./context";

const POLL_MS = 2500;
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

/** A persistent, review-only evidence surface. A bundle is never copied into the working design. */
export function DeepResearchPanel() {
  const { frame, store } = useResearch();
  const [runs, setRuns] = useState<DeepResearchRun[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [bundle, setBundle] = useState<DeepResearchBundle | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const jobs = await deepResearch.runs(frame.studyId);
    setRuns(jobs);
    setSelected((old) => old ?? jobs[0]?.run_id ?? null);
  }, [frame.studyId]);

  useEffect(() => {
    let live = true;
    deepResearch.runs(frame.studyId).then((jobs) => {
      if (!live) return;
      setRuns(jobs);
      setSelected(jobs[0]?.run_id ?? null);
    }).catch((e: unknown) => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [frame.studyId]);

  const current = runs.find((job) => job.run_id === selected) ?? null;
  const running = current ? deepResearchRunOrb(current.steps) : null;
  useEffect(() => {
    if (!current || current.is_terminal) return;
    const id = setInterval(() => { void refresh().catch((e: unknown) => setError(message(e))); }, POLL_MS);
    return () => clearInterval(id);
  }, [current, refresh]);

  useEffect(() => {
    let live = true;
    setBundle(null);
    if (frame.canEdit && current?.phase === "COMPLETED") {
      deepResearch.bundle(frame.studyId, current.run_id).then((result) => {
        if (live) setBundle(result);
      }).catch((e: unknown) => { if (live) setError(message(e)); });
    }
    return () => { live = false; };
  }, [frame.studyId, frame.canEdit, current?.run_id, current?.phase]);

  const start = async () => {
    setBusy(true); setError(null);
    try {
      await store.flush("questionnaire");
      const revision = await research.submitDesign(frame.studyId, store.get().project, "questionnaire");
      const job = await deepResearch.start(frame.studyId, revision.revision_id);
      await refresh();
      setSelected(job.run_id);
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };

  return (
    <section className="rounded-md border border-border bg-surface-raised p-5" aria-labelledby="deep-research-title">
      <h2 id="deep-research-title" className="text-base font-semibold">Veřejný hloubkový výzkum</h2>
      <p className="mt-1 text-sm text-ink-muted">Vyhledávání ve veřejné české Wikipedii. Nálezy jsou podklady k interní revizi; nejde o hotový výstup pro klienta.</p>
      {frame.canEdit ? <AiButton className="mt-3" small disabled={busy} onClick={() => void start()}>{busy ? "Spouštím…" : "Spustit veřejný výzkum"}</AiButton> : null}
      {error ? <p role="alert" className="mt-3 text-sm text-status-fault">{error}</p> : null}
      {runs.length ? (
        <div className="mt-4 flex flex-wrap gap-2" aria-label="Uložené běhy výzkumu">
          {runs.map((job) => <Button key={job.run_id} small variant={selected === job.run_id ? "primary" : "quiet"} onClick={() => setSelected(job.run_id)}>{job.created_at ? new Date(job.created_at).toLocaleString("cs-CZ") : "Nový běh"}</Button>)}
        </div>
      ) : <p className="mt-3 text-sm text-ink-muted">Zatím bez běhů.</p>}
      {current ? (
        <div className="mt-4 space-y-2 text-sm">
          <p role="status" className="flex items-center gap-2">
            {running ? <ActivityOrb orb={running} /> : null}
            Stav: {current.phase} · {current.status}
          </p>
          {current.steps.filter((step) => step.waiting_reason || step.error_message).map((step) => <p key={step.node_key} className="text-status-fault">{step.node_key}: {step.waiting_reason ?? step.error_message}</p>)}
          {current.retryable && frame.canEdit ? <Button small variant="quiet" onClick={() => void deepResearch.retry(frame.studyId, current.run_id).then(refresh).catch((e: unknown) => setError(message(e)))}>Opakovat běh</Button> : null}
          {!current.is_terminal && frame.canEdit ? <Button small variant="quiet" onClick={() => void deepResearch.cancel(frame.studyId, current.run_id).then(refresh).catch((e: unknown) => setError(message(e)))}>Zrušit běh</Button> : null}
        </div>
      ) : null}
      {bundle ? (
        <div className="mt-4 space-y-4 text-sm">
          <p className="font-semibold">Výsledek: {bundle.quality_status} · přijaté podklady {bundle.accepted.length} · odmítnuté {bundle.quarantined.length}</p>
          {bundle.accepted.map((item, index) => {
            const source = bundle.snapshots.find((snapshot) => snapshot.snapshot_id === item.evidence.source_ref);
            return <article key={`${item.evidence.source_ref}-${index}`} className="rounded-sm border border-border p-3">
              <p className="font-medium">{item.evidence.claim}</p>
              <blockquote className="mt-2 border-l-2 border-border-strong pl-3 text-ink-muted">{item.evidence.quote}</blockquote>
              <p className="mt-2 text-xs text-ink-muted">Zdroj: {source ? <a href={source.url} target="_blank" rel="noopener noreferrer" className="underline">{source.title}</a> : item.evidence.source_ref} · hodnocení {item.score.score}</p>
            </article>;
          })}
          <p className="text-xs text-ink-muted">Důkazy jsou zapečetěné otiskem {bundle.sha256.slice(0, 12)}. Před použitím mimo AIA je zkontrolujte.</p>
        </div>
      ) : null}
    </section>
  );
}
