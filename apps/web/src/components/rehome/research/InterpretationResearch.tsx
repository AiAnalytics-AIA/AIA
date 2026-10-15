"use client";

import { useEffect, useState } from "react";
import { ApiError, deepResearch, research, type DeepResearchBundle, type DeepResearchRun, type ResearchRun } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { deepResearchRunningStep } from "@/lib/activity-orb";
import { activityOf } from "@/lib/step-activity";
import { StepActivityPanel } from "./StepActivityPanel";
import { useStepActivity } from "./useStepActivity";
import { phaseLabel } from "@/lib/research-execution";
import { AiButton, Button, Field, Select } from "../ui";
import { useResearch } from "./context";
import { FormattedText } from "./FormattedText";

const message = (e: unknown) => e instanceof Error ? e.message : String(e);
const coverageLabel = (status: string) => ({
  GROUNDED: "Doložené podklady", PARTIAL: "Částečné pokrytí",
  INSUFFICIENT: "Nedostatek podkladů", NO_EVIDENCE: "Bez ověřených zjištění",
}[status] ?? "Pokrytí nelze určit");

/** Research over the pinned result, with its own explicit report selection. */
export function InterpretationResearch({ run }: { run: ResearchRun }) {
  const { frame, confirm } = useResearch();
  const [jobs, setJobs] = useState<DeepResearchRun[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [bundleFor, setBundleFor] = useState<{ runId: string; value: DeepResearchBundle } | null>(null);
  const [analysisReady, setAnalysisReady] = useState<"loading" | "ready" | "incomplete" | "unavailable">("loading");
  const [preset, setPreset] = useState<"QUICK" | "STANDARD">("QUICK");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  // The stored draft the last download was, for its approval (complete-study-report B2/B1d).
  const [stored, setStored] = useState<{ runId: string; artifactId: string; approved: boolean } | null>(null);
  const artifact = run.steps.find(s => s.node_key === "analysis_research_questions" && s.status === "SUCCEEDED")?.artifact_id;
  const current = jobs.find(j => j.run_id === selected);
  const bundle = bundleFor && current && bundleFor.runId === current.run_id ? bundleFor.value : null;
  const currentStored = stored && current && stored.runId === current.run_id ? stored : null;
  const running = jobs.some(j => !j.is_terminal);
  const active = current ? deepResearchRunningStep(current.steps) : null;
  // The rešerše's feed, read live while one of its steps runs (lib/step-activity.ts).
  const feed = useStepActivity(current?.run_id ?? null, (since) => deepResearch.events(frame.studyId, current!.run_id, since), !!active);

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
    setBundleFor(null);
    if (current?.status === "COMPLETED" && frame.canEdit) {
      deepResearch.bundle(frame.studyId, current.run_id).then(
        value => { if (live) setBundleFor({ runId: current.run_id, value }); },
        (e: unknown) => { if (live) setError(message(e)); },
      );
    }
    return () => { live = false; };
  }, [frame.studyId, frame.canEdit, current?.run_id, current?.status]);

  useEffect(() => {
    if (!bundle) { setAnalysisReady("loading"); return; }
    let live = true;
    setAnalysisReady("loading");
    research.analysis(frame.studyId, run.run_id).then(
      value => { if (live) setAnalysisReady(value.complete === true ? "ready" : "incomplete"); },
      () => { if (live) setAnalysisReady("unavailable"); },
    );
    return () => { live = false; };
  }, [bundle, frame.studyId, run.run_id]);

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
    if (!current || !bundle || analysisReady !== "ready" || busy) return;
    setBusy(true); setError(null);
    try {
      const got = await deepResearch.downloadContextReport(frame.studyId, run.run_id, current.run_id);
      saveBlob(got.blob, `AIA-${frame.studyId}-with-research.docx`);
      setStored(got.artifactId ? { runId: current.run_id, artifactId: got.artifactId, approved: got.reviewState === "APPROVED_INTERNAL" } : null);
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  };

  const approve = async () => {
    if (!currentStored || busy) return;
    setBusy(true); setError(null);
    try {
      await research.approveReport(frame.studyId, run.run_id, currentStored.artifactId);
      setStored({ ...currentStored, approved: true });
    } catch (e) {
      setError(e instanceof ApiError && e.code === "separation_of_duties"
        ? "Tuto zprávu musí schválit někdo jiný než ten, kdo ji vytvořil." : message(e));
    } finally { setBusy(false); }
  };

  const control = async (action: "retry" | "cancel") => {
    if (!current || busy) return;
    if (action === "cancel" && !await confirm("Zrušit probíhající literární rešerši? Již získané podklady a vykázané náklady zůstanou uložené.")) return;
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
    <h2 id="literature-title" className="mb-2 text-base font-semibold">Literární rešerše k výsledkům</h2>
    <p className="mb-3 max-w-3xl text-sm leading-6 text-ink-muted">Rešerše hledá externí kontext k tomuto běhu. Do zprávy mohou vstoupit jen přijatá zjištění s kontrolovaným zdrojem; zachycená stránka sama o sobě není ověřený důkaz. Spuštění rešerše čerpá rozpočet studie a nemění odpovědi ani mapy.</p>
    <details className="mb-4 rounded-control border border-border p-3" open={!jobs.length}>
    <summary className="cursor-pointer text-sm font-semibold">{jobs.length ? "Spustit další rešerši · čerpá rozpočet studie" : "Přidat literární kontext k této zprávě"}</summary>
    <div className="mt-3 flex flex-wrap items-end gap-3">
      <Field label="Rozsah rešerše"><Select value={preset} onChange={e => setPreset(e.target.value as "QUICK" | "STANDARD")} disabled={busy || running}>
        <option value="QUICK">Rychlá rešerše</option><option value="STANDARD">Standardní rešerše</option>
      </Select></Field>
      <AiButton onClick={start} disabled={!frame.canEdit || !artifact || busy || running}>Spustit rešerši výsledků</AiButton>
      <Button small onClick={() => setRefresh(n => n + 1)} disabled={busy}>Obnovit</Button>
    </div>
    {!artifact ? <p className="text-sm text-ink-muted">Nejprve je potřeba dokončit analýzu výzkumných otázek.</p> : null}
    </details>
    {jobs.length ? <Field label="Rešerše pro tuto zprávu"><Select value={selected ?? ""} onChange={e => { setSelected(e.target.value); setBundleFor(null); setError(null); }}>
      {jobs.map(j => <option key={j.run_id} value={j.run_id}>{j.title ?? "Literární rešerše"} · {j.preset === "QUICK" ? "Rychlá" : j.preset === "STANDARD" ? "Standardní" : j.preset} · {phaseLabel(j.phase)} · {j.created_at ? new Date(j.created_at).toLocaleString("cs-CZ") : ""}</option>)}
    </Select></Field> : <p className="text-sm text-ink-muted">K tomuto běhu zatím není připojena interpretační rešerše.</p>}
    {current ? <div className="mt-3">
      <p role="status" className="text-sm font-semibold">{phaseLabel(current.phase)}</p>
      <StepActivityPanel orb={active?.orb ?? null} activity={activityOf(feed, active?.step.step_id)} startedAt={active?.step.started_at} label={active?.step.node_key ?? phaseLabel(current.phase)} />
      <details className="mt-2 text-xs text-ink-muted"><summary className="cursor-pointer">Identifikace rešerše</summary><p className="mt-1 break-all">{current.run_id}</p></details>
      {current.actual_cost_usd !== null ? <p className="mt-1 text-sm text-ink-muted">Skutečné náklady: {current.actual_cost_usd.toFixed(4)} USD</p> : null}
      {current.steps.filter(s => s.error_message || s.waiting_reason).map(s => <p key={s.node_key} className="mt-2 text-sm text-status-fault">{s.error_message ?? s.waiting_reason}</p>)}
      {!current.is_terminal ? <Button small disabled={busy || !frame.canEdit} onClick={() => control("cancel")}>Zrušit rešerši</Button> : null}
      {current.retryable ? <AiButton small disabled={busy || !frame.canEdit} onClick={() => control("retry")}>Zkusit znovu</AiButton> : null}
    </div> : null}
    {bundle ? <div className="mt-4 space-y-3">
      <div className="grid grid-cols-2 gap-3 rounded-control bg-surface-sunken p-3 sm:grid-cols-3">
        <div><p className="text-xs text-ink-muted">Přijatá zjištění</p><p className="text-xl font-semibold">{bundle.accepted.length}</p></div>
        <div><p className="text-xs text-ink-muted">Zachycené zdroje</p><p className="text-xl font-semibold">{bundle.snapshots.length}</p></div>
        <div><p className="text-xs text-ink-muted">Pokrytí podklady</p><p className="text-sm font-semibold">{coverageLabel(bundle.quality_status)}</p></div>
      </div>
      {bundle.accepted.length === 0 ? <p role="note" className="rounded-control border border-status-you-ink/40 bg-status-you-wash p-3 text-sm leading-6">Rešerše dokončila hledání, ale žádné externí tvrzení neprošlo ověřením. Zachycené zdroje si můžete prohlédnout níže; zpráva z nich nesmí vytvářet benchmark ani literární závěr.</p> : null}
      <div className="rounded-control border border-signal/30 bg-signal-wash p-4">
        <p className="mb-2 text-sm font-semibold">AIA zpráva s vybranou rešerší</p>
        <p className="mb-3 text-sm leading-6">{bundle.accepted.length
          ? "Zpráva spojí uložené výsledky a sociomapy s přijatými externími podklady a jejich zdroji. Stažení nespouští další placený výzkum."
          : "Zpráva může uvést, že rešerše nepřinesla ověřené zjištění; nebude tvrdit, že obsahuje externě doložený benchmark. Stažení nespouští další placený výzkum."}</p>
        {analysisReady === "incomplete" ? <p role="status" className="mb-3 text-sm font-medium">Analýza běhu není úplná. Zprávu lze stáhnout až po dokončení všech jejích částí.</p> : null}
        {analysisReady === "unavailable" ? <p role="status" className="mb-3 text-sm font-medium">Připravenost analýzy se nepodařilo ověřit. Obnovte stránku a zkuste to znovu.</p> : null}
        {analysisReady === "loading" ? <p role="status" className="mb-3 text-sm text-ink-muted">Ověřuji připravenost zprávy…</p> : null}
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={download} disabled={busy || !frame.canEdit || analysisReady !== "ready"}>{busy ? "Připravuji zprávu…" : "Stáhnout AIA zprávu s rešerší"}</Button>
          {currentStored && !currentStored.approved && frame.canEdit ? <Button onClick={approve} disabled={busy}>Schválit pro interní použití</Button> : null}
        </div>
        {currentStored ? <p className="mt-2 text-xs text-ink-muted">{currentStored.approved ? "Stažený dokument je schválen pro interní použití." : "Stažený dokument je koncept: schvalujete právě ten, který jste stáhli."}</p> : null}
      </div>
      {bundle.origins?.includes("RECORDED_FIXTURE") ? <p className="text-sm text-status-fault">Podklady obsahují testovací výměny; nejde výhradně o živou rešerši.</p> : null}
      <p className="text-sm leading-6">Níže jsou přijatá zjištění s kontrolovanou citací. Generovaná syntéza vyžaduje věcné posouzení; kontrola citací a čísel sama nepotvrzuje její interpretace. Zpráva obsahuje přijaté podklady a uvádí toto omezení.</p>
      <ol className="space-y-3" aria-label="Přijatá zjištění">{bundle.accepted.map((a, i) => {
        const source = bundle.snapshots.find(s => s.snapshot_id === a.evidence.source_ref);
        return <li key={i} data-accepted-finding className="rounded-control border border-border p-4">
          <p className="text-xs font-semibold text-ink-muted">Zjištění č. {i + 1}</p>
          <FormattedText text={a.evidence.claim} className="mt-1" />
          <p className="mt-2 break-words text-xs text-ink-muted">Zdroj: {source ? <a href={source.url} target="_blank" rel="noreferrer" className="underline">{source.title || source.url}</a> : a.evidence.source_ref}{a.score?.source_class ? ` · třída zdroje ${a.score.source_class}` : ""}</p>
          {a.evidence.quote ? <details className="mt-2 text-xs"><summary className="cursor-pointer text-ink-muted">Citovaný podklad</summary><blockquote className="mt-2 whitespace-pre-wrap border-l-2 border-border pl-3 leading-5 text-ink-muted">{a.evidence.quote}</blockquote></details> : null}
        </li>;
      })}</ol>
      <details><summary className="cursor-pointer text-sm font-medium">Zachycené zdroje ({bundle.snapshots.length})</summary>
        <ul className="mt-2 flex flex-col gap-1">{bundle.snapshots.map(s => <li key={s.snapshot_id} className="text-sm"><a href={s.url} target="_blank" rel="noreferrer" className="underline">{s.title || s.url}</a>{s.retrieval_mode ? <span className="text-xs text-ink-muted"> · {s.retrieval_mode}</span> : null}</li>)}</ul>
      </details>
      <details><summary className="cursor-pointer text-sm font-medium">Mezery a odmítnutá zjištění</summary>
        {bundle.synthesis?.brief?.gaps.length ? <><h4 className="mt-3 text-sm font-semibold">Co se nepodařilo doložit</h4>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6">{bundle.synthesis.brief.gaps.map((g, i) => <li key={i}>{g.need}{g.reason ? <span className="text-ink-muted"> · {g.reason}</span> : null}</li>)}</ul></> : null}
        <h4 className="mt-3 text-sm font-semibold">Odmítnutá zjištění: {bundle.quarantined.length}</h4>
        {bundle.quarantined.length ? <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6">{bundle.quarantined.map((q, i) => <li key={i}>{q.claim ? <FormattedText text={q.claim} /> : null}<span className={q.claim ? "text-xs text-ink-muted" : undefined}>{q.reason}{q.detail ? <span className="text-ink-muted"> · {q.detail}</span> : null}</span></li>)}</ul> : null}
        {Object.keys(bundle.counts ?? {}).length ? <p className="mt-3 text-xs text-ink-muted">Počty: {Object.entries(bundle.counts).map(([k, v]) => `${k} ${v}`).join(" · ")}</p> : null}
      </details>
      {bundle.synthesis ? <details data-synthesis-draft><summary className="cursor-pointer text-sm font-medium">Generovaný návrh syntézy · věcně neschválený</summary>
        <p className="mt-2 text-sm">Pracovní text může obsahovat nepodložené interpretace. Je uchován pro kontrolu; není součástí stažené zprávy.</p>
        {bundle.synthesis.check.status ? <p className="mt-1 text-xs text-ink-muted">Stav kontroly: {bundle.synthesis.check.status}</p> : null}
        {bundle.synthesis.check.summary ? <><h4 className="mt-3 text-sm font-semibold">Shrnutí</h4><FormattedText text={bundle.synthesis.check.summary} className="mt-1" /></> : null}
        {bundle.synthesis.check.findings.length ? <><h4 className="mt-3 text-sm font-semibold">Zjištění</h4>
          <ul className="mt-1 flex flex-col gap-3">{bundle.synthesis.check.findings.map((f, i) => {
            const rests = f.evidence_ids.map(id => bundle.accepted.findIndex(a => a.evidence.evidence_id === id)).filter(n => n >= 0).map(n => n + 1);
            return <li key={i} className="border-l-2 border-border pl-3">
              <FormattedText text={f.text} />
              <p className="mt-1 text-xs text-ink-muted">{rests.length ? `Opírá se o přijatá zjištění č. ${rests.join(", ")}` : "Neopírá se o žádné přijaté zjištění"}{f.evidence_ids.length > rests.length ? ` · odkazy mimo přijatá zjištění: ${f.evidence_ids.length - rests.length}` : ""}</p>
            </li>;
          })}</ul></> : null}
        {bundle.synthesis.check.gaps.length ? <><h4 className="mt-3 text-sm font-semibold">Mezery</h4><ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6">{bundle.synthesis.check.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul></> : null}
        {bundle.synthesis.check.limitations.length ? <><h4 className="mt-3 text-sm font-semibold">Omezení</h4><ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6">{bundle.synthesis.check.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul></> : null}
        {bundle.synthesis.check.summary_withheld || bundle.synthesis.check.excluded?.length ? <div data-synthesis-rejected>
          <h4 className="mt-3 text-sm font-semibold">Odmítnuto kontrolou</h4>
          <p className="mt-1 text-xs text-ink-muted">Text, který kontrola citací a čísel nepustila do syntézy, s důvodem.</p>
          {bundle.synthesis.check.summary_withheld ? <p className="mt-2 text-sm">Shrnutí zadrženo<span className="text-ink-muted"> · {bundle.synthesis.check.summary_withheld}</span></p> : null}
          {bundle.synthesis.check.excluded?.length ? <ul className="mt-2 flex flex-col gap-3">{bundle.synthesis.check.excluded.map((x, i) => <li key={i} className="border-l-2 border-status-fault pl-3">
            <FormattedText text={x.text} />
            <p className="mt-1 text-xs text-ink-muted">{x.reason}{x.detail ? ` · ${x.detail}` : ""}</p>
          </li>)}</ul> : null}
        </div> : null}
      </details> : null}
    </div> : null}
    {error ? <p role="alert" className="mt-3 text-sm text-status-fault">{error}</p> : null}
  </section>;
}
