"use client";

// The client's knowledge as a library (client-workspace C4): the items a view, a kind and a
// search select, as a table; ticked items moved and labelled together; the open item beside
// the list -- its text edited into a new revision, its folder and labels, its history.
// Folders and labels are organization: filing writes no revision and no model sees it (D4).

import { type ReactNode, useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  ApiError,
  type KnowledgeFolder,
  type KnowledgeItem,
  type KnowledgeLabel,
  type KnowledgeSection,
  type Placement,
  workspace,
} from "@/lib/api";
import { sourceIdOf, takesFile, withSource } from "@/lib/client-sources";
import { relative } from "@/lib/format";
import { LABEL_DOT, type LibraryView, actedOn, atCap, filingFor, shown, staleEdit, toggled, toggledAll } from "@/lib/knowledge-library";
import { Button, Field, Tag, TextArea, TextInput } from "../../rehome/ui";
import { type MenuItem, MenuButton } from "../../ui/MenuButton";
import { CARD, Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { SourceCard, SourcePicker } from "./SourceFile";
import type { AiRights } from "./SourceProposals";

const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

/** How long the search waits for typing to pause before it asks (MemorySearch's 300 ms). */
const SEARCH_PAUSE_MS = 300;

/** "Bez složky" as a menu item: takes the items out of every folder. */
const NO_FOLDER = "none";

/** The folders as menu items, "Bez složky" last; `current` (the item's own) offered but disabled. */
function folderItems(folders: readonly KnowledgeFolder[], current?: string | null): MenuItem<string>[] {
  return [
    ...folders.map((f) => ({ key: f.folder_id, label: f.name, disabled: f.folder_id === current })),
    { key: NO_FOLDER, label: t("aia.library.noFolder"), disabled: current === null },
  ];
}

function labelItems(labels: readonly KnowledgeLabel[]): MenuItem<string>[] {
  return labels.map((l) => ({ key: l.label_id, label: <LabelName label={l} /> }));
}

function LabelName({ label }: { label: KnowledgeLabel }): ReactNode {
  return (
    <span className="inline-flex min-w-0 items-center gap-2">
      <span aria-hidden="true" className={`size-[7px] shrink-0 rounded-full ${LABEL_DOT[label.colour]}`} />
      <span className="truncate">{label.name}</span>
    </span>
  );
}

const folderOfKey = (key: string): string | null => (key === NO_FOLDER ? null : key);

/** A refusal in words: the API's code where AIA has its own wording, else its message. */
export function said(e: unknown): string {
  if (e instanceof ApiError && e.code === "name_taken") return t("aia.library.nameTaken");
  const stale = staleEdit(e);
  if (stale) return tv("aia.library.staleEdit", { current: stale.current });
  if (e instanceof ApiError && e.status === 404) return t("aia.library.goneMeanwhile");
  return e instanceof Error ? e.message : String(e);
}

export function LabelChip({ label, onRemove }: { label: KnowledgeLabel; onRemove?: () => void }) {
  return (
    <span className="inline-flex min-h-5 items-center gap-1.5 rounded-pill border border-border bg-surface-raised px-2 text-[11px] leading-4 text-ink-muted">
      <span aria-hidden="true" className={`size-[7px] shrink-0 rounded-full ${LABEL_DOT[label.colour]}`} />
      {label.name}
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          aria-label={tv("aia.library.removeLabel", { name: label.name })}
          className={`-mr-1 rounded-sm px-1 text-ink-faint hover:text-ink ${FOCUS}`}
        >
          ×
        </button>
      ) : null}
    </span>
  );
}

type LibraryProps = {
  clientId: string;
  view: LibraryView;
  label: string | null;
  section: KnowledgeSection | "all";
  folders: KnowledgeFolder[];
  labels: KnowledgeLabel[];
  mayPropose: boolean;
  /** AI proposals from a document's file (lifecycle K2d5); absent: not offered. */
  ai?: AiRights;
  /** Bumped by anything that changed what the library shows. */
  version: number;
  /** Something was filed, edited or retitled: folders, labels and the tabs' counts follow. */
  onChanged: () => void;
  /** The item another page linked to (?item=…), open from the start. */
  initialOpen?: string | null;
};

export function KnowledgeLibrary({ clientId, view, label, section, folders, labels, mayPropose, ai, version, onChanged, initialOpen = null }: LibraryProps) {
  // What is typed, and what is asked: the API is asked once the typing pauses for SEARCH_PAUSE_MS
  // (audit D9, IA-4: ten letters were ten requests), as project memory's search does.
  const [typed, setTyped] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setQ(typed.trim()), SEARCH_PAUSE_MS);
    return () => clearTimeout(id);
  }, [typed]);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [openId, setOpenId] = useState<string | null>(initialOpen);
  const [error, setError] = useState<string | null>(null);
  // "A year ago" is fixed when the library opens, so a re-render never reshuffles the old view.
  const [now] = useState(() => Date.now());
  const filing = filingFor(view, label);
  const [res, retry] = useResource(
    () => workspace.knowledge(clientId, section === "all" ? undefined : section, q || undefined, filing),
    [clientId, section, q, filing.folder, filing.label, version],
  );
  const folderName = new Map(folders.map((f) => [f.folder_id, f.name]));
  const labelOf = new Map(labels.map((l) => [l.label_id, l]));

  const place = (placement: Placement) =>
    workspace.place(clientId, placement).then(
      () => {
        setError(null);
        onChanged();
      },
      (e: unknown) => setError(said(e)),
    );

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-3">
      <Field label={t("aia.knowledge.search")} className="max-w-md">
        <TextInput type="search" value={typed} onChange={(e) => setTyped(e.target.value)} />
      </Field>
      {error ? <p role="alert" className="rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{error}</p> : null}
      <Loaded res={res} retry={retry}>
        {(all) => {
          const items = shown(all, view, now);
          const ids = items.map((i) => i.item_id);
          const acting = actedOn(selected, ids);
          const open = items.find((i) => i.item_id === openId) ?? null;
          return (
            <div className="flex flex-wrap items-start gap-5">
              <div className="flex min-w-0 flex-[999_1_32rem] flex-col gap-3">
                {mayPropose && acting.length ? (
                  <BulkBar
                    count={acting.length}
                    folders={folders}
                    labels={labels}
                    onPlace={(p) => void place({ ...p, item_ids: acting })}
                    onClear={() => setSelected(new Set())}
                  />
                ) : null}
                {items.length ? (
                  <div className="overflow-x-auto rounded-md border border-border bg-surface-raised">
                    <table className="w-full border-collapse text-sm">
                      <caption className="sr-only">{t("aia.library.tableCaption")}</caption>
                      <thead>
                        <tr className="border-b border-border bg-surface-sunken text-left text-[11px] font-semibold uppercase tracking-[0.04em] text-ink-muted">
                          {mayPropose ? (
                            <th scope="col" className="w-10 px-3 py-2">
                              <input
                                type="checkbox"
                                aria-label={t("aia.library.selectAll")}
                                checked={ids.length > 0 && ids.every((id) => selected.has(id))}
                                onChange={() => setSelected(toggledAll(selected, ids))}
                                className="size-4"
                              />
                            </th>
                          ) : null}
                          <th scope="col" className="px-3 py-2">{t("aia.library.columns.item")}</th>
                          <th scope="col" className="px-3 py-2">{t("aia.library.columns.kind")}</th>
                          {/* Below sm the filing and the revision stay in the opened item, so the row fits a phone. */}
                          <th scope="col" className="hidden px-3 py-2 sm:table-cell">{t("aia.library.columns.filed")}</th>
                          <th scope="col" className="hidden px-3 py-2 text-right sm:table-cell">{t("aia.library.columns.revision")}</th>
                          <th scope="col" className="px-3 py-2 text-right">{t("aia.library.columns.changed")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((i) => (
                          <tr key={i.item_id} className={`border-b border-border last:border-b-0 ${i.item_id === openId ? "bg-signal-wash" : "hover:bg-surface"}`}>
                            {mayPropose ? (
                              <td className="px-3 py-2.5 align-top">
                                <input
                                  type="checkbox"
                                  aria-label={tv("aia.library.select", { title: i.title })}
                                  checked={selected.has(i.item_id)}
                                  onChange={() => setSelected(toggled(selected, i.item_id))}
                                  className="mt-0.5 size-4"
                                />
                              </td>
                            ) : null}
                            <td className="max-w-[28rem] px-3 py-2.5 align-top">
                              <button
                                type="button"
                                aria-pressed={i.item_id === openId}
                                onClick={() => setOpenId(i.item_id === openId ? null : i.item_id)}
                                className={`block w-full rounded-sm text-left ${FOCUS}`}
                              >
                                <span className="block font-medium text-ink underline-offset-2 hover:underline">{i.title}</span>
                                {i.summary ? <span className="mt-0.5 line-clamp-2 block text-[13px] text-ink-muted">{i.summary}</span> : null}
                              </button>
                            </td>
                            <td className="px-3 py-2.5 align-top">
                              <Tag>{t(`aia.knowledge.kinds.${i.kind}`)}</Tag>
                            </td>
                            <td className="hidden px-3 py-2.5 align-top sm:table-cell">
                              <span className="flex flex-wrap items-center gap-1">
                                <span className="mr-1 text-xs text-ink-muted">{i.folder_id ? (folderName.get(i.folder_id) ?? "") : t("aia.library.noFolder")}</span>
                                {(i.label_ids ?? []).map((id) => {
                                  const l = labelOf.get(id);
                                  return l ? <LabelChip key={id} label={l} /> : null;
                                })}
                              </span>
                            </td>
                            <td className="hidden px-3 py-2.5 text-right align-top font-mono text-xs sm:table-cell">{i.revision}</td>
                            <td className="whitespace-nowrap px-3 py-2.5 text-right align-top text-xs text-ink-faint">{relative(i.modified_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty>{t(view === "old" ? "aia.library.emptyOld" : "aia.library.empty")}</Empty>
                )}
                {atCap(all) ? <p className="text-xs text-ink-muted">{t("aia.library.atCap")}</p> : null}
              </div>
              {open ? (
                <aside aria-label={t("aia.library.openLabel")} className="min-w-0 flex-[1_1_20rem] lg:max-w-[26rem]">
                  <ItemPanel
                    key={`${open.item_id}@${open.revision}`}
                    clientId={clientId}
                    item={open}
                    folders={folders}
                    labels={labels}
                    mayPropose={mayPropose}
                    ai={ai}
                    onClose={() => setOpenId(null)}
                    onPlace={(p) => place({ ...p, item_ids: [open.item_id] })}
                    onChanged={onChanged}
                  />
                </aside>
              ) : null}
            </div>
          );
        }}
      </Loaded>
    </div>
  );
}

function BulkBar({
  count,
  folders,
  labels,
  onPlace,
  onClear,
}: {
  count: number;
  folders: KnowledgeFolder[];
  labels: KnowledgeLabel[];
  onPlace: (p: Omit<Placement, "item_ids">) => void;
  onClear: () => void;
}) {
  return (
    <div role="region" aria-label={t("aia.library.bulkLabel")} className="flex flex-wrap items-center gap-2 rounded-md border border-border-strong bg-surface-sunken px-3 py-2">
      <span className="text-sm font-semibold">{tv("aia.library.selected", { n: count })}</span>
      <span className="flex-1" />
      {/* Actions, so menus: never a select that files on change (I3, audit D11 / IA-6). */}
      <MenuButton icon="projects" label={t("aia.library.moveTo")} items={folderItems(folders)} onSelect={(k) => onPlace({ folder_id: folderOfKey(k) })} />
      {labels.length ? (
        <>
          <MenuButton icon="tag" label={t("aia.library.addLabel")} items={labelItems(labels)} onSelect={(k) => onPlace({ add_labels: [k] })} />
          <MenuButton label={t("aia.library.removeLabelBulk")} items={labelItems(labels)} onSelect={(k) => onPlace({ remove_labels: [k] })} />
        </>
      ) : null}
      <Button small variant="quiet" onClick={onClear}>{t("aia.library.clearSelection")}</Button>
    </div>
  );
}

function ItemPanel({
  clientId,
  item,
  folders,
  labels,
  mayPropose,
  ai,
  onClose,
  onPlace,
  onChanged,
}: {
  clientId: string;
  item: KnowledgeItem;
  folders: KnowledgeFolder[];
  labels: KnowledgeLabel[];
  mayPropose: boolean;
  ai?: AiRights;
  onClose: () => void;
  onPlace: (p: Omit<Placement, "item_ids">) => Promise<void>;
  onChanged: () => void;
}) {
  const [title, setTitle] = useState(item.title);
  const [summary, setSummary] = useState(item.summary);
  // The item's file (C7a): the one it names, or one just picked to be named by the next revision.
  const named = sourceIdOf(item.content);
  const [picked, setPicked] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, retryHistory] = useResource(() => workspace.revisions(clientId, item.item_id), [clientId, item.item_id, item.revision]);
  const on = new Set(item.label_ids ?? []);
  const fileShown = picked ?? named;
  const changed = title.trim() !== item.title || summary !== item.summary || (picked !== null && picked !== named);
  // An edit keeps the item's content: it names the file shown, and keeps whatever else it held.
  const save = () =>
    workspace
      .propose(clientId, {
        kind: item.kind,
        title: title.trim(),
        summary,
        content: picked ? withSource(item.content, picked) : (item.content ?? {}),
        item_id: item.item_id,
        base_revision: item.revision,
      })
      .then(
        (p) => {
          setPicked(null);
          setError(null);
          // Where the client asked for independent review, an edit waits for someone else.
          setNote(p.status === "PROPOSED" ? t("aia.library.editWaits") : null);
          onChanged();
        },
        (e: unknown) => setError(said(e)),
      );
  return (
    <section aria-labelledby="kn-open" className={`${CARD} flex flex-col gap-4`}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <Tag>{t(`aia.knowledge.kinds.${item.kind}`)}</Tag>
          <h2 id="kn-open" className="mt-1.5 text-base font-semibold">{item.title}</h2>
          <p className="text-xs text-ink-faint">{tv("aia.knowledge.revision", { n: item.revision })} · {relative(item.modified_at)}</p>
        </div>
        <Button small variant="quiet" onClick={onClose}>{t("aia.library.close")}</Button>
      </div>
      {mayPropose ? (
        <div className="flex flex-col gap-3">
          <Field label={t("aia.knowledge.proposeTitleField")}>
            <TextInput value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
          <Field label={t("aia.library.summary")}>
            <TextArea value={summary} onChange={(e) => setSummary(e.target.value)} />
          </Field>
          {takesFile(item.kind) ? (
            <div className="flex flex-col gap-2" role="group" aria-label={t("aia.sources.file")}>
              <span className="text-xs font-medium text-ink-muted">{t("aia.sources.file")}</span>
              {fileShown ? <SourceCard key={fileShown} clientId={clientId} sourceId={fileShown} ai={fileShown === named ? ai : undefined} mayMark={mayPropose} /> : null}
              <SourcePicker
                clientId={clientId}
                label={fileShown ? t("aia.sources.replace") : t("aia.sources.attach")}
                onStored={(s) => setPicked(s.source_id)}
              />
              {picked !== null && picked !== named ? <p className="text-xs text-status-you-ink">{t("aia.sources.fileIsSaved")}</p> : null}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <Button small variant="primary" disabled={!changed || !title.trim()} onClick={() => void save()}>
              {tv("aia.library.saveRevision", { n: item.revision + 1 })}
            </Button>
            {note ? <span role="status" className="text-xs text-status-you-ink">{note}</span> : null}
          </div>
        </div>
      ) : (
        <>
          {item.summary ? <p className="text-sm text-ink-muted">{item.summary}</p> : null}
          {named ? <SourceCard clientId={clientId} sourceId={named} ai={ai} mayMark={mayPropose} /> : null}
        </>
      )}
      {error ? <p role="alert" className="text-sm text-status-fault">{error}</p> : null}

      <div className="grid gap-3 border-t border-border pt-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5" role="group" aria-labelledby="kn-open-folder">
          <span id="kn-open-folder" className="text-xs font-medium text-ink-muted">{t("aia.library.folder")}</span>
          <span className="text-sm">{item.folder_id ? (folders.find((f) => f.folder_id === item.folder_id)?.name ?? "") : t("aia.library.noFolder")}</span>
          {mayPropose ? (
            <span>
              <MenuButton
                icon="projects"
                label={t("aia.library.changeFolder")}
                items={folderItems(folders, item.folder_id ?? null)}
                onSelect={(k) => void onPlace({ folder_id: folderOfKey(k) })}
              />
            </span>
          ) : null}
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-ink-muted">{t("aia.library.labels")}</span>
          <span className="flex flex-wrap items-center gap-1">
            {labels
              .filter((l) => on.has(l.label_id))
              .map((l) => (
                <LabelChip key={l.label_id} label={l} onRemove={mayPropose ? () => void onPlace({ remove_labels: [l.label_id] }) : undefined} />
              ))}
            {on.size === 0 ? <span className="text-xs text-ink-faint">{t("aia.library.noLabels")}</span> : null}
          </span>
          {mayPropose && labels.length ? (
            <span>
              <MenuButton
                icon="plus"
                label={t("aia.library.addLabel")}
                items={labelItems(labels.filter((l) => !on.has(l.label_id)))}
                empty={t("aia.library.allLabelsOn")}
                onSelect={(k) => void onPlace({ add_labels: [k] })}
              />
            </span>
          ) : null}
        </div>
      </div>
      <p className="text-xs leading-5 text-ink-faint">{t("aia.library.filingNote")}</p>

      <div className="border-t border-border pt-3">
        <h3 className="mb-2 text-xs font-semibold text-ink-muted">{t("aia.library.history")}</h3>
        <Loaded res={history} retry={retryHistory}>
          {(revs) => (
            <ol className="flex flex-col gap-2">
              {[...revs].reverse().map((r) => (
                <li key={r.revision} className="grid grid-cols-[2.5rem_minmax(0,1fr)] gap-2 text-xs leading-4">
                  <span className="font-mono text-ink-muted">r{r.revision}</span>
                  <span>
                    <span className="block text-ink">{r.title}</span>
                    <span className="text-ink-faint">{originOf(r.provenance)} · {relative(r.approved_at)}</span>
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Loaded>
      </div>
    </section>
  );
}

/** Where a revision came from, in words: a study, a person writing, or a decided proposal. */
function originOf(provenance: Record<string, unknown>): string {
  if (provenance.origin === "STUDY") return t("aia.library.originStudy");
  if (provenance.authored === "person") return t("aia.library.originPerson");
  return t("aia.library.originDecided");
}
