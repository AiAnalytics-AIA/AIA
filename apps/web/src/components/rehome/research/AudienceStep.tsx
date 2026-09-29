"use client";

// 4. Audience / Cílová skupina, rebuilt (research-flow-rehome.md, chunk 5): the
// classic renderAudience (:374) under its three wrappers -- the branch banner
// (1785), the wizard's way on (1789) and the readable summary (1795). What each
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
  analyticsBack,
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
import { Button, Chip, Field, Tag, TextArea, TextInput } from "../ui";
import { useResearch } from "./context";
import { AiFailureCard, useAiStep } from "./useAiStep";

const CARD = "rounded-md border border-border bg-surface-raised p-5";
const NOT_IN_AIA = "rounded-md border border-status-you-ink/40 bg-status-you-wash p-5";
const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint";
const TILE = "flex flex-col items-start gap-2 rounded-sm border p-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

/** A capability 18.6.6 had and AIA does not, said where the person meets it. */
function NotInAia({ title, children }: { title: string; children: string }) {
  return (
    <section className={NOT_IN_AIA}>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold">{title}</h2>
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

  const apply = (c: Change | null) => {
    if (!c) return;
    store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
  };
  const toPersona = () => {
    router.push(stepHref("persona"));
  };
  const backToSource = (
    <Button small variant="quiet" icon="back" onClick={() => apply(setAudienceEntry(store.get().project, "choose"))}>
      {t("research.audience.backSource")}
    </Button>
  );
  const backToAnalytics = (
    <Button small variant="quiet" icon="back" onClick={() => apply(analyticsBack(store.get().project))}>
      {t("research.audience.backAnalytics")}
    </Button>
  );
  // The classic "Zkontrolovat audience" asked 18.6.6 to count the audience in its panel.
  const goOn = (label: string, disabled = false) => (
    <div className="mt-3">
      <Button variant="primary" disabled={disabled} onClick={toPersona}>{label}</Button>
      <p className="mt-2 text-xs text-ink-muted">{t("research.audience.checkNotInAia")}</p>
    </div>
  );

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      {ui(p).audience_entry === "analytics" ? (
        <p className="rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm leading-6">
          <b>{t("research.audience.bannerPopulation")}</b> {t("research.audience.bannerPopulationText")} <b>{t("research.audience.bannerIdeal")}</b>{" "}
          {t("research.audience.bannerIdealText")}
        </p>
      ) : null}

      {view === "choose" ? (
        <section className={CARD} aria-labelledby="aud-choose">
          <h2 id="aud-choose" className="text-lg font-semibold">{t("research.audience.chooseTitle")}</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {([["own", t("research.audience.own"), t("research.audience.ownText")], ["analytics", t("research.audience.analytics"), t("research.audience.analyticsText")]] as const).map(([k, title, text], i) => (
              <button key={k} type="button" className={`${TILE} border-border-strong bg-surface hover:bg-surface-sunken`} onClick={() => apply(setAudienceEntry(store.get().project, k))}>
                <span className="font-mono text-xs text-ink-faint">{i + 1}</span>
                <span className="text-sm font-semibold">{title}</span>
                <span className="text-sm text-ink-muted">{text}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {view === "own" ? (
        <>
          <div>{backToSource}</div>
          <NotInAia title={t("research.audience.own")}>{t("research.audience.ownNotInAia")}</NotInAia>
          {p.audience.dataset_id ? (
            <section className={CARD}>
              <p className="text-sm">
                <b>{t("research.audience.storedDataset")}</b> {String(p.audience.dataset_name || p.audience.dataset_id)}
              </p>
              <p className="mt-1 text-xs text-ink-muted">{t("research.audience.storedNotUsed")}</p>
              {goOn(t("research.audience.toPersona"), !ready)}
            </section>
          ) : null}
        </>
      ) : null}

      {view === "analytics" ? (
        <>
          <div>{backToSource}</div>
          <section className={CARD} aria-labelledby="aud-analytics">
            <h2 id="aud-analytics" className="text-lg font-semibold">{t("research.audience.analytics")}</h2>
            <p className="mt-1 text-sm text-ink-muted">{t("research.audience.analyticsIntro")}</p>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {([
                ["cz18", t("research.audience.cz18"), t("research.audience.cz18Text"), <Chip key="c" tone="done">{t("research.audience.ready")}</Chip>],
                ["cz_coming", t("research.audience.czComing"), t("research.audience.czComingText"), <Chip key="c" tone="you">{t("research.audience.comingSoon")}</Chip>],
                ["special", t("research.audience.special"), t("research.audience.specialText"), <Chip key="c" tone="you">{t("research.audience.notInAiaChip")}</Chip>],
              ] as const).map(([k, title, text, chip], i) => (
                <button key={k} type="button" className={`${TILE} border-border-strong bg-surface hover:bg-surface-sunken ${k === "cz18" ? "" : "opacity-70"}`} onClick={() => apply(setAnalyticsChoice(store.get().project, k))}>
                  <span className="font-mono text-xs text-ink-faint">{i + 1}</span>
                  <span className="text-sm font-semibold">{title}</span>
                  <span className="text-sm text-ink-muted">{text}</span>
                  {chip}
                </button>
              ))}
            </div>
          </section>
        </>
      ) : null}

      {view === "cz_coming" ? (
        <>
          <div>{backToAnalytics}</div>
          <section className="rounded-md border border-status-you-ink/40 bg-status-you-wash p-5">
            <h2 className="text-lg font-semibold">{t("research.audience.czComingTitle")}</h2>
            <p className="mt-1 text-sm">{t("research.audience.czComingNote")}</p>
          </section>
        </>
      ) : null}

      {view === "special" ? (
        <>
          <div>{backToAnalytics}</div>
          <NotInAia title={t("research.audience.special")}>{t("research.audience.specialNotInAia")}</NotInAia>
          {p.audience.special_catalog_key ? (
            <section className={CARD}>
              <p className="text-sm">
                <b>{t("research.audience.selected")}</b> {String(p.audience.dataset_name || p.audience.description || p.audience.special_catalog_key)}
              </p>
              <p className="mt-1 text-xs text-ink-muted">{t("research.audience.storedNotUsed")}</p>
            </section>
          ) : null}
        </>
      ) : null}

      {view === "cz18" ? (
        <>
          <div>{backToAnalytics}</div>
          <section className={CARD} aria-labelledby="aud-cz18">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <div className={EYEBROW}>{t("research.audience.czTag")}</div>
                <h2 id="aud-cz18" className="mt-1 text-lg font-semibold">{t("research.audience.cz18")}</h2>
              </div>
              <Chip tone="done">{t("research.audience.ready")}</Chip>
            </div>
            <p className="mt-1 text-sm text-ink-muted">
              {t("research.audience.czIntroBefore")} <b>{t("research.audience.czIntroBold")}</b>
              {t("research.audience.czIntroAfter")}
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {([["population", "strategyPopulation"], ["filters", "strategyFilters"], ["discover", "strategyDiscover"]] as const).map(([k, key]) => {
                const on = (p.audience.strategy || "population") === k;
                return (
                  <button key={k} type="button" aria-pressed={on} onClick={() => apply(chooseAudience(store.get().project, k as Strategy))} className={`${TILE} ${on ? "border-signal bg-signal-wash" : "border-border-strong bg-surface hover:bg-surface-sunken"}`}>
                    <span className="text-sm font-semibold">{t(`research.audience.${key}`)}</span>
                    <span className="text-sm text-ink-muted">{t(`research.audience.${key}Text`)}</span>
                    {k === "filters" ? <Chip tone="you">{t("research.audience.notInAiaChip")}</Chip> : null}
                  </button>
                );
              })}
            </div>
          </section>
          {p.audience.strategy === "filters" ? <FilterEditor /> : null}
          {p.audience.strategy === "discover" ? <DiscoverEditor /> : null}
          <section className={CARD}>{goOn(t("research.audience.toPersona"))}</section>
        </>
      ) : null}

      <Summary project={p} />
      <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
        {ready ? null : <span className="text-sm text-ink-muted">{t("research.audience.nextHint")}</span>}
        <Button variant="primary" disabled={!ready} onClick={toPersona}>
          {t("research.audience.next")}
          <Icon name="next" size={14} />
        </Button>
      </div>
    </div>
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
    <>
      <NotInAia title={t("research.audience.filterTitle")}>{t("research.audience.filtersNotInAia")}</NotInAia>
      <section className={CARD} aria-labelledby="aud-filters">
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
            <Button disabled={step.busy} onClick={() => void propose()}>{t("research.audience.propose")}</Button>
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
    </>
  );
}

/** discoverEditor: what the product is and what "ideal" means, for the outcome-based segment. */
function DiscoverEditor() {
  const { store, state } = useResearch();
  const d = discoverText(state.project);
  return (
    <section className={CARD} aria-labelledby="aud-discover">
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

/** The readable summary (1795): the same settings the preflight and the sampling use. */
function Summary({ project }: { project: ResearchProject }) {
  const pairs = humanSummary(project.audience);
  const filters = humanFilters(project);
  return (
    <section className={CARD} aria-labelledby="aud-summary">
      <h2 id="aud-summary" className="text-base font-semibold">{t("research.audience.summaryTitle")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("research.audience.summaryIntro")}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {pairs.map(([k, v]) => (
          <Tag key={k}>
            <b>{k}:</b>&nbsp;{v}
          </Tag>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {filters.length ? filters.map(([k, v]) => (
          <Tag key={k}>
            <b>{k}:</b>&nbsp;{v}
          </Tag>
        )) : <p className="w-full rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm">{t("research.audience.summaryNone")}</p>}
      </div>
    </section>
  );
}
