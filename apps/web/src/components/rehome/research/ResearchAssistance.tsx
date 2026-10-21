"use client";

import { type ReactNode, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import type { ResearchAgentAction } from "@/lib/api";
import { ACTION_LABELS } from "@/lib/research-agent-jobs";
import type { JobUpdate } from "@/research/jobs";
import type { StepKey } from "@/research/steps";
import { t } from "@/i18n/t";
import { AiButton, Button, Field, TextArea } from "../ui";
import { Sparkle } from "../icons";
import { AgentProposalContent } from "./AgentProposalDialog";
import { JobPanel } from "./JobPanel";
import type { useResearchAgents } from "./useResearchAgents";

export type AdviceAction = Extract<ResearchAgentAction, "critique_design" | "design_copilot" | "answer_memory">;
export const isAdviceAction = (action: ResearchAgentAction | null): action is AdviceAction => action === "critique_design" || action === "design_copilot" || action === "answer_memory";
type Action = { action: ResearchAgentAction; label: string; title: string };
type Agents = ReturnType<typeof useResearchAgents>;

const SUGGESTIONS: Partial<Record<StepKey, string>> = {
  brief: "Jaké schválené podklady klienta se vztahují k tomuto zadání?",
  plan: "Které výzkumné otázky potřebují zpřesnit, aby podpořily rozhodnutí?",
  questionnaire: "Jsou škály a formulace otázek konzistentní?",
  audience: "Jaká omezení cílové skupiny mám uvést při interpretaci?",
  persona: "Které dimenze potřebují doložený zdroj?",
  run: "Jaké mezery má současný návrh před spuštěním?",
  results: "Jaké schválené znalosti klienta poskytují kontext k tématu studie?",
};
const media = () => typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(max-width: 1023px)") : null;
const subscribeNarrow = (change: () => void) => {
  const query = media(); query?.addEventListener("change", change);
  return () => query?.removeEventListener("change", change);
};
const narrowSnapshot = () => media()?.matches ?? false;
const serverSnapshot = () => false;

/**
 * Claude Research R1 layout, with AIA's real jobs/tokens and study-session drafts. `starts: false`
 * (the workbench, where every AI action goes through the Research Lead, plan research-lead-workbench
 * D15): no AI pomoc card and no way to ask from here; an advice answer opened from the
 * conversation's card is still shown, read-only.
 */
export function ResearchAssistance({ step, studyName, canEdit, memory, actions, agents, job, onCancel, studyId, starts = true, children }: {
  step: StepKey; studyName: string; canEdit: boolean; memory: Map<string, unknown>;
  actions: Action[]; agents: Agents; job: JobUpdate | null; studyId: string;
  onCancel: (id: string) => void;
  starts?: boolean;
  children: (view: { card: ReactNode; panel: ReactNode; expanded: boolean; ask: (action: AdviceAction, question?: string) => void }) => ReactNode;
}) {
  const [opened, setOpened] = useState(false);
  const [selected, setSelected] = useState<AdviceAction>(isAdviceAction(actions[0]?.action ?? null) ? actions[0].action as AdviceAction : "answer_memory");
  const [questions, setQuestions] = useState<Partial<Record<AdviceAction, string>>>(() => {
    const saved = memory.get("contextual-ai-questions");
    return saved && typeof saved === "object" ? saved as Partial<Record<AdviceAction, string>> : {};
  });
  const [error, setError] = useState<string | null>(null);
  const narrow = useSyncExternalStore(subscribeNarrow, narrowSnapshot, serverSnapshot);
  const invoker = useRef<HTMLElement | null>(null);
  const fallback = useRef<HTMLElement | null>(null);
  const dialog = useRef<HTMLDialogElement | null>(null);
  const heading = useRef<HTMLHeadingElement | null>(null);
  const question = useRef<HTMLTextAreaElement | null>(null);
  const wasOpen = useRef(false);
  const review = agents.adviceReview;
  const visible = (starts && opened) || !!review;
  const adviceJob = isAdviceAction(agents.activeAction) ? job : null;
  const saved = agents.recent.filter((item) => isAdviceAction(item.action));
  const writeQuestion = (action: AdviceAction, value: string) => {
    const next = { ...questions, [action]: value }; memory.set("contextual-ai-questions", next); setQuestions(next);
  };
  const ask = (action: AdviceAction, value?: string) => {
    if (!starts || !actions.some((item) => item.action === action)) return;
    invoker.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setSelected(action); setError(null); setOpened(true);
    if (value !== undefined) writeQuestion(action, value);
  };
  const close = () => {
    setOpened(false); review?.decide(false);
  };
  useLayoutEffect(() => {
    if (!visible) {
      if (wasOpen.current) {
        const original = invoker.current;
        const trigger = original?.dataset.assistanceTrigger;
        const replacement = trigger ? fallback.current?.querySelector<HTMLButtonElement>(`[data-assistance-trigger="${trigger}"]`) : null;
        if (original?.isConnected && !(original instanceof HTMLButtonElement && original.disabled)) original.focus();
        else if (replacement && !replacement.disabled) replacement.focus(); else fallback.current?.focus();
      }
      wasOpen.current = false;
      return;
    }
    wasOpen.current = true;
    const node = dialog.current;
    if (narrow) node?.showModal();
    (review || selected === "critique_design" ? heading.current : question.current)?.focus();
    return () => { if (node?.open) node.close(); };
  }, [visible, narrow, selected, review]);
  useEffect(() => {
    if (!visible || narrow) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented || document.querySelector("dialog[open]")) return;
      event.preventDefault(); setOpened(false); review?.decide(false);
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [visible, narrow, review]);
  const perform = async (operation: () => Promise<unknown>) => {
    setError(null);
    try { await operation(); } catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
  };
  const send = (action: AdviceAction) => {
    const instruction = action === "critique_design" ? "Zkontroluj současný návrh." : questions[action]?.trim();
    if (!instruction || !canEdit || agents.busy) return;
    setSelected(action); setOpened(true);
    void perform(() => agents.run(action, { instruction }, ACTION_LABELS[action]));
  };
  const suggestion = SUGGESTIONS[step];
  const suggestionAction: AdviceAction = actions.some((item) => item.action === "design_copilot") ? "design_copilot" : "answer_memory";
  const card = !starts ? null : <section ref={fallback} tabIndex={-1} aria-label={t("research.aiHelpLabel")} data-contextual-assistance className="w-full rounded-card border border-ai-edge bg-ai-wash p-3.5 text-ink">
    <h2 className="flex items-center gap-2 text-sm font-semibold text-ai-ink"><Sparkle size={15} />{t("research.aiHelp")} · {t(`aia.stages.${step}`)}</h2>
    {visible ? <><p className="mt-1 text-xs leading-5 text-ink-muted">Pomoc je otevřená vedle pracovní plochy. Otázka se zachová při přepínání kroků.</p><Button className="mt-2 !min-h-11 !whitespace-normal" onClick={() => (review || selected === "critique_design" ? heading.current : question.current)?.focus()}>Přejít k AI pomoci</Button></> : <>
    <p className="mt-1 text-xs leading-5 text-ink-muted">Uložený návrh a schválené znalosti klienta. AI odpověď nemění návrh ani schválení evidence.</p>
    {canEdit ? <p className="mt-1 text-xs text-ink-muted">AI kroky čerpají rozpočet této studie.</p> : null}
    {canEdit ? <div className="mt-2 flex flex-wrap gap-2">{actions.map((item, index) => <AiButton key={item.action} data-assistance-trigger={item.action} variant={index === 0 ? "primary" : "secondary"} className="!min-h-11 !whitespace-normal text-left" disabled={agents.busy}
      onClick={(event) => { invoker.current = event.currentTarget; if (item.action === "critique_design") send(item.action); else if (isAdviceAction(item.action)) ask(item.action); }}>{t(item.label)}</AiButton>)}</div>
      : <p className="mt-2 text-xs text-ink-muted">Pouze ke čtení. Uložené odpovědi můžete otevřít; nový AI krok zde nelze spustit.</p>}
    {canEdit && suggestion ? <button type="button" data-assistance-trigger="suggestion" disabled={agents.busy} onClick={() => ask(suggestionAction, suggestion)} className="mt-2 !min-h-11 rounded-control border border-dashed border-ai-edge px-3 py-2 text-left text-xs leading-5 focus-visible:outline-2 focus-visible:outline-focus-ring disabled:opacity-50">{suggestion}</button> : null}
    {agents.busy || saved.length ? <Button data-assistance-trigger="history" className="mt-2 !min-h-11 !whitespace-normal" onClick={() => { invoker.current = document.activeElement as HTMLElement; setOpened(true); }}>{agents.busy ? "Zobrazit průběh AI úlohy" : "Otevřít uložené odpovědi"}</Button> : null}
    </>}
  </section>;
  const content = <>
    <div className="flex items-start justify-between gap-3"><div><h2 ref={heading} tabIndex={-1} id="research-assistance-title" className="text-base font-semibold text-ai-ink">{review ? "Odpověď AI" : ACTION_LABELS[selected]}</h2><p className="mt-1 text-xs text-ink-muted">{studyName} · {t(`aia.stages.${step}`)}</p></div><Button className="!min-h-11 min-w-11 justify-center" aria-label="Zavřít AI pomoc" onClick={close}>×</Button></div>
    <section className="rounded-md border border-border bg-surface-sunken p-3 text-xs leading-5"><h3 className="font-semibold">Co AI uvidí</h3><p>Uloženou revizi návrhu, schválené znalosti dostupné této studii a vaši otázku.</p><p className="mt-2 text-ink-muted">Hodnoty výsledků a sociomap se neposílají automaticky. Odpověď z klientských znalostí nenahrazuje literární rešerši ani numerickou interpretaci.</p></section>
    {review ? <section aria-label="Uložená odpověď AI"><p className="mb-3 text-xs leading-5 text-ink-muted">Odpověď vychází z uloženého kontextu. Nenahrazuje schválení evidence.</p><AgentProposalContent result={review.result} /><details className="mt-3 text-xs text-ink-muted"><summary className="!min-h-11 cursor-pointer py-3">Původ odpovědi</summary><p className="break-all">Revize {review.result.provenance.design_revision_id} · kontext {review.result.provenance.context_sha256}</p></details><Button className="!min-h-11" onClick={close}>Zavřít</Button></section> : <>
      {canEdit ? <form onSubmit={(event) => { event.preventDefault(); send(selected); }} className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">{actions.filter((item) => isAdviceAction(item.action)).map((item) => <Button key={item.action} aria-pressed={selected === item.action} disabled={agents.busy} className="!min-h-11 !whitespace-normal text-left" onClick={() => setSelected(item.action as AdviceAction)}>{item.title}</Button>)}</div>
        {selected === "critique_design" ? <p className="text-sm">Zkontroluje současný uložený návrh. Rozpracované změny AIA před odesláním uloží.</p> : <Field label="Co chcete zjistit?"><TextArea ref={question} rows={4} maxLength={8000} value={questions[selected] ?? ""} disabled={agents.busy} onChange={(event) => writeQuestion(selected, event.target.value)} /></Field>}
        <AiButton type="submit" className="!min-h-11 justify-center !whitespace-normal" disabled={agents.busy || (selected !== "critique_design" && !questions[selected]?.trim())}>{agents.busy ? "Čekám na odezvu…" : selected === "critique_design" ? "AI zkontroluje návrh" : "Odeslat otázku"}</AiButton>
        <p className="text-xs leading-5 text-ink-muted">Spustí AI úlohu na pozadí · platí se z rozpočtu studie. Nový krok se spustí jen po vašem odeslání.</p>
      </form> : null}
      {agents.busy && !adviceJob ? <p role="status" className="rounded-md border border-ai-edge bg-ai-wash p-3 text-sm">{isAdviceAction(agents.activeAction) ? "Ukládám kontext nebo načítám uloženou odpověď…" : "Jiný AI krok ještě běží. Otázka zůstává rozpracovaná."}</p> : null}
      {adviceJob ? <JobPanel embedded job={adviceJob} onCancel={onCancel} studyId={studyId} /> : null}
      {error ? <p role="alert" className="rounded-md border border-status-fault bg-status-fault-wash p-3 text-sm">{error} Uloženou úlohu lze zkontrolovat níže; nový krok nespouštějte automaticky.</p> : null}
      {agents.notice ? <p role="status" className="text-sm leading-6 text-ink-muted">{agents.notice}</p> : null}
      <section aria-label="Uložené návrhy AI" className="border-t border-border pt-3"><h3 className="text-sm font-semibold">Uložené návrhy AI</h3><p className="mt-1 text-xs text-ink-muted">Otevření hotové odpovědi nevolá model.</p>
        <Button className="my-2 !min-h-11" disabled={agents.busy} onClick={() => void perform(agents.refresh)}>Obnovit stav</Button>
        {!saved.length ? <p className="text-xs text-ink-muted">Zatím zde není uložená odpověď.</p> : <ul className="space-y-2">{saved.slice(0, 8).map((item) => <li key={item.run_id} className="rounded-md border border-border p-3 text-xs"><p className="font-semibold">{ACTION_LABELS[item.action]}</p><p className="mt-1 break-all text-ink-muted">{item.status} · {item.run_id}</p><p className="mt-1 text-ink-muted">{item.actual_cost_usd === null ? "Náklady nejsou vykázané" : `${item.actual_cost_usd.toFixed(3)} USD`}</p>
          {item.steps.find((s) => s.error_message)?.error_message ? <p className="mt-2">{item.steps.find((s) => s.error_message)?.error_message}</p> : null}
          {item.status === "COMPLETED" ? <Button className="mt-2 !min-h-11" disabled={agents.busy} onClick={() => void perform(() => agents.open(item))}>Otevřít odpověď</Button>
            : !item.is_terminal ? <div className="mt-2 flex flex-wrap gap-2">{!item.needs_attention || item.status === "WAITING_PROVIDER" && item.steps.some((s) => s.waiting_reason === "ai_runtime_unavailable") ? <Button className="!min-h-11 !whitespace-normal" disabled={agents.busy || !canEdit} onClick={() => void perform(() => agents.continueAdvice(item))}>{item.status === "WAITING_PROVIDER" ? "Pokračovat v uložené úloze" : "Sledovat uloženou úlohu"}</Button> : null}{canEdit ? <Button className="!min-h-11" onClick={() => onCancel(item.run_id)}>Zrušit běh</Button> : null}</div> : null}
        </li>)}</ul>}
      </section>
    </>}
  </>;
  const panel = !visible ? null : narrow ? <dialog ref={dialog} aria-labelledby="research-assistance-title" onCancel={(event) => { event.preventDefault(); close(); }} className="fixed inset-y-0 right-0 m-0 ml-auto h-dvh max-h-dvh w-full max-w-md overflow-auto border-l border-ai-edge bg-surface-overlay p-4 text-ink shadow-[var(--shadow-overlay)] backdrop:bg-surface-inverse/40"><div className="flex min-w-0 flex-col gap-4">{content}</div></dialog>
    : <aside aria-labelledby="research-assistance-title" data-assistance-panel className="flex max-h-[calc(100vh-10rem)] min-w-0 flex-col gap-4 overflow-auto rounded-card border border-ai-edge bg-surface-raised p-4">{content}</aside>;
  // eslint-disable-next-line react-hooks/refs -- passes rendered elements and event callbacks; no ref value is read during render
  return children({ card, panel, expanded: visible && !narrow, ask });
}
