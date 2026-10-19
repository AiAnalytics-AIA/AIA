"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { researchAgents, type ResearchAgentAction, type ResearchAgentJob, type ResearchAgentResult } from "@/lib/api";
import { followAgentJob } from "@/lib/research-agent-jobs";
import { JobError, type JobUpdate } from "@/research/jobs";
import { staleDetails, staleMessage } from "@/research/proposal-items";
import { submitWorkingDesign, type ResearchStore } from "@/research/store";
import { AgentProposalDialog } from "./AgentProposalDialog";

/** What a person decides on a proposal: `true` is "apply", `false` is "keep" (the dialog's two buttons). */
export type ProposalDecision = "apply" | "keep";
const decisionOf = (d: boolean | ProposalDecision): ProposalDecision => (d === true ? "apply" : d === false ? "keep" : d);
/** A refused accept, in words: the proposal stays open to read, and may not be applied. */
export type StaleNotice = { message: string; items: string[] };

const adviceActions = new Set<ResearchAgentAction>(["critique_design", "design_copilot", "answer_memory"]);
const message = (e: unknown) => e instanceof Error ? e.message : String(e);
function check(signal: AbortSignal) {
  if (signal.aborted) throw new JobError("Sledování přerušeno; běh zůstává uložený.", "cancelled", null);
}

/**
 * `adviceInWorkspace`: advice opens in the workspace's AI panel. `proposalsInWorkspace`:
 * a design proposal is reviewed inline at the top of the stage (ProposalReview)
 * instead of the modal dialog; the decision and what it does are the same.
 */
export function useResearchAgents(studyId: string, store: ResearchStore, onUpdate: (u: JobUpdate | null) => void, adviceInWorkspace = false, proposalsInWorkspace = false) {
  const [recent, setRecent] = useState<ResearchAgentJob[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [activeAction, setActiveAction] = useState<ResearchAgentAction | null>(null);
  const [review, setReview] = useState<{ result: ResearchAgentResult; advice: boolean; stale: StaleNotice | null; decide: (d: boolean | ProposalDecision) => void } | null>(null);
  const lifetime = useRef<AbortController | null>(null);
  const active = useRef<AbortController | null>(null);
  const pendingDecision = useRef<((d: ProposalDecision) => void) | null>(null);
  const refresh = useCallback(async () => {
    const owner = lifetime.current;
    const jobs = await researchAgents.jobs(studyId);
    if (owner && owner === lifetime.current && !owner.signal.aborted) setRecent(jobs);
    return jobs;
  }, [studyId]);
  const askReview = useCallback((result: ResearchAgentResult, advice: boolean, stale: StaleNotice | null = null) => new Promise<ProposalDecision>((resolve) => {
    pendingDecision.current = resolve;
    setReview({ result, advice, stale, decide: (d) => {
      pendingDecision.current = null; setReview(null); resolve(decisionOf(d));
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
      active.current = owner; setBusy(true); setActiveAction(running.action);
      try {
        await followAgentJob(studyId, running.run_id, "Uložený AI krok", onUpdate, owner.signal);
        check(owner.signal);
        setNotice("Návrh AI je uložený. Otevřete jej k revizi."); await refresh();
      } catch (e) { if (!owner.signal.aborted) setNotice(message(e)); }
      finally {
        if (active.current === owner) active.current = null;
        if (!owner.signal.aborted) { setBusy(false); setActiveAction(null); onUpdate(null); }
      }
    }).catch((e: unknown) => { if (!owner.signal.aborted) setNotice(message(e)); });
    return () => {
      owner.abort(); active.current?.abort(); active.current = null;
      pendingDecision.current?.("keep"); pendingDecision.current = null;
      setRecent([]); setNotice(null); setReview(null); setBusy(false); setActiveAction(null);
    };
  }, [studyId, refresh, onUpdate]);

  // Accepting is one server transaction (ADR 0026 decision 6): the proposal is merged into the
  // working copy on the server, item by item, beside the new Design Revision and the ledger row.
  // The browser writes nothing back; it reloads what the server wrote. A proposal whose items
  // the person changed since its baseline is refused by name, and stays open to read.
  const apply = useCallback(async (job: ResearchAgentJob, signal: AbortSignal) => {
    const result = await researchAgents.result(studyId, job.run_id); check(signal);
    const advice = adviceActions.has(job.action);
    let stale: StaleNotice | null = null;
    for (;;) {
      const decision = await askReview(result, advice, stale); check(signal);
      if (advice) return { ...result.result, native: true };
      if (decision === "keep" || stale) throw new JobError("Návrh je uložený, současný návrh jste ponechali.", "cancelled", job.run_id);
      // A change still waiting for its save is saved first, so the server checks it too.
      await store.flush(); check(signal);
      const revision = store.get().revision;
      if (revision === null) throw new JobError("Pracovní obsah studie ještě není uložený.", "error", job.run_id);
      try {
        await researchAgents.accept(studyId, job.run_id, job.design_revision_id, revision); check(signal);
      } catch (e) {
        const details = staleDetails(e);
        if (!details) throw e;
        stale = { message: staleMessage(details, store.get().project), items: details.conflicting_items };
        setNotice(stale.message);
        continue;
      }
      try { await store.reload(); }
      catch {
        throw new JobError("Návrh je použitý a uložený v AIA, ale pracovní kopii se nepodařilo znovu načíst. Načtěte studii znovu.", "error", job.run_id);
      }
      return { ...result.result, native: true };
    }
  }, [studyId, store, askReview]);

  const finish = useCallback(async (controller: AbortController) => {
    if (active.current === controller) active.current = null;
    if (!controller.signal.aborted && !lifetime.current?.signal.aborted) {
      setBusy(false); setActiveAction(null); onUpdate(null);
      // A failed inbox refresh must not hide the job's original result or error.
      await refresh().catch((e: unknown) => { if (!controller.signal.aborted) setNotice(message(e)); });
    }
  }, [onUpdate, refresh]);

  const run = useCallback(async (action: ResearchAgentAction, payload: Record<string, unknown>, title: string) => {
    if (active.current) throw new JobError("Jiný AI krok ještě běží.", "busy", null);
    const controller = new AbortController(); active.current = controller; setBusy(true); setActiveAction(action); setNotice(null);
    try {
      if (action === "analyze_brief" && payload.briefing) store.update(({ project }) => ({ project: { ...project, briefing: payload.briefing } as typeof project }), { reason: "native_ai_context" });
      await store.flush(); check(controller.signal);
      const source = action === "analyze_brief" ? "brief" : action === "propose_audience" ? "audience" : action === "suggest_dimensions" ? "persona" : "questionnaire";
      // The design names the working revision it is: the proposal's baseline (ADR 0026 decision 5).
      const revision = await submitWorkingDesign(store, studyId, source); check(controller.signal);
      let job = await researchAgents.start(studyId, revision.revision_id, action, String(payload.instruction || payload.popis || "")); check(controller.signal);
      // A repeated button press is an explicit request to continue a job that
      // parked before any provider call while the runtime was unavailable.
      if (job.status === "WAITING_PROVIDER" && job.steps.some((step) => step.waiting_reason === "ai_runtime_unavailable")) {
        job = await researchAgents.resume(studyId, job.run_id); check(controller.signal);
      }
      await refresh(); check(controller.signal);
      const finished = await followAgentJob(studyId, job.run_id, title, onUpdate, controller.signal);
      onUpdate(null);
      return await apply(finished, controller.signal);
    } finally { await finish(controller); }
  }, [store, studyId, refresh, onUpdate, apply, finish]);

  const open = useCallback(async (job: ResearchAgentJob) => {
    if (active.current) { setNotice("Jiný AI krok ještě běží."); return; }
    const controller = new AbortController(); active.current = controller; setBusy(true); setActiveAction(job.action);
    try {
      // Whether it still applies is the server's to say, item by item, when it is accepted.
      await apply(job, controller.signal);
    } catch (e) { if (!controller.signal.aborted) setNotice(message(e)); }
    finally { await finish(controller); }
  }, [apply, finish]);
  // Continue the same advice job. A status refresh never enqueues another paid call.
  const continueAdvice = useCallback(async (job: ResearchAgentJob) => {
    if (active.current) throw new JobError("Jiný AI krok ještě běží.", "busy", job.run_id);
    if (!adviceActions.has(job.action)) throw new Error("Tento návrh otevřete v jeho kroku výzkumu.");
    const controller = new AbortController(); active.current = controller;
    setBusy(true); setActiveAction(job.action); setNotice(null);
    try {
      if (job.status === "WAITING_PROVIDER" && job.steps.some((step) => step.waiting_reason === "ai_runtime_unavailable")) {
        await researchAgents.resume(studyId, job.run_id); check(controller.signal);
      }
      const finished = await followAgentJob(studyId, job.run_id, "Uložený AI krok", onUpdate, controller.signal);
      await apply(finished, controller.signal);
    } finally { await finish(controller); }
  }, [studyId, onUpdate, apply, finish]);

  return { run, recent, notice, busy, activeAction, open, refresh, continueAdvice,
    adviceReview: adviceInWorkspace && review?.advice ? review : null,
    proposalReview: proposalsInWorkspace && review && !review.advice ? review : null,
    dialog: review && !(adviceInWorkspace && review.advice) && !(proposalsInWorkspace && !review.advice) ? <AgentProposalDialog result={review.result} advice={review.advice} onDecision={review.decide} /> : null };
}
