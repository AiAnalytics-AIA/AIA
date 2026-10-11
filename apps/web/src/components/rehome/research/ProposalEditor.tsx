"use client";

import { useState } from "react";
import { t } from "@/i18n/t";
import { applyNarrative, lines } from "@/research/plan-edit";
import type { Analysis } from "@/research/store";
import { Button, Field, TextArea } from "../ui";
import { useResearch } from "./context";

export function ProposalEditor({ analysis, onClose }: { analysis: Analysis; onClose: () => void }) {
  const { store, toast } = useResearch();
  const [summary, setSummary] = useState(String(analysis.problem_summary || store.get().project.goal || ""));
  const initial = (key: string) => Array.isArray(analysis[key]) ? analysis[key].map(String).join("\n") : "";
  const [questions, setQuestions] = useState(initial("research_questions"));
  const [objectives, setObjectives] = useState(initial("objectives"));
  const [hypotheses, setHypotheses] = useState(initial("hypotheses"));
  const [error, setError] = useState<string | null>(null);
  return <form aria-label={t("research.plan.edit")} className="flex flex-col gap-4" onSubmit={(e) => {
    e.preventDefault();
    if (!summary.trim() || !lines(objectives).length) {
      setError(t(`research.plan.${!summary.trim() ? "requiredSummary" : "requiredObjectives"}`)); return;
    }
    store.update((state) => applyNarrative(state, { problem_summary: summary.trim(), research_questions: lines(questions), objectives: lines(objectives), hypotheses: lines(hypotheses) }), { reason: "plan_narrative_edited" });
    toast(t("research.plan.editsApplied")); onClose();
  }}>
    <Field label={t("research.plan.summaryLabel")}><TextArea aria-label={t("research.plan.summaryLabel")} value={summary} rows={4} onChange={(e) => setSummary(e.target.value)} autoFocus /></Field>
    <p className="text-xs text-ink-muted">{t("research.plan.onePerLine")}</p>
    <Field label={t("research.plan.questionsLabel")}><TextArea aria-label={t("research.plan.questionsLabel")} value={questions} rows={3} onChange={(e) => setQuestions(e.target.value)} /></Field>
    <div className="grid gap-4 lg:grid-cols-2">
      <Field label={t("research.plan.objectives")}><TextArea aria-label={t("research.plan.objectives")} value={objectives} rows={4} onChange={(e) => setObjectives(e.target.value)} /></Field>
      <Field label={t("research.plan.hypotheses")}><TextArea aria-label={t("research.plan.hypotheses")} value={hypotheses} rows={4} onChange={(e) => setHypotheses(e.target.value)} /></Field>
    </div>
    {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}
    <div className="flex flex-wrap gap-2"><Button type="submit" variant="primary">{t("research.plan.saveEdits")}</Button><Button onClick={onClose}>{t("research.plan.cancelEdits")}</Button></div>
  </form>;
}
