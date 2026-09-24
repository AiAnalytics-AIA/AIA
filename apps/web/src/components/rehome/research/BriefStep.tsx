"use client";

// 1. Zadání, rebuilt (research-flow-rehome.md, chunk 2): the classic renderBrief
// and its two wrappers, block for block -- what the research is about, the
// attachments and links, the further context, and the AI analysis that turns it
// into a plan. What each control does to the project is src/unit/research/brief.ts,
// parity-tested against the original; this file only draws it.

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { classicHref } from "@/lib/interface-handoff";
import { t, tv } from "@/i18n/t";
import { unit } from "@/unit/client";
import {
  ANALYSIS_JOB_TITLE,
  ANALYSIS_REUSED,
  ANALYSIS_WARN_MS,
  ATTACHMENT_TIMEOUT_MS,
  BRIEF_EMPTY,
  type BriefingField,
  MAX_FILES_PER_PICK,
  type TopField,
  addAttachments,
  addLink,
  analysisPayload,
  attachmentLine,
  briefEmpty,
  canAnalyse,
  editBrief,
  fileToBase64,
  mergeAnalysis,
  removeAttachment,
  reusableAnalysis,
  titleValue,
  toggleProblemType,
  withAttachmentContext,
} from "@/unit/research/brief";
import { JobError } from "@/unit/research/jobs";
import { type Attachment, PROBLEM_TYPES, selectedProblemTypes } from "@/unit/research/model";
import { activeProvider, notReadyMessage, providerReady } from "@/unit/research/provider";
import { createSupportBundle } from "@/unit/support";
import { Icon } from "../icons";
import { Button, ClassicLink, Field, Tag, TextArea, TextInput } from "../ui";
import { useResearch } from "./context";

const CARD = "rounded-md border border-border bg-surface-raised p-5";
const EYEBROW = "font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint";
const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

type Failure = { kind: "analysis"; message: string; jobId: string | null } | { kind: "provider"; message: string };

export function BriefStep() {
  const { store, boot, state, runJob, toast } = useResearch();
  const router = useRouter();
  const p = state.project;
  const [failure, setFailure] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);

  const edit = (field: TopField | BriefingField, value: string) =>
    store.update(({ project, analysis }) => editBrief(project, analysis, field, value));

  // analyzeBrief -> ensureAnalysis1776 -> go('plan').
  const analyse = async () => {
    setFailure(null);
    setBusy(true);
    try {
      const current = store.get();
      const withCtx = withAttachmentContext(current.project);
      if (reusableAnalysis(withCtx, current.analysis)) {
        if (withCtx.briefing.attachments_context !== current.project.briefing.attachments_context) {
          store.update(() => ({ project: withCtx }), { reason: "brief_attachments_context", invalidateCheck: false });
        }
        toast(ANALYSIS_REUSED);
      } else {
        if (briefEmpty(withCtx)) throw new Error(BRIEF_EMPTY);
        const provider = activeProvider(current.preferredProvider, current.project.run_policy?.provider, boot);
        if (!(await providerReady(provider, { boot, model: String(current.project.model || "") }))) {
          setFailure({ kind: "provider", message: notReadyMessage(provider) });
          return;
        }
        // The job is addressed to the saved project: a new or edited brief is saved first.
        if (!current.projectId || current.save.kind !== "saved") await store.flush();
        const result = await runJob("researchAnalyze", analysisPayload(withCtx), { title: ANALYSIS_JOB_TITLE, warnMs: ANALYSIS_WARN_MS });
        store.update(() => mergeAnalysis(withCtx, result, boot), { reason: "ai_analysis_1780" });
      }
      const id = store.get().projectId;
      if (id) router.push(`/app/research/${encodeURIComponent(id)}/plan`);
    } catch (e) {
      setFailure({ kind: "analysis", message: message(e), jobId: e instanceof JobError ? e.jobId : null });
    } finally {
      setBusy(false);
    }
  };

  const selected = new Set(selectedProblemTypes(p));
  return (
    <div className="flex max-w-5xl flex-col gap-4">
      {failure ? <FailureCard failure={failure} onRetry={analyse} /> : null}

      <section className={CARD} aria-labelledby="brief-what">
        <div className={EYEBROW}>{t("research.brief.quickStart")}</div>
        <h2 id="brief-what" className="mt-1 text-lg font-semibold">{t("research.brief.whatSolve")}</h2>
        <div className="mt-3 grid grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] gap-2">
          {PROBLEM_TYPES.map(([key, label, sub]) => {
            const on = selected.has(key);
            return (
              <button
                key={key}
                type="button"
                aria-pressed={on}
                onClick={() => store.update(({ project }) => ({ project: toggleProblemType(project, key) }), { reason: "problem_types_1789" })}
                className={`flex min-h-16 flex-col items-start gap-0.5 rounded-sm border px-3 py-2 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${
                  on ? "border-signal bg-signal-wash text-signal" : "border-border-strong bg-surface hover:bg-surface-sunken"
                }`}
              >
                <span className="flex w-full items-center gap-1.5 text-sm font-semibold">
                  <span className="flex-1">{label}</span>
                  {on ? <Icon name="done" size={14} /> : null}
                </span>
                <span className={`text-xs ${on ? "text-signal" : "text-ink-muted"}`}>{sub}</span>
              </button>
            );
          })}
        </div>
        <p className="mt-2 text-xs text-ink-muted">{t("research.brief.typesHelp")}</p>

        <div className="mt-5 flex flex-col gap-4">
          <Field label={`${t("research.brief.titleLabel")} · ${t("research.brief.optional")}`}>
            <TextInput value={titleValue(p)} placeholder={t("research.brief.titlePlaceholder")} onChange={(e) => edit("title", e.target.value)} />
          </Field>
          <Field label={t("research.brief.goalLabel")}>
            <TextArea
              className="min-h-32 w-full"
              value={p.goal || ""}
              placeholder={t("research.brief.goalPlaceholder")}
              onChange={(e) => edit("goal", e.target.value)}
            />
          </Field>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-surface px-4 py-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold">{t("research.brief.aiLabel")}</div>
            <div className="text-xs text-ink-muted">{t("research.brief.aiHelp")}</div>
          </div>
          <Button variant="primary" onClick={analyse} disabled={busy}>
            {t("research.brief.aiLabel")}
          </Button>
        </div>
      </section>

      <Attachments />

      <details className={`${CARD} group`}>
        <summary className="cursor-pointer list-none text-sm">
          <span className="inline-flex items-center gap-2">
            <Icon name="back" size={12} className="-rotate-180 transition-transform group-open:-rotate-90" />
            <b>{t("research.brief.moreContext")}</b>
            <span className="text-xs text-ink-muted">{t("research.brief.optional")}</span>
          </span>
        </summary>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Field label={t("research.brief.productDescription")}>
            <TextArea value={p.briefing.product_description || ""} onChange={(e) => edit("product_description", e.target.value)} />
          </Field>
          <Field label={t("research.brief.decisionUse")}>
            <TextArea value={p.decision_use || ""} onChange={(e) => edit("decision_use", e.target.value)} />
          </Field>
          <Field label={t("research.brief.situation")}>
            <TextArea value={p.briefing.situation || ""} onChange={(e) => edit("situation", e.target.value)} />
          </Field>
          <Field label={t("research.brief.whatIsKnown")}>
            <TextArea value={p.briefing.what_is_known || ""} onChange={(e) => edit("what_is_known", e.target.value)} />
          </Field>
          <Field label={t("research.brief.constraints")} className="md:col-span-2">
            <TextArea value={p.briefing.constraints || ""} onChange={(e) => edit("constraints", e.target.value)} />
          </Field>
        </div>
      </details>

      <div className="flex justify-end border-t border-border pt-4">
        <Button variant="primary" onClick={analyse} disabled={busy || !canAnalyse(p)}>
          {t("research.brief.next")}
          <Icon name="next" size={14} />
        </Button>
      </div>
    </div>
  );
}

/** The classic error card, with what failed said in words, or the provider notice. */
function FailureCard({ failure, onRetry }: { failure: Failure; onRetry: () => void }) {
  const { toast } = useResearch();
  if (failure.kind === "provider") {
    return (
      <section role="alert" className="rounded-md border border-status-you-ink/40 bg-status-you-wash p-5">
        <p className="flex items-center gap-2 text-sm font-semibold text-status-you-ink">
          <Icon name="you" size={14} />
          {failure.message}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={onRetry}>{t("research.retry")}</Button>
          <ClassicLink href={classicHref({ go: "settings" })}>{t("research.openSettings")}</ClassicLink>
        </div>
      </section>
    );
  }
  const diagnostics = () =>
    createSupportBundle(failure.jobId).then(
      (url) => {
        toast(t("research.supportCreated"));
        window.location.href = url;
      },
      (e: unknown) => toast(tv("research.supportFailed", { message: message(e) })),
    );
  return (
    <section role="alert" className="rounded-md border border-status-fault/40 bg-status-fault-wash p-5">
      <h2 className="flex items-center gap-2 font-semibold text-status-fault">
        <Icon name="fault" size={14} />
        {t("research.brief.failedTitle")}
      </h2>
      <p className="mt-1 text-sm text-ink">{t("research.brief.failedSub")}</p>
      {failure.message ? <p className="mt-1 text-xs text-ink-muted">{failure.message}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" onClick={onRetry}>{t("research.retry")}</Button>
        <Button onClick={() => void diagnostics()}>{t("research.diagnostics")}</Button>
      </div>
    </section>
  );
}

/** Přílohy a odkazy: files are uploaded as they are picked, links kept as http(s) only. */
function Attachments() {
  const { store, state, toast } = useResearch();
  const files = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const list: Attachment[] = state.project.briefing.attachments || [];

  // uploadBriefAttachments1785: up to eight files, one request each, saved once at the end.
  const upload = async (picked: File[]) => {
    if (!picked.length) return;
    setError(null);
    setUploading(true);
    const records: Attachment[] = [];
    try {
      for (const f of picked.slice(0, MAX_FILES_PER_PICK)) {
        records.push(
          (await unit("projectAttachment", {
            body: { filename: f.name, data_b64: await fileToBase64(f) },
            timeoutMs: ATTACHMENT_TIMEOUT_MS,
          })) as Attachment,
        );
      }
      toast(t("research.brief.uploaded"));
    } catch (e) {
      setError(message(e));
    } finally {
      // What the unit already stored is kept, even when a later file failed.
      if (records.length) store.update(({ project }) => ({ project: addAttachments(project, records) }), { reason: "brief_attachments" });
      setUploading(false);
      if (files.current) files.current.value = "";
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
    <section className={CARD} aria-labelledby="brief-attach">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 id="brief-attach" className="text-base font-semibold">{t("research.brief.attachTitle")}</h2>
          <p className="mt-1 text-sm text-ink-muted">{t("research.brief.attachHelp")}</p>
        </div>
        <Tag>{list.length}</Tag>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input
          ref={files}
          type="file"
          multiple
          hidden
          aria-label={t("research.brief.filesLabel")}
          accept=".pdf,.docx,.xlsx,.xlsm,.csv,.txt,.md,.json,.tsv,image/*,video/*"
          onChange={(e) => void upload([...(e.target.files || [])])}
        />
        <Button icon="attach" aria-label={t("research.brief.addFilesAria")} disabled={uploading} onClick={() => files.current?.click()}>
          {t("research.brief.addFiles")}
        </Button>
        <form
          className="flex min-w-64 flex-1 gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            link();
          }}
        >
          <TextInput
            inputMode="url"
            aria-label={t("research.brief.urlLabel")}
            placeholder={t("research.brief.urlPlaceholder")}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="min-w-0 flex-1"
          />
          <Button type="submit" variant="quiet" icon="link" aria-label={t("research.brief.addLinkAria")}>
            {t("research.brief.addLink")}
          </Button>
        </form>
      </div>
      <div aria-live="polite">
        {uploading ? (
          <p className="mt-3 flex items-center gap-2 text-sm text-status-running">
            <Icon name="running" size={14} className="animate-spin" />
            <b>{t("research.brief.uploading")}</b> {t("research.brief.uploadingSub")}
          </p>
        ) : null}
        {error ? <p role="alert" className="mt-3 text-sm text-status-fault">{error}</p> : null}
      </div>
      <ul className="mt-3 flex flex-col divide-y divide-border rounded-sm border border-border">
        {list.length ? (
          list.map((x, i) => {
            const line = attachmentLine(x);
            return (
              <li key={`${i}-${x.sha256 || x.url || x.filename}`} className="flex items-center gap-3 px-3 py-2">
                <Icon name={x.kind === "url" ? "link" : "attach"} size={14} className="text-ink-muted" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-semibold">{line.name}</div>
                  <div className="truncate text-xs text-ink-muted">{line.detail}</div>
                </div>
                <Button
                  small
                  variant="quiet"
                  onClick={() => store.update(({ project }) => ({ project: removeAttachment(project, i) }), { reason: "brief_attachment_remove" })}
                >
                  {t("research.brief.remove")}
                </Button>
              </li>
            );
          })
        ) : (
          <li className="px-3 py-2 text-xs text-ink-muted">{t("research.brief.noAttachments")}</li>
        )}
      </ul>
    </section>
  );
}
