"use client";

// 2. Návrh, rebuilt (research-flow-rehome.md, chunk 3): the classic renderPlan
// with the four wrappers that run over it -- the design variants (1793), the
// wizard's way on (1789), and the comment workflow (26), which also removes the
// review note (1785) and the "Další krok: dotazník" card, so neither is here.
// What each control does is src/unit/research/plan.ts, parity-tested against
// the original; this file only draws it.

import { useRouter } from "next/navigation";
import { type ReactNode, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  CONFIRM_REMOVE_SET,
  PROMPT_COMMENT,
  PROMPT_OBJECT,
  PROMPT_RENAME,
  PROMPT_SET_OBJECTS,
  PROMPT_SET_TITLE,
  SET_PURPOSE_DEFAULT,
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
} from "@/unit/research/plan";
import type { Analysis } from "@/unit/research/store";
import { Icon } from "../icons";
import { Button, Chip, Tag, TextArea } from "../ui";
import { useResearch } from "./context";
import { AnalysisFailureCard, useAnalysis } from "./useAnalysis";

const CARD = "rounded-md border border-border bg-surface-raised p-5";
const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint";

export function PlanStep() {
  const { store, state, toast } = useResearch();
  const router = useRouter();
  const { analyse, failure, busy } = useAnalysis();
  const a = state.analysis;
  const p = state.project;
  const variants = projectVariants(state);

  const next = () => {
    store.update(({ project }) => ({ project: toQuestionnaire(project) }), { reason: "questionnaire_path", invalidateCheck: false });
    const id = store.get().projectId;
    if (id) router.push(`/app/research/${encodeURIComponent(id)}/questionnaire`);
  };
  const nextButton = (
    <div className="flex justify-end border-t border-border pt-4">
      <Button variant="primary" onClick={next}>
        {t("research.plan.next")}
        <Icon name="next" size={14} />
      </Button>
    </div>
  );

  const variantCard = variants.length ? (
    <Variants
      variants={variants}
      current={selectedVariant(p)}
      onApply={(id) => {
        const r = applyVariant(store.get(), id);
        if (!r) return;
        store.update(() => r.state, { reason: "project_variant_1793" });
        toast(tv("research.plan.variantApplied", { title: r.title }));
      }}
    />
  ) : null;

  if (!a) {
    return (
      <div className="flex max-w-5xl flex-col gap-4">
        {variantCard}
        <section className={`${CARD} py-10 text-center`}>
          <h2 className="text-lg font-semibold">{t("research.plan.emptyTitle")}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("research.plan.emptySub")}</p>
          <Button
            className="mt-4"
            icon="back"
            onClick={() => state.projectId && router.push(`/app/research/${encodeURIComponent(state.projectId)}/brief`)}
          >
            {t("research.plan.backToBrief")}
          </Button>
        </section>
        {nextButton}
      </div>
    );
  }

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      {failure ? <AnalysisFailureCard failure={failure} onRetry={() => void analyse()} /> : null}
      {variantCard}
      <Commentable>
        <div className="grid gap-4 lg:grid-cols-3">
          <Understanding analysis={a} goal={p.goal || ""} changed={Boolean(p.ui_state.plan_changed26)} />
          <section className={CARD} aria-labelledby="plan-principle">
            <h2 id="plan-principle" className="text-base font-semibold">{t("research.plan.principle")}</h2>
            <p className="mt-2 text-sm leading-6 text-ink-muted">{t("research.plan.principleIntro")}</p>
            <div className="mt-3 flex flex-col gap-3 rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm leading-6">
              <p><b>{t("research.plan.principleYes")}</b> {t("research.plan.principleYesText")}</p>
              <p><b>{t("research.plan.principleNo")}</b> {t("research.plan.principleNoText")}</p>
            </div>
          </section>
        </div>
        <Sets analysis={a} />
        <FollowUps
          questions={followUps(a)}
          busy={busy}
          onSubmit={async (answers) => {
            const r = answerFollowUps(store.get().project, answers);
            if ("error" in r) return r.error;
            store.update(() => ({ project: r.project }));
            await analyse();
            return null;
          }}
        />
      </Commentable>
      <Comments
        busy={busy}
        onProcess={async () => {
          const reviewed = commentsToReview(store.get().project);
          if (!reviewed) return;
          store.update(() => ({ project: reviewed }), { reason: "plan_comments_applied26", invalidateCheck: false });
          if (await analyse({ force: true, byComments: true })) toast(t("research.plan.commentsDone"));
        }}
      />
      {nextButton}
    </div>
  );
}

function Understanding({ analysis, goal, changed }: { analysis: Analysis; goal: string; changed: boolean }) {
  const objectives = Array.isArray(analysis.objectives) ? analysis.objectives.map(String) : [];
  const hypotheses = Array.isArray(analysis.hypotheses) ? analysis.hypotheses.map(String) : [];
  return (
    <section
      className={`${CARD} lg:col-span-2 ${changed ? "border-l-4 border-l-status-done" : ""}`}
      aria-labelledby="plan-understood"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 id="plan-understood" className="text-lg font-semibold">{t("research.plan.understood")}</h2>
        {changed ? <Chip tone="done">{t("research.plan.changed")}</Chip> : null}
      </div>
      <p className="mt-2 text-sm leading-6">{String(analysis.problem_summary || goal)}</p>
      <h3 className="mt-4 text-sm font-semibold">{t("research.plan.objectives")}</h3>
      <ul className="mt-1 list-disc pl-5 text-sm leading-6">
        {objectives.map((x, i) => <li key={i}>{x}</li>)}
      </ul>
      {hypotheses.length ? (
        <>
          <h3 className="mt-4 text-sm font-semibold">{t("research.plan.hypotheses")}</h3>
          <ul className="mt-1 list-disc pl-5 text-sm leading-6">
            {hypotheses.map((x, i) => <li key={i}>{x}</li>)}
          </ul>
        </>
      ) : null}
    </section>
  );
}

function Variants({ variants, current, onApply }: { variants: Variant[]; current: string; onApply: (id: string) => void }) {
  return (
    <section className={CARD} aria-labelledby="plan-variants">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className={EYEBROW}>{t("research.plan.variantsTag")}</div>
          <h2 id="plan-variants" className="mt-1 text-base font-semibold">{t("research.plan.variantsTitle")}</h2>
        </div>
        <Tag>{t("research.plan.variantsChip")}</Tag>
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        {variants.map((v) => {
          const on = current === v.id;
          return (
            <button
              key={String(v.id)}
              type="button"
              aria-pressed={on}
              onClick={() => onApply(String(v.id))}
              className={`flex flex-col items-start gap-2 rounded-sm border p-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${
                on ? "border-signal bg-signal-wash" : "border-border-strong bg-surface hover:bg-surface-sunken"
              }`}
            >
              {v.badge ? <span className={EYEBROW}>{v.badge}</span> : null}
              <span className="text-sm font-semibold">{v.title}</span>
              <span className="text-sm text-ink-muted">{v.summary}</span>
              <span className="flex flex-wrap gap-1">
                {v.n != null ? <Tag>N={String(v.n)}</Tag> : null}
                {v.complexity ? <Tag>{v.complexity}</Tag> : null}
                {v.deep_research ? <Chip tone="you">{t("research.plan.variantDeep")}</Chip> : null}
              </span>
              <span className="text-xs text-ink-muted">{tv("research.plan.variantTradeoff", { text: v.tradeoff || "" })}</span>
              {on ? (
                <span className="flex items-center gap-1 text-sm font-semibold text-signal">
                  <Icon name="done" size={14} />
                  {t("research.plan.variantChosen")}
                </span>
              ) : (
                <span className="text-xs text-ink-muted">{t("research.plan.variantUse")}</span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}

/** Porovnatelné sady, with the classic editors behind the classic prompts. */
function Sets({ analysis }: { analysis: Analysis }) {
  const { store, confirm, prompt, toast } = useResearch();
  const sets = trackedSets(analysis);
  const put = (next: Analysis | null, reason: string) => {
    if (next) store.update(() => ({ project: store.get().project, analysis: next }), { reason });
  };
  const add = async () => {
    const title = await prompt(PROMPT_SET_TITLE);
    if (!title?.trim()) return;
    const raw = await prompt(PROMPT_SET_OBJECTS);
    put(addSet(store.get(), title, raw), "plan_set_added");
  };
  const current = () => store.get().analysis as Analysis;
  return (
    <section className={`${CARD} mt-4`} aria-labelledby="plan-sets">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className={EYEBROW}>{t("research.plan.mapTag")}</div>
          <h2 id="plan-sets" className="mt-1 text-base font-semibold">{t("research.plan.setsTitle")}</h2>
        </div>
        <Button small icon="plus" onClick={() => void add()}>{t("research.plan.addSet")}</Button>
      </div>
      {sets.length ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          {sets.map((set, si) => (
            <SetCard
              key={si}
              set={set}
              onAddObject={async () => {
                const r = addObject(current(), si, await prompt(PROMPT_OBJECT));
                if (r && "error" in r) return toast(r.error);
                put(r?.analysis ?? null, "plan_objects");
              }}
              onRename={async () => put(renameSet(current(), si, await prompt(PROMPT_RENAME, setTitle(set))), "plan_set_renamed")}
              onRemove={async () => {
                if (await confirm(CONFIRM_REMOVE_SET)) put(removeSet(current(), si), "plan_set_removed");
              }}
              onRemoveObject={(oi) => put(removeObject(current(), si, oi), "plan_objects")}
            />
          ))}
        </div>
      ) : (
        <p className="mt-4 rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm">{t("research.plan.noSets")}</p>
      )}
    </section>
  );
}

function SetCard({ set, onAddObject, onRename, onRemove, onRemoveObject }: {
  set: TrackedSet;
  onAddObject: () => void;
  onRename: () => void;
  onRemove: () => void;
  onRemoveObject: (oi: number) => void;
}) {
  const objects = set.objects || [];
  const rows = objectQuestionRows(set);
  return (
    <article className="flex flex-col gap-3 rounded-sm border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className={EYEBROW}>{comparableFamily(set)}</div>
          <h3 className="mt-0.5 text-sm font-semibold">{set.title || set.object_type || t("research.plan.untitledSet")}</h3>
        </div>
        <Tag>{tv("research.plan.items", { n: objects.length })}</Tag>
      </div>
      <p className="rounded-sm bg-signal-wash px-3 py-2 text-xs text-signal">
        <b>{t("research.plan.compare")}</b> {set.purpose || SET_PURPOSE_DEFAULT}
      </p>
      <ul className="flex flex-wrap gap-1.5">
        {objects.length ? (
          objects.map((x, oi) => (
            <li key={`${oi}-${x}`} className="inline-flex items-center gap-1 rounded-sm border border-border-strong bg-surface-raised py-0.5 pl-2 pr-0.5 text-xs">
              {x}
              <button
                type="button"
                aria-label={tv("research.plan.removeObject", { name: x })}
                onClick={() => onRemoveObject(oi)}
                className="rounded-sm px-1 text-ink-muted hover:bg-surface-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring"
              >
                ×
              </button>
            </li>
          ))
        ) : (
          <li className="text-xs text-ink-muted">{t("research.plan.noObjects")}</li>
        )}
      </ul>
      {rows.length ? (
        <div>
          <div className={EYEBROW}>{t("research.plan.previewTag")}</div>
          <ol className="mt-1.5 flex flex-col gap-1.5">
            {rows.map((r, i) => (
              <li key={i} className="rounded-sm border border-border bg-surface-sunken px-3 py-2">
                <div className="flex items-start justify-between gap-2 text-sm font-semibold">
                  <span>{r.question}</span>
                  <Tag>{t("research.plan.scale")}</Tag>
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-ink-muted">
                  <span>{r.low}</span>
                  <span aria-hidden="true">←</span>
                  <span className="font-mono tracking-wide">1 2 3 4 5 6 7 8 9 10</span>
                  <span aria-hidden="true">→</span>
                  <span>{r.high}</span>
                </div>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-1">
        <Button small variant="quiet" icon="plus" onClick={onAddObject}>{t("research.plan.addObject")}</Button>
        <Button small variant="quiet" onClick={onRename}>{t("research.plan.rename")}</Button>
        <Button small variant="quiet" onClick={onRemove}>{t("research.plan.removeSet")}</Button>
      </div>
    </article>
  );
}

function FollowUps({ questions, busy, onSubmit }: { questions: string[]; busy: boolean; onSubmit: (answers: string) => Promise<string | null> }) {
  const [answers, setAnswers] = useState("");
  const [error, setError] = useState<string | null>(null);
  if (!questions.length) return null;
  return (
    <section className={`${CARD} mt-4`} aria-labelledby="plan-follow">
      <h2 id="plan-follow" className="text-base font-semibold">{t("research.plan.followTitle")}</h2>
      <ol className="mt-2 list-decimal pl-5 text-sm leading-6">
        {questions.map((q, i) => <li key={i}>{q}</li>)}
      </ol>
      <TextArea
        className="mt-3 w-full"
        aria-label={t("research.plan.followTitle")}
        placeholder={t("research.plan.followPlaceholder")}
        value={answers}
        onChange={(e) => setAnswers(e.target.value)}
      />
      {error ? <p role="alert" className="mt-2 text-sm text-status-fault">{error}</p> : null}
      <Button
        className="mt-3"
        disabled={busy}
        onClick={async () => {
          const e = await onSubmit(answers);
          setError(e);
          if (!e) setAnswers("");
        }}
      >
        {t("research.plan.followSubmit")}
      </Button>
    </section>
  );
}

/**
 * The comment workflow's selection: select text in the plan, as in a word
 * processor, and a button offers to comment on it (floatButton26). Keyboard
 * selection counts as well as the mouse.
 */
function Commentable({ children }: { children: ReactNode }) {
  const { store, prompt } = useResearch();
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

  const comment = async () => {
    if (!sel) return;
    const quote = sel.text;
    setSel(null);
    const next = addComment(store.get().project, quote, await prompt(PROMPT_COMMENT, ""));
    if (next) store.update(() => ({ project: next }), { reason: "plan_comments26", invalidateCheck: false });
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
          onClick={() => void comment()}
          className="fixed z-40 inline-flex items-center gap-1.5 rounded-sm border border-signal bg-signal px-3 py-1.5 text-xs font-semibold text-on-signal shadow-[var(--shadow-overlay)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          <Icon name="plus" size={12} />
          {t("research.plan.commentAdd")}
        </button>
      ) : null}
    </div>
  );
}

function Comments({ busy, onProcess }: { busy: boolean; onProcess: () => Promise<void> }) {
  const { store, state } = useResearch();
  const cs = planComments(state.project);
  return (
    <section className={CARD} aria-labelledby="plan-comments">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className={EYEBROW}>{t("research.plan.commentsTag")}</div>
          <h2 id="plan-comments" className="mt-1 text-base font-semibold">{t("research.plan.commentsTitle")}</h2>
        </div>
        <Tag>{cs.length}</Tag>
      </div>
      <p className="mt-1 text-sm text-ink-muted">{t("research.plan.commentsHelp")}</p>
      {cs.length ? (
        <ul className="mt-3 flex flex-col divide-y divide-border rounded-sm border border-border">
          {cs.map((c, i) => (
            <li key={i} className="flex items-start gap-3 px-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="text-xs text-ink-muted">„{c.quote}“</div>
                <div className="text-sm">{c.comment}</div>
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
        </ul>
      ) : null}
      <Button className="mt-3" disabled={!cs.length || busy} onClick={() => void onProcess()}>
        {t("research.plan.commentsProcess")}
      </Button>
    </section>
  );
}
