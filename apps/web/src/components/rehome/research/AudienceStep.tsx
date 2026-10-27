"use client";

// 4. Audience / Cílová skupina, rebuilt (research-flow-rehome.md, chunk 5) and drawn toward the
// research stages v73 board (R4, spec vzorek/A1): one question, "Koho mají výsledky reprezentovat?",
// with three answers -- Celá ČR 18+, Zúžit, and Najít ve výsledcích, shown disabled because AIA
// cannot run it -- and the description in the person's own words. The source and population
// questions of the classic renderAudience (:374) are gone: AIA has one population, so a choice writes
// it (normalizeEntry). A study stored on a path the screen no longer offers (an own dataset, a
// special group, a Discover) opens readable and says what is kept. What each control does to the
// project is src/research/audience.ts, parity-tested against the original; this file only draws it.
//
// The factor catalogue and its filters, the feasibility preview and the built-in subpanels (under
// Zúžit) are AIA's own, from its population (GET /population/audience-catalogue, POST
// /population/audience-preview); where this deployment has none, the step says why. Whether a run
// applies the filters is the run's pin, and readiness says it ("audience").

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useContext, useEffect, useState } from "react";

import { ChoiceChips } from "@/components/ui/ChoiceChips";
import { InlineText } from "@/components/ui/InlineText";
import { Stepper } from "@/components/ui/Stepper";
import { ApiError, type AudienceCatalogue, population } from "@/lib/api";
import { audienceFilterAia, audiencePartAia, audienceSubpanelAia } from "@/lib/artifacts/audience";
import { rangeWords } from "@/lib/number-input";
import { isNativeResult } from "@/lib/research-agent-jobs";
import { stageHref } from "@/lib/workbench-stages";
import { t, tv } from "@/i18n/t";
import {
  type Catalog,
  type Catalogues,
  type Change,
  DEFAULT_CATEGORY,
  type Factor,
  PROPOSE_EMPTY,
  PROPOSE_FAILED_SUFFIX,
  PROPOSE_TITLE,
  PROPOSE_UNCOVERED,
  PROPOSE_WARN_MS,
  type Strategy,
  applyPopulationSubpanel,
  applyProposal,
  audienceReady,
  boundOf,
  endUnreadable,
  chooseStrategy,
  detachSubpanel,
  factorRefusal,
  filterCategories,
  filterChips,
  filterProblems,
  filterableFactors,
  humanFilters,
  humanSummary,
  keptPaths,
  normalizeEntry,
  setAudienceDescription,
  strategyOf,
  liveCatalog,
  liveSubpanels,
  matchingSubpanels,
  feasibility,
  type Feasibility,
  filterCountLines,
  proposePayload,
  proposeText,
  rangeBounds,
  removeAudienceFactor,
  searchKey,
  setAudienceCategory,
  setRange,
  storedRange,
  storedValues,
  CATALOGUE_TOP_VALUES,
  VALUE_CHIPS_MAX,
  matchingValues,
  pickValues,
} from "@/research/audience";
import type { Json, ResearchProject } from "@/research/model";
import { Icon } from "../icons";
import { ActionDock, FrameNavigation, RadioCard, StepSection } from "../step";
import { AiButton, Button, Chip, Field, Tag, TextInput } from "../ui";
import { useResearch } from "./context";
import { InspectorSlot } from "./Inspector";
import { AskLead, useLeadOwnsAiStarts } from "./AskLead";
import { AiFailureCard, useAiStep } from "./useAiStep";
import { useAudiencePreview } from "./useAudiencePreview";
import { errorText } from "@/lib/error-words";

/** A filter refused whole, in words (filterProblems' reasons other than `values`). */
const PROBLEM_WORDS = { factor: "research.audience.problemFactor", policy: "research.audience.problemPolicy", empty: "research.audience.problemEmpty", range: "research.audience.problemRange" } as const;

const NOT_IN_AIA = "rounded-control border border-status-you-ink/40 bg-status-you-wash p-4";
const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint";

/** A capability 18.6.6 had and AIA does not, said where the person meets it. */
function NotInAia({ title, children }: { title: string; children: string }) {
  return (
    <section className={NOT_IN_AIA}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <Chip tone="you">{t("research.audience.notInAiaChip")}</Chip>
      </div>
      <p className="mt-1 text-sm leading-6">{children}</p>
    </section>
  );
}

/** AIA's own catalogue of filters and subpanels, or why this deployment has none. */
type Live =
  | { state: "loading" }
  | { state: "ready"; api: AudienceCatalogue; catalog: Catalog; subpanels: Catalogues }
  | { state: "missing"; text: string };

function useLiveAudience(): Live {
  const [live, setLive] = useState<Live>({ state: "loading" });
  useEffect(() => {
    let on = true;
    population.audienceCatalogue().then(
      (api) => on && setLive({ state: "ready", api, catalog: liveCatalog(api), subpanels: liveSubpanels(api) }),
      (e: unknown) => {
        if (!on) return;
        if (e instanceof ApiError && e.code === "population_not_established") return setLive({ state: "missing", text: t("research.audience.catalogueNoPopulation") });
        if (e instanceof ApiError && e.status === 404) return setLive({ state: "missing", text: t("research.audience.catalogueMissing") });
        setLive({ state: "missing", text: tv("research.audience.catalogueFailed", { message: errorText(e) }) });
      },
    );
    return () => {
      on = false;
    };
  }, []);
  return live;
}

export function AudienceStep() {
  const { store, state, stepHref } = useResearch();
  const router = useRouter();
  // Inside the workbench the frame opens the next stage (its leave guard, its heading's focus); outside it, the route.
  const frameNav = useContext(FrameNavigation);
  const p = state.project;
  const ready = audienceReady(p);
  const strategy = strategyOf(p);
  const kept = keptPaths(p);
  const live = useLiveAudience();
  const isLive = live.state === "ready";

  // R4: one choice of three (chooseStrategy), written as ČR 18+.
  const pickStrategy = (k: Strategy) => {
    const c = chooseStrategy(store.get().project, k);
    if (c) store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
  };


  return (
    <div className="flex max-w-[82.5rem] flex-col gap-4">
      <InspectorSlot>
        <Summary project={p} strategy={strategy} />
      </InspectorSlot>

      <div className="flex min-w-0 flex-col gap-4">
        <StepSection n={1} lead done={strategy !== null} title={t("research.audience.strategyTitle")}>
          <div role="radiogroup" aria-label={t("research.audience.strategyTitle")} className="grid gap-2 md:grid-cols-3">
            {([["population", "strategyPopulation"], ["filters", "strategyFilters"], ["discover", "strategyDiscover"]] as const).map(([k, key]) => (
              <RadioCard
                key={k}
                checked={strategy === k}
                // Najít ve výsledcích is not executable in AIA (R9: disabled, its reason in its caption).
                disabled={k === "discover"}
                onSelect={() => pickStrategy(k)}
                title={<>{t(`research.audience.${key}`)} {k === "filters" && !isLive ? <Tagged>{t("research.audience.notInAiaChip")}</Tagged> : null}</>}
              >
                {t(`research.audience.${key}Text`)}
              </RadioCard>
            ))}
          </div>
          {kept.map((k) => (
            <div key={k.kind} className="mt-3 rounded-control border border-border bg-surface p-3">
              <p className="text-sm">
                {k.kind === "discover" ? t("research.audience.keptDiscover") : <><b>{t(k.kind === "dataset" ? "research.audience.storedDataset" : "research.audience.keptSpecial")}</b> {k.name}</>}
              </p>
              {k.kind === "discover" ? null : <p className="mt-1 text-xs text-ink-muted">{t("research.audience.storedNotUsed")}</p>}
            </div>
          ))}
          <div data-aia={audiencePartAia("definition")} className="mt-4">
            <p aria-hidden className="text-sm font-medium">{t("research.audience.describe")}</p>
            <InlineText
              value={String(p.audience.description || "")}
              label={t("research.audience.describe")}
              placeholder={t("research.audience.describePlaceholder")}
              className="mt-1"
              rules={{ required: false }}
              disabled={state.save.kind === "readonly"}
              onCommit={(v) => store.update(({ project }) => ({ project: setAudienceDescription(project, v) }), { reason: "audience_description" })}
            />
          </div>
          {strategy === "filters" ? <FilterEditor live={live} /> : null}
          {p.audience.strategy === "discover" ? <DiscoverKept /> : null}
        </StepSection>

        <ActionDock
          back={{ href: stepHref("questionnaire"), label: `3. ${t("aia.stages.questionnaire")}` }}
          ready={ready}
          note={ready ? (isLive ? t("research.audience.liveCheck") : t("research.audience.checkNotInAia")) : t("research.audience.nextHint")}
        >
          <Button variant="primary" className="!rounded-control" disabled={!ready} onClick={() => (frameNav?.next ? frameNav.next.go() : router.push(stepHref("persona")))}>
            {t("research.audience.next")}
            <Icon name="next" size={14} />
          </Button>
        </ActionDock>
      </div>
    </div>
  );
}

/** A small status tag beside a choice's title. */
function Tagged({ children }: { children: string }) {
  return <span className="ml-1 whitespace-nowrap rounded-md bg-status-you-wash px-1.5 py-px align-middle font-mono text-[10px] font-semibold tracking-[0.04em] text-status-you-ink">{children}</span>;
}

/**
 * filterEditor. With AIA's catalogue: the factors of its population, their values and
 * counts, the chips of what is chosen and the feasibility preview. Without one (this
 * deployment has no population or no kept catalogue): what needs no panel -- the filters
 * a study already stores (removable) -- and why the rest is missing. Either way the AI's
 * proposed description of the audience (a native job, ADR 0016/0018).
 */
/** Said once a native audience proposal is reviewed, whether it ran at once or after a budget lift. */
const PROPOSE_SAVED = "Návrh audience je uložený. Zkontrolujte popis a omezení.";

function FilterEditor({ live }: { live: Live }) {
  const { store, state, runJob, toast } = useResearch();
  const step = useAiStep();
  const leadOwnsAiStarts = useLeadOwnsAiStarts();
  const chips = filterChips(state.project, live.state === "ready" ? live.catalog : null);
  // What the population cannot honour as stored, said now rather than at the preview or the run.
  const version = live.state === "ready" ? live.api.version_label : null;
  const problems = live.state === "ready" ? filterProblems(state.project, live.catalog) : [];
  const problemOf = new Map(problems.map((x) => [x.id, x]));
  // Every filter edit here, the AI proposal's too, leaves a chosen subpanel behind (detachSubpanel).
  const change = (raw: Change) => {
    const c = detachSubpanel(raw);
    store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
  };

  // proposeAudience: the job; the model proposes a description, never filters (research_agents).
  const propose = () =>
    step.run(async () => {
      // The description written in §01 is what the job is asked to turn into an audience.
      const typed = proposeText("", store.get().project);
      if (!typed) throw new Error(PROPOSE_EMPTY);
      await step.saved();
      const r = (await runJob("audiencePropose", proposePayload(store.get().project, typed), { title: PROPOSE_TITLE, warnMs: PROPOSE_WARN_MS })) as Parameters<typeof applyProposal>[2];
      if (isNativeResult(r)) { toast(PROPOSE_SAVED); return; }
      const a = applyProposal(store.get().project, typed, r || {});
      change(a.change);
      if (a.uncovered) toast(PROPOSE_UNCOVERED);
    }, (m) => (m === PROPOSE_EMPTY ? m : m + PROPOSE_FAILED_SUFFIX));

  return (
    <div className="mt-4 flex flex-col gap-3">
      {live.state === "loading" ? null : (
        <div data-aia={audiencePartAia("filters")}>
          {live.state === "ready" ? <LiveFilters live={live} /> : (
            <NotInAia title={t("research.audience.filterTitle")}>{`${live.text} ${t("research.audience.filtersNotInAia")}`}</NotInAia>
          )}
        </div>
      )}
      <div className="rounded-control border border-border bg-surface p-4">
        {step.failure ? (
          <div className="mb-4">
            <AiFailureCard failure={step.failure} title={t("research.audience.failedTitle")} onRetry={() => step.setFailure(null)} onContinue={(id) => void step.resume(id, () => toast(PROPOSE_SAVED))} />
          </div>
        ) : null}
        {leadOwnsAiStarts ? <AskLead what="Návrh cílové skupiny z popisu" /> : <AiButton disabled={step.busy} onClick={() => void propose()}>{t("research.audience.propose")}</AiButton>}
        {chips.length ? (
          <>
            <p className="mt-3 text-xs text-ink-muted">{live.state === "ready" ? t("research.audience.selectedFilters") : t("research.audience.storedFilters")}</p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {chips.map((c) => {
                const problem = problemOf.get(c.id);
                return (
                <li key={c.id} data-aia={audienceFilterAia(c.id) ?? undefined} data-filter-problem={problem ? true : undefined} className={`inline-flex items-center gap-1 rounded-sm border pl-2 text-xs ${problem ? "border-status-you-ink/40 bg-status-you-wash" : "border-signal-edge bg-signal-wash"}`}>
                  <b>{c.label}</b>: {c.text}
                  {problem ? <span className="font-medium text-status-you-ink"> · {t(problem.reason === "values" && !problem.noneKnown ? "research.audience.problemChipPartial" : "research.audience.problemChip")}</span> : null}
                  <button
                    type="button"
                    aria-label={tv("research.audience.removeFilter", { label: c.label })}
                    onClick={() => change(removeAudienceFactor(store.get().project, c.id))}
                    className="inline-flex size-6 shrink-0 items-center justify-center rounded-sm text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring"
                  >
                    ×
                  </button>
                </li>
                );
              })}
            </ul>
            {problems.length ? (
              <div role="note" data-filter-problems className="mt-2 rounded-control border border-status-you-ink/40 bg-status-you-wash p-3 text-xs leading-5">
                <p className="font-medium">{tv("research.audience.problemTitle", { version: String(version) })}</p>
                <ul className="mt-1 list-disc pl-5">
                  {problems.map((x) => (
                    <li key={x.id}>
                      {x.reason === "values"
                        ? tv(x.noneKnown ? "research.audience.problemValuesAll" : "research.audience.problemValues", { label: x.label, values: x.unknownValues.join(", ") })
                        : tv(PROBLEM_WORDS[x.reason], { label: x.label })}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
      {live.state === "ready" ? <Subpanels live={live} /> : null}
    </div>
  );
}

/** The factor editor over AIA's catalogue (filterEditor + factorEditor1793), and the preview. */
function LiveFilters({ live }: { live: Extract<Live, { state: "ready" }> }) {
  const { store, state } = useResearch();
  const [category, setCategory] = useState(DEFAULT_CATEGORY);
  const [query, setQuery] = useState("");
  const { categories, sensitive } = filterCategories(live.catalog);
  const { shown, total } = filterableFactors(live.catalog, category, searchKey(query));
  // Every filter edit here, the AI proposal's too, leaves a chosen subpanel behind (detachSubpanel).
  const change = (raw: Change) => {
    const c = detachSubpanel(raw);
    store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
  };
  return (
    <section className="rounded-control border border-border bg-surface p-4" aria-labelledby="aud-live-filters">
      <div className={EYEBROW}>{t("research.audience.filterTag")}</div>
      <h2 id="aud-live-filters" className="mt-1 text-base font-semibold">{t("research.audience.filterTitle")}</h2>
      <p className="mt-1 text-xs text-ink-muted">
        {tv("research.audience.liveFiltersIntro", { version: live.api.version_label })} {t("research.audience.liveLogic")}
      </p>
      <ChoiceChips
        className="mt-3"
        label={t("research.audience.categoryLabel")}
        options={[{ key: "all", label: t("research.audience.categoryAll") }, ...categories.map((c) => ({ key: c.id, label: c.label || c.id }))]}
        value={category}
        onChange={setCategory}
      />
      {sensitive ? <p className="mt-2 text-xs text-ink-muted">{tv("research.audience.sensitiveCount", { n: sensitive })}</p> : null}
      <Field label={t("research.audience.searchFactors")} className="mt-3">
        <TextInput value={query} onChange={(e) => setQuery(e.target.value)} />
      </Field>
      <p aria-live="polite" className="mt-2 text-xs text-ink-muted">{tv("research.audience.factorsShown", { shown: shown.length, total })}</p>
      {/* Factors as rows divided by hairlines, not cards inside the step's card (design system v3). */}
      <ul className="mt-2 flex flex-col divide-y divide-border border-y border-border">
        {shown.map((f) => (
          <li key={f.id}>
            <FactorEditor factor={f} project={state.project} onChange={change} />
          </li>
        ))}
      </ul>
      <Preview catalog={live.catalog} />
    </section>
  );
}

/**
 * A numeric factor's range (input-interactions I2, audit B6): two steppers bounded by the
 * population's own range, each also bounded by the other end, so a crossed range is refused at the
 * field rather than swapped as the population would. An unset end is "Bez omezení", said, and an end
 * is unset by its own button: the population's end then stands for it (setRange leaves it out).
 * Nothing typed is clamped. A stored end the stepper cannot show is said, never shown as no end.
 */
function RangeEditor({ factor, legend, lo, hi, disabled, onSave }: { factor: Factor; legend: string; lo: Json; hi: Json; disabled: boolean; onSave: (min: number | null, max: number | null) => void }) {
  const bounds = rangeBounds(factor);
  if (!bounds) return <p className="text-xs text-ink-muted">{t("research.audience.rangeUnknown")}</p>;
  const low = boundOf(lo);
  const high = boundOf(hi);
  const within = (v: number) => Math.min(Math.max(v, bounds.min), bounds.max);
  const side = (end: "min" | "max") => {
    const value = end === "min" ? low : high;
    const unreadable = endUnreadable(end === "min" ? lo : hi);
    const label = tv(end === "min" ? "research.audience.rangeFromOf" : "research.audience.rangeToOf", { factor: legend });
    const save = (v: number | null) => (end === "min" ? onSave(v, high) : onSave(low, v));
    return (
      <div className="flex flex-col gap-1">
        <span aria-hidden className="text-xs text-ink-muted">{t(end === "min" ? "research.audience.rangeMin" : "research.audience.rangeMax")}</span>
        <Stepper
          // Either end moving moves this field's bounds: it starts afresh, so a draft refused against
          // the old bounds never outlives them.
          key={`${String(low)}-${String(high)}`}
          value={value}
          label={label}
          min={end === "min" ? bounds.min : within(low ?? bounds.min)}
          max={end === "min" ? within(high ?? bounds.max) : bounds.max}
          decimals={bounds.decimals}
          showBounds={false}
          disabled={disabled}
          onCommit={save}
          note={value === null ? <span className="text-xs text-ink-muted">{t(unreadable ? "research.audience.rangeUnreadable" : "research.audience.rangeOpen")}</span> : undefined}
        />
        {/* Beside the field, not its note: a refused value replaces the note, and clearing the end
            is a way out of it. */}
        {value === null ? null : (
          <button type="button" disabled={disabled} aria-label={tv("research.audience.rangeClear", { label })} onClick={() => save(null)} className="min-h-6 self-start rounded-sm text-xs text-ink-muted underline hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring">
            {t("research.audience.rangeOpen")}
          </button>
        )}
      </div>
    );
  };
  return (
    <>
      <div className="flex flex-wrap items-start gap-4">
        {side("min")}
        {side("max")}
      </div>
      <p className="mt-1 text-xs text-ink-muted">
        {tv("research.audience.rangeHint", { range: rangeWords(bounds) })}
        {low !== null && high !== null ? ` ${t("research.audience.rangeOrder")}` : ""}
      </p>
    </>
  );
}

/** One factor: a range for a numeric one, its values (with counts) for any other. */
function FactorEditor({ factor, project, onChange }: { factor: Factor; project: ResearchProject; onChange: (c: Change) => void }) {
  const refusal = factorRefusal(factor);
  const legend = `${factor.label || factor.id}`;
  if (factor.kind === "numeric") {
    const { lo, hi } = storedRange(project, factor.id);
    return (
      <fieldset className="min-w-0 py-3" disabled={!!refusal}>
        <legend className="mb-1.5 text-sm font-medium">{legend}</legend>
        {refusal ? <p className="text-xs text-ink-muted">{refusal}</p> : null}
        <RangeEditor factor={factor} legend={legend} lo={lo} hi={hi} disabled={!!refusal} onSave={(min, max) => onChange(setRange(project, factor.id, min, max))} />
      </fieldset>
    );
  }
  const chosen = storedValues(project, factor.id);
  return (
    <fieldset className="min-w-0 py-3" disabled={!!refusal}>
      <legend className="mb-1.5 text-sm font-medium">{legend}</legend>
      {refusal ? <p className="text-xs text-ink-muted">{refusal}</p> : null}
      <ValueChips legend={legend} values={factor.values || []} chosen={chosen} disabled={!!refusal} onPick={(next) => onChange(setAudienceCategory(project, factor.id, next))} />
    </fieldset>
  );
}

/**
 * A categorical factor's values as toggle chips, each with how many people hold it (input-interactions
 * I3, audit B7); past VALUE_CHIPS_MAX, under a filter field. A stored value not on screen is kept.
 */
function ValueChips({ legend, values, chosen, disabled, onPick }: { legend: string; values: { value: string; count?: number }[]; chosen: Json[]; disabled: boolean; onPick: (values: Json[]) => void }) {
  const [query, setQuery] = useState("");
  const long = values.length > VALUE_CHIPS_MAX;
  const shown = long ? matchingValues(values, query) : values;
  const listed = shown.map((v) => v.value);
  return (
    <>
      {long ? (
        <>
          <Field label={tv("research.audience.searchValues", { factor: legend })}>
            <TextInput value={query} disabled={disabled} onChange={(e) => setQuery(e.target.value)} />
          </Field>
          <p className="mt-1 text-xs text-ink-muted">
            {/* Only the count is announced as the person types; the cut list's note is read once. */}
            <span aria-live="polite">{tv("research.audience.valuesShown", { shown: shown.length, total: values.length })}</span>
            {values.length >= CATALOGUE_TOP_VALUES ? ` ${tv("research.audience.valuesCut", { n: CATALOGUE_TOP_VALUES })}` : ""}
          </p>
        </>
      ) : null}
      <ChoiceChips
        multiple
        className={long ? "mt-2" : undefined}
        label={tv("research.audience.valuesOf", { factor: legend })}
        disabled={disabled}
        options={shown.map((v) => ({
          key: v.value,
          label: (
            <>
              {v.value}
              {v.count != null ? <span className="text-xs font-normal text-ink-muted">({tv("research.audience.valueCount", { count: v.count.toLocaleString("cs-CZ") })})</span> : null}
            </>
          ),
        }))}
        value={listed.filter((v) => chosen.some((c) => String(c) === v))}
        onChange={(picked) => onPick(pickValues(chosen, listed, picked))}
      />
    </>
  );
}

/** The words of "Lze vytáhnout" and the tone each verdict reads in (unknown never good). */
const FEASIBLE: Record<Feasibility["verdict"], { key: string; tone: string }> = {
  yes: { key: "research.audience.feasibleYes", tone: "text-status-done" },
  tight: { key: "research.audience.feasibleTight", tone: "text-status-you-ink" },
  no: { key: "research.audience.feasibleNo", tone: "text-status-fault" },
  unknown: { key: "research.audience.feasibleUnknown", tone: "text-ink-muted" },
};

/**
 * Proveditelnost (AUD9, spec vzorek/A5): counted by the API over AIA's population, through the run's
 * own functions, again after every change (useAudiencePreview), as three figures: whom the filters
 * select, the sample's n and whether it can be drawn. A count not answered is said, never 0.
 */
function Preview({ catalog }: { catalog: Catalog }) {
  const { state, stepHref } = useResearch();
  const p = state.project;
  const size = Number(p.n);
  const n = Number.isFinite(size) && size >= 1 ? size : null;
  const { answer, error, busy } = useAudiencePreview((p.audience.filters as Record<string, unknown>) || {}, n, population.audiencePreview);
  const verdict = feasibility(answer);
  const lines = answer ? filterCountLines(answer, catalog) : [];
  const unknown = t("research.audience.countUnknown");
  const failed = error
    ? error instanceof ApiError && error.code === "audience_preview_unavailable"
      ? t("research.audience.previewUnavailable")
      : tv("research.audience.previewFailed", { message: errorText(error) })
    : null;
  return (
    <section data-aia={audiencePartAia("preview")} aria-labelledby="aud-feasibility" className="mt-4 border-t border-border pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="aud-feasibility" className="text-sm font-semibold">{t("research.audience.feasibilityTitle")}</h3>
        <span className="text-xs text-ink-muted">{busy ? t("research.audience.previewRunning") : t("research.audience.feasibilityLive")}</span>
      </div>
      {/* Announced as it changes: the figures are the only answer a filter edit gets. */}
      <div aria-live="polite" aria-busy={busy} className={`mt-2 ${busy && answer ? "opacity-60" : ""}`}>
        {failed ? (
          <p className="rounded-control border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">{failed}</p>
        ) : (
          <>
            {/* One strip of three figures, not three cards inside the step's card (design system v3). */}
            <dl className="grid divide-y divide-border rounded-control border border-border bg-surface sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              <div className="p-3">
                <dt className="text-xs text-ink-muted">{t("research.audience.feasibilitySelected")}</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums">{answer?.selected_rows != null ? answer.selected_rows.toLocaleString("cs-CZ") : unknown}</dd>
                <dd className="text-xs text-ink-muted">{answer ? tv("research.audience.feasibilityOf", { rows: answer.population_rows.toLocaleString("cs-CZ") }) : null}</dd>
              </div>
              <div className="p-3">
                <dt className="text-xs text-ink-muted">{t("research.audience.feasibilitySample")}</dt>
                <dd className="mt-1 text-lg font-semibold tabular-nums">{n != null ? `N ${n.toLocaleString("cs-CZ")}` : t("research.audience.unset")}</dd>
                <dd className="text-xs">
                  {/* Client-side, as every stage link: a document load would drop an edit still waiting to save and the Lead's pane. */}
                  <Link className="text-signal underline" href={stageHref("sample", stepHref)}>{t("research.audience.feasibilitySampleEdit")}</Link>
                </dd>
              </div>
              <div className="p-3">
                <dt className="text-xs text-ink-muted">{t("research.audience.feasibilityDraw")}</dt>
                <dd className={`mt-1 text-lg font-semibold ${FEASIBLE[verdict.verdict].tone}`}>{t(FEASIBLE[verdict.verdict].key)}</dd>
                <dd className="text-xs text-ink-muted">{verdict.text}</dd>
              </div>
            </dl>
            {lines.length ? (
              <ul className="mt-2 text-xs text-ink-muted">
                {lines.map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            ) : null}
            {answer ? <p className="mt-1 text-xs text-ink-muted">{tv("research.audience.previewSeed", { seed: answer.seed })}</p> : null}
          </>
        )}
      </div>
    </section>
  );
}

/**
 * The 18 built-in subpanels: each a filter on one factor, chosen like any audience
 * (usePopulationSubpanel), by a click on its card, never by moving through them (a choice rewrites
 * the audience). A search above them (input-interactions I3, audit B9); the chosen one stays shown
 * whatever the search, and the count says what matched.
 */
function Subpanels({ live }: { live: Extract<Live, { state: "ready" }> }) {
  const { store, state } = useResearch();
  const [query, setQuery] = useState("");
  const current = String(state.project.audience.builtin_subpanel || "");
  const pick = (key: string) =>
    store.update(({ project }) => ({ project: applyPopulationSubpanel(normalizeEntry(project), key, live.subpanels) }), { reason: "population_subpanel", invalidateCheck: true });
  const all = live.api.subpanels;
  const matched = matchingSubpanels(all, query);
  const shown = all.filter((sp) => sp.key === current || matched.includes(sp));
  return (
    <div className="mt-3 flex flex-col gap-3">
      <section aria-labelledby="aud-subpanels">
        <h3 id="aud-subpanels" className="text-sm font-semibold">{t("research.audience.subpanelsTitle")}</h3>
        <p className="mt-1 text-xs text-ink-muted">{tv("research.audience.subpanelsIntro", { measured: live.api.subpanels_measured_on })}</p>
        <Field label={t("research.audience.searchSubpanels")} className="mt-2">
          <TextInput value={query} onChange={(e) => setQuery(e.target.value)} />
        </Field>
        {/* The search's only feedback, so it is announced as the person types. */}
        <p aria-live="polite" className="mt-1 text-xs text-ink-muted">{tv("research.audience.subpanelsShown", { shown: matched.length, total: all.length })}</p>
        <div role="radiogroup" aria-label={t("research.audience.subpanelsTitle")} className="mt-2 grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
          {shown.map((sp) => (
            <div key={sp.key} data-aia={audienceSubpanelAia(sp.key) ?? undefined} className="grid">
              <RadioCard checked={current === sp.key} disabled={sp.usable !== true} onSelect={() => current !== sp.key && pick(sp.key)} title={sp.name}>
                {tv("research.audience.subpanelRows", { rows: sp.measured_by_18_6_6.rows.toLocaleString("cs-CZ"), donors: sp.measured_by_18_6_6.unique_core_donors.toLocaleString("cs-CZ") })}
                {sp.usable === false ? <> · {tv("research.audience.subpanelUnusable", { reason: sp.reason || "?" })}</> : null}
                {sp.usable == null ? <> · {t("research.audience.subpanelUnknown")}</> : null}
              </RadioCard>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

/** A stored Discover's product and success criterion, read only: AIA cannot run the path (R4), so nothing here takes an edit. */
function DiscoverKept() {
  const { state } = useResearch();
  const a = state.project.audience;
  const rows = ([["discoverProduct", a.product_description], ["discoverSuccess", a.success_definition]] as const).filter(([, v]) => v);
  if (!rows.length) return null;
  return (
    <dl className="mt-2 grid gap-1 rounded-control border border-border bg-surface p-3 text-sm">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt className="text-xs text-ink-muted">{t(`research.audience.${k}`)}</dt>
          <dd className="whitespace-pre-wrap">{String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * "Souhrn cílové skupiny": what is chosen so far, and the readable summary (1795)
 * -- the same settings the preflight and the sampling use.
 */
function Summary({ project, strategy }: { project: ResearchProject; strategy: Strategy | null }) {
  const pairs = humanSummary(project.audience);
  const filters = humanFilters(project);
  const strat = strategy ? t(`research.audience.strategy${strategy[0]!.toUpperCase()}${strategy.slice(1)}`) : null;
  return (
    <aside aria-labelledby="aud-summary" className="flex flex-col gap-3 rounded-card border border-border bg-surface-raised p-3.5">
      <h2 id="aud-summary" className="text-sm font-semibold">{t("research.audience.summaryTitleV3")}</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 text-[13px]">
        <dt className="text-ink-muted">{t("research.audience.summaryStrategy")}</dt>
        <dd className={strat ? "font-medium" : "text-status-you-ink"}>{strat || t("research.audience.unset")}</dd>
      </dl>
      <div className="border-t border-border pt-3">
        <p className="text-xs text-ink-muted">{t("research.audience.summaryIntro")}</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {pairs.map(([k, v]) => (
            <Tag key={k}>
              <b>{k}:</b>&nbsp;{v}
            </Tag>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {filters.length ? (
            filters.map(([k, v]) => (
              <Tag key={k}>
                <b>{k}:</b>&nbsp;{v}
              </Tag>
            ))
          ) : (
            <p className="w-full rounded-control border border-signal-edge bg-signal-tint p-2.5 text-xs">{t("research.audience.summaryNone")}</p>
          )}
        </div>
      </div>
    </aside>
  );
}
