// What a person sees of an AI step while it runs (ADR 0014, area A4), ported from
// the classic interface's job panel (the wrapper @439417 over the original
// @109829): the phase, real elapsed time, the heartbeat, the provider, the cost it
// can state -- never an invented percentage (design brief §4.3). The steps
// themselves are AIA's research agent jobs (/api/v1/studies/{id}/research/agent-jobs,
// lib/research-agent-jobs.ts); the 18.6.6 unit's own job runner is gone (ADR 0018).

export type Telemetry = {
  elapsed_seconds?: number;
  hard_seconds?: number;
  usual_seconds?: [number, number];
  heartbeat_age_seconds?: number | null;
  provider?: string;
  provider_stage?: string;
  provider_error?: string;
  model?: string;
  actual_cost_usd?: number;
  estimated_cost_usd?: number;
};

export type JobRead = {
  state?: string;
  phase?: string;
  result?: unknown;
  error?: { error?: string; message?: string } | null;
  telemetry?: Telemetry;
};

/** fmtTime: seconds as the classic interface prints them. */
export function fmtTime(sec: unknown): string {
  const s = Math.max(0, Number(sec || 0));
  if (s < 60) return `${Math.round(s)} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${String(Math.round(s % 60)).padStart(2, "0")} s`;
  return `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")} min`;
}

/** usualRange */
export function usualRange(x: unknown): string {
  if (!Array.isArray(x) || x.length < 2) return "";
  return `${fmtTime(x[0])}–${fmtTime(x[1])}`;
}

/** aiProviderLabel's effective binding: the name shown when the unit reports no provider. */
export const PROVIDER_LABEL = "AI partner";

/** The classic progress meta line, as parts a screen can lay out. */
export function jobMeta(j: JobRead, fallback: { model?: string; elapsed: number }) {
  const t = j.telemetry || {};
  const provider = t.provider || PROVIDER_LABEL;
  const model = t.model || fallback.model || "";
  const cost =
    String(provider).includes("claude_code") || String(provider).includes("strict_claude")
      ? "subscription · API $0 · tokeny po dokončení"
      : t.actual_cost_usd
        ? `$${Number(t.actual_cost_usd).toFixed(3)}`
        : t.estimated_cost_usd
          ? `odhad $${Number(t.estimated_cost_usd).toFixed(3)}`
          : "náklad po dokončení";
  return {
    elapsed: fmtTime(t.elapsed_seconds ?? fallback.elapsed),
    usual: t.usual_seconds ? usualRange(t.usual_seconds) : "",
    hardStop: t.hard_seconds ? fmtTime(t.hard_seconds) : "",
    /** The server's own stop, in seconds (0 when it states none): the notice's threshold. */
    hardSeconds: Number(t.hard_seconds || 0),
    providerStage: t.provider_stage || "",
    heartbeat: t.heartbeat_age_seconds == null ? "—" : fmtTime(t.heartbeat_age_seconds),
    provider,
    model,
    cost,
  };
}

/** The classic meta line, verbatim, for comparison with the original. */
export function jobMetaLine(m: ReturnType<typeof jobMeta>): string {
  return (
    `Běží ${m.elapsed}` +
    (m.usual ? ` · obvykle ${m.usual}` : "") +
    (m.hardStop ? ` · server hard stop ${m.hardStop}` : "") +
    (m.providerStage ? ` · provider: ${m.providerStage}` : "") +
    ` · worker ${m.heartbeat} · ${m.provider}` +
    (m.model ? ` · ${m.model}` : "") +
    ` · ${m.cost}`
  );
}

export class JobError extends Error {
  constructor(
    message: string,
    readonly kind: "waiting_user" | "error" | "cancelled" | "busy",
    readonly jobId: string | null,
  ) {
    super(message);
    this.name = "JobError";
  }
}

export const CANCEL_CONFIRM = "Opravdu chcete tento běh zrušit? Rozpracovaný krok se bezpečně ukončí.";
/** progress(): the cancel button arms 5 s after a job starts, so it is never hit by accident. */
export const CANCEL_ARM_MS = 5000;

export type JobUpdate = {
  jobId: string | null;
  title: string;
  phase: string;
  meta: ReturnType<typeof jobMeta> | null;
  paused: string | null;
  startedAt: number;
};
