"use client";

// Run, Progress and Results (ADR 0016): the research lifecycle in AIA, against
// AIA's study-scoped execution API. The browser submits the design it holds as a
// Design Revision, reads what AIA's checks say about it, starts one run over that
// exact revision, and then only reads: state, steps, and the artifacts the run
// produced. Nothing here decides a number; everything here says where a number
// came from -- and when it came from the fictional dataset, that it is fiction.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  ApiError,
  api,
  type Artifact,
  type ResearchAnalysis,
  type ResearchReport,
  type Readiness,
  type ResearchRun,
  type ResearchRunSummary,
  type ResearchStep,
  type Study,
  research,
} from "@/lib/api";
import { ActivityOrb } from "@/components/brand/ActivityOrb";
import { researchStepOrb } from "@/lib/activity-orb";
import { saveBlob } from "@/lib/download";
import { type BatteryWithMaps, readObjectMap } from "@/lib/object-map-view";
import {
  STEP_ORDER,
  ANALYSIS_ORDER,
  isSynthetic,
  parkedForRuntime,
  waitingDetail,
  phaseLabel,
  phaseTone,
  resultTable,
  shouldPoll,
  sociomapObjects,
  stepLabel,
  stepOf,
  stepStatusLabel,
  stepTone,
  supportNote,
  type ResultTable,
} from "@/lib/research-execution";
import { CONFLICT_MESSAGE } from "@/research/store";
import { projectVariants, selectedVariant } from "@/research/plan";
import { withApproval } from "@/research/persona";
import type { StepKey } from "@/research/steps";
import { ActionDock, Switch } from "../step";
import { AiButton, Button, Chip, Field, TextArea, TextInput } from "../ui";
import { useResearch } from "./context";
import { SociomappingView } from "./SociomappingView";
import { ObjectMapView } from "./ObjectMapView";

const POLL_MS = 2000;
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** The server refused a start or retry because the study's limit asks first: the ceiling it worked out. */
function confirmationAsked(e: unknown): { ceiling: number; limit: number } | null {
  if (!(e instanceof ApiError) || e.code !== "cost_confirmation_required") return null;
  const { ceiling_usd, limit_usd } = e.details as { ceiling_usd?: unknown; limit_usd?: unknown };
  return typeof ceiling_usd === "number" && typeof limit_usd === "number" ? { ceiling: ceiling_usd, limit: limit_usd } : null;
}
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString("cs-CZ") : "—");

function Card({ id, title, children, tone, region }: { id?: string; title?: string; children: ReactNode; tone?: "notice" | "fault"; region?: boolean }) {
  const frame =
    tone === "fault"
      ? "border-status-fault/40 bg-status-fault-wash"
      : tone === "notice"
        ? "border-status-you-ink/40 bg-status-you-wash"
        : "border-border bg-surface-raised";
  return (
    <section id={id} aria-label={region ? title : undefined} className={`scroll-mt-60 rounded-card border p-5 ${frame}`}>
      {title ? <h2 className="mb-2 text-base font-semibold">{title}</h2> : null}
      {children}
    </section>
  );
}

function SyntheticBanner() {
  return (
    <p role="note" data-origin="synthetic" className="rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm font-semibold text-status-fault">
      {t("research.exec.syntheticNotice")}
    </p>
  );
}

function useFrame() {
  return useResearch().frame;
}

// ---------------------------------------------------------------- Run --------

/**
 * What starting this run can cost at most, beside what the study has left, and the study's limit
 * above which Start asks first (plan 5b.2). The ceiling is the server's; the page only shows it,
 * and an unknown one is said to be unknown, never drawn as zero.
 */
function CostCard({ readiness, canEdit, onLimitSaved }: { readiness: Readiness; canEdit: boolean; onLimitSaved: () => void }) {
  const frame = useFrame();
  const [study, setStudy] = useState<Study | null | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    api.study(frame.studyId).then(
      (s) => live && setStudy(s),
      () => live && setStudy(null),
    );
    return () => {
      live = false;
    };
  }, [frame.studyId, readiness]);
  // An API that does not send a figure has not given one: read it as absent, never as zero.
  const ceiling = num(readiness.cost_ceiling_usd);
  const limit = num(readiness.spend_confirm_usd);
  // The switch is on while a limit is stored, or while the person is typing one; the switch
  // and the amount follow the stored limit when it changes. They are adjusted during render,
  // never in an effect: an effect runs after the commit, so a switch turned on (or an amount
  // typed) before it ran was overwritten by the mount's "no limit".
  const [asking, setAsking] = useState(limit !== null);
  const [amount, setAmount] = useState(limit === null ? "" : String(limit));
  const [shownLimit, setShownLimit] = useState(limit);
  if (limit !== shownLimit) {
    setShownLimit(limit);
    setAsking(limit !== null);
    setAmount(limit === null ? "" : String(limit));
  }

  const save = async (limit: number | null) => {
    setSaving(true);
    setError(null);
    try {
      await research.setSpendConfirm(frame.studyId, limit);
      onLimitSaved();
    } catch (e) {
      setError(message(e));
    } finally {
      setSaving(false);
    }
  };
  const typed = amount.trim() === "" ? Number.NaN : Number(amount);
  const remaining = num(study?.remaining_usd);
  const budget = num(study?.budget_usd);
  const commit = () => {
    if (Number.isFinite(typed) && typed >= 0 && typed !== limit) void save(typed);
  };
  return (
    <Card title={t("research.exec.cost.title")} region>
      {ceiling !== null ? (
        <>
          <p className="text-sm font-medium">{tv("research.exec.cost.ceiling", { ceiling: ceiling.toFixed(2) })}</p>
          <p className="text-xs text-ink-muted">
            {tv("research.exec.cost.basis", { requests: readiness.fieldwork_requests, calls: readiness.analysis_calls })}
          </p>
          <p className="text-xs text-ink-muted">{t("research.exec.cost.bound")}</p>
          <CostBar ceiling={ceiling} limit={limit} asks={readiness.confirmation_required} />
        </>
      ) : (
        <p className="text-sm">{t(`research.exec.cost.unknown.${readiness.cost_ceiling_unknown ?? "sample_size_missing"}`)}</p>
      )}
      {study === undefined ? null : remaining !== null && budget !== null ? (
        <p className="mt-2 text-sm">{tv("research.exec.cost.remaining", { remaining: remaining.toFixed(2), budget: budget.toFixed(2) })}</p>
      ) : (
        <p className="mt-2 text-sm text-ink-muted">{t("research.exec.cost.budgetUnknown")}</p>
      )}
      <p className="mt-2 text-sm">
        {limit === null ? t("research.exec.cost.limitNone") : tv("research.exec.cost.limitSet", { limit: limit.toFixed(2) })}
      </p>
      {readiness.confirmation_required ? <p className="text-sm font-medium text-status-you-ink">{t("research.exec.cost.willAsk")}</p> : null}
      {limit !== null && ceiling === null ? (
        <p role="alert" className="text-sm text-status-fault">{t("research.exec.cost.unknownBlocks")}</p>
      ) : null}
      {canEdit ? (
        // The limit is saved when the amount is left or Enter is pressed; switching it off clears it.
        <form
          aria-label={t("research.exec.cost.limit")}
          className="mt-3 flex flex-wrap items-center gap-3 border-t border-border pt-3"
          onSubmit={(e) => {
            e.preventDefault();
            commit();
          }}
        >
          <Switch
            checked={asking}
            disabled={saving}
            label={t("research.exec.cost.switch")}
            onChange={(on) => {
              setAsking(on);
              if (!on && limit !== null) void save(null);
              if (!on) setAmount("");
            }}
          />
          {asking ? (
            <span className="inline-flex items-center gap-2">
              <input
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                aria-label={t("research.exec.cost.limitAmount")}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                onBlur={commit}
                className="min-h-9 w-28 rounded-control border border-border-strong bg-surface-raised px-2.5 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
              />
              <span className="text-sm text-ink-muted">USD</span>
            </span>
          ) : null}
          {saving ? <span className="text-xs text-ink-muted">{t("research.exec.cost.saving")}</span> : null}
        </form>
      ) : null}
      {error ? <p role="alert" className="mt-2 text-sm text-status-fault">{error}</p> : null}
    </Card>
  );
}

/** The run's ceiling against the study's limit: amber when Start will ask first; the limit as a mark. */
function CostBar({ ceiling, limit, asks }: { ceiling: number; limit: number | null; asks: boolean }) {
  const scale = Math.max(ceiling, limit ?? 0) * 1.4 || 1;
  const pct = (x: number) => `${Math.min(100, (x / scale) * 100)}%`;
  return (
    <div className="mt-3">
      <div aria-hidden="true" className="relative h-2.5 rounded-sm bg-surface-sunken">
        <div className={`h-2.5 rounded-sm ${asks ? "bg-status-you" : "bg-signal"}`} style={{ width: pct(ceiling) }} />
        {limit !== null ? <i className="absolute -top-1 block h-[18px] w-0.5 bg-ink" style={{ left: pct(limit) }} /> : null}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
        <span className="inline-flex items-center gap-1.5">
          <i aria-hidden="true" className={`block size-2.5 rounded-sm ${asks ? "bg-status-you" : "bg-signal"}`} />
          {t("research.exec.cost.legendCeiling")}
        </span>
        {limit !== null ? (
          <span className="inline-flex items-center gap-1.5">
            <i aria-hidden="true" className="block h-2.5 w-0.5 bg-ink" />
            {t("research.exec.cost.legendLimit")}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/** Where a failing readiness check is fixed: the sample on Dimenze, the audience on Audience, the rest on Dotazník. */
export function fixStep(checkId: string): StepKey {
  if (/sample|^n$/.test(checkId)) return "persona";
  if (/audience/.test(checkId)) return "audience";
  return "questionnaire";
}

/** "Co spustíte": each step of the design in one line, as the revision carries it, with a way back to it. */
function Receipt({ revision, readiness }: { revision: number; readiness: Readiness }) {
  const { state, stepHref } = useResearch();
  const p = state.project;
  const variant = projectVariants(state).find((v) => v.id === selectedVariant(p));
  const clip = (x: unknown) => {
    const v = String(x || "").trim();
    return v.length > 140 ? `${v.slice(0, 139)}…` : v;
  };
  const rows: [StepKey, string][] = [
    ["brief", clip(p.goal) || "—"],
    ["plan", clip(variant?.title || state.analysis?.problem_summary) || "—"],
    ["questionnaire", tv("research.exec.counts", { questions: readiness.questions, batteries: readiness.batteries, objects: readiness.objects, n: readiness.n ?? "—" })],
    ["audience", clip(p.audience?.description || p.audience?.dataset_name) || "—"],
    ["persona", tv("research.exec.receiptDims", { d: withApproval(p).approved.length, n: readiness.n ?? "—" })],
  ];
  return (
    <Card title={tv("research.exec.revision", { revision })}>
      <p className="text-[13px] text-ink-muted">{t("research.exec.revisionHelp")}</p>
      <h3 className="mt-3 text-[13px] font-semibold">{t("research.exec.receiptTitle")}</h3>
      <dl className="mt-1.5 divide-y divide-border rounded-control border border-border">
        {rows.map(([k, v]) => (
          <div key={k} className="grid grid-cols-[8rem_1fr_auto] items-baseline gap-3 px-3 py-2 text-sm">
            <dt className="text-ink-muted">{t(`aia.stages.${k}`)}</dt>
            <dd className="min-w-0">{v}</dd>
            <dd>
              <Link href={stepHref(k)} className="text-xs text-signal no-underline hover:underline">{t("research.exec.edit")}</Link>
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

export function RunStep() {
  const { store, stepHref, confirm } = useResearch();
  const frame = useFrame();
  const router = useRouter();
  const [prepared, setPrepared] = useState<
    | { kind: "loading" }
    | { kind: "failed"; message: string }
    | { kind: "none" }
    | { kind: "ready"; revision: number; readiness: Readiness }
  >({ kind: "loading" });
  const [runs, setRuns] = useState<ResearchRunSummary[]>([]);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      let revisionId: string;
      let revision: number;
      if (frame.canEdit) {
        // The design the person sees, once per visit -- but only as AIA holds it: a
        // change still waiting for its save is saved first, and a copy whose save was
        // refused (someone saved a newer one) never becomes a revision a run executes.
        const s = store.get();
        if (s.revision === null || s.save.kind !== "saved") {
          try {
            await store.flush("run");
          } catch (e) {
            throw store.get().save.kind === "conflict" ? new Error(CONFLICT_MESSAGE) : e;
          }
        }
        const r = await research.submitDesign(frame.studyId, store.get().project, "run");
        revisionId = r.revision_id;
        revision = r.revision;
      } else {
        const latest = (await research.revisions(frame.studyId))[0];
        if (!latest) return live && setPrepared({ kind: "none" });
        revisionId = latest.revision_id;
        revision = latest.revision;
      }
      const readiness = await research.readiness(frame.studyId, revisionId);
      if (live) setPrepared({ kind: "ready", revision, readiness });
    })().catch((e: unknown) => live && setPrepared({ kind: "failed", message: message(e) }));
    research.runs(frame.studyId).then((r) => live && setRuns(r), () => {});
    return () => {
      live = false;
    };
  }, [frame.studyId, frame.canEdit, store]);

  const rereadReadiness = async () => {
    if (prepared.kind !== "ready") return;
    try {
      const readiness = await research.readiness(frame.studyId, prepared.readiness.design_revision_id);
      setPrepared({ ...prepared, readiness });
    } catch (e) {
      setStartError(message(e));
    }
  };

  const ask = (ceiling: number, limit: number) =>
    confirm(tv("research.exec.cost.confirm", { ceiling: ceiling.toFixed(2), limit: limit.toFixed(2) }));

  const start = async () => {
    if (prepared.kind !== "ready") return;
    const { readiness } = prepared;
    const ceiling = num(readiness.cost_ceiling_usd);
    const limit = num(readiness.spend_confirm_usd);
    let yes: number | undefined;
    if (readiness.confirmation_required && ceiling !== null && limit !== null) {
      if (!(await ask(ceiling, limit))) return;
      yes = ceiling;
    }
    setStarting(true);
    setStartError(null);
    try {
      try {
        await research.start(frame.studyId, readiness.design_revision_id, yes);
      } catch (e) {
        // The limit or the ceiling changed since the page read them: ask with the server's figure.
        const asked = confirmationAsked(e);
        if (!asked || yes !== undefined || !(await ask(asked.ceiling, asked.limit))) throw e;
        await research.start(frame.studyId, readiness.design_revision_id, asked.ceiling);
      }
      router.push(stepHref("progress"));
    } catch (e) {
      setStartError(message(e));
      setStarting(false);
    }
  };
  const blocked =
    prepared.kind === "ready" && num(prepared.readiness.spend_confirm_usd) !== null && num(prepared.readiness.cost_ceiling_usd) === null;

  return (
    <div className="flex max-w-4xl flex-col gap-4">
      {prepared.kind === "loading" ? <p className="text-sm text-ink-muted">{t("research.exec.preparing")}</p> : null}
      {prepared.kind === "failed" ? (
        <Card title={t("research.exec.readinessFailed")} tone="fault">
          <p className="text-sm">{prepared.message}</p>
        </Card>
      ) : null}
      {prepared.kind === "none" ? <Card><p className="text-sm">{t("research.exec.noRuns")}</p></Card> : null}
      {prepared.kind === "ready" ? (
        <>
          <Receipt revision={prepared.revision} readiness={prepared.readiness} />
          <Card title={prepared.readiness.ready ? t("research.exec.ready") : t("research.exec.notReady")}>
            <ul className="flex flex-col gap-2" aria-label={t("research.exec.steps.preflight")}>
              {prepared.readiness.checks.map((c) => (
                <li key={c.id} className="flex items-start gap-2 text-sm">
                  <Chip tone={c.status === "FAIL" ? "fault" : c.status === "WARN" ? "you" : "done"}>{c.status}</Chip>
                  <span className="flex-1">{c.message}</span>
                  {c.status !== "PASS" ? (
                    <Link href={stepHref(fixStep(c.id))} className="whitespace-nowrap text-xs text-signal no-underline hover:underline">
                      {t("research.exec.fix")}
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs text-ink-muted">{tv("research.exec.rules", { rules: prepared.readiness.rules })}</p>
          </Card>
          <CostCard readiness={prepared.readiness} canEdit={frame.canEdit} onLimitSaved={rereadReadiness} />
          {prepared.readiness.fieldwork_source === "ai_runtime" ? (
            <p role="note" className="rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">{t("research.exec.aiRuntimeNotice")}</p>
          ) : (
            <SyntheticBanner />
          )}
          {startError ? <p role="alert" className="text-sm text-status-fault">{startError}</p> : null}
        </>
      ) : null}
      <RunList runs={runs} />
      <ActionDock
        back={{ href: stepHref("persona"), label: `5. ${t("aia.stages.persona")}` }}
        ready={prepared.kind === "ready" && prepared.readiness.ready && frame.canEdit && !blocked}
        note={
          !frame.canEdit
            ? t("research.exec.readOnly")
            : prepared.kind !== "ready"
              ? null
              : !prepared.readiness.ready
                ? t("research.exec.dockNotReady")
                : blocked
                  ? t("research.exec.dockBlocked")
                  : prepared.readiness.confirmation_required
                    ? t("research.exec.dockAsk")
                    : t("research.exec.dockReady")
        }
      >
        {prepared.kind === "ready" ? (
          <AiButton variant="primary" onClick={() => void start()} disabled={!prepared.readiness.ready || !frame.canEdit || starting || blocked}>
            {starting ? t("research.exec.starting") : t("research.exec.start")}
          </AiButton>
        ) : null}
      </ActionDock>
    </div>
  );
}

function RunList({ runs }: { runs: ResearchRunSummary[] }) {
  const { stepHref } = useResearch();
  return (
    <Card title={t("research.exec.previous")}>
      {runs.length === 0 ? (
        <p className="text-sm text-ink-muted">{t("research.exec.noRuns")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {runs.map((r) => (
            <li key={r.run_id} className="flex flex-wrap items-center gap-2 text-sm">
              <Chip tone={phaseTone(r.phase)}>{phaseLabel(r.phase)}</Chip>
              <span>{tv("research.exec.revision", { revision: r.design_revision })}</span>
              <span className="text-ink-muted">{tv("research.exec.startedAt", { when: when(r.created_at) })}</span>
              {isSynthetic(r) ? <Chip tone="fault">{t("research.exec.fictional")}</Chip> : null}
              <a className="underline" href={`${stepHref(r.phase === "COMPLETED" ? "results" : "progress")}?run=${encodeURIComponent(r.run_id)}`}>
                {r.phase === "COMPLETED" ? t("research.exec.toResults") : t("research.exec.toProgress")}
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ------------------------------------------------------------ the run -------

function runFromQuery(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("run");
}

/** The run the page is about: `?run=` if given, else the newest; kept fresh while it can change. */
function useRun(): [ResearchRun | null | undefined, () => void, (r: ResearchRun) => void, string | null] {
  const frame = useFrame();
  const [run, setRun] = useState<ResearchRun | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const wanted = runFromQuery();
    const read = async () => {
      try {
        // The list is a summary (no steps, no artifacts): the newest is read in full.
        const id = wanted ?? (await research.runs(frame.studyId))[0]?.run_id;
        const current = id ? await research.run(frame.studyId, id) : null;
        if (!live) return;
        setRun(current);
        setError(null);
        if (current && shouldPoll(current)) timer = setTimeout(read, POLL_MS);
      } catch (e) {
        if (!live) return;
        if (e instanceof ApiError && e.status === 404) return setRun(null);
        setError(message(e));
      }
    };
    void read();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [frame.studyId, version]);
  return [run, () => setVersion((v) => v + 1), setRun, error];
}

/**
 * A step the study's budget stopped (AWAITING_BUDGET) can be let through by a person who may spend:
 * they name a new total, never lower than the budget now, and the cap stays hard -- the step stops
 * again if that is still not enough. The decision is recorded by the API; nothing here decides it.
 */
function BudgetLift({ run, step, act, busy }: { run: ResearchRun; step: ResearchStep; act: (fn: () => Promise<ResearchRun>) => Promise<void>; busy: boolean }) {
  const frame = useFrame();
  const [current, setCurrent] = useState<{ budget: number; spent: number } | null | undefined>(undefined);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  useEffect(() => {
    let live = true;
    api.study(frame.studyId).then(
      (s) => {
        if (!live) return;
        const budget = typeof s.budget_usd === "number" ? s.budget_usd : null;
        setCurrent(budget === null ? null : { budget, spent: s.spent_usd ?? 0 });
        if (budget !== null) setAmount(String(budget));
      },
      () => live && setCurrent(null),
    );
    return () => {
      live = false;
    };
  }, [frame.studyId, run.run_id]);
  const total = amount.trim() === "" ? Number.NaN : Number(amount);
  const valid = current != null && Number.isFinite(total) && total >= current.budget;
  return (
    <form
      aria-label={t("research.exec.budget.title")}
      className="mt-1 flex flex-col gap-2 rounded-sm border border-border bg-surface p-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) void act(() => research.liftBudget(frame.studyId, run.run_id, step.node_key, total, note.trim()));
      }}
    >
      {current === undefined ? (
        <p className="text-xs text-ink-muted">{t("research.loading")}</p>
      ) : current === null ? (
        <p role="alert" className="text-xs text-status-fault">{t("research.exec.budget.unknown")}</p>
      ) : (
        <p className="text-xs">{tv("research.exec.budget.status", { budget: current.budget.toFixed(2), spent: current.spent.toFixed(2) })}</p>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("research.exec.budget.amount")} className="w-48">
          <TextInput type="number" inputMode="decimal" min={current?.budget ?? 0} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} disabled={current == null} />
        </Field>
        <Field label={t("research.exec.budget.note")} className="min-w-48 flex-1">
          <TextArea rows={1} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} className="min-h-9 w-full" />
        </Field>
        <Button type="submit" variant="primary" disabled={!valid || busy}>{t("research.exec.budget.lift")}</Button>
      </div>
      <p className="text-xs text-ink-muted">{t("research.exec.budget.hardCap")}</p>
    </form>
  );
}

// ------------------------------------------------------------ Progress -------

/** An orb beside a step while it runs (lib/activity-orb.ts), else nothing. */
function StepOrb({ run, step }: { run: ResearchRun; step: ResearchStep }) {
  const orb = researchStepOrb(run, step);
  return orb ? <ActivityOrb orb={orb} /> : null;
}

export function ProgressStep() {
  const { confirm, stepHref } = useResearch();
  const frame = useFrame();
  const [run, refresh, setRun, error] = useRun();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const act = useCallback(
    async (fn: () => Promise<ResearchRun>) => {
      setBusy(true);
      setActionError(null);
      try {
        setRun(await fn());
      } catch (e) {
        setActionError(message(e));
      } finally {
        setBusy(false);
      }
    },
    [setRun],
  );

  if (run === undefined) return <p className="text-sm text-ink-muted">{t("research.loading")}</p>;
  if (run === null) return <Card><p className="text-sm">{t("research.exec.noRuns")}</p></Card>;
  const parked = parkedForRuntime(run);
  const failed = run.steps.find((s) => s.status === "FAILED");
  return (
    <div className="flex max-w-3xl flex-col gap-4">
      {isSynthetic(run) ? <SyntheticBanner /> : null}
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <Chip tone={phaseTone(run.phase)}>{phaseLabel(run.phase)}</Chip>
          <span className="text-sm">{tv("research.exec.revision", { revision: run.design_revision })}</span>
          <span className="text-sm text-ink-muted">{tv("research.exec.startedAt", { when: when(run.created_at) })}</span>
          {run.finished_at ? <span className="text-sm text-ink-muted">{tv("research.exec.finishedAt", { when: when(run.finished_at) })}</span> : null}
          {run.retry_of ? <span className="text-xs text-ink-muted">{tv("research.exec.retryOf", { run: run.retry_of })}</span> : null}
        </div>
        {parked ? (
          <p role="status" className="mt-3 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">
            {parked.node_key === "run" ? t("research.exec.parked") : tv("research.exec.parkedAt", { step: stepLabel(parked.node_key) })}
          </p>
        ) : null}
        {failed ? (
          <p role="alert" className="mt-3 text-sm text-status-fault">
            {tv("research.exec.failed", { step: stepLabel(failed.node_key) })} {failed.error_message ?? ""}
          </p>
        ) : null}
        {error ? <p role="alert" className="mt-3 text-sm text-status-fault">{error}</p> : null}
      </Card>
      <Card title={t("aia.stages.progress")}>
        <ol className="flex flex-col gap-3" aria-label={t("aia.stages.progress")}>
          {[...STEP_ORDER, ...ANALYSIS_ORDER.map((id) => `analysis_${id}`), "report"].map((key) => stepOf(run, key)).filter((s): s is ResearchStep => !!s).map((s) => (
            <li key={s.node_key} data-step={s.node_key} data-status={s.status} className="flex flex-col gap-0.5 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={stepTone(s)}>{stepStatusLabel(s)}</Chip>
                <StepOrb run={run} step={s} />
                <span className="font-medium">{stepLabel(s.node_key)}</span>
                {s.data_origin ? <Chip tone="fault">{s.data_origin}</Chip> : null}
              </div>
              <span className="text-xs text-ink-muted">
                {s.started_at ? tv("research.exec.startedAt", { when: when(s.started_at) }) : null}
                {s.finished_at ? ` · ${tv("research.exec.finishedAt", { when: when(s.finished_at) })}` : null}
                {s.attempts_recorded ? ` · ${tv("research.exec.attempts", { n: s.attempts_recorded, max: s.max_attempts })}` : null}
              </span>
              {waitingDetail(s) ? <span className="text-xs text-ink">{waitingDetail(s)}</span> : null}
              {frame.canEdit && s.status === "AWAITING_BUDGET" && !run.is_terminal ? (
                <BudgetLift run={run} step={s} act={act} busy={busy} />
              ) : null}
            </li>
          ))}
        </ol>
      </Card>
      <div className="flex flex-wrap items-center gap-3">
        {run.phase === "COMPLETED" ? (
          <a className="text-sm underline" href={`${stepHref("results")}?run=${encodeURIComponent(run.run_id)}`}>{t("research.exec.toResults")}</a>
        ) : null}
        {frame.canEdit && !run.is_terminal ? (
          <Button
            disabled={busy}
            onClick={async () => {
              if (await confirm(t("research.exec.cancelConfirm"))) await act(() => research.cancel(frame.studyId, run.run_id));
            }}
          >
            {t("research.exec.cancel")}
          </Button>
        ) : null}
        {frame.canEdit && run.retryable ? (
          <Button
            variant="primary"
            disabled={busy}
            onClick={() =>
              act(async () => {
                try {
                  return await research.retry(frame.studyId, run.run_id);
                } catch (e) {
                  // A retry is a new run, so the study's limit asks again.
                  const asked = confirmationAsked(e);
                  if (!asked) throw e;
                  const yes = await confirm(tv("research.exec.cost.confirm", { ceiling: asked.ceiling.toFixed(2), limit: asked.limit.toFixed(2) }));
                  if (!yes) return run;
                  return research.retry(frame.studyId, run.run_id, asked.ceiling);
                }
              })
            }
          >
            {t("research.exec.retry")}
          </Button>
        ) : null}
        <Button variant="quiet" onClick={refresh}>{t("research.exec.refresh")}</Button>
      </div>
      {actionError ? <p role="alert" className="text-sm text-status-fault">{actionError}</p> : null}
    </div>
  );
}

// ------------------------------------------------------------- Results -------

type Loaded<T> = { state: "loading" } | { state: "ready"; value: T } | { state: "failed"; message: string } | { state: "hidden" };

function useArtifact(run: ResearchRun | null | undefined, nodeKey: string): Loaded<Artifact> | null {
  const frame = useFrame();
  const id = run ? (stepOf(run, nodeKey)?.artifact_id ?? null) : null;
  // Keyed by artifact id: a result for another id reads as still loading.
  const [loaded, setLoaded] = useState<{ id: string; value: Loaded<Artifact> } | null>(null);
  useEffect(() => {
    if (!run || !id) return;
    let live = true;
    research.artifact(frame.studyId, run.run_id, id).then(
      (value) => live && setLoaded({ id, value: { state: "ready", value } }),
      (e: unknown) =>
        live &&
        setLoaded({
          id,
          value: e instanceof ApiError && e.status === 403 ? { state: "hidden" } : { state: "failed", message: message(e) },
        }),
    );
    return () => {
      live = false;
    };
  }, [frame.studyId, run, id]);
  if (!id) return null;
  return loaded && loaded.id === id ? loaded.value : { state: "loading" };
}

function Provenance({ artifact, run }: { artifact: Artifact; run: ResearchRun }) {
  return (
    <p className="mt-3 text-xs text-ink-muted">
      {t("research.exec.results.provenance")}:{" "}
      {tv("research.exec.results.artifact", {
        id: artifact.artifact_id,
        sha: artifact.sha256.slice(0, 12),
        run: run.run_id,
        revision: run.design_revision,
      })}
    </p>
  );
}

function Table({ table }: { table: ResultTable }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs text-ink-muted">{supportNote(table)}</p>
      {table.rows.length ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-ink-muted">
              <th className="py-1 font-medium"> </th>
              <th className="py-1 font-medium"><span className="sr-only">{t("research.exec.results.bar")}</span></th>
              <th className="whitespace-nowrap py-1 font-medium">{t("research.exec.results.value")}</th>
              <th className="whitespace-nowrap py-1 font-medium">{t("research.exec.results.interval")}</th>
            </tr>
          </thead>
          <tbody>
            {table.rows.map((r) => (
              <tr key={r.label} className="border-t border-border">
                <td className="py-1 pr-3">{r.label}</td>
                <td className="w-[40%] min-w-20 py-1 pr-3">{r.bar ? <IntervalBar bar={r.bar} /> : null}</td>
                <td className="whitespace-nowrap py-1 pr-3 tabular-nums">{r.value ?? "—"}</td>
                <td className="whitespace-nowrap py-1 tabular-nums text-ink-muted">{r.interval ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {table.verbatims.length ? (
        <ul className="list-disc pl-5 text-sm text-ink-muted" aria-label={t("research.exec.results.verbatims")}>
          {table.verbatims.map((v) => <li key={v}>{v}</li>)}
        </ul>
      ) : null}
    </div>
  );
}

/** A share on 0–100 %: its 95 % interval as a band, the value as a tick. */
function IntervalBar({ bar }: { bar: NonNullable<ResultTable["rows"][number]["bar"]> }) {
  const pc = (v: number) => `${Math.max(0, Math.min(100, v))}%`;
  return (
    <span aria-hidden="true" className="relative block h-3.5 rounded-sm bg-surface-sunken">
      {bar.low !== null && bar.high !== null ? (
        <i className="absolute inset-y-0 block rounded-sm bg-signal/25" style={{ left: pc(bar.low), width: pc(bar.high - bar.low) }} />
      ) : null}
      <i className="absolute -inset-y-0.5 block w-[3px] -translate-x-1/2 rounded-sm bg-signal" style={{ left: pc(bar.value) }} />
    </span>
  );
}

/** Jump chips over the results that this run has. */
function ResultChips({ items }: { items: [string, string][] }) {
  return (
    <nav aria-label={t("research.exec.results.jumpLabel")} className="flex flex-wrap gap-1.5">
      {items.map(([id, label]) => (
        <button
          key={id}
          type="button"
          onClick={() => document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" })}
          className="inline-flex items-center whitespace-nowrap rounded-pill border border-border bg-surface-raised px-3 py-1 text-[13px] leading-5 hover:border-border-strong hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          {label}
        </button>
      ))}
    </nav>
  );
}

export function ResultsStep() {
  const [run] = useRun();
  const frame = useFrame();
  const aggregate = useArtifact(run, "aggregate");
  const sociomap = useArtifact(run, "sociomap");
  const sociomapping = useArtifact(run, "sociomapping");
  const report = run?.steps.some((step) => step.kind === "research_report")
    ? <InternalReport key={run.run_id} run={run} />
    : <p className="text-sm text-ink-muted">{t("research.exec.results.reportNotInAia")}</p>;

  if (run === undefined) return <p className="text-sm text-ink-muted">{t("research.loading")}</p>;
  if (run === null || !stepOf(run, "aggregate")?.artifact_id) {
    return (
      <div className="flex max-w-3xl flex-col gap-4">
        <Card>
          <p className="text-sm">{run && parkedForRuntime(run) ? t("research.exec.noResultsParked") : t("research.exec.noResults")}</p>
        </Card>
        {report}
      </div>
    );
  }
  const showMap = Boolean(sociomap && sociomap.state !== "hidden");
  const showMapping = Boolean(sociomapping && sociomapping.state !== "hidden");
  const showAnalysis = run.steps.some((step) => step.kind === "research_analysis");
  const chips: [string, string][] = [
    ["res-aggregate", t("research.exec.results.aggregate")],
    ...(showMap ? ([["res-sociomap", t("research.exec.results.sociomap")]] as [string, string][]) : []),
    ...(showMapping ? ([["res-sociomapping", t("research.exec.results.sociomapping")]] as [string, string][]) : []),
    ...(showAnalysis ? ([["res-analysis", t("research.exec.results.jumpAnalysis")]] as [string, string][]) : []),
    ["res-report", t("research.exec.results.jumpReport")],
  ];
  return (
    <div className="flex max-w-4xl flex-col gap-4">
      <ResultChips items={chips} />
      {isSynthetic(run) ? <SyntheticBanner /> : null}
      <Card id="res-aggregate" title={t("research.exec.results.aggregate")}>
        {aggregate?.state === "ready" ? <AggregateView artifact={aggregate.value} run={run} /> : null}
        {aggregate?.state === "failed" ? <p role="alert" className="text-sm text-status-fault">{aggregate.message}</p> : null}
        {aggregate?.state === "loading" ? <p className="text-sm text-ink-muted">{t("research.loading")}</p> : null}
      </Card>
      {sociomap && sociomap.state !== "hidden" ? (
        <Card id="res-sociomap" title={t("research.exec.results.sociomap")} tone="notice">
          <p role="note" className="mb-3 text-sm font-semibold">{t("research.exec.results.internal")}</p>
          <p className="mb-3 text-sm text-ink-muted">{t("research.exec.results.mapToolNotInAia")}</p>
          {sociomap.state === "ready" ? <SociomapView artifact={sociomap.value} run={run} /> : null}
          {sociomap.state === "failed" ? <p role="alert" className="text-sm text-status-fault">{sociomap.message}</p> : null}
        </Card>
      ) : null}
      {sociomapping && sociomapping.state !== "hidden" ? (
        <Card id="res-sociomapping" title={t("research.exec.results.sociomapping")} tone="notice">
          {sociomapping.state === "ready" ? (
            <SociomappingView artifact={sociomapping.value} run={run} studyId={frame.studyId} canEdit={frame.canEdit} />
          ) : null}
          {sociomapping.state === "loading" ? <p className="text-sm text-ink-muted">{t("research.loading")}</p> : null}
          {sociomapping.state === "failed" ? <p role="alert" className="text-sm text-status-fault">{sociomapping.message}</p> : null}
        </Card>
      ) : null}
      {showAnalysis ? <div id="res-analysis" className="scroll-mt-60"><AnalysisResults key={run.run_id} run={run} /></div> : null}
      <div id="res-report" className="scroll-mt-60">{report}</div>
    </div>
  );
}

function InternalReport({ run }: { run: ResearchRun }) {
  const frame = useFrame();
  const [loaded, setLoaded] = useState<Loaded<ResearchReport>>({ state: "loading" });
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const step = stepOf(run, "report");
  useEffect(() => {
    let live = true;
    setLoaded({ state: "loading" });
    research.report(frame.studyId, run.run_id).then(
      (value) => live && setLoaded({ state: "ready", value }),
      (error: unknown) => live && setLoaded(
        error instanceof ApiError && error.status === 403
          ? { state: "hidden" } : { state: "failed", message: message(error) }
      ),
    );
    return () => { live = false; };
  }, [frame.studyId, run.run_id, step?.status, step?.artifact_id]);

  if (loaded.state === "hidden") return null;
  const status = loaded.state === "ready" ? loaded.value : null;
  const download = async () => {
    setDownloading(true);
    setDownloadError(null);
    try {
      saveBlob(await research.downloadReport(frame.studyId, run.run_id), `AIA-${frame.studyId}-internal-draft.docx`);
    } catch (error) {
      setDownloadError(message(error));
    } finally {
      setDownloading(false);
    }
  };
  return (
    <Card title={t("research.exec.results.report")} tone="notice">
      <p role="note" className="mb-2 text-sm font-semibold">{t("research.exec.results.reportInternal")}</p>
      {loaded.state === "loading" ? <p className="text-sm text-ink-muted">{t("research.loading")}</p> : null}
      {loaded.state === "failed" ? <p role="alert" className="text-sm text-status-fault">{loaded.message}</p> : null}
      {status?.state === "READY" ? (
        <>
          <p className="text-sm">{status.review_state === "APPROVED_INTERNAL"
            ? t("research.exec.results.reportApprovedInternal")
            : t("research.exec.results.reportDraft")}</p>
          {status.synthetic ? <p className="mt-2 text-sm text-status-fault">{t("research.exec.results.reportSynthetic")}</p> : null}
          <p className="mt-2 text-xs text-ink-muted">{tv("research.exec.results.reportProvenance", {
            id: status.artifact_id ?? "—", sha: status.sha256?.slice(0, 12) ?? "—", run: run.run_id,
          })}</p>
          <Button onClick={download} disabled={downloading || !frame.canEdit}>
            {downloading ? t("research.exec.results.reportDownloading") : t("research.exec.results.reportDownload")}
          </Button>
        </>
      ) : null}
      {status && status.state !== "READY" ? (
        <p className="text-sm text-ink-muted">
          {status.state === "FAILED"
            ? status.reason === "report_inputs_refused"
              ? t("research.exec.results.reportInputsRefused")
              : t("research.exec.results.reportFailed")
            : t("research.exec.results.reportWaiting")}
        </p>
      ) : null}
      {downloadError ? <p role="alert" className="mt-2 text-sm text-status-fault">{downloadError}</p> : null}
    </Card>
  );
}

function AnalysisResults({ run }: { run: ResearchRun }) {
  const frame = useFrame();
  const [loaded, setLoaded] = useState<Loaded<ResearchAnalysis>>({ state: "loading" });
  const states = run.steps.filter((step) => step.kind === "research_analysis")
    .map((step) => `${step.node_key}:${step.status}:${step.artifact_id ?? ""}`).join("|");
  useEffect(() => {
    let live = true;
    research.analysis(frame.studyId, run.run_id).then(
      (value) => live && setLoaded({ state: "ready", value }),
      (error: unknown) => live && setLoaded(
        error instanceof ApiError && error.status === 403
          ? { state: "hidden" } : { state: "failed", message: message(error) }
      ),
    );
    return () => { live = false; };
  }, [frame.studyId, run.run_id, states]);
  if (loaded.state === "hidden") return null;
  return (
    <Card title={t("research.exec.results.analysis")} tone="notice">
      <p role="note" className="mb-3 text-sm font-semibold">
        {loaded.state === "ready" && loaded.value.synthetic
          ? t("research.exec.results.analysisSynthetic")
          : t("research.exec.results.analysisInternal")}
      </p>
      {loaded.state === "failed" ? <p role="alert">{loaded.message}</p> : null}
      {loaded.state === "loading" ? <p>{t("research.loading")}</p> : null}
      {loaded.state === "ready" ? (
        <div className="flex flex-col gap-4">
          {ANALYSIS_ORDER.map((id) => {
            const outcome = loaded.value.modules[id];
            const pending = loaded.value.pending[id];
            return (
              <section key={id} className="border-t border-border pt-3">
                <h3 className="font-semibold">{stepLabel(`analysis_${id}`)}</h3>
                {pending ? <p className="text-sm text-ink-muted">{t("research.exec.results.analysisPending")}: {pending}</p> : null}
                {outcome?.outcome === "BLOCKED" ? (
                  <ul className="text-sm text-status-you-ink">{outcome.violations.map((v, index) => <li key={index}>{v.code}: {v.detail}</li>)}</ul>
                ) : null}
                {outcome?.summary ? <p className="mt-2 whitespace-pre-wrap text-sm">{outcome.summary}</p> : null}
                {outcome?.research_question_answers.map((answer, index) => (
                  <p key={index} className="mt-2 text-sm"><strong>{answer.question}</strong> {answer.answer}</p>
                ))}
                {outcome?.key_findings.map((finding, index) => (
                  <p key={index} className="mt-2 text-sm">{finding.text}</p>
                ))}
                {outcome?.claims.length ? <p className="mt-2 text-xs text-ink-muted">{t("research.exec.results.analysisEvidence")}: {outcome.claims.map((claim) => `${claim.claim_id} → ${claim.evidence_ref}`).join(", ")}</p> : null}
              </section>
            );
          })}
        </div>
      ) : null}
    </Card>
  );
}

type AggregatePayload = {
  aggregate: {
    questions: Record<string, Parameters<typeof resultTable>[1]>;
    batteries: Record<string, { title: string; objects: Record<string, Parameters<typeof resultTable>[1] & { label: string }> }>;
  };
};

function AggregateView({ artifact, run }: { artifact: Artifact; run: ResearchRun }) {
  const payload = artifact.payload as AggregatePayload | null;
  if (!payload) return null;
  const { questions, batteries } = payload.aggregate;
  return (
    <div className="flex flex-col gap-5">
      {Object.entries(questions).map(([id, result]) => (
        <section key={id} aria-label={id}>
          <h3 className="text-sm font-semibold">{id}</h3>
          <Table table={resultTable(id, result)} />
        </section>
      ))}
      {Object.entries(batteries).map(([id, battery]) => (
        <section key={id} aria-label={battery.title}>
          <h3 className="text-sm font-semibold">{battery.title}</h3>
          {Object.entries(battery.objects).map(([oid, result]) => (
            <div key={oid} className="mt-2">
              <p className="text-sm">{result.label}</p>
              <Table table={resultTable(oid, result)} />
            </div>
          ))}
        </section>
      ))}
      <Provenance artifact={artifact} run={run} />
    </div>
  );
}

function SociomapView({ artifact, run }: { artifact: Artifact; run: ResearchRun }) {
  const payload = artifact.payload as {
    sociomap: { data_origin?: string | null; batteries: (Parameters<typeof sociomapObjects>[0] & BatteryWithMaps)[] };
  } | null;
  if (!payload) return null;
  return (
    <div className="flex flex-col gap-4">
      {payload.sociomap.batteries.map((b) => {
        const objects = sociomapObjects(b);
        const objectMap = readObjectMap(b);
        const table = (
            <table className="mt-1 w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-ink-muted">
                  <th className="py-1 font-medium">{t("research.exec.results.object")}</th>
                  <th className="py-1 font-medium">{t("research.exec.results.score")}</th>
                  <th className="py-1 font-medium">{t("research.exec.results.position")}</th>
                </tr>
              </thead>
              <tbody>
                {objects.map((o) => (
                  <tr key={o.id} className="border-t border-border">
                    <td className="py-1 pr-3">{o.label}</td>
                    <td className="py-1 pr-3 tabular-nums">{o.score === null ? "—" : o.score.toLocaleString("cs-CZ", { maximumFractionDigits: 2 })}</td>
                    <td className="py-1 tabular-nums text-ink-muted">
                      {o.x.toLocaleString("cs-CZ", { maximumFractionDigits: 1 })}, {o.y.toLocaleString("cs-CZ", { maximumFractionDigits: 1 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
        );
        return (
          <section key={b.battery_id} aria-label={b.title} className="flex flex-col gap-2">
            {objectMap.ok || objectMap.reason === "contract" ? (
              <>
                <ObjectMapView battery={b} dataOrigin={payload.sociomap.data_origin ?? null} />
                <details className="text-sm">
                  <summary className="cursor-pointer font-semibold">{t("research.exec.objectMap.comparison")}</summary>
                  {table}
                </details>
              </>
            ) : (
              <>
                <h3 className="text-sm font-semibold">{b.title}</h3>
                {table}
              </>
            )}
          </section>
        );
      })}
      <Provenance artifact={artifact} run={run} />
    </div>
  );
}
