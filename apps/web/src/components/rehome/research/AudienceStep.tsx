"use client";

// 4. Audience / Cílová skupina, rebuilt (research-flow-rehome.md, chunk 5) and drawn
// as Studio v3 (studio-v3.md, chunk 6): the classic renderAudience (:374) under its
// three wrappers -- the branch banner (1785), the wizard's way on (1789) and the
// readable summary (1795) -- as one page of three questions that appear in turn
// (source, population, strategy) instead of screens with back buttons. What each
// control does to the project is src/research/audience.ts, parity-tested
// against the original; this file only draws it.
//
// In AIA (ADR 0018) the step keeps what it can decide without 18.6.6: the source,
// the whole population, the outcome-based definition, the AI's proposed
// description, and the summary. Since panel-grounded-respondents 6e the factor
// catalogue and its filters, the feasibility preview and the built-in subpanels
// are AIA's own, from its population (GET /population/audience-catalogue, POST
// /population/audience-preview); where this deployment has none, the step says
// why, as before. Special panels and customer audience upload were 18.6.6's
// audience store, and still say they are not in AIA. Whether a run applies the
// filters is the run's pin, and readiness says it ("audience").

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, type AudienceCatalogue, population } from "@/lib/api";
import { isNativeResult } from "@/lib/research-agent-jobs";
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
  audienceView,
  chooseAudience,
  discoverText,
  factorRefusal,
  filterCategories,
  filterChips,
  filterableFactors,
  humanFilters,
  humanSummary,
  liveCatalog,
  liveSubpanels,
  liveVerdict,
  proposePayload,
  proposeText,
  rangeOf,
  removeAudienceFactor,
  searchKey,
  selectedValues,
  setAnalyticsChoice,
  setAudienceCategory,
  setAudienceEntry,
  setDiscoverField,
  setRange,
} from "@/research/audience";
import type { ResearchProject } from "@/research/model";
import { Icon } from "../icons";
import { ActionDock, RadioCard, StepSection } from "../step";
import { AiButton, Button, Chip, Field, Tag, TextArea, TextInput } from "../ui";
import { useResearch } from "./context";
import { InspectorSlot } from "./Inspector";
import { AskLead, useLeadOwnsAiStarts } from "./AskLead";
import { AiFailureCard, useAiStep } from "./useAiStep";

/**
 * What the Research Lead can name on this screen (artifact-audience § 4): the description, the
 * filters, one factor by its catalogue id, one built-in subpanel, the preview. The workbench
 * focuses them through lib/lead.ts focusSelector's `data-aia` fall-through.
 */
export const AUDIENCE_TARGET = { definition: "audience:definition", filters: "audience:filters", preview: "audience:preview" } as const;
/**
 * One stored filter's target, by its factor's catalogue id (`audience:filter:kraj`). It sits on the
 * filter's chip under "Vybrané filtry", which every stored filter has whatever category, search or
 * 80-factor cut the editor shows; a factor's editor may be off screen.
 */
export const audienceFactorTarget = (factorId: string) => `audience:filter:${factorId}`;
/** One built-in subpanel's target, by its key (`audience:subpanel:young_18_29`). */
export const audienceSubpanelTarget = (key: string) => `audience:subpanel:${key}`;

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
        setLive({ state: "missing", text: tv("research.audience.catalogueFailed", { message: e instanceof Error ? e.message : String(e) }) });
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
  const p = state.project;
  const view = audienceView(p);
  const ready = audienceReady(p);
  const entry = String(ui(p).audience_entry || "choose");
  const choice = String(ui(p).analytics_choice || "");
  const strategy = (p.audience.strategy || "population") as Strategy;
  const live = useLiveAudience();
  const isLive = live.state === "ready";

  const apply = (c: Change | null) => {
    if (!c) return;
    store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
  };
  // Choosing what is already chosen changes nothing: the classic tiles were not shown then.
  const pickSource = (k: "own" | "analytics") => entry !== k && apply(setAudienceEntry(store.get().project, k));
  const pickPopulation = (k: "cz18" | "cz_coming" | "special") => choice !== k && apply(setAnalyticsChoice(store.get().project, k));
  const pickStrategy = (k: Strategy) => (p.audience.strategy || "population") !== k && apply(chooseAudience(store.get().project, k));

  return (
    <div className="flex max-w-[82.5rem] flex-col gap-4">
      <InspectorSlot>
        <Summary project={p} entry={entry} choice={choice} strategy={view === "cz18" ? strategy : null} />
      </InspectorSlot>

      <div className="flex min-w-0 flex-col gap-4">
        {entry === "analytics" ? (
          <p className="rounded-card border border-signal-edge bg-signal-tint p-3 text-[13px] leading-5">
            <b>{t("research.audience.bannerPopulation")}</b> {t("research.audience.bannerPopulationText")} <b>{t("research.audience.bannerIdeal")}</b>{" "}
            {t("research.audience.bannerIdealText")}
          </p>
        ) : null}

        <StepSection n={1} lead done={entry !== "choose"} title={t("research.audience.chooseTitle")}>
          <div role="radiogroup" aria-label={t("research.audience.chooseTitle")} className="grid gap-3 md:grid-cols-2">
            <RadioCard checked={entry === "own"} onSelect={() => pickSource("own")} title={t("research.audience.own")}>
              {t("research.audience.ownText")}
            </RadioCard>
            <RadioCard checked={entry === "analytics"} onSelect={() => pickSource("analytics")} title={t("research.audience.analytics")}>
              {t("research.audience.analyticsText")}
            </RadioCard>
          </div>
          {view === "own" ? (
            <div className="mt-3 flex flex-col gap-3">
              <NotInAia title={t("research.audience.own")}>{t("research.audience.ownNotInAia")}</NotInAia>
              {p.audience.dataset_id ? (
                <div className="rounded-control border border-border bg-surface p-3">
                  <p className="text-sm">
                    <b>{t("research.audience.storedDataset")}</b> {String(p.audience.dataset_name || p.audience.dataset_id)}
                  </p>
                  <p className="mt-1 text-xs text-ink-muted">{t("research.audience.storedNotUsed")}</p>
                </div>
              ) : null}
            </div>
          ) : null}
        </StepSection>

        {entry === "analytics" ? (
          <StepSection n={2} done={Boolean(choice)} title={t("research.audience.populationTitle")} hint={t("research.audience.populationHint")}>
            <div role="radiogroup" aria-label={t("research.audience.populationTitle")} className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(200px,1fr))]">
              <RadioCard checked={choice === "cz18"} onSelect={() => pickPopulation("cz18")} title={<>{t("research.audience.cz18")} <Tagged tone="done">{t("research.audience.ready")}</Tagged></>}>
                {t("research.audience.cz18Text")}
              </RadioCard>
              <RadioCard checked={choice === "cz_coming"} onSelect={() => pickPopulation("cz_coming")} title={<>{t("research.audience.czComing")} <Tagged tone="you">{t("research.audience.comingSoon")}</Tagged></>}>
                {t("research.audience.czComingText")}
              </RadioCard>
              <RadioCard checked={choice === "special"} onSelect={() => pickPopulation("special")} title={<>{t("research.audience.special")} {isLive ? null : <Tagged tone="you">{t("research.audience.notInAiaChip")}</Tagged>}</>}>
                {isLive ? t("research.audience.liveSpecialText") : t("research.audience.specialText")}
              </RadioCard>
            </div>
            {view === "cz_coming" ? (
              <p className="mt-3 rounded-control border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">
                <b>{t("research.audience.czComingTitle")}</b> · {t("research.audience.czComingNote")}
              </p>
            ) : null}
            {view === "special" && live.state === "ready" ? <Subpanels live={live} /> : null}
            {view === "special" && live.state !== "ready" ? (
              <div className="mt-3 flex flex-col gap-3">
                <NotInAia title={t("research.audience.special")}>{t("research.audience.specialNotInAia")}</NotInAia>
                {p.audience.special_catalog_key ? (
                  <div className="rounded-control border border-border bg-surface p-3">
                    <p className="text-sm">
                      <b>{t("research.audience.selected")}</b> {String(p.audience.dataset_name || p.audience.description || p.audience.special_catalog_key)}
                    </p>
                    <p className="mt-1 text-xs text-ink-muted">{t("research.audience.storedNotUsed")}</p>
                  </div>
                ) : null}
              </div>
            ) : null}
          </StepSection>
        ) : null}

        {view === "cz18" ? (
          <StepSection n={3} done title={t("research.audience.strategyTitle")} hint={t("research.audience.czIntroBefore")}>
            <div role="radiogroup" aria-label={t("research.audience.strategyTitle")} className="grid gap-2 md:grid-cols-3">
              {([["population", "strategyPopulation"], ["filters", "strategyFilters"], ["discover", "strategyDiscover"]] as const).map(([k, key]) => (
                <RadioCard
                  key={k}
                  checked={strategy === k}
                  onSelect={() => pickStrategy(k)}
                  title={<>{t(`research.audience.${key}`)} {k === "filters" && !isLive ? <Tagged tone="you">{t("research.audience.notInAiaChip")}</Tagged> : null}</>}
                >
                  {t(`research.audience.${key}Text`)}
                </RadioCard>
              ))}
            </div>
            {p.audience.strategy === "filters" ? <FilterEditor live={live} /> : null}
            {p.audience.strategy === "discover" ? <DiscoverEditor /> : null}
          </StepSection>
        ) : null}

        <ActionDock
          back={{ href: stepHref("questionnaire"), label: `3. ${t("aia.stages.questionnaire")}` }}
          ready={ready}
          note={ready ? (isLive ? t("research.audience.liveCheck") : t("research.audience.checkNotInAia")) : t("research.audience.nextHint")}
        >
          <Button variant="primary" className="!rounded-control" disabled={!ready} onClick={() => router.push(stepHref("persona"))}>
            {t("research.audience.next")}
            <Icon name="next" size={14} />
          </Button>
        </ActionDock>
      </div>
    </div>
  );
}

/** A small status tag beside a choice's title. */
function Tagged({ tone, children }: { tone: "done" | "you"; children: string }) {
  return (
    <span className={`ml-1 whitespace-nowrap rounded-md px-1.5 py-px align-middle font-mono text-[10px] font-semibold tracking-[0.04em] ${tone === "done" ? "bg-status-done/14 text-status-done" : "bg-status-you-wash text-status-you-ink"}`}>
      {children}
    </span>
  );
}

const ui = (p: ResearchProject) => (p.ui_state || {}) as Record<string, unknown>;

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
  const [text, setText] = useState(String(state.project.audience.description || ""));
  const chips = filterChips(state.project, live.state === "ready" ? live.catalog : null);
  const change = (c: Change) => store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });

  // proposeAudience: the job; the model proposes a description, never filters (research_agents).
  const propose = () =>
    step.run(async () => {
      const typed = proposeText(text, store.get().project);
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
        <div data-aia={AUDIENCE_TARGET.filters}>
          {live.state === "ready" ? <LiveFilters live={live} /> : (
            <NotInAia title={t("research.audience.filterTitle")}>{`${live.text} ${t("research.audience.filtersNotInAia")}`}</NotInAia>
          )}
        </div>
      )}
      <section data-aia={AUDIENCE_TARGET.definition} className="rounded-control border border-border bg-surface p-4" aria-labelledby="aud-filters">
        {step.failure ? (
          <div className="mb-4">
            <AiFailureCard failure={step.failure} title={t("research.audience.failedTitle")} onRetry={() => step.setFailure(null)} onContinue={(id) => void step.resume(id, () => toast(PROPOSE_SAVED))} />
          </div>
        ) : null}
        <div className={EYEBROW}>{t("research.audience.filterTag")}</div>
        <h2 id="aud-filters" className="mt-1 text-base font-semibold">{t("research.audience.describeTitle")}</h2>
        <Field label={t("research.audience.describe")} className="mt-3">
          <div className="flex flex-wrap gap-2">
            <TextInput className="min-w-64 flex-1" value={text} placeholder={t("research.audience.describePlaceholder")} onChange={(e) => setText(e.target.value)} />
            {!leadOwnsAiStarts ? <AiButton disabled={step.busy} onClick={() => void propose()}>{t("research.audience.propose")}</AiButton> : null}
          </div>
        </Field>
        {leadOwnsAiStarts ? <AskLead className="mt-2" what="Návrh cílové skupiny z popisu" /> : null}
        {chips.length ? (
          <>
            <p className="mt-3 text-xs text-ink-muted">{live.state === "ready" ? t("research.audience.selectedFilters") : t("research.audience.storedFilters")}</p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {chips.map((c) => (
                <li key={c.id} data-aia={audienceFactorTarget(c.id)} className="inline-flex items-center gap-1 rounded-sm border border-signal-edge bg-signal-wash py-0.5 pl-2 pr-0.5 text-xs">
                  <b>{c.label}</b>: {c.text}
                  <button
                    type="button"
                    aria-label={tv("research.audience.removeFilter", { label: c.label })}
                    onClick={() => change(removeAudienceFactor(store.get().project, c.id))}
                    className="rounded-sm px-1 text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </section>
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
  const change = (c: Change) => store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
  return (
    <section className="rounded-control border border-border bg-surface p-4" aria-labelledby="aud-live-filters">
      <div className={EYEBROW}>{t("research.audience.filterTag")}</div>
      <h2 id="aud-live-filters" className="mt-1 text-base font-semibold">{t("research.audience.filterTitle")}</h2>
      <p className="mt-1 text-xs text-ink-muted">
        {tv("research.audience.liveFiltersIntro", { version: live.api.version_label })} {t("research.audience.liveLogic")}
      </p>
      <div role="group" aria-label={t("research.audience.filterTitle")} className="mt-3 flex flex-wrap gap-1.5">
        {[{ id: "all", label: t("research.audience.categoryAll") }, ...categories].map((c) => (
          <Button key={c.id} small variant={category === c.id ? "primary" : "secondary"} aria-pressed={category === c.id} onClick={() => setCategory(c.id)}>
            {c.label || c.id}
          </Button>
        ))}
      </div>
      {sensitive ? <p className="mt-2 text-xs text-ink-muted">{tv("research.audience.sensitiveCount", { n: sensitive })}</p> : null}
      <Field label={t("research.audience.searchFactors")} className="mt-3">
        <TextInput value={query} onChange={(e) => setQuery(e.target.value)} />
      </Field>
      <p className="mt-2 text-xs text-ink-muted">{tv("research.audience.factorsShown", { shown: shown.length, total })}</p>
      <ul className="mt-2 flex flex-col gap-2">
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

/** One factor: a range for a numeric one, its values (with counts) for any other. */
function FactorEditor({ factor, project, onChange }: { factor: Factor; project: ResearchProject; onChange: (c: Change) => void }) {
  const refusal = factorRefusal(factor);
  const legend = `${factor.label || factor.id}`;
  if (factor.kind === "numeric") {
    const { lo, hi } = rangeOf(project, factor.id);
    const commit = (min: string, max: string) => onChange(setRange(project, factor.id, min, max));
    return (
      <fieldset className="rounded-control border border-border p-3" disabled={!!refusal}>
        <legend className="px-1 text-sm font-medium">{legend}</legend>
        {refusal ? <p className="text-xs text-ink-muted">{refusal}</p> : null}
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t("research.audience.rangeMin")}>
            <TextInput key={`lo-${String(lo)}`} type="number" disabled={!!refusal} className="w-28" defaultValue={lo == null ? "" : String(lo)} onBlur={(e) => commit(e.target.value, hi == null ? "" : String(hi))} />
          </Field>
          <Field label={t("research.audience.rangeMax")}>
            <TextInput key={`hi-${String(hi)}`} type="number" disabled={!!refusal} className="w-28" defaultValue={hi == null ? "" : String(hi)} onBlur={(e) => commit(lo == null ? "" : String(lo), e.target.value)} />
          </Field>
        </div>
        {factor.min != null && factor.max != null ? (
          <p className="mt-1 text-xs text-ink-muted">{tv("research.audience.rangeHint", { min: factor.min, max: factor.max })}</p>
        ) : null}
      </fieldset>
    );
  }
  const chosen = selectedValues(project, factor.id);
  const toggle = (value: string, on: boolean) => {
    const next = new Set(chosen);
    if (on) next.add(value);
    else next.delete(value);
    onChange(setAudienceCategory(project, factor.id, [...next]));
  };
  return (
    <fieldset className="rounded-control border border-border p-3" disabled={!!refusal}>
      <legend className="px-1 text-sm font-medium">{legend}</legend>
      {refusal ? <p className="text-xs text-ink-muted">{refusal}</p> : null}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {(factor.values || []).map((v) => (
          <label key={v.value} className="inline-flex items-center gap-1.5 text-sm">
            <input type="checkbox" disabled={!!refusal} checked={chosen.has(v.value)} onChange={(e) => toggle(v.value, e.target.checked)} />
            {v.value}
            {v.count != null ? <span className="text-xs text-ink-muted">({tv("research.audience.valueCount", { count: v.count.toLocaleString("cs-CZ") })})</span> : null}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** The feasibility preview: counted by the API over AIA's population, through the run's own functions. */
function Preview({ catalog }: { catalog: Catalog }) {
  const { store } = useResearch();
  const [answer, setAnswer] = useState<{ ok: boolean; lines: string[]; seed?: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const check = async () => {
    setBusy(true);
    const p = store.get().project;
    const n = Number(p.n);
    try {
      const r = await population.audiencePreview((p.audience.filters as Record<string, unknown>) || {}, Number.isFinite(n) && n >= 1 ? n : null);
      setAnswer({ ...liveVerdict(r, catalog), seed: r.seed });
    } catch (e: unknown) {
      if (e instanceof ApiError && e.code === "audience_preview_unavailable") setAnswer({ ok: false, lines: [t("research.audience.previewUnavailable")] });
      else setAnswer({ ok: false, lines: [tv("research.audience.previewFailed", { message: e instanceof Error ? e.message : String(e) })] });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div data-aia={AUDIENCE_TARGET.preview} className="mt-4 border-t border-border pt-3">
      <Button disabled={busy} onClick={() => void check()}>
        {busy ? t("research.audience.previewRunning") : t("research.audience.previewButton")}
      </Button>
      {answer ? (
        <div role="status" className={`mt-2 rounded-control border p-3 text-sm ${answer.ok ? "border-signal-edge bg-signal-tint" : "border-status-you-ink/40 bg-status-you-wash"}`}>
          {answer.lines.map((l) => (
            <p key={l}>{l}</p>
          ))}
          {answer.seed != null ? <p className="mt-1 text-xs text-ink-muted">{tv("research.audience.previewSeed", { seed: answer.seed })}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

/** The 18 built-in subpanels: each a filter on one factor, chosen like any audience (usePopulationSubpanel). */
function Subpanels({ live }: { live: Extract<Live, { state: "ready" }> }) {
  const { store, state } = useResearch();
  const current = String(state.project.audience.builtin_subpanel || "");
  const pick = (key: string) =>
    store.update(({ project }) => ({ project: applyPopulationSubpanel(project, key, live.subpanels) }), { reason: "population_subpanel", invalidateCheck: true });
  return (
    <div className="mt-3 flex flex-col gap-3">
      <section aria-labelledby="aud-subpanels">
        <h3 id="aud-subpanels" className="text-sm font-semibold">{t("research.audience.subpanelsTitle")}</h3>
        <p className="mt-1 text-xs text-ink-muted">{tv("research.audience.subpanelsIntro", { measured: live.api.subpanels_measured_on })}</p>
        <div role="radiogroup" aria-label={t("research.audience.subpanelsTitle")} className="mt-2 grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
          {live.api.subpanels.map((sp) => (
            <div key={sp.key} data-aia={audienceSubpanelTarget(sp.key)} className="grid">
              <RadioCard checked={current === sp.key} disabled={sp.usable !== true} onSelect={() => current !== sp.key && pick(sp.key)} title={sp.name}>
                {tv("research.audience.subpanelRows", { rows: sp.measured_by_18_6_6.rows.toLocaleString("cs-CZ"), donors: sp.measured_by_18_6_6.unique_core_donors.toLocaleString("cs-CZ") })}
                {sp.usable === false ? <> · {tv("research.audience.subpanelUnusable", { reason: sp.reason || "?" })}</> : null}
                {sp.usable == null ? <> · {t("research.audience.subpanelUnknown")}</> : null}
              </RadioCard>
            </div>
          ))}
        </div>
      </section>
      <NotInAia title={t("research.audience.special")}>{t("research.audience.specialPanelsNotInAia")}</NotInAia>
    </div>
  );
}

/** discoverEditor: what the product is and what "ideal" means, for the outcome-based segment. */
function DiscoverEditor() {
  const { store, state } = useResearch();
  const d = discoverText(state.project);
  return (
    <section className="mt-4 rounded-control border border-border bg-surface p-4" aria-labelledby="aud-discover">
      <h2 id="aud-discover" className="text-base font-semibold">{t("research.audience.discoverTitle")}</h2>
      <Field label={t("research.audience.discoverProduct")} className="mt-3">
        <TextArea value={d.product} placeholder={t("research.audience.discoverProductPlaceholder")} onChange={(e) => store.update(({ project }) => ({ project: setDiscoverField(project, "product_description", e.target.value) }))} />
      </Field>
      <Field label={t("research.audience.discoverSuccess")} className="mt-3">
        <TextArea value={d.success} placeholder={t("research.audience.discoverSuccessPlaceholder")} onChange={(e) => store.update(({ project }) => ({ project: setDiscoverField(project, "success_definition", e.target.value) }))} />
      </Field>
      <p className="mt-3 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm leading-6">
        <strong>{t("research.audience.discoverAdviceBold")}</strong> {t("research.audience.discoverAdvice")}
      </p>
    </section>
  );
}

/**
 * "Souhrn cílové skupiny": what is chosen so far, and the readable summary (1795)
 * -- the same settings the preflight and the sampling use.
 */
function Summary({ project, entry, choice, strategy }: { project: ResearchProject; entry: string; choice: string; strategy: Strategy | null }) {
  const pairs = humanSummary(project.audience);
  const filters = humanFilters(project);
  const none = t("research.audience.unset");
  const source = entry === "own" ? t("research.audience.own") : entry === "analytics" ? t("research.audience.analytics") : null;
  const population = entry !== "analytics" ? null : choice === "cz18" ? t("research.audience.cz18") : choice === "cz_coming" ? t("research.audience.czComing") : choice === "special" ? t("research.audience.special") : null;
  const strat = strategy ? t(`research.audience.strategy${strategy[0]!.toUpperCase()}${strategy.slice(1)}`) : null;
  return (
    <aside aria-labelledby="aud-summary" className="flex flex-col gap-3 rounded-card border border-border bg-surface-raised p-3.5">
      <h2 id="aud-summary" className="text-sm font-semibold">{t("research.audience.summaryTitleV3")}</h2>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[13px]">
        {([["summarySource", source], ["summaryPopulation", population], ["summaryStrategy", strat]] as const).map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-ink-muted">{t(`research.audience.${k}`)}</dt>
            <dd className={v ? "font-medium" : "text-status-you-ink"}>{v || none}</dd>
          </div>
        ))}
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
