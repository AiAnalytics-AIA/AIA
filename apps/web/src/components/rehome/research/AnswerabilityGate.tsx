"use client";

/**
 * Runnable is not answerable (research-integrity-report 1). Shown when a run cannot show an
 * answer to every research question its design states: which ones, whether the run will not or
 * may not answer each and why, and a link to fix it in Dotazník. Where the deployment requires it
 * (`acknowledgement_required`), the person's explicit acknowledgement with a reason, given for
 * exactly these gaps, which the run records and the report prints; elsewhere the gaps alone.
 */
import Link from "next/link";
import { t, tv } from "@/i18n/t";
import type { Answerability } from "@/lib/api";
import { type AcknowledgementState, confirmedFor, gapWords, MAX_REASON, needsAcknowledgement } from "@/lib/answerability";
import { Field, TextArea } from "../ui";

export type { AcknowledgementState } from "@/lib/answerability";

export function AnswerabilityGate({
  answer,
  value,
  onChange,
  fixHref,
  disabled,
}: {
  answer: Answerability;
  value: AcknowledgementState;
  onChange: (next: AcknowledgementState) => void;
  fixHref: string;
  disabled?: boolean;
}) {
  const asks = needsAcknowledgement(answer);
  // Given for other gaps (the design changed since): shown unchecked, asked again.
  const confirmed = confirmedFor(answer, value);
  const pending = answer.pending ?? [];
  return (
    <section aria-labelledby="answerability-title" className="flex flex-col gap-3 rounded-card border border-status-you-ink/40 bg-status-you-wash p-3.5">
      <h2 id="answerability-title" className="text-sm font-semibold">{t("research.exec.answerability.title")}</h2>
      <p className="text-sm">{t("research.exec.answerability.help")}</p>
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
        {answer.gaps.map((gap, i) => {
          const { question, verdict, why } = gapWords(gap);
          return (
            <li key={`${gap.research_question ?? "none"}-${i}`}>
              {question ? <strong className="font-semibold">{question}</strong> : null}
              {question ? ` — ${verdict}: ` : null}
              {why}
            </li>
          );
        })}
      </ul>
      {pending.length ? <p className="text-sm text-ink-muted">{tv("research.exec.answerability.pending", { list: pending.join("; ") })}</p> : null}
      <Link href={fixHref} className="text-sm text-signal no-underline hover:underline">{t("research.exec.answerability.fix")}</Link>
      {asks ? (
        <>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={confirmed}
              disabled={disabled}
              onChange={(e) => onChange({ ...value, digest: answer.digest, confirmed: e.target.checked })}
            />
            <span>{t("research.exec.answerability.confirm")}</span>
          </label>
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
