"use client";

// Přidat podklady (client-workspace C7b): the client's one way in for files, as the
// design draws it (artboard "Klient · Přidat podklady"). Every file is kept as the
// client's source the moment it lands, one request at a time, and its row says what
// reading produced; a table asks Datová sada or Dokument and names its personal-data
// columns; pasted text is kept as a text file. Přidat makes one knowledge item per
// file (C7a's content.source_id) and files them; with Navrhnout znalosti z textu ticked, it
// then asks AI for proposals from each document (lifecycle K2d5, paid by the client). Links
// are drawn and say they are not in AIA yet. Nothing here decides what is knowledge: the API does.

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { ApiError, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { FILE_ACCEPT, FILE_MAX_BYTES, reasonKnown, reasonWords, sizeWords } from "@/lib/client-sources";
import { plural } from "@/lib/format";
import {
  type Entry,
  type IntakeKind,
  type Made,
  action,
  alreadyKept,
  badge,
  changed,
  detailFailed,
  failed,
  folderOf,
  isTable,
  itemsFor,
  newEntry,
  pastedFile,
  personalColumns,
  placementsFor,
  removed,
  retryable,
  retrying,
  rowLine,
  stored,
  summary,
  withDetail,
} from "@/lib/intake";
import { canPropose, proposalsReason } from "@/lib/source-proposals";
import { fileToBase64 } from "@/research/brief";
import { Button, Chip, Field, Select, TextArea, TextInput } from "../../rehome/ui";
import { useResource } from "../useResource";
import { useClient } from "./ClientContext";
import { LabelChip } from "./KnowledgeLibrary";

const BADGE: Record<ReturnType<typeof badge>["tone"], string> = {
  pdf: "bg-status-fault-wash text-status-fault",
  word: "bg-status-running-wash text-status-running",
  table: "bg-signal-wash text-signal",
  slides: "bg-status-you-wash text-status-you-ink",
  plain: "bg-surface-sunken text-ink-muted",
};

/** A refused upload in words: the API's reason where AIA has words for it. */
function refusal(e: unknown): string {
  if (e instanceof ApiError && e.status === 422 && reasonKnown(e.code)) return tv("aia.sources.refused", { reason: reasonWords(e.code) });
  return e instanceof Error ? e.message : String(e);
}

let seq = 0;

export function IntakeSheet() {
  const { client, intake, closeIntake, noteAdded, reload } = useClient();
  const clientId = client.client_id;
  const router = useRouter();
  const path = usePathname() ?? "";
  const dialog = useRef<HTMLDialogElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [batchFolder, setBatchFolder] = useState<string | null>(null);
  const [labels, setLabels] = useState<string[]>([]);
  const [paste, setPaste] = useState<{ name: string; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [folders] = useResource(() => workspace.folders(clientId), [clientId]);
  const [labelList] = useResource(() => workspace.labels(clientId), [clientId]);
  const folderList = folders.state === "ready" ? folders.data : [];
  const allLabels = labelList.state === "ready" ? labelList.data : [];

  // Files are read one at a time, in the order they came: the queue and whether it runs.
  const queue = useRef<{ key: string; file: File }[]>([]);
  const running = useRef(false);
  const handed = useRef(0);
  // Items already made by an earlier attempt, and whether their filing is still owed: a retry
  // files them and never makes them again.
  const made = useRef<Made[]>([]);
  const waiting = useRef(0);
  // AI proposals (lifecycle K2d5): whether to ask, who may, and the documents whose items
  // exist and whose proposals are still owed -- asked once their batch is filed, kept for a
  // retry when filing fails, never asked twice (the API answers a second ask with the same run).
  const mayExtract = client.permissions.includes("PROPOSE_CLIENT_KNOWLEDGE") && client.permissions.includes("RUN_CLIENT_WORK");
  const [extract, setExtract] = useState(false);
  const owed = useRef<{ sourceId: string; name: string }[]>([]);
  const [unfiled, setUnfiled] = useState(false);
  // The files the page handed over, as of the last render: a drop during a save waits for it.
  const latest = useRef(intake);
  useEffect(() => {
    latest.current = intake;
  });

  // A table's columns, for the personal-data warning: the row reads until they are in.
  const columns = async (key: string, sourceId: string) => {
    try {
      const detail = await workspace.source(clientId, sourceId);
      setEntries((es) => withDetail(es, key, detail));
    } catch {
      setEntries((es) => detailFailed(es, key, t("aia.intake.columnsFailed")));
    }
  };

  const pump = async () => {
    if (running.current) return;
    running.current = true;
    try {
      for (let next = queue.current.shift(); next; next = queue.current.shift()) {
        const { key, file } = next;
        let source;
        try {
          source = await workspace.addSource(clientId, { filename: file.name, data_b64: await fileToBase64(file) });
        } catch (e) {
          setEntries((es) => failed(es, key, refusal(e)));
          continue;
        }
        setEntries((es) => stored(es, key, source));
        if (source.family === "DATASET") await columns(key, source.source_id);
      }
    } finally {
      running.current = false;
    }
  };

  const retry = (e: Entry) => {
    if (!e.source) return;
    setEntries((es) => retrying(es, e.key));
    void columns(e.key, e.source.source_id);
  };

  const take = (files: File[]) => {
    const added: Entry[] = [];
    for (const file of files) {
      const entry = newEntry(file, `f${++seq}`);
      if (file.size > FILE_MAX_BYTES) {
        added.push({ ...entry, phase: "failed", error: t("aia.intake.tooLarge") });
        continue;
      }
      added.push(entry);
      queue.current.push({ key: entry.key, file });
    }
    setNote(null);
    setEntries((es) => [...es, ...added]);
    void pump();
  };

  // Files handed over by the page (a drop anywhere on the client) join the list; during a save
  // they wait for it, so nothing joins a batch already being sent.
  useEffect(() => {
    if (!intake || saving) return;
    const fresh = intake.files.slice(handed.current);
    handed.current = intake.files.length;
    if (fresh.length) take(fresh);
    // take reads only refs and setters
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intake, saving]);

  useLayoutEffect(() => {
    const d = dialog.current;
    if (d && !d.open) d.showModal();
  }, []);

  const drop = (key: string) => {
    queue.current = queue.current.filter((q) => q.key !== key);
    setEntries((es) => removed(es, key));
  };

  const addPasted = () => {
    if (!paste || !paste.text.trim()) return;
    take([pastedFile(paste.name, paste.text)]);
    setPaste(null);
  };

  const close = () => {
    if (!saving) closeIntake();
  };

  // Every control is still while a save runs: the batch it sends is the one on screen.
  const save = async () => {
    setSaving(true);
    setError(null);
    const all = entries;
    let filing = false;
    try {
      for (const item of itemsFor(all)) {
        const p = await workspace.propose(clientId, { kind: item.kind, title: item.title, content: item.content });
        const row = all.find((e) => e.key === item.key)!;
        if (p.status === "APPROVED" && p.item_id) made.current.push({ itemId: p.item_id, folder: folderOf(row, batchFolder) });
        else waiting.current += 1;
        if (extract && row.source && canPropose(row.source)) owed.current.push({ sourceId: row.source.source_id, name: row.name });
        // Made: never sent twice, even if a later one fails.
        setEntries((es) => removed(es, item.key));
      }
      filing = true;
      // Filed from what is owed, so a failed placement is tried again with every item it held.
      for (const placement of placementsFor(made.current, labels)) await workspace.place(clientId, placement);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(filing ? tv("aia.intake.unfiled", { error: message }) : message);
      setUnfiled(made.current.length > 0);
      setSaving(false);
      if (made.current.length || waiting.current) {
        noteAdded();
        reload();
      }
      return;
    }
    const waited = waiting.current;
    made.current = [];
    waiting.current = 0;
    setUnfiled(false);
    // The items exist and are filed: ask AI about their documents, each on its own; one
    // refused says so and stops none of the others.
    const asking = owed.current;
    owed.current = [];
    const refused: string[] = [];
    for (const doc of asking) {
      try {
        await workspace.proposeFromSource(clientId, doc.sourceId);
      } catch (e) {
        refused.push(tv("aia.intake.extractFailed", { name: doc.name, reason: e instanceof ApiError ? proposalsReason(e.code) : String(e) }));
      }
    }
    setSaving(false);
    noteAdded();
    reload();
    const asked = asking.length - refused.length;
    if (refused.length) setError(refused.join(" "));
    if (waited || asking.length) {
      setNote(
        [
          waited ? t("aia.intake.waitsForApproval") : null,
          asked ? tv("aia.intake.extractAsked", { n: plural(asked, "dokumentu", "dokumentů", "dokumentů") }) : null,
        ]
          .filter(Boolean)
          .join(" "),
      );
      return;
    }
    // Files dropped on the page during the save stay on the sheet.
    if ((latest.current?.files.length ?? 0) > handed.current) return;
    closeIntake();
    if (!path.includes("/knowledge") && !path.includes("/data")) router.push(appRoutes.area(clientId, "knowledge"));
  };

  const act = action(entries, unfiled);
  return (
    <dialog
      ref={dialog}
      aria-labelledby="intake-title"
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      className="m-0 ml-auto flex h-dvh max-h-dvh w-[min(48rem,100vw)] max-w-none flex-col border-0 border-l border-border bg-surface-raised p-0 text-ink shadow-[var(--shadow-overlay)] backdrop:bg-surface-inverse/40"
    >
      <header className="flex items-start gap-3 border-b border-border px-6 pb-3.5 pt-[18px]">
        <div className="min-w-0 flex-1">
          <h2 id="intake-title" className="text-lg font-semibold leading-6">{tv("aia.intake.title", { client: client.name })}</h2>
          <p className="mt-0.5 text-[13px] text-ink-muted">{t("aia.intake.sub")}</p>
        </div>
        <Button small variant="quiet" disabled={saving} onClick={close}>{t("aia.intake.close")}</Button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto px-6 py-4">
        <div
          className="flex flex-col items-center justify-center gap-1.5 rounded-md border-[1.5px] border-dashed border-border-strong bg-surface px-4 py-6 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (!saving) take(Array.from(e.dataTransfer.files));
          }}
        >
          <strong className="text-sm">{t("aia.intake.drop")}</strong>
          <span className="text-xs leading-4 text-ink-muted">{t("aia.intake.formats")}</span>
          <input
            ref={picker}
            type="file"
            multiple
            hidden
            disabled={saving}
            aria-label={t("aia.intake.pickLabel")}
            accept={FILE_ACCEPT}
            onChange={(e) => {
              take(Array.from(e.target.files ?? []));
              e.target.value = "";
            }}
          />
          <span className="mt-1 flex flex-wrap items-center justify-center gap-1.5">
            <Button small disabled={saving} onClick={() => picker.current?.click()}>{t("aia.intake.pick")}</Button>
            <Button small disabled={saving} aria-expanded={paste !== null} onClick={() => setPaste(paste ? null : { name: "", text: "" })}>{t("aia.intake.pasteOpen")}</Button>
            <Button small disabled aria-describedby="intake-link-later">{t("aia.intake.link")}</Button>
            <span id="intake-link-later" className="text-xs text-ink-faint">{t("aia.intake.linkLater")}</span>
          </span>
        </div>

        {paste ? (
          <div className="flex flex-col gap-2 rounded-md border border-border bg-surface p-3">
            <Field label={t("aia.intake.pasteName")}>
              <TextInput disabled={saving} value={paste.name} onChange={(e) => setPaste({ ...paste, name: e.target.value })} />
            </Field>
            <Field label={t("aia.intake.pasteText")}>
              <TextArea rows={4} disabled={saving} value={paste.text} onChange={(e) => setPaste({ ...paste, text: e.target.value })} />
            </Field>
            <span className="flex flex-wrap items-center gap-2">
              <Button small disabled={saving || !paste.text.trim()} onClick={addPasted}>{t("aia.intake.pasteAdd")}</Button>
              <span className="text-xs text-ink-muted">{t("aia.intake.pasteHint")}</span>
            </span>
          </div>
        ) : null}

        <div className="grid gap-2.5 sm:grid-cols-2">
          <Field label={t("aia.intake.folderAll")}>
            <Select disabled={saving} value={batchFolder ?? ""} onChange={(e) => setBatchFolder(e.target.value || null)}>
              <option value="">{t("aia.intake.noFolder")}</option>
              {folderList.map((f) => (
                <option key={f.folder_id} value={f.folder_id}>{f.name}</option>
              ))}
            </Select>
          </Field>
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-ink-muted">{t("aia.intake.labelsAll")}</span>
            <span className="flex min-h-9 flex-wrap items-center gap-1">
              {allLabels
                .filter((l) => labels.includes(l.label_id))
                .map((l) => (
                  <LabelChip key={l.label_id} label={l} onRemove={saving ? undefined : () => setLabels(labels.filter((x) => x !== l.label_id))} />
                ))}
              {allLabels.some((l) => !labels.includes(l.label_id)) ? (
                <label>
                  <span className="sr-only">{t("aia.intake.addLabel")}</span>
                  <Select disabled={saving} value="" className="min-h-8" onChange={(e) => e.target.value && setLabels([...labels, e.target.value])}>
                    <option value="">{t("aia.intake.addLabel")}</option>
                    {allLabels
                      .filter((l) => !labels.includes(l.label_id))
                      .map((l) => (
                        <option key={l.label_id} value={l.label_id}>{l.name}</option>
                      ))}
                  </Select>
                </label>
              ) : null}
            </span>
          </div>
        </div>

        {entries.length ? (
          <ul aria-label={t("aia.intake.listLabel")} className="divide-y divide-border rounded-md border border-border">
            {entries.map((e) => (
              <Row
                key={e.key}
                entry={e}
                entries={entries}
                folders={folderList}
                locked={saving}
                onRetry={() => retry(e)}
                onChange={(change) => setEntries((es) => changed(es, e.key, change))}
                onRemove={() => drop(e.key)}
              />
            ))}
          </ul>
        ) : null}

        <div className="flex items-start gap-2.5 rounded-md border border-border bg-surface px-3.5 py-3">
          <input
            id="intake-extract"
            type="checkbox"
            disabled={!mayExtract || saving}
            checked={extract}
            onChange={(e) => setExtract(e.target.checked)}
            className="mt-0.5 size-[18px] accent-ai"
          />
          <label htmlFor="intake-extract" className="flex-1 text-[13px] leading-[18px]">
            <span className="flex flex-wrap items-center gap-2 font-semibold">{t("aia.intake.extract")}</span>
            <span className="mt-0.5 block text-ink-muted">{t("aia.intake.extractText")}</span>
          </label>
        </div>
      </div>

      <footer className="flex flex-wrap items-center gap-2.5 border-t border-border bg-surface px-6 py-3.5">
        <span aria-live="polite" className="min-w-0 flex-[1_1_16rem] text-xs leading-4 text-ink-muted">
          {error ? <span role="alert" className="text-status-fault">{error}</span> : note ?? summary(entries)}
        </span>
        <Button disabled={saving} onClick={close}>{t("aia.intake.cancel")}</Button>
        <Button variant="primary" disabled={act.disabled || saving} onClick={() => void save()}>
          {saving ? t("aia.intake.adding") : act.label}
        </Button>
      </footer>
    </dialog>
  );
}

function Row({
  entry: e,
  entries,
  folders,
  locked,
  onRetry,
  onChange,
  onRemove,
}: {
  entry: Entry;
  entries: Entry[];
  folders: { folder_id: string; name: string }[];
  locked: boolean;
  onRetry: () => void;
  onChange: (change: Partial<Pick<Entry, "kind" | "title" | "folder">>) => void;
  onRemove: () => void;
}) {
  const b = badge(e.name);
  const line = rowLine(entries, e);
  const kept = alreadyKept(e);
  const personal = personalColumns(e.detail);
  const takesItem = e.phase === "stored" && !e.duplicateOf;
  const kindWord = t(`aia.knowledge.kinds.${e.kind}`);
  return (
    <li className={`grid grid-cols-[44px_minmax(0,1fr)_auto] items-start gap-2.5 p-3 ${e.phase === "failed" ? "bg-status-fault-wash" : ""}`}>
      <span aria-hidden="true" className={`inline-flex h-[26px] min-w-10 items-center justify-center rounded-sm font-mono text-[10px] font-semibold ${BADGE[b.tone]}`}>
        {b.label}
      </span>
      <span className="flex min-w-0 flex-col gap-1.5">
        <span className="text-[13px] font-semibold [overflow-wrap:anywhere]">
          {e.name} <span className="font-normal text-ink-muted">· {sizeWords(e.size)}{e.phase === "stored" ? ` · ${kindWord}` : ""}</span>
        </span>
        <span role={e.phase === "failed" ? "alert" : undefined}>
          <Chip tone={line.tone}>{line.text}</Chip>
        </span>
        {kept ? <span className="text-xs leading-4 text-ink-muted">{kept}</span> : null}
        {takesItem && isTable(e) ? (
          <>
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-ink-muted">{t("aia.intake.saveAs")}</span>
              <span role="group" aria-label={tv("aia.intake.saveAsFor", { name: e.name })} className="inline-flex rounded-control border border-border bg-surface-sunken p-0.5">
                {(["DATASET", "DOCUMENT"] as IntakeKind[]).map((k) => (
                  <button
                    key={k}
                    type="button"
                    aria-pressed={e.kind === k}
                    disabled={locked}
                    onClick={() => onChange({ kind: k })}
                    className={`min-h-[30px] rounded-[4px] px-2.5 text-xs font-medium ${e.kind === k ? "bg-surface-raised text-ink shadow-[0_0_0_1px_var(--border)]" : "text-ink-muted"}`}
                  >
                    {k === "DATASET" ? t("aia.intake.asDataset") : t("aia.intake.asDocument")}
                  </button>
                ))}
              </span>
            </span>
            <span className={`text-xs leading-4 ${e.kind === "DATASET" ? "text-status-you-ink" : "text-ink-muted"}`}>
              {e.kind === "DATASET" ? t("aia.intake.datasetNote") : t("aia.intake.documentNote")}
              {personal.length
                ? ` ${tv(personal.length === 1 ? "aia.intake.personal" : "aia.intake.personalMany", { names: personal.join(", ") })}`
                : ""}
            </span>
          </>
        ) : null}
        {takesItem ? (
          <span className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_14rem]">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink-muted">{t("aia.intake.itemTitle")}</span>
              <TextInput disabled={locked} aria-label={tv("aia.intake.itemTitleFor", { name: e.name })} value={e.title} onChange={(ev) => onChange({ title: ev.target.value })} />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-ink-muted">{t("aia.library.folder")}</span>
              <Select
                disabled={locked}
                aria-label={tv("aia.intake.fileFolder", { name: e.name })}
                value={e.folder === undefined ? "__batch" : (e.folder ?? "")}
                onChange={(ev) => onChange({ folder: ev.target.value === "__batch" ? undefined : ev.target.value || null })}
              >
                <option value="__batch">{t("aia.intake.sameFolder")}</option>
                <option value="">{t("aia.intake.noFolder")}</option>
                {folders.map((f) => (
                  <option key={f.folder_id} value={f.folder_id}>{f.name}</option>
                ))}
              </Select>
            </label>
          </span>
        ) : null}
      </span>
      <span className="flex flex-col items-end gap-1">
        {retryable(e) ? (
          <Button small disabled={locked} aria-label={tv("aia.intake.retryFile", { name: e.name })} onClick={onRetry}>
            {t("aia.intake.retry")}
          </Button>
        ) : null}
        <Button small variant="quiet" disabled={locked} aria-label={tv(e.phase === "reading" ? "aia.intake.cancelFile" : "aia.intake.removeFile", { name: e.name })} onClick={onRemove}>
          {e.phase === "reading" ? t("aia.intake.cancel") : t("aia.intake.remove")}
        </Button>
      </span>
    </li>
  );
}
