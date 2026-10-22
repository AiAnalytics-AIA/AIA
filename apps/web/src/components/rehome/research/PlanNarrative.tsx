"use client";

// Návrh's narrative as items (artifact-design DSN3, input-interactions 4, audit A30): the problem
// summary and every research question, objective and hypothesis edited where it is shown (I1),
// a new one added in its list (I5), a removal taken back for 8 s (I6). Each change is one store
// update, saved by the store's autosave, so there is no separate editor, no "Použít úpravy" and
// no unsaved form to guard. What each change does is research/plan-narrative.ts.

import { useMemo } from "react";

import { t, tv } from "@/i18n/t";
import { type Edited, type NarrativeList, NARRATIVE_LISTS, addItem, addProblem, itemProblem, itemTargets, narrativeOf, removeItem, setItem, setSummary } from "@/research/plan-narrative";
import type { PlanState } from "@/research/plan";
import { Icon } from "../icons";
import { InlineCreateRow } from "../../ui/InlineCreateRow";
import { InlineText } from "../../ui/InlineText";
import { FOCUS } from "../../ui/parts";
import { UndoToast, useUndo } from "../../ui/UndoToast";
import { useResearch } from "./context";

/** A research question or a hypothesis is a sentence, not a name: longer than a folder's. */
const ITEM_MAX = 500;
const SUMMARY_MAX = 4000;
const TITLE: Record<NarrativeList, string> = {
  research_questions: "research.plan.questionsLabel",
  objectives: "research.plan.objectives",
  hypotheses: "research.plan.hypotheses",
};

/**
 * `onQuote`: a comment on an item, quoting it whole (audit A35), for a touch or keyboard reader. A
 * part of an item's words is quoted by selecting it (the product owner, Q68): the items are drawn
 * `selectable`, and the stage's Commentable picks the selection up.
 */
export function PlanNarrative({ disabled = false, onQuote }: { disabled?: boolean; onQuote?: (quote: string) => void }) {
  const { store, state, toast } = useResearch();
  const undo = useUndo();
  const n = narrativeOf(state);
  // Each item's Lead target, by its stable id (never its place); none where no id can be read.
  const targets = useMemo(() => itemTargets(state), [state]);
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
        className={`mt-1 shrink-0 whitespace-nowrap rounded-control px-1.5 text-xs leading-6 text-ink-faint hover:bg-surface-sunken hover:text-ink ${FOCUS}`}
      >
        {t("research.plan.narrative.commentShort")}
      </button>
    ) : null;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] text-ink-muted">{t("research.plan.narrative.hint")}</p>
      <div className="flex items-start gap-2">
      <InlineText
        value={n.problem_summary}
        label={t("research.plan.summaryLabel")}
        multiline
        selectable
        disabled={disabled}
        rules={{ maxLength: SUMMARY_MAX }}
        className="min-w-0 flex-1 text-[15px] leading-6"
        onCommit={(v) => commit((s) => setSummary(s, v))}
      />
      {comment(n.problem_summary)}
      </div>
      {NARRATIVE_LISTS.map((list) => (
        <div key={list}>
          <h3 className="text-[13px] font-semibold">{t(TITLE[list])}</h3>
          {n[list].length ? (
            <ul className="mt-1 flex flex-col gap-1 text-sm leading-6">
              {n[list].map((text, i) => (
                // Keyed by place: an item's place is what every edit names (the ids are the store's).
                <li key={`${list}-${i}`} data-aia={targets[list][i] ?? undefined} className="group flex items-start gap-2">
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
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-[13px] text-ink-muted">{t("research.plan.narrative.none")}</p>
          )}
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
      ))}
      <UndoToast offer={undo.current} onDone={undo.clear} />
    </div>
  );
}
