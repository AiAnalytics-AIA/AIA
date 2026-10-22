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
import { type DragEvent, type ReactNode, createContext, useContext, useEffect, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { hashTarget, questionElementId, questionnairePlace, setElementId } from "@/lib/answerability";
import { workspace } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { fileToBase64 } from "@/research/brief";
import {
  BUILD_FAILED_SUFFIX,
  BUILD_TITLE,
  BUILD_WARN_MS,
  type GuidedKind,
  OPTIMIZE_DONE,
  OPTIMIZE_TITLE,
  type PreviewItem,
  type Question,
  type QuestionnairePath,
  SET_TOO_SMALL,
  type Section,
  TEMPLATE_FILENAME,
  UPLOAD_NO_FILE,
  addGuidedQuestion,
  addNamedSection,
  addNamedTrackedSet,
  addQuestionTo,
  applyBuilt,
  applyImport,
  applyOptimized,
  buildPayload,
  changeQType,
  optimizePayload,
  questionnaireCounts,
  countWords,
  countsWords,
  questionnaireHasQuestions,
  questionnaireView,
  questionCondition,
  removeCondition,
  removeQuestion,
  removeSection,
  restoreOption,
  type WordingEdit,
  wordingEscape,
  wordingFocused,
  wordingTyped,
  restoreQuestion,
  restoreSection,
  respondentPreview,
  sections,
  setObjectFamily,
  priceBandsOf,
  priceProblem,
  setPriceBandList,
  setQuestionOptions,
  setQuestionText,
  setQuestionnairePath,
  setQuestionScale,
  setSetScaleLabels,
  setSectionField,
  toAudience,
  updateObjects,
  SET_SIZE,
} from "@/research/questionnaire";
import type { ResearchProject } from "@/research/model";
import { COMPARISONS, CONCEPT_TEST, comparisonOf, danglingLinks, linkKey, linksOf, researchQuestionsOf, setComparison, setConceptTest, toggleQuestionLink, toggleSectionLink, togglesConceptTest } from "@/research/trace";
import { Icon, type IconName } from "../icons";
import { ActionDock, ChipInput, InlineConfirm, Segmented, Switch } from "../step";
import { ChoiceChips } from "@/components/ui/ChoiceChips";
import { InlineCreateRow } from "@/components/ui/InlineCreateRow";
import { InlineText } from "@/components/ui/InlineText";
import { editKeyAction } from "@/lib/inline-edit";
import { AiButton, Button } from "../ui";
import { isNativeResult } from "@/lib/research-agent-jobs";
import { openPlace, scrollBehavior, scrollToPlace } from "@/lib/open-place";
import { useResearch } from "./context";
import { useFrame } from "./frame-hook";
import { ID_SOURCE, type TargetKind, aiaId } from "@/lib/workbench-artifacts";
import { QuestionnaireDependencies } from "./QuestionnaireDependencies";
import { QuestionnaireStrip } from "./QuestionnaireStrip";
import { InspectorSlot } from "./Inspector";
import { questionnaireIssues } from "@/research/lane";
import { AskLead, useAskLead, useLeadOwnsAiStarts } from "./AskLead";
import { AiFailureCard, useAiStep } from "./useAiStep";
import { AnalysisFailureCard, useAnalysis } from "./useAnalysis";
import { DeepResearchPanel } from "./DeepResearchPanel";
import { ScaleEditor, ScaleUndoProvider, useEditorUndo } from "./ScaleEditor";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const INPUT = `min-h-9 w-full rounded-control border border-border-strong bg-surface-raised px-2.5 text-sm text-ink placeholder:text-ink-faint ${FOCUS}`;
const LABEL = "text-xs font-medium text-ink-muted";
const CARD = "rounded-card border border-border bg-surface-raised p-5";

/** The longest question wording a row takes: a question, not a name (NAME_MAX is a folder's). */
const WORDING_MAX = 1000;

/**
 * The `data-aia` a block, a tracked set or a question carries for the Research Lead (the contract's
 * targets, lib/workbench-artifacts.ts): `section:<id>` and `question:<id>` by the item's stored id.
 * An item with no id yet, or one outside the id grammar, carries none: nothing is named for it.
 * Each mark names one element: a repeated id (an import or a merged proposal keeps two items,
 * design_items.py occurrence_keys) marks its first occurrence in the questionnaire's order only.
 */
const ID_RULE = new RegExp(ID_SOURCE);
type LeadMarks = { sections: (string | undefined)[]; questions: (string | undefined)[][] };
function leadMarks(xs: Section[]): LeadMarks {
  const given = new Set<string>();
  const mark = (kind: TargetKind, id: unknown): string | undefined => {
    if (typeof id !== "string" || !ID_RULE.test(id)) return undefined;
    const aia = aiaId(kind, id);
    if (given.has(aia)) return undefined;
    given.add(aia);
    return aia;
  };
  const sections: (string | undefined)[] = [];
  const questions: (string | undefined)[][] = [];
  for (const sec of xs) {
    sections.push(mark("section", sec.id));
    questions.push(sec.type === "questions" ? (sec.questions || []).map((q) => mark("question", q.id)) : []);
  }
  return { sections, questions };
}
const useLeadMarks = (): LeadMarks => leadMarks(sections(useResearch().state.project));

/**
 * A block or a tracked set removed at once, with "Vrátit" on the editor's toast (input-interactions
 * I6, audit A18): the undo puts the same section back where it was.
 */
type EditorUndo = ReturnType<typeof useEditorUndo>;

/** Offer Vrátit for a delete, naming the item by at most 60 characters of its wording or title. */
function offerRestore(undo: EditorUndo, what: "questionRemoved" | "blockRemoved" | "setRemoved" | "optionRemoved", name: unknown, restore: () => void) {
  const text = String(name || "").trim();
  const clipped = text.length > 60 ? `${text.slice(0, 59)}…` : text;
  undo?.offer({ message: clipped ? tv(`research.questionnaire.undo.${what}`, { name: clipped }) : t(`research.questionnaire.undo.${what}Bare`), undo: restore });
}

function removeWithUndo(update: Update, undo: EditorUndo, si: number, sec: Section, what: "blockRemoved" | "setRemoved") {
  update((p) => removeSection(p, si));
  offerRestore(undo, what, sec.title, () => update((p) => restoreSection(p, si, sec)));
}

/** A tracked set is measured on 4–15 objects (SET_SIZE). */
const setInvalid = (sec: Section) => {
  const n = (sec.objects || []).length;
  return n < 4 || n > 15;
};
const OBJECT = "{object}";

const jumpTo = (id: string) => scrollToPlace(id, "center");
/**
 * How the outline opens a place (QF-6): the editor's card or set, scrolled to and focused, so Tab
 * goes on from there; from the respondent preview, which draws no editor, Upravit first.
 */
const OpenPlace = createContext<(id: string) => void>((id) => void openPlace(id, "center"));

export function QuestionnaireStep() {
  const { store, state, template, runJob, toast, stepHref } = useResearch();
  const router = useRouter();
  const analysis = useAnalysis();
  const step = useAiStep();
  const leadOwnsAiStarts = useLeadOwnsAiStarts();
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
  const buildJob = () =>
    step.run(async () => {
      if (!(await step.providerOk())) return;
      await step.saved();
      const s = store.get();
      const result = await runJob("researchBuildQuestionnaire", buildPayload(s.project, s.analysis), { title: BUILD_TITLE, warnMs: BUILD_WARN_MS });
      if (isNativeResult(result)) return;
      store.update(({ project: before }) => ({ project: applyBuilt(result, template, before) }), { reason: "questionnaire_ai_1776" });
    }, (m) => m + BUILD_FAILED_SUFFIX);
  const build = async () => {
    step.setFailure(null);
    if (!(await analysis.analyse())) return;
    await buildJob();
  };
  // The build's analysis waited for budget and was lifted: the same analysis job goes on, and on
  // its accept the build the person asked for follows, as it does after `analyse` (CR-2). The
  // analysis is not asked again.
  const continueBuild = async (jobId: string) => {
    step.setFailure(null);
    if (!(await analysis.resume(jobId))) return;
    await buildJob();
  };

  // The optimisation remains an agent proposal; Deep Research has its own durable panel.
  const optimize = () =>
    step.run(async () => {
      await step.saved();
      const s = store.get();
      const result = await runJob("questionnaireOptimize", optimizePayload(s.project), { title: OPTIMIZE_TITLE });
      if (isNativeResult(result)) return;
      store.update(({ project: before, analysis: a }) => applyOptimized(result, a, template, before), { reason: "questionnaire_optimized" });
      toast(OPTIMIZE_DONE);
    });

  const has = questionnaireHasQuestions(p);
  const xs = sections(p);
  const editor = view === "editor" || (view === "upload" && xs.length > 0);
  // A link to a place in the questionnaire (#qedit_<id>, #qset_<id>, #q-comparisons: the Run
  // stage's gaps, lib/answerability.ts gapFixes) opens the editor there, once it is drawn; a place
  // it no longer has opens the editor itself. A question or set is named by the id the server
  // compiled, which is not the one drawn here (questionnairePlace).
  useEffect(() => {
    if (!editor) return;
    const read = () => {
      const id = hashTarget(window.location.hash);
      if (!id) return;
      setTab("edit");
      const place = questionnairePlace(id, sections(store.get().project));
      // Focus follows the scroll there, so Tab goes on from the place (openPlace).
      window.requestAnimationFrame(() => openPlace(document.getElementById(place) ? place : "q-editor", "center"));
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, [editor, store]);
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
  // React commits the tab before the frame, so the place is drawn when it opens (as for a hash).
  const open = (id: string) => {
    setTab("edit");
    window.requestAnimationFrame(() => openPlace(id, "center"));
  };
  // Around the whole stage: a delete's Vrátit outlives the preview tab, and the editor itself when
  // the last block goes on the upload or AI path.
  return (
    <OpenPlace.Provider value={open}>
    <ScaleUndoProvider>
    <div className="flex max-w-[82.5rem] flex-col gap-4">
      {editor ? (
        <InspectorSlot>
          <QuestionnaireReadiness />
        </InspectorSlot>
      ) : null}
      {/* One toolbar: where the questionnaire comes from, how it is seen, and the AI that improves it. */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-card border border-border bg-surface-raised px-3 py-2">
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
        {editor ? (
          <>
            <span aria-hidden="true" className="hidden h-6 w-px bg-border sm:block" />
            <Segmented
              label={t("research.questionnaire.viewLabel")}
              value={tab}
              options={[
                { key: "edit", label: t("research.questionnaire.viewEdit") },
                { key: "preview", label: t("research.questionnaire.viewPreview") },
              ]}
              onChange={setTab}
            />
            <span className="flex-1" />
            {!leadOwnsAiStarts ? (
              <AiButton small disabled={step.busy} onClick={() => void optimize()}>
                {t("research.questionnaire.optimizeAction")}
              </AiButton>
            ) : null}
          </>
        ) : null}
      </div>
      {editor && current === "ai" ? <AiOnExisting /> : null}
      {analysis.failure ? <AnalysisFailureCard failure={analysis.failure} onRetry={() => void build()} onContinue={(id) => void continueBuild(id)} /> : null}
      {step.failure ? <AiFailureCard failure={step.failure} title={t("research.questionnaire.failedTitle")} onRetry={() => step.setFailure(null)} onContinue={(id) => void step.resume(id)} /> : null}
      {view === "upload" ? <Upload /> : null}
      {view === "ai" ? (
        <section className={CARD} aria-labelledby="q-ai">
          <h2 id="q-ai" className="text-lg font-semibold">{t("research.questionnaire.aiTitle")}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("research.questionnaire.aiIntro")}</p>
          {!leadOwnsAiStarts ? (
            <AiButton variant="primary" className="mt-4" disabled={step.busy || analysis.busy} onClick={() => void build()}>
              {t("research.questionnaire.aiBuild")}
            </AiButton>
          ) : <AskLead className="mt-4" what="Návrh dotazníku i jeho úpravu" />}
        </section>
      ) : null}
      {editor ? (
        <>
          <div className="flex flex-wrap items-start gap-4">
            <Outline />
            <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-4">
              {tab === "edit" ? <Editor update={update} /> : <Preview items={respondentPreview(p)} />}
            </div>
          </div>
          <section className={CARD} aria-labelledby="q-final">
            <h2 id="q-final" className="text-base font-semibold">{t("research.questionnaire.finalTitle")}</h2>
            <p className="mt-1 text-[13px] leading-5 text-ink-muted">{t("research.questionnaire.finalIntro")}</p>
            <p className="mt-1 text-xs text-ink-muted">{t("research.questionnaire.optimizeHelp")}</p>
            <details className="mt-3 rounded-control border border-border bg-surface px-3 py-2" open>
              <summary className="cursor-pointer text-[13px] font-medium">{t("research.questionnaire.deepTitle")}</summary>
              <div className="mt-2"><DeepResearchPanel /></div>
            </details>
          </section>
        </>
      ) : null}
      {dock}
    </div>
    </ScaleUndoProvider>
    </OpenPlace.Provider>
  );
}

/** The questionnaire's readiness beside it: what stops the run, each a way to the question. */
function QuestionnaireReadiness() {
  const { state } = useResearch();
  const counts = questionnaireCounts(state.project);
  const issues = questionnaireIssues(state.project);
  const firstUnworded = () => document.querySelector<HTMLElement>("[data-unworded]")?.scrollIntoView?.({ behavior: scrollBehavior(), block: "center" });
  const rows: { label: string; detail: string; ok: boolean; go?: () => void }[] = [
    { label: countsWords(counts), detail: t("research.questionnaire.readyCountsDetail"), ok: counts.questions > 0 },
    ...(issues.empty ? [{ label: tv("research.questionnaire.dockEmpty", { n: issues.empty }), detail: t("research.questionnaire.unworded"), ok: false, go: firstUnworded }] : []),
    ...(issues.badSets ? [{ label: tv("research.questionnaire.dockSets", { n: issues.badSets }), detail: SET_SIZE, ok: false }] : []),
  ];
  return (
    <section aria-labelledby="q-ready" className="flex flex-col gap-2 rounded-card border border-border bg-surface-raised p-3.5">
      <h2 id="q-ready" className="text-sm font-semibold">{t("research.questionnaire.readyTitle")}</h2>
      <ul className="flex flex-col gap-0.5">
        {rows.map((r) => (
          <li key={r.label}>
            <button type="button" disabled={!r.go} onClick={r.go} className={`grid w-full grid-cols-[18px_1fr] items-start gap-2 rounded-control p-1.5 text-left enabled:hover:bg-surface-sunken ${FOCUS}`}>
              <span aria-hidden="true" className={`mt-px inline-flex size-[18px] items-center justify-center rounded-full ${r.ok ? "bg-status-done text-surface-raised" : "bg-status-you text-ink"}`}>
                {r.ok ? <Icon name="done" size={10} /> : <span className="text-[11px] font-bold leading-none">!</span>}
              </span>
              <span className="min-w-0">
                <span className="block text-[13px] font-medium leading-[18px]">{r.label}</span>
                <span className="block text-xs leading-4 text-ink-muted">{r.detail}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
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

/**
 * "Sestavit s AI" on a questionnaire that already has items (QF-4): the AI does not build it anew
 * (questionnaireView keeps the editor), so the choice says what AI does here instead and, in the
 * workbench, asks the Lead in one click; elsewhere the toolbar's optimize button is the way.
 */
function AiOnExisting() {
  const leadOwns = useLeadOwnsAiStarts();
  const ask = useAskLead();
  return (
    <div role="status" className="flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface-raised px-4 py-3 text-sm">
      <span className="min-w-0 flex-1">{t(leadOwns ? "research.questionnaire.aiExisting.lead" : "research.questionnaire.aiExisting.optimize")}</span>
      {leadOwns && ask ? <Button small onClick={() => ask(t("research.questionnaire.aiExisting.message"))}>{t("research.questionnaire.aiExisting.ask")}</Button> : null}
    </div>
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
function Outline() {
  const { store, state } = useResearch();
  const open = useContext(OpenPlace);
  const xs = sections(state.project);
  const counts = questionnaireCounts(state.project);

  // Quick add (input-interactions I5, audit A6, A7): the kind chosen, the wording typed in the row;
  // Enter adds it to the first block and opens the next row. A single choice starts as Ano / Ne,
  // its options then edited on its card, never typed as a comma string in a prompt.
  const [kind, setKind] = useState<GuidedKind>("choice");
  const quickAdd = (text: string) => {
    const r = addGuidedQuestion(store.get().project, kind, text, null);
    if (!r) return t("research.questionnaire.inlineAdd.empty");
    store.update(() => ({ project: r.project }), { reason: "guided_question" });
  };
  // A block and a set named in their rows (audit A21, A8), then opened where they are.
  const newBlock = (name: string) => {
    const r = addNamedSection(store.get().project, name);
    if (!r) return t("research.questionnaire.inlineAdd.empty");
    store.update(() => ({ project: r.project }), { reason: "questionnaire_block" });
    setTimeout(() => jumpTo(`qblock_${r.sectionId}`), 50);
  };
  const newSet = (name: string) => {
    const r = addNamedTrackedSet(store.get().project, name);
    if (!r) return t("research.questionnaire.inlineAdd.empty");
    store.update(() => ({ project: r.project }), { reason: "questionnaire_set" });
    setTimeout(() => {
      jumpTo(setElementId({ id: r.sectionId }, 0));
      document.querySelector<HTMLInputElement>(`#${setElementId({ id: r.sectionId }, 0)} input[aria-label="${t("research.questionnaire.setObjectAdd")}"]`)?.focus();
    }, 50);
  };

  let b = 0;
  let q = 0;
  let s = 0;
  const row = (id: string, tag: string, label: string, bad: boolean, depth = 0) => (
    <li key={id}>
      <button
        type="button"
        onClick={() => open(id)}
        className={`grid w-full grid-cols-[2.25rem_1fr] items-baseline gap-1.5 rounded-control px-1.5 py-1 text-left text-[13px] leading-5 hover:bg-surface-sunken ${FOCUS} ${depth ? "pl-4" : ""}`}
      >
        <span className={`font-mono text-[11px] ${bad ? "text-status-you-ink" : "text-ink-faint"}`}>{tag}</span>
        <span className={`truncate ${bad ? "text-status-you-ink" : depth ? "text-ink" : "font-semibold"}`}>{label || "—"}</span>
      </button>
    </li>
  );

  // The wrapper stretches to its flex line, and the outline sticks only within it: beside the
  // editor the line is the editor's height; wrapped onto a line of its own (a narrow pane, a
  // phone) it is the outline's, so the outline scrolls away instead of covering the editor.
  return (
    <div className="flex flex-[1_1_240px] flex-col self-stretch">
      <aside aria-labelledby="q-editor" className="sticky top-[136px] flex flex-col gap-3 rounded-card border border-border bg-surface-raised p-3.5">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{t("research.questionnaire.editorTag")}</div>
          <h2 id="q-editor" className={`mt-0.5 rounded-sm text-sm font-semibold ${FOCUS}`}>{countsWords(counts)}</h2>
        </div>
        {xs.length ? (
          <ul className="flex max-h-[45vh] flex-col gap-0.5 overflow-y-auto">
            {xs.flatMap((sec, si) =>
              sec.type === "questions"
                ? [
                    row(`qblock_${sec.id || si}`, `B${++b}`, String(sec.title || ""), !(sec.questions || []).length),
                    ...(sec.questions || []).map((x) => row(questionElementId(x), `Q${++q}`, String(x.text || ""), !String(x.text || "").trim(), 1)),
                  ]
                : [row(setElementId(sec, si), `S${++s}`, String(sec.title || ""), setInvalid(sec))],
            )}
          </ul>
        ) : null}
        <div className="flex flex-col gap-1.5 border-t border-border pt-3">
          <div className={LABEL}>{t("research.questionnaire.quickAdd")}</div>
          <ChoiceChips
            label={t("research.questionnaire.inlineAdd.kind")}
            value={kind}
            options={([["choice", "addChoice"], ["scale", "addScale"], ["open", "addOpen"]] as const).map(([key, label]) => ({ key, label: t(`research.questionnaire.${label}`) }))}
            onChange={setKind}
          />
          <InlineCreateRow label={t("research.questionnaire.inlineAdd.question")} maxLength={WORDING_MAX} onCreate={quickAdd} />
          <p className="text-xs text-ink-muted">{t("research.questionnaire.quickHelp")}</p>
        </div>
        <div className="flex flex-col gap-1">
          <InlineCreateRow label={t("research.questionnaire.addBlockV3")} next={false} onCreate={newBlock} />
          <InlineCreateRow label={t("research.questionnaire.addSet")} next={false} placeholder={t("research.questionnaire.inlineAdd.setPlaceholder")} onCreate={newSet} />
        </div>
      </aside>
    </div>
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
      <QuestionnaireStrip />
      <p className="text-[13px] leading-5 text-ink-muted">{t("research.questionnaire.editorIntro")}</p>
      <ResearchQuestionComparisons update={update} />
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
      <QuestionnaireDependencies />
    </div>
  );
}

/**
 * "Jak výzkumné otázky zodpovíme": for each research question of the plan, the comparison
 * that answers it (run-recovery-and-truth 3c). Readiness checks that the questions linked
 * to it can carry that comparison; "neurčeno" declares nothing and checks nothing.
 */
/** "Neurčeno": no comparison declared, so readiness checks none (setComparison(…, null)). */
const NONE = "none";

function ResearchQuestionComparisons({ update }: { update: Update }) {
  const { state } = useResearch();
  const stated = researchQuestionsOf(state.project);
  if (!stated.length) return null;
  return (
    <section id="q-comparisons" aria-label={t("research.questionnaire.comparisons.title")} className={`scroll-mt-40 ${CARD} ${FOCUS}`}>
      <h3 className="text-[15px] font-semibold">{t("research.questionnaire.comparisons.title")}</h3>
      <p className="mt-1 text-[13px] text-ink-muted">{t("research.questionnaire.comparisons.help")}</p>
      <ul className="mt-3 flex flex-col gap-2">
        {stated.map((rq) => (
          <li key={rq} className="flex flex-col gap-1.5 text-sm">
            <span>{rq}</span>
            <ChoiceChips
              label={tv("research.questionnaire.comparisons.choose", { rq })}
              value={comparisonOf(state.project, rq) ?? NONE}
              options={[{ key: NONE, label: t("research.questionnaire.comparisons.none") }, ...COMPARISONS.map((kind) => ({ key: kind, label: t(`research.questionnaire.comparisons.kind.${kind}`) }))]}
              onChange={(key) => update((p) => setComparison(p, rq, key === NONE ? null : key), "research_question_comparison")}
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * A block's or set's short text, edited in place (input-interactions I1, audit A4, A13): Enter or
 * blur saves, Esc restores. The change goes to the working copy at once and saves with it, the
 * header saying the save, as Návrh's narrative does. A name is required; a purpose may be left empty.
 */
function InlineField({ label, value, onChange, strong = false, required = true, placeholder, validate }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  strong?: boolean;
  required?: boolean;
  placeholder?: string;
  /** A further rule, said at the field (I9); null when the draft passes. */
  validate?: (v: string) => string | null;
}) {
  const { canEdit } = useFrame();
  // A line of its own: the purpose under the name, as the inputs stood before.
  return (
    <div className="min-w-0">
      <InlineText
        label={label}
        value={value}
        placeholder={placeholder ?? label}
        disabled={!canEdit}
        rules={{ required, validate }}
        onCommit={onChange}
        className={strong ? "text-[15px] font-semibold text-ink" : "text-[13px] text-ink-muted"}
      />
    </div>
  );
}

function QuestionBlock({ n, firstQ, sec, si, update }: { n: number; firstQ: number; sec: Section; si: number; update: Update }) {
  const qs = sec.questions || [];
  const [confirming, setConfirming] = useState(false);
  const marks = useLeadMarks();
  const undo = useEditorUndo();
  return (
    <article id={`qblock_${sec.id || si}`} data-aia={marks.sections[si]} className="scroll-mt-40 rounded-panel bg-surface-sunken p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{tv("research.questionnaire.blockHead", { n, q: countWords("questions", qs.length) })}</div>
          {/* The block as a heading: navigable by a screen reader, and the title the Lead names it by (lead.ts titleOf). */}
          <h3 className="sr-only">{sec.title?.trim() || tv("research.questionnaire.untitledBlock", { n })}</h3>
          <InlineField strong label={t("research.questionnaire.blockTitle")} value={sec.title || ""} onChange={(v) => update((p) => setSectionField(p, si, "title", v))} />
          <InlineField required={false} label={t("research.questionnaire.blockPurpose")} value={sec.purpose || ""} onChange={(v) => update((p) => setSectionField(p, si, "purpose", v))} />
        </div>
        {confirming ? (
          <InlineConfirm message={t("research.questionnaire.removeBlockConfirm")} action={t("research.questionnaire.remove")} onConfirm={() => removeWithUndo(update, undo, si, sec, "blockRemoved")} onCancel={() => setConfirming(false)} />
        ) : (
          <Button small variant="quiet" icon="trash" className="!rounded-control" onClick={() => setConfirming(true)}>{t("research.questionnaire.remove")}</Button>
        )}
      </div>
      <div className="mt-3 flex flex-col gap-3">
        {qs.length ? (
          qs.map((q, qi) => <QuestionCard key={q.id || qi} n={firstQ + qi + 1} q={q} si={si} sectionId={sec.id} qi={qi} update={update} />)
        ) : (
          <p className="rounded-control border border-signal-edge bg-signal-wash p-3 text-sm">{t("research.questionnaire.blockEmpty")}</p>
        )}
        <div>
          <InlineCreateRow
            label={t("research.questionnaire.addQuestionV3")}
            maxLength={WORDING_MAX}
            onCreate={(text) => {
              let made = false;
              update((p) => {
                const r = addQuestionTo(p, si, text);
                made = r !== null;
                return r?.project ?? p;
              }, "questionnaire_question");
              return made ? undefined : t("research.questionnaire.inlineAdd.empty");
            }}
          />
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
type TypeKey = (typeof TYPES)[number][0];
const typeKey = (typ: string): TypeKey | null => TYPES.find(([key]) => key === typ)?.[0] ?? null;

/** questionCard: the type as pills, the text, and below it what the type needs. */
function QuestionCard({ n, q, si, sectionId, qi, update }: { n: number; q: Question; si: number; sectionId: string | undefined; qi: number; update: Update }) {
  const marks = useLeadMarks();
  const undo = useEditorUndo();
  const wording = useRef<WordingEdit | null>(null);
  const typ = String(q.typ || "");
  const skala = q.skala || [1, 10];
  const labels = q.popisky_skaly || ["vůbec", "zcela"];
  // A question without wording stops the run: marked where it is, not only in the dock.
  const unworded = !String(q.text || "").trim();
  const hint = `${questionElementId(q)}_missing`;
  return (
    <div id={questionElementId(q)} data-aia={marks.questions[si]?.[qi]} data-unworded={unworded || undefined} className={`scroll-mt-40 rounded-card border bg-surface-raised p-4 ${FOCUS} ${unworded ? "border-status-you shadow-[0_0_0_3px_var(--color-status-you-wash)]" : "border-border"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-signal-wash px-1.5 py-0.5 font-mono text-xs font-semibold text-signal" title={String(q.id || "")}>Q{n}</span>
        <ChoiceChips
          label={t("research.questionnaire.questionType")}
          value={typeKey(typ)}
          options={TYPES.map(([key, label]) => ({ key, label: t(`research.questionnaire.${label}`) }))}
          onChange={(key) => key !== typ && update((p) => changeQType(p, si, qi, key))}
        />
        <Button
          small
          variant="quiet"
          className="ml-auto"
          aria-label={tv("research.questionnaire.removeQuestion", { number: `Q${n}` })}
          onClick={() => {
            update((p) => removeQuestion(p, si, qi));
            offerRestore(undo, "questionRemoved", q.text, () => update((p) => restoreQuestion(p, si, sectionId, qi, q)));
          }}
        >
          ×
        </Button>
      </div>
      <textarea
        aria-label={t("research.questionnaire.questionText")}
        aria-describedby={unworded ? hint : undefined}
        aria-invalid={unworded || undefined}
        value={q.text || ""}
        onChange={(e) => {
          if (wording.current) wording.current = wordingTyped(wording.current, q.text || "", e.target.value);
          update((p) => setQuestionText(p, si, qi, e.target.value));
        }}
        // Esc puts back the wording this field's typing started from (wordingEscape), never one older
        // than a change accepted from elsewhere meanwhile (a Lead edit, a reload).
        onFocus={(e) => {
          wording.current = wordingFocused(e.currentTarget.value);
        }}
        onKeyDown={(e) => {
          if (e.nativeEvent.isComposing || editKeyAction(e, true) !== "cancel" || !wording.current) return;
          const back = wordingEscape(wording.current, q.text || "");
          if (back === null) return;
          e.preventDefault();
          update((p) => setQuestionText(p, si, qi, back));
          e.currentTarget.blur();
        }}
        rows={2}
        className={`mt-3 block w-full resize-y rounded-control border border-border-strong bg-surface px-3 py-2 text-[15px] font-medium leading-6 ${FOCUS} ${unworded ? "border-status-you-ink" : ""}`}
      />
      {unworded ? (
        <p id={hint} className="mt-1.5 flex items-center gap-1.5 text-xs text-status-you-ink">
          <Icon name="you" size={12} />
          {t("research.questionnaire.unworded")}
        </p>
      ) : null}
      {questionCondition(q) !== null ? (
        <div data-question-condition className="mt-2 flex flex-wrap items-center gap-2 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-2 text-xs">
          <span className="flex-1">{tv("research.questionnaire.condition", { condition: questionCondition(q)! })}</span>
          <Button small onClick={() => update((p) => removeCondition(p, si, qi))}>{t("research.questionnaire.removeCondition")}</Button>
        </div>
      ) : null}
      {typ === "vyber" || typ === "multi" ? (
        <OptionRows key={(q.kategorie || []).join("\n")} multi={typ === "multi"} options={q.kategorie || []} onCommit={(raw) => update((p) => setQuestionOptions(p, si, qi, raw))} onRestore={(at, value) => update((p) => restoreOption(p, si, sectionId, qi, q.id, at, value))} />
      ) : null}
      {typ === "skala" ? (
        <ScaleEditor
          className="mt-3"
          name={`Q${n}`}
          scale={skala}
          labels={labels}
          onChange={(v) => update((p) => setQuestionScale(p, si, qi, v.scale, v.labels), "scale")}
        />
      ) : null}
      {typ === "otevrena" ? (
        <p className="mt-3 rounded-control border border-dashed border-border-strong px-3 py-2 text-xs text-ink-muted">{t("research.questionnaire.openNote")}</p>
      ) : null}
      <ResearchQuestionLinks item={q} onToggle={(rq) => update((p) => toggleQuestionLink(p, si, qi, rq), "questionnaire_links")} />
    </div>
  );
}

/**
 * "Odpovídá na výzkumné otázky": which of the plan's research questions this item measures
 * (run-recovery-and-truth 3b). Readiness traces each research question to the items that
 * say so before a run; a link the plan no longer states is shown to be removed.
 */
function ResearchQuestionLinks({ item, onToggle }: { item: Question | Section; onToggle: (rq: string) => void }) {
  const { state } = useResearch();
  const stated = researchQuestionsOf(state.project);
  const links = linksOf(item);
  const dangling = danglingLinks(item, stated);
  if (!stated.length && !dangling.length) return <p className="mt-3 text-xs text-ink-muted">{t("research.questionnaire.links.none")}</p>;
  const on = (rq: string) => links.some((l) => linkKey(l) === linkKey(rq));
  return (
    <fieldset className="mt-3 flex flex-col gap-1">
      <legend className={LABEL}>{t("research.questionnaire.links.label")}</legend>
      <div className="flex flex-wrap items-start gap-1.5">
        {stated.length ? (
          <ChoiceChips
            multiple
            label={t("research.questionnaire.links.choices")}
            value={stated.filter(on)}
            options={stated.map((rq) => ({ key: rq, label: rq }))}
            // One toggled at a time: the one whose state the new value changes.
            onChange={(next) => {
              const flipped = stated.find((rq) => next.includes(rq) !== on(rq));
              if (flipped) onToggle(flipped);
            }}
          />
        ) : null}
        {dangling.map((rq) => (
          <button
            key={`dangling-${rq}`}
            type="button"
            aria-label={tv("research.questionnaire.links.removeDangling", { rq })}
            onClick={() => onToggle(rq)}
            className={`max-w-full rounded-pill border border-status-you-ink/40 bg-status-you-wash px-2.5 text-left text-xs leading-6 text-status-you-ink ${FOCUS}`}
          >
            {rq} ×
          </button>
        ))}
      </div>
      {dangling.length ? <p className="text-xs text-status-you-ink">{t("research.questionnaire.links.dangling")}</p> : null}
    </fieldset>
  );
}

/**
 * A choice question's options, one row each. Typed rows are kept on the page and
 * applied when the list is left, as the classic textarea's onchange: trimmed, empty
 * rows dropped (setQuestionOptions). Enter adds a row below; × removes one.
 */
function OptionRows({ options, multi, onCommit, onRestore }: {
  options: string[];
  multi: boolean;
  onCommit: (raw: string) => void;
  /** Vrátit for a removed option: the one option back at its place (restoreOption). */
  onRestore: (index: number, value: string) => void;
}) {
  const [rows, setRows] = useState<string[]>(options.length ? options : [""]);
  const undo = useEditorUndo();
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
              // Vrátit puts the removed option back in its place, whatever was edited since (I6, A3).
              const value = r.trim();
              const at = rows.slice(0, i).filter((x) => x.trim()).length;
              if (value) offerRestore(undo, "optionRemoved", value, () => onRestore(at, value));
            }}
            className={`inline-flex size-6 shrink-0 items-center justify-center rounded-sm text-ink-faint hover:text-ink ${FOCUS}`}
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
  const marks = useLeadMarks();
  const undo = useEditorUndo();
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const labels = sec.scale_labels || ["vůbec", "velmi"];
  const objects = sec.objects || [];
  const question = sec.object_question || "Jak hodnotíte {object}?";
  const objectMissing = tv("research.questionnaire.setQuestionMissing", { object: OBJECT });
  const bad = setInvalid(sec);
  // updateObjects takes the objects one per line, as the classic textarea gave them.
  const setObjects = (next: string[]) => {
    const r = updateObjects(store.get().project, si, next.join("\n"));
    store.update(() => ({ project: r.project }));
    setNote(r.note);
  };
  return (
    <article id={setElementId(sec, si)} data-aia={marks.sections[si]} className={`scroll-mt-40 flex flex-col gap-3 rounded-card border border-border border-t-[3px] border-t-hue-violet bg-surface-raised p-4 ${FOCUS}`}>
      {/* The name keeps 12rem; on a phone the count and Smazat wrap below it rather than squeeze it. */}
      <div className="flex flex-wrap items-start gap-3">
        <span className="mt-1 whitespace-nowrap rounded-md bg-hue-violet/12 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-hue-violet">{tv("research.questionnaire.setBadge", { n })}</span>
        <div className="min-w-[12rem] flex-1">
          <h3 className="sr-only">{sec.title?.trim() || tv("research.questionnaire.untitledSet", { n })}</h3>
          <InlineField strong label={t("research.questionnaire.setTitle")} value={sec.title || ""} onChange={(v) => update((p) => setSectionField(p, si, "title", v))} />
        </div>
        <span className={`whitespace-nowrap rounded-md px-1.5 py-0.5 font-mono text-xs ${bad ? "bg-status-you-wash text-status-you-ink" : "bg-surface-sunken text-ink-muted"}`}>
          {tv("research.questionnaire.setCount", { n: objects.length })}
        </span>
        {confirming ? (
          <InlineConfirm message={t("research.questionnaire.removeSetConfirm")} action={t("research.questionnaire.remove")} onConfirm={() => removeWithUndo(update, undo, si, sec, "setRemoved")} onCancel={() => setConfirming(false)} />
        ) : (
          <Button small variant="quiet" icon="trash" className="!rounded-control" onClick={() => setConfirming(true)}>{t("research.questionnaire.remove")}</Button>
        )}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <div className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.questionnaire.setFamily")}</span>
          <InlineField required={false} label={t("research.questionnaire.setFamily")} placeholder={t("research.questionnaire.setFamilyPlaceholder")} value={sec.object_family || sec.object_type || ""} onChange={(v) => update((p) => setObjectFamily(p, si, v))} />
          <span className="text-xs text-ink-muted">{t("research.questionnaire.setFamilyHelp")}</span>
        </div>
        <div className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.questionnaire.setPurpose")}</span>
          <InlineField required={false} label={t("research.questionnaire.setPurpose")} placeholder="" value={sec.purpose || ""} onChange={(v) => update((p) => setSectionField(p, si, "purpose", v))} />
        </div>
      </div>
      <div className="flex flex-col gap-1">
        <span className={LABEL}>{t("research.questionnaire.setQuestion")}</span>
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <InlineField
              label={t("research.questionnaire.setQuestion")}
              value={question}
              validate={(v) => (v.includes(OBJECT) ? null : objectMissing)}
              onChange={(v) => update((p) => setSectionField(p, si, "object_question", v))}
            />
          </div>
          {/* Only for a stored question without {object} (an older copy): the field refuses a new one. */}
          {question.includes(OBJECT) ? null : (
            <Button
              small
              className="!min-h-9 shrink-0 !rounded-control font-mono"
              onClick={() => update((p) => setSectionField(p, si, "object_question", `${String(sections(p)[si]?.object_question || "").trimEnd()} ${OBJECT}`.trim()))}
            >
              + {OBJECT}
            </Button>
          )}
        </div>
        {question.includes(OBJECT) ? (
          <span className="text-xs text-ink-muted">
            {t("research.questionnaire.setQuestionHelp")} <code className="font-mono">{OBJECT}</code>.
          </span>
        ) : (
          <span className="text-xs text-status-you-ink">{objectMissing}</span>
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
      <ScaleEditor
        name={`sada ${n}`}
        scale={sec.scale || [1, 10]}
        labels={labels}
        rangeFixed
        perPoint={false}
        onChange={(v) => update((p) => setSetScaleLabels(p, si, v.labels), "scale")}
      />
      <div className="flex flex-col gap-1">
        <Switch checked={Boolean(sec.familiarity_required)} onChange={(on) => update((p) => setSectionField(p, si, "familiarity_required", on))} label={<b className="font-semibold">{t("research.questionnaire.familiarity")}</b>} />
        <p className="pl-[44px] text-xs text-ink-muted">{t("research.questionnaire.familiarityHelp")}</p>
      </div>
      {togglesConceptTest(sec) ? (
        <div className="flex flex-col gap-1">
          <Switch
            checked={sec.output_type === CONCEPT_TEST}
            onChange={(on) => update((p) => setConceptTest(p, si, on), "concept_test")}
            label={<b className="font-semibold">{t("research.questionnaire.conceptTest")}</b>}
          />
          <p className="pl-[44px] text-xs text-ink-muted">{t("research.questionnaire.conceptTestHelp")}</p>
        </div>
      ) : null}
      {sec.output_type === CONCEPT_TEST ? (
        <div className="flex flex-col gap-1">
          <span className={LABEL}>{t("research.questionnaire.priceBands")}</span>
          {/* One chip per price, each checked as an amount at the field (input-interactions I9, A16). */}
          <ChipInput
            label={t("research.questionnaire.priceBandAdd")}
            placeholder={t("research.questionnaire.priceBandsPlaceholder")}
            values={priceBandsOf(sec)}
            refuse={priceProblem}
            onAdd={(v) => update((p) => setPriceBandList(p, si, [...priceBandsOf(sec), v]))}
            onRemove={(i) => update((p) => setPriceBandList(p, si, priceBandsOf(sec).filter((_, j) => j !== i)))}
          />
          <span className="text-xs text-ink-muted">{t("research.questionnaire.priceBandsHelp")}</span>
        </div>
      ) : null}
      <ResearchQuestionLinks item={sec} onToggle={(rq) => update((p) => toggleSectionLink(p, si, rq), "questionnaire_links")} />
      <p className="rounded-control border border-signal-edge bg-signal-tint p-3 text-[13px]">
        <strong>{t("research.questionnaire.outputLabel")}</strong> {t("research.questionnaire.outputText")}
      </p>
    </article>
  );
}

