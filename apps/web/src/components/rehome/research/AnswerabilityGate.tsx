"use client";

/**
 * Runnable is not answerable (research-integrity-report 1). Shown when a run cannot show an
 * answer to every research question its design states: which ones, whether the run will not or
 * may not answer each and why, and under each the links to where it is fixed (gapFixes: Návrh,
 * a place in Dotazník, Dimenze), with Dotazník itself below them all. Where the deployment
 * requires it (`acknowledgement_required`), the person's explicit choice to continue with
 * limitations ("Pokračovat s omezeními", the owner's D1) with a reason, made for exactly these
 * gaps, which the run records as its acknowledgement and the internal report prints; elsewhere
 * the gaps alone.
 */
import Link from "next/link";
import { useId } from "react";
import { t, tv } from "@/i18n/t";
import type { Answerability, QuestionOutlook } from "@/lib/api";
import { type AcknowledgementState, confirmedFor, fixHref, gapFixes, gapWords, MAX_REASON, needsAcknowledgement } from "@/lib/answerability";
import type { StepKey } from "@/research/steps";
import { Field, TextArea } from "../ui";

export type { AcknowledgementState } from "@/lib/answerability";

export function AnswerabilityGate({
  answer,
  value,
  onChange,
  outlook,
  stepHref,
  disabled,
  runnable = true,
}: {
  answer: Answerability;
  value: AcknowledgementState;
  onChange: (next: AcknowledgementState) => void;
  /** Readiness's question outlook, which says where a measure is; null where there is none (a refused retry). */
  outlook: readonly QuestionOutlook[] | null;
  stepHref: (step: StepKey) => string;
  disabled?: boolean;
  /** Whether readiness lets the design run: the card calls it runnable only then. */
  runnable?: boolean;
}) {
  const asks = needsAcknowledgement(answer);
  const helpId = useId();
  // Given for other gaps (the design changed since): shown unchecked, asked again.
  const confirmed = confirmedFor(answer, value);
  const pending = answer.pending ?? [];
  return (
    <section aria-labelledby="answerability-title" className="flex flex-col gap-3 rounded-card border border-status-you-ink/40 bg-status-you-wash p-3.5">
      <h2 id="answerability-title" className="text-sm font-semibold">{t(runnable ? "research.exec.answerability.title" : "research.exec.answerability.titleNotReady")}</h2>
      <p className="text-sm">{t("research.exec.answerability.help")}</p>
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
        {answer.gaps.map((gap, i) => {
          const { question, verdict, why } = gapWords(gap);
          return (
            <li key={`${gap.research_question ?? "none"}-${i}`}>
              {question ? <strong className="font-semibold">{question}</strong> : null}
              {question ? ` — ${verdict}: ` : null}
              {why}
              <span className="mt-0.5 flex flex-wrap gap-x-3">
                {gapFixes(gap, outlook).map((fix) => (
                  <Link key={`${fix.step}#${fix.anchor ?? ""}`} href={fixHref(fix, stepHref)} className="text-[13px] text-signal no-underline hover:underline">
                    {fix.words}
                  </Link>
                ))}
              </span>
            </li>
          );
        })}
      </ul>
      {pending.length ? <p className="text-sm text-ink-muted">{tv("research.exec.answerability.pending", { list: pending.join("; ") })}</p> : null}
      <Link href={stepHref("questionnaire")} className="text-sm text-signal no-underline hover:underline">{t("research.exec.answerability.fix")}</Link>
      {asks ? (
        <>
          <div className="flex flex-col gap-1">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                checked={confirmed}
                disabled={disabled}
                aria-describedby={helpId}
                onChange={(e) => onChange({ ...value, digest: answer.digest, confirmed: e.target.checked })}
              />
              <span className="font-semibold">{t("research.exec.answerability.choice")}</span>
            </label>
            <p id={helpId} className="pl-6 text-[13px] text-ink-muted">{t("research.exec.answerability.choiceHelp")}</p>
          </div>
          <Field label={t("research.exec.answerability.why")}>
            <TextArea
              value={value.reason}
              maxLength={MAX_REASON}
              disabled={disabled || !confirmed}
              placeholder={t("research.exec.answerability.whyHint")}
              onChange={(e) => onChange({ ...value, reason: e.target.value })}
            />
          </Field>
        </>
      ) : (
        <p className="text-sm">{t("research.exec.answerability.notRequired")}</p>
      )}
    </section>
  );
}
