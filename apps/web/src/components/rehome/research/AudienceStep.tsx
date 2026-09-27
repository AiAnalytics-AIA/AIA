"use client";

// 4. Audience / Cílová skupina, rebuilt (research-flow-rehome.md, chunk 5): the
// classic renderAudience (:374) under its three wrappers -- the branch banner
// (1785), the wizard's way on (1789) and the readable summary (1795). What each
// control does to the project is src/unit/research/audience.ts, parity-tested
// against the original; this file only draws it. The preview is page memory,
// as the classic AUDIENCE_PREVIEW: kept while the person stays in the project,
// never saved.

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { isNativeResult } from "@/lib/research-agent-jobs";
import { t, tv } from "@/i18n/t";
import { unit } from "@/unit/client";
import {
  type Catalog,
  type Change,
  DEFAULT_CATEGORY,
  type Factor,
  PROPOSE_EMPTY,
  PROPOSE_FAILED_SUFFIX,
  PROPOSE_TITLE,
  PROPOSE_UNCOVERED,
  PROPOSE_WARN_MS,
  SPECIAL_AUDIENCE_PRESETS,
  type SavedAudience,
  type Strategy,
  UPLOAD_DONE,
  UPLOAD_NO_FILE,
  UPLOAD_TIMEOUT_MS,
  analyticsBack,
  applyProposal,
  applyUpload,
  audienceReady,
  audienceView,
  catalogues,
  chooseAudience,
  chooseSpecialPreset,
  customerAudiences,
  discoverText,
  factorStatus,
  filterCategories,
  filterChips,
  filterableFactors,
  humanFilters,
  humanSummary,
  loadAudienceCatalog,
  previewRequest,
  previewVerdict,
  proposePayload,
  proposeText,
  rangeOf,
  removeAudienceFactor,
  searchKey,
  selectAudienceDataset,
  selectedValues,
  setAnalyticsChoice,
  setAudienceCategory,
  setAudienceEntry,
  setAudienceRange,
  setDiscoverField,
  specialSelected,
  uploadBody,
} from "@/unit/research/audience";
import { fileToBase64 } from "@/unit/research/brief";
import type { ResearchProject } from "@/unit/research/model";
import { Icon } from "../icons";
import { Button, Chip, Field, Tag, TextArea, TextInput } from "../ui";
import { useResearch, useSessionState } from "./context";
import { AiFailureCard, useAiStep } from "./useAiStep";

const CARD = "rounded-md border border-border bg-surface-raised p-5";
const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint";
const TILE = "flex flex-col items-start gap-2 rounded-sm border p-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const TEMPLATE_HREF = "/api/audiences/template";
const INSTRUCTIONS_HREF = "/files/docs/reference/AUDIENCE_IMPORT_AI_INSTRUCTIONS.md";

type Preview = { result: Record<string, unknown> } | { error: string } | null;

/** The page-memory preview (AUDIENCE_PREVIEW) and the request that fills it. */
function usePreview() {
  const { store } = useResearch();
  const [preview, setPreview] = useSessionState<Preview>("audience.preview", null);
  const check = async () => {
    const req = previewRequest(store.get().project);
    if ("error" in req) return setPreview({ error: req.error });
    try {
      const r = (await unit(req.route, { body: req.body })) as Record<string, unknown>;
      setPreview({ result: r });
    } catch (e) {
      setPreview({ error: e instanceof Error ? e.message : String(e) });
    }
  };
  return { preview, setPreview, check };
}

export function AudienceStep() {
  const { store, state, boot, stepHref } = useResearch();
  const router = useRouter();
  const { preview, setPreview, check } = usePreview();
  const p = state.project;
  const view = audienceView(p);
  const ready = audienceReady(p);
  const cat = catalogues(boot.raw);

  const apply = (c: Change | null, { clearPreview = false } = {}) => {
    if (!c) return;
    store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
    if (clearPreview) setPreview(null);
  };
  const toPersona = () => {
    router.push(stepHref("persona"));
  };
  const backToSource = (
    <Button small variant="quiet" icon="back" onClick={() => apply(setAudienceEntry(store.get().project, "choose"), { clearPreview: true })}>
      {t("research.audience.backSource")}
    </Button>
  );
  const backToAnalytics = (
    <Button small variant="quiet" icon="back" onClick={() => apply(analyticsBack(store.get().project))}>
      {t("research.audience.backAnalytics")}
    </Button>
  );
  const checkAndGo = (label: string, disabled = false) => (
    <div className="mt-3">
      <div className="flex flex-wrap gap-2">
        <Button disabled={disabled} onClick={() => void check()}>{t("research.audience.check")}</Button>
        <Button variant="primary" disabled={disabled} onClick={toPersona}>{label}</Button>
      </div>
      <PreviewBox preview={preview} n={p.n} />
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
              <button key={k} type="button" className={`${TILE} border-border-strong bg-surface hover:bg-surface-sunken`} onClick={() => apply(setAudienceEntry(store.get().project, k), { clearPreview: true })}>
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
          <section className={CARD} aria-labelledby="aud-own">
            <h2 id="aud-own" className="text-lg font-semibold">{t("research.audience.own")}</h2>
            <p className="mt-1 text-sm text-ink-muted">{t("research.audience.ownIntro")}</p>
            <Links />
          </section>
          <DatasetEditor onPreflight={(r) => setPreview({ result: r })} />
          <section className={CARD} aria-labelledby="aud-continue">
            <h2 id="aud-continue" className="text-base font-semibold">{t("research.audience.continueTitle")}</h2>
            <p className={`mt-2 rounded-sm border p-3 text-sm ${ready ? "border-status-done/40 bg-surface-sunken" : "border-signal-edge bg-signal-wash"}`}>
              {ready ? t("research.audience.ownReady") : t("research.audience.ownNotReady")}
            </p>
            {checkAndGo(t("research.audience.toPersona"), !ready)}
          </section>
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
                ["special", t("research.audience.special"), t("research.audience.specialText"), null],
              ] as const).map(([k, title, text, chip], i) => (
                <button key={k} type="button" className={`${TILE} border-border-strong bg-surface hover:bg-surface-sunken ${k === "cz_coming" ? "opacity-70" : ""}`} onClick={() => apply(setAnalyticsChoice(store.get().project, k), { clearPreview: k === "cz18" })}>
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
          <section className={CARD} aria-labelledby="aud-special">
            <h2 id="aud-special" className="text-lg font-semibold">{t("research.audience.special")}</h2>
            <p className="mt-1 text-sm text-ink-muted">{t("research.audience.specialIntro")}</p>
            <ul className="mt-4 flex flex-col gap-2">
              {SPECIAL_AUDIENCE_PRESETS.map((x) => {
                const active = p.audience?.special_catalog_key === x.key;
                return (
                  <li key={x.key}>
                    <button
                      type="button"
                      aria-pressed={active}
                      onClick={() => apply(chooseSpecialPreset(store.get().project, x.key, cat), { clearPreview: true })}
                      className={`flex w-full items-center gap-3 rounded-sm border px-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${active ? "border-signal bg-signal-wash" : "border-border-strong bg-surface hover:bg-surface-sunken"}`}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-semibold">{x.name}</span>
                        <span className="block text-xs text-ink-muted">{x.note}</span>
                      </span>
                      {x.kind === "coming_soon" ? <Chip tone="you">{t("research.audience.ownData")}</Chip> : <Chip tone="done">{t("research.audience.ready")}</Chip>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
          {specialSelected(p) ? (
            <section className={CARD}>
              <p className="rounded-sm border border-status-done/40 bg-surface-sunken p-3 text-sm">
                <b>{t("research.audience.selected")}</b> {String(p.audience.dataset_name || p.audience.description || "")}
              </p>
              {checkAndGo(t("research.audience.toPersonaSpecial"))}
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
                  <button key={k} type="button" aria-pressed={on} onClick={() => apply(chooseAudience(store.get().project, k as Strategy), { clearPreview: true })} className={`${TILE} ${on ? "border-signal bg-signal-wash" : "border-border-strong bg-surface hover:bg-surface-sunken"}`}>
                    <span className="text-sm font-semibold">{t(`research.audience.${key}`)}</span>
                    <span className="text-sm text-ink-muted">{t(`research.audience.${key}Text`)}</span>
                  </button>
                );
              })}
            </div>
          </section>
          {p.audience.strategy === "filters" ? <FilterEditor onPreview={check} /> : null}
          {p.audience.strategy === "discover" ? <DiscoverEditor /> : null}
          <section className={CARD}>{checkAndGo(t("research.audience.toPersona"))}</section>
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

function Links() {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      <a href={TEMPLATE_HREF} download className="inline-flex min-h-9 items-center rounded-sm border border-border-strong bg-surface-raised px-3 text-sm font-medium text-ink no-underline hover:bg-surface-sunken">
        {t("research.audience.template")}
      </a>
      <a href={INSTRUCTIONS_HREF} target="_blank" rel="noopener" className="inline-flex min-h-9 items-center rounded-sm px-3 text-sm font-medium text-ink-muted no-underline hover:bg-surface-sunken hover:text-ink">
        {t("research.audience.instructions")}
        <Icon name="external" size={12} className="ml-1.5 opacity-60" />
      </a>
    </div>
  );
}

function PreviewBox({ preview, n }: { preview: Preview; n: unknown }) {
  if (!preview) return null;
  if ("error" in preview) return <p role="alert" className="mt-3 text-sm text-status-fault">{preview.error}</p>;
  const v = previewVerdict(preview.result, n as never);
  return (
    <div role="status" className={`mt-3 rounded-sm border p-3 text-sm ${v.ok ? "border-status-done/40 bg-surface-sunken" : "border-status-fault/40 bg-status-fault-wash"}`}>
      <strong>{v.ok ? t("research.audience.previewOk") : t("research.audience.previewBad")}</strong>
      <br />
      {v.text}
    </div>
  );
}

/** audienceDatasetEditor: the saved customer audiences, and an upload. */
function DatasetEditor({ onPreflight }: { onPreflight: (r: Record<string, unknown>) => void }) {
  const { store, state, boot, toast } = useResearch();
  const [list, setList] = useSessionState<unknown>("audience.list", boot.raw.audiences ?? []);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [status, setStatus] = useState<{ kind: "loading" } | { kind: "error"; message: string } | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const a = state.project.audience;
  const saved: SavedAudience[] = customerAudiences(list);

  const refresh = async () => setList(await unit("audiences"));
  const upload = async () => {
    const f = file.current?.files?.[0];
    if (!f) return setStatus({ kind: "error", message: UPLOAD_NO_FILE });
    setStatus({ kind: "loading" });
    try {
      const body = uploadBody(store.get().project, { name: f.name, b64: await fileToBase64(f) }, name, desc);
      const r = (await unit("audiencesUpload", { body, timeoutMs: UPLOAD_TIMEOUT_MS })) as { audience?: Record<string, string>; preflight?: Record<string, unknown> };
      setList(await unit("audiences"));
      store.update(({ project }) => ({ project: applyUpload(project, r) }), { reason: "audience_upload" });
      if (r.preflight) onPreflight(r.preflight);
      toast(UPLOAD_DONE);
      setStatus(null);
    } catch (e) {
      setStatus({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <section className={CARD} aria-labelledby="aud-dataset">
      <h2 id="aud-dataset" className="text-base font-semibold">{t("research.audience.own")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("research.audience.datasetIntro")}</p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <Field label={t("research.audience.savedLabel")} className="min-w-64 flex-1">
          <select
            value={String(a.dataset_id || "")}
            onChange={(e) => store.update(({ project }) => ({ project: selectAudienceDataset(project, e.target.value, saved) }))}
            className="min-h-9 w-full rounded-sm border border-border-strong bg-surface-raised px-2.5 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            <option value="">{t("research.audience.savedNone")}</option>
            {saved.map((x) => (
              <option key={x.audience_id} value={x.audience_id}>{`${x.name} · N=${x.rows}`}</option>
            ))}
          </select>
        </Field>
        <Button variant="quiet" onClick={() => void refresh()}>{t("research.audience.refresh")}</Button>
      </div>
      {a.dataset_id ? (
        <p className="mt-3 rounded-sm border border-status-done/40 bg-surface-sunken p-3 text-sm">
          <strong>{String(a.dataset_name || "")}</strong>
          <br />
          {String(a.description || "")}
          <br />
          <span className="text-xs text-ink-muted">{t("research.audience.datasetNote")}</span>
        </p>
      ) : null}
      <h3 className="mt-5 border-t border-border pt-4 text-sm font-semibold">{t("research.audience.uploadTitle")}</h3>
      <div className="mt-2 grid gap-3 md:grid-cols-2">
        <Field label={t("research.audience.uploadName")}>
          <TextInput value={name} placeholder={t("research.audience.uploadNamePlaceholder")} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label={t("research.audience.uploadFile")}>
          <input ref={file} type="file" accept=".xlsx,.csv" className="text-sm" />
        </Field>
        <Field label={t("research.audience.uploadDesc")} className="md:col-span-2">
          <TextArea value={desc} placeholder={t("research.audience.uploadDescPlaceholder")} onChange={(e) => setDesc(e.target.value)} />
        </Field>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button icon="attach" disabled={status?.kind === "loading"} onClick={() => void upload()}>{t("research.audience.uploadRun")}</Button>
        <a href={TEMPLATE_HREF} download className="inline-flex min-h-9 items-center rounded-sm px-3 text-sm font-medium text-ink-muted no-underline hover:bg-surface-sunken hover:text-ink">
          {t("research.audience.template")}
        </a>
      </div>
      <div aria-live="polite">
        {status?.kind === "loading" ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-status-running">
            <Icon name="running" size={14} className="animate-spin" />
            <b>{t("research.audience.uploading")}</b> {t("research.audience.uploadingSub")}
          </p>
        ) : null}
        {status?.kind === "error" ? <p role="alert" className="mt-3 text-sm text-status-fault">{status.message}</p> : null}
      </div>
      <p className="mt-3 rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm">
        <b>{t("research.audience.uploadMinimum")}</b> {t("research.audience.uploadMinimumText")}
      </p>
    </section>
  );
}

/** filterEditor: the society-factor catalogue, OR inside a factor, AND across factors. */
function FilterEditor({ onPreview }: { onPreview: () => Promise<void> }) {
  const { store, state, runJob, toast } = useResearch();
  const step = useAiStep();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [category, setCategory] = useSessionState("audience.category", DEFAULT_CATEGORY);
  const [query, setQuery] = useSessionState("audience.search", "");
  const [text, setText] = useState(String(state.project.audience.description || ""));
  const [, setPreview] = useSessionState<Preview>("audience.preview", null);

  useEffect(() => {
    let live = true;
    loadAudienceCatalog().then((c) => live && setCatalog(c), () => {});
    return () => {
      live = false;
    };
  }, []);

  if (!catalog) {
    return (
      <section className={CARD}>
        <h2 className="text-base font-semibold">{t("research.audience.filterLoadingTitle")}</h2>
        <p className="mt-1 text-sm text-ink-muted">{t("research.audience.filterLoading")}</p>
      </section>
    );
  }
  const { categories, sensitive } = filterCategories(catalog);
  const { shown, total } = filterableFactors(catalog, category, searchKey(query));
  const chips = filterChips(state.project, catalog);
  const change = (c: Change, preview: boolean) => {
    store.update(() => ({ project: c.project }), { reason: c.reason, invalidateCheck: c.invalidateCheck });
    if (preview) void onPreview();
  };

  // proposeAudience: the provider check, then the job; the model's filters replace the project's.
  const propose = () =>
    step.run(async () => {
      const typed = proposeText(text, store.get().project);
      if (!typed) throw new Error(PROPOSE_EMPTY);
      if (!(await step.providerOk())) return;
      await step.saved();
      const r = (await runJob("audiencePropose", proposePayload(store.get().project, typed), { title: PROPOSE_TITLE, warnMs: PROPOSE_WARN_MS })) as Parameters<typeof applyProposal>[2];
      if (isNativeResult(r)) { setPreview(null); toast("Návrh audience je uložený. Zkontrolujte filtry a proveditelnost."); return; }
      const a = applyProposal(store.get().project, typed, r || {});
      store.update(() => ({ project: a.change.project }), { reason: a.change.reason, invalidateCheck: a.change.invalidateCheck });
      setPreview(a.preview ? { result: a.preview as Record<string, unknown> } : null);
      if (a.uncovered) toast(PROPOSE_UNCOVERED);
    }, (m) => (m === PROPOSE_EMPTY ? m : m + PROPOSE_FAILED_SUFFIX));

  return (
    <section className={CARD} aria-labelledby="aud-filters">
      {step.failure ? (
        <div className="mb-4">
          <AiFailureCard failure={step.failure} title={t("research.audience.failedTitle")} onRetry={() => step.setFailure(null)} />
        </div>
      ) : null}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className={EYEBROW}>{t("research.audience.filterTag")}</div>
          <h2 id="aud-filters" className="mt-1 text-base font-semibold">{t("research.audience.filterTitle")}</h2>
        </div>
        <Chip tone="done">{tv("research.audience.filterCount", { n: String(catalog.filterable_count ?? "") })}</Chip>
      </div>
      <p className="mt-1 text-sm leading-6 text-ink-muted">
        <b>{t("research.audience.logic")}</b> {t("research.audience.logicText")}
      </p>
      <Field label={t("research.audience.describe")} className="mt-3">
        <div className="flex flex-wrap gap-2">
          <TextInput className="min-w-64 flex-1" value={text} placeholder={t("research.audience.describePlaceholder")} onChange={(e) => setText(e.target.value)} />
          <Button disabled={step.busy} onClick={() => void propose()}>{t("research.audience.propose")}</Button>
        </div>
      </Field>
      <ul className="my-3 flex flex-wrap gap-1.5">
        {chips.length ? (
          chips.map((c) => (
            <li key={c.id} className="inline-flex items-center gap-1 rounded-sm border border-signal-edge bg-signal-wash py-0.5 pl-2 pr-0.5 text-xs">
              <b>{c.label}</b>: {c.text}
              <button
                type="button"
                aria-label={tv("research.audience.removeFilter", { label: c.label })}
                onClick={() => change(removeAudienceFactor(store.get().project, c.id), false)}
                className="rounded-sm px-1 text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-focus-ring"
              >
                ×
              </button>
            </li>
          ))
        ) : (
          <li className="text-xs text-ink-muted">{t("research.audience.noFilters")}</li>
        )}
      </ul>
      <TextInput aria-label={t("research.audience.search")} placeholder={t("research.audience.searchPlaceholder")} value={query} onChange={(e) => setQuery(e.target.value)} />
      <div className="my-3 flex flex-wrap gap-1">
        {categories.map((c) => (
          <Button key={c.id} small variant={category === c.id ? "primary" : "quiet"} aria-pressed={category === c.id} onClick={() => setCategory(c.id)}>
            {tv("research.audience.categoryCount", { label: String(c.label || c.id), n: String(c.filterable_count ?? "") })}
          </Button>
        ))}
        <Button small variant={category === "all" ? "primary" : "quiet"} aria-pressed={category === "all"} onClick={() => setCategory("all")}>
          {t("research.audience.all")}
        </Button>
      </div>
      <div className="flex flex-col gap-2">
        {shown.length ? shown.map((f) => <FactorRow key={f.id} f={f} project={state.project} onChange={(c) => change(c, true)} />) : (
          <p className="rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm">{t("research.audience.noFactor")}</p>
        )}
      </div>
      {total > 80 ? <p className="mt-2 rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm">{tv("research.audience.moreFactors", { n: total })}</p> : null}
      <p className="mt-3 rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm">
        <b>{t("research.audience.sensitiveBold")}</b> {tv("research.audience.sensitiveText", { n: sensitive })}
      </p>
    </section>
  );
}

/** factorEditor1793: a range for a numeric factor, a multi-select of values otherwise. */
function FactorRow({ f, project, onChange }: { f: Factor; project: ResearchProject; onChange: (c: Change) => void }) {
  const lo = useRef<HTMLInputElement>(null);
  const hi = useRef<HTMLInputElement>(null);
  const cur = (project.audience.filters as Record<string, unknown> | undefined)?.[f.id];
  if (f.kind === "numeric") {
    const { lo: l, hi: h } = rangeOf(project, f.id);
    return (
      <div className={`rounded-sm border p-3 ${cur != null ? "border-signal bg-signal-wash" : "border-border bg-surface"}`}>
        <b className="text-sm">{f.label}</b>
        <small className="block text-xs text-ink-muted">{`${f.category_label} · ${factorStatus(f.status)} · ${f.source || ""}`}</small>
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          <TextInput ref={lo} key={`lo-${l}`} type="number" step="any" aria-label={tv("research.audience.from", { v: String(f.min ?? "") })} placeholder={tv("research.audience.from", { v: String(f.min ?? "") })} defaultValue={l == null ? "" : String(l)} />
          <TextInput ref={hi} key={`hi-${h}`} type="number" step="any" aria-label={tv("research.audience.to", { v: String(f.max ?? "") })} placeholder={tv("research.audience.to", { v: String(f.max ?? "") })} defaultValue={h == null ? "" : String(h)} />
        </div>
        {/* As the classic reads the two inputs: an empty one is 0 (OI-50, a decision). */}
        <Button small variant="quiet" className="mt-2" onClick={() => onChange(setAudienceRange(project, f.id, lo.current?.value, hi.current?.value))}>
          {t("research.audience.applyRange")}
        </Button>
      </div>
    );
  }
  const vals = (f.values || []).slice(0, 40);
  const selected = selectedValues(project, f.id);
  return (
    <div className={`rounded-sm border p-3 ${selected.size ? "border-signal bg-signal-wash" : "border-border bg-surface"}`}>
      <b className="text-sm">{f.label}</b>
      <small className="block text-xs text-ink-muted">{`${f.category_label} · ${factorStatus(f.status)} · ${t("research.audience.orInside")}`}</small>
      <select
        multiple
        aria-label={String(f.label || f.id)}
        size={Math.min(6, Math.max(2, vals.length))}
        value={[...selected]}
        onChange={(e) => onChange(setAudienceCategory(project, f.id, [...e.target.selectedOptions].map((o) => o.value)))}
        className="mt-2 w-full rounded-sm border border-border-strong bg-surface-raised p-1 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
      >
        {vals.map((v) => (
          <option key={v.value} value={v.value}>{`${v.value} (${v.count})`}</option>
        ))}
      </select>
    </div>
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
