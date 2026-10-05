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
// description, and the summary. What 18.6.6 computed from its licensed panel or
// its own audience store -- the factor catalogue and its filters, the feasibility
// preview, the special subpanels, customer audience upload and preflight -- is
// not in AIA, and each says so where the person meets it. A choice stored before
// (a migrated study's filters or dataset) stays visible, and a run in AIA says it
// does not use it (research readiness: "audience").

import { useRouter } from "next/navigation";
import { useState } from "react";

import { isNativeResult } from "@/lib/research-agent-jobs";
import { t, tv } from "@/i18n/t";
import {
  type Change,
  PROPOSE_EMPTY,
  PROPOSE_FAILED_SUFFIX,
  PROPOSE_TITLE,
  PROPOSE_UNCOVERED,
  PROPOSE_WARN_MS,
  type Strategy,
  applyProposal,
  audienceReady,
  audienceView,
  chooseAudience,
  discoverText,
  filterChips,
  humanFilters,
  humanSummary,
  proposePayload,
  proposeText,
  removeAudienceFactor,
  setAnalyticsChoice,
  setAudienceEntry,
  setDiscoverField,
} from "@/research/audience";
import type { ResearchProject } from "@/research/model";
import { Icon } from "../icons";
import { ActionDock, RadioCard, StepSection } from "../step";
import { AiButton, Button, Chip, Field, Tag, TextArea, TextInput } from "../ui";
import { useResearch } from "./context";
import { AiFailureCard, useAiStep } from "./useAiStep";

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

export function AudienceStep() {
  const { store, state, stepHref } = useResearch();
  const router = useRouter();
  const p = state.project;
  const view = audienceView(p);
  const ready = audienceReady(p);
  const entry = String(ui(p).audience_entry || "choose");
  const choice = String(ui(p).analytics_choice || "");
  const strategy = (p.audience.strategy || "population") as Strategy;

  const apply = (c: Change | null) => {
    if (!c) return;
    store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
  };
  // Choosing what is already chosen changes nothing: the classic tiles were not shown then.
  const pickSource = (k: "own" | "analytics") => entry !== k && apply(setAudienceEntry(store.get().project, k));
  const pickPopulation = (k: "cz18" | "cz_coming" | "special") => choice !== k && apply(setAnalyticsChoice(store.get().project, k));
  const pickStrategy = (k: Strategy) => (p.audience.strategy || "population") !== k && apply(chooseAudience(store.get().project, k));

  return (
    <div className="flex max-w-[82.5rem] flex-wrap items-start gap-6">
      <Summary project={p} entry={entry} choice={choice} strategy={view === "cz18" ? strategy : null} />

      <div className="order-1 flex min-w-0 flex-[999_1_520px] flex-col gap-4">
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
              <RadioCard checked={choice === "special"} onSelect={() => pickPopulation("special")} title={<>{t("research.audience.special")} <Tagged tone="you">{t("research.audience.notInAiaChip")}</Tagged></>}>
                {t("research.audience.specialText")}
              </RadioCard>
            </div>
            {view === "cz_coming" ? (
              <p className="mt-3 rounded-control border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">
                <b>{t("research.audience.czComingTitle")}</b> · {t("research.audience.czComingNote")}
              </p>
            ) : null}
            {view === "special" ? (
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
            <div role="radiogroup" aria-label={t("research.audience.strategyTitle")} className="flex flex-col gap-2">
              {([["population", "strategyPopulation"], ["filters", "strategyFilters"], ["discover", "strategyDiscover"]] as const).map(([k, key]) => (
                <RadioCard
                  key={k}
                  checked={strategy === k}
                  onSelect={() => pickStrategy(k)}
                  title={<>{t(`research.audience.${key}`)} {k === "filters" ? <Tagged tone="you">{t("research.audience.notInAiaChip")}</Tagged> : null}</>}
                >
                  {t(`research.audience.${key}Text`)}
                </RadioCard>
              ))}
            </div>
            {p.audience.strategy === "filters" ? <FilterEditor /> : null}
            {p.audience.strategy === "discover" ? <DiscoverEditor /> : null}
          </StepSection>
        ) : null}

        <ActionDock
          back={{ href: stepHref("questionnaire"), label: `3. ${t("aia.stages.questionnaire")}` }}
          ready={ready}
          note={ready ? t("research.audience.checkNotInAia") : t("research.audience.nextHint")}
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
 * filterEditor without its catalogue: the factors, their values and counts were
 * 18.6.6's licensed panel, which AIA does not have. What is kept is what needs no
 * panel -- the filters a study already stores (removable), and the AI's proposed
 * description of the audience (a native job, ADR 0016/0018).
 */
function FilterEditor() {
  const { store, state, runJob, toast } = useResearch();
  const step = useAiStep();
  const [text, setText] = useState(String(state.project.audience.description || ""));
  const chips = filterChips(state.project, null);
  const change = (c: Change) => store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });

  // proposeAudience: the job; the model proposes a description, never filters (research_agents).
  const propose = () =>
    step.run(async () => {
      const typed = proposeText(text, store.get().project);
      if (!typed) throw new Error(PROPOSE_EMPTY);
      await step.saved();
      const r = (await runJob("audiencePropose", proposePayload(store.get().project, typed), { title: PROPOSE_TITLE, warnMs: PROPOSE_WARN_MS })) as Parameters<typeof applyProposal>[2];
      if (isNativeResult(r)) { toast("Návrh audience je uložený. Zkontrolujte popis a omezení."); return; }
      const a = applyProposal(store.get().project, typed, r || {});
      change(a.change);
      if (a.uncovered) toast(PROPOSE_UNCOVERED);
    }, (m) => (m === PROPOSE_EMPTY ? m : m + PROPOSE_FAILED_SUFFIX));

  return (
    <div className="mt-4 flex flex-col gap-3">
      <NotInAia title={t("research.audience.filterTitle")}>{t("research.audience.filtersNotInAia")}</NotInAia>
      <section className="rounded-control border border-border bg-surface p-4" aria-labelledby="aud-filters">
        {step.failure ? (
          <div className="mb-4">
            <AiFailureCard failure={step.failure} title={t("research.audience.failedTitle")} onRetry={() => step.setFailure(null)} />
          </div>
        ) : null}
        <div className={EYEBROW}>{t("research.audience.filterTag")}</div>
        <h2 id="aud-filters" className="mt-1 text-base font-semibold">{t("research.audience.describeTitle")}</h2>
        <Field label={t("research.audience.describe")} className="mt-3">
          <div className="flex flex-wrap gap-2">
            <TextInput className="min-w-64 flex-1" value={text} placeholder={t("research.audience.describePlaceholder")} onChange={(e) => setText(e.target.value)} />
            <AiButton disabled={step.busy} onClick={() => void propose()}>{t("research.audience.propose")}</AiButton>
          </div>
        </Field>
        {chips.length ? (
          <>
            <p className="mt-3 text-xs text-ink-muted">{t("research.audience.storedFilters")}</p>
            <ul className="mt-1 flex flex-wrap gap-1.5">
              {chips.map((c) => (
                <li key={c.id} className="inline-flex items-center gap-1 rounded-sm border border-signal-edge bg-signal-wash py-0.5 pl-2 pr-0.5 text-xs">
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
    <aside aria-labelledby="aud-summary" className="sticky top-60 order-2 flex flex-[1_1_280px] flex-col gap-3 rounded-card border border-border bg-surface-raised p-4">
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
