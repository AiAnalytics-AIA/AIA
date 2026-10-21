"use client";

// Dotazník's strip (artifact-questionnaire QST2; V2 DesignStages.tsx:103-107): the items a
// respondent answers and, per stated research question, how many items say they measure it,
// read by trace.ts's coverageOf. Coverage is unknown until an item declares a link, never a gap.
// The length (QST7) is Metodika's rule applied by research/length.ts, read from the study's
// limits; unset, unread or unpriced it says so, never a figure made up.

import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { research } from "@/lib/api";
import { type LengthRule, questionnaireLength, readRule } from "@/research/length";
import { coverageOf } from "@/research/trace";
import { useResearch } from "./context";
import { useFrame } from "./frame-hook";

type RuleRead = { state: "loading" } | { state: "read"; rule: LengthRule | null } | { state: "failed" };

/** Metodika's length rule for the study, read once per visit from its readiness limits. */
function useLengthRule(studyId: string): RuleRead {
  const [read, setRead] = useState<RuleRead>({ state: "loading" });
  useEffect(() => {
    let live = true;
    research.limits(studyId).then(
      (l) => live && setRead({ state: "read", rule: readRule(l.questionnaire_length) }),
      () => live && setRead({ state: "failed" }),
    );
    return () => {
      live = false;
    };
  }, [studyId]);
  return read;
}

/** Minutes in Czech print: a decimal comma, at most one place. */
const minutesWords = (m: number): string => String(Math.round(m * 10) / 10).replace(".", ",");

function LengthWords({ read }: { read: RuleRead }) {
  const { state } = useResearch();
  if (read.state === "loading") return null;
  if (read.state === "failed") return <span className="text-ink-muted">{t("research.questionnaire.strip.length.unread")}</span>;
  const length = questionnaireLength(state.project, read.rule);
  if (length.kind === "unset") return <span className="text-ink-muted">{t("research.questionnaire.strip.length.unset")}</span>;
  if (length.kind === "unknown") return <span className="text-ink-muted">{tv("research.questionnaire.strip.length.unknown", { n: length.unpriced })}</span>;
  const rule = tv("research.questionnaire.strip.length.rule", { version: length.rule.version, ...length.rule.seconds });
  const max = length.rule.max_seconds === null ? "" : minutesWords(length.rule.max_seconds / 60);
  const limit =
    length.limit === "unset" ? t("research.questionnaire.strip.length.noLimit") : tv(`research.questionnaire.strip.length.${length.limit}`, { max });
  return (
    <span title={rule}>
      {tv("research.questionnaire.strip.length.estimate", { minutes: minutesWords(length.minutes) })}
      {" · "}
      <span className={length.limit === "over" ? "font-medium text-status-you-ink" : "text-ink-muted"}>{limit}</span>
      <span className="sr-only"> ({rule})</span>
    </span>
  );
}

const plural = (n: number) => (n === 1 ? "one" : n >= 2 && n <= 4 ? "few" : "many");

export function QuestionnaireStrip() {
  const { state } = useResearch();
  const frame = useFrame();
  const rule = useLengthRule(frame.studyId);
  const { items, linked, questions } = coverageOf(state.project);
  if (!items && !questions.length) return null;
  return (
    <section aria-label={t("research.questionnaire.strip.label")} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-panel border border-border bg-surface-raised px-4 py-2.5 text-[13px] leading-5">
      <span className="font-medium">{tv(`research.questionnaire.strip.items.${plural(items)}`, { n: items })}</span>
      <LengthWords read={rule} />
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
