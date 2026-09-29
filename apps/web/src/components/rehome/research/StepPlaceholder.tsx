"use client";

// A research step AIA has not rebuilt (verify, next; OI-47). It says so where the
// person is (ADR 0018): there is no 18.6.6 interface to hand off to any more, and a
// capability hidden behind a link is not a capability AIA has.

import { t } from "@/i18n/t";
import type { StepKey } from "@/research/steps";

export function StepPlaceholder({ step }: { step: StepKey }) {
  return (
    <section className="max-w-2xl rounded-md border border-border bg-surface-raised p-6" data-step={step}>
      <h2 className="text-base font-semibold">{t("research.notInAia")}</h2>
      <p className="mt-1 text-sm leading-6 text-ink-muted">{t("research.notInAiaHelp")}</p>
    </section>
  );
}
