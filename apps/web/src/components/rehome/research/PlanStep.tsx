"use client";

// 2. Návrh, rebuilt (research-flow-rehome.md, chunk 3) and drawn as Studio v3
// (studio-v3.md, chunk 4): the classic renderPlan with the four wrappers that run
// over it -- the design variants (1793), the wizard's way on (1789), and the
// comment workflow (26), which also removes the review note (1785) and the
// "Další krok: dotazník" card, so neither is here. Five numbered sections, jump
// chips over them and the step's dock. What each control does is
// src/research/plan.ts, parity-tested against the original; this file only draws
// it. The inline editors call the same functions the classic prompts did.

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  type TrackedSet,
  type Variant,
  addComment,
  addObject,
  addSet,
  answerFollowUps,
  applyVariant,
  commentableSelection,
  commentsToReview,
  comparableFamily,
  followUps,
  objectQuestionRows,
  planComments,
  projectVariants,
  removeComment,
  removeObject,
  removeSet,
  renameSet,
  selectedVariant,
  setTitle,
  toQuestionnaire,
  trackedSets,
  SET_PURPOSE_DEFAULT,
} from "@/research/plan";
import type { Analysis } from "@/research/store";
import { applyPlanSets, lines, proposalAnalysis, validMeasurement } from "@/research/plan-edit";
import { ProposalEditor } from "./ProposalEditor";
import { Icon, type IconName, Sparkle } from "../icons";
import { ActionDock, ChipInput, InlineConfirm, StepSection } from "../step";
import { AiButton, Button, Field, TextArea, TextInput } from "../ui";
import { useResearch } from "./context";
import { AnalysisFailureCard, useAnalysis } from "./useAnalysis";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const INPUT = `min-h-9 w-full rounded-control border border-border-strong bg-surface-raised px-2.5 text-sm text-ink placeholder:text-ink-faint ${FOCUS}`;
const LABEL = "text-xs font-medium text-ink-muted";

/** A comparable set is measured with 4–15 items (the questionnaire's SET_SIZE). */
export const SET_MIN = 4;
export const SET_MAX = 15;
const outOfRange = (set: TrackedSet) => {
  const n = (set.objects || []).length;
  return n < SET_MIN || n > SET_MAX;
};

const jumpTo = (id: string) => document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });

/**
 * The follow-up answers, one per question, as the one block of text the classic
 * textarea took: each answered question with its answer. Unanswered ones are left
 * out; the AI resolves them by assumption.
 */
export function followUpAnswers(questions: string[], answers: string[]): string {
  return questions
    .map((q, i) => ((answers[i] || "").trim() ? `${q}\n${(answers[i] || "").trim()}` : ""))
    .filter(Boolean)
    .join("\n\n");
}

export function PlanStep() {
  const { store, state, toast, stepHref, confirm, askAssistance } = useResearch();
  const router = useRouter();
  const { analyse, failure, busy } = useAnalysis();
  const a = proposalAnalysis(state);
  const p = state.project;
  const variants = projectVariants(state);
  const sets = trackedSets(a);
  const questions = followUps(a);
  const comments = planComments(p);
  const [editingNarrative, setEditingNarrative] = useState(false);
  const [editingSet, setEditingSet] = useState<string | null>(null);
  const [pendingVariant, setPendingVariant] = useState<string | null>(null);
  const editing = editingNarrative || editingSet !== null;
  useEffect(() => {
    if (!editing) return;
    const beforeUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    const leave = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const link = (e.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target || link.download || link.origin !== location.origin || link.pathname === location.pathname) return;
      e.preventDefault();
      void confirm(t("research.plan.leaveEdits")).then((discard) => { if (discard) router.push(link.pathname + link.search + link.hash); });
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", leave, true);
    return () => { window.removeEventListener("beforeunload", beforeUnload); document.removeEventListener("click", leave, true); };
  }, [editing, confirm, router]);
  const [answers, setAnswers] = useState<string[]>([]);
  // Comments still being typed: a quote and its text, kept on the page until they have text.
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const seq = useRef(0);
  const answered = questions.filter((_, i) => (answers[i] || "").trim()).length;

  const next = () => {
    if (editing) { toast(t("research.plan.pendingEdits")); return; }
    store.update(({ project }) => ({ project: toQuestionnaire(project) }), { reason: "questionnaire_path", invalidateCheck: false });
    router.push(stepHref("questionnaire"));
  };
  const short = sets.find(outOfRange);
  const dock = (
    <ActionDock
      back={{ href: stepHref("brief"), label: `1. ${t("aia.stages.brief")}` }}
      ready={!short && !editing}
      note={
        editing ? t("research.plan.pendingEdits") : short
          ? tv("research.plan.dockSetSize", { name: setTitle(short) || t("research.plan.untitledSet"), n: (short.objects || []).length })
          : comments.length
            ? tv("research.plan.dockComments", { n: comments.length })
            : a
              ? t("research.plan.dockReady")
              : null
      }
    >
      <Button variant="primary" className="!rounded-control" disabled={editing} onClick={next}>
        {t("research.plan.next")}
        <Icon name="next" size={14} />
      </Button>
    </ActionDock>
  );

  const chooseVariant = (id: string) => {
    const snapshot = store.get();
    const analysis = proposalAnalysis(snapshot);
    const r = applyVariant({ ...snapshot, analysis }, id);
    if (!r) return;
    store.update(() => ({ ...r.state, project: { ...r.state.project, ui_state: { ...r.state.project.ui_state, plan_manual_changed: false } } }), { reason: "project_variant_1793" });
    setPendingVariant(null);
    toast(tv("research.plan.variantApplied", { title: r.title }));
  };
  const variantSection = variants.length ? <>
    <Variants variants={variants} current={selectedVariant(p)} onApply={(id) => {
      if (editing) { toast(t("research.plan.pendingEdits")); return; }
      if (p.ui_state.plan_manual_changed) setPendingVariant(id); else chooseVariant(id);
    }} />
    {pendingVariant ? <InlineConfirm message={t("research.plan.variantReplace")} action={t("research.plan.variantConfirm")} onConfirm={() => chooseVariant(pendingVariant)} onCancel={() => setPendingVariant(null)} /> : null}
  </> : null;

  if (!a) {
    return (
      <div className="flex max-w-6xl flex-col gap-4">
        {variantSection}
        <section className="rounded-card border border-border bg-surface-raised px-5 py-10 text-center">
          <h2 className="text-lg font-semibold">{t("research.plan.emptyTitle")}</h2>
          <p className="mx-auto mt-1 max-w-xl text-sm text-ink-muted">{t("research.plan.manualEmptyText")}</p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <Button variant="primary" onClick={() => { store.update((current) => ({ ...current, analysis: { problem_summary: current.project.goal || "", objectives: [], hypotheses: [], research_questions: [], tracked_sets: [] } }), { reason: "plan_manual_started" }); setEditingNarrative(true); }}>{t("research.plan.createManual")}</Button>
            <Button icon="back" className="!rounded-control" onClick={() => router.push(stepHref("brief"))}>
              {t("research.plan.openBrief")}
            </Button>
            <Button variant="quiet" className="!rounded-control" onClick={next}>{t("research.plan.skipToQuestionnaire")}</Button>
          </div>
        </section>
        {dock}
      </div>
    );
  }

  const chips: OutlineItem[] = [
    ...(variants.length ? [{ id: "plan-variants", label: t("research.plan.jumpScope"), state: "done" as const }] : []),
    { id: "plan-understanding", label: t("research.plan.jumpUnderstanding"), state: editingNarrative ? "you" : p.ui_state.plan_changed26 ? "done" : "neutral" },
    { id: "plan-sets", label: tv("research.plan.jumpSets", { n: sets.length }), state: short ? "you" : sets.length ? "done" : "neutral",
      children: sets.map((set, i) => ({ id: `plan-set-${i}`, label: `${setTitle(set) || t("research.plan.untitledSet")} · ${(set.objects || []).length}`, state: outOfRange(set) ? "you" as const : "done" as const })) },
    ...(questions.length
      ? [{ id: "plan-questions", label: tv("research.plan.jumpQuestions", { a: answered, b: questions.length }), state: answered ? ("done" as const) : ("you" as const) }]
      : []),
    { id: "plan-comments", label: tv("research.plan.jumpComments", { n: comments.length }), state: comments.length ? "you" : "neutral" },
  ];
  // Section numbers follow what is on the page: no variants, no "Rozsah".
  let n = variants.length ? 1 : 0;
  // Where the proposal's text stands: the AI's, reworked from comments, or a person's own edit.
  const origin = p.ui_state.plan_changed26 ? "research.plan.originComments" : p.ui_state.plan_manual_changed ? "research.plan.originManual" : "research.plan.originAi";
  const counts = [
    { label: "objectiveTotal", value: Array.isArray(a.objectives) ? a.objectives.length : 0 },
    { label: "questionTotal", value: Array.isArray(a.research_questions) ? a.research_questions.length : 0 },
    { label: "itemTotal", value: sets.reduce((total, s) => total + (s.objects?.length ?? 0), 0) },
  ];

  return (
    <div className="grid min-w-0 items-start gap-6 xl:grid-cols-[12rem_minmax(0,1fr)] 2xl:grid-cols-[12rem_minmax(0,1fr)_20rem]">
      <Outline items={chips} />

      {/* The proposal itself: what is accepted, edited in place. */}
      <div className="flex min-w-0 flex-col gap-4">
        <div data-proposal-status className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-border pb-3">
          <span className="text-sm font-semibold">{t(origin)}</span>
          {editing ? <span role="status" className="rounded-sm bg-status-you-wash px-1.5 text-xs font-semibold text-status-you-ink">{t("research.plan.unsavedEdits")}</span> : null}
          <dl className="ml-auto flex flex-wrap gap-x-4 text-xs text-ink-muted">
            {counts.map((item) => <div key={item.label} className="flex gap-1"><dt>{t(`research.plan.${item.label}`)}</dt><dd className="font-mono font-semibold text-ink">{item.value}</dd></div>)}
          </dl>
        </div>
        {failure ? <AnalysisFailureCard failure={failure} onRetry={() => void analyse()} /> : null}
        {variantSection}
        <Commentable onQuote={(quote) => setDrafts((d) => [...d, { key: ++seq.current, quote, text: "" }])}>
          <div className="flex flex-col gap-4">
            <Understanding n={++n} analysis={a} goal={p.goal || ""} editing={editingNarrative} setEditing={setEditingNarrative} blocked={editingSet !== null || busy} />
            <Sets n={++n} analysis={a} editing={editingSet} onEditing={setEditingSet} blocked={editingNarrative || busy} />
          </div>
        </Commentable>
        {dock}
      </div>

      {/* The AI's side, kept apart from the accepted text: its check, its questions, the comments it will work in. */}
      <aside aria-label={t("research.plan.reviewTitle")} className="flex min-w-0 flex-col gap-4 xl:col-start-2 2xl:sticky 2xl:top-20 2xl:col-start-auto">
        {askAssistance ? (
          <section aria-labelledby="plan-critique" className="rounded-card border border-ai-edge bg-surface-raised p-4">
            <h2 id="plan-critique" className="text-sm font-semibold">{t("research.plan.critiqueTitle")}</h2>
            <p className="mt-1 text-[13px] leading-5 text-ink-muted">{t("research.plan.critiqueHint")}</p>
            <button
              type="button"
              disabled={busy}
              onClick={() => askAssistance("critique_design")}
              className={`mt-3 inline-flex min-h-9 items-center gap-1.5 rounded-control border border-ai-edge bg-ai-wash px-3 text-sm font-semibold text-ai-ink hover:border-ai disabled:opacity-50 ${FOCUS}`}
            >
              <Sparkle size={14} />
              {t("research.plan.critiqueOpen")}
            </button>
          </section>
        ) : null}
        {questions.length ? (
          <FollowUps
            n={++n}
            questions={questions}
            answers={answers}
            answered={answered}
            setAnswers={setAnswers}
            busy={busy || editing}
            onSubmit={async () => {
              const r = answerFollowUps(store.get().project, followUpAnswers(questions, answers));
              if ("error" in r) return r.error;
              store.update(() => ({ project: r.project }));
              setAnswers([]);
              await analyse();
              return null;
            }}
          />
        ) : null}
        <Comments
          n={++n}
          busy={busy || editing}
          drafts={drafts}
          setDrafts={setDrafts}
          onProcess={async () => {
            const reviewed = commentsToReview(store.get().project);
            if (!reviewed) return;
            store.update(() => ({ project: reviewed }), { reason: "plan_comments_applied26", invalidateCheck: false });
            if (await analyse({ force: true, byComments: true })) toast(t("research.plan.commentsDone"));
          }}
        />
        <p className="text-xs leading-5 text-ink-muted">{t("research.plan.manualNote")}</p>
      </aside>
    </div>
  );
}

const DOT: Record<"done" | "you" | "neutral", { glyph: IconName; look: string }> = {
  done: { glyph: "done", look: "bg-status-done/14 text-status-done" },
  you: { glyph: "you", look: "bg-status-you-wash text-status-you-ink" },
  neutral: { glyph: "dot", look: "bg-surface-sunken text-ink-faint" },
};

type OutlineItem = { id: string; label: string; state: "done" | "you" | "neutral"; children?: OutlineItem[] };

/** The proposal in research order: scope, understanding, each comparable set, the AI's questions, comments. */
function Outline({ items }: { items: OutlineItem[] }) {
  const entry = (c: OutlineItem, child = false) => (
    <li key={c.id}>
      <button
        type="button"
        onClick={() => jumpTo(c.id)}
        className={`flex min-h-8 w-full items-center gap-2 rounded-sm px-2 text-left leading-5 hover:bg-surface-sunken ${child ? "pl-7 text-[13px] text-ink-muted" : "text-sm text-ink"} ${FOCUS}`}
      >
        {child ? null : (
          <span aria-hidden="true" className={`inline-flex size-4 shrink-0 items-center justify-center rounded-full ${DOT[c.state].look}`}>
            <Icon name={DOT[c.state].glyph} size={10} />
          </span>
        )}
        <span className={`min-w-0 flex-1 ${child && c.state === "you" ? "font-medium text-status-you-ink" : ""}`}>{c.label}</span>
      </button>
      {c.children?.length ? <ul className="flex flex-col">{c.children.map((x) => entry(x, true))}</ul> : null}
    </li>
  );
  return (
    <nav aria-label={t("research.plan.jumpLabel")} className="min-w-0 xl:sticky xl:top-20">
      <ul className="flex flex-wrap gap-1 xl:flex-col xl:flex-nowrap xl:gap-0.5">{items.map((c) => entry(c))}</ul>
    </nav>
  );
}

function Variants({ variants, current, onApply }: { variants: Variant[]; current: string; onApply: (id: string) => void }) {
  return (
    <StepSection id="plan-variants" n={1} title={t("research.plan.variantsTitle")} hint={t("research.plan.variantsHint")}>
      <div role="radiogroup" aria-label={t("research.plan.variantsGroup")} className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
        {variants.map((v) => {
          const on = current === v.id;
          return (
            <button
              key={String(v.id)}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onApply(String(v.id))}
              className={`flex flex-col items-start gap-2 rounded-card p-4 text-left hover:border-signal ${FOCUS} ${on ? "border-2 border-signal bg-signal-wash" : "m-px border border-border bg-surface-raised"}`}
            >
              <span className="flex w-full items-start gap-2">
                <span aria-hidden="true" className={`mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full border ${on ? "border-signal" : "border-border-strong"}`}>
                  {on ? <i className="block size-2 rounded-full bg-signal" /> : null}
                </span>
                <span className="flex-1 text-sm font-semibold">{v.title}</span>
                {v.badge ? <span className="whitespace-nowrap rounded-pill bg-signal px-2 text-[11px] font-semibold leading-[18px] text-on-signal">{v.badge}</span> : null}
              </span>
              <span className="text-[13px] leading-5 text-ink-muted">{v.summary}</span>
              <span className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs leading-4">
                {v.n != null ? (
                  <>
                    <span className="text-ink-faint">{t("research.plan.variantSample")}</span>
                    <span className="font-mono">N={String(v.n)}</span>
                  </>
                ) : null}
                {v.complexity ? (
                  <>
                    <span className="text-ink-faint">{t("research.plan.variantComplexity")}</span>
                    <span>{v.complexity}</span>
                  </>
                ) : null}
                {v.tradeoff ? (
                  <>
                    <span className="text-ink-faint">{t("research.plan.variantTradeoffLabel")}</span>
                    <span>{v.tradeoff}</span>
                  </>
                ) : null}
              </span>
              {v.deep_research ? (
                <span className="inline-flex items-center gap-1 rounded-md bg-status-you-wash px-1.5 py-0.5 text-xs text-status-you-ink">
                  <Icon name="you" size={12} />
                  {t("research.plan.variantDeep")}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </StepSection>
  );
}

function Understanding({ n, analysis, goal, editing, setEditing, blocked }: { n: number; analysis: Analysis; goal: string; editing: boolean; setEditing: (v: boolean) => void; blocked: boolean }) {
  const objectives = Array.isArray(analysis.objectives) ? analysis.objectives.map(String) : [];
  const hypotheses = Array.isArray(analysis.hypotheses) ? analysis.hypotheses.map(String) : [];
  const list = (title: string, items: string[]) =>
    items.length ? (
      <div>
        <h3 className="text-[13px] font-semibold">{title}</h3>
        <ul className="mt-1 flex flex-col gap-1 text-sm leading-6">
          {items.map((x, i) => (
            <li key={i} className="flex gap-2">
              <span aria-hidden="true" className="mt-2.5 block size-1.5 shrink-0 rounded-full bg-signal" />
              <span>{x}</span>
            </li>
          ))}
        </ul>
      </div>
    ) : null;
  return (
    <StepSection
      id="plan-understanding"
      n={n}
      title={t("research.plan.understoodTitle")}
      hint={t("research.plan.understoodHint")}
      aside={<div className="flex flex-wrap gap-2">
        <Button small disabled={blocked} onClick={() => setEditing(!editing)}>{t(`research.plan.${editing ? "cancelEdits" : "edit"}`)}</Button>
      </div>}
    >
      {editing ? <ProposalEditor analysis={analysis} onClose={() => setEditing(false)} /> : <>
      <p className="text-[15px] leading-6">{String(analysis.problem_summary || goal)}</p>
      {list(t("research.plan.questionsLabel"), Array.isArray(analysis.research_questions) ? analysis.research_questions.map(String) : [])}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {list(t("research.plan.objectives"), objectives)}
        {list(t("research.plan.hypotheses"), hypotheses)}
      </div>
      </>}
    </StepSection>
  );
}

/** Porovnatelné sady: each set edited where it is drawn, through the classic editors. */
function Sets({ n, analysis, editing, onEditing, blocked }: { n: number; analysis: Analysis; editing: string | null; onEditing: (v: string | null) => void; blocked: boolean }) {
  const { store, toast } = useResearch();
  const sets = trackedSets(analysis);
  const [adding, setAdding] = useState<string | null>(null);
  const put = (next: Analysis | null, reason: string) => {
    if (next) store.update((s) => applyPlanSets(s, trackedSets(next)), { reason });
  };
  const current = () => proposalAnalysis(store.get()) as Analysis;
  const create = () => {
    // addPlanSet with the title typed here; its items are then added on the card.
    put(addSet({ ...store.get(), analysis: current() }, adding, ""), "plan_set_added");
    setAdding(null);
  };
  return (
    <StepSection
      id="plan-sets"
      n={n}
      title={t("research.plan.setsTitle")}
      hint={t("research.plan.setsHint")}
      aside={
        <Button small icon="plus" className="!rounded-control" disabled={blocked || editing !== null} onClick={() => setAdding("")}>
          {t("research.plan.addSet")}
        </Button>
      }
    >
      {adding !== null ? (
        <form
          className="mb-3 flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            create();
          }}
        >
          <input
            autoFocus
            aria-label={t("research.plan.setName")} disabled={blocked}
            placeholder={t("research.plan.newSetPlaceholder")}
            value={adding}
            onChange={(e) => setAdding(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setAdding(null)}
            className={`${INPUT} min-w-60 flex-1`}
          />
          <Button type="submit" variant="primary" className="!rounded-control" disabled={!adding.trim()}>{t("research.plan.newSetAdd")}</Button>
          <Button variant="quiet" className="!rounded-control" onClick={() => setAdding(null)}>{t("aia.cancel")}</Button>
        </form>
      ) : null}
      <p className="mb-3 max-w-3xl text-[13px] leading-5 text-ink-muted">
        {t("research.plan.principleIntro")} <b className="text-ink">{t("research.plan.principleYes")}</b> {t("research.plan.principleYesText")} <b className="text-ink">{t("research.plan.principleNo")}</b>{" "}
        {t("research.plan.principleNoText")}
      </p>
      {sets.length ? (
        <div className="grid gap-4">
          {sets.map((set, si) => (
            <SetCard
              key={`${si}-${setTitle(set)}`}
              anchor={`plan-set-${si}`}
              set={set} blocked={blocked || (editing !== null && editing !== String(si))} editing={editing === String(si)} onEditing={(value) => onEditing(value ? String(si) : null)}
              onMeasurement={(updated) => { const fresh = trackedSets(current()); put({ ...current(), tracked_sets: fresh.map((s, i) => i === si ? updated : s) }, "plan_measurement_edited"); toast(t("research.plan.measurementChanged")); }}
              onAddObject={(value) => {
                const r = addObject(current(), si, value);
                if (r && "error" in r) return toast(r.error);
                put(r?.analysis ?? null, "plan_objects");
              }}
              onRename={(value) => put(renameSet(current(), si, value), "plan_set_renamed")}
              onRemove={() => put(removeSet(current(), si), "plan_set_removed")}
              onRemoveObject={(oi) => put(removeObject(current(), si, oi), "plan_objects")}
            />
          ))}
        </div>
      ) : (
        <p className="rounded-control border border-signal-edge bg-signal-wash p-3 text-sm">{t("research.plan.noSets")}</p>
      )}
    </StepSection>
  );
}

function SetCard({ anchor, set, onAddObject, onRename, onRemove, onRemoveObject, onMeasurement, onEditing, blocked, editing }: {
  anchor: string; blocked: boolean; editing: boolean;
  onEditing: (v: boolean) => void;
  onMeasurement: (set: TrackedSet) => void;
  set: TrackedSet;
  onAddObject: (value: string) => void;
  onRename: (value: string) => void;
  onRemove: () => void;
  onRemoveObject: (oi: number) => void;
}) {
  const objects = set.objects || [];
  const [title, setTitleDraft] = useState(setTitle(set));
  const [confirming, setConfirming] = useState(false);
  const rows = objectQuestionRows(set);
  const first = rows[0];
  const bad = outOfRange(set);
  const commit = () => {
    if (title.trim() && title.trim() !== setTitle(set)) onRename(title);
    else setTitleDraft(setTitle(set));
  };
  return (
    <article id={anchor} className="flex min-w-0 scroll-mt-20 flex-col gap-3 rounded-card border border-border bg-surface p-4">
      {editing ? <MeasurementEditor set={set} onCancel={() => onEditing(false)} onSave={(updated) => { onEditing(false); onMeasurement(updated); }} /> : <>

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{comparableFamily(set)}</div>
          <input
            aria-label={t("research.plan.setName")}
            disabled={blocked}
            placeholder={t("research.plan.setName")}
            value={title}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => e.key === "Enter" && (e.currentTarget as HTMLInputElement).blur()}
            className={`-ml-1.5 mt-0.5 w-full rounded-control border border-transparent bg-transparent px-1.5 py-0.5 text-[15px] font-semibold text-ink hover:border-border focus:border-signal focus:bg-surface-raised ${FOCUS}`}
          />
        </div>
        <span className={`whitespace-nowrap rounded-md px-1.5 py-0.5 font-mono text-xs ${bad ? "bg-status-you-wash text-status-you-ink" : "bg-surface-sunken text-ink-muted"}`}>
          {tv("research.plan.setCount", { n: objects.length })}
        </span>
      </div>
      <p className="rounded-control bg-signal-wash px-3 py-2 text-xs text-signal">
        <b>{t("research.plan.compare")}</b> {set.purpose || SET_PURPOSE_DEFAULT}
      </p>
      <div className="flex flex-col gap-1">
        <span className={LABEL}>{t("research.plan.setItems")}</span>
        <ChipInput
          disabled={blocked} label={t("research.plan.setItemAdd")}
          placeholder={t("research.plan.setItemAdd")}
          values={objects}
          onAdd={onAddObject}
          onRemove={onRemoveObject}
          backspaceRemoves
        />
      </div>
      {set.object_question ? (
        <div className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.plan.setQuestion")}</span>
          <p className="text-sm">{String(set.object_question)}</p>
        </div>
      ) : null}
      {first ? (
        <div className="rounded-control border border-border bg-surface-sunken px-3 py-2.5">
          <div className={LABEL}>{t("research.plan.example")}</div>
          <div className="mt-1 text-sm font-semibold">{first.question}</div>
          <div className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
            <span>{first.low}</span>
            <span aria-hidden="true" className="flex flex-1 gap-0.5">
              {Array.from({ length: 10 }, (_, i) => (
                <i key={i} className="block h-2 flex-1 rounded-sm border border-border-strong bg-surface-raised" />
              ))}
            </span>
            <span>{first.high}</span>
          </div>
        </div>
      ) : null}
      <div className="flex flex-wrap justify-between gap-2">
        <Button small disabled={blocked} onClick={() => onEditing(true)}>{t("research.plan.editMeasurement")}</Button>
        {confirming ? (
          <InlineConfirm message={t("research.plan.removeSetConfirm")} action={t("research.plan.removeSetAction")} onConfirm={onRemove} onCancel={() => setConfirming(false)} />
        ) : (
          <Button small disabled={blocked} variant="quiet" className="!rounded-control hover:!bg-status-fault-wash hover:!text-status-fault" onClick={() => setConfirming(true)}>
            {t("research.plan.removeSet")}
          </Button>
        )}
      </div>
      </>}
    </article>
  );
}

function MeasurementEditor({ set, onSave, onCancel }: { set: TrackedSet; onSave: (s: TrackedSet) => void; onCancel: () => void }) {
  const [title, setTitle] = useState(set.title || set.object_type || "");
  const [purpose, setPurpose] = useState(set.purpose || "");
  const [items, setItems] = useState((set.objects || []).join("\n"));
  const [question, setQuestion] = useState(set.object_question || "Jak hodnotíte {object}?");
  const [low, setLow] = useState(set.scale_labels?.[0] || "vůbec");
  const [high, setHigh] = useState(set.scale_labels?.[1] || "velmi");
  const [error, setError] = useState(false);
  const updated: TrackedSet = { ...set, title: title.trim(), purpose: purpose.trim(), objects: lines(items), object_question: question.trim(), scale_labels: [low.trim(), high.trim()] };
  const preview = objectQuestionRows(updated)[0];
  return <form aria-label={t("research.plan.editMeasurement")} className="flex flex-col gap-3" onSubmit={(e) => {
    e.preventDefault();
    if (!validMeasurement(updated)) { setError(true); return; }
    onSave(updated);
  }}>
    <Field label={t("research.plan.setName")}><TextInput autoFocus value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
    <Field label={t("research.plan.purposeLabel")}><TextArea rows={2} value={purpose} onChange={(e) => setPurpose(e.target.value)} /></Field>
    <Field label={t("research.plan.objectsLabel")}><TextArea rows={5} value={items} onChange={(e) => setItems(e.target.value)} /></Field>
    <Field label={t("research.plan.setQuestion")}><TextArea rows={2} value={question} aria-describedby="measurement-template-help" onChange={(e) => setQuestion(e.target.value)} /></Field>
    <p id="measurement-template-help" className="text-xs text-ink-muted">{t("research.plan.questionHelp")}</p>
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t("research.plan.scaleLow")}><TextInput value={low} onChange={(e) => setLow(e.target.value)} /></Field>
      <Field label={t("research.plan.scaleHigh")}><TextInput value={high} onChange={(e) => setHigh(e.target.value)} /></Field>
    </div>
    {preview ? <div className="rounded-control border border-border bg-surface-sunken p-3 text-sm"><p className={LABEL}>{t("research.plan.example")}</p><p className="mt-1">{preview.question}</p><p className="mt-2 text-xs text-ink-muted">1 · {preview.low} — 10 · {preview.high}</p></div> : null}
    {error ? <p role="alert" className="text-sm text-status-fault">{t("research.plan.measurementError")}</p> : null}
    <div className="flex flex-wrap gap-2"><Button variant="primary" type="submit">{t("research.plan.saveMeasurement")}</Button><Button onClick={onCancel}>{t("research.plan.cancelEdits")}</Button></div>
  </form>;
}

function FollowUps({ n, questions, answers, answered, setAnswers, busy, onSubmit }: {
  n: number;
  questions: string[];
  answers: string[];
  answered: number;
  setAnswers: (a: string[]) => void;
  busy: boolean;
  onSubmit: () => Promise<string | null>;
}) {
  const [error, setError] = useState<string | null>(null);
  return (
    <StepSection
      id="plan-questions"
      n={n}
      title={t("research.plan.followTitle")}
      hint={t("research.plan.followHint")}
      aside={<span className="whitespace-nowrap text-xs text-ink-muted">{tv("research.plan.followAnswered", { a: answered, b: questions.length })}</span>}
    >
      <ol className="flex flex-col gap-3.5">
        {questions.map((q, i) => (
          <li key={i}>
            <label className="flex flex-col gap-1.5">
              <span className="text-sm leading-5">
                <span className="font-mono text-ink-faint">{i + 1}.</span> {q}
              </span>
              <input
                aria-label={tv("research.plan.followAnswer", { n: i + 1 })}
                placeholder={t("research.plan.followPlaceholder")}
                value={answers[i] || ""}
                onChange={(e) => {
                  const next = [...answers];
                  next[i] = e.target.value;
                  setAnswers(next);
                }}
                className={INPUT}
              />
            </label>
          </li>
        ))}
      </ol>
      {error ? <p role="alert" className="mt-2 text-sm text-status-fault">{error}</p> : null}
      <AiButton
        className="mt-4"
        disabled={busy}
        onClick={async () => {
          setError(await onSubmit());
        }}
      >
        {t("research.plan.followSubmit")}
      </AiButton>
    </StepSection>
  );
}

/**
 * The comment workflow's selection: select text in the plan, as in a word
 * processor, and a button offers to comment on it (floatButton26). Keyboard
 * selection counts as well as the mouse. The comment is then typed on its row in
 * Komentáře (Studio v3) instead of in a prompt; it is kept once it has text.
 */
type Draft = { key: number; quote: string; text: string };

function Commentable({ onQuote, children }: { onQuote: (quote: string) => void; children: ReactNode }) {
  const root = useRef<HTMLDivElement>(null);
  const [sel, setSel] = useState<{ text: string; x: number; y: number } | null>(null);

  const onSelect = () => {
    const s = window.getSelection();
    const text = commentableSelection(s?.toString() || "");
    const node = s?.anchorNode?.parentElement;
    if (!text || !s?.rangeCount || !node || !root.current?.contains(node) || node.closest("input,textarea,button,select")) {
      setSel(null);
      return;
    }
    const r = s.getRangeAt(0).getBoundingClientRect();
    setSel({ text, x: Math.max(8, Math.min(window.innerWidth - 180, r.left + r.width / 2 - 70)), y: Math.max(8, r.top - 42) });
  };

  return (
    <div ref={root} onMouseUp={onSelect} onKeyUp={onSelect}>
      {children}
      {sel ? (
        <button
          type="button"
          style={{ left: sel.x, top: sel.y }}
          // Keep the selection while the button is pressed.
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            onQuote(sel.text);
            setSel(null);
            jumpTo("plan-comments");
          }}
          className={`fixed z-40 inline-flex items-center gap-1.5 rounded-control border border-signal bg-signal px-3 py-1.5 text-xs font-semibold text-on-signal shadow-[var(--shadow-overlay)] ${FOCUS}`}
        >
          <Icon name="plus" size={12} />
          {t("research.plan.commentAdd")}
        </button>
      ) : null}
    </div>
  );
}

function Comments({ n, busy, drafts, setDrafts, onProcess }: {
  n: number;
  busy: boolean;
  drafts: Draft[];
  setDrafts: (update: (d: Draft[]) => Draft[]) => void;
  onProcess: () => Promise<void>;
}) {
  const { store, state } = useResearch();
  const cs = planComments(state.project);
  const keep = (key: number) => {
    const d = drafts.find((x) => x.key === key);
    if (!d) return;
    const next = addComment(store.get().project, d.quote, d.text);
    if (!next) return;
    store.update(() => ({ project: next }), { reason: "plan_comments26", invalidateCheck: false });
    setDrafts((all) => all.filter((x) => x.key !== key));
  };
  return (
    <StepSection id="plan-comments" n={n} optional={false} title={`${t("research.plan.commentsTitle")} · ${cs.length}`} hint={t("research.plan.commentsHint")}>
      {cs.length || drafts.length ? (
        <ul className="flex flex-col gap-2">
          {cs.map((c, i) => (
            <li key={`c-${i}`} className="flex items-start gap-3 rounded-control border border-border bg-surface px-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="text-xs italic text-ink-muted">„{c.quote}“</div>
                <div className="mt-0.5 text-sm">{c.comment}</div>
              </div>
              <Button
                small
                variant="quiet"
                aria-label={t("research.plan.commentRemove")}
                onClick={() => store.update(({ project }) => ({ project: removeComment(project, i) }), { reason: "plan_comments26", invalidateCheck: false })}
              >
                ×
              </Button>
            </li>
          ))}
          {drafts.map((d) => (
            <li key={`d-${d.key}`} className="flex items-start gap-3 rounded-control border border-signal-edge bg-signal-tint px-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="text-xs italic text-ink-muted">„{d.quote}“</div>
                <input
                  autoFocus
                  aria-label={t("research.plan.commentDraft")}
                  placeholder={t("research.plan.commentDraft")}
                  value={d.text}
                  onChange={(e) => setDrafts((all) => all.map((x) => (x.key === d.key ? { ...x, text: e.target.value } : x)))}
                  onKeyDown={(e) => e.key === "Enter" && keep(d.key)}
                  onBlur={() => keep(d.key)}
                  className={`${INPUT} mt-1`}
                />
              </div>
              <Button small variant="quiet" aria-label={t("research.plan.commentRemove")} onClick={() => setDrafts((all) => all.filter((x) => x.key !== d.key))}>
                ×
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      <AiButton className={cs.length || drafts.length ? "mt-4" : ""} disabled={!cs.length || busy} onClick={() => void onProcess()}>
        {t("research.plan.commentsProcess")}
      </AiButton>
    </StepSection>
  );
}
