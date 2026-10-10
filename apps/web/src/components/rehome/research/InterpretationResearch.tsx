"use client";

import { useEffect, useState } from "react";
import { ApiError, deepResearch, type DeepResearchBundle, type DeepResearchRun, type ResearchRun } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { ActivityOrb } from "@/components/brand/ActivityOrb";
import { deepResearchRunOrb } from "@/lib/activity-orb";
import { AiButton, Button, Field, Select } from "../ui";
import { useResearch } from "./context";

const message = (e: unknown) => e instanceof Error ? e.message : String(e);

/** Research over the pinned result, with its own explicit report selection. */
export function InterpretationResearch({ run }: { run: ResearchRun }) {
  const { frame, confirm } = useResearch();
  const [jobs, setJobs] = useState<DeepResearchRun[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [bundle, setBundle] = useState<DeepResearchBundle | null>(null);
  const [preset, setPreset] = useState<"QUICK" | "STANDARD">("QUICK");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const artifact = run.steps.find(s => s.node_key === "analysis_research_questions" && s.status === "SUCCEEDED")?.artifact_id;
  const current = jobs.find(j => j.run_id === selected);
  const running = jobs.some(j => !j.is_terminal);
  const orb = current ? deepResearchRunOrb(current.steps) : null;

  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const all = await deepResearch.runs(frame.studyId);
        const matching = all.filter(j => j.purpose === "INTERPRETATION_RESEARCH" && j.target?.research_run_id === run.run_id);
        if (live) {
          setJobs(matching);
          setSelected(old => matching.some(j => j.run_id === old) ? old : matching[0]?.run_id ?? null);
        }
      } catch (e) { if (live) setError(message(e)); }
    };
    void load();
    const timer = running ? setInterval(() => { void load(); }, 2500) : null;
    return () => { live = false; if (timer) clearInterval(timer); };
  }, [frame.studyId, run.run_id, refresh, running]);

  useEffect(() => {
    let live = true;
    setBundle(null);
    if (current?.status === "COMPLETED" && frame.canEdit) {
      deepResearch.bundle(frame.studyId, current.run_id).then(
        value => { if (live) setBundle(value); },
        (e: unknown) => { if (live) setError(message(e)); },
      );
    }
    return () => { live = false; };
  }, [frame.studyId, frame.canEdit, current?.run_id, current?.status]);

  const start = async () => {
    if (!artifact || busy) return;
    setBusy(true); setError(null);
    try {
      let job: DeepResearchRun;
      try {
        job = await deepResearch.interpret(frame.studyId, run.run_id, artifact, preset);
      } catch (e) {
        if (!(e instanceof ApiError) || e.code !== "cost_confirmation_required" || typeof e.details.ceiling_usd !== "number") throw e;
        const ceiling = e.details.ceiling_usd;
        if (!await confirm(`Rešerše může stát nejvýše ${ceiling.toFixed(2)} USD. Čerpá rozpočet této studie. Spustit?`)) return;
        job = await deepResearch.interpret(frame.studyId, run.run_id, artifact, preset, ceiling);
      }
      setJobs(old => [job, ...old.filter(j => j.run_id !== job.run_id)]);
      setSelected(job.run_id); setRefresh(n => n + 1);
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };

  const download = async () => {
    if (!current || !bundle || busy) return;
    setBusy(true); setError(null);
    try {
      saveBlob(await deepResearch.downloadContextReport(frame.studyId, run.run_id, current.run_id), `AIA-${frame.studyId}-with-research.docx`);
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };

  const control = async (action: "retry" | "cancel") => {
    if (!current || busy) return;
    setBusy(true); setError(null);
    try {
      try { await deepResearch[action](frame.studyId, current.run_id); }
      catch (e) {
        if (action !== "retry" || !(e instanceof ApiError) || e.code !== "cost_confirmation_required" || typeof e.details.ceiling_usd !== "number") throw e;
        const ceiling = e.details.ceiling_usd;
        if (!await confirm(`Opakování rešerše může stát nejvýše ${ceiling.toFixed(2)} USD. Čerpá rozpočet této studie. Pokračovat?`)) return;
        await deepResearch.retry(frame.studyId, current.run_id, ceiling);
      }
      setRefresh(n => n + 1);
    }
    catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };

  return <section id="res-literature" aria-labelledby="literature-title" className="scroll-mt-60 rounded-md border border-border bg-surface-raised p-4">
    <h2 id="literature-title" className="mb-2 text-lg font-semibold">Literární rešerše a externí kontext</h2>
    <p className="mb-3 text-sm text-ink-muted">Deep Research vyhledá veřejné podklady k výzkumným otázkám tohoto běhu. Ověřená zjištění, dostupné benchmarky, zdroje a omezení lze zahrnout do AIA zprávy společně s výsledky a sociomapami. Rešerše čerpá rozpočet studie.</p>
    <p className="mb-3 text-sm">Interní návrh. Externí literatura nemění odpovědi respondentů ani výpočty map. Cílená rešerše nemusí pokrýt veškerou akademickou literaturu.</p>
    <div className="mb-3 flex flex-wrap items-end gap-3">
      <Field label="Rozsah rešerše"><Select value={preset} onChange={e => setPreset(e.target.value as "QUICK" | "STANDARD")} disabled={busy || running}>
        <option value="QUICK">Rychlá rešerše</option><option value="STANDARD">Standardní rešerše</option>
      </Select></Field>
      <AiButton onClick={start} disabled={!frame.canEdit || !artifact || busy || running}>Spustit rešerši výsledků</AiButton>
      <Button small onClick={() => setRefresh(n => n + 1)} disabled={busy}>Obnovit</Button>
    </div>
    {!artifact ? <p className="text-sm text-ink-muted">Nejprve je potřeba dokončit analýzu výzkumných otázek.</p> : null}
    {jobs.length ? <Field label="Rešerše pro tuto zprávu"><Select value={selected ?? ""} onChange={e => { setSelected(e.target.value); setError(null); }}>
      {jobs.map(j => <option key={j.run_id} value={j.run_id}>{j.title ?? j.run_id} · {j.preset} · {j.status} · {j.created_at ? new Date(j.created_at).toLocaleString("cs-CZ") : ""}</option>)}
    </Select></Field> : <p className="text-sm text-ink-muted">K tomuto běhu zatím není připojena interpretační rešerše.</p>}
    {current ? <div className="mt-3">
      <div className="flex items-center gap-2">{orb ? <ActivityOrb orb={orb} /> : null}<p role="status" className="text-sm">{current.phase} · {current.run_id}</p></div>
      {current.actual_cost_usd !== null ? <p className="mt-1 text-sm text-ink-muted">Skutečné náklady: {current.actual_cost_usd.toFixed(4)} USD</p> : null}
      {current.steps.filter(s => s.error_message || s.waiting_reason).map(s => <p key={s.node_key} className="mt-2 text-sm text-status-fault">{s.error_message ?? s.waiting_reason}</p>)}
      {!current.is_terminal ? <Button small disabled={busy || !frame.canEdit} onClick={() => control("cancel")}>Zrušit rešerši</Button> : null}
      {current.retryable ? <AiButton small disabled={busy || !frame.canEdit} onClick={() => control("retry")}>Zkusit znovu</AiButton> : null}
    </div> : null}
    {bundle ? <div className="mt-4 space-y-3">
      <p className="text-sm">Stav evidence: {bundle.quality_status} · Přijatá zjištění: {bundle.accepted.length} · Zachycené zdroje: {bundle.snapshots.length}</p>
      {bundle.origins?.includes("RECORDED_FIXTURE") ? <p className="text-sm text-status-fault">Podklady obsahují testovací výměny; nejde výhradně o živou rešerši.</p> : null}
      {bundle.synthesis?.check.summary ? <p className="text-sm leading-6">{bundle.synthesis.check.summary}</p> : null}
      {bundle.synthesis?.check.findings.map((f, i) => <p key={i} className="text-sm leading-6">{f.text}</p>)}
      {bundle.accepted.length === 0 ? <p className="text-sm">Zatím nejsou ověřené podklady ani benchmarky. Zpráva uvede toto omezení.</p> : null}
      <details><summary className="cursor-pointer text-sm font-medium">Ověřená zjištění a zdroje</summary>
        {bundle.accepted.map((a, i) => <p key={i} className="mt-3 text-sm leading-6">{a.evidence.claim} <span className="text-ink-muted">({a.evidence.source_ref})</span></p>)}
        {bundle.snapshots.map(s => <p key={s.snapshot_id} className="mt-2 text-sm"><a href={s.url} target="_blank" rel="noreferrer" className="underline">{s.title || s.url}</a></p>)}
      </details>
      <details><summary className="cursor-pointer text-sm font-medium">Mezery a omezení</summary>
        {[...(bundle.synthesis?.check.gaps ?? []), ...(bundle.synthesis?.check.limitations ?? [])].map((s, i) => <p key={i} className="mt-2 text-sm">{s}</p>)}
        {bundle.synthesis?.brief?.gaps.map((g, i) => <p key={i} className="mt-2 text-sm">{g.need} {g.reason}</p>)}
        <p className="mt-2 text-sm">Odmítnutá zjištění: {bundle.quarantined.length}</p>
      </details>
      <Button onClick={download} disabled={busy || !frame.canEdit}>{busy ? "Připravuji zprávu…" : "Stáhnout AIA zprávu s rešerší"}</Button>
    </div> : null}
    {error ? <p role="alert" className="mt-3 text-sm text-status-fault">{error}</p> : null}
  </section>;
}
