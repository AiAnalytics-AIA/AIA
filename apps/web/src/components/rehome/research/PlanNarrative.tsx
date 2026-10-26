"use client";

// Návrh's narrative as items (artifact-design DSN3, input-interactions 4, audit A30): the problem
// summary and every research question and objective (PlanNarrative), and the hypotheses in a section
// of their own (PlanHypotheses, DSN12), each edited where it is shown (I1), a new one added in its list
// (I5), a removal taken back for 8 s (I6) through the stage's one undo offer. Each change is one store
// update, saved by the store's autosave, so there is no separate editor, no "Použít úpravy" and
// no unsaved form to guard. What each change does is research/plan-narrative.ts.

import { useId, useMemo } from "react";

import { t, tv } from "@/i18n/t";
import { type Edited, type NarrativeList, addItem, addProblem, itemProblem, itemTargets, narrativeOf, removeItem, setItem, setSummary } from "@/research/plan-narrative";
import type { PlanState } from "@/research/plan";
import { MAX_RESEARCH_QUESTIONS } from "@/research/trace";
import { Icon } from "../icons";
import { InlineCreateRow } from "../../ui/InlineCreateRow";
import { InlineText } from "../../ui/InlineText";
import { FOCUS } from "../../ui/parts";
import type { useUndo } from "../../ui/UndoToast";
import { useResearch } from "./context";
import { type DesignCoverage, RqCoverageLine, useDesignCoverage } from "./DesignCoverage";

/** A research question or a hypothesis is a sentence, not a name: longer than a folder's. */
const ITEM_MAX = 500;
const SUMMARY_MAX = 4000;
/** A list's heading where it shares its section; the hypotheses are named by their section's title. */
const TITLE: Partial<Record<NarrativeList, string>> = {
  research_questions: "research.plan.coverage.title",
  objectives: "research.plan.objectives",
};

type Undo = ReturnType<typeof useUndo>;

/**
 * `onQuote`: a comment on an item, quoting it whole (audit A35), for a touch or keyboard reader. A
 * part of an item's words is quoted by selecting it (the product owner, Q68): the items are drawn
 * `selectable`, and the stage's Commentable picks the selection up.
 */
/** `undo`: the stage's one undo offer, shared with PlanHypotheses, so one removal is offered at a time. */
export function PlanNarrative({ disabled = false, onQuote, undo }: { disabled?: boolean; onQuote?: (quote: string) => void; undo: Undo }) {
  const { state } = useResearch();
  // Each research question's coverage on its own row (DSN2b), read on the working revision.
  const coverage = useDesignCoverage(narrativeOf(state).research_questions);
  return <Narrative disabled={disabled} onQuote={onQuote} lists={["research_questions", "objectives"]} summary coverage={coverage} undo={undo} />;
}

/** Návrh's hypotheses, a section of their own (DSN12; spec navrh D5). What verifies one has no server answer yet, so none is said. */
export function PlanHypotheses({ disabled = false, onQuote, undo }: { disabled?: boolean; onQuote?: (quote: string) => void; undo: Undo }) {
  return <Narrative disabled={disabled} onQuote={onQuote} lists={["hypotheses"]} summary={false} coverage={null} undo={undo} />;
}

function Narrative({ disabled, onQuote, lists, summary, coverage, undo }: {
  disabled: boolean;
  onQuote?: (quote: string) => void;
  lists: readonly NarrativeList[];
  /** Whether the problem summary is drawn here. */
  summary: boolean;
  /** The research questions' coverage, where they are drawn. */
  coverage: DesignCoverage | null;
  undo: Undo;
}) {
  const { store, state, toast } = useResearch();
  const n = narrativeOf(state);
  // Each item's Lead target, by its stable id (never its place); none where no id can be read.
  const targets = useMemo(() => itemTargets(state), [state]);
  const rqHeading = useId();
  // A change is checked against the copy as it stands now, then written in one update.
  const apply = (edit: (s: PlanState) => Edited): string | null => {
    const r = edit(store.get());
    if ("refused" in r) return r.refused;
    store.update(() => r.state, { reason: "plan_narrative_edited" });
    return null;
  };
  // InlineText says a thrown refusal as "Neuloženo"; the rules below catch the ones a person can fix.
  const commit = (edit: (s: PlanState) => Edited) => {
    const refused = apply(edit);
    if (refused) throw new Error(refused);
  };
  const remove = (list: NarrativeList, index: number, text: string) => {
    const refused = apply((s) => removeItem(s, list, index));
    if (refused) return toast(refused);
    undo.offer({
      message: tv("research.plan.narrative.removed", { text }),
      undo: () => {
        const back = apply((s) => addItem(s, list, text, index));
        if (back) toast(back);
      },
    });
  };

  const comment = (text: string) =>
    onQuote && text.trim() ? (
      <button
        type="button"
        aria-label={tv("research.plan.narrative.comment", { text })}
        onClick={() => onQuote(text)}
        title={t("research.plan.narrative.commentShort")}
        className={`-mt-1.5 inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center gap-1 whitespace-nowrap rounded-control px-1.5 text-xs leading-6 text-ink-faint hover:bg-surface-sunken hover:text-ink @md:mt-1 @md:min-h-7 @md:min-w-0 ${FOCUS}`}
      >
        {/* A narrow column (a phone, a narrow workbench pane) keeps the item's words their width:
            the action as its glyph, named by aria-label and title. */}
        <Icon name="comment" size={14} className="@md:hidden" />
        <span className="hidden @md:inline">{t("research.plan.narrative.commentShort")}</span>
      </button>
    ) : null;

  return (
    <div className="@container flex flex-col gap-4">
      {summary ? (
        <>
        <p className="text-[13px] text-ink-muted">{t("research.plan.narrative.hint")}</p>
        <div className="flex items-start gap-2">
        <InlineText
          value={n.problem_summary}
          label={t("research.plan.summaryLabel")}
          // An empty summary says what to write where it can be written, and offers no words to quote.
          placeholder={disabled ? undefined : t("research.plan.requiredSummary")}
          multiline
          selectable={!!n.problem_summary}
          disabled={disabled}
          rules={{ maxLength: SUMMARY_MAX }}
          className="min-w-0 flex-1 text-[15px] leading-6"
          onCommit={(v) => commit((s) => setSummary(s, v))}
        />
        {comment(n.problem_summary)}
        </div>
        </>
      ) : null}
      {lists.map((list) => {
        const cov = list === "research_questions" ? coverage : null;
        const rq = cov !== null;
        return (
        // The research questions are a region of their own, named for what it shows: each with what measures it.
        <div key={list} role={rq ? "region" : undefined} aria-labelledby={rq ? rqHeading : undefined}>
          <div className="flex flex-wrap items-baseline justify-between gap-x-3">
            {TITLE[list] ? <h3 id={rq ? rqHeading : undefined} className="text-[13px] font-semibold">{t(TITLE[list])}</h3> : null}
            {rq ? <span className="text-xs text-ink-faint">{t("research.plan.coverage.aside")}</span> : null}
          </div>
          {cov ? (
            <p role={cov.line.alert ? "alert" : undefined} className={`mt-0.5 text-[13px] ${cov.line.alert ? "text-status-fault-ink" : "text-ink-muted"}`}>{cov.line.words}</p>
          ) : null}
          {n[list].length ? (
            <ul className="mt-1 flex flex-col gap-1 text-sm leading-6">
              {n[list].map((text, i) => (
                // Keyed by place: an item's place is what every edit names (the ids are the store's).
                // The coverage line sits outside the Lead's target: the target's words are the item's own.
                <li key={`${list}-${i}`} className="flex flex-col">
                  <div data-aia={targets[list][i] ?? undefined} className="group flex items-start gap-2">
                    <span aria-hidden="true" className="mt-2.5 block size-1.5 shrink-0 rounded-full bg-signal" />
                    <InlineText
                      value={text}
                      label={tv(`research.plan.narrative.item.${list}`, { n: i + 1 })}
                      multiline
                      selectable
                      disabled={disabled}
                      rules={{ maxLength: ITEM_MAX, validate: (v) => itemProblem(narrativeOf(store.get()), list, v, i) }}
                      className="min-w-0 flex-1"
                      onCommit={(v) => commit((s) => setItem(s, list, i, v))}
                    />
                    {comment(text)}
                    <button
                      type="button"
                      disabled={disabled}
                      aria-label={tv("research.plan.narrative.remove", { text })}
                      onClick={() => remove(list, i, text)}
                      className={`mt-1 inline-flex size-7 shrink-0 items-center justify-center rounded-control text-ink-faint hover:bg-surface-sunken hover:text-ink disabled:opacity-40 ${FOCUS}`}
                    >
                      <Icon name="trash" size={14} />
                    </button>
                  </div>
                  {cov?.rows[i] && cov.revision !== null ? (
                    <div className="pl-3.5">
                      {/* Past the analysis's cap and not in the read: not read at all, never unknown. */}
                      {!cov.rows[i].checked && i >= MAX_RESEARCH_QUESTIONS ? (
                        <p data-no-quote className="mt-1 text-[13px] text-ink-muted">{tv("research.plan.coverage.beyondCap", { max: MAX_RESEARCH_QUESTIONS })}</p>
                      ) : (
                        <RqCoverageLine row={cov.rows[i]} revision={cov.revision} />
                      )}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-[13px] text-ink-muted">{t("research.plan.narrative.none")}</p>
          )}
          {cov?.elsewhere.length && cov.revision !== null ? (
            // What the server traces that the list does not show (the objectives or the goal it reads
            // when the list is empty, or a copy whose plan and analysis disagree): never hidden.
            <div className="mt-2" role="group" aria-label={t("research.plan.coverage.elsewhere")}>
              <p className="text-[13px] font-semibold">{t("research.plan.coverage.elsewhere")}</p>
              <ul className="mt-1 flex flex-col gap-1 text-sm leading-6">
                {cov.elsewhere.map((row) => (
                  <li key={row.text}>
                    <span>{row.text}</span>
                    <RqCoverageLine row={row} revision={cov.revision!} />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {disabled ? null : (
            // A repeat is refused as typed by the list's own rule and words, the ones an edit in place
            // says (itemProblem), never the row's name rules ("„…“ už existuje"); an empty row says
            // what to write. addItem checks both again when it writes.
            <InlineCreateRow
              label={t(`research.plan.narrative.add.${list}`)}
              validate={(v) => itemProblem(n, list, v, null)}
              emptyWords={t(`research.plan.narrative.addEmpty.${list}`)}
              maxLength={ITEM_MAX}
              disabled={addProblem(n, list) !== null}
              className="mt-1"
              onCreate={(text) => apply((s) => addItem(s, list, text)) ?? undefined}
            />
          )}
          {addProblem(n, list) ? <p className="mt-1 text-[13px] text-ink-muted">{addProblem(n, list)}</p> : null}
        </div>
        );
      })}
    </div>
  );
}
