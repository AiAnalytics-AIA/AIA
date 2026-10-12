"use client";

// A running step's own space (.planning/plans/step-activity.md): it opens beneath the step while
// the API reports it RUNNING and closes when it stops. It holds the large orb, the latest thing
// the step reported, the real counts it reported, how long it has run, and its last few feed
// lines. Everything in it comes from the step's events (lib/step-activity.ts) and the step's own
// record; nothing is estimated. The panel opens over --duration-panel, only where motion is
// welcome; the feed is a polite live log, the orb is decoration.

import { useEffect, useState } from "react";

import { ActivityOrb } from "@/components/brand/ActivityOrb";
import { t, tv } from "@/i18n/t";
import type { Orb } from "@/lib/activity-orb";
import { fmtTime } from "@/research/jobs";
import { formatUsd, type StepActivity } from "@/lib/step-activity";

/** The panel's close transition, as tokens.css --duration-panel. */
const PANEL_MS = 180;

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

const clock = (at: string | null) => {
  const d = at ? new Date(at) : null;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
};

export function StepActivityPanel({
  orb,
  activity,
  startedAt,
  attempt,
  label,
}: {
  /** The step's orb while it runs; null closes the panel. */
  orb: Orb | null;
  activity: StepActivity | null;
  startedAt?: string | null;
  attempt?: { n: number; max: number } | null;
  /** What the log is about, for assistive technology ("Sběr dat"). */
  label: string;
}) {
  const open = orb !== null;
  // Kept on screen while it closes, so the height can ease to nothing; opened at once.
  const [present, setPresent] = useState(open);
  // Closed for one frame before it opens, so the opening is a transition, not a jump.
  const [expanded, setExpanded] = useState(false);
  if (open && !present) setPresent(true);
  if (!open && expanded) setExpanded(false);
  useEffect(() => {
    if (open) {
      const id = requestAnimationFrame(() => setExpanded(true));
      return () => cancelAnimationFrame(id);
    }
    const id = setTimeout(() => setPresent(false), PANEL_MS);
    return () => clearTimeout(id);
  }, [open]);
  const now = useNow(open);
  if (!present) return null;

  const started = startedAt ? Date.parse(startedAt) : NaN;
  const latest = activity?.lines.at(-1) ?? null;
  const facts = [
    Number.isFinite(started) ? tv("research.exec.activity.elapsed", { time: fmtTime((now - started) / 1000) }) : null,
    attempt && attempt.n > 0 ? tv("research.exec.activity.attempt", { n: attempt.n, max: attempt.max }) : null,
    activity?.progress ? tv("research.exec.activity.respondents", activity.progress) : null,
    activity && activity.model.answered > 0
      ? tv("research.exec.activity.modelSummary", {
          answered: activity.model.answered,
          tokens: activity.model.tokens ?? t("research.exec.activity.tokensUnknown"),
          cost: formatUsd(activity.model.costUsd),
        })
      : null,
    activity && activity.toolCalls > 0 ? tv("research.exec.activity.toolSummary", { calls: activity.toolCalls }) : null,
  ].filter((f): f is string => !!f);

  return (
    <div
      data-step-activity={open ? "open" : "closing"}
      className="grid motion-safe:transition-[grid-template-rows,opacity] motion-safe:duration-[var(--duration-panel)] motion-safe:ease-out"
      style={{ gridTemplateRows: expanded ? "1fr" : "0fr", opacity: expanded ? 1 : 0 }}
    >
      <div className="min-h-0 overflow-hidden">
        <div className="mt-2 flex gap-4 rounded-md border border-signal-edge bg-signal-tint p-4">
          {orb ? <ActivityOrb orb={orb} size={64} className="mt-0.5" /> : <span aria-hidden="true" className="w-16 shrink-0" />}
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">{t("research.exec.activity.title")}</p>
            <p className="mt-0.5 text-sm font-medium text-ink">{latest ? latest.text : t("research.exec.activity.empty")}</p>
            {facts.length ? (
              <p className="mt-1 font-mono text-xs tabular-nums text-ink-muted">{facts.join(" · ")}</p>
            ) : null}
            {activity && activity.lines.length > 1 ? <ActivityLog activity={activity} label={label} /> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

/** The step's last few feed lines, newest last: a polite live log. */
export function ActivityLog({ activity, label }: { activity: StepActivity; label: string }) {
  return (
    <ol role="log" aria-live="polite" aria-label={`${label}: ${t("research.exec.activity.title")}`} className="mt-3 flex flex-col gap-0.5 border-t border-signal-edge pt-2">
      {activity.lines.map((line) => (
        <li key={line.id} data-level={line.level} className={`flex gap-2 text-xs ${line.level === "warn" ? "text-status-you-ink" : "text-ink-muted"}`}>
          <span className="shrink-0 font-mono tabular-nums text-ink-faint">{clock(line.at)}</span>
          <span className="min-w-0">{line.text}</span>
        </li>
      ))}
    </ol>
  );
}
