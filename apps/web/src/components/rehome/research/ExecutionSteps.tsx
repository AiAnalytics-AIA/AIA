"use client";

// Run, Progress and Results (ADR 0016): the research lifecycle in AIA, against
// AIA's study-scoped execution API. The browser submits the design it holds as a
// Design Revision, reads what AIA's checks say about it, starts one run over that
// exact revision, and then only reads: state, steps, and the artifacts the run
// produced. Nothing here decides a number; everything here says where a number
// came from -- and when it came from the fictional dataset, that it is fiction.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  ApiError,
  api,
  type Artifact,
  type ResearchAnalysis,
  type ResearchReport,
  type QuestionOutlook,
  type Readiness,
  type ResearchTrace,
  type DeepResearchBundle,
  type DeepResearchRun,
  type DesignProposal,
  deepResearch,
  type ResearchRun,
  type ResearchRunSummary,
  type ResearchStep,
  type PopulationVersion,
  type Study,
  population,
  research,
} from "@/lib/api";
import { clientChildren, outcomeValue, targetVerdict } from "@/lib/population";
import { latestDesignRun, questionEvidence } from "@/lib/design-evidence";
import { researchStepOrb } from "@/lib/activity-orb";
import { activityOf } from "@/lib/step-activity";
import { type BatteryWithMaps, mapApproval, readObjectMap, type RecordedMethod, type RegisterEntry } from "@/lib/object-map-view";
import {
  STEP_ORDER,
  ANALYSIS_ORDER,
  hasUnknownOrigin,
  isModelled,
  isSynthetic,
  mayRetryAnalysis,
  outlookByVerdict,
  outlookCounts,
  outlookFixStep,
  outlookReason,
  parkedForRuntime,
  traceMeasures,
  reportHolds,
  resultOriginKind,
  stepOriginKind,
  type OriginKind,
  waitingDetail,
  phaseLabel,
  phaseTone,
  aggregateDeviation,
  resultTable,
  shouldPoll,
  sociomapObjects,
  stepLabel,
  stepOf,
  populationNote,
  stepStatusLabel,
  stepTone,
  supportNote,
  topBoxWidth,
  type AggregateDeviation,
  type ResultTable,
  verdictTone,
} from "@/lib/research-execution";
import { CONFLICT_MESSAGE } from "@/research/store";
import { projectVariants, selectedVariant } from "@/research/plan";
import { withApproval } from "@/research/persona";
import type { StepKey } from "@/research/steps";
import { ActionDock, Switch } from "../step";
import { AiButton, Button, Chip, Field, TextArea, TextInput } from "../ui";
import { useFrame } from "./frame-hook";
import { InspectorSlot } from "./Inspector";
import { ResearchContext, useResearch } from "./context";
import { SociomappingView } from "./SociomappingView";
import { StepActivityPanel } from "./StepActivityPanel";
import { useStepActivity } from "./useStepActivity";
import { ObjectMapView } from "./ObjectMapView";
import { InterpretationResearch } from "./InterpretationResearch";
import { ResultsWorkspace } from "./ResultsWorkspace";
import { CompleteReport } from "./CompleteReport";

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

/** What a report and an analysis say about their data, by origin kind (ADR 0024 §7). */
const REPORT_ORIGIN: Record<OriginKind, string> = {
  SIMULATED: "research.exec.results.reportSynthetic",
  MODELLED: "research.exec.results.reportModelled",
  UNKNOWN: "research.exec.results.reportUnknownOrigin",
};
const ANALYSIS_ORIGIN: Record<OriginKind, string> = {
  SIMULATED: "research.exec.results.analysisSynthetic",
  MODELLED: "research.exec.results.analysisModelled",
  UNKNOWN: "research.exec.results.analysisUnknownOrigin",
};

function SyntheticBanner() {
  return (
    <p role="note" data-origin="synthetic" className="rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm font-semibold text-status-fault">
      {t("research.exec.syntheticNotice")}
    </p>
  );
}

/** Every origin kind a run's data is, each said once: fictional, modelled, or unknown -- never fieldwork. */
function OriginBanners({ run }: { run: ResearchRun }) {
  return (
    <>
      {isSynthetic(run) ? <SyntheticBanner /> : null}
      {isModelled(run) ? (
        <p role="note" data-origin="modelled" className="rounded-sm border border-ink/30 bg-status-world-wash p-3 text-sm font-semibold text-ink">
          {t("research.exec.modelledNotice")}
        </p>
      ) : null}
      {hasUnknownOrigin(run) ? (
        <p role="note" data-origin="unknown" className="rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm font-semibold text-status-fault">
          {t("research.exec.unknownOriginNotice")}
        </p>
      ) : null}
    </>
  );
}

// The population a run recorded, and that fieldwork did not read it (population-operations P3).
function PopulationNote({ run }: { run: ResearchRun }) {
  const note = populationNote(run);
  return note ? (
    <p role="note" data-population={run.population?.version_label} className="text-sm text-ink-muted">
      {note}
    </p>
  ) : null;
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

/** Where a failing readiness check is fixed: the sample (and the support it gives) on Dimenze, the audience on Audience, the rest on Dotazník. */
export function fixStep(checkId: string): StepKey {
  if (/sample|^n$|^support_forecast$/.test(checkId)) return "persona";
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

/** "Výzkumné otázky a jejich měření": each research question of the plan, the questions that
 * measure it and what the run will make of them (plan run-recovery-and-truth 3b). */
type DesignEvidence = { run: DeepResearchRun; proposal: DesignProposal; bundle: DeepResearchBundle };

/** What the study's Design Research run found for one research question (3d): its accepted
 * findings with their sources, a gap, or that it never studied it; every rejection by reason. */
function DesignEvidenceNote({ rq, design }: { rq: string; design: DesignEvidence }) {
  const found = questionEvidence(rq, design.proposal, design.bundle);
  if (!found.studied) return <p className="mt-1 text-[13px] text-ink-muted">{t("research.exec.trace.evidence.notStudied")}</p>;
  return (
    <div className="mt-1 rounded-control border border-border bg-surface-sunken px-2.5 py-1.5 text-[13px]">
      {found.findings.length ? (
        <>
          <p className="font-medium">{tv("research.exec.trace.evidence.found", { count: found.findings.length })}</p>
          <ul className="mt-1 flex flex-col gap-1">
            {found.findings.slice(0, 3).map((f) => (
              <li key={f.evidence_id}>
                <span>{f.claim}</span>
                <span className="block text-ink-muted">„{f.quote}“ · {f.source_title || f.source}</span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p>{t("research.exec.trace.evidence.gap")}</p>
      )}
      {found.rejected.length ? (
        <p className="mt-1 text-ink-muted">
          {tv("research.exec.trace.evidence.rejected", { list: found.rejected.map((r) => `${r.count}× ${quarantineWords(r.reason)}`).join("; ") })}
        </p>
      ) : null}
    </div>
  );
}

/** A quarantine reason in words; one this client does not know is named, never hidden. */
function quarantineWords(code: string): string {
  const key = `research.exec.trace.quarantine.${code}`;
  const words = t(key);
  return words === key ? code : words;
}

function ResearchTraceCard({ trace, outlook, design }: { trace: ResearchTrace; outlook: readonly QuestionOutlook[]; design: DesignEvidence | null }) {
  const { stepHref } = useResearch();
  // Stale links stay visible even when the plan states no research question any more.
  if (!trace.questions.length && !trace.dangling.length) return null;
  return (
    <Card title={t("research.exec.trace.title")} region>
      <p className="text-[13px] text-ink-muted">{t("research.exec.trace.help")}</p>
      {design ? <p className="mt-1 text-[13px] text-ink-muted">{t("research.exec.trace.evidence.source")}</p> : null}
      <ol className="mt-3 flex flex-col gap-3">
        {trace.questions.map((q, i) => {
          const measures = traceMeasures(q, outlook);
          return (
            <li key={`${i}-${q.text}`} className="flex items-start gap-2 text-sm">
              <Chip tone={verdictTone(q.verdict)}>{t(`research.exec.outlook.verdict.${q.verdict}`)}</Chip>
              <div className="min-w-0 flex-1">
                <p className="font-medium">{q.text}</p>
                {q.comparison ? (
                  <p className="text-[13px] text-ink-muted">{tv("research.exec.trace.comparison", { kind: t(`research.questionnaire.comparisons.kind.${q.comparison}`) })}</p>
                ) : null}
                {q.reasons.map((r) => (
                  <p key={r} className="text-[13px] text-ink-muted">{t(`research.exec.trace.reason.${r}`)}</p>
                ))}
                {design ? <DesignEvidenceNote rq={q.text} design={design} /> : null}
                {measures.length ? (
                  <ul className="mt-1 flex flex-col gap-1">
                    {measures.map((m) => (
                      <li key={m.key} className="flex items-start gap-2 text-[13px]">
                        <Chip tone={verdictTone(m.verdict)}>{t(`research.exec.outlook.verdict.${m.verdict}`)}</Chip>
                        <span className="min-w-0 flex-1">{m.text}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              {q.verdict !== "ANSWERABLE" ? (
                <Link href={stepHref("questionnaire")} className="whitespace-nowrap text-xs text-signal no-underline hover:underline">
                  {t("research.exec.fix")}
                </Link>
              ) : null}
            </li>
          );
        })}
      </ol>
      {trace.dangling.length ? (
        <p className="mt-3 text-[13px] text-status-you-ink">
          {tv("research.exec.trace.dangling", { list: [...new Set(trace.dangling.map((d) => d.research_question))].join("; ") })}
        </p>
      ) : null}
    </Card>
  );
}

/** "Na co běh odpoví": every item a respondent will answer, worst first, as they read it, with
 * the reasons in words; what the run will answer folds away (plan run-recovery-and-truth 2b). */
function QuestionOutlookCard({ items }: { items: readonly QuestionOutlook[] }) {
  const { stepHref } = useResearch();
  if (!items.length) return null;
  const counts = outlookCounts(items);
  const sorted = outlookByVerdict(items);
  const flagged = sorted.filter((i) => i.verdict !== "ANSWERABLE");
  const answerable = sorted.filter((i) => i.verdict === "ANSWERABLE");
  const row = (item: QuestionOutlook) => {
    const fix = outlookFixStep(item.reasons);
    return (
      <li key={item.question_id} className="flex items-start gap-2 text-sm">
        <Chip tone={verdictTone(item.verdict)}>{t(`research.exec.outlook.verdict.${item.verdict}`)}</Chip>
        <div className="min-w-0 flex-1">
          <p>{item.text}</p>
          {item.reasons.length ? (
            <ul className="mt-0.5 text-[13px] text-ink-muted">
              {item.reasons.map((r) => (
                <li key={r}>{outlookReason(r)}</li>
              ))}
            </ul>
          ) : null}
        </div>
        {fix && item.verdict !== "ANSWERABLE" ? (
          <Link href={stepHref(fix)} className="whitespace-nowrap text-xs text-signal no-underline hover:underline">
            {t("research.exec.fix")}
          </Link>
        ) : null}
      </li>
    );
  };
  return (
    <Card title={t("research.exec.outlook.title")} region>
      <p className="text-[13px] text-ink-muted">{t("research.exec.outlook.help")}</p>
      <p className="mt-2 text-sm font-medium">{tv("research.exec.outlook.summary", counts)}</p>
      {flagged.length ? (
        <ul className="mt-3 flex flex-col gap-2" aria-label={t("research.exec.outlook.title")}>
          {flagged.map(row)}
        </ul>
      ) : null}
      {answerable.length ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm">{tv("research.exec.outlook.answerable", { count: answerable.length })}</summary>
          <ul className="mt-2 flex flex-col gap-2">{answerable.map(row)}</ul>
        </details>
      ) : null}
    </Card>
  );
}

/** Failures first, then warnings: what stops the run is read before what passed. */
const CHECK_ORDER: Record<string, number> = { FAIL: 0, WARN: 1, PASS: 2 };

/** The most runs `GET …/deep-research/runs` lists (its `limit` query, le=100). */
const DEEP_RESEARCH_RUNS_MAX = 100;

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
  // The newest finished Design Research run and what it found (3d); its routes need EDIT_STUDY.
  const [design, setDesign] = useState<DesignEvidence | null>(null);
  useEffect(() => {
    let live = true;
    setDesign(null);
    if (!frame.canEdit) return;
    (async () => {
      // The server's widest page: newer interpretation or unfinished runs must not push the
      // finished design run out of the default 20 (review, Codex on #427).
      const run = latestDesignRun(await deepResearch.runs(frame.studyId, DEEP_RESEARCH_RUNS_MAX));
      if (!run) return;
      const [proposal, bundle] = await Promise.all([deepResearch.designProposal(frame.studyId, run.run_id), deepResearch.bundle(frame.studyId, run.run_id)]);
      if (live) setDesign({ run, proposal, bundle });
    })().catch(() => {
      // Nothing to show is said by the card's own absence: the trace stands without it.
    });
    return () => {
      live = false;
    };
  }, [frame.studyId, frame.canEdit]);
  // The client's materialized children a run may be started over (P4d4c); none read is LIVE.
  const [children, setChildren] = useState<PopulationVersion[]>([]);
  const [childId, setChildId] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    population.registry().then(
      (r) => live && setChildren(clientChildren(r, frame.clientId)),
      () => live && setChildren([]),
    );
    return () => {
      live = false;
    };
  }, [frame.clientId]);

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
        await research.start(frame.studyId, readiness.design_revision_id, yes, childId ?? undefined);
      } catch (e) {
        // The limit or the ceiling changed since the page read them: ask with the server's figure.
        const asked = confirmationAsked(e);
        if (!asked || yes !== undefined || !(await ask(asked.ceiling, asked.limit))) throw e;
        await research.start(frame.studyId, readiness.design_revision_id, asked.ceiling, childId ?? undefined);
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
          {/* What stops the run first, then what runs (research-lane-redesign). */}
          <Card title={prepared.readiness.ready ? t("research.exec.ready") : t("research.exec.notReady")}>
            <ul className="flex flex-col gap-2" aria-label={t("research.exec.steps.preflight")}>
              {[...prepared.readiness.checks].sort((a, b) => (CHECK_ORDER[a.status] ?? 3) - (CHECK_ORDER[b.status] ?? 3)).map((c) => (
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
          {prepared.readiness.research_trace ? <ResearchTraceCard trace={prepared.readiness.research_trace} outlook={prepared.readiness.question_outlook ?? []} design={design} /> : null}
          <QuestionOutlookCard items={prepared.readiness.question_outlook ?? []} />
          <Receipt revision={prepared.revision} readiness={prepared.readiness} />
          <CostCard readiness={prepared.readiness} canEdit={frame.canEdit} onLimitSaved={rereadReadiness} />
          {children.length ? <PopulationChoice choices={children} value={childId} onChange={setChildId} disabled={!frame.canEdit || starting} /> : null}
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

// Which population the run is computed over (P4d4c): LIVE, or one of this client's materialized
// children with its target beside what it reached. Shown only when the client has a child.
function PopulationChoice({
  choices,
  value,
  onChange,
  disabled,
}: {
  choices: PopulationVersion[];
  value: string | null;
  onChange: (id: string | null) => void;
  disabled: boolean;
}) {
  const P = "research.exec.population";
  return (
    <Card title={t(`${P}.title`)}>
      <fieldset className="flex flex-col gap-2 text-sm" disabled={disabled}>
        <legend className="mb-1 text-ink-muted">{t(`${P}.text`)}</legend>
        <label className="flex items-start gap-2">
          <input type="radio" name="run-population" checked={value === null} onChange={() => onChange(null)} />
          <span>{t(`${P}.live`)}</span>
        </label>
        {choices.map((v) => {
          const m = v.materialized ?? null;
          const verdict = targetVerdict(m);
          return (
            <label key={v.version_id} className="flex items-start gap-2">
              <input type="radio" name="run-population" checked={value === v.version_id} onChange={() => onChange(v.version_id)} />
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{m?.dimension_id ?? v.label}</span>
                {m ? <span className="text-ink-muted">{tv(`${P}.outcome`, { target: outcomeValue(m.kind, m.target), achieved: outcomeValue(m.kind, m.achieved) })}</span> : null}
                <Chip tone={verdict === "met" ? "done" : "fault"}>{t(`aia.intelligence.population.children.verdict.${verdict}`)}</Chip>
              </span>
            </label>
          );
        })}
      </fieldset>
      <p className="mt-2 text-xs text-ink-muted">{t(`${P}.note`)}</p>
    </Card>
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
              {isModelled(r) ? <Chip tone="neutral">{t("research.exec.modelled")}</Chip> : null}
              {hasUnknownOrigin(r) ? <Chip tone="fault">{t("research.exec.unknownOrigin")}</Chip> : null}
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

/**
 * The run the page is about: `?run=` if given, else the run an action last answered with, else the
 * newest; kept fresh while it can change.
 *
 * The third value is how an action hands the page the run it answered with. A retry answers with a
 * new run: the page follows it -- `?run=` names it, so a reload stays on it -- and reads it again
 * at once, which restarts the poll the old, finished run had stopped. Setting it without reading
 * again left the new run's first step "running" on screen for good while the worker went on.
 */
function useRun(): [ResearchRun | null | undefined, () => void, (r: ResearchRun) => void, string | null] {
  const frame = useFrame();
  const [run, setRun] = useState<ResearchRun | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const followed = useRef<string | null>(null);
  const follow = useCallback((next: ResearchRun) => {
    setRun(next);
    followed.current = next.run_id;
    const params = new URLSearchParams(window.location.search);
    if (params.has("run") && params.get("run") !== next.run_id) {
      params.set("run", next.run_id);
      window.history.replaceState(window.history.state, "", `${window.location.pathname}?${params}${window.location.hash}`);
    }
    setVersion((v) => v + 1);
  }, []);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const wanted = runFromQuery() ?? followed.current;
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
        // 404 is "no run here": a retry that lands on it clears the earlier failure.
        if (e instanceof ApiError && e.status === 404) {
          setError(null);
          return setRun(null);
        }
        setError(message(e));
      }
    };
    void read();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [frame.studyId, version]);
  return [run, () => setVersion((v) => v + 1), follow, error];
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

/**
 * The modules of a finished run a person may ask again (`GET …/analysis/retryable`), or `null` while
 * there is nothing to ask about. Read once per finished run, not on every poll.
 */
function useRetryableModules(run: ResearchRun | null | undefined): string[] | null {
  const frame = useFrame();
  const runId = run?.run_id ?? null;
  const possible = !!run && mayRetryAnalysis(run);
  const [modules, setModules] = useState<{ runId: string; list: string[] } | null>(null);
  useEffect(() => {
    if (!possible || !runId) return;
    let live = true;
    research
      .retryableModules(frame.studyId, runId)
      .then((list) => live && setModules({ runId, list }))
      .catch(() => live && setModules({ runId, list: [] }));
    return () => {
      live = false;
    };
  }, [frame.studyId, runId, possible]);
  return possible && modules && modules.runId === runId && modules.list.length ? modules.list : null;
}

/** A finished run whose analysis a model could not complete: the data stands, the modules are asked again. */
function AnalysisRepair({ run, modules, act, busy }: { run: ResearchRun; modules: string[]; act: (fn: () => Promise<ResearchRun>) => Promise<void>; busy: boolean }) {
  const { confirm } = useResearch();
  const frame = useFrame();
  return (
    <Card title={t("research.exec.analysisRetry.title")} tone="notice" region>
      <p className="text-sm">{tv("research.exec.analysisRetry.body", { n: modules.length })}</p>
      <p className="mt-1 text-sm">{tv("research.exec.analysisRetry.modules", { list: modules.map((m) => stepLabel(`analysis_${m}`)).join(", ") })}</p>
      <p className="mt-1 text-xs text-ink-muted">{t("research.exec.analysisRetry.how")}</p>
      {frame.canEdit ? (
        <Button
          className="mt-3"
          variant="primary"
          disabled={busy}
          onClick={() =>
            act(async () => {
              try {
                return await research.retryAnalysis(frame.studyId, run.run_id);
              } catch (e) {
                // The retry asks a model again, so the study's limit asks again over what it may cost.
                const asked = confirmationAsked(e);
                if (!asked) throw e;
                const yes = await confirm(tv("research.exec.cost.confirm", { ceiling: asked.ceiling.toFixed(2), limit: asked.limit.toFixed(2) }));
                if (!yes) return run;
                return research.retryAnalysis(frame.studyId, run.run_id, asked.ceiling);
              }
            })
          }
        >
          {t("research.exec.analysisRetry.action")}
        </Button>
      ) : null}
    </Card>
  );
}

/** The run's state and what a person can do with it, in the inspector beside its steps. */
function ProgressActions({ run, act, busy, refresh, actionError, repairable }: {
  run: ResearchRun; act: (fn: () => Promise<ResearchRun>) => Promise<void>; busy: boolean; refresh: () => void; actionError: string | null;
  /** Modules an analysis retry would ask again: the whole-run retry then steps back. */
  repairable: string[] | null;
}) {
  const { confirm, stepHref } = useResearch();
  const frame = useFrame();
  return (
    <section aria-labelledby="run-actions" className="flex flex-col gap-3 rounded-card border border-border bg-surface-raised p-3.5">
      <h2 id="run-actions" className="text-sm font-semibold">{tv("research.exec.revision", { revision: run.design_revision })}</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[13px]">
        <dt className="text-ink-muted">{t("research.exec.runCost")}</dt><dd className="font-mono">{run.actual_cost_usd == null ? t("research.exec.runCostUnknown") : `${run.actual_cost_usd.toFixed(2)} USD`}</dd>
      </dl>
      <div className="flex flex-wrap items-center gap-2">
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
            variant={repairable ? undefined : "primary"}
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
            {repairable ? t("research.exec.retryWhole") : t("research.exec.retry")}
          </Button>
        ) : null}
        <Button variant="quiet" onClick={refresh}>{t("research.exec.refresh")}</Button>
      </div>
      {actionError ? <p role="alert" className="text-sm text-status-fault">{actionError}</p> : null}
    </section>
  );
}

export function ProgressStep() {
  const frame = useFrame();
  const [run, refresh, setRun, error] = useRun();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const repairable = useRetryableModules(run);
  // The run's feed, read live while one of its steps runs (lib/step-activity.ts).
  const running = !!run && !run.is_terminal && run.steps.some((s) => s.status === "RUNNING");
  const activity = useStepActivity(run?.run_id ?? null, (since) => research.events(frame.studyId, run!.run_id, since), running);

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

  if (run === undefined && error) return <Card><p role="alert" className="text-sm text-status-fault">{error}</p><Button className="mt-3" onClick={refresh}>{t("research.retry")}</Button></Card>;
  if (run === undefined) return <p className="text-sm text-ink-muted">{t("research.loading")}</p>;
  if (run === null) return <Card><p className="text-sm">{t("research.exec.noRuns")}</p></Card>;
  const parked = parkedForRuntime(run);
  const failed = run.steps.find((s) => s.status === "FAILED");
  const listed = [...STEP_ORDER, ...ANALYSIS_ORDER.map((id) => `analysis_${id}`), "report"].map((key) => stepOf(run, key)).filter((s): s is ResearchStep => !!s);
  const finished = listed.filter((s) => s.status === "SUCCEEDED" || s.status === "SKIPPED").length;
  return (
    <div className="flex max-w-[82.5rem] flex-col gap-4">
      <InspectorSlot>
        <ProgressActions run={run} act={act} busy={busy} refresh={refresh} actionError={actionError} repairable={repairable} />
      </InspectorSlot>
      <OriginBanners run={run} />
      <PopulationNote run={run} />
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <Chip tone={phaseTone(run.phase)}>{phaseLabel(run.phase)}</Chip>
          <span className="text-sm">{tv("research.exec.revision", { revision: run.design_revision })}</span>
          <span className="text-sm text-ink-muted">{tv("research.exec.startedAt", { when: when(run.created_at) })}</span>
          {run.finished_at ? <span className="text-sm text-ink-muted">{tv("research.exec.finishedAt", { when: when(run.finished_at) })}</span> : null}
          {run.retry_of ? <span className="text-xs text-ink-muted">{tv("research.exec.retryOf", { run: run.retry_of })}</span> : null}
        </div>
        {listed.length ? (
          <div className="mt-3 flex items-center gap-3">
            <span aria-hidden="true" className="h-1.5 max-w-md flex-1 overflow-hidden rounded-sm bg-surface-sunken">
              <i className="block h-1.5 bg-status-running" style={{ width: `${Math.round((finished / listed.length) * 100)}%` }} />
            </span>
            <span className="font-mono text-xs text-ink-muted">{tv("research.exec.stepsFinished", { done: finished, total: listed.length })}</span>
          </div>
        ) : null}
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
      {repairable ? <AnalysisRepair run={run} modules={repairable} act={act} busy={busy} /> : null}
      <Card title={t("aia.stages.progress")}>
        <ol className="flex flex-col gap-3" aria-label={t("aia.stages.progress")}>
          {listed.map((s) => (
            <li key={s.node_key} data-step={s.node_key} data-status={s.status} className="flex flex-col gap-0.5 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone={stepTone(s)}>{stepStatusLabel(s)}</Chip>
                <span className="font-medium">{stepLabel(s.node_key)}</span>
                {stepOriginKind(s) ? (
                  <span title={s.data_origin ?? undefined} data-origin-kind={stepOriginKind(s)}>
                    <Chip tone={stepOriginKind(s) === "MODELLED" ? "neutral" : "fault"}>{t(`research.exec.originKind.${stepOriginKind(s)}`)}</Chip>
                  </span>
                ) : null}
              </div>
              <span className="text-xs text-ink-muted">
                {s.started_at ? tv("research.exec.startedAt", { when: when(s.started_at) }) : null}
                {s.finished_at ? ` · ${tv("research.exec.finishedAt", { when: when(s.finished_at) })}` : null}
                {s.attempts_recorded ? ` · ${tv("research.exec.attempts", { n: s.attempts_recorded, max: s.max_attempts })}` : null}
              </span>
              {waitingDetail(s) ? <span className="text-xs text-ink">{waitingDetail(s)}</span> : null}
              <StepActivityPanel orb={researchStepOrb(run, s)} activity={activityOf(activity, s.step_id)} startedAt={s.started_at} label={stepLabel(s.node_key)} />
              {frame.canEdit && s.status === "AWAITING_BUDGET" && !run.is_terminal ? (
                <BudgetLift run={run} step={s} act={act} busy={busy} />
              ) : null}
            </li>
          ))}
        </ol>
      </Card>
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

function Table({ table, showSupportNote = true }: { table: ResultTable; showSupportNote?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      {showSupportNote ? <p className="text-xs text-ink-muted">{supportNote(table)}</p> : null}
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

/** Separate views of the artifacts belonging to the selected frozen run. */
export function ResultsStep() {
  const [run, refresh, , error] = useRun();
  const frame = useFrame();
  if (error) return <Card><p role="alert" className="text-sm text-status-fault">{error}</p><Button className="mt-3" onClick={refresh}>{t("research.retry")}</Button></Card>;
  if (run === undefined) return <p className="text-sm text-ink-muted">{t("research.loading")}</p>;
  return <RunResults key={run?.run_id ?? "none"} run={run} progressHref={run ? `${frame.stepHref("progress")}?run=${encodeURIComponent(run.run_id)}` : null} />;
}

/**
 * One run's results, every label with them: the Results stage's body for the run it is given.
 * Read-only where the frame says so (`canEdit: false`): no download, and no Interpretation
 * Research, which starts work.
 */
export function RunResults({ run, progressHref }: { run: ResearchRun | null; progressHref: string | null }) {
  const frame = useFrame();
  const session = useContext(ResearchContext);
  const assistance = session?.askAssistance;
  const specification = useArtifact(run && stepOf(run, "aggregate")?.artifact_id ? run : null, "compile");
  const aggregate = useArtifact(run, "aggregate");
  const sociomap = useArtifact(run, "sociomap");
  const sociomapping = useArtifact(run, "sociomapping");
  const report = run?.steps.some((step) => step.kind === "research_report")
    ? <InternalReport key={run.run_id} run={run} progressHref={progressHref} />
    : <p className="text-sm text-ink-muted">{t("research.exec.results.reportNotInAia")}</p>;

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
  const knowledgeContext = <section aria-label="Kontext klienta a literatura" className="rounded-md border border-border bg-surface-raised p-4">
    <h3 className="text-sm font-semibold">Doplňte souvislosti k interpretaci</h3>
    <div className="mt-3 grid gap-4 sm:grid-cols-2"><div><h4 className="text-sm font-semibold">Schválené znalosti klienta</h4><p className="mt-1 text-xs leading-5 text-ink-muted">Podklady dostupné této studii. Otázka neposílá hodnoty výsledků nebo map automaticky a nemění zmrazený běh.</p>{assistance && frame.canEdit ? <Button className="mt-2 !min-h-11 !whitespace-normal" onClick={() => assistance("answer_memory", "Jaké schválené znalosti klienta poskytují kontext k tématu této studie?")}>Zeptat se na klientské znalosti</Button> : null}</div>
    <div><h4 className="text-sm font-semibold">Literární rešerše</h4><p className="mt-1 text-xs leading-5 text-ink-muted">Externí kontext a citované zdroje patří do samostatné rešerše. Vyberte ji v oddílu Rešerše a zpráva; odpověď AI z klientských znalostí ji nenahrazuje.</p></div></div>
  </section>;
  return <ResultsWorkspace run={run} progressHref={progressHref}
    notice={<><OriginBanners run={run} /><PopulationNote run={run} /></>}
    lead={session ? <CompleteReport run={run} /> : null}
    panels={[
      { id: "data", label: "Data", description: "Odpovědi a srovnání hodnocených objektů. U každého výsledku zůstává uvedena podpora dat a nejistota.", content: <>
      <Card id="res-aggregate" title={t("research.exec.results.aggregate")}>
        {aggregate?.state === "ready" ? <AggregateView artifact={aggregate.value} run={run} specification={specification?.state === "ready" ? specification.value : null} /> : null}
        {aggregate?.state === "failed" ? <p role="alert" className="text-sm text-status-fault">{aggregate.message}</p> : null}
        {aggregate?.state === "loading" ? <p className="text-sm text-ink-muted">{t("research.loading")}</p> : null}
      </Card>
      </> },
      ...(showMap || showMapping ? [{ id: "maps", label: "Sociomapy", description: "Prostorové vztahy a 3D pohledy nad uloženými výsledky. Výška, vzdálenost a barva mají odlišný význam; metodická omezení jsou uvedena u každé mapy.", content: <>
      <details className="rounded-md border border-border bg-surface-raised p-3"><summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">Jak používat mapu a AI pomoc</summary><p className="mt-2 text-sm leading-6 text-ink-muted">Začněte legendou a metodikou uloženou u konkrétní mapy. Polohu, výšku a barvu čtěte odděleně. Potlačené a chybějící hodnoty nenahrazujte nulou. AI pomoc pracuje s návrhem a schválenými znalostmi; číselné hodnoty z mapy se do otázky neposílají automaticky.</p></details>
      {sociomap && sociomap.state !== "hidden" ? (
        <Card id="res-sociomap" title={t("research.exec.results.sociomap")} tone="notice">
          <p role="note" className="mb-3 text-sm font-semibold">{t("research.exec.results.mapsByMethod")}</p>
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
      </> }] : []),
      ...(showAnalysis ? [{ id: "analysis", label: "AI analýza", description: "Souhrn, odpovědi na výzkumné otázky a omezení. Interpretace vychází z podkladů tohoto běhu a čeká na posouzení výzkumníkem.", content: <div id="res-analysis"><AnalysisResults key={run.run_id} run={run} /></div> }] : []),
      { id: "report", label: "Rešerše a zpráva", description: "Zkontrolujte připravenost interní zprávy, přijaté externí podklady a omezení rešerše. Dostupnost stažení závisí na úplnosti analýzy.", content: <>
        <div id="res-report">{report}</div>
        {showAnalysis && frame.canEdit ? <InterpretationResearch key={run.run_id} run={run} /> : null}
        <details><summary className="cursor-pointer text-sm font-medium">Klientské znalosti a kontextová AI pomoc</summary><div className="mt-3">{knowledgeContext}</div></details>
      </> },
    ]} />;
}

function InternalReport({ run, progressHref }: { run: ResearchRun; progressHref: string | null }) {
  const frame = useFrame();
  const step = stepOf(run, "report");
  // What the last read answered, and for which state of the report step: a read for an
  // earlier state reads as loading, so nothing is set synchronously in the effect.
  const key = `${frame.studyId}:${run.run_id}:${step?.status ?? ""}:${step?.artifact_id ?? ""}`;
  const [answer, setAnswer] = useState<{ key: string; loaded: Loaded<ResearchReport> } | null>(null);
  const loaded: Loaded<ResearchReport> = answer?.key === key ? answer.loaded : { state: "loading" };
  useEffect(() => {
    let live = true;
    research.report(frame.studyId, run.run_id).then(
      (value) => live && setAnswer({ key, loaded: { state: "ready", value } }),
      (error: unknown) => live && setAnswer({
        key,
        loaded: error instanceof ApiError && error.status === 403
          ? { state: "hidden" } : { state: "failed", message: message(error) },
      }),
    );
    return () => { live = false; };
  }, [frame.studyId, run.run_id, key]);

  if (loaded.state === "hidden") return null;
  const status = loaded.state === "ready" ? loaded.value : null;
  const reportKind = status ? resultOriginKind(status) ?? "UNKNOWN" : "UNKNOWN";
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
          {/* A ready report rests on data, so a kind it does not state is unknown, never neutral. */}
          <p data-origin-kind={reportKind} className={reportKind === "MODELLED" ? "mt-2 text-sm" : "mt-2 text-sm text-status-fault"}>
            {t(REPORT_ORIGIN[reportKind])}
          </p>
          <p className="mt-2 text-xs text-ink-muted">{tv("research.exec.results.reportProvenance", {
            id: status.artifact_id ?? "—", sha: status.sha256?.slice(0, 12) ?? "—", run: run.run_id,
          })}</p>
          {/* Downloading and approving happen in one place: the report card above (CompleteReport). */}
          {frame.canEdit ? <p className="mt-2 text-xs text-ink-muted">{t("research.exec.results.reportActionsAbove")}</p> : null}
          {status.pdf && status.pdf.state !== "READY" ? (
            <p className="mt-1 text-xs text-ink-muted">{t("research.exec.results.reportPdfFailed")}</p>
          ) : null}
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
      {status && status.state !== "READY" ? <ReportHolds run={run} progressHref={progressHref} /> : null}
    </Card>
  );
}

/** Which module or step keeps the report from being ready, and why, with the way to Progress. */
function ReportHolds({ run, progressHref }: { run: ResearchRun; progressHref: string | null }) {
  const holds = reportHolds(run);
  if (!holds.length && !progressHref) return null;
  return (
    <div className="mt-2 text-sm">
      {holds.length ? (
        <>
          <p className="font-medium">{t("research.exec.results.reportHeldBy")}</p>
          <ul className="mt-1 flex flex-col gap-1">
            {holds.map(({ step, detail }) => (
              <li key={step.node_key} data-hold={step.node_key} data-status={step.status}>
                <span className="font-medium">{stepLabel(step.node_key)}</span>
                {" · "}
                {stepStatusLabel(step)}
                {detail ? <span className="text-ink-muted">{`: ${detail}`}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {progressHref ? (
        <a className="mt-2 inline-block underline" href={progressHref}>{t("research.exec.results.reportSeeProgress")}</a>
      ) : null}
    </div>
  );
}

function AnalysisResults({ run }: { run: ResearchRun }) {
  const frame = useFrame();
  const [loaded, setLoaded] = useState<Loaded<ResearchAnalysis>>({ state: "loading" });
  const [selectedModule, setSelectedModule] = useState<(typeof ANALYSIS_ORDER)[number]>("executive");
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
  const analysis = loaded.state === "ready" ? loaded.value : null;
  const complete = ANALYSIS_ORDER.filter((id) => analysis?.modules[id]?.outcome === "COMPLETED").length;
  const blocked = ANALYSIS_ORDER.filter((id) => analysis?.modules[id]?.outcome === "BLOCKED").length;
  const selected = analysis?.modules[selectedModule];
  const selectedStep = run.steps.find((step) => step.node_key === `analysis_${selectedModule}`);
  return (
    <Card title={t("research.exec.results.analysis")} tone="notice">
      <p role="note" className="mb-3 text-sm font-semibold">
        {loaded.state === "ready" && resultOriginKind(loaded.value)
          ? t(ANALYSIS_ORIGIN[resultOriginKind(loaded.value)!])
          : t("research.exec.results.analysisInternal")}
      </p>
      {loaded.state === "failed" ? <p role="alert">{loaded.message}</p> : null}
      {loaded.state === "loading" ? <p>{t("research.loading")}</p> : null}
      {loaded.state === "ready" && loaded.value.aggregation_deviation ? (
        <div className="mb-3"><Deviation deviation={aggregateDeviation({ deviation: loaded.value.aggregation_deviation }) as AggregateDeviation} /></div>
      ) : null}
      {analysis ? (
        <div className="flex flex-col gap-4">
          <section data-analysis-overview className={`rounded-md border p-4 ${blocked ? "border-status-fault/40 bg-status-fault-wash" : "border-border bg-surface-sunken"}`}>
            <p className="text-sm font-semibold">{complete} z {ANALYSIS_ORDER.length} částí analýzy dokončeno{blocked ? ` · k opravě: ${blocked}` : ""}</p>
            <p className="mt-1 text-sm leading-6 text-ink-muted">{blocked
              ? "Některé výstupy neprošly kontrolou. AIA je nepoužije ve zprávě; dokončení pracovního kroku samo o sobě neznamená platný analytický výstup."
              : analysis.complete
                ? "Všechny části jsou uložené. Interpretaci a vhodnost pro zprávu musí posoudit výzkumník."
                : "Zbývající části ještě čekají na dokončení. Zpráva může vzniknout až z úplné analýzy."}</p>
          </section>
          <div className="grid gap-4 lg:grid-cols-[15rem_minmax(0,1fr)]">
            <nav aria-label="Části AI analýzy" className="flex flex-col gap-1">
              {ANALYSIS_ORDER.map((id) => {
                const outcome = analysis.modules[id];
                const label = outcome?.outcome === "COMPLETED" ? "Dokončeno" : outcome?.outcome === "BLOCKED" ? "Vyžaduje opravu" : "Čeká";
                return <button key={id} type="button" onClick={() => setSelectedModule(id)} aria-current={selectedModule === id ? "true" : undefined}
                  className={`flex items-center justify-between gap-2 rounded-control px-3 py-2 text-left text-sm focus-visible:outline-2 focus-visible:outline-focus-ring ${selectedModule === id ? "bg-signal-wash font-semibold text-signal" : "hover:bg-surface-sunken"}`}>
                  <span>{stepLabel(`analysis_${id}`)}</span><span className="shrink-0 text-xs font-normal text-ink-muted">{label}</span>
                </button>;
              })}
            </nav>
            <section aria-label={stepLabel(`analysis_${selectedModule}`)} className="min-w-0 rounded-md border border-border bg-surface-raised p-4">
              <h3 className="text-base font-semibold">{stepLabel(`analysis_${selectedModule}`)}</h3>
              {selected?.outcome === "BLOCKED" ? <>
                <p className="mt-3 text-sm leading-6">Výstup této části neprošel kontrolou, proto se nesmí interpretovat ani použít ve zprávě.</p>
                <details className="mt-3 text-xs text-ink-muted"><summary className="cursor-pointer">Technické důvody odmítnutí</summary>
                  <ul className="mt-2 list-disc space-y-1 pl-5">{selected.violations.map((v, index) => <li key={index}>{v.code}: {v.detail}</li>)}</ul>
                </details>
              </> : selected?.outcome === "COMPLETED" ? <>
                {selected.summary ? <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{selected.summary}</p> : null}
                {selected.research_question_answers.length ? <div className="mt-5 space-y-4"><h4 className="text-sm font-semibold">Odpovědi na výzkumné otázky</h4>
                  {selected.research_question_answers.map((answer, index) => <div key={index}><h5 className="text-sm font-medium">{answer.question}</h5><p className="mt-1 whitespace-pre-wrap text-sm leading-6">{answer.answer}</p></div>)}
                </div> : null}
                {selected.key_findings.length ? <div className="mt-5"><h4 className="text-sm font-semibold">Hlavní zjištění</h4><ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-6">{selected.key_findings.map((finding, index) => <li key={index}>{finding.text}</li>)}</ul></div> : null}
                {!selected.summary && !selected.research_question_answers.length && !selected.key_findings.length ? <p className="mt-3 text-sm text-ink-muted">Tato část nemá textový souhrn.</p> : null}
                {selected.claims.length ? <details className="mt-5 border-t border-border pt-3 text-xs text-ink-muted"><summary className="cursor-pointer">{t("research.exec.results.analysisEvidence")} a technický původ tvrzení</summary><p className="mt-2 break-words">{selected.claims.map((claim) => `${claim.claim_id} → ${claim.evidence_ref}`).join(", ")}</p></details> : null}
              </> : <div className="mt-3 text-sm text-ink-muted"><p>{selectedStep ? `Stav kroku: ${stepStatusLabel(selectedStep)}` : "Tato část zatím nemá uložený výstup."}</p>{selectedStep && waitingDetail(selectedStep) ? <p className="mt-1">{waitingDetail(selectedStep)}</p> : null}</div>}
            </section>
          </div>
        </div>
      ) : null}
    </Card>
  );
}

type AggregatePayload = {
  aggregate: {
    deviation?: unknown;
    questions: Record<string, Parameters<typeof resultTable>[1]>;
    batteries: Record<string, { title: string; objects: Record<string, Parameters<typeof resultTable>[1] & { label: string }> }>;
  };
};

type SpecificationPayload = {
  design_revision_id?: string;
  specification?: {
    n?: number | null;
    questions?: { id: string; text: string }[];
  };
};

type AggregateMeasure = { id: string; title: string; group: string | null; table: ResultTable };
type AggregateFilter = "all" | ResultTable["support"];

function measureSummary(table: ResultTable): string {
  if (table.suppressed) return "Číselný výsledek je skrytý, protože podpora dat nestačí.";
  if (table.typ === "vyber" || table.typ === "multi") {
    const leading = table.rows.filter((row) => row.bar).sort((a, b) => (b.bar?.value ?? 0) - (a.bar?.value ?? 0))[0];
    return leading ? `Nejčastější ${table.typ === "multi" ? "výběr" : "odpověď"}: ${leading.label} · ${leading.value}.` : "Pro tuto otázku není dostupný číselný souhrn.";
  }
  if (table.typ === "skala") {
    const [mean, top] = table.rows;
    return mean?.value ? `Průměr ${mean.value}${top?.value ? ` · horní část škály ${top.value}` : ""}.` : "Pro tuto škálu není dostupný číselný souhrn.";
  }
  return "Otevřete detail pro dostupné odpovědi a podporu dat.";
}

function supportLabel(support: ResultTable["support"]): string {
  if (support === "REPORTABLE") return "Podložené v rámci běhu";
  if (support === "INDICATIVE") return "Orientační";
  return "Potlačené";
}

function AggregateView({ artifact, run, specification }: { artifact: Artifact; run: ResearchRun; specification: Artifact | null }) {
  const [filter, setFilter] = useState<AggregateFilter>("all");
  const [query, setQuery] = useState("");
  const payload = artifact.payload as AggregatePayload | null;
  if (!payload?.aggregate) return null;
  const { questions, batteries } = payload.aggregate;
  const deviation = aggregateDeviation(payload.aggregate);
  const box = topBoxWidth(deviation);
  const spec = specification?.payload as SpecificationPayload | null;
  // The compile step is the run's source of truth. An identical specification can be reused
  // from an earlier revision, so its original revision id need not equal this run's id.
  const pinned = specification?.artifact_type === "research_specification" ? spec?.specification : null;
  const questionNames = new Map((pinned?.questions ?? []).map((question) => [question.id, question.text]));
  const measures: AggregateMeasure[] = [
    ...Object.entries(questions).map(([id, result]) => ({ id, title: questionNames.get(id) || `Otázka ${id}`, group: null, table: resultTable(id, result, box) })),
    ...Object.entries(batteries).flatMap(([id, battery]) => Object.entries(battery.objects).map(([oid, result]) => ({ id: `${id}:${oid}`, title: result.label || `Objekt ${oid}`, group: battery.title || `Sada ${id}`, table: resultTable(oid, result, box) }))),
  ];
  const counts = {
    REPORTABLE: measures.filter((measure) => measure.table.support === "REPORTABLE").length,
    INDICATIVE: measures.filter((measure) => measure.table.support === "INDICATIVE").length,
    SUPPRESS: measures.filter((measure) => measure.table.support === "SUPPRESS").length,
  };
  const matching = measures.filter((measure) =>
    (filter === "all" || measure.table.support === filter) &&
    `${measure.title} ${measure.group ?? ""} ${measure.id}`.toLocaleLowerCase("cs-CZ").includes(query.trim().toLocaleLowerCase("cs-CZ")),
  );
  return (
    <div className="flex flex-col gap-5" data-aggregate-explorer>
      {deviation ? <Deviation deviation={deviation} /> : null}
      <section aria-label="Jak číst tato data" className="rounded-md border border-border bg-surface-sunken p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-base font-semibold">Nejdřív posuďte sílu podkladů</h3>
          {typeof pinned?.n === "number" ? <span className="text-sm text-ink-muted">Plánovaný vzorek: {pinned.n.toLocaleString("cs-CZ")}</span> : null}
        </div>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-ink-muted">Každá karta popisuje jednu otázku nebo hodnocený objekt. Podpora se posuzuje zvlášť pro každou kartu; počet platných odpovědí se může lišit. Nejčastější odpověď ani rozdíl mezi procenty samy o sobě neprokazují významný rozdíl.</p>
        <dl className="mt-4 grid gap-2 sm:grid-cols-3">
          {(["REPORTABLE", "INDICATIVE", "SUPPRESS"] as const).map((status) => <div key={status} className="rounded-md border border-border bg-surface-raised px-3 py-2"><dt className="text-xs text-ink-muted">{supportLabel(status)}</dt><dd className="mt-1 text-xl font-semibold tabular-nums">{counts[status]}</dd></div>)}
        </dl>
        <p className="mt-3 text-xs leading-5 text-ink-muted">Pruh označuje podíl odpovědí; světlé pásmo jeho 95% interval nejistoty. Potlačené hodnoty se nezobrazují. U fiktivních a modelovaných respondentů jde o výsledky simulace, nikoli o měření skutečné populace.</p>
      </section>
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-56 flex-1 text-sm font-medium">Najít otázku nebo objekt
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Hledat podle názvu nebo ID" className="mt-1 block w-full rounded-control border border-border bg-surface-raised px-3 py-2 text-sm font-normal focus-visible:outline-2 focus-visible:outline-focus-ring" />
        </label>
        <label className="text-sm font-medium">Podpora dat
          <select value={filter} onChange={(event) => setFilter(event.target.value as AggregateFilter)} className="mt-1 block min-h-10 rounded-control border border-border bg-surface-raised px-3 py-2 text-sm font-normal focus-visible:outline-2 focus-visible:outline-focus-ring">
            <option value="all">Všechny výsledky ({measures.length})</option>
            <option value="REPORTABLE">Podložené ({counts.REPORTABLE})</option>
            <option value="INDICATIVE">Orientační ({counts.INDICATIVE})</option>
            <option value="SUPPRESS">Potlačené ({counts.SUPPRESS})</option>
          </select>
        </label>
      </div>
      <div className="flex flex-col gap-3" aria-live="polite">
        {matching.length ? matching.map((measure) => <section key={measure.id} aria-label={measure.title} className="rounded-md border border-border bg-surface-raised p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              {measure.group ? <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{measure.group}</p> : null}
              <h3 className="mt-1 text-sm font-semibold leading-6">{measure.title}</h3>
              <p className="mt-1 text-sm leading-6">{measureSummary(measure.table)}</p>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${measure.table.suppressed ? "bg-status-fault-wash text-status-fault" : "bg-signal-wash text-signal"}`}>{supportLabel(measure.table.support)}</span>
          </div>
          <p className="mt-2 text-xs text-ink-muted">{supportNote(measure.table)}</p>
          <details className="mt-3 border-t border-border pt-3 text-sm">
            <summary className="cursor-pointer font-medium">Odpovědi, intervaly a původ otázky</summary>
            <div className="mt-3"><Table table={measure.table} showSupportNote={false} /></div>
            <p className="mt-2 text-xs text-ink-muted">ID otázky: <code>{measure.id}</code> · platných odpovědí: {measure.table.respondents.toLocaleString("cs-CZ")} · unikátních dárců: {measure.table.donors.toLocaleString("cs-CZ")} · efektivní n: {measure.table.effectiveN.toLocaleString("cs-CZ")}</p>
          </details>
        </section>) : <p className="rounded-md border border-border bg-surface-sunken p-4 text-sm text-ink-muted">Žádný výsledek neodpovídá filtru. Změňte hledání nebo podporu dat.</p>}
      </div>
      <details className="text-xs text-ink-muted"><summary className="cursor-pointer">Původ agregace</summary><Provenance artifact={artifact} run={run} /></details>
    </div>
  );
}

/** The aggregate is no longer 18.6.6's port: said above its numbers, with what changed. */
function Deviation({ deviation: d }: { deviation: AggregateDeviation }) {
  const D = "research.exec.results.deviation";
  const shown = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v));
  const named = d.changed.length + d.formulas.length;
  return (
    <div role="note" data-aggregate-deviation className="flex flex-col gap-1 rounded-sm border border-status-fault p-3 text-sm">
      <div><Chip tone="fault">{t(`${D}.chip`)}</Chip></div>
      <p>{tv(`${D}.text`, { version: d.version ?? t(`${D}.unknownVersion`) })}</p>
      {named ? (
        <ul className="list-disc pl-5 text-xs">
          {d.changed.map((c) => <li key={c.path}>{tv(`${D}.changed`, { path: c.path, unit: shown(c.unit), used: shown(c.used) })}</li>)}
          {d.formulas.map((f) => <li key={f}>{tv(`${D}.formula`, { slot: f })}</li>)}
        </ul>
      ) : <p className="text-xs text-ink-muted">{t(`${D}.unreadable`)}</p>}
    </div>
  );
}

function SociomapView({ artifact, run }: { artifact: Artifact; run: ResearchRun }) {
  const frame = useFrame();
  // The register a map's approval is read from (B4); not read, every map stays internal.
  const [register, setRegister] = useState<RegisterEntry[] | null>(null);
  useEffect(() => {
    let live = true;
    research.sociomapRegister(frame.studyId).then(
      (value) => live && setRegister(value.entries ?? null),
      () => live && setRegister(null),
    );
    return () => { live = false; };
  }, [frame.studyId]);
  const payload = artifact.payload as {
    sociomap: {
      data_origin?: string | null;
      methods?: RecordedMethod[];
      batteries: (Parameters<typeof sociomapObjects>[0] & BatteryWithMaps)[];
    };
  } | null;
  if (!payload) return null;
  const approvalOf = (methodId: string) => mapApproval(payload.sociomap.methods, register, methodId);
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
                <ObjectMapView battery={b} dataOrigin={payload.sociomap.data_origin ?? null} approvalOf={approvalOf} />
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
