"use client";

// 5. Dimenze, rebuilt (research-flow-rehome.md, chunk 6): the classic
// renderPersona reassignment (:979) under its 1793 wrapper -- the fixed base,
// the dimension catalogue, a dimension request, the sample, and the society
// factors with the model's proposed new dimensions. What each control does to
// the project is src/unit/research/persona.ts, parity-tested against the
// original; this file only draws it. The model's suggestion and the refreshed
// library are page memory, as the classic PERSONA_AI_SUGGESTION and
// LIBRARY_STATE: kept while the person stays in the project, never saved.

import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { DIMENSION_RESEARCH_KEY, classicHref, rememberReturn } from "@/lib/interface-handoff";
import { isNativeResult } from "@/lib/research-agent-jobs";
import { t, tv } from "@/i18n/t";
import { unit } from "@/unit/client";
import { type Catalog, loadAudienceCatalog } from "@/unit/research/audience";
import {
  type Change,
  type NewDimension,
  REQUEST_AI_DONE,
  REQUEST_DONE,
  REQUEST_EMPTY,
  REQUEST_TIMEOUT_MS,
  SUGGEST_FAILED_SUFFIX,
  SUGGEST_TITLE,
  SUGGEST_WARN_MS,
  type Suggestion,
  activeDimensions,
  addDimension,
  applySuggestion,
  autofill,
  catalogEntries,
  dimensionLabels,
  matchesDimensionSearch,
  personaDone,
  recommendedSample,
  recordRequest,
  refreshLibrary,
  removeDimension,
  requestBody,
  requestLabel,
  requestedLabels,
  setSampleSize,
  suggestPayload,
  suggestedPersonaDims,
  suggestedRequest,
  applyRecommendedSample,
  withApproval,
} from "@/unit/research/persona";
import { Icon } from "../icons";
import { Button, Chip, Field, TextInput } from "../ui";
import { useResearch, useSessionState } from "./context";
import { AiFailureCard, useAiStep } from "./useAiStep";

const CARD = "rounded-md border border-border bg-surface-raised p-5";
const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export function PersonaStep() {
  const { store, state, boot, runJob, toast, stepHref } = useResearch();
  const router = useRouter();
  const step = useAiStep();
  const [library, setLibrary] = useSessionState<unknown>("persona.library", null);
  const [suggestion, setSuggestion] = useSessionState<Suggestion | null>("persona.suggestion", null);
  const [query, setQuery] = useState("");
  const [custom, setCustom] = useState("");
  const [requestError, setRequestError] = useState<string | null>(null);
  const [requesting, setRequesting] = useState(false);

  const p = state.project;
  const active = activeDimensions(library, boot.raw);
  const labels = dimensionLabels(active);
  const { approved } = withApproval(p);
  const chosen = new Set(approved);
  const suggested = new Set(suggestedPersonaDims(p));
  const entries = catalogEntries(active);
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

  // requestDimension1793: the request, the project's record of it, the library read again.
  const request = async (label: string, sourceStrategy: string, extra: Parameters<typeof requestBody>[2], done: string) => {
    setRequestError(null);
    if (!label) return setRequestError(REQUEST_EMPTY);
    setRequesting(true);
    try {
      const res = (await unit("libraryDimensionRequest", { body: requestBody(label, sourceStrategy, extra), timeoutMs: REQUEST_TIMEOUT_MS })) as { dimension_id?: string; proposal_id?: string };
      apply(recordRequest(store.get().project, label, sourceStrategy, res || {}));
      // refreshLibraryState swallows its own failure; so does the rebuild.
      await refreshLibrary().then(setLibrary, () => {});
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
    if (await request(requestLabel(custom), "document_or_research", {}, REQUEST_DONE)) setCustom("");
  };
  const requestSuggested = (x: NewDimension) => {
    const q = suggestedRequest(x);
    void request(q.label, q.sourceStrategy, q.extra, REQUEST_AI_DONE);
  };

  const toRun = () => {
    apply(personaDone(store.get().project));
    router.push(stepHref("run"));
  };
  const toAudience = () => {
    router.push(stepHref("audience"));
  };

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <section className={CARD} aria-labelledby="per-base">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className={EYEBROW}>{t("research.persona.baseTag")}</div>
            <h2 id="per-base" className="mt-1 text-base font-semibold">{t("research.persona.baseTitle")}</h2>
          </div>
          <Chip tone="done">{t("research.persona.baseChip")}</Chip>
        </div>
        <p className="mt-2 text-sm leading-6 text-ink-muted">{t("research.persona.baseIntro")}</p>
      </section>

      {step.failure ? <AiFailureCard failure={step.failure} title={t("research.persona.failedTitle")} onRetry={() => step.setFailure(null)} /> : null}

      <section className={CARD} aria-labelledby="per-catalog">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className={EYEBROW}>{t("research.persona.catalogTag")}</div>
            <h2 id="per-catalog" className="mt-1 text-base font-semibold">{t("research.persona.catalogTitle")}</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button small icon="assistant" disabled={step.busy} onClick={() => void suggest()}>{t("research.persona.suggest")}</Button>
            <Button small variant="quiet" onClick={() => apply(autofill(store.get().project))}>{t("research.persona.autofill")}</Button>
          </div>
        </div>

        <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={t("research.persona.catalogTitle")}>
          {approved.length ? (
            approved.map((id) => (
              <li key={id} className="inline-flex items-center gap-1 rounded-sm border border-signal-edge bg-signal-wash py-0.5 pl-2 pr-0.5 text-xs">
                {labels[id] || id}
                <button
                  type="button"
                  aria-label={tv("research.persona.remove", { label: labels[id] || id })}
                  onClick={() => apply(removeDimension(store.get().project, id))}
                  className="rounded-sm px-1 text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring"
                >
                  ×
                </button>
              </li>
            ))
          ) : (
            <li className="text-xs text-ink-muted">{t("research.persona.noneSelected")}</li>
          )}
        </ul>

        <div className="mt-3">
          <TextInput aria-label={t("research.persona.searchLabel")} placeholder={t("research.persona.search")} value={query} onChange={(e) => setQuery(e.target.value)} />
          <ul className="mt-2 grid gap-1 sm:grid-cols-2">
            {entries.filter((d) => matchesDimensionSearch(d, query)).map((d) => {
              const on = chosen.has(d.id);
              return (
                <li key={d.id}>
                  <button
                    type="button"
                    aria-pressed={on}
                    onClick={() => apply(on ? removeDimension(store.get().project, d.id) : addDimension(store.get().project, d.id))}
                    className={`flex w-full items-center justify-between gap-2 rounded-sm border px-3 py-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${on ? "border-signal bg-signal-wash" : "border-border bg-surface hover:bg-surface-sunken"}`}
                  >
                    <span className="min-w-0">
                      <b className="block text-sm">{d.label}</b>
                      <small className="text-xs text-ink-muted">
                        {d.source}
                        {suggested.has(d.id) ? t("research.persona.recommended") : ""}
                      </small>
                    </span>
                    <Chip tone={on ? "done" : "neutral"}>{on ? t("research.persona.selected") : t("research.persona.add")}</Chip>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <details className="mt-4 rounded-sm border border-border bg-surface p-3">
          <summary className="cursor-pointer text-sm">
            <b>{t("research.persona.customSummary")}</b> <span className="text-xs text-ink-muted">{t("research.persona.customSecondary")}</span>
          </summary>
          <div className="mt-3 flex flex-wrap items-end gap-2">
            <Field label={t("research.persona.customLabel")} className="min-w-64 flex-1">
              <TextInput value={custom} placeholder={t("research.persona.customPlaceholder")} onChange={(e) => setCustom(e.target.value)} />
            </Field>
            <Button disabled={requesting} onClick={() => void requestCustom()}>{t("research.persona.customAdd")}</Button>
          </div>
          <p className="mt-2 text-xs leading-5 text-ink-muted">{t("research.persona.customHelper")}</p>
        </details>
        {requestError ? (
          <p role="alert" className="mt-3 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">
            <b>{t("research.persona.requestFailedTitle")}</b> {requestError}
          </p>
        ) : null}
        {requested.length ? (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {requested.map((label, i) => (
              <Chip key={`${label}-${i}`} tone="you">{tv("research.persona.waiting", { label })}</Chip>
            ))}
          </div>
        ) : null}
      </section>

      <section className={CARD} aria-labelledby="per-sample">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className={EYEBROW}>{t("research.persona.sampleTag")}</div>
            <h2 id="per-sample" className="mt-1 text-base font-semibold">{t("research.persona.sampleTitle")}</h2>
          </div>
          <Chip tone="done">{tv("research.persona.sampleChip", { n: r.n })}</Chip>
        </div>
        <p className="mt-2 text-sm text-ink-muted">{r.why}</p>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <SampleInput
            key={Number(p.n) || r.n}
            value={Number(p.n) || r.n}
            onCommit={(raw) => {
              const c = setSampleSize(store.get().project, raw);
              apply(c);
              return Number(c.project.n);
            }}
          />
          <Button onClick={() => apply(applyRecommendedSample(store.get().project))}>{tv("research.persona.sampleUse", { n: r.n })}</Button>
        </div>
      </section>

      {/* The 1793 wrapper draws both cards only once the audience catalogue is loaded. */}
      <Factors onUse={toAudience}>
        {suggestion?.new_dimension_suggestions?.length ? (
          <section className={CARD} aria-labelledby="per-new">
            <h2 id="per-new" className="text-base font-semibold">{t("research.persona.newTitle")}</h2>
            <p className="mt-1 text-sm text-ink-muted">{t("research.persona.newHelper")}</p>
            <ul className="mt-3 flex flex-col gap-2">
              {suggestion.new_dimension_suggestions.map((x, i) => (
                <li key={`${x.label}-${i}`} className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border bg-surface p-3">
                  <div className="min-w-0">
                    <b className="text-sm">{String(x.label ?? "")}</b>
                    <div className="text-xs text-ink-muted">{tv("research.persona.newWhy", { why: String(x.why ?? ""), evidence: String(x.evidence_needed ?? "") })}</div>
                    <div className="text-xs text-ink-muted">
                      {tv("research.persona.newPredictors", { list: (x.suggested_predictors || []).join(", ") || t("research.persona.newPredictorsNone") })}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button small disabled={requesting} onClick={() => requestSuggested(x)}>{t("research.persona.newRequest")}</Button>
                    <Button small variant="quiet" onClick={() => openResearch(String(x.label ?? ""))}>{t("research.persona.newResearch")}</Button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </Factors>

      <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
        <Button variant="primary" onClick={toRun}>
          {t("research.persona.next")}
          <Icon name="next" size={14} />
        </Button>
      </div>
    </div>
  );
}

/** openDimensionResearch1793 is the classic Data Library's: the label goes by session storage (ADR 0014). */
function openResearch(label: string) {
  try {
    window.sessionStorage.setItem(DIMENSION_RESEARCH_KEY, label);
  } catch {
    // Without storage the classic page opens without the topic filled in.
  }
  rememberReturn(window.location.pathname + window.location.search);
  window.location.href = classicHref({ dimension: "research" });
}

/** The classic number input saves on change (blur or Enter), not on each key; a new stored N redraws it (key). */
function SampleInput({ value, onCommit }: { value: number; onCommit: (raw: string) => number }) {
  const [draft, setDraft] = useState(String(value));
  const commit = () => {
    if (draft !== String(value)) setDraft(String(onCommit(draft)));
  };
  return (
    <Field label={t("research.persona.sampleLabel")} className="w-48">
      <TextInput
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

/** The 1793 card: the society factors the panel already has, drawn once the audience catalogue is loaded. */
function Factors({ onUse, children }: { onUse: () => void; children: ReactNode }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  useEffect(() => {
    let live = true;
    // One request per visit; a failure leaves the card out (OI-57: the classic asks again on every draw).
    loadAudienceCatalog().then((c) => live && setCatalog(c), () => {});
    return () => {
      live = false;
    };
  }, []);
  if (!catalog) return null;
  const cats = (catalog.categories || []).filter((c) => c.id !== "research_only");
  return (
    <>
    <section className={CARD} aria-labelledby="per-factors">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className={EYEBROW}>{t("research.persona.factorsTag")}</div>
          <h2 id="per-factors" className="mt-1 text-base font-semibold">{t("research.persona.factorsTitle")}</h2>
        </div>
        <Chip tone="done">{tv("research.persona.factorsChip", { n: String(catalog.filterable_count ?? "") })}</Chip>
      </div>
      <p className="mt-2 text-sm leading-6 text-ink-muted">{t("research.persona.factorsIntro")}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {cats.map((c) => (
          <Chip key={String(c.id)} tone="neutral">{`${c.label ?? ""} · ${c.filterable_count ?? ""}`}</Chip>
        ))}
      </div>
      <Button className="mt-3" onClick={onUse}>{t("research.persona.factorsUse")}</Button>
    </section>
    {children}
    </>
  );
}
