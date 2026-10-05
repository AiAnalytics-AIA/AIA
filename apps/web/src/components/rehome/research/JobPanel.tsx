"use client";

// One AI step while it runs: what the unit reports and nothing it does not --
// the phase, real elapsed time, the heartbeat, the provider, the cost it can
// state (design brief §4.3). Cancel arms after five seconds, as the classic
// progress() does, and asks first. The "AI úloha" badge (Studio v3) ties it to the
// AI action that started it.

import { useEffect, useState } from "react";

import { t } from "@/i18n/t";
import { CANCEL_ARM_MS, type JobUpdate } from "@/research/jobs";
import { Button } from "../ui";
import { Icon, Sparkle } from "../icons";

export function JobPanel({ job, onCancel }: { job: JobUpdate; onCancel: (jobId: string) => void }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setArmed(true), Math.max(0, job.startedAt + CANCEL_ARM_MS - Date.now()));
    return () => clearTimeout(id);
  }, [job.startedAt]);

  const m = job.meta;
  const rows: [string, string][] = m
    ? [
        [t("research.jobElapsed"), m.elapsed + (m.usual ? ` · ${t("research.jobUsual")} ${m.usual}` : "")],
        ...(m.hardStop ? ([[t("research.jobHardStop"), m.hardStop]] as [string, string][]) : []),
        ...(m.providerStage ? ([[t("research.jobProviderStage"), m.providerStage]] as [string, string][]) : []),
        [t("research.jobHeartbeat"), m.heartbeat],
        ["AI", [m.provider, m.model].filter(Boolean).join(" · ")],
        ["", m.cost],
      ]
    : [];

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="job-title" className="fixed inset-0 z-40 flex items-center justify-center bg-surface-inverse/40 p-4">
      <div className="w-[min(34rem,100%)] rounded-md border border-border-strong bg-surface-overlay p-5 text-ink shadow-[var(--shadow-overlay)]">
        <div className="flex items-start gap-3">
          <Icon name="running" className="mt-0.5 text-status-running motion-safe:animate-spin" />
          <div className="min-w-0 flex-1">
            <span className="inline-flex items-center gap-1 rounded-pill bg-ai-wash px-2 py-px text-[11px] font-semibold leading-[18px] text-ai-ink">
              <Sparkle size={11} />
              {t("research.aiJob")}
            </span>
            <h2 id="job-title" className="mt-1 text-base font-semibold">{job.title}</h2>
            <p aria-live="polite" className="mt-1 text-sm text-ink">{job.phase}</p>
            {job.paused ? <p className="mt-2 rounded-sm border border-status-world/35 bg-status-world-wash px-2 py-1 text-xs text-status-world">{job.paused}</p> : null}
          </div>
        </div>
        {rows.length ? (
          <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t border-border pt-3 font-mono text-xs tabular-nums">
            {rows.map(([k, v], i) => (
              <div key={i} className="contents">
                <dt className="text-ink-faint">{k}</dt>
                <dd className="text-ink-muted">{v}</dd>
              </div>
            ))}
          </dl>
        ) : null}
        <div className="mt-4 flex items-center justify-end gap-3">
          {!armed ? <span className="text-xs text-ink-faint">{t("research.jobCancelArming")}</span> : null}
          <Button variant="secondary" small disabled={!armed || !job.jobId} onClick={() => job.jobId && onCancel(job.jobId)}>
            {t("research.jobCancel")}
          </Button>
        </div>
      </div>
    </div>
  );
}
