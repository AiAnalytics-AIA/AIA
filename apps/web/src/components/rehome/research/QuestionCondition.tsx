"use client";

// A question's display condition, edited at the question on Dotazník (working-copy-edit-ops WCE13 (c)):
// an earlier selection question and the answers after which the question is asked. It is written
// through the shared vocabulary's route_set (lib/lead.ts applyEdit), held to the compiler's own rule
// (research_design.py condition_refusal); a stored condition the rule refuses, or one 18.6.6 wrote
// that AIA cannot read, is shown as stored with why, never rewritten here.

import { useEffect, useState } from "react";

import { ChoiceChips } from "@/components/ui/ChoiceChips";
import { t, tv } from "@/i18n/t";
import { loadConfig } from "@/lib/auth";
import { EDIT_REFUSAL_WORDS, applyEdit } from "@/lib/lead";
import type { ResearchProject } from "@/research/model";
import { type ConditionSource, type ConditionValue, type Question, conditionOf, removeCondition } from "@/research/questionnaire";
import { Button } from "../ui";
import { useResearch } from "./context";
import { useFrame } from "./frame-hook";

type Update = (next: (p: ResearchProject) => ResearchProject, reason?: string) => void;

const quoted = (xs: readonly string[]) => xs.map((x) => `„${x}“`).join(", ");
const label = (s: ConditionSource) => (s.number === null ? s.id : `Q${s.number}`);

/** /config's routing switch once read, so a card mounted later starts from it (null until then). */
let routingKnown: boolean | null = null;

/** /config's routing switch (AIA_ROUTING_ENABLED); off until read, and off when it cannot be. */
function useRouting(): boolean {
  const [on, setOn] = useState(routingKnown ?? false);
  useEffect(() => {
    let live = true;
    loadConfig().then(
      (c) => {
        routingKnown = c.routing === true;
        if (live) setOn(routingKnown);
      },
      () => undefined,
    );
    return () => {
      live = false;
    };
  }, []);
  return on;
}

export function QuestionCondition({ q, si, qi, update }: { q: Question; si: number; qi: number; update: Update }) {
  const { state: research } = useResearch();
  const { canEdit } = useFrame();
  const routing = useRouting();
  const [editing, setEditing] = useState(false);
  const { state, sources } = conditionOf(research.project, si, qi);
  const id = String(q.id ?? "").trim();

  // Held to the rule before it is written; a refusal is said in the form, which stays open.
  const save = (condition: ConditionValue): string | null => {
    const edit = { op: "route_set", question_id: id, condition, why: "" } as const;
    const r = applyEdit({ project: research.project, analysis: null }, edit);
    if ("refused" in r) return EDIT_REFUSAL_WORDS[r.reason] ?? r.refused;
    update((p) => {
      const now = applyEdit({ project: p, analysis: null }, edit);
      return "content" in now ? now.content.project : p;
    }, "questionnaire_condition");
    setEditing(false);
    return null;
  };

  if (editing) return <ConditionForm sources={sources} initial={state.kind === "set" ? state : null} onCancel={() => setEditing(false)} onSave={save} />;
  // Set or edited only behind the switch (off until fieldwork routes, RQC11); a stored one is
  // still shown and can be removed.
  const editable = canEdit && routing && sources.length > 0;
  if (state.kind === "none") {
    // Only where a condition can stand: an earlier selection question with answers.
    if (!editable) return null;
    return (
      <Button small variant="quiet" icon="plus" className="mt-2" onClick={() => setEditing(true)}>
        {t("research.questionnaire.conditionEdit.add")}
      </Button>
    );
  }
  return (
    <div data-question-condition className="mt-2 flex flex-wrap items-center gap-2 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-2 text-xs">
      {/* Wraps above its buttons on a phone rather than shrinking to a word a line. */}
      <span className="min-w-[min(100%,16rem)] flex-1">
        {state.kind === "set" ? (
          <>
            {tv("research.questionnaire.conditionEdit.shown", { n: label(state.source), text: state.source.text, answers: quoted(state.options) })}{" "}
            {t("research.questionnaire.conditionEdit.notRouted")}
          </>
        ) : state.kind === "refused" ? (
          tv("research.questionnaire.conditionEdit.refused", { reason: EDIT_REFUSAL_WORDS[state.reason] ?? state.reason })
        ) : (
          tv("research.questionnaire.condition", { condition: state.stored })
        )}
      </span>
      {editable ? <Button small onClick={() => setEditing(true)}>{t(state.kind === "set" ? "research.questionnaire.conditionEdit.edit" : "research.questionnaire.conditionEdit.again")}</Button> : null}
      <Button small onClick={() => update((p) => removeCondition(p, si, qi))} disabled={!canEdit}>{t("research.questionnaire.removeCondition")}</Button>
    </div>
  );
}

function ConditionForm({
  sources,
  initial,
  onCancel,
  onSave,
}: {
  sources: readonly ConditionSource[];
  initial: { source: ConditionSource; options: string[] } | null;
  onCancel: () => void;
  /** Why the condition was refused, in words, or null once it is written. */
  onSave: (c: ConditionValue) => string | null;
}) {
  const start = sources.find((s) => s.id === initial?.source.id) ?? null;
  const [sourceId, setSourceId] = useState<string | null>(start?.id ?? null);
  const [answers, setAnswers] = useState<string[]>(start && initial ? start.options.filter((o) => initial.options.includes(o)) : []);
  const [problem, setProblem] = useState<string | null>(null);
  const source = sources.find((s) => s.id === sourceId) ?? null;
  return (
    <div
      data-condition-form
      onKeyDown={(e) => {
        if (e.key !== "Escape") return;
        e.preventDefault();
        onCancel();
      }}
      className="mt-2 flex flex-col gap-2 rounded-sm border border-border-strong bg-surface p-3 text-xs"
    >
      <div className="font-semibold">{t("research.questionnaire.conditionEdit.source")}</div>
      <ChoiceChips
        label={t("research.questionnaire.conditionEdit.source")}
        value={sourceId}
        options={sources.map((s) => ({ key: s.id, label: <span title={s.text}>{label(s)}{s.text ? ` · ${s.text.length > 48 ? `${s.text.slice(0, 47)}…` : s.text}` : ""}</span> }))}
        onChange={(key) => {
          setSourceId(key);
          setAnswers([]);
          setProblem(null);
        }}
      />
      {source ? (
        <>
          <div className="font-semibold">{t("research.questionnaire.conditionEdit.answers")}</div>
          <ChoiceChips multiple label={t("research.questionnaire.conditionEdit.answers")} value={answers} options={source.options.map((o) => ({ key: o, label: o }))} onChange={setAnswers} />
        </>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button small variant="primary" disabled={!source || !answers.length} onClick={() => source && setProblem(onSave({ question_id: source.id, options: answers }))}>
          {t("research.questionnaire.conditionEdit.save")}
        </Button>
        <Button small variant="quiet" onClick={onCancel}>{t("research.questionnaire.conditionEdit.cancel")}</Button>
        {source && !answers.length ? <span className="text-ink-muted">{t("research.questionnaire.conditionEdit.noAnswer")}</span> : null}
      </div>
      {problem ? <p role="alert" className="text-status-you-ink">{problem}</p> : null}
    </div>
  );
}
