// AI steps as durable jobs (ADR 0014, area A4): what the classic `job` does
// (the wrapper @439417 over the original @109829), ported. A job is started
// with POST <endpoint> -> {job_id}, then read with GET /api/job?id= every
// 700 ms until it is done, waits on a person, fails or is cancelled; a paused
// job keeps being read. One job at a time, as in the classic interface.
//
// What a person sees follows the design brief (§4.3): the phase the unit
// reports, real elapsed time, the heartbeat, the provider, the cost it can
// state -- never an invented percentage.

import { UnitError, unit } from "../client";
import type { UnitRouteKey } from "../routes";

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

export type JobContext = {
  projectId: string | null;
  revision: number | null;
  /** activeProvider1790: the project's preferred provider, its run policy's, the unit's default. */
  provider: string;
};

type Payload = Record<string, unknown> & { project?: unknown; spec?: unknown };

/** What the classic wrapper and job add to a payload before POSTing it. */
export function jobPayload(payload: Payload, ctx: JobContext, clientRequestId: string): Payload {
  const out: Payload = { ...payload };
  if (ctx.projectId) {
    out.project_id = ctx.projectId;
    out.project_revision = ctx.revision || (out.project_revision as number | undefined) || 0;
  }
  const p = ctx.provider;
  if (p === "anthropic" || p === "claude_code_subscription") {
    out.provider = p;
    if (out.project && typeof out.project === "object") {
      const project = out.project as Record<string, unknown>;
      out.project = { ...project, run_policy: { ...((project.run_policy as object) || {}), provider: p, allow_provider_fallback: false } };
    }
    if (out.spec && typeof out.spec === "object") out.spec = { ...(out.spec as object), provider: p };
  }
  return { ...out, client_request_id: (payload.client_request_id as string | undefined) || clientRequestId };
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

export type JobOutcome =
  | { kind: "running" }
  | { kind: "paused"; note: string }
  | { kind: "done"; result: unknown }
  | { kind: "waiting_user"; message: string }
  | { kind: "error"; message: string }
  | { kind: "cancelled"; message: string };

/** What one read of a job means, with the classic interface's wording. */
export function jobOutcome(j: JobRead): JobOutcome {
  const r = (j.result || {}) as { error?: string; message?: string };
  switch (j.state) {
    case "done":
      return { kind: "done", result: j.result };
    case "waiting_user":
      return { kind: "waiting_user", message: r.error || j.error?.error || "AI krok čeká na zásah. Projekt zůstává uložený." };
    case "paused":
      return { kind: "paused", note: `Běh je bezpečně pozastaven. ${j.phase || "Čekám na dostupnost Claude Pro."} · checkpoint zůstává uložený` };
    case "error": {
      const detail = r.error || r.message || j.error?.error || j.error?.message || j.telemetry?.provider_error || "";
      return { kind: "error", message: detail || "AI krok se nepodařilo dokončit. Projekt zůstává uložený; otevřete Diagnostiku." };
    }
    case "cancelled":
      return { kind: "cancelled", message: "JOB_CANCELLED: Běh byl zrušen uživatelem." };
    default:
      return { kind: "running" };
  }
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

export const JOB_BUSY = "Jiný AI krok už běží. Počkejte na jeho dokončení nebo jej explicitně zrušte.";
export const CANCEL_CONFIRM = "Opravdu chcete tento běh zrušit? Rozpracovaný krok se bezpečně ukončí.";
/** progress(): the cancel button arms 5 s after a job starts, so it is never hit by accident. */
export const CANCEL_ARM_MS = 5000;
export const POLL_MS = 700;

export type JobUpdate = {
  jobId: string | null;
  title: string;
  phase: string;
  meta: ReturnType<typeof jobMeta> | null;
  paused: string | null;
  startedAt: number;
};

type RunOptions = {
  title: string;
  ctx: JobContext;
  model?: string;
  /** Called on every read, for the job panel. */
  onUpdate?: (u: JobUpdate) => void;
  /** Injected in tests. */
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
  fetchImpl?: typeof fetch;
  requestId?: () => string;
};

let active: string | null = null;
let starting = false;

/** The id of the job this page is running, if any (ACTIVE_JOB_ID). */
export function activeJobId(): string | null {
  return active;
}

/** Start an AI step and read it until it ends. Resolves with its result; throws a JobError otherwise. */
export async function runJob(endpoint: UnitRouteKey, payload: Payload, o: RunOptions): Promise<unknown> {
  if (starting || active) throw new JobError(JOB_BUSY, "busy", active);
  const sleep = o.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  const now = o.now ?? Date.now;
  const requestId =
    o.requestId ?? (() => globalThis.crypto?.randomUUID?.() ?? `REQ-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  const startedAt = now();
  starting = true;
  o.onUpdate?.({ jobId: null, title: o.title, phase: "Zakládám durable úlohu…", meta: null, paused: null, startedAt });
  try {
    const body = jobPayload(payload, o.ctx, requestId());
    const st = (await unit(endpoint, { body, fetchImpl: o.fetchImpl })) as { job_id?: unknown };
    if (typeof st.job_id !== "string" || !st.job_id) throw new UnitError("Backend nevrátil job_id.", null);
    active = st.job_id;
    starting = false;
    for (;;) {
      await sleep(POLL_MS);
      const j = (await unit("job", { query: { id: active }, fetchImpl: o.fetchImpl })) as JobRead;
      const outcome = jobOutcome(j);
      const meta = jobMeta(j, {
        model: o.model,
        elapsed: Math.round((now() - startedAt) / 1000),
      });
      o.onUpdate?.({
        jobId: active,
        title: o.title,
        phase: j.phase || "Pracuji…",
        meta,
        paused: outcome.kind === "paused" ? outcome.note : null,
        startedAt,
      });
      if (outcome.kind === "done") return outcome.result;
      if (outcome.kind === "waiting_user" || outcome.kind === "error" || outcome.kind === "cancelled") {
        throw new JobError(outcome.message, outcome.kind, active);
      }
    }
  } finally {
    active = null;
    starting = false;
  }
}

/** cancelActiveJob: the classic body, sent only after the person confirmed. */
export async function cancelJob(jobId: string, fetchImpl?: typeof fetch): Promise<void> {
  await unit("jobCancel", {
    id: jobId,
    body: { source: "ui_progress_button", reason: "explicit_user_confirmation" },
    timeoutMs: 20_000,
    fetchImpl,
  });
}
