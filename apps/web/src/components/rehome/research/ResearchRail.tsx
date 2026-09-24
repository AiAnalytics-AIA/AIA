"use client";

// The current project's steps in the rail, as RESEARCH_STEPS draws them: every
// step can be opened, the current one is marked. A step not yet rebuilt says so.

import Link from "next/link";

import { t } from "@/i18n/t";
import { RAIL_STEPS, REBUILT_STEPS, type StepKey } from "@/unit/research/steps";
import { Icon } from "../icons";

export function ResearchRail({ projectId, current }: { projectId: string | null; current: StepKey }) {
  const base = projectId ? `/app/research/${encodeURIComponent(projectId)}` : "/app/research/new";
  return (
    <div className="px-2 pt-3">
      <div className="px-2 pb-1 font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{t("research.railTag")}</div>
      <div className="px-2 pb-2 font-mono text-[11px] uppercase tracking-[0.08em] text-signal">{t("research.railMode")}</div>
      <ol className="flex flex-col gap-0.5">
        {RAIL_STEPS.map((s) => {
          const on = s.key === current || (current === "progress" && s.key === "run");
          const rebuilt = REBUILT_STEPS.has(s.key);
          return (
            <li key={s.key}>
              <Link
                href={projectId || s.key === "brief" ? `${base}/${s.key}` : base}
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
    </div>
  );
}
