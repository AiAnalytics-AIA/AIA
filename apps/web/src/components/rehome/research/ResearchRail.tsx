"use client";

// The open study's stages, as RESEARCH_STEPS draws them: every stage can be
// opened, the current one is marked, a stage not yet rebuilt says so. It is the
// study's own navigation, drawn beside the stage -- never the global menu.

import Link from "next/link";

import { t } from "@/i18n/t";
import { RAIL_STEPS, REBUILT_STEPS, type StepKey } from "@/research/steps";
import { Icon } from "../icons";

export function ResearchRail({ stepHref, current, studyName }: { stepHref: (step: StepKey) => string; current: StepKey; studyName: string }) {
  return (
    <nav aria-label={t("aia.study.stagesLabel")} className="px-2 pt-4">
      <div className="px-2 pb-1 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{t("aia.study.stagesLabel")}</div>
      <div className="px-2 pb-3 text-sm font-semibold leading-5 text-ink">{studyName}</div>
      <ol className="flex flex-col gap-0.5">
        {RAIL_STEPS.map((s) => {
          const on = s.key === current || (current === "progress" && s.key === "run");
          const rebuilt = REBUILT_STEPS.has(s.key);
          return (
            <li key={s.key}>
              <Link
                href={stepHref(s.key)}
                aria-current={on ? "step" : undefined}
                className={`grid grid-cols-[1.25rem_1fr_auto] items-start gap-x-2 rounded-sm px-2 py-1.5 no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${on ? "bg-signal-wash" : "hover:bg-surface-raised"}`}
              >
                <span className={`pt-0.5 font-mono text-xs tabular-nums ${on ? "text-signal" : "text-ink-faint"}`}>{s.num}</span>
                <span className="min-w-0">
                  <span className={`block text-sm leading-5 ${on ? "font-semibold text-signal" : "text-ink"}`}>{s.label}</span>
                  <span className="block text-xs leading-4 text-ink-faint">{s.sub}</span>
                </span>
                {!rebuilt ? <Icon name="external" size={12} className="mt-1 opacity-40" /> : null}
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
