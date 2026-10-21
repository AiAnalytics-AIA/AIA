"use client";

// 1. Zadání, rebuilt (research-flow-rehome.md, chunk 2) and drawn as Studio v3
// (studio-v3.md, chunk 3): the classic renderBrief and its two wrappers as four
// numbered sections -- the goal, the problem types, the attachments and links,
// the further context -- a readiness panel beside them, and the AI analysis that
// turns it into a plan in the step's dock. What each control does to the project
// is src/research/brief.ts, parity-tested against the original; this file only
// draws it. The sentence starters and "Navrhnout z cíle" write the same fields a
// person types into; nothing here calls a model but the analysis.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { type DragEvent, type ReactNode, useEffect, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { workspace } from "@/lib/api";
import { saveBlob } from "@/lib/download";
import { type BriefMaterials, classLabel, classOf } from "@/lib/material-class";
import { briefElementId, contextField, materialAia } from "@/lib/artifacts/brief";
import { aiaId } from "@/lib/workbench-artifacts";
import { OBJECTIVE_MAX, addObjective, objectivesEditable, objectivesOf, removeObjective, restoreObjective, setObjective } from "@/research/brief-objectives";
import { InlineCreateRow } from "../../ui/InlineCreateRow";
import { InlineText } from "../../ui/InlineText";
import { UndoToast, useUndo } from "../../ui/UndoToast";
import {
  type BriefingField,
  MAX_FILES_PER_PICK,
  type TopField,
  addAttachments,
  addLink,
  attachmentLine,
  canAnalyse,
  editBrief,
  fileToBase64,
  removeAttachment,
  restoreAttachment,
  storedAttachmentId,
  titleValue,
  toggleProblemType,
} from "@/research/brief";
import { type Attachment, PROBLEM_TYPES, type ResearchProject, selectedProblemTypes } from "@/research/model";
import { Icon, type IconName } from "../icons";
import { StepSection } from "../step";
import { InspectorSlot } from "./Inspector";
import { AiButton, Button, TextInput } from "../ui";
import { useResearch } from "./context";
import { AskLead, useLeadOwnsAiStarts } from "./AskLead";
import { AnalysisFailureCard, useAnalysis } from "./useAnalysis";

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";
const INPUT = `rounded-control border border-border-strong text-ink placeholder:text-ink-faint ${FOCUS}`;

/** A goal this long reads as a sentence; shorter, the AI will have to ask. */
export const GOAL_SENTENCE = 40;

/** The further context, in the order the classic form showed it. */
const CONTEXT: { field: TopField | BriefingField; label: string }[] = [
  { field: "product_description", label: "research.brief.productDescription" },
  { field: "decision_use", label: "research.brief.decisionUse" },
  { field: "situation", label: "research.brief.situation" },
  { field: "what_is_known", label: "research.brief.whatIsKnown" },
  { field: "constraints", label: "research.brief.constraints" },
];

function contextValue(p: ResearchProject, field: TopField | BriefingField): string {
  return field === "decision_use" ? p.decision_use || "" : String((p.briefing as Record<string, unknown>)[field] || "");
}

/**
 * "Navrhnout z cíle": a short title from the goal's first clause, without its
 * sentence starter. Done in the browser; the person can change it like any title.
 */
export function titleFromGoal(goal: string): string {
  const words = goal
    .trim()
    .replace(/^(Chceme zjistit|Rozhodujeme mezi|Potřebujeme ověřit)(,?\s+(jak|zda|jestli|co|kdo|proč))?\s*/i, "")
    .split(/[.,;:!?]/)[0]!
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 5)
    .join(" ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const jumpTo = (id: string) => document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });

export function BriefStep() {
  const { store, state, stepHref } = useResearch();
  const router = useRouter();
  const p = state.project;
  const { analyse: runAnalysis, resume, failure, busy } = useAnalysis();
  const leadOwnsAiStarts = useLeadOwnsAiStarts();

  const edit = (field: TopField | BriefingField, value: string) =>
    store.update(({ project, analysis }) => editBrief(project, analysis, field, value));

  // analyzeBrief -> ensureAnalysis1776 -> go('plan').
  const analyse = async () => {
    if (!(await runAnalysis({ force: true }))) return;
    router.push(stepHref("plan"));
  };
  // The same analysis job, after a budget lift: on its accept the person goes on to Návrh, as
  // `analyse` does, so "Další krok" is never pressed again for an analysis already made (CR-2).
  const continueAnalysis = async (jobId: string) => {
    if (!(await resume(jobId))) return;
    router.push(stepHref("plan"));
  };

  const selected = new Set(selectedProblemTypes(p));
  const goal = p.goal || "";
  const goalLength = goal.trim().length;
  const attachments = p.briefing.attachments || [];
  const filled = CONTEXT.filter((c) => contextValue(p, c.field).trim()).length;
  const ready = canAnalyse(p);
  const score = [goalLength >= GOAL_SENTENCE, selected.size > 0, attachments.length > 0, filled > 0].filter(Boolean).length * 25;

  const uploads = useUploads();
  const note = ready ? (goalLength < GOAL_SENTENCE && !selected.size ? t("research.brief.dockShort") : t("research.brief.dockReady")) : t("research.brief.dockMissing");

  return (
    <div
      className="relative flex max-w-[82.5rem] flex-col gap-4"
      onDragEnter={(e) => { if (hasFiles(e)) { e.preventDefault(); uploads.setOver(true); } }}
      onDragOver={(e) => { if (hasFiles(e)) e.preventDefault(); }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) uploads.setOver(false); }}
      onDrop={(e) => { if (hasFiles(e)) uploads.drop(e); }}
    >
      <InspectorSlot>
        <Readiness
          score={score}
          ready={ready}
          rows={[
            { id: "brief-goal", label: "research.brief.readyGoal", need: true, ok: goalLength >= GOAL_SENTENCE,
              detail: goalLength ? tv("research.brief.chars", { n: goalLength }) + (goalLength < GOAL_SENTENCE ? t("research.brief.readyGoalShort") : "") : t("research.brief.readyGoalEmpty") },
            { id: "brief-type", label: "research.brief.readyTypes", need: true, ok: selected.size > 0,
              detail: selected.size ? tv("research.brief.readyTypesN", { n: selected.size }) : t("research.brief.readyTypesEmpty") },
            { id: "brief-files", label: "research.brief.readyFiles", need: false, ok: attachments.length > 0,
              detail: attachments.length ? tv("research.brief.readyFilesN", { n: attachments.length }) : t("research.brief.readyFilesEmpty") },
            { id: "brief-context", label: "research.brief.readyContext", need: false, ok: filled > 0,
              detail: filled ? tv("research.brief.readyContextN", { n: filled }) : t("research.brief.readyContextEmpty") },
          ]}
        >
          <p aria-live="polite" className={`text-[13px] leading-5 ${ready ? "text-ink-muted" : "text-status-you-ink"}`}>{note}</p>
          {!leadOwnsAiStarts ? (
            <AiButton variant="primary" className="w-full justify-center !min-h-11" onClick={analyse} disabled={busy || !ready}>
              {t("research.brief.next")}
              <Icon name="next" size={14} />
            </AiButton>
          ) : (
            <>
              <Link href={stepHref("plan")} className="inline-flex w-full items-center justify-center gap-1 rounded-control border border-border-strong px-3 !min-h-11 text-sm no-underline">
                Pokračovat na Návrh
                <Icon name="next" size={14} />
              </Link>
              <AskLead className="mt-2" what="Analýzu zadání" />
            </>
          )}
        </Readiness>
      </InspectorSlot>

      {failure ? <AnalysisFailureCard failure={failure} onRetry={analyse} onContinue={(id) => void continueAnalysis(id)} /> : null}

      <StepSection id="brief-goal" n={1} lead title={t("research.brief.goalTitle")} hint={t("research.brief.goalHint")}>
        <textarea
          aria-label={t("research.brief.goalLabel")}
          placeholder={t("research.brief.goalPlaceholder")}
          value={goal}
          onChange={(e) => edit("goal", e.target.value)}
          className={`block min-h-24 w-full resize-y bg-surface-raised px-3 py-2.5 text-[15px] leading-6 ${INPUT}`}
        />
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-ink-muted">{t("research.brief.startWith")}</span>
          {[0, 1, 2].map((i) => {
            const starter = t(`research.brief.starters.${i}`);
            return (
              <button
                key={i}
                type="button"
                onClick={() => edit("goal", goal.trim() ? `${goal.trim()} ${starter}` : starter)}
                className={`min-h-7 rounded-pill border border-dashed border-border-strong px-2.5 text-xs leading-5 text-ink-muted hover:border-solid hover:text-ink ${FOCUS}`}
              >
                {starter.trim()}…
              </button>
            );
          })}
          {goalLength ? (
            <span className={`ml-auto font-mono text-[11px] ${goalLength < GOAL_SENTENCE ? "text-status-you-ink" : "text-ink-faint"}`}>
              {tv("research.brief.chars", { n: goalLength })}
            </span>
          ) : null}
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="flex min-w-60 flex-1 flex-col gap-1">
            <span className="text-xs font-medium text-ink-muted">{t("research.brief.titleLabel")} · {t("research.brief.optional")}</span>
            <TextInput id={briefElementId("title")} className="w-full !rounded-control" value={titleValue(p)} placeholder={t("research.brief.titlePlaceholder")} onChange={(e) => edit("title", e.target.value)} />
          </label>
          <Button variant="quiet" className="!rounded-control" disabled={!goalLength} onClick={() => edit("title", titleFromGoal(goal))}>
            {t("research.brief.suggestTitle")}
          </Button>
        </div>
      </StepSection>

      <Objectives />

      <StepSection
        id="brief-type"
        n={3}
        title={t("research.brief.typesTitle")}
        hint={t("research.brief.typesHelp")}
        aside={selected.size ? <span className="font-mono text-xs text-ink-muted">{tv("research.brief.readyTypesN", { n: selected.size })}</span> : null}
      >
        <div role="group" aria-label={t("research.brief.typesGroup")} className="grid grid-cols-[repeat(auto-fill,minmax(min(12rem,100%),1fr))] gap-1.5">
          {PROBLEM_TYPES.map(([key, label, sub]) => {
            const on = selected.has(key);
            return (
              <button
                key={key}
                type="button"
                aria-pressed={on}
                onClick={() => store.update(({ project }) => ({ project: toggleProblemType(project, key) }), { reason: "problem_types_1789" })}
                className={`flex min-h-12 flex-col items-start justify-center rounded-control border px-2.5 py-1.5 text-left ${FOCUS} ${
                  on ? "border-signal bg-signal-wash shadow-[inset_0_0_0_1px_var(--color-signal)]" : "border-border bg-surface-raised hover:border-border-strong"
                }`}
              >
                <span className={`flex items-center gap-1.5 text-[13px] font-semibold leading-[18px] ${on ? "text-signal" : "text-ink"}`}>
                  {on ? <Icon name="done" size={12} /> : null}
                  {label}
                </span>
                <span className="text-[11px] leading-4 text-ink-muted">{sub}</span>
              </button>
            );
          })}
        </div>
      </StepSection>

      <Attachments uploads={uploads} />

      <ContextFields edit={edit} p={p} />

      {uploads.over ? (
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 z-10 flex items-start justify-center rounded-card border-2 border-dashed border-signal bg-signal-wash/90 pt-40">
          <div className="flex flex-col items-center gap-2 rounded-card bg-surface-raised px-8 py-6 shadow-[var(--shadow-overlay)]">
            <Icon name="attach" size={28} className="text-signal" />
            <strong className="text-base">{t("research.brief.dropAnywhere")}</strong>
            <span className="text-[13px] text-ink-muted">{t("research.brief.dropAnywhereSub")}</span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Cíle (artifact-brief BRF2): the study's objectives as items, each edited where it is shown, added
 * in the list and removed with "Vrátit". The same list Návrh shows (brief-objectives.ts); each item
 * is a Lead target, objective:<id>. None yet reads "Zatím prázdné", never the goal in their place.
 */
function Objectives() {
  const { store, state } = useResearch();
  const undo = useUndo();
  const design = { project: state.project, analysis: state.analysis };
  const items = objectivesOf(design);
  const editable = objectivesEditable(design);
  const remove = (index: number) => {
    const { removed } = removeObjective(store.get(), index);
    if (removed === null) return;
    store.update((d) => removeObjective(d, index).design, { reason: "brief_objective_remove" });
    undo.offer({
      message: tv("research.brief.objectiveRemoved", { text: removed.length > 60 ? `${removed.slice(0, 57)}…` : removed }),
      undo: () => store.update((d) => restoreObjective(d, index, removed), { reason: "brief_objective_restore" }),
    });
  };
  return (
    <StepSection id={briefElementId("objectives")} n={2} title={t("research.brief.objectivesTitle")} hint={t("research.brief.objectivesHint")}>
      {items.length ? (
        <ol className="flex flex-col gap-1.5">
          {items.map((o, i) => (
            <li key={o.id} data-aia={aiaId("objective", o.id)} className="flex items-start gap-2">
              <span aria-hidden="true" className="mt-1.5 w-5 shrink-0 text-right font-mono text-xs text-ink-faint">{i + 1}.</span>
              <InlineText
                className="min-w-0 flex-1"
                multiline
                value={o.text}
                label={tv("research.brief.objectiveLabel", { n: i + 1 })}
                rules={{ maxLength: OBJECTIVE_MAX }}
                onCommit={(text) => store.update((d) => setObjective(d, i, text), { reason: "brief_objective" })}
              />
              <Button small variant="quiet" aria-label={tv("research.brief.objectiveRemoveAria", { n: i + 1 })} onClick={() => remove(i)}>
                ×
              </Button>
            </li>
          ))}
        </ol>
      ) : (
        <p className="text-sm text-ink-muted">
          {editable ? t("research.brief.objectivesEmpty") : t("research.brief.objectivesUnreadable")}
        </p>
      )}
      {editable ? (
        <InlineCreateRow
          className="mt-2"
          label={t("research.brief.objectiveAdd")}
          maxLength={OBJECTIVE_MAX}
          existing={items.map((o) => o.text)}
          onCreate={(text) => store.update((d) => addObjective(d, text), { reason: "brief_objective_add" })}
        />
      ) : null}
      <UndoToast offer={undo.current} onDone={undo.clear} />
    </StepSection>
  );
}

/** A drag that carries files (not text or a link dragged within the page). */
function hasFiles(e: DragEvent): boolean {
  return Array.from(e.dataTransfer?.types || []).includes("Files") || (e.dataTransfer?.files?.length ?? 0) > 0;
}

const ROW_LOOK = {
  ok: { glyph: "done", look: "bg-status-done/14 text-status-done" },
  need: { glyph: "you", look: "bg-status-you-wash text-status-you-ink" },
  optional: { glyph: "dot", look: "bg-surface-sunken text-ink-faint" },
} as const satisfies Record<string, { glyph: IconName; look: string }>;

/** "Připravenost zadání": what the brief has, each row a way to the section that gives it. */
function Readiness({ score, ready, rows, children }: {
  score: number;
  ready: boolean;
  rows: { id: string; label: string; need: boolean; ok: boolean; detail: string }[];
  /** The stage's action, closing the list: what the readiness is for. */
  children?: ReactNode;
}) {
  return (
    <aside aria-label={t("research.brief.readyTitle")} className="flex flex-col gap-3 rounded-card border border-border bg-surface-raised p-3.5">
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold">{t("research.brief.readyTitle")}</h2>
          <span className="font-mono text-xs text-ink-muted">{score} %</span>
        </div>
        <div aria-hidden="true" className="mt-2 h-1 rounded-sm bg-surface-sunken">
          <div className={`h-1 rounded-sm ${ready ? "bg-signal" : "bg-status-you-ink"}`} style={{ width: `${score}%` }} />
        </div>
      </div>
      <ul className="flex flex-col gap-1">
        {rows.map((r) => {
          const look = ROW_LOOK[r.ok ? "ok" : r.need ? "need" : "optional"];
          return (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => jumpTo(r.id)}
                className={`grid w-full grid-cols-[20px_1fr] items-start gap-2 rounded-control p-1.5 text-left hover:bg-surface-sunken ${FOCUS}`}
              >
                <span aria-hidden="true" className={`inline-flex size-5 items-center justify-center rounded-full ${look.look}`}>
                  <Icon name={look.glyph} size={12} />
                </span>
                <span className="min-w-0">
                  <span className="block text-[13px] font-medium leading-[18px]">
                    {t(r.label)}
                    {r.need ? null : <span className="font-normal text-ink-faint"> · {t("research.brief.optional")}</span>}
                  </span>
                  <span className="block text-xs text-ink-muted">{r.detail}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <div className="flex flex-col gap-2 border-t border-border pt-3">
        {children}
        <p className="text-xs leading-4 text-ink-muted">{t("research.brief.readyNote")}</p>
      </div>
    </aside>
  );
}

/**
 * The further context, one field at a time: a field with a value is open, an
 * empty one is a "+" chip until the person opens it. × empties the field (the
 * same edit as deleting its text) and closes it.
 */
function ContextFields({ p, edit }: { p: ResearchProject; edit: (field: TopField | BriefingField, value: string) => void }) {
  const [opened, setOpened] = useState<ReadonlySet<string>>(() => new Set());
  const open = CONTEXT.filter((c) => opened.has(c.field) || contextValue(p, c.field));
  const closed = CONTEXT.filter((c) => !open.includes(c));
  return (
    <StepSection id="brief-context" n={5} optional title={t("research.brief.contextTitle")} hint={t("research.brief.contextHint")}>
      <div className="flex flex-col gap-3">
        {open.map((c) => (
          <div key={c.field} className="flex flex-col gap-1">
            <span className="flex items-center justify-between gap-2 text-xs font-medium text-ink-muted">
              <label htmlFor={briefElementId(contextField(c.field))}>{t(c.label)}</label>
              <button
                type="button"
                aria-label={tv("research.brief.contextRemoveAria", { label: t(c.label) })}
                onClick={() => {
                  edit(c.field, "");
                  setOpened((s) => new Set([...s].filter((f) => f !== c.field)));
                }}
                className={`rounded-sm px-1 text-sm text-ink-faint hover:text-ink ${FOCUS}`}
              >
                ×
              </button>
            </span>
            <textarea
              id={briefElementId(contextField(c.field))}
              rows={2}
              placeholder={t(`research.brief.examples.${c.field}`)}
              value={contextValue(p, c.field)}
              onChange={(e) => edit(c.field, e.target.value)}
              className={`min-h-[60px] w-full resize-y bg-surface-raised px-2.5 py-2 text-sm leading-[22px] ${INPUT}`}
            />
          </div>
        ))}
        {closed.length ? (
          <div className="flex flex-wrap gap-1.5">
            {closed.map((c) => (
              <button
                key={c.field}
                id={briefElementId(contextField(c.field))}
                type="button"
                onClick={() => setOpened((s) => new Set([...s, c.field]))}
                className={`inline-flex items-center gap-1 rounded-pill border border-border bg-surface px-3 py-1 text-[13px] leading-5 text-ink hover:border-signal hover:text-signal ${FOCUS}`}
              >
                <Icon name="plus" size={12} />
                {t(c.label)}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </StepSection>
  );
}

// A file's kind, as its badge: PDF in the fault tint, sheets in the done tint, the rest in the signal tint.
function badge(x: Attachment): { label: string; look: string } {
  if (x.kind === "url") return { label: "URL", look: "bg-signal-wash text-signal" };
  const ext = (x.filename || "").split(".").pop()?.toUpperCase() || "";
  if (ext === "PDF") return { label: ext, look: "bg-status-fault-wash text-status-fault" };
  if (["XLSX", "XLSM", "XLS", "CSV", "TSV"].includes(ext)) return { label: ext, look: "bg-status-done/14 text-status-done" };
  return { label: ext.slice(0, 4) || "—", look: "bg-signal-wash text-signal" };
}

/**
 * The class of each material, as the server answers it for the saved revision (artifact-brief
 * BRF3); read again after every save. Null until an answer comes: no chip is shown rather than a
 * guessed one, and a failed read leaves it so.
 */
function useMaterialClasses(studyId: string, revision: number | null): BriefMaterials | null {
  const [answer, setAnswer] = useState<BriefMaterials | null>(null);
  useEffect(() => {
    if (revision === null) return;
    let live = true;
    workspace.materials(studyId).then(
      (r) => live && setAnswer(r),
      () => undefined,
    );
    return () => {
      live = false;
    };
  }, [studyId, revision]);
  return answer;
}

type Pending = { name: string; state: "waiting" | "uploading" | "done" | "failed"; message?: string };

/**
 * Podklady's uploads, for the files section and for a drop anywhere on the stage:
 * files are kept in AIA's storage as they are picked or dropped (ADR 0018), one
 * request each, in order, each with its own state. A file belongs to the study's
 * working content, so a study never saved is saved first; the brief then keeps each
 * stored file's record and saves again -- what AIA stored is kept even when a later
 * file fails.
 */
function useUploads() {
  const { store, toast, frame } = useResearch();
  const [pending, setPending] = useState<Pending[]>([]);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const busy = pending.some((x) => x.state === "waiting" || x.state === "uploading");

  // uploadBriefAttachments1785: up to eight files, one request each, saved once at the end.
  const upload = async (picked: File[]) => {
    if (!picked.length || busy) return;
    const batch = picked.slice(0, MAX_FILES_PER_PICK);
    setError(null);
    setPending(batch.map((f) => ({ name: f.name, state: "waiting" })));
    const records: Attachment[] = [];
    const mark = (i: number, x: Partial<Pending>) => setPending((xs) => xs.map((y, j) => (j === i ? { ...y, ...x } : y)));
    let failed = false;
    try {
      if (!store.saved) await store.flush("brief_attachments");
      for (const [i, f] of batch.entries()) {
        mark(i, { state: "uploading" });
        try {
          records.push(await workspace.attach(frame.studyId, { filename: f.name, data_b64: await fileToBase64(f) }));
          mark(i, { state: "done" });
        } catch (e) {
          failed = true;
          mark(i, { state: "failed", message: message(e) });
          setError(message(e));
          break;
        }
      }
      if (records.length && !failed) toast(t("research.brief.uploaded"));
    } catch (e) {
      setError(message(e));
      setPending([]);
    } finally {
      if (records.length) store.update(({ project }) => ({ project: addAttachments(project, records) }), { reason: "brief_attachments" });
      setPending((xs) => xs.filter((x) => x.state === "failed"));
    }
  };

  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    void upload([...e.dataTransfer.files]);
  };

  return { upload, drop, pending, busy, over, setOver, error, setError };
}

type Uploads = ReturnType<typeof useUploads>;

/** Podklady: the stored files and links, the files on their way, and how to add more. */
function Attachments({ uploads }: { uploads: Uploads }) {
  const { store, state, frame } = useResearch();
  const files = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const list: Attachment[] = state.project.briefing.attachments || [];
  const { upload, pending, busy, error, setError } = uploads;
  const classes = useMaterialClasses(frame.studyId, state.revision);
  // A removal happens at once, with Vrátit (I6, audit A28). The stored file stays in AIA's storage
  // until then and after: removing it from the brief only drops its record, which the undo puts back.
  const undo = useUndo();

  const download = async (x: Attachment, attachmentId: string) => {
    setError(null);
    try {
      saveBlob(await workspace.attachment(frame.studyId, attachmentId), x.filename || "priloha");
    } catch (e) {
      setError(message(e));
    }
  };

  const link = () => {
    const r = addLink(store.get().project, url);
    if ("error" in r) return setError(r.error);
    setError(null);
    setUrl("");
    store.update(() => r, { reason: "brief_link" });
  };

  return (
    <StepSection
      id="brief-files"
      n={4}
      optional
      title={t("research.brief.filesTitle")}
      hint={t("research.brief.attachHelpAnywhere")}
      aside={
        list.length ? (
          <span className="font-mono text-xs text-ink-muted">
            {tv("research.brief.readyFilesN", { n: list.length })} · {t("research.brief.dataClassAside")}
          </span>
        ) : null
      }
    >
      <input
        ref={files}
        type="file"
        multiple
        hidden
        aria-label={t("research.brief.filesLabel")}
        accept=".pdf,.docx,.xlsx,.xlsm,.csv,.txt,.md,.json,.tsv,image/*,video/*"
        onChange={(e) => {
          void upload([...(e.target.files || [])]);
          e.target.value = "";
        }}
      />
      <div className="flex flex-wrap items-center gap-2 rounded-card border-[1.5px] border-dashed border-border-strong bg-surface px-3 py-2.5">
        <Icon name="attach" size={18} className="text-signal" />
        <span className="min-w-0 flex-[1_1_12rem]">
          <span className="block text-[13px] font-semibold">{t("research.brief.dropTitle")}</span>
          <span className="block text-xs text-ink-muted">{t("research.brief.dropKinds")}</span>
        </span>
        <Button className="!rounded-control" aria-label={t("research.brief.addFilesAria")} disabled={busy} onClick={() => files.current?.click()}>
          {t("research.brief.pickFiles")}
        </Button>
        <form
          className="flex min-w-0 flex-[1_1_16rem] gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            link();
          }}
        >
          <span className="flex min-w-0 flex-1 items-center gap-2 rounded-control border border-border-strong bg-surface-raised px-2.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-focus-ring">
            <Icon name="link" size={14} className="text-ink-muted" />
            <input
              inputMode="url"
              aria-label={t("research.brief.urlLabel")}
              placeholder={t("research.brief.urlPlaceholder")}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="min-h-[34px] min-w-0 flex-1 border-0 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
            />
          </span>
          <Button type="submit" className="!rounded-control" aria-label={t("research.brief.addLinkAria")}>
            {t("research.brief.addLink")}
          </Button>
        </form>
      </div>
      {error ? <p role="alert" className="mt-2 text-[13px] text-status-fault">{error}</p> : null}
      {list.length || pending.length ? (
        <ul aria-live="polite" className="mt-3 flex flex-col overflow-hidden rounded-card border border-border">
          {list.map((x, i) => {
            const line = attachmentLine(x);
            const stored = storedAttachmentId(x);
            const missing = x.kind !== "url" && !stored;
            const b = badge(x);
            const cls = classOf(classes, state.revision, x, i);
            const first = stored !== null && list.findIndex((y) => storedAttachmentId(y) === stored) === i;
            return (
              <li key={`${i}-${x.sha256 || x.url || x.filename}`} data-aia={first ? materialAia(stored) : undefined} className="flex items-center gap-3 border-b border-border px-2.5 py-2 last:border-b-0">
                <span aria-hidden="true" className={`inline-flex h-7 min-w-10 items-center justify-center rounded-md px-1 font-mono text-[10px] font-semibold ${b.look}`}>{b.label}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{line.name}</div>
                  <div className={`truncate text-xs ${missing ? "text-status-you-ink" : "text-ink-muted"}`}>
                    {line.detail}
                    {missing ? ` · ${t("research.brief.notInAia")}` : ""}
                  </div>
                </div>
                {cls ? (
                  <span
                    data-data-class={cls.data_class ?? "unknown"}
                    title={cls.class_source ? tv("research.brief.dataClassRule", { rule: cls.class_source }) : undefined}
                    className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[11px] ${cls.data_class ? "border-border-strong text-ink-muted" : "border-status-you-ink text-status-you-ink"}`}
                  >
                    {classLabel(cls.data_class)}
                  </span>
                ) : null}
                {stored ? (
                  <Button small variant="quiet" aria-label={tv("research.brief.downloadAria", { name: line.name })} onClick={() => void download(x, stored)}>
                    {t("research.brief.download")}
                  </Button>
                ) : null}
                <Button
                  small
                  variant="quiet"
                  aria-label={tv("research.brief.removeAria", { name: line.name })}
                  onClick={() => {
                    store.update(({ project }) => ({ project: removeAttachment(project, i) }), { reason: "brief_attachment_remove" });
                    undo.offer({
                      message: tv("research.brief.attachmentRemoved", { name: line.name }),
                      undo: () => store.update(({ project }) => ({ project: restoreAttachment(project, i, x) }), { reason: "brief_attachment_restore" }),
                    });
                  }}
                >
                  ×
                </Button>
              </li>
            );
          })}
          {pending.filter((x) => x.state !== "done").map((x, i) => (
            <li key={`pending-${i}-${x.name}`} data-upload-state={x.state} className="flex items-center gap-3 border-b border-border px-2.5 py-2 last:border-b-0">
              <span aria-hidden="true" className="inline-flex h-7 min-w-10 items-center justify-center rounded-md bg-surface-sunken px-1">
                {x.state === "uploading" ? <Icon name="running" size={14} className="animate-spin text-status-running" /> : x.state === "failed" ? <Icon name="fault" size={14} className="text-status-fault" /> : <Icon name="dot" size={12} className="text-ink-faint" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{x.name}</div>
                <div className={`truncate text-xs ${x.state === "failed" ? "text-status-fault" : x.state === "uploading" ? "text-status-running" : "text-ink-muted"}`}>
                  {x.state === "uploading" ? t("research.brief.fileUploading") : x.state === "failed" ? `${t("research.brief.fileFailed")}${x.message ? ` · ${x.message}` : ""}` : t("research.brief.fileWaiting")}
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      <UndoToast offer={undo.current} onDone={undo.clear} />
    </StepSection>
  );
}
