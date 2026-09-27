"use client";

// A step not yet rebuilt: said plainly, with the hand-off to the same step of
// the same project in the classic interface (#aia:open=<id>@<route>).

import { classicHref } from "@/lib/interface-handoff";
import { t } from "@/i18n/t";
import { CLASSIC_ROUTE, type StepKey } from "@/unit/research/steps";
import { ClassicLink } from "../ui";

export function StepPlaceholder({ projectId, step }: { projectId: string | null; step: StepKey }) {
  return (
    <section className="max-w-2xl rounded-md border border-border bg-surface-raised p-6">
      <h2 className="text-base font-semibold">{t("research.notRebuilt")}</h2>
      {projectId ? (
        <>
          <p className="mt-1 text-sm leading-6 text-ink-muted">{t("research.notRebuiltHelp")}</p>
          <div className="mt-4">
            <ClassicLink href={classicHref({ open: projectId, step: CLASSIC_ROUTE[step] })} variant="primary">
              {t("research.openStepInClassic")}
            </ClassicLink>
          </div>
        </>
      ) : (
        <p className="mt-1 text-sm leading-6 text-ink-muted">{t("research.unsavedForClassic")}</p>
      )}
    </section>
  );
}
