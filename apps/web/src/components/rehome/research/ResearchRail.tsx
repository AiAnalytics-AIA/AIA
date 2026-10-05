"use client";

// The open study's stages, as RESEARCH_STEPS draws them: every stage can be
// opened, the current one is marked, a stage not yet rebuilt says so. It is the
// study's own navigation, drawn beside the stage -- never the global menu.
// Studio v3 groups the seven stages into three phases, shows how far along the
// study is, and marks the stages before the current one as passed.

import Link from "next/link";

import { t, tv } from "@/i18n/t";
import { RAIL_STEPS, REBUILT_STEPS, type StepKey } from "@/research/steps";
import { Icon } from "../icons";

// The first stage of each phase, its name and its dot (wayfinding tints, never a status).
const PHASES: Partial<Record<StepKey, { key: string; dot: string }>> = {
  brief: { key: "design", dot: "bg-signal" },
  audience: { key: "sample", dot: "bg-hue-violet" },
  run: { key: "run", dot: "bg-hue-green" },
};

export function ResearchRail({ stepHref, current, studyName }: { stepHref: (step: StepKey) => string; current: StepKey; studyName: string }) {
  // Průběh is drawn on Kontrola & spuštění's entry; Ověření and Další krok are not on the rail.
  const at = RAIL_STEPS.findIndex((s) => s.key === (current === "progress" ? "run" : current));
  return (
    <nav aria-label={t("aia.study.stagesLabel")} className="px-2 pt-4">
      <div className="px-2 pb-1 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{t("aia.study.stagesLabel")}</div>
      <div className="px-2 pb-1 text-sm font-semibold leading-5 text-ink">{studyName}</div>
      {at >= 0 ? (
        <div className="px-2 pb-3">
          <div className="text-xs text-ink-muted">{tv("aia.study.stepOf", { n: at + 1, total: RAIL_STEPS.length })}</div>
          <div aria-hidden="true" className="mt-1.5 h-0.5 bg-border">
            <div className="h-0.5 bg-signal" style={{ width: `${Math.round(((at + 1) / RAIL_STEPS.length) * 100)}%` }} />
          </div>
        </div>
      ) : (
        <div className="pb-2" />
      )}
      <ol className="flex flex-col gap-0.5">
        {RAIL_STEPS.map((s, i) => {
          const on = i === at;
          const done = at >= 0 && i < at;
          const rebuilt = REBUILT_STEPS.has(s.key);
          const phase = PHASES[s.key];
          return [
            phase ? (
              <li key={`phase-${phase.key}`} role="presentation" className={`flex items-center gap-1.5 px-2 pb-1 text-[11px] font-semibold leading-4 tracking-[0.04em] text-ink-faint ${i ? "pt-3.5" : "pt-1"}`}>
                <i aria-hidden="true" className={`block size-1.5 rounded-full ${phase.dot}`} />
                {t(`aia.study.phases.${phase.key}`)}
              </li>
            ) : null,
            <li key={s.key}>
              <Link
                href={stepHref(s.key)}
                aria-current={on ? "step" : undefined}
                className={`grid grid-cols-[1.25rem_1fr_auto] items-start gap-x-2 rounded-sm px-2 py-1.5 no-underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${on ? "bg-signal-wash" : "hover:bg-surface-sunken"}`}
              >
                <span
                  className={`inline-flex size-5 items-center justify-center rounded-full border font-mono text-[11px] leading-none tabular-nums ${
                    on ? "border-signal bg-surface-raised text-signal" : done ? "border-ink bg-ink text-surface-raised" : "border-border-strong text-ink-faint"
                  }`}
                >
                  {done ? <Icon name="done" size={12} /> : s.num}
                </span>
                <span className="min-w-0">
                  <span className={`block text-sm leading-5 ${on ? "font-semibold text-signal" : "text-ink"}`}>{s.label}</span>
                  <span className="block text-xs leading-4 text-ink-faint">{s.sub}</span>
                </span>
                {!rebuilt ? <Icon name="external" size={12} className="mt-1 opacity-40" /> : null}
              </Link>
            </li>,
          ];
        })}
      </ol>
    </nav>
  );
}
