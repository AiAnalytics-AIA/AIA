"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { research, researchAgents, type ResearchAgentAction, type ResearchAgentJob, type ResearchAgentResult } from "@/lib/api";
import { followAgentJob } from "@/lib/research-agent-jobs";
import { JobError, type JobUpdate } from "@/research/jobs";
import type { ResearchProject } from "@/research/model";
import { briefFingerprint } from "@/research/model";
import type { Analysis, ResearchStore } from "@/research/store";
import { AgentProposalDialog } from "./AgentProposalDialog";

const adviceActions = new Set<ResearchAgentAction>(["critique_design", "design_copilot", "answer_memory"]);
const message = (e: unknown) => e instanceof Error ? e.message : String(e);
// Server JSON may use a different key order. Arrays retain their meaningful order.
export function canonicalProject(value: unknown): string {
  const normalize = (v: unknown): unknown => Array.isArray(v) ? v.map(normalize)
    : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).sort(([a], [b]) => a.localeCompare(b)).map(([k, x]) => [k, normalize(x)])) : v;
  return JSON.stringify(normalize(value));
}
function check(signal: AbortSignal) {
  if (signal.aborted) throw new JobError("Sledování přerušeno; běh zůstává uložený.", "cancelled", null);
}

export function useResearchAgents(studyId: string, store: ResearchStore, onUpdate: (u: JobUpdate | null) => void) {
  const [recent, setRecent] = useState<ResearchAgentJob[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<{ result: ResearchAgentResult; advice: boolean; decide: (ok: boolean) => void } | null>(null);
  const lifetime = useRef<AbortController | null>(null);
  const active = useRef<AbortController | null>(null);
  const pendingDecision = useRef<((ok: boolean) => void) | null>(null);
  const refresh = useCallback(async () => {
    const owner = lifetime.current;
    const jobs = await researchAgents.jobs(studyId);
    if (owner && owner === lifetime.current && !owner.signal.aborted) setRecent(jobs);
    return jobs;
  }, [studyId]);
  const askReview = useCallback((result: ResearchAgentResult, advice: boolean) => new Promise<boolean>((resolve) => {
    pendingDecision.current = resolve;
    setReview({ result, advice, decide: (ok) => {
      pendingDecision.current = null; setReview(null); resolve(ok);
    } });
  }), []);

  // React may run this effect after the first click: the screen is committed and
  // clickable before its passive effects flush. A mount that reset the state would
  // clear the busy flag and the open review of a run that already began, leaving it
  // waiting on a dialog nobody sees. The previous study's state is cleared when it is
  // left, in the cleanup, so the mount only starts its own work.
  useEffect(() => {
    const owner = new AbortController(); lifetime.current = owner;
    refresh().then(async (jobs) => {
      if (owner.signal.aborted || active.current) return;
      const running = jobs.find((j) => !j.is_terminal && !j.needs_attention && !j.status.startsWith("WAITING"));
      if (!running) return;
      active.current = owner; setBusy(true);
      try {
        await followAgentJob(studyId, running.run_id, "Uložený AI krok", onUpdate, owner.signal);
        check(owner.signal);
        setNotice("Návrh AI je uložený. Otevřete jej k revizi."); await refresh();
      } catch (e) { if (!owner.signal.aborted) setNotice(message(e)); }
      finally {
        if (active.current === owner) active.current = null;
        if (!owner.signal.aborted) { setBusy(false); onUpdate(null); }
      }
    }).catch((e: unknown) => { if (!owner.signal.aborted) setNotice(message(e)); });
    return () => {
      owner.abort(); active.current?.abort(); active.current = null;
      pendingDecision.current?.(false); pendingDecision.current = null;
      setRecent([]); setNotice(null); setReview(null); setBusy(false);
    };
  }, [studyId, refresh, onUpdate]);

  const apply = useCallback(async (job: ResearchAgentJob, baseline: string, signal: AbortSignal) => {
    const result = await researchAgents.result(studyId, job.run_id); check(signal);
    const advice = adviceActions.has(job.action);
    const approved = await askReview(result, advice); check(signal);
    if (advice) return { ...result.result, native: true };
    if (!approved) throw new JobError("Návrh je uložený, současný návrh jste ponechali.", "cancelled", job.run_id);
    if (canonicalProject(store.get().project) !== baseline) throw new JobError("Zadání se během AI kroku změnilo. Návrh je uložený; nejprve porovnejte změny.", "error", job.run_id);
    await researchAgents.accept(studyId, job.run_id, job.design_revision_id); check(signal);
    const project = result.result.project as ResearchProject;
    const analysis = result.result.analysis as Analysis | undefined;
    store.update(() => ({ project,
      ...(analysis ? { analysis: { ...analysis, _brief_signature: briefFingerprint(project) } } : {}) }), { reason: "native_ai_proposal_accepted" });
    try { await store.flush(); }
    catch {
      throw new JobError("Schválená revize je uložená v AIA, ale pracovní kopii se nepodařilo uložit. Opakujte uložení; AI krok nespouštějte znovu.", "error", job.run_id);
    }
    return { ...result.result, native: true };
  }, [studyId, store, askReview]);

  const finish = useCallback(async (controller: AbortController) => {
    if (active.current === controller) active.current = null;
    if (!controller.signal.aborted && !lifetime.current?.signal.aborted) {
      setBusy(false); onUpdate(null);
      // A failed inbox refresh must not hide the job's original result or error.
      await refresh().catch((e: unknown) => { if (!controller.signal.aborted) setNotice(message(e)); });
    }
  }, [onUpdate, refresh]);

  const run = useCallback(async (action: ResearchAgentAction, payload: Record<string, unknown>, title: string) => {
    if (active.current) throw new JobError("Jiný AI krok ještě běží.", "busy", null);
    const controller = new AbortController(); active.current = controller; setBusy(true); setNotice(null);
    try {
      if (action === "analyze_brief" && payload.briefing) store.update(({ project }) => ({ project: { ...project, briefing: payload.briefing } as ResearchProject }), { reason: "native_ai_context" });
      await store.flush(); check(controller.signal);
      const content = store.get().project;
      const baseline = canonicalProject(content);
      const source = action === "analyze_brief" ? "brief" : action === "propose_audience" ? "audience" : action === "suggest_dimensions" ? "persona" : "questionnaire";
      const revision = await research.submitDesign(studyId, content, source); check(controller.signal);
      let job = await researchAgents.start(studyId, revision.revision_id, action, String(payload.instruction || payload.popis || "")); check(controller.signal);
      // A repeated button press is an explicit request to continue a job that
      // parked before any provider call while the runtime was unavailable.
      if (job.status === "WAITING_PROVIDER" && job.steps.some((step) => step.waiting_reason === "ai_runtime_unavailable")) {
        job = await researchAgents.resume(studyId, job.run_id); check(controller.signal);
      }
      await refresh(); check(controller.signal);
      const finished = await followAgentJob(studyId, job.run_id, title, onUpdate, controller.signal);
      onUpdate(null);
      return await apply(finished, baseline, controller.signal);
    } finally { await finish(controller); }
  }, [store, studyId, refresh, onUpdate, apply, finish]);

  const open = useCallback(async (job: ResearchAgentJob) => {
    if (active.current) { setNotice("Jiný AI krok ještě běží."); return; }
    const controller = new AbortController(); active.current = controller; setBusy(true);
    try {
      const response = await researchAgents.design(studyId, job.design_revision_id); check(controller.signal);
      if (!adviceActions.has(job.action) && canonicalProject(response.content) !== canonicalProject(store.get().project)) {
        const result = await researchAgents.result(studyId, job.run_id); check(controller.signal);
        await askReview(result, true); check(controller.signal);
        setNotice("Návrh vychází ze staršího zadání. Pro použití jej spusťte nad současným zadáním."); return;
      }
      await apply(job, canonicalProject(store.get().project), controller.signal);
    } catch (e) { if (!controller.signal.aborted) setNotice(message(e)); }
    finally { await finish(controller); }
  }, [studyId, store, apply, askReview, finish]);
  return { run, recent, notice, busy, open, refresh,
    dialog: review ? <AgentProposalDialog result={review.result} advice={review.advice} onDecision={review.decide} /> : null };
}
