"use client";

// 3. Dotazník, rebuilt (research-flow-rehome.md, chunk 4) and drawn as Studio v3
// (studio-v3.md, chunk 5): the classic renderQuestionnaire (:341) under its
// wizard wrapper (:960) -- the three paths, the XLSX/CSV import, the AI build,
// the respondent preview, the guided editor and the final optimisation. A method
// switcher replaces "změnit způsob", an outline sits beside the editor, the
// preview is a tab of it, and the way on is the step's dock. What each control
// does to the project is src/research/questionnaire.ts, parity-tested against the
// original; this file only draws it. The block's "AI: zlepšit blok" is not drawn:
// it does nothing in the classic interface (OI-49).

import { useRouter } from "next/navigation";
import { type DragEvent, type ReactNode, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { workspace } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { fileToBase64 } from "@/research/brief";
import {
  BUILD_FAILED_SUFFIX,
  BUILD_TITLE,
  BUILD_WARN_MS,
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
  SET_TOO_SMALL,
  type Section,
  TEMPLATE_FILENAME,
  UPLOAD_NO_FILE,
  addGuidedQuestion,
  addQuestion,
  addQuestionSection,
  addTrackedSet,
  applyBuilt,
  applyImport,
  applyOptimized,
  buildPayload,
  changeQType,
  optimizePayload,
  questionnaireCounts,
  questionnaireHasQuestions,
  questionnaireView,
  removeQuestion,
  removeSection,
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
} from "@/research/questionnaire";
import type { ResearchProject } from "@/research/model";
import { Icon, type IconName } from "../icons";
import { ActionDock, ChipInput, InlineConfirm, Segmented, Switch } from "../step";
import { AiButton, Button } from "../ui";
import { isNativeResult } from "@/lib/research-agent-jobs";
import { useResearch } from "./context";
import { AiFailureCard, useAiStep } from "./useAiStep";
import { AnalysisFailureCard, useAnalysis } from "./useAnalysis";
import { DeepResearchPanel } from "./DeepResearchPanel";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const INPUT = `min-h-9 w-full rounded-control border border-border-strong bg-surface-raised px-2.5 text-sm text-ink placeholder:text-ink-faint ${FOCUS}`;
const LABEL = "text-xs font-medium text-ink-muted";
const CARD = "rounded-card border border-border bg-surface-raised p-5";

/** A tracked set is measured on 4–15 objects (SET_SIZE). */
const setInvalid = (sec: Section) => {
  const n = (sec.objects || []).length;
  return n < 4 || n > 15;
};
const OBJECT = "{object}";

const jumpTo = (id: string) => document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "center" });

export function QuestionnaireStep() {
  const { store, state, template, runJob, toast, stepHref } = useResearch();
  const router = useRouter();
  const analysis = useAnalysis();
  const step = useAiStep();
  const p = state.project;
  const view = questionnaireView(p);
  const [tab, setTab] = useState<"edit" | "preview">("edit");

  const update = (next: (p: ResearchProject) => ResearchProject, reason?: string) =>
    store.update(({ project }) => ({ project: next(project) }), reason ? { reason } : {});
  const path = (x: QuestionnairePath) =>
    store.update(({ project }) => ({ project: setQuestionnairePath(project, x) }), { reason: "questionnaire_path", invalidateCheck: false });

  // continueQuestionnaireToAudience: the run check and the final review are cleared.
  const toAudienceStep = () => {
    store.update(({ project }) => ({ project: toAudience(project) }), { reason: "questionnaire_done" });
    router.push(stepHref("audience"));
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
      if (isNativeResult(result)) return;
      store.update(() => ({ project: applyBuilt(result, template) }), { reason: "questionnaire_ai_1776" });
    }, (m) => m + BUILD_FAILED_SUFFIX);
  };

  // The optimisation remains an agent proposal; Deep Research has its own durable panel.
  const optimize = () =>
    step.run(async () => {
      await step.saved();
      const s = store.get();
      const result = await runJob("questionnaireOptimize", optimizePayload(s.project), { title: OPTIMIZE_TITLE });
      if (isNativeResult(result)) return;
      store.update(({ analysis: a }) => applyOptimized(result, a, template), { reason: "questionnaire_optimized" });
      toast(OPTIMIZE_DONE);
    });

  const has = questionnaireHasQuestions(p);
  const xs = sections(p);
  const editor = view === "editor" || (view === "upload" && xs.length > 0);
  // The classic screen went on from two places: "Další" once a regular question exists,
  // and "Dotazník mám → Koho se ptát" whenever the editor was open. The dock keeps both.
  const canGo = has || editor;
  const emptyQuestions = xs.reduce((n, s) => n + (s.type === "questions" ? (s.questions || []).filter((q) => !String(q.text || "").trim()).length : 0), 0);
  const badSets = xs.filter((s) => s.type === "object_battery" && setInvalid(s)).length;
  const dock = (
    <ActionDock
      back={{ href: stepHref("plan"), label: `2. ${t("aia.stages.plan")}` }}
      ready={canGo && !emptyQuestions && !badSets}
      note={
        !canGo
          ? t("research.questionnaire.nextHint")
          : emptyQuestions
            ? tv("research.questionnaire.dockEmpty", { n: emptyQuestions })
            : badSets
              ? tv("research.questionnaire.dockSets", { n: badSets })
              : t("research.questionnaire.dockReady")
      }
    >
      <Button variant="primary" className="!rounded-control" onClick={toAudienceStep} disabled={!canGo}>
        {t("research.questionnaire.next")}
        <Icon name="next" size={14} />
      </Button>
    </ActionDock>
  );

  if (view === "choose") return <Choose onPick={path}>{dock}</Choose>;

  const current = String(p.ui_state?.questionnaire_path || "manual") as QuestionnairePath;
  return (
    <div className="flex max-w-[82.5rem] flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className={LABEL}>{t("research.questionnaire.method")}</span>
        <Segmented
          label={t("research.questionnaire.method")}
          value={current === "choose" ? "manual" : current}
          options={[
            { key: "upload", label: t("research.questionnaire.pathUpload") },
            { key: "manual", label: t("research.questionnaire.pathManual") },
            { key: "ai", label: t("research.questionnaire.pathAi") },
          ]}
          onChange={path}
        />
      </div>
      {analysis.failure ? <AnalysisFailureCard failure={analysis.failure} onRetry={() => void build()} /> : null}
      {step.failure ? <AiFailureCard failure={step.failure} title={t("research.questionnaire.failedTitle")} onRetry={() => step.setFailure(null)} /> : null}
      {view === "upload" ? <Upload /> : null}
      {view === "ai" ? (
        <section className={CARD} aria-labelledby="q-ai">
          <h2 id="q-ai" className="text-lg font-semibold">{t("research.questionnaire.aiTitle")}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.aiIntro")}</p>
          <p className="mt-1 text-xs text-ink-muted">{t("research.questionnaire.aiBuildHelp")}</p>
          <AiButton variant="primary" className="mt-4" disabled={step.busy || analysis.busy} onClick={() => void build()}>
            {t("research.questionnaire.aiBuild")}
          </AiButton>
        </section>
      ) : null}
      {editor ? (
        <>
          <div className="flex flex-wrap items-start gap-6">
            <Outline update={update} />
            <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-4">
              <Segmented
                label={t("research.questionnaire.viewLabel")}
                value={tab}
                options={[
                  { key: "edit", label: t("research.questionnaire.viewEdit") },
                  { key: "preview", label: t("research.questionnaire.viewPreview") },
                ]}
                onChange={setTab}
              />
              {tab === "edit" ? <Editor update={update} /> : <Preview items={respondentPreview(p)} />}
            </div>
          </div>
          <section className={CARD} aria-labelledby="q-final">
            <h2 id="q-final" className="text-base font-semibold">{t("research.questionnaire.finalTitle")}</h2>
            <p className="mt-1 text-[13px] leading-5 text-ink-muted">{t("research.questionnaire.finalIntro")}</p>
            <p className="mt-1 text-xs text-ink-muted">{t("research.questionnaire.optimizeHelp")}</p>
            <AiButton className="mt-3" disabled={step.busy} onClick={() => void optimize()}>
              {t("research.questionnaire.optimizeAction")}
            </AiButton>
            <details className="mt-4 rounded-control border border-border bg-surface px-3 py-2" open>
              <summary className="cursor-pointer text-[13px] font-medium">{t("research.questionnaire.deepTitle")}</summary>
              <div className="mt-2"><DeepResearchPanel /></div>
            </details>
          </section>
        </>
      ) : null}
      {dock}
    </div>
  );
}

const PATHS: { key: QuestionnairePath; icon: IconName; title: string; text: string; when: string; chip?: string }[] = [
  { key: "upload", icon: "attach", title: "research.questionnaire.pathUpload", text: "research.questionnaire.pathUploadText", when: "research.questionnaire.whenUpload" },
  { key: "manual", icon: "plus", title: "research.questionnaire.pathManual", text: "research.questionnaire.pathManualText", when: "research.questionnaire.whenManual" },
  { key: "ai", icon: "assistant", title: "research.questionnaire.pathAi", text: "research.questionnaire.pathAiText", when: "research.questionnaire.whenAi", chip: "aia.settings.aiDesignPending" },
];

function Choose({ onPick, children }: { onPick: (x: QuestionnairePath) => void; children: ReactNode }) {
  return (
    <div className="flex max-w-5xl flex-col gap-4">
      <section className={CARD} aria-labelledby="q-choose">
        <h2 id="q-choose" className="text-lg font-semibold">{t("research.questionnaire.chooseTitle")}</h2>
        <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.chooseIntro")}</p>
        <div className="mt-4 grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(220px,1fr))]">
          {PATHS.map((x) => (
            <button
              key={x.key}
              type="button"
              onClick={() => onPick(x.key)}
              className={`flex flex-col items-start gap-2 rounded-card border border-border bg-surface p-4 text-left hover:border-signal hover:bg-signal-tint ${FOCUS}`}
            >
              <span aria-hidden="true" className={`inline-flex size-9 items-center justify-center rounded-control ${x.key === "ai" ? "bg-ai-wash text-ai-ink" : "bg-signal-wash text-signal"}`}>
                <Icon name={x.icon} size={18} />
              </span>
              <span className="text-[15px] font-semibold">{t(x.title)}</span>
              <span className="text-[13px] leading-5 text-ink-muted">{t(x.text)}</span>
              <span className="text-xs text-ink-faint">{t(x.when)}</span>
              {x.chip ? <span className="rounded-md border border-border bg-surface-raised px-1.5 py-0.5 text-xs text-ink-muted">{t(x.chip)}</span> : null}
            </button>
          ))}
        </div>
      </section>
      {children}
    </div>
  );
}

/**
 * uploadQuestionnaireFile: AIA reads the file (ADR 0018), and its sections replace
 * this questionnaire's. The template is AIA's own workbook; its second sheet, NAVOD,
 * is the guide the classic interface's missing methodology link pointed at nothing for.
 */
function Upload() {
  const { store, template, toast, frame } = useResearch();
  const input = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<{ kind: "loading" } | { kind: "error"; message: string } | null>(null);
  const [over, setOver] = useState(false);

  const load = async (f: File | undefined) => {
    if (!f) return setStatus({ kind: "error", message: UPLOAD_NO_FILE });
    setStatus({ kind: "loading" });
    try {
      const r = await workspace.importQuestionnaire(frame.studyId, { filename: f.name, data_b64: await fileToBase64(f) });
      const imported = applyImport(store.get().project, r, template);
      store.update(() => ({ project: imported.project }), { reason: "questionnaire_import" });
      toast(imported.toast);
      setStatus(null);
    } catch (e) {
      setStatus({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    } finally {
      if (input.current) input.current.value = "";
    }
  };

  const downloadTemplate = async () => {
    try {
      saveBlob(await workspace.questionnaireTemplate(frame.studyId), TEMPLATE_FILENAME);
    } catch (e) {
      setStatus({ kind: "error", message: e instanceof Error ? e.message : String(e) });
    }
  };
  const loading = status?.kind === "loading";

  return (
    <section className={CARD} aria-labelledby="q-upload">
      <h2 id="q-upload" className="text-lg font-semibold">{t("research.questionnaire.uploadTitle")}</h2>
      <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.uploadIntro")}</p>
      <ol className="mt-4 flex flex-col gap-4">
        <li className="flex gap-3">
          <span aria-hidden="true" className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-signal-wash font-mono text-xs font-semibold text-signal">1</span>
          <div>
            <Button className="!rounded-control" icon="data" onClick={() => void downloadTemplate()}>{t("research.questionnaire.template")}</Button>
          </div>
        </li>
        <li className="flex gap-3">
          <span aria-hidden="true" className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-signal-wash font-mono text-xs font-semibold text-signal">2</span>
          <div className="min-w-0 flex-1">
            <input ref={input} type="file" hidden accept=".xlsx,.csv" aria-label={t("research.questionnaire.fileLabel")} onChange={(e) => void load(e.target.files?.[0])} />
            <button
              type="button"
              disabled={loading}
              onClick={() => input.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(e: DragEvent) => {
                e.preventDefault();
                setOver(false);
                if (!loading) void load(e.dataTransfer.files[0]);
              }}
              className={`flex w-full flex-col items-center gap-1.5 rounded-card border-[1.5px] border-dashed p-5 hover:border-signal hover:bg-signal-wash disabled:opacity-50 ${FOCUS} ${over ? "border-signal bg-signal-wash" : "border-border-strong bg-surface"}`}
            >
              <Icon name="attach" size={20} className="text-signal" />
              <span className="text-sm font-semibold">{t("research.questionnaire.load")}</span>
              <span className="text-xs text-ink-muted">{t("research.questionnaire.fileLabel")}</span>
            </button>
          </div>
        </li>
      </ol>
      <div aria-live="polite">
        {loading ? (
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
    <section aria-labelledby="q-preview" className="max-w-[560px]">
      <h2 id="q-preview" className="sr-only">{t("research.questionnaire.previewTitle")}</h2>
      <p className="mb-3 text-[13px] text-ink-muted">{t("research.questionnaire.previewHelp")}</p>
      <ol className="flex flex-col gap-3">
        {items.length ? (
          items.map((it) =>
            it.kind === "question" ? (
              <li key={it.index} className={CARD}>
                <div className="text-xs text-ink-muted">{tv("research.questionnaire.previewQuestion", { n: it.index })}</div>
                <div className="mt-0.5 text-[15px] font-medium leading-6">{it.text}</div>
                {it.options.length ? (
                  <div className="mt-3 flex flex-col gap-1.5">
                    {it.options.map((o, i) => (
                      <span key={i} className="inline-flex items-center gap-2 rounded-control border border-border px-3 py-2 text-sm">
                        <span aria-hidden="true" className={`block size-3.5 border border-border-strong ${it.typ === "multi" ? "rounded-sm" : "rounded-full"}`} />
                        {o}
                      </span>
                    ))}
                  </div>
                ) : it.scale ? (
                  <ScaleBoxes low={it.scale[0]} high={it.scale[1]} />
                ) : (
                  <div aria-hidden="true" className="mt-3 h-16 rounded-control border border-border bg-surface" />
                )}
              </li>
            ) : (
              <li key={it.index} className={`${CARD} border-t-[3px] border-t-hue-violet`}>
                <div className="text-xs text-ink-muted">{tv("research.questionnaire.previewSet", { n: it.index, title: it.title })}</div>
                {it.rows.slice(0, 2).map((r, i) => (
                  <div key={i} className="mt-3">
                    <div className="text-sm font-medium">{r}</div>
                    <ScaleBoxes low={it.low} high={it.high} />
                  </div>
                ))}
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

function ScaleBoxes({ low, high, from = 1, to = 10 }: { low: string; high: string; from?: number; to?: number }) {
  const n = Math.max(0, Math.min(12, to - from + 1));
  return (
    <div className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
      <span className="shrink-0">{low}</span>
      <span aria-hidden="true" className="flex flex-1 gap-0.5">
        {Array.from({ length: n }, (_, i) => (
          <i key={i} className="flex h-6 flex-1 items-center justify-center rounded-sm border border-border-strong bg-surface-raised font-mono text-[10px] not-italic">
            {from + i}
          </i>
        ))}
      </span>
      <span className="shrink-0">{high}</span>
    </div>
  );
}

type Update = (next: (p: ResearchProject) => ResearchProject, reason?: string) => void;

/** The questionnaire at a glance: blocks and their questions, then the sets; quick add beneath. */
function Outline({ update }: { update: Update }) {
  const { store, state, prompt, toast } = useResearch();
  const xs = sections(state.project);
  const counts = questionnaireCounts(state.project);

  const guided = async (kind: GuidedKind) => {
    const text = await prompt(GUIDED_PROMPT[kind]);
    if (!text?.trim()) return;
    const choices = kind === "choice" ? await prompt(PROMPT_CHOICES, PROMPT_CHOICES_DEFAULT) : null;
    const r = addGuidedQuestion(store.get().project, kind, text, choices);
    if (!r) return;
    store.update(() => ({ project: r.project }), { reason: "guided_question" });
    setTimeout(() => jumpTo(`qedit_${r.questionId}`), 50);
  };
  const trackedSet = async () => {
    const typ = await prompt(PROMPT_SET_TYPE);
    if (!typ) return;
    const raw = await prompt(PROMPT_SET_ITEMS);
    const r = addTrackedSet(store.get().project, typ, raw);
    if (r && "error" in r) return toast(r.error);
    if (r) store.update(() => ({ project: r.project }));
  };

  let b = 0;
  let q = 0;
  let s = 0;
  const row = (id: string, tag: string, label: string, bad: boolean, depth = 0) => (
    <li key={id}>
      <button
        type="button"
        onClick={() => jumpTo(id)}
        className={`grid w-full grid-cols-[2.25rem_1fr] items-baseline gap-1.5 rounded-control px-1.5 py-1 text-left text-[13px] leading-5 hover:bg-surface-sunken ${FOCUS} ${depth ? "pl-4" : ""}`}
      >
        <span className={`font-mono text-[11px] ${bad ? "text-status-you-ink" : "text-ink-faint"}`}>{tag}</span>
        <span className={`truncate ${bad ? "text-status-you-ink" : depth ? "text-ink" : "font-semibold"}`}>{label || "—"}</span>
      </button>
    </li>
  );

  return (
    <aside aria-labelledby="q-editor" className="sticky top-60 flex flex-[1_1_260px] flex-col gap-3 rounded-card border border-border bg-surface-raised p-4">
      <div>
        <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{t("research.questionnaire.editorTag")}</div>
        <h2 id="q-editor" className="mt-0.5 text-sm font-semibold">{tv("research.questionnaire.editorCounts", counts)}</h2>
      </div>
      {xs.length ? (
        <ul className="flex max-h-[45vh] flex-col gap-0.5 overflow-y-auto">
          {xs.flatMap((sec, si) =>
            sec.type === "questions"
              ? [
                  row(`qblock_${sec.id || si}`, `B${++b}`, String(sec.title || ""), !(sec.questions || []).length),
                  ...(sec.questions || []).map((x) => row(`qedit_${x.id || "Q"}`, `Q${++q}`, String(x.text || ""), !String(x.text || "").trim(), 1)),
                ]
              : [row(`qset_${sec.id || si}`, `S${++s}`, String(sec.title || ""), setInvalid(sec))],
          )}
        </ul>
      ) : null}
      <div className="border-t border-border pt-3">
        <div className={LABEL}>{t("research.questionnaire.quickAdd")}</div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {([["choice", "addChoice"], ["scale", "addScale"], ["open", "addOpen"]] as const).map(([kind, label]) => (
            <Button key={kind} small variant="secondary" icon="plus" className="!rounded-control" onClick={() => void guided(kind)}>{t(`research.questionnaire.${label}`)}</Button>
          ))}
        </div>
        <p className="mt-1.5 text-xs text-ink-muted">{t("research.questionnaire.quickHelp")}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Button small icon="plus" className="!rounded-control" onClick={() => update((p) => addQuestionSection(p))}>{t("research.questionnaire.addBlockV3")}</Button>
        <Button small icon="plus" className="!rounded-control" onClick={() => void trackedSet()}>{t("research.questionnaire.addSet")}</Button>
      </div>
    </aside>
  );
}

/** questionnaireEditorHtml: one panel per block, one card per tracked set. */
function Editor({ update }: { update: Update }) {
  const { state } = useResearch();
  const xs = sections(state.project);
  let blocks = 0;
  let qn = 0;
  let sets = 0;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] leading-5 text-ink-muted">{t("research.questionnaire.editorIntro")}</p>
      {xs.length ? (
        xs.map((sec, si) => {
          if (sec.type === "questions") {
            const first = qn;
            qn += (sec.questions || []).length;
            return <QuestionBlock key={sec.id || si} n={++blocks} firstQ={first} sec={sec} si={si} update={update} />;
          }
          return <TrackedSet key={sec.id || si} n={++sets} sec={sec} si={si} update={update} />;
        })
      ) : (
        <div className="rounded-card border border-dashed border-border-strong p-6 text-center">
          <h3 className="text-base font-semibold">{t("research.questionnaire.emptyTitle")}</h3>
          <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.emptyText")}</p>
        </div>
      )}
    </div>
  );
}

/** A field edited in place: a quiet input that shows its border on hover and focus. */
function InlineField({ label, value, placeholder, onChange, strong = false }: {
  label: string;
  value: string;
  placeholder?: string;
  onChange: (v: string) => void;
  strong?: boolean;
}) {
  return (
    <input
      aria-label={label}
      placeholder={placeholder ?? label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`-ml-1.5 w-full rounded-control border border-transparent bg-transparent px-1.5 py-0.5 text-ink placeholder:text-ink-faint hover:border-border focus:border-signal focus:bg-surface-raised ${FOCUS} ${strong ? "text-[15px] font-semibold" : "text-[13px] text-ink-muted"}`}
    />
  );
}

function QuestionBlock({ n, firstQ, sec, si, update }: { n: number; firstQ: number; sec: Section; si: number; update: Update }) {
  const qs = sec.questions || [];
  const [confirming, setConfirming] = useState(false);
  return (
    <article id={`qblock_${sec.id || si}`} className="scroll-mt-60 rounded-panel bg-surface-sunken p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{tv("research.questionnaire.blockHead", { n, q: qs.length })}</div>
          <InlineField strong label={t("research.questionnaire.blockTitle")} value={sec.title || ""} onChange={(v) => update((p) => setSectionField(p, si, "title", v))} />
          <InlineField label={t("research.questionnaire.blockPurpose")} value={sec.purpose || ""} onChange={(v) => update((p) => setSectionField(p, si, "purpose", v))} />
        </div>
        {confirming ? (
          <InlineConfirm message={t("research.questionnaire.removeBlockConfirm")} action={t("research.questionnaire.remove")} onConfirm={() => update((p) => removeSection(p, si))} onCancel={() => setConfirming(false)} />
        ) : (
          <Button small variant="quiet" icon="trash" className="!rounded-control" onClick={() => setConfirming(true)}>{t("research.questionnaire.remove")}</Button>
        )}
      </div>
      <div className="mt-3 flex flex-col gap-3">
        {qs.length ? (
          qs.map((q, qi) => <QuestionCard key={q.id || qi} n={firstQ + qi + 1} q={q} si={si} qi={qi} update={update} />)
        ) : (
          <p className="rounded-control border border-signal-edge bg-signal-wash p-3 text-sm">{t("research.questionnaire.blockEmpty")}</p>
        )}
        <div>
          <Button small icon="plus" className="!rounded-control" onClick={() => update((p) => addQuestion(p, si))}>{t("research.questionnaire.addQuestionV3")}</Button>
        </div>
      </div>
    </article>
  );
}

const TYPES = [
  ["vyber", "typeChoice"],
  ["multi", "typeMulti"],
  ["skala", "typeScale"],
  ["otevrena", "typeOpen"],
] as const;

/** questionCard: the type as pills, the text, and below it what the type needs. */
function QuestionCard({ n, q, si, qi, update }: { n: number; q: Question; si: number; qi: number; update: Update }) {
  const typ = String(q.typ || "");
  const skala = q.skala || [1, 10];
  const labels = q.popisky_skaly || ["vůbec", "zcela"];
  return (
    <div id={`qedit_${q.id || "Q"}`} className="scroll-mt-60 rounded-card border border-border bg-surface-raised p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-signal-wash px-1.5 py-0.5 font-mono text-xs font-semibold text-signal" title={String(q.id || "")}>Q{n}</span>
        <span className="sr-only">{q.id || "Q"}</span>
        <div role="radiogroup" aria-label={t("research.questionnaire.questionType")} className="flex flex-wrap gap-1">
          {TYPES.map(([key, label]) => {
            const on = typ === key;
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => !on && update((p) => changeQType(p, si, qi, key))}
                className={`whitespace-nowrap rounded-pill border px-2.5 text-xs leading-6 ${FOCUS} ${on ? "border-signal bg-signal-wash font-semibold text-signal" : "border-border bg-surface text-ink-muted hover:text-ink"}`}
              >
                {t(`research.questionnaire.${label}`)}
              </button>
            );
          })}
        </div>
        <Button
          small
          variant="quiet"
          className="ml-auto"
          aria-label={tv("research.questionnaire.removeQuestion", { id: String(q.id || "Q") })}
          onClick={() => update((p) => removeQuestion(p, si, qi))}
        >
          ×
        </Button>
      </div>
      <textarea
        aria-label={t("research.questionnaire.questionText")}
        value={q.text || ""}
        onChange={(e) => update((p) => setQuestionText(p, si, qi, e.target.value))}
        rows={2}
        className={`mt-3 block w-full resize-y rounded-control border border-border-strong bg-surface px-3 py-2 text-[15px] font-medium leading-6 ${FOCUS} ${String(q.text || "").trim() ? "" : "border-status-you-ink"}`}
      />
      {typ === "vyber" || typ === "multi" ? (
        <OptionRows key={(q.kategorie || []).join("\n")} multi={typ === "multi"} options={q.kategorie || []} onCommit={(raw) => update((p) => setQuestionOptions(p, si, qi, raw))} />
      ) : null}
      {typ === "skala" ? (
        <div className="mt-3 flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              key={`lo-${labels[0]}`}
              aria-label={t("research.questionnaire.scaleLow")}
              defaultValue={labels[0]}
              onBlur={(e) => update((p) => setScaleLabel(p, si, qi, 0, e.target.value))}
              className={`${INPUT} !w-32`}
            />
            <div className="min-w-40 flex-1">
              <ScaleBoxes low="" high="" from={Number(skala[0])} to={Number(skala[1])} />
            </div>
            <input
              key={`hi-${labels[1]}`}
              aria-label={t("research.questionnaire.scaleHigh")}
              defaultValue={labels[1]}
              onBlur={(e) => update((p) => setScaleLabel(p, si, qi, 1, e.target.value))}
              className={`${INPUT} !w-32`}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            <span>{t("research.questionnaire.range")}</span>
            <input key={`min-${skala[0]}`} type="number" min={0} max={11} aria-label={t("research.questionnaire.scaleMin")} defaultValue={String(skala[0])} onBlur={(e) => update((p) => setScaleEnd(p, si, qi, 0, e.target.value))} className={`${INPUT} !w-20`} />
            <span aria-hidden="true">–</span>
            <input key={`max-${skala[1]}`} type="number" min={0} max={11} aria-label={t("research.questionnaire.scaleMax")} defaultValue={String(skala[1])} onBlur={(e) => update((p) => setScaleEnd(p, si, qi, 1, e.target.value))} className={`${INPUT} !w-20`} />
          </div>
        </div>
      ) : null}
      {typ === "otevrena" ? (
        <p className="mt-3 rounded-control border border-dashed border-border-strong px-3 py-2 text-xs text-ink-muted">{t("research.questionnaire.openNote")}</p>
      ) : null}
    </div>
  );
}

/**
 * A choice question's options, one row each. Typed rows are kept on the page and
 * applied when the list is left, as the classic textarea's onchange: trimmed, empty
 * rows dropped (setQuestionOptions). Enter adds a row below; × removes one.
 */
function OptionRows({ options, multi, onCommit }: { options: string[]; multi: boolean; onCommit: (raw: string) => void }) {
  const [rows, setRows] = useState<string[]>(options.length ? options : [""]);
  const list = useRef<HTMLDivElement>(null);
  const commit = (next = rows) => onCommit(next.join("\n"));
  const focusRow = (i: number) => setTimeout(() => list.current?.querySelectorAll("input")[i]?.focus(), 0);
  return (
    <div
      ref={list}
      role="group"
      aria-label={t("research.questionnaire.options")}
      className="mt-3 flex flex-col gap-1.5"
      onBlur={(e) => {
        if (!list.current?.contains(e.relatedTarget as Node | null)) commit();
      }}
    >
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-2">
          <span aria-hidden="true" className={`block size-3.5 shrink-0 border border-border-strong ${multi ? "rounded-sm" : "rounded-full"}`} />
          <input
            aria-label={tv("research.questionnaire.optionN", { n: i + 1 })}
            value={r}
            onChange={(e) => setRows(rows.map((x, j) => (j === i ? e.target.value : x)))}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              e.preventDefault();
              setRows([...rows.slice(0, i + 1), "", ...rows.slice(i + 1)]);
              focusRow(i + 1);
            }}
            className={`${INPUT} !min-h-8`}
          />
          <button
            type="button"
            aria-label={tv("research.questionnaire.optionRemove", { n: i + 1 })}
            onClick={() => {
              const next = rows.filter((_, j) => j !== i);
              setRows(next.length ? next : [""]);
              commit(next);
            }}
            className={`rounded-sm px-1.5 text-ink-faint hover:text-ink ${FOCUS}`}
          >
            ×
          </button>
        </div>
      ))}
      <div>
        <Button small variant="quiet" icon="plus" onClick={() => {
          setRows([...rows, ""]);
          focusRow(rows.length);
        }}>
          {t("research.questionnaire.optionAdd")}
        </Button>
      </div>
    </div>
  );
}

/** objectSection: a tracked set of 4–15 comparable objects on one question and scale. */
function TrackedSet({ n, sec, si, update }: { n: number; sec: Section; si: number; update: Update }) {
  const { store } = useResearch();
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const labels = sec.scale_labels || ["vůbec", "velmi"];
  const objects = sec.objects || [];
  const question = sec.object_question || "Jak hodnotíte {object}?";
  const bad = setInvalid(sec);
  // updateObjects takes the objects one per line, as the classic textarea gave them.
  const setObjects = (next: string[]) => {
    const r = updateObjects(store.get().project, si, next.join("\n"));
    store.update(() => ({ project: r.project }));
    setNote(r.note);
  };
  return (
    <article id={`qset_${sec.id || si}`} className="scroll-mt-60 flex flex-col gap-3 rounded-card border border-border border-t-[3px] border-t-hue-violet bg-surface-raised p-4">
      <div className="flex items-start gap-3">
        <span className="mt-1 whitespace-nowrap rounded-md bg-hue-violet/12 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-hue-violet">{tv("research.questionnaire.setBadge", { n })}</span>
        <div className="min-w-0 flex-1">
          <InlineField strong label={t("research.questionnaire.setTitle")} value={sec.title || ""} onChange={(v) => update((p) => setSectionField(p, si, "title", v))} />
        </div>
        <span className={`whitespace-nowrap rounded-md px-1.5 py-0.5 font-mono text-xs ${bad ? "bg-status-you-wash text-status-you-ink" : "bg-surface-sunken text-ink-muted"}`}>
          {tv("research.questionnaire.setCount", { n: objects.length })}
        </span>
        {confirming ? (
          <InlineConfirm message={t("research.questionnaire.removeSetConfirm")} action={t("research.questionnaire.remove")} onConfirm={() => update((p) => removeSection(p, si))} onCancel={() => setConfirming(false)} />
        ) : (
          <Button small variant="quiet" icon="trash" className="!rounded-control" onClick={() => setConfirming(true)}>{t("research.questionnaire.remove")}</Button>
        )}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.questionnaire.setFamily")}</span>
          <input className={INPUT} value={sec.object_family || sec.object_type || ""} placeholder={t("research.questionnaire.setFamilyPlaceholder")} onChange={(e) => update((p) => setObjectFamily(p, si, e.target.value))} />
          <span className="text-xs text-ink-muted">{t("research.questionnaire.setFamilyHelp")}</span>
        </label>
        <label className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.questionnaire.setPurpose")}</span>
          <input className={INPUT} value={sec.purpose || ""} onChange={(e) => update((p) => setSectionField(p, si, "purpose", e.target.value))} />
        </label>
      </div>
      <div className="flex flex-col gap-1">
        <span className={LABEL}>{t("research.questionnaire.setQuestion")}</span>
        <div className="flex gap-2">
          <input
            aria-label={t("research.questionnaire.setQuestion")}
            className={`${INPUT} ${question.includes(OBJECT) ? "" : "!border-status-you-ink"}`}
            value={question}
            onChange={(e) => update((p) => setSectionField(p, si, "object_question", e.target.value))}
          />
          <Button small className="!min-h-9 shrink-0 !rounded-control font-mono" onClick={() => update((p) => setSectionField(p, si, "object_question", `${question.trimEnd()} ${OBJECT}`))}>
            + {OBJECT}
          </Button>
        </div>
        {question.includes(OBJECT) ? (
          <span className="text-xs text-ink-muted">
            {t("research.questionnaire.setQuestionHelp")} <code className="font-mono">{OBJECT}</code>.
          </span>
        ) : (
          <span className="text-xs text-status-you-ink">{tv("research.questionnaire.setQuestionMissing", { object: OBJECT })}</span>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <span className={LABEL}>{t("research.questionnaire.setObjectsV3")}</span>
        <ChipInput
          label={t("research.questionnaire.setObjectAdd")}
          placeholder={t("research.questionnaire.setObjectAdd")}
          values={objects}
          onAdd={(v) => setObjects([...objects, v])}
          onRemove={(i) => setObjects(objects.filter((_, j) => j !== i))}
        />
        {note || (objects.length && bad) ? <span className="text-xs text-status-you-ink">{note || SET_TOO_SMALL}</span> : null}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.questionnaire.setLow")}</span>
          <input key={`lo-${labels[0]}`} className={INPUT} defaultValue={labels[0]} onBlur={(e) => update((p) => setObjectLabel(p, si, 0, e.target.value))} />
        </label>
        <label className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.questionnaire.setHigh")}</span>
          <input key={`hi-${labels[1]}`} className={INPUT} defaultValue={labels[1]} onBlur={(e) => update((p) => setObjectLabel(p, si, 1, e.target.value))} />
        </label>
      </div>
      <div className="flex flex-col gap-1">
        <Switch checked={Boolean(sec.familiarity_required)} onChange={(on) => update((p) => setSectionField(p, si, "familiarity_required", on))} label={<b className="font-semibold">{t("research.questionnaire.familiarity")}</b>} />
        <p className="pl-[44px] text-xs text-ink-muted">{t("research.questionnaire.familiarityHelp")}</p>
      </div>
      {sec.output_type === "test_konceptu" ? (
        <label className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.questionnaire.priceBands")}</span>
          <input
            key={((sec.metadata?.price_bands as string[] | undefined) || []).join(", ")}
            className={INPUT}
            defaultValue={((sec.metadata?.price_bands as string[] | undefined) || []).join(", ")}
            placeholder={t("research.questionnaire.priceBandsPlaceholder")}
            onBlur={(e) => update((p) => setPriceBands(p, si, e.target.value))}
          />
          <span className="text-xs text-ink-muted">{t("research.questionnaire.priceBandsHelp")}</span>
        </label>
      ) : null}
      <p className="rounded-control border border-signal-edge bg-signal-tint p-3 text-[13px]">
        <strong>{t("research.questionnaire.outputLabel")}</strong> {t("research.questionnaire.outputText")}
      </p>
    </article>
  );
}

