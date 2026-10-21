"use client";

// Dotazník's strip (artifact-questionnaire QST2; V2 DesignStages.tsx:103-107): the items a
// respondent answers and, per stated research question, how many items say they measure it,
// read by trace.ts's coverageOf. Coverage is unknown until an item declares a link, never a gap.
// The length stays unestimated until the owner's rule (QQ1, QST7): never a figure made up.

import { t, tv } from "@/i18n/t";
import { coverageOf } from "@/research/trace";
import { useResearch } from "./context";

const plural = (n: number) => (n === 1 ? "one" : n >= 2 && n <= 4 ? "few" : "many");

export function QuestionnaireStrip() {
  const { state } = useResearch();
  const { items, linked, questions } = coverageOf(state.project);
  if (!items && !questions.length) return null;
  return (
    <section aria-label={t("research.questionnaire.strip.label")} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-panel border border-border bg-surface-raised px-4 py-2.5 text-[13px] leading-5">
      <span className="font-medium">{tv(`research.questionnaire.strip.items.${plural(items)}`, { n: items })}</span>
      <span className="text-ink-muted">{t("research.questionnaire.strip.noLength")}</span>
      {questions.length ? (
        linked ? (
          <ul aria-label={t("research.questionnaire.strip.coverage")} className="flex flex-wrap gap-1.5">
            {questions.map((q, i) => {
              const words = q.measures
                ? tv("research.questionnaire.strip.measured", { n: i + 1, rq: q.researchQuestion, count: q.measures })
                : tv("research.questionnaire.strip.gap", { n: i + 1, rq: q.researchQuestion });
              return (
                <li key={q.researchQuestion} title={words}
                  className={`rounded-full border px-2 py-0.5 font-mono text-[11px] ${q.measures ? "border-border-strong" : "border-status-you-ink bg-status-you-wash"}`}>
                  <span aria-hidden="true">{tv("research.questionnaire.strip.rq", { n: i + 1 })} {q.measures}</span>
                  <span className="sr-only">{words}</span>
                </li>
              );
            })}
          </ul>
        ) : (
          <span className="text-ink-muted">{t("research.questionnaire.strip.unlinked")}</span>
        )
      ) : null}
    </section>
  );
}
