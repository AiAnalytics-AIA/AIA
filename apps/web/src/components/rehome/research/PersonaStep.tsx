"use client";

// 5. Dimenze, rebuilt (research-flow-rehome.md, chunk 6) and drawn as Studio v3
// (studio-v3.md, chunk 7: grouped checklists, the selection and the sample beside
// them, the dock): the classic
// renderPersona reassignment (:979) under its 1793 wrapper -- the fixed base,
// the dimension catalogue, a dimension request, the sample, and the model's
// proposed new dimensions. What each control does to the project is
// src/research/persona.ts, parity-tested against the original; this file only
// draws it. The model's suggestion is page memory, as the classic
// PERSONA_AI_SUGGESTION: kept while the person stays in the project, never saved.
//
// In AIA (ADR 0018) the catalogue's library is the client's own approved
// knowledge, read through the study, and a request is a proposal to it. The
// society-factor card and Deep Research for a new dimension were 18.6.6's (its
// licensed panel, its Data Library): the screen says they are not in AIA.

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { workspace } from "@/lib/api";
import { isNativeResult } from "@/lib/research-agent-jobs";
import { t, tv } from "@/i18n/t";
import {
  CLIENT_LIBRARY_LABEL,
  type ActiveDimensions,
  type Change,
  type NewDimension,
  PROPOSAL_AI_DONE,
  PROPOSAL_DONE,
  REQUEST_EMPTY,
  SUGGEST_FAILED_SUFFIX,
  SUGGEST_TITLE,
  SUGGEST_WARN_MS,
  type Suggestion,
  addDimension,
  applySuggestion,
  autofill,
  catalogEntries,
  clientDimensions,
  dimensionLabels,
  dimensionProposal,
  matchesDimensionSearch,
  personaDone,
  recommendedSample,
  recordRequest,
  removeDimension,
  requestLabel,
  requestedLabels,
  setSampleSize,
  suggestPayload,
  suggestedPersonaDims,
  suggestedRequest,
  applyRecommendedSample,
  withApproval,
} from "@/research/persona";
import { Icon } from "../icons";
import { ActionDock, StepSection } from "../step";
import { AiButton, Button, Field, TextInput } from "../ui";
import { useResearch, useSessionState } from "./context";
import { AiFailureCard, useAiStep } from "./useAiStep";


const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The client's approved dimensions, read once per visit through the study; none until they arrive. */
function useClientDimensions(studyId: string): ActiveDimensions {
  const [active, setActive] = useState<ActiveDimensions>({});
  useEffect(() => {
    let live = true;
    workspace.studyContext(studyId).then(
      (c) => live && setActive(clientDimensions(c.client)),
      // Without the client's knowledge the catalogue is the system's own dimensions.
      () => {},
    );
    return () => {
      live = false;
    };
  }, [studyId]);
  return active;
}

export function PersonaStep() {
  const { store, state, runJob, toast, stepHref, frame } = useResearch();
  const router = useRouter();
  const step = useAiStep();
  const active = useClientDimensions(frame.studyId);
  const [suggestion, setSuggestion] = useSessionState<Suggestion | null>("persona.suggestion", null);
  const [query, setQuery] = useState("");
  const [custom, setCustom] = useState("");
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);

  const p = state.project;
  const labels = dimensionLabels(active);
  const { approved } = withApproval(p);
  const chosen = new Set(approved);
  const suggested = new Set(suggestedPersonaDims(p));
  const entries = catalogEntries(active, CLIENT_LIBRARY_LABEL);
  const requested = requestedLabels(p);
  const r = recommendedSample(p);

  const apply = (c: Change) => store.update(() => ({ project: c.project }), { reason: c.reason });

  // suggestPersonaAI: the provider check, then the job; the model's dimensions become the approval.
  const suggest = () =>
    step.run(async () => {
      if (!(await step.providerOk())) return;
      await step.saved();
      const res = (await runJob("personaSuggest", suggestPayload(store.get().project, active), { title: SUGGEST_TITLE, warnMs: SUGGEST_WARN_MS })) as Suggestion;
      setSuggestion(res);
      if (isNativeResult(res)) return;
      apply(applySuggestion(store.get().project, res || {}));
    }, (m) => m + SUGGEST_FAILED_SUFFIX);

  // requestDimension1793, in AIA: a proposal to the client's knowledge, and the project's
  // record of it. It is in the catalogue once someone approves it, not before.
  const request = async (label: string, sourceStrategy: string, extra: Parameters<typeof dimensionProposal>[2], done: string) => {
    setRequestError(null);
    if (!label) return setRequestError(REQUEST_EMPTY);
    setRequesting(true);
    try {
      const res = await workspace.proposeFromStudy(frame.studyId, dimensionProposal(label, sourceStrategy, extra));
      apply(recordRequest(store.get().project, label, sourceStrategy, { proposal_id: res.proposal_id }));
      toast(done);
      return true;
    } catch (e) {
      setRequestError(message(e));
      return false;
    } finally {
      setRequesting(false);
    }
  };
  const requestCustom = async () => {
    if (await request(requestLabel(custom), "document_or_research", {}, PROPOSAL_DONE)) setCustom("");
  };
  const requestSuggested = (x: NewDimension) => {
    const q = suggestedRequest(x);
    void request(q.label, q.sourceStrategy, q.extra, PROPOSAL_AI_DONE);
  };

  const toRun = () => {
    apply(personaDone(store.get().project));
    router.push(stepHref("run"));
  };

  const visible = entries.filter((d) => matchesDimensionSearch(d, query));
  const recommendedRows = visible.filter((d) => suggested.has(d.id));
  const catalogRows = visible.filter((d) => !suggested.has(d.id));
  const toggle = (id: string) => apply(chosen.has(id) ? removeDimension(store.get().project, id) : addDimension(store.get().project, id));
  const n = Number(p.n) || r.n;

  return (
    <div className="flex max-w-[82.5rem] flex-wrap items-start gap-6">
      <aside aria-label={t("research.persona.asideLabel")} className="sticky top-60 order-2 flex flex-[1_1_280px] flex-col gap-4">
        <section aria-labelledby="per-chosen" className="rounded-card border border-border bg-surface-raised p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 id="per-chosen" className="text-sm font-semibold">{t("research.persona.chosenTitle")}</h2>
            <span className="rounded-pill bg-signal-wash px-2 font-mono text-xs leading-5 text-signal">{approved.length}</span>
          </div>
          <ul className="mt-3 flex flex-col gap-1" aria-label={t("research.persona.catalogTitle")}>
            <li className="flex items-center gap-2 rounded-control bg-surface-sunken px-2.5 py-1.5 text-[13px]">
              <Icon name="pin" size={12} className="text-ink-faint" />
              <span className="flex-1">{t("research.persona.baseRow")}</span>
            </li>
            {approved.length ? (
              approved.map((id) => (
                <li key={id} className="flex items-center gap-2 rounded-control border border-border px-2.5 py-1 text-[13px]">
                  <span className="min-w-0 flex-1 truncate">{labels[id] || id}</span>
                  <button
                    type="button"
                    aria-label={tv("research.persona.remove", { label: labels[id] || id })}
                    onClick={() => apply(removeDimension(store.get().project, id))}
                    className="rounded-sm px-1 text-ink-faint hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring"
                  >
                    ×
                  </button>
                </li>
              ))
            ) : (
              <li className="text-xs text-ink-muted">{t("research.persona.noneSelected")}</li>
            )}
            {requested.map((label, i) => (
              <li key={`${label}-${i}`} className="rounded-control border border-dashed border-status-you-ink/50 bg-status-you-wash px-2.5 py-1 text-[13px] text-status-you-ink">
                {tv("research.persona.waiting", { label })}
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="per-sample" className="rounded-card border border-border bg-surface-raised p-4">
          <div className="flex items-center justify-between gap-2">
            <h2 id="per-sample" className="text-sm font-semibold">{t("research.persona.sampleTitle")}</h2>
            <span className="font-mono text-xs text-ink-muted">{tv("research.persona.sampleChip", { n: r.n })}</span>
          </div>
          <div className="mt-3">
            <SampleInput
              key={n}
              value={n}
              onCommit={(raw) => {
                const c = setSampleSize(store.get().project, raw);
                apply(c);
                return Number(c.project.n);
              }}
            />
          </div>
          <SampleSlider key={`s-${n}`} value={n} recommended={r.n} onCommit={(v) => apply(setSampleSize(store.get().project, String(v)))} />
          <div className="mt-3 flex flex-wrap gap-1.5">
            <button
              type="button"
              aria-label={tv("research.persona.sampleUse", { n: r.n })}
              aria-pressed={n === r.n}
              onClick={() => apply(applyRecommendedSample(store.get().project))}
              className={`${PRESET} ${n === r.n ? PRESET_ON : ""}`}
            >
              {tv("research.persona.presetRecommended", { n: r.n })}
            </button>
            {[400, 800, 1200].filter((x) => x !== r.n).map((x) => (
              <button key={x} type="button" aria-pressed={n === x} onClick={() => apply(setSampleSize(store.get().project, String(x)))} className={`${PRESET} ${n === x ? PRESET_ON : ""}`}>
                {x}
              </button>
            ))}
          </div>
          <p className={`mt-3 text-xs leading-[18px] ${n < r.n ? "text-status-you-ink" : "text-ink-muted"}`}>
            {n < r.n ? tv("research.persona.sampleBelow", { n: r.n }) : r.why}
          </p>
        </section>
      </aside>

      <div className="order-1 flex min-w-0 flex-[999_1_520px] flex-col gap-4">
        {step.failure ? <AiFailureCard failure={step.failure} title={t("research.persona.failedTitle")} onRetry={() => step.setFailure(null)} /> : null}

        <StepSection
          n={1}
          lead
          title={t("research.persona.catalogTitle")}
          hint={t("research.persona.baseIntro")}
          aside={<AiButton small disabled={step.busy} onClick={() => void suggest()}>{t("research.persona.suggest")}</AiButton>}
        >
          <label className="flex items-center gap-2 rounded-control border border-border-strong bg-surface-raised px-2.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus-ring">
            <Icon name="search" size={14} className="text-ink-muted" />
            <input
              aria-label={t("research.persona.searchLabel")}
              placeholder={t("research.persona.search")}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-h-[34px] min-w-0 flex-1 border-0 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          {visible.length ? (
            <>
              {recommendedRows.length ? (
                <DimensionGroup
                  title={t("research.persona.groupRecommended")}
                  action={<Button small variant="quiet" onClick={() => apply(autofill(store.get().project))}>{t("research.persona.autofill")}</Button>}
                  rows={recommendedRows}
                  chosen={chosen}
                  suggested={suggested}
                  onToggle={toggle}
                />
              ) : null}
              {catalogRows.length ? <DimensionGroup title={t("research.persona.groupCatalog")} rows={catalogRows} chosen={chosen} suggested={suggested} onToggle={toggle} /> : null}
            </>
          ) : (
            <p className="mt-3 text-sm text-ink-muted">{t("research.persona.noMatch")}</p>
          )}
        </StepSection>

        {suggestion?.new_dimension_suggestions?.length ? (
          <section className="rounded-card border border-border border-l-[3px] border-l-signal bg-surface-raised p-5" aria-labelledby="per-new">
            <h2 id="per-new" className="text-base font-semibold">{t("research.persona.newTitle")}</h2>
            <p className="mt-1 text-[13px] text-ink-muted">{t("research.persona.newHelper")}</p>
            <ul className="mt-3 flex flex-col gap-2">
              {suggestion.new_dimension_suggestions.map((x, i) => (
                <li key={`${x.label}-${i}`} className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-border bg-surface p-3">
                  <div className="min-w-0">
                    <b className="text-sm">{String(x.label ?? "")}</b>
                    <div className="text-xs text-ink-muted">{tv("research.persona.newWhy", { why: String(x.why ?? ""), evidence: String(x.evidence_needed ?? "") })}</div>
                    <div className="text-xs text-ink-muted">
                      {tv("research.persona.newPredictors", { list: (x.suggested_predictors || []).join(", ") || t("research.persona.newPredictorsNone") })}
                    </div>
                  </div>
                  <Button small className="!rounded-control" disabled={requesting} onClick={() => requestSuggested(x)}>{t("research.persona.newRequest")}</Button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <StepSection n={2} optional title={t("research.persona.customSummary")} hint={t("research.persona.customHelper")}>
          <div className="flex flex-wrap items-end gap-2">
            <Field label={t("research.persona.customLabel")} className="min-w-64 flex-1">
              <TextInput className="w-full !rounded-control" value={custom} placeholder={t("research.persona.customPlaceholder")} onChange={(e) => setCustom(e.target.value)} />
            </Field>
            <Button className="!rounded-control" disabled={requesting} onClick={() => void requestCustom()}>{t("research.persona.customAdd")}</Button>
          </div>
          {requestError ? (
            <p role="alert" className="mt-3 rounded-control border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">
              <b>{t("research.persona.requestFailedTitle")}</b> {requestError}
            </p>
          ) : null}
          {/* The 1793 society-factor card is drawn from 18.6.6's licensed panel: not in AIA. */}
          <section className="mt-4 rounded-control border border-status-you-ink/40 bg-status-you-wash p-3" aria-labelledby="per-factors">
            <h3 id="per-factors" className="text-sm font-semibold">{t("research.persona.factorsNotInAiaTitle")}</h3>
            <p className="mt-1 text-[13px] leading-5">{t("research.persona.factorsNotInAia")}</p>
          </section>
        </StepSection>

        <ActionDock
          back={{ href: stepHref("audience"), label: `4. ${t("aia.stages.audience")}` }}
          note={tv("research.persona.dockNote", { d: approved.length, n })}
        >
          <Button variant="primary" className="!rounded-control" onClick={toRun}>
            {t("research.persona.next")}
            <Icon name="next" size={14} />
          </Button>
        </ActionDock>
      </div>
    </div>
  );
}

const PRESET = "rounded-pill border border-border bg-surface px-2.5 font-mono text-xs leading-6 text-ink hover:border-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const PRESET_ON = "!border-signal bg-signal-wash font-semibold text-signal";

/** One group of the catalogue as a checklist: a row per dimension, toggled by a click. */
function DimensionGroup({ title, action, rows, chosen, suggested, onToggle }: {
  title: string;
  action?: ReactNode;
  rows: { id: string; label: string; source: string }[];
  chosen: Set<string>;
  suggested: Set<string>;
  onToggle: (id: string) => void;
}) {
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[13px] font-semibold">{title}</h3>
        {action}
      </div>
      <ul className="mt-1.5 divide-y divide-border overflow-hidden rounded-control border border-border">
        {rows.map((d) => {
          const on = chosen.has(d.id);
          return (
            <li key={d.id}>
              <button
                type="button"
                aria-pressed={on}
                onClick={() => onToggle(d.id)}
                className={`flex w-full items-center gap-3 px-3 py-2 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring ${on ? "bg-signal-wash font-semibold" : "bg-surface-raised hover:bg-surface-sunken"}`}
              >
                <span aria-hidden="true" className={`inline-flex size-4 shrink-0 items-center justify-center rounded-sm border ${on ? "border-signal bg-signal text-on-signal" : "border-border-strong bg-surface-raised"}`}>
                  {on ? <Icon name="done" size={12} /> : null}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm">{d.label}</span>
                  <small className="block text-xs font-normal text-ink-muted">
                    {d.source}
                    {suggested.has(d.id) ? t("research.persona.recommended") : ""}
                  </small>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** The sample as a slider (200–2 000, step 50) with the recommendation marked; it commits on release. */
function SampleSlider({ value, recommended, onCommit }: { value: number; recommended: number; onCommit: (v: number) => void }) {
  const [v, setV] = useState(Math.max(200, Math.min(2000, value)));
  const pos = (x: number) => `${((Math.max(200, Math.min(2000, x)) - 200) / 1800) * 100}%`;
  return (
    <div className="mt-3">
      <input
        type="range"
        min={200}
        max={2000}
        step={50}
        value={v}
        aria-label={t("research.persona.sampleSlider")}
        onChange={(e) => setV(Number(e.target.value))}
        onPointerUp={() => v !== value && onCommit(v)}
        onKeyUp={() => v !== value && onCommit(v)}
        className="w-full accent-signal"
      />
      <div aria-hidden="true" className="relative h-4 text-[10px] text-ink-faint">
        <span className="absolute -translate-x-1/2 font-mono" style={{ left: pos(recommended) }}>▲ {recommended}</span>
      </div>
    </div>
  );
}

/** The classic number input saves on change (blur or Enter), not on each key; a new stored N redraws it (key). */
function SampleInput({ value, onCommit }: { value: number; onCommit: (raw: string) => number }) {
  const [draft, setDraft] = useState(String(value));
  const commit = () => {
    if (draft !== String(value)) setDraft(String(onCommit(draft)));
  };
  return (
    <Field label={t("research.persona.sampleLabel")} className="w-full">
      <TextInput
        className="w-full !rounded-control"
        type="number"
        min={50}
        max={5000}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
        }}
      />
    </Field>
  );
}
