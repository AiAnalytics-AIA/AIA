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
import { hashTarget } from "@/lib/answerability";
import { openPlace, scrollToPlace } from "@/lib/open-place";
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
  QUESTION_DEFAULT,
  SCALE_DEFAULT,
  SET_PURPOSE_DEFAULT,
} from "@/research/plan";
import { type SetLimits, setAboveRecommended, setSizeRefused, setWords } from "@/research/questionnaire";
import type { Analysis } from "@/research/store";
import { type SetField, applyPlanSets, objectProblem, proposalAnalysis, setFieldProblem, withObject, withSetField } from "@/research/plan-edit";
import { DesignCoverage } from "./DesignCoverage";
import { PlanNarrative } from "./PlanNarrative";
import { Icon, type IconName } from "../icons";
import { ActionDock, ChipInput, InlineConfirm, StepSection } from "../step";
import { AiButton, Button } from "../ui";
import { InlineText } from "../../ui/InlineText";
import { useResearch } from "./context";
import { SavedForLead, useLeadOwnsAiStarts } from "./AskLead";
import { AnalysisFailureCard, modeOf, useAnalysis } from "./useAnalysis";
import { readyLimits, readySetLimits, useSampleLimits } from "./useSampleLimits";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const INPUT = `min-h-9 w-full rounded-control border border-border-strong bg-surface-raised px-2.5 text-sm text-ink placeholder:text-ink-faint ${FOCUS}`;
const LABEL = "text-xs font-medium text-ink-muted";

/** A set that stops the plan by the limits in force; above the recommendation it only warns (Q75 (a)). */
const outOfRange = (set: TrackedSet, l: SetLimits) => setSizeRefused((set.objects || []).length, l);

const jumpTo = (id: string) => scrollToPlace(id, "start");
/**
 * Whether a field inside `el` holds a draft refused at the field (I9), which a remount or a way out
 * would drop. `remount: "items"`: only a chip being reworded, which an item's removal remounts
 * (a chip of ChipInput's data-chips list; its add field, a sibling of the chips, keeps its draft).
 */
const holdsRefused = (el: Element | null, remount?: "items") =>
  !!el?.querySelector(remount ? '[data-chips] > span [aria-invalid="true"]' : '[aria-invalid="true"]');

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
  const { store, state, toast, stepHref, confirm, frame } = useResearch();
  const sampleLimits = useSampleLimits(frame.studyId);
  const setLimits = readySetLimits(sampleLimits);
  const router = useRouter();
  const { analyse, resume, failure, busy } = useAnalysis();
  const a = proposalAnalysis(state);
  const p = state.project;
  const variants = projectVariants(state);
  const sets = trackedSets(a);
  const questions = followUps(a);
  const comments = planComments(p);
  const [pendingVariant, setPendingVariant] = useState<string | null>(null);
  // Every field saves itself, so nothing is unsaved but a draft refused at its field, which stays
  // there (I9). Leaving the stage would drop it: the person is asked first, on any way out.
  const root = useRef<HTMLDivElement>(null);
  const held = () => holdsRefused(root.current);
  useEffect(() => {
    const beforeUnload = (e: BeforeUnloadEvent) => { if (held()) e.preventDefault(); };
    const leave = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !held()) return;
      const link = (e.target as Element).closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.target || link.download || link.origin !== location.origin || link.pathname === location.pathname) return;
      e.preventDefault();
      void confirm(t("research.plan.setField.leave")).then((discard) => { if (discard) router.push(link.pathname + link.search + link.hash); });
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", leave, true);
    return () => { window.removeEventListener("beforeunload", beforeUnload); document.removeEventListener("click", leave, true); };
  }, [confirm, router]);
  // A link to a section of the plan (#plan-understanding: the Run stage's gap of a design with no
  // research question, lib/answerability.ts gapFixes) opens it, once the plan is drawn.
  const drawn = !!a;
  useEffect(() => {
    if (!drawn) return;
    const read = () => {
      const id = hashTarget(window.location.hash);
      // Focus follows the scroll there, so Tab goes on from the place (openPlace).
      if (id) window.requestAnimationFrame(() => openPlace(id, "start"));
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, [drawn]);
  const [answers, setAnswers] = useState<string[]>([]);
  // In the workbench the Lead updates the design from the person's answers and comments (the owner,
  // 2026-10-21): these controls save them into the working copy only, with no paid call.
  const leadOwnsAiStarts = useLeadOwnsAiStarts();
  const [savedForLead, setSavedForLead] = useState<"answers" | "comments" | null>(null);
  // Comments still being typed: a quote and its text, kept on the page until they have text.
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const seq = useRef(0);
  const answered = questions.filter((_, i) => (answers[i] || "").trim()).length;

  const next = async () => {
    if (held() && !(await confirm(t("research.plan.setField.leave")))) return;
    store.update(({ project }) => ({ project: toQuestionnaire(project) }), { reason: "questionnaire_path", invalidateCheck: false });
    router.push(stepHref("questionnaire"));
  };
  const short = sets.find((s) => outOfRange(s, setLimits));
  const dock = (
    <ActionDock
      back={{ href: stepHref("brief"), label: `1. ${t("aia.stages.brief")}` }}
      ready={!short}
      note={
        short
          ? tv("research.plan.dockSetSize", { name: setTitle(short) || t("research.plan.untitledSet"), n: (short.objects || []).length, ...setWords(setLimits) })
          : comments.length
            ? tv("research.plan.dockComments", { n: comments.length })
            : a
              ? t("research.plan.dockReady")
              : null
      }
    >
      <Button variant="primary" className="!rounded-control" onClick={() => void next()}>
        {t("research.plan.next")}
        <Icon name="next" size={14} />
      </Button>
    </ActionDock>
  );

  const chooseVariant = (id: string) => {
    // A variant carries an n; until the valid range is read nothing is applied (RQC9).
    if (sampleLimits.state === "loading") return toast(t("research.plan.variantWaitLimits"));
    const snapshot = store.get();
    const analysis = proposalAnalysis(snapshot);
    const r = applyVariant({ ...snapshot, analysis }, id, readyLimits(sampleLimits));
    if (!r) return;
    store.update(() => ({ ...r.state, project: { ...r.state.project, ui_state: { ...r.state.project.ui_state, plan_manual_changed: false } } }), { reason: "project_variant_1793" });
    setPendingVariant(null);
    const applied = tv("research.plan.variantApplied", { title: r.title });
    // The variant's n outside the valid range is not stored, and the person is told (RQC9).
    toast(r.sampleRefused ? `${applied}. ${tv("research.plan.variantSampleKept", { why: r.sampleRefused })}` : applied);
  };
  const variantSection = variants.length ? <>
    <Variants variants={variants} current={selectedVariant(p)} onApply={(id) => {
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
            <Button variant="primary" onClick={() => { store.update((current) => ({ ...current, analysis: { problem_summary: current.project.goal || "", objectives: [], hypotheses: [], research_questions: [], tracked_sets: [] } }), { reason: "plan_manual_started" }); }}>{t("research.plan.createManual")}</Button>
            <Button icon="back" className="!rounded-control" onClick={() => router.push(stepHref("brief"))}>
              {t("research.plan.openBrief")}
            </Button>
            <Button variant="quiet" className="!rounded-control" onClick={() => void next()}>{t("research.plan.skipToQuestionnaire")}</Button>
          </div>
        </section>
        {dock}
      </div>
    );
  }

  const chips: { id: string; label: string; state: "done" | "you" | "neutral" }[] = [
    ...(variants.length ? [{ id: "plan-variants", label: t("research.plan.jumpScope"), state: "done" as const }] : []),
    { id: "plan-understanding", label: t("research.plan.jumpUnderstanding"), state: p.ui_state.plan_changed26 ? "done" : "neutral" },
    { id: "plan-sets", label: tv("research.plan.jumpSets", { n: sets.length }), state: short ? "you" : sets.length ? "done" : "neutral" },
    ...(questions.length
      ? [{ id: "plan-questions", label: tv("research.plan.jumpQuestions", { a: answered, b: questions.length }), state: answered ? ("done" as const) : ("you" as const) }]
      : []),
    { id: "plan-comments", label: tv("research.plan.jumpComments", { n: comments.length }), state: comments.length ? "you" : "neutral" },
  ];
  // Section numbers follow what is on the page: no variants, no "Rozsah".
  let n = variants.length ? 1 : 0;

  return (
    <div ref={root} className="flex max-w-6xl flex-col gap-4">
      <header className="rounded-card border border-signal-edge bg-signal-wash p-4 sm:p-5">
        <h2 className="text-xl font-semibold">{t("research.plan.workspaceTitle")}</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-ink-muted">{t("research.plan.workspaceHint")}</p>
        <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-signal-edge pt-3">
          {[{ label: "objectiveTotal", value: Array.isArray(a.objectives) ? a.objectives.length : 0 }, { label: "questionTotal", value: Array.isArray(a.research_questions) ? a.research_questions.length : 0 }, { label: "itemTotal", value: sets.reduce((n, s) => n + (s.objects?.length ?? 0), 0) }].map((item) => <div key={item.label}><dt className="text-xs text-ink-muted">{t(`research.plan.${item.label}`)}</dt><dd className="mt-1 text-xl font-semibold">{item.value}</dd></div>)}
        </dl>
        <p className="mt-3 text-xs leading-5 text-ink-muted">{t("research.plan.manualNote")}</p>
      </header>
      <JumpChips chips={chips} />
      {failure ? <AnalysisFailureCard failure={failure} onRetry={() => void analyse()} onContinue={(id) => {
        // A wait from "process comments" ends as that action does, with its toast (CR-2).
        const comments = modeOf(failure, id) === true;
        void resume(id).then((ok) => { if (ok && comments) toast(t("research.plan.commentsDone")); });
      }} /> : null}
      {variantSection}
      <DesignCoverage />
      <Commentable onQuote={(quote) => setDrafts((d) => [...d, { key: ++seq.current, quote, text: "" }])}>
        <div className="flex flex-col gap-4">
          <Understanding n={++n} changed={Boolean(p.ui_state.plan_changed26)} blocked={busy} onQuote={(quote) => { setDrafts((d) => [...d, { key: ++seq.current, quote, text: "" }]); jumpTo("plan-comments"); }} />
          <Sets n={++n} analysis={a} blocked={busy} limits={setLimits} />
        </div>
      </Commentable>
      {questions.length ? (
        <FollowUps
          n={++n}
          questions={questions}
          answers={answers}
          answered={answered}
          setAnswers={setAnswers}
          busy={busy}
          saveOnly={leadOwnsAiStarts}
          onSubmit={async () => {
            const r = answerFollowUps(store.get().project, followUpAnswers(questions, answers));
            if ("error" in r) return r.error;
            store.update(() => ({ project: r.project }));
            setAnswers([]);
            if (leadOwnsAiStarts) setSavedForLead("answers");
            else await analyse();
            return null;
          }}
        />
      ) : null}
      {savedForLead === "answers" ? <SavedForLead saved="Odpovědi jsou uložené" message="Aktualizuj návrh podle mých odpovědí." /> : null}
      <Comments
        n={++n}
        busy={busy}
        drafts={drafts}
        setDrafts={setDrafts}
        saveOnly={leadOwnsAiStarts}
        onProcess={async () => {
          const reviewed = commentsToReview(store.get().project);
          if (!reviewed) return;
          if (leadOwnsAiStarts) {
            // The plan is marked as changed by comments, as the analysis by comments marks it.
            store.update(() => ({ project: { ...reviewed, ui_state: { ...reviewed.ui_state, plan_changed26: true } } }), { reason: "plan_comments_applied26", invalidateCheck: false });
            setSavedForLead("comments");
            return;
          }
          store.update(() => ({ project: reviewed }), { reason: "plan_comments_applied26", invalidateCheck: false });
          if (await analyse({ force: true, byComments: true })) toast(t("research.plan.commentsDone"));
        }}
      />
      {savedForLead === "comments" ? <SavedForLead saved="Komentáře jsou uložené" message="Aktualizuj návrh podle mých komentářů." /> : null}
      {dock}
    </div>
  );
}

const DOT: Record<"done" | "you" | "neutral", { glyph: IconName; look: string }> = {
  done: { glyph: "done", look: "bg-status-done/14 text-status-done" },
  you: { glyph: "you", look: "bg-status-you-wash text-status-you-ink" },
  neutral: { glyph: "dot", look: "bg-surface-sunken text-ink-faint" },
};

function JumpChips({ chips }: { chips: { id: string; label: string; state: "done" | "you" | "neutral" }[] }) {
  return (
    <nav aria-label={t("research.plan.jumpLabel")} className="flex flex-wrap gap-1.5">
      {chips.map((c) => (
        <button
          key={c.id}
          type="button"
          onClick={() => jumpTo(c.id)}
          className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-pill border border-border bg-surface-raised py-1 pl-1.5 pr-3 text-[13px] leading-5 hover:border-border-strong hover:bg-surface-sunken ${FOCUS}`}
        >
          <span aria-hidden="true" className={`inline-flex size-4 items-center justify-center rounded-full ${DOT[c.state].look}`}>
            <Icon name={DOT[c.state].glyph} size={10} />
          </span>
          {c.label}
        </button>
      ))}
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

function Understanding({ n, changed, blocked, onQuote }: { n: number; changed: boolean; blocked: boolean; onQuote: (quote: string) => void }) {
  return (
    <StepSection
      id="plan-understanding"
      n={n}
      title={t("research.plan.understoodTitle")}
      hint={t("research.plan.understoodHint")}
      aside={changed ? (
        <span className="inline-flex items-center gap-1 whitespace-nowrap rounded-pill bg-status-done/14 px-2 py-0.5 text-xs text-status-done">
          <Icon name="done" size={12} />
          {t("research.plan.changed")}
        </span>
      ) : null}
    >
      <PlanNarrative disabled={blocked} onQuote={onQuote} />
      <details className="group mt-4 rounded-control border border-signal-edge bg-signal-tint px-3 py-2">
        <summary className="cursor-pointer text-[13px] font-medium text-signal">{t("research.plan.principleSummary")}</summary>
        <p className="mt-2 text-[13px] leading-5">
          {t("research.plan.principleIntro")} <b>{t("research.plan.principleYes")}</b> {t("research.plan.principleYesText")} <b>{t("research.plan.principleNo")}</b>{" "}
          {t("research.plan.principleNoText")}
        </p>
      </details>
    </StepSection>
  );
}

/** Porovnatelné sady: each set edited where it is drawn, one field at a time (audit A33). */
function Sets({ n, analysis, blocked, limits }: { n: number; analysis: Analysis; blocked: boolean; limits: SetLimits }) {
  const { store, toast, confirm } = useResearch();
  const sets = trackedSets(analysis);
  // Cards and chips are keyed by place (sets and their items carry no id): adding or removing a set
  // remounts every other card, and removing an item that set's chips, so a draft refused in one of
  // them is asked about first. `remounts` names the cards whose drafts the change would drop.
  const cards = useRef<HTMLDivElement>(null);
  const keepDrafts = async (go: () => void, remounts: (i: number) => boolean = () => true, remount?: "items") => {
    const held = [...(cards.current?.children ?? [])].some((card, i) => remounts(i) && holdsRefused(card, remount));
    if (held && !(await confirm(t("research.plan.setField.leave")))) return;
    go();
  };
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
      hint={tv("research.plan.setsHint", setWords(limits))}
      aside={
        <Button small icon="plus" className="!rounded-control" disabled={blocked} onClick={() => setAdding("")}>
          {t("research.plan.addSet")}
        </Button>
      }
    >
      {adding !== null ? (
        <form
          className="mb-3 flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void keepDrafts(create);
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
      {sets.length ? (
        <div ref={cards} className="grid gap-4 xl:grid-cols-2">
          {sets.map((set, si) => (
            <SetCard
              // Keyed by place, as every edit names it: a rename keeps the card and its save note, and a
              // set added or removed remounts every card, so no field's state moves to another set.
              key={`${si}/${sets.length}`}
              set={set} limits={limits} blocked={blocked}
              onSet={(edit) => {
                const a = current();
                const fresh = trackedSets(a);
                if (!fresh[si]) throw new Error(t("research.plan.narrative.gone"));
                put({ ...a, tracked_sets: fresh.map((s, i) => (i === si ? edit(s) : s)) }, "plan_measurement_edited");
              }}
              onAddObject={(value) => {
                // The chip refuses a repeat or one past the full set first (objectProblem); addObject's own
                // refusal is said here should the copy have moved meanwhile.
                const r = addObject(current(), si, value, limits.max);
                if (r && "error" in r) return toast(r.error);
                put(r?.analysis ?? null, "plan_objects");
              }}
              onRename={(value) => put(renameSet(current(), si, value), "plan_set_renamed")}
              onRemove={() => void keepDrafts(() => put(removeSet(current(), si), "plan_set_removed"), (i) => i !== si)}
              onRemoveObject={(oi) => void keepDrafts(() => put(removeObject(current(), si, oi), "plan_objects"), (i) => i === si, "items")}
            />
          ))}
        </div>
      ) : (
        <p className="rounded-control border border-signal-edge bg-signal-wash p-3 text-sm">{t("research.plan.noSets")}</p>
      )}
    </StepSection>
  );
}

/** A set's question and the ends of its scale are short; its purpose a sentence or two. */
const SET_FIELD_MAX = 500;

function SetCard({ set, limits, onAddObject, onRename, onRemove, onRemoveObject, onSet, blocked }: {
  blocked: boolean;
  limits: SetLimits;
  set: TrackedSet;
  /** The set rewritten by `edit`, from the copy as it stands now. */
  onSet: (edit: (set: TrackedSet) => TrackedSet) => void;
  onAddObject: (value: string) => void;
  onRename: (value: string) => void;
  onRemove: () => void;
  onRemoveObject: (oi: number) => void;
}) {
  const objects = set.objects || [];
  const [confirming, setConfirming] = useState(false);
  const first = objectQuestionRows(set)[0];
  const bad = outOfRange(set, limits);
  const title = setTitle(set);
  // Each field is checked at the field (I9) and written alone; the store saves it.
  const field = (name: SetField, label: string, value: string, placeholder: string, multiline = false) => (
    <InlineText
      value={value}
      label={tv("research.plan.setField.label", { field: label, set: title || t("research.plan.untitledSet") })}
      placeholder={placeholder}
      multiline={multiline}
      disabled={blocked}
      // An unchanged value is not checked: a field opened and left as it was sends nothing.
      rules={{ required: false, maxLength: SET_FIELD_MAX, validate: (v) => (v === value ? null : setFieldProblem(name, v)) }}
      className="min-w-0 text-sm"
      onCommit={(v) => onSet((s) => withSetField(s, name, v))}
    />
  );
  return (
    <article className="flex min-w-0 flex-col gap-3 rounded-card border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{comparableFamily(set)}</div>
          <InlineText
            value={title}
            label={t("research.plan.setName")}
            placeholder={t("research.plan.setName")}
            disabled={blocked}
            rules={{ maxLength: SET_FIELD_MAX }}
            className="mt-0.5 min-w-0 text-[15px] font-semibold"
            onCommit={onRename}
          />
        </div>
        <span className={`whitespace-nowrap rounded-md px-1.5 py-0.5 font-mono text-xs ${bad ? "bg-status-you-wash text-status-you-ink" : "bg-surface-sunken text-ink-muted"}`}>
          {tv("research.plan.setCount", { n: objects.length, ...setWords(limits) })}
        </span>
      </div>
      <div className="flex flex-col gap-1 rounded-control bg-signal-wash px-3 py-2">
        <span className="text-xs font-semibold text-signal">{t("research.plan.purposeLabel")}</span>
        {field("purpose", t("research.plan.purposeLabel"), set.purpose || "", SET_PURPOSE_DEFAULT, true)}
      </div>
      <div className="flex flex-col gap-1">
        <span className={LABEL}>{t("research.plan.setItems")}</span>
        <ChipInput
          disabled={blocked} label={t("research.plan.setItemAdd")}
          placeholder={t("research.plan.setItemAdd")}
          values={objects}
          refuse={(v, i) => objectProblem(set, v, i, limits)}
          rename={{ label: t("research.plan.setField.item"), onRename: (i, v) => onSet((s) => withObject(s, i, v)) }}
          onAdd={onAddObject}
          onRemove={onRemoveObject}
          backspaceRemoves
        />
        {setAboveRecommended(objects.length, limits) ? (
          <span className="text-xs text-status-you-ink">{tv("research.questionnaire.setAboveRecommended", { max: limits.recommended_max, hard: limits.max })}</span>
        ) : null}
      </div>
      <div className="flex flex-col gap-1">
        <span className={LABEL}>{t("research.plan.setQuestion")}</span>
        {field("object_question", t("research.plan.setQuestion"), set.object_question || "", QUESTION_DEFAULT, true)}
        <p className="text-xs text-ink-muted">{t("research.plan.questionHelp")}</p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.plan.scaleLow")}</span>
          {field("scale_low", t("research.plan.scaleLow"), set.scale_labels?.[0] ?? "", set.scale_labels ? "" : SCALE_DEFAULT[0])}
        </div>
        <div className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.plan.scaleHigh")}</span>
          {field("scale_high", t("research.plan.scaleHigh"), set.scale_labels?.[1] ?? "", set.scale_labels ? "" : SCALE_DEFAULT[1])}
        </div>
      </div>
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
      <div className="flex flex-wrap justify-end gap-2">
        {confirming ? (
          <InlineConfirm message={t("research.plan.removeSetConfirm")} action={t("research.plan.removeSetAction")} onConfirm={() => { setConfirming(false); onRemove(); }} onCancel={() => setConfirming(false)} />
        ) : (
          <Button small disabled={blocked} variant="quiet" className="!rounded-control hover:!bg-status-fault-wash hover:!text-status-fault" onClick={() => setConfirming(true)}>
            {t("research.plan.removeSet")}
          </Button>
        )}
      </div>
    </article>
  );
}

function FollowUps({ n, questions, answers, answered, setAnswers, busy, onSubmit, saveOnly = false }: {
  /** The workbench: the answers are saved for the Lead, with no AI call from here. */
  saveOnly?: boolean;
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
      {saveOnly ? (
        <Button className="mt-4" disabled={busy} onClick={async () => setError(await onSubmit())}>Uložit odpovědi</Button>
      ) : (
        <AiButton
          className="mt-4"
          disabled={busy}
          onClick={async () => {
            setError(await onSubmit());
          }}
        >
          {t("research.plan.followSubmit")}
        </AiButton>
      )}
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

function Comments({ n, busy, drafts, setDrafts, onProcess, saveOnly = false }: {
  /** The workbench: the comments are saved for the Lead, with no AI call from here. */
  saveOnly?: boolean;
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
      {saveOnly ? (
        <Button className={cs.length || drafts.length ? "mt-4" : ""} disabled={!cs.length || busy} onClick={() => void onProcess()}>Uložit komentáře</Button>
      ) : (
        <AiButton className={cs.length || drafts.length ? "mt-4" : ""} disabled={!cs.length || busy} onClick={() => void onProcess()}>
          {t("research.plan.commentsProcess")}
        </AiButton>
      )}
    </StepSection>
  );
}
