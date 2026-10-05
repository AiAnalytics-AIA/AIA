"use client";

// 1. Zadání, rebuilt (research-flow-rehome.md, chunk 2) and drawn as Studio v3
// (studio-v3.md, chunk 3): the classic renderBrief and its two wrappers as four
// numbered sections -- the goal, the problem types, the attachments and links,
// the further context -- a readiness panel beside them, and the AI analysis that
// turns it into a plan in the step's dock. What each control does to the project
// is src/research/brief.ts, parity-tested against the original; this file only
// draws it. The sentence starters and "Navrhnout z cíle" write the same fields a
// person types into; nothing here calls a model but the analysis.

import { useRouter } from "next/navigation";
import { type DragEvent, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { saveBlob } from "@/lib/download";
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
  storedAttachmentId,
  titleValue,
  toggleProblemType,
} from "@/research/brief";
import { type Attachment, PROBLEM_TYPES, type ResearchProject, selectedProblemTypes } from "@/research/model";
import { Icon, type IconName } from "../icons";
import { ActionDock, StepSection } from "../step";
import { AiButton, Button, TextInput } from "../ui";
import { useResearch } from "./context";
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
  const { store, state, frame, stepHref } = useResearch();
  const router = useRouter();
  const p = state.project;
  const { analyse: runAnalysis, failure, busy } = useAnalysis();

  const edit = (field: TopField | BriefingField, value: string) =>
    store.update(({ project, analysis }) => editBrief(project, analysis, field, value));

  // analyzeBrief -> ensureAnalysis1776 -> go('plan').
  const analyse = async () => {
    if (!(await runAnalysis({ force: true }))) return;
    router.push(stepHref("plan"));
  };

  const selected = new Set(selectedProblemTypes(p));
  const goal = p.goal || "";
  const goalLength = goal.trim().length;
  const attachments = p.briefing.attachments || [];
  const filled = CONTEXT.filter((c) => contextValue(p, c.field).trim()).length;
  const ready = canAnalyse(p);
  const score = [goalLength >= GOAL_SENTENCE, selected.size > 0, attachments.length > 0, filled > 0].filter(Boolean).length * 25;

  return (
    <div className="flex max-w-[82.5rem] flex-wrap items-start gap-6">
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
      />

      <div className="order-1 flex min-w-0 flex-[999_1_520px] flex-col gap-4">
        {failure ? <AnalysisFailureCard failure={failure} onRetry={analyse} /> : null}

        <StepSection id="brief-goal" n={1} lead title={t("research.brief.goalTitle")} hint={t("research.brief.goalHint")}>
          <textarea
            aria-label={t("research.brief.goalLabel")}
            placeholder={t("research.brief.goalPlaceholder")}
            value={goal}
            onChange={(e) => edit("goal", e.target.value)}
            className={`block min-h-[120px] w-full resize-y bg-surface px-3.5 py-3 text-[15px] leading-[26px] ${INPUT}`}
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
                  className={`rounded-pill border border-dashed border-border-strong px-2.5 text-xs leading-5 text-ink-muted hover:border-solid hover:text-ink ${FOCUS}`}
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
          <div className="mt-4 flex flex-wrap items-end gap-2">
            <label className="flex min-w-60 flex-1 flex-col gap-1">
              <span className="text-xs font-medium text-ink-muted">{t("research.brief.titleLabel")} · {t("research.brief.optional")}</span>
              <TextInput className="w-full !rounded-control" value={titleValue(p)} placeholder={t("research.brief.titlePlaceholder")} onChange={(e) => edit("title", e.target.value)} />
            </label>
            <Button variant="quiet" className="!rounded-control" disabled={!goalLength} onClick={() => edit("title", titleFromGoal(goal))}>
              {t("research.brief.suggestTitle")}
            </Button>
          </div>
        </StepSection>

        <StepSection id="brief-type" n={2} title={t("research.brief.typesTitle")} hint={t("research.brief.typesHelp")}>
          <div role="group" aria-label={t("research.brief.typesGroup")} className="flex flex-wrap gap-2">
            {PROBLEM_TYPES.map(([key, label, sub]) => {
              const on = selected.has(key);
              return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={on}
                  title={sub}
                  onClick={() => store.update(({ project }) => ({ project: toggleProblemType(project, key) }), { reason: "problem_types_1789" })}
                  className={`inline-flex items-center gap-1.5 rounded-pill border px-3.5 py-1.5 text-[13px] leading-5 hover:border-signal ${FOCUS} ${
                    on ? "border-signal bg-signal-wash font-semibold text-signal" : "border-border-strong bg-surface text-ink"
                  }`}
                >
                  {on ? <Icon name="done" size={12} /> : null}
                  {label}
                </button>
              );
            })}
          </div>
          {selected.size ? (
            <p className="mt-2.5 text-xs leading-[18px] text-ink-muted">
              {tv("research.brief.selected", {
                list: PROBLEM_TYPES.filter(([k]) => selected.has(k)).map(([, label, sub]) => `${label} (${sub.toLowerCase()})`).join(" · "),
              })}
            </p>
          ) : null}
        </StepSection>

        <Attachments />

        <ContextFields edit={edit} p={p} />

        <ActionDock
          back={{ href: appRoutes.client(frame.clientId), label: t("aia.backToClient") }}
          ready={ready}
          note={ready ? (goalLength < GOAL_SENTENCE && !selected.size ? t("research.brief.dockShort") : t("research.brief.dockReady")) : t("research.brief.dockMissing")}
        >
          <AiButton variant="primary" onClick={analyse} disabled={busy || !ready}>
            {t("research.brief.next")}
            <Icon name="next" size={14} />
          </AiButton>
        </ActionDock>
      </div>
    </div>
  );
}

const ROW_LOOK = {
  ok: { glyph: "done", look: "bg-status-done/14 text-status-done" },
  need: { glyph: "you", look: "bg-status-you-wash text-status-you-ink" },
  optional: { glyph: "dot", look: "bg-surface-sunken text-ink-faint" },
} as const satisfies Record<string, { glyph: IconName; look: string }>;

/** "Připravenost zadání": what the brief has, each row a way to the section that gives it. */
function Readiness({ score, ready, rows }: {
  score: number;
  ready: boolean;
  rows: { id: string; label: string; need: boolean; ok: boolean; detail: string }[];
}) {
  return (
    <aside aria-label={t("research.brief.readyTitle")} className="sticky top-60 order-2 flex flex-[1_1_260px] flex-col gap-3.5 rounded-card border border-border bg-surface-raised p-4">
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
      <p className="border-t border-border pt-3 text-xs leading-[18px] text-ink-muted">{t("research.brief.readyNote")}</p>
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
    <StepSection id="brief-context" n={4} optional title={t("research.brief.contextTitle")} hint={t("research.brief.contextHint")}>
      <div className="flex flex-col gap-3">
        {open.map((c) => (
          <div key={c.field} className="flex flex-col gap-1">
            <span className="flex items-center justify-between gap-2 text-xs font-medium text-ink-muted">
              <label htmlFor={`brief-${c.field}`}>{t(c.label)}</label>
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
              id={`brief-${c.field}`}
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
 * Podklady: files are kept in AIA's storage as they are picked or dropped (ADR 0018),
 * links as http(s) only. A file belongs to the study's working content, so a study
 * never saved is saved first; the brief then keeps each file's record and saves again.
 */
function Attachments() {
  const { store, state, toast, frame } = useResearch();
  const files = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const list: Attachment[] = state.project.briefing.attachments || [];

  // uploadBriefAttachments1785: up to eight files, one request each, saved once at the end.
  const upload = async (picked: File[]) => {
    if (!picked.length) return;
    setError(null);
    setUploading(true);
    const records: Attachment[] = [];
    try {
      if (!store.saved) await store.flush("brief_attachments");
      for (const f of picked.slice(0, MAX_FILES_PER_PICK)) {
        records.push(await workspace.attach(frame.studyId, { filename: f.name, data_b64: await fileToBase64(f) }));
      }
      toast(t("research.brief.uploaded"));
    } catch (e) {
      setError(message(e));
    } finally {
      // What AIA already stored is kept, even when a later file failed.
      if (records.length) store.update(({ project }) => ({ project: addAttachments(project, records) }), { reason: "brief_attachments" });
      setUploading(false);
      if (files.current) files.current.value = "";
    }
  };

  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    if (!uploading) void upload([...e.dataTransfer.files]);
  };

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
    <StepSection id="brief-files" n={3} optional title={t("research.brief.filesTitle")} hint={t("research.brief.attachHelp")}>
      <input
        ref={files}
        type="file"
        multiple
        hidden
        aria-label={t("research.brief.filesLabel")}
        accept=".pdf,.docx,.xlsx,.xlsm,.csv,.txt,.md,.json,.tsv,image/*,video/*"
        onChange={(e) => void upload([...(e.target.files || [])])}
      />
      <button
        type="button"
        aria-label={t("research.brief.addFilesAria")}
        disabled={uploading}
        onClick={() => files.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        className={`flex w-full flex-col items-center gap-1.5 rounded-card border-[1.5px] border-dashed p-5 text-ink hover:border-signal hover:bg-signal-wash disabled:opacity-50 ${FOCUS} ${
          over ? "border-signal bg-signal-wash" : "border-border-strong bg-surface"
        }`}
      >
        <Icon name="attach" size={22} className="text-signal" />
        <span className="text-sm font-semibold">{t("research.brief.dropTitle")}</span>
        <span className="text-xs text-ink-muted">{t("research.brief.dropKinds")}</span>
      </button>
      <form
        className="mt-2.5 flex gap-2"
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
      <div aria-live="polite">
        {uploading ? (
          <p className="mt-2.5 flex items-center gap-2 text-[13px] text-status-running">
            <Icon name="running" size={14} className="animate-spin" />
            <b>{t("research.brief.uploading")}</b> {t("research.brief.uploadingSub")}
          </p>
        ) : null}
        {error ? <p role="alert" className="mt-2 text-[13px] text-status-fault">{error}</p> : null}
      </div>
      {list.length ? (
        <ul className="mt-3 flex flex-col gap-1.5">
          {list.map((x, i) => {
            const line = attachmentLine(x);
            const stored = storedAttachmentId(x);
            const missing = x.kind !== "url" && !stored;
            const b = badge(x);
            return (
              <li key={`${i}-${x.sha256 || x.url || x.filename}`} className="flex items-center gap-3 rounded-control border border-border bg-surface px-2.5 py-2">
                <span aria-hidden="true" className={`inline-flex h-7 min-w-10 items-center justify-center rounded-md px-1 font-mono text-[10px] font-semibold ${b.look}`}>{b.label}</span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{line.name}</div>
                  <div className={`truncate text-xs ${missing ? "text-status-you-ink" : "text-ink-muted"}`}>
                    {line.detail}
                    {missing ? ` · ${t("research.brief.notInAia")}` : ""}
                  </div>
                </div>
                {stored ? (
                  <Button small variant="quiet" aria-label={tv("research.brief.downloadAria", { name: line.name })} onClick={() => void download(x, stored)}>
                    {t("research.brief.download")}
                  </Button>
                ) : null}
                <Button
                  small
                  variant="quiet"
                  aria-label={tv("research.brief.removeAria", { name: line.name })}
                  onClick={() => store.update(({ project }) => ({ project: removeAttachment(project, i) }), { reason: "brief_attachment_remove" })}
                >
                  ×
                </Button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </StepSection>
  );
}
