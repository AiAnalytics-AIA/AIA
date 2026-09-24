"use client";

// 3. Dotazník, rebuilt (research-flow-rehome.md, chunk 4): the classic
// renderQuestionnaire (:341) under its wizard wrapper (:960) -- the three
// paths, the XLSX/CSV import, the AI build, the respondent preview, the guided
// editor and the final optimisation. What each control does to the project is
// src/unit/research/questionnaire.ts, parity-tested against the original; this
// file only draws it. The block's "AI: zlepšit blok" is not drawn: it does
// nothing in the classic interface (OI-49).

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { unit } from "@/unit/client";
import { fileToBase64 } from "@/unit/research/brief";
import { PROVIDER_LABEL } from "@/unit/research/jobs";
import {
  BUILD_FAILED_SUFFIX,
  BUILD_TITLE,
  BUILD_WARN_MS,
  CONFIRM_REMOVE_SECTION,
  DEEP_TITLE,
  GUIDED_PROMPT,
  type GuidedKind,
  OPTIMIZE_DONE,
  OPTIMIZE_TITLE,
  PROMPT_CHOICES,
  PROMPT_CHOICES_DEFAULT,
  PROMPT_SET_ITEMS,
  PROMPT_SET_TYPE,
  type PreviewItem,
  type Question,
  type QuestionnairePath,
  type Section,
  UPLOAD_NO_FILE,
  UPLOAD_TIMEOUT_MS,
  addGuidedQuestion,
  addQuestion,
  addQuestionSection,
  addTrackedSet,
  applyBuilt,
  applyDeep,
  applyImport,
  applyOptimized,
  buildPayload,
  changeQType,
  deepPayload,
  optimizePayload,
  questionnaireCounts,
  questionnaireHasQuestions,
  questionnaireView,
  removeQuestion,
  removeSection,
  researchCount,
  respondentPreview,
  sections,
  setObjectFamily,
  setObjectLabel,
  setPriceBands,
  setQuestionOptions,
  setQuestionText,
  setQuestionnairePath,
  setScaleEnd,
  setScaleLabel,
  setSectionField,
  toAudience,
  updateObjects,
} from "@/unit/research/questionnaire";
import type { ResearchProject } from "@/unit/research/model";
import { Icon } from "../icons";
import { Button, Field, Tag, TextArea, TextInput } from "../ui";
import { useResearch } from "./context";
import { AiFailureCard, useAiStep } from "./useAiStep";
import { AnalysisFailureCard, useAnalysis } from "./useAnalysis";

const CARD = "rounded-md border border-border bg-surface-raised p-5";
const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint";
const TEMPLATE_HREF = "/api/questionnaire/template";
const METHODOLOGY_HREF = "/files/docs/reference/QUESTIONNAIRE_IMPORT_AI_INSTRUCTIONS.md";

export function QuestionnaireStep() {
  const { store, state, boot, runJob, toast } = useResearch();
  const router = useRouter();
  const analysis = useAnalysis();
  const step = useAiStep();
  const p = state.project;
  const view = questionnaireView(p);

  const update = (next: (p: ResearchProject) => ResearchProject, reason?: string) =>
    store.update(({ project }) => ({ project: next(project) }), reason ? { reason } : {});
  const path = (x: QuestionnairePath) =>
    store.update(({ project }) => ({ project: setQuestionnairePath(project, x) }), { reason: "questionnaire_path", invalidateCheck: false });

  // continueQuestionnaireToAudience: the run check and the final review are cleared.
  const toAudienceStep = () => {
    store.update(({ project }) => ({ project: toAudience(project) }), { reason: "questionnaire_done" });
    const id = store.get().projectId;
    if (id) router.push(`/app/research/${encodeURIComponent(id)}/audience`);
  };

  // buildQuestionnaire: the analysis first (reused when the brief is the same), then the job.
  const build = async () => {
    step.setFailure(null);
    if (!(await analysis.analyse())) return;
    await step.run(async () => {
      if (!(await step.providerOk())) return;
      await step.saved();
      const s = store.get();
      const result = await runJob("researchBuildQuestionnaire", buildPayload(s.project, s.analysis), { title: BUILD_TITLE, warnMs: BUILD_WARN_MS });
      store.update(() => ({ project: applyBuilt(result, boot) }), { reason: "questionnaire_ai_1776" });
    }, (m) => m + BUILD_FAILED_SUFFIX);
  };

  // optimizeQuestionnaireAI and runProjectDeepResearch: no provider check, as the classic (OI-55).
  const optimize = () =>
    step.run(async () => {
      await step.saved();
      const s = store.get();
      const result = await runJob("questionnaireOptimize", optimizePayload(s.project), { title: OPTIMIZE_TITLE });
      store.update(({ analysis: a }) => applyOptimized(result, a, boot), { reason: "questionnaire_optimized" });
      toast(OPTIMIZE_DONE);
    });
  const deep = () =>
    step.run(async () => {
      await step.saved();
      const result = await runJob("researchDeep", deepPayload(store.get().project), { title: DEEP_TITLE });
      const r = applyDeep(store.get().project, result);
      store.update(() => ({ project: r.project }), { reason: "deep_research" });
      toast(r.toast);
    });

  const back = (
    <Button small variant="quiet" icon="back" onClick={() => path("choose")}>
      {t("research.questionnaire.back")}
    </Button>
  );
  const failures = (
    <>
      {analysis.failure ? <AnalysisFailureCard failure={analysis.failure} onRetry={() => void build()} /> : null}
      {step.failure ? <AiFailureCard failure={step.failure} title={t("research.questionnaire.failedTitle")} onRetry={() => step.setFailure(null)} /> : null}
    </>
  );
  const has = questionnaireHasQuestions(p);
  const next = (
    <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border pt-4">
      {has ? null : <span className="text-sm text-ink-muted">{t("research.questionnaire.nextHint")}</span>}
      <Button variant="primary" onClick={toAudienceStep} disabled={!has}>
        {t("research.questionnaire.next")}
        <Icon name="next" size={14} />
      </Button>
    </div>
  );

  if (view === "choose") {
    const tiles: [QuestionnairePath, string, string, string?][] = [
      ["upload", t("research.questionnaire.pathUpload"), t("research.questionnaire.pathUploadText")],
      ["manual", t("research.questionnaire.pathManual"), t("research.questionnaire.pathManualText")],
      ["ai", t("research.questionnaire.pathAi"), t("research.questionnaire.pathAiText"), `${PROVIDER_LABEL} · ${String(p.model || "")}`],
    ];
    return (
      <div className="flex max-w-5xl flex-col gap-4">
        <section className={CARD} aria-labelledby="q-choose">
          <h2 id="q-choose" className="text-lg font-semibold">{t("research.questionnaire.chooseTitle")}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.chooseIntro")}</p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {tiles.map(([key, title, text, chip], i) => (
              <button
                key={key}
                type="button"
                onClick={() => path(key)}
                className="flex flex-col items-start gap-2 rounded-sm border border-border-strong bg-surface p-4 text-left hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
              >
                <span className="font-mono text-xs text-ink-faint">{i + 1}</span>
                <span className="text-sm font-semibold">{title}</span>
                <span className="text-sm text-ink-muted">{text}</span>
                {chip ? <Tag>{chip}</Tag> : null}
              </button>
            ))}
          </div>
        </section>
        {next}
      </div>
    );
  }

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <div>{back}</div>
      {failures}
      {view === "upload" ? <Upload /> : null}
      {view === "ai" ? (
        <section className={CARD} aria-labelledby="q-ai">
          <h2 id="q-ai" className="text-lg font-semibold">{t("research.questionnaire.aiTitle")}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.aiIntro")}</p>
          <AiAction label={t("research.questionnaire.aiBuild")} help={t("research.questionnaire.aiBuildHelp")} busy={step.busy || analysis.busy} onClick={() => void build()} />
        </section>
      ) : null}
      {view === "editor" || (view === "upload" && sections(p).length) ? (
        <>
          <Preview items={respondentPreview(p)} />
          <Editor update={update} />
          <section className={CARD} aria-labelledby="q-final">
            <h2 id="q-final" className="text-lg font-semibold">{t("research.questionnaire.finalTitle")}</h2>
            <p className="mt-1 text-sm leading-6 text-ink-muted">{t("research.questionnaire.finalIntro")}</p>
            <div className="mt-3">
              <Tag>{researchCount(p) ? tv("research.questionnaire.researchYes", { n: researchCount(p) }) : t("research.questionnaire.researchNo")}</Tag>
            </div>
            <AiAction label={t("research.questionnaire.optimize")} help={t("research.questionnaire.optimizeHelp")} busy={step.busy} onClick={() => void optimize()} />
            {researchCount(p) ? (
              <Button small variant="quiet" className="mt-2" disabled={step.busy} onClick={() => void deep()}>
                {t("research.questionnaire.refreshResearch")}
              </Button>
            ) : null}
            <div className="mt-4">
              <Button variant="primary" onClick={toAudienceStep}>{t("research.questionnaire.done")}</Button>
            </div>
          </section>
        </>
      ) : null}
      {next}
    </div>
  );
}

function AiAction({ label, help, busy, onClick }: { label: string; help: string; busy: boolean; onClick: () => void }) {
  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-surface px-4 py-3">
      <div className="min-w-0">
        <div className="text-sm font-semibold">{label}</div>
        <div className="text-xs text-ink-muted">{help}</div>
      </div>
      <Button variant="primary" onClick={onClick} disabled={busy}>{label}</Button>
    </div>
  );
}

/** uploadQuestionnaireFile: the file is parsed by the unit, and its project replaces this one. */
function Upload() {
  const { store, boot, toast } = useResearch();
  const input = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<{ kind: "loading" } | { kind: "error"; message: string } | null>(null);

  const load = async (f: File | undefined) => {
    if (!f) return setStatus({ kind: "error", message: UPLOAD_NO_FILE });
    setStatus({ kind: "loading" });
    try {
      const r = await unit("questionnaireUpload", {
        body: { filename: f.name, data_b64: await fileToBase64(f), project: store.get().project },
        timeoutMs: UPLOAD_TIMEOUT_MS,
      });
      const imported = applyImport(r, boot);
      store.update(() => ({ project: imported.project }), { reason: "questionnaire_import" });
      toast(imported.toast);
      setStatus(null);
    } catch (e) {
      setStatus({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    } finally {
      if (input.current) input.current.value = "";
    }
  };

  return (
    <section className={CARD} aria-labelledby="q-upload">
      <h2 id="q-upload" className="text-lg font-semibold">{t("research.questionnaire.uploadTitle")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.uploadIntro")}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <a href={TEMPLATE_HREF} download className="inline-flex min-h-9 items-center rounded-sm border border-border-strong bg-surface-raised px-3 text-sm font-medium text-ink no-underline hover:bg-surface-sunken">
          {t("research.questionnaire.template")}
        </a>
        <a href={METHODOLOGY_HREF} target="_blank" rel="noopener" className="inline-flex min-h-9 items-center rounded-sm px-3 text-sm font-medium text-ink-muted no-underline hover:bg-surface-sunken hover:text-ink">
          {t("research.questionnaire.methodology")}
          <Icon name="external" size={12} className="ml-1.5 opacity-60" />
        </a>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium text-ink-muted">{t("research.questionnaire.fileLabel")}</span>
        <input ref={input} type="file" hidden accept=".xlsx,.csv" aria-label={t("research.questionnaire.fileLabel")} onChange={(e) => void load(e.target.files?.[0])} />
        <Button variant="primary" icon="attach" disabled={status?.kind === "loading"} onClick={() => input.current?.click()}>
          {t("research.questionnaire.load")}
        </Button>
      </div>
      <div aria-live="polite">
        {status?.kind === "loading" ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-status-running">
            <Icon name="running" size={14} className="animate-spin" />
            <b>{t("research.questionnaire.loading")}</b> {t("research.questionnaire.loadingSub")}
          </p>
        ) : null}
        {status?.kind === "error" ? <p role="alert" className="mt-3 text-sm text-status-fault">{status.message}</p> : null}
      </div>
    </section>
  );
}

function Preview({ items }: { items: PreviewItem[] }) {
  return (
    <section className={CARD} aria-labelledby="q-preview">
      <div className={EYEBROW}>{t("research.questionnaire.previewTag")}</div>
      <h2 id="q-preview" className="mt-1 text-lg font-semibold">{t("research.questionnaire.previewTitle")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.previewHelp")}</p>
      <ol className="mt-3 flex flex-col gap-3 rounded-sm border border-border bg-surface p-4">
        {items.length ? (
          items.map((it) =>
            it.kind === "question" ? (
              <li key={it.index} className="border-b border-border pb-3 last:border-b-0 last:pb-0">
                <div className="text-xs text-ink-muted">{tv("research.questionnaire.previewQuestion", { n: it.index })}</div>
                <div className="text-sm font-semibold">{it.text}</div>
                {it.options.length ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {it.options.map((o, i) => (
                      <span key={i} className="inline-flex items-center gap-1.5 rounded-sm border border-border-strong bg-surface-raised px-2 py-1 text-xs">
                        <span aria-hidden="true" className="block size-2.5 rounded-full border border-ink-muted" />
                        {o}
                      </span>
                    ))}
                  </div>
                ) : it.scale ? (
                  <div className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
                    <span>{it.scale[0]}</span>
                    <span aria-hidden="true" className="block h-1 flex-1 rounded-sm bg-signal" />
                    <span>{it.scale[1]}</span>
                  </div>
                ) : (
                  <div aria-hidden="true" className="mt-2 h-10 rounded-sm border border-border bg-surface-raised" />
                )}
              </li>
            ) : (
              <li key={it.index} className="border-b border-border pb-3 last:border-b-0 last:pb-0">
                <div className="text-xs text-ink-muted">{tv("research.questionnaire.previewSet", { n: it.index, title: it.title })}</div>
                <ul className="mt-2 flex flex-col gap-1.5">
                  {it.rows.map((r, i) => (
                    <li key={i} className="rounded-sm border border-border bg-surface-sunken px-3 py-2">
                      <div className="flex items-start justify-between gap-2 text-sm">
                        <span>{r}</span>
                        <Tag>{t("research.questionnaire.scale")}</Tag>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-ink-muted">
                        <span>{it.low}</span>
                        <span aria-hidden="true">←</span>
                        <span className="font-mono tracking-wide">1 2 3 4 5 6 7 8 9 10</span>
                        <span aria-hidden="true">→</span>
                        <span>{it.high}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </li>
            ),
          )
        ) : (
          <li className="text-sm text-ink-muted">{t("research.questionnaire.previewEmpty")}</li>
        )}
      </ol>
    </section>
  );
}

type Update = (next: (p: ResearchProject) => ResearchProject, reason?: string) => void;

/** questionnaireEditorHtml: quick add, one card per section, new block / new set. */
function Editor({ update }: { update: Update }) {
  const { store, state, prompt, confirm, toast } = useResearch();
  const xs = sections(state.project);
  const counts = questionnaireCounts(state.project);

  const guided = async (kind: GuidedKind) => {
    const text = await prompt(GUIDED_PROMPT[kind]);
    if (!text?.trim()) return;
    const choices = kind === "choice" ? await prompt(PROMPT_CHOICES, PROMPT_CHOICES_DEFAULT) : null;
    const r = addGuidedQuestion(store.get().project, kind, text, choices);
    if (!r) return;
    store.update(() => ({ project: r.project }), { reason: "guided_question" });
    setTimeout(() => document.getElementById(`qedit_${r.questionId}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 50);
  };
  const trackedSet = async () => {
    const typ = await prompt(PROMPT_SET_TYPE);
    if (!typ) return;
    const raw = await prompt(PROMPT_SET_ITEMS);
    const r = addTrackedSet(store.get().project, typ, raw);
    if (r && "error" in r) return toast(r.error);
    if (r) store.update(() => ({ project: r.project }));
  };
  const removeBlock = async (si: number) => {
    if (await confirm(CONFIRM_REMOVE_SECTION)) update((p) => removeSection(p, si));
  };

  return (
    <section className={CARD} aria-labelledby="q-editor">
      <div className={EYEBROW}>{t("research.questionnaire.editorTag")}</div>
      <h2 id="q-editor" className="mt-1 text-lg font-semibold">{tv("research.questionnaire.editorCounts", counts)}</h2>
      <p className="mt-1 text-sm leading-6 text-ink-muted">{t("research.questionnaire.editorIntro")}</p>
      <div className="mt-3 rounded-sm border border-signal-edge bg-signal-wash p-3">
        <b className="text-sm">{t("research.questionnaire.quickAdd")}</b>
        <div className="mt-2 flex flex-wrap gap-1">
          <Button small variant="quiet" icon="plus" onClick={() => void guided("choice")}>{t("research.questionnaire.addChoice")}</Button>
          <Button small variant="quiet" icon="plus" onClick={() => void guided("scale")}>{t("research.questionnaire.addScale")}</Button>
          <Button small variant="quiet" icon="plus" onClick={() => void guided("open")}>{t("research.questionnaire.addOpen")}</Button>
          <Button small variant="quiet" icon="plus" onClick={() => void trackedSet()}>{t("research.questionnaire.addSet")}</Button>
        </div>
        <p className="mt-1 text-xs text-ink-muted">{t("research.questionnaire.quickHelp")}</p>
      </div>
      <div className="mt-4 flex flex-col gap-4">
        {xs.length ? (
          xs.map((sec, si) =>
            sec.type === "questions" ? (
              <QuestionBlock key={sec.id || si} sec={sec} si={si} update={update} onRemove={() => void removeBlock(si)} />
            ) : (
              <TrackedSet key={sec.id || si} sec={sec} si={si} update={update} onRemove={() => void removeBlock(si)} />
            ),
          )
        ) : (
          <div className="rounded-sm border border-dashed border-border-strong p-6 text-center">
            <h3 className="text-base font-semibold">{t("research.questionnaire.emptyTitle")}</h3>
            <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.emptyText")}</p>
          </div>
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button icon="plus" onClick={() => update((p) => addQuestionSection(p))}>{t("research.questionnaire.addBlock")}</Button>
        <Button icon="plus" onClick={() => void trackedSet()}>{t("research.questionnaire.addSetLower")}</Button>
      </div>
    </section>
  );
}

function SectionHead({ tag, sec, si, update, titleLabel, purposePlaceholder, onRemove }: {
  tag: string; sec: Section; si: number; update: Update; titleLabel: string; purposePlaceholder: string; onRemove: () => void;
}) {
  return (
    <div className="flex items-start gap-3 border-b border-border bg-surface-sunken p-4">
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className={EYEBROW}>{tag}</div>
        <TextInput aria-label={titleLabel} className="w-full font-semibold" value={sec.title || ""} onChange={(e) => update((p) => setSectionField(p, si, "title", e.target.value))} />
        <TextInput aria-label={purposePlaceholder} placeholder={purposePlaceholder} value={sec.purpose || ""} onChange={(e) => update((p) => setSectionField(p, si, "purpose", e.target.value))} />
      </div>
      <Button small variant="quiet" icon="trash" onClick={onRemove}>{t("research.questionnaire.remove")}</Button>
    </div>
  );
}

function QuestionBlock({ sec, si, update, onRemove }: { sec: Section; si: number; update: Update; onRemove: () => void }) {
  const qs = sec.questions || [];
  return (
    <article className="overflow-hidden rounded-sm border border-border bg-surface">
      <SectionHead tag={t("research.questionnaire.blockTag")} sec={sec} si={si} update={update} titleLabel={t("research.questionnaire.blockTitle")} purposePlaceholder={t("research.questionnaire.blockPurpose")} onRemove={onRemove} />
      <div className="flex flex-col gap-3 p-4">
        {qs.length ? qs.map((q, qi) => <QuestionCard key={q.id || qi} q={q} si={si} qi={qi} update={update} />) : (
          <p className="rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm">{t("research.questionnaire.blockEmpty")}</p>
        )}
        <div>
          <Button small icon="plus" onClick={() => update((p) => addQuestion(p, si))}>{t("research.questionnaire.addQuestion")}</Button>
        </div>
      </div>
    </article>
  );
}

/** questionCard: text and type; options for a choice, the scale's ends for a scale. */
function QuestionCard({ q, si, qi, update }: { q: Question; si: number; qi: number; update: Update }) {
  const typ = String(q.typ || "");
  const skala = q.skala || [1, 10];
  const labels = q.popisky_skaly || ["vůbec", "zcela"];
  return (
    <div id={`qedit_${q.id || "Q"}`} className="rounded-sm border border-border bg-surface-raised p-4">
      <div className="flex items-center justify-between gap-2">
        <Tag>{q.id || "Q"}</Tag>
        <Button small variant="quiet" aria-label={tv("research.questionnaire.removeQuestion", { id: String(q.id || "Q") })} onClick={() => update((p) => removeQuestion(p, si, qi))}>
          ✕
        </Button>
      </div>
      <div className="mt-2 grid gap-3 md:grid-cols-[1fr_12rem]">
        <Field label={t("research.questionnaire.questionText")}>
          <TextArea className="min-h-16 w-full" value={q.text || ""} onChange={(e) => update((p) => setQuestionText(p, si, qi, e.target.value))} />
        </Field>
        <Field label={t("research.questionnaire.questionType")}>
          <select
            value={typ}
            onChange={(e) => update((p) => changeQType(p, si, qi, e.target.value))}
            className="min-h-9 w-full rounded-sm border border-border-strong bg-surface-raised px-2.5 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            {!["vyber", "multi", "skala", "otevrena"].includes(typ) ? <option value={typ} /> : null}
            <option value="vyber">{t("research.questionnaire.typeChoice")}</option>
            <option value="multi">{t("research.questionnaire.typeMulti")}</option>
            <option value="skala">{t("research.questionnaire.typeScale")}</option>
            <option value="otevrena">{t("research.questionnaire.typeOpen")}</option>
          </select>
        </Field>
      </div>
      {typ === "vyber" || typ === "multi" ? (
        <Field label={t("research.questionnaire.options")} className="mt-3">
          {/* Applied on leaving the field, as the classic onchange: lines are trimmed and blank ones dropped. */}
          <TextArea
            key={(q.kategorie || []).join("\n")}
            className="min-h-18 w-full"
            defaultValue={(q.kategorie || []).join("\n")}
            onBlur={(e) => update((p) => setQuestionOptions(p, si, qi, e.target.value))}
          />
        </Field>
      ) : null}
      {typ === "skala" ? (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Field label={t("research.questionnaire.scaleMin")}>
            <TextInput key={`min-${skala[0]}`} type="number" defaultValue={String(skala[0])} onBlur={(e) => update((p) => setScaleEnd(p, si, qi, 0, e.target.value))} />
          </Field>
          <Field label={t("research.questionnaire.scaleMax")}>
            <TextInput key={`max-${skala[1]}`} type="number" defaultValue={String(skala[1])} onBlur={(e) => update((p) => setScaleEnd(p, si, qi, 1, e.target.value))} />
          </Field>
          <Field label={t("research.questionnaire.scaleLow")}>
            <TextInput key={`lo-${labels[0]}`} defaultValue={labels[0]} onBlur={(e) => update((p) => setScaleLabel(p, si, qi, 0, e.target.value))} />
          </Field>
          <Field label={t("research.questionnaire.scaleHigh")}>
            <TextInput key={`hi-${labels[1]}`} defaultValue={labels[1]} onBlur={(e) => update((p) => setScaleLabel(p, si, qi, 1, e.target.value))} />
          </Field>
        </div>
      ) : null}
    </div>
  );
}

/** objectSection: a tracked set of 4–15 comparable objects on one question and scale. */
function TrackedSet({ sec, si, update, onRemove }: { sec: Section; si: number; update: Update; onRemove: () => void }) {
  const { store, toast } = useResearch();
  const labels = sec.scale_labels || ["vůbec", "velmi"];
  const objects = (sec.objects || []).join("\n");
  return (
    <article className="overflow-hidden rounded-sm border border-border bg-surface">
      <SectionHead tag={t("research.questionnaire.setTag")} sec={sec} si={si} update={update} titleLabel={t("research.questionnaire.setTitle")} purposePlaceholder={t("research.questionnaire.setPurpose")} onRemove={onRemove} />
      <div className="flex flex-col gap-3 p-4">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label={t("research.questionnaire.setFamily")}>
            <TextInput value={sec.object_family || sec.object_type || ""} placeholder={t("research.questionnaire.setFamilyPlaceholder")} onChange={(e) => update((p) => setObjectFamily(p, si, e.target.value))} />
            <span className="text-xs text-ink-muted">{t("research.questionnaire.setFamilyHelp")}</span>
          </Field>
          <Field label={t("research.questionnaire.setQuestion")}>
            <TextInput value={sec.object_question || "Jak hodnotíte {object}?"} onChange={(e) => update((p) => setSectionField(p, si, "object_question", e.target.value))} />
            <span className="text-xs text-ink-muted">
              {t("research.questionnaire.setQuestionHelp")} <code className="font-mono">{"{object}"}</code>.
            </span>
          </Field>
        </div>
        <Field label={t("research.questionnaire.setObjects")}>
          <TextArea
            key={objects}
            className="min-h-26 w-full"
            defaultValue={objects}
            onBlur={(e) => {
              const r = updateObjects(store.get().project, si, e.target.value);
              store.update(() => ({ project: r.project }));
              if (r.note) toast(r.note);
            }}
          />
        </Field>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label={t("research.questionnaire.setLow")}>
            <TextInput key={`lo-${labels[0]}`} defaultValue={labels[0]} onBlur={(e) => update((p) => setObjectLabel(p, si, 0, e.target.value))} />
          </Field>
          <Field label={t("research.questionnaire.setHigh")}>
            <TextInput key={`hi-${labels[1]}`} defaultValue={labels[1]} onBlur={(e) => update((p) => setObjectLabel(p, si, 1, e.target.value))} />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm font-semibold">
          <input type="checkbox" checked={Boolean(sec.familiarity_required)} onChange={(e) => update((p) => setSectionField(p, si, "familiarity_required", e.target.checked))} />
          {t("research.questionnaire.familiarity")}
        </label>
        <p className="text-xs text-ink-muted">{t("research.questionnaire.familiarityHelp")}</p>
        {sec.output_type === "test_konceptu" ? (
          <Field label={t("research.questionnaire.priceBands")}>
            <TextInput
              key={((sec.metadata?.price_bands as string[] | undefined) || []).join(", ")}
              defaultValue={((sec.metadata?.price_bands as string[] | undefined) || []).join(", ")}
              placeholder={t("research.questionnaire.priceBandsPlaceholder")}
              onBlur={(e) => update((p) => setPriceBands(p, si, e.target.value))}
            />
            <span className="text-xs text-ink-muted">{t("research.questionnaire.priceBandsHelp")}</span>
          </Field>
        ) : null}
        <p className="rounded-sm border border-signal-edge bg-signal-wash p-3 text-sm">
          <strong>{t("research.questionnaire.outputLabel")}</strong> {t("research.questionnaire.outputText")}
        </p>
      </div>
    </article>
  );
}
