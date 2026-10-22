"use client";

// Vlastní dimenze klienta (artifact-dimensions DIM4, V2 DimensionsArt §2): the client's own
// dimensions this study materialized, each with its run's state and the child's outcome, and the
// way to the run that can use one ("Populace běhu" on Sběr dat). Read only: how a person writes a
// definition waits on client-knowledge-lifecycle K5.

import Link from "next/link";

import { t } from "@/i18n/t";
import { population } from "@/lib/api";
import { ownDimension } from "@/lib/own-dimensions";
import { aiaId } from "@/lib/workbench-artifacts";
import { useResource } from "../../aia/useResource";
import { StepSection } from "../step";
import { CodedWords } from "./CodedWords";

export function OwnDimensions({ studyId, runHref }: { studyId: string; runHref: string }) {
  const [res] = useResource(() => population.materializations(studyId), [studyId]);
  const items = res.state === "ready" ? res.data.items : [];
  return (
    <StepSection title={t("research.persona.own.title")} hint={t("research.persona.own.hint")}>
      {res.state === "loading" ? <p className="text-xs text-ink-muted">{t("research.persona.own.loading")}</p> : null}
      {res.state === "failed" ? <p role="status" className="text-xs text-status-you-ink">{t("research.persona.own.failed")}</p> : null}
      {res.state !== "loading" && res.state !== "failed" && !items.length ? <p className="text-sm text-ink-muted">{t("research.persona.own.none")}</p> : null}
      {items.length ? (
        <ul className="flex flex-col divide-y divide-border" aria-label={t("research.persona.own.title")}>
          {items.map((m) => {
            const d = ownDimension(m);
            return (
              <li key={m.run_id} data-aia={aiaId("own_dimension", m.run_id)} className="flex flex-col gap-1 py-2 text-sm">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="min-w-0 flex-1 basis-48 font-semibold">{d.name}</span>
                  <span className="rounded-pill border border-border px-2 text-xs leading-5"><CodedWords inline coded={d.status} /></span>
                </div>
                {d.reason ? <p className="text-xs text-ink-muted"><CodedWords inline coded={d.reason} /></p> : null}
                {d.outcome ? (
                  <p className={`text-xs ${d.outcome.verdict === "met" ? "text-ink" : "text-status-you-ink"}`}>
                    {d.outcome.words} · {t(`aia.intelligence.population.children.verdict.${d.outcome.verdict}`)}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {res.state === "ready" || res.state === "not-found" ? (
        <p className="mt-2 text-xs">
          <Link href={runHref} className="underline">{t("research.persona.own.useInRun")}</Link>
        </p>
      ) : null}
    </StepSection>
  );
}
