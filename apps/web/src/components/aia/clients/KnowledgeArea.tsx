"use client";

// Znalosti: this client's own context (ADR 0015 decision 7) -- never a global
// knowledge base -- as a library (client-workspace C4). Views (everything, waiting on a
// person, in no folder, unchanged for a year), the client's folders and labels, the kinds;
// the items as a table with the open item beside it. What a person adds or edits takes
// effect at once (ADR 0019); what a study or an AI offers waits as a proposal a person
// accepts -- the one who offered it may accept it, unless the client turned that off and
// the API says so. Folders and labels are organization, never knowledge (D4).

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { t, tv } from "@/i18n/t";
import {
  type KnowledgeFiling,
  type KnowledgeFolder,
  type KnowledgeLabel,
  type KnowledgeSection,
  type LabelColour,
  type Proposal,
  workspace,
} from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { locatorWords, takesFile } from "@/lib/client-sources";
import { relative } from "@/lib/format";
import { LABEL_DOT, type LibraryView, type StaleEdit, folderOf, folderView, nextLabelColour, staleEdit, undoable } from "@/lib/knowledge-library";
import { Button, Chip, Field, Select, TextArea, TextInput } from "../../rehome/ui";
import { InlineCreateRow } from "../../ui/InlineCreateRow";
import { UndoToast, useUndo } from "../../ui/UndoToast";
import { CARD, EYEBROW, Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { ClientPage, IntakeButton, useClient } from "./ClientContext";
import { FolderRow, LabelRow, NavButton, NewLabelRow, type OrganizerEdit } from "./KnowledgeOrganizers";
import { KnowledgeLibrary, said } from "./KnowledgeLibrary";
import { SourceCard } from "./SourceFile";
import { errorText } from "@/lib/error-words";

const PROPOSABLE = ["SOURCE", "DOCUMENT", "FACT", "FINDING", "TERM", "ENTITY", "DIMENSION", "AUDIENCE", "DATASET"] as const;
const KINDS: (KnowledgeSection | "all")[] = ["all", "sources", "knowledge", "dimensions", "audiences", "data"];
// Where an added item shows up (domain KNOWLEDGE_SECTIONS).
const SECTION_OF: Record<string, KnowledgeSection> = {
  SOURCE: "sources",
  DOCUMENT: "sources",
  DIMENSION: "dimensions",
  AUDIENCE: "audiences",
  DATASET: "data",
};
const FOCUS = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring";

function Pending({ clientId, mayApprove, onDecided }: { clientId: string; mayApprove: boolean; onDecided: () => void }) {
  const [res, retry] = useResource(() => workspace.proposals(clientId, "PROPOSED"), [clientId]);
  const [error, setError] = useState<string | null>(null);
  // An approval refused because the item moved on (F-K1): which proposal, and the revision now current.
  const [stale, setStale] = useState<{ proposalId: string; edit: StaleEdit } | null>(null);
  // The proposal a decision is being sent for: its buttons wait, so a second click sends nothing.
  const [deciding, setDeciding] = useState<string | null>(null);
  const decide = (p: Proposal, approve: boolean, reviewedRevision?: number) => {
    if (deciding) return Promise.resolve();
    setDeciding(p.proposal_id);
    return workspace.decide(clientId, p.proposal_id, approve, "", reviewedRevision).then(
      () => {
        setError(null);
        setStale(null);
        retry();
        onDecided();
      },
      (e: unknown) => {
        const edit = staleEdit(e);
        if (edit) {
          setError(null);
          setStale({ proposalId: p.proposal_id, edit });
        } else {
          setStale(null);
          setError(errorText(e));
        }
      },
    ).finally(() => setDeciding(null));
  };
  return (
    <>
      {error ? <p role="alert" className="mb-3 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{error}</p> : null}
      <Loaded res={res} retry={retry}>
        {(list) =>
          list.length ? (
            <ul className="flex flex-col gap-3">
              {list.map((p) => (
                <li key={p.proposal_id} className={CARD}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className={EYEBROW}>{t(`aia.knowledge.kinds.${p.kind}`)}</div>
                      <div className="mt-1 font-medium">{p.title}</div>
                      {p.summary ? <p className="mt-1 text-sm text-ink-muted">{p.summary}</p> : null}
                      {p.source_id ? (
                        <div className="mt-2">
                          <SourceCard clientId={clientId} sourceId={p.source_id} compact />
                        </div>
                      ) : null}
                      {p.from_source ? (
                        // What an AI proposal rests on: the words, found by code where it says.
                        <figure className="mt-2 flex flex-col gap-1.5">
                          <blockquote className="border-l-2 border-spark-1 pl-2 text-sm">„{p.from_source.quote}“</blockquote>
                          <figcaption className="text-xs text-ink-faint">
                            {t("aia.sources.ai.quote")} · {locatorWords(p.from_source.locator)}
                          </figcaption>
                          <SourceCard clientId={clientId} sourceId={p.from_source.source_id} compact />
                        </figure>
                      ) : null}
                      <p className="mt-2 text-xs text-ink-faint">
                        {p.from_source
                          ? t("aia.sources.ai.fromAi")
                          : p.study_name
                            ? tv("aia.knowledge.fromStudy", { name: p.study_name })
                            : t("aia.knowledge.fromClient")}{" "}
                        · {relative(p.proposed_at)}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {/* An AI proposal is the AI's words, not its starter's. */}
                      {p.yours && !p.from_source ? <Chip tone="neutral">{t("aia.knowledge.yours")}</Chip> : null}
                      {mayApprove ? (
                        <>
                          <Button small variant="primary" disabled={deciding !== null} aria-busy={deciding === p.proposal_id || undefined} onClick={() => void decide(p, true)}>{t("aia.knowledge.approve")}</Button>
                          <Button small disabled={deciding !== null} aria-busy={deciding === p.proposal_id || undefined} onClick={() => void decide(p, false)}>{t("aia.knowledge.reject")}</Button>
                        </>
                      ) : null}
                    </div>
                  </div>
                  {stale?.proposalId === p.proposal_id ? (
                    <div role="alert" className="mt-3 flex flex-col gap-2 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">
                      <p>
                        {stale.edit.base === null
                          ? tv("aia.knowledge.staleDecisionUnknown", { current: stale.edit.current })
                          : tv("aia.knowledge.staleDecision", { base: stale.edit.base, current: stale.edit.current })}
                      </p>
                      <div>
                        <Button small onClick={() => void decide(p, true, stale.edit.current)}>
                          {tv("aia.knowledge.approveOver", { current: stale.edit.current })}
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>{t("aia.knowledge.empty.pending")}</Empty>
          )
        }
      </Loaded>
    </>
  );
}

function AddForm({ clientId, onDone }: { clientId: string; onDone: (added?: Proposal) => void }) {
  const { openIntake } = useClient();
  const [kind, setKind] = useState<string>("FACT");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // A form: Enter in the title saves, Esc leaves; one request at a time (design system v3, Interakce).
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!title.trim() || busy) return;
    setBusy(true);
    workspace.propose(clientId, { kind, title: title.trim(), summary }).then(
      (added) => onDone(added),
      (err: unknown) => { setError(errorText(err)); setBusy(false); },
    );
  };
  return (
    <form className={`${CARD} mb-5`} aria-labelledby="kn-propose" onSubmit={submit}
      onKeyDown={(e) => { if (e.key === "Escape" && !e.defaultPrevented && !busy) { e.preventDefault(); onDone(); } }}>
      <h2 id="kn-propose" className="text-base font-semibold">{t("aia.knowledge.proposeTitle")}</h2>
      <div className="mt-3 grid gap-3 md:grid-cols-[12rem_minmax(0,1fr)]">
        <Field label={t("aia.knowledge.proposeKind")}>
          <Select value={kind} onChange={(e) => setKind(e.target.value)}>
            {PROPOSABLE.map((k) => (
              <option key={k} value={k}>{t(`aia.knowledge.kinds.${k}`)}</option>
            ))}
          </Select>
        </Field>
        <Field label={t("aia.knowledge.proposeTitleField")}>
          <TextInput value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
      </div>
      {takesFile(kind) ? (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-xs leading-5 text-ink-muted">
          <span>{t("aia.knowledge.fileByIntake")}</span>
          <Button small icon="attach" onClick={() => openIntake()}>{t("aia.client.addKnowledge")}</Button>
        </p>
      ) : null}
      <Field label={t("aia.knowledge.proposeSummary")} className="mt-3">
        <TextArea value={summary} onChange={(e) => setSummary(e.target.value)} />
      </Field>
      {error ? <p role="alert" className="mt-2 text-sm text-status-fault">{error}</p> : null}
      <div className="mt-3 flex gap-2">
        <Button variant="primary" type="submit" disabled={!title.trim() || busy} aria-busy={busy || undefined}>{t("aia.knowledge.proposeSubmit")}</Button>
        <Button variant="quiet" disabled={busy} onClick={() => onDone()}>{t("aia.cancel")}</Button>
      </div>
    </form>
  );
}

/** A view another page links to (Přehled's "Projít", its health lines); any other value is ignored. */
const viewRequested = (params: URLSearchParams): LibraryView | null => {
  const v = params.get("view");
  return v === "review" || v === "unfiled" || v === "old" ? v : null;
};

const SECTION_HEAD = "mx-2 mb-1 mt-3 text-xs font-medium text-ink-faint";

/** A folder or a label just deleted, or about to be once its row is confirmed. */
type Doomed = { kind: "folder"; folder: KnowledgeFolder } | { kind: "label"; label: KnowledgeLabel };

export function KnowledgeArea() {
  // `reload` re-reads the client, so the tabs' counts follow an addition or a decision.
  const { client, reload, added } = useClient();
  const router = useRouter();
  const clientId = client.client_id;
  const mayView = client.permissions.includes("VIEW_CLIENT_KNOWLEDGE");
  const mayPropose = client.permissions.includes("PROPOSE_CLIENT_KNOWLEDGE");
  const mayApprove = client.permissions.includes("APPROVE_CLIENT_KNOWLEDGE");
  // AI proposals from a document, paid by the client (lifecycle K2d5).
  const ai = {
    ask: mayPropose && client.permissions.includes("RUN_CLIENT_WORK"),
    lift: client.permissions.includes("MANAGE_CLIENT_BUDGET"),
  };
  // What another page asked for (?add=1, ?view=…), from the router: after an in-app navigation
  // window.location is not yet the new URL when this first renders.
  const params = useSearchParams();
  const addRequested = params.get("add") === "1";
  const asked = params.get("add") !== null || params.get("view") !== null || params.get("item") !== null;
  // An item another page linked to ("Ověřeno, přidat zdroj"), opened once in the library.
  const [linkedItem] = useState(() => params.get("item"));
  const [view, setView] = useState<LibraryView>(() => viewRequested(new URLSearchParams(params.toString())) ?? "all");
  const [label, setLabel] = useState<string | null>(null);
  const [section, setSection] = useState<KnowledgeSection | "all">("all");
  // "Přidat znalost" on any other area of the client lands here with ?add=1: the form opens.
  const [proposing, setProposing] = useState(() => mayPropose && mayView && addRequested);
  const [edits, setVersion] = useState(0);
  // What the intake sheet added is read again here, wherever the sheet was opened.
  const version = edits + added;
  const [error, setError] = useState<string | null>(null);
  // A deletion whose row asks first (its items could not all be read, so it could not be undone).
  const [asking, setAsking] = useState<Doomed | null>(null);
  const undo = useUndo();
  const [folders, retryFolders] = useResource(() => (mayView ? workspace.folders(clientId) : Promise.resolve([])), [clientId, mayView, version]);
  const [labels, retryLabels] = useResource(() => (mayView ? workspace.labels(clientId) : Promise.resolve([])), [clientId, mayView, version]);
  // Once read, the request leaves the URL, so a reload or a shared link does not reopen the form.
  useEffect(() => {
    if (asked) router.replace(appRoutes.area(clientId, "knowledge"));
  }, [asked, clientId, router]);

  const changed = () => {
    setVersion((v) => v + 1);
    reload();
  };
  const attempt = (work: Promise<unknown>, after?: () => void) =>
    work.then(
      () => {
        setError(null);
        after?.();
        changed();
        return true;
      },
      (e: unknown) => {
        setError(said(e));
        return false;
      },
    );
  const folderList: KnowledgeFolder[] = folders.state === "ready" ? folders.data : [];
  const labelList: KnowledgeLabel[] = labels.state === "ready" ? labels.data : [];
  const folderId = folderOf(view);
  const folder = folderList.find((f) => f.folder_id === folderId) ?? null;
  const activeLabel = labelList.find((l) => l.label_id === label) ?? null;
  const pick = (v: LibraryView) => {
    setView(v);
    if (v === "review") setLabel(null);
  };

  // "+ Nová složka" is a row in the folder list (input-interactions I5, audit D1): a refusal is
  // said at the row, the name kept; a created folder is listed and the next row opens.
  const newFolder = (name: string) =>
    workspace.createFolder(clientId, name).then(
      () => {
        setError(null);
        changed();
      },
      (e: unknown) => said(e),
    );
  // A rename is said at its field (InlineText): a rejection there is "Neuloženo – Zkusit znovu".
  const rename = (work: Promise<unknown>) =>
    work.then(() => {
      setError(null);
      changed();
    });
  const newLabel = (name: string, colour: LabelColour) =>
    workspace.createLabel(clientId, name, colour).then(
      () => {
        setError(null);
        changed();
      },
      (e: unknown) => said(e),
    );

  // A delete happens at once with "Vrátit" (input-interactions I6, audit D3, D7). Its items are read
  // first, so undo can make the folder or label again and file them back: new ids and two audit
  // entries, which the audit accepts for the MVP (§5.6; C9 owns a soft delete). When the read is
  // not every item filed there, nothing is deleted yet: the row asks, saying it cannot be undone.
  const filingOf = (d: Doomed): KnowledgeFiling => (d.kind === "folder" ? { folder: d.folder.folder_id } : { label: d.label.label_id });
  const countOf = (d: Doomed) => (d.kind === "folder" ? d.folder.item_count : d.label.item_count);
  const deleteNow = (d: Doomed) =>
    d.kind === "folder"
      ? attempt(workspace.deleteFolder(clientId, d.folder.folder_id), () => {
          if (folderId === d.folder.folder_id) setView("all");
        })
      : attempt(workspace.deleteLabel(clientId, d.label.label_id), () => {
          if (label === d.label.label_id) setLabel(null);
        });
  const restore = (d: Doomed, itemIds: string[]) => {
    const remade =
      d.kind === "folder"
        ? workspace.createFolder(clientId, d.folder.name).then((f) => (itemIds.length ? workspace.place(clientId, { item_ids: itemIds, folder_id: f.folder_id }) : null))
        : workspace.createLabel(clientId, d.label.name, d.label.colour).then((l) => (itemIds.length ? workspace.place(clientId, { item_ids: itemIds, add_labels: [l.label_id] }) : null));
    void remade.then(
      () => {
        setError(null);
        changed();
      },
      (e: unknown) => {
        setError(tv("aia.library.undoFailed", { reason: said(e) }));
        changed();
      },
    );
  };
  const remove = async (d: Doomed) => {
    setAsking(null);
    let filed: { item_id: string }[];
    try {
      filed = await workspace.knowledge(clientId, undefined, undefined, filingOf(d));
    } catch (e) {
      setError(said(e));
      return;
    }
    if (!undoable(countOf(d), filed)) {
      setAsking(d);
      return;
    }
    if (!(await deleteNow(d))) return;
    const ids = filed.map((i) => i.item_id);
    undo.offer({
      message: d.kind === "folder" ? tv("aia.library.folderDeleted", { name: d.folder.name }) : tv("aia.library.labelDeleted", { name: d.label.name }),
      undo: () => restore(d, ids),
    });
  };
  const askingFor = (kind: Doomed["kind"], id: string): string | null => {
    if (!asking || asking.kind !== kind) return null;
    if (asking.kind === "folder") return asking.folder.folder_id === id ? tv("aia.library.deleteFolderConfirm", { name: asking.folder.name, n: asking.folder.item_count }) : null;
    return asking.label.label_id === id ? tv("aia.library.deleteLabelConfirm", { name: asking.label.name, n: asking.label.item_count }) : null;
  };
  const editOf = (d: Doomed, names: readonly string[], save: (name: string) => Promise<unknown>): OrganizerEdit => ({
    names,
    rename: (name) => rename(save(name)),
    remove: () => void remove(d),
    confirm: askingFor(d.kind, d.kind === "folder" ? d.folder.folder_id : d.label.label_id),
    onConfirm: () => {
      setAsking(null);
      void deleteNow(d);
    },
    onKeep: () => setAsking(null),
  });

  const heading =
    view === "review"
      ? t("aia.library.views.review")
      : folder
        ? folder.name
        : view.startsWith("folder:")
          ? t("aia.library.views.all")
          : t(`aia.library.views.${view as "all" | "unfiled" | "old"}`);

  return (
    <ClientPage
      sub={t("aia.knowledge.sub")}
      actions={
        mayPropose ? (
          <>
            <IntakeButton variant="primary" />
            <Button icon="plus" onClick={() => setProposing(true)}>{t("aia.knowledge.propose")}</Button>
          </>
        ) : null
      }
    >
      {!mayView ? (
        <Empty>{t("aia.knowledge.noAccess")}</Empty>
      ) : (
        <>
          {proposing ? (
            <AddForm
              clientId={clientId}
              onDone={(added) => {
                setProposing(false);
                if (added) {
                  // Added knowledge is listed where it belongs; only a held-back one (the client asked
                  // for independent review) waits under Ke schválení.
                  if (added.status === "PROPOSED") pick("review");
                  else {
                    setView("all");
                    setLabel(null);
                    setSection(SECTION_OF[added.kind] ?? "knowledge");
                  }
                  changed();
                }
              }}
            />
          ) : null}
          {error ? <p role="alert" className="mb-4 rounded-sm border border-status-fault/40 bg-status-fault-wash p-3 text-sm text-status-fault">{error}</p> : null}
          <div className="flex flex-wrap items-start gap-5">
            <nav aria-label={t("aia.library.navLabel")} className="min-w-[13rem] flex-[1_1_13rem] rounded-md border border-border bg-surface-raised p-2 lg:max-w-[16rem]">
              <p className={`${SECTION_HEAD} mt-1`}>{t("aia.library.viewsTitle")}</p>
              <NavButton on={view === "all"} onClick={() => pick("all")}>{t("aia.library.views.all")}</NavButton>
              <NavButton on={view === "review"} onClick={() => pick("review")} count={client.counts?.pending_proposals} attention>
                {t("aia.library.views.review")}
              </NavButton>
              <NavButton on={view === "unfiled"} onClick={() => pick("unfiled")}>{t("aia.library.views.unfiled")}</NavButton>
              <NavButton on={view === "old"} onClick={() => pick("old")}>{t("aia.library.views.old")}</NavButton>

              <p className={SECTION_HEAD}>{t("aia.library.foldersTitle")}</p>
              <Loaded res={folders} retry={retryFolders}>
                {(list) =>
                  list.length ? (
                    <>
                      {list.map((f) => (
                        <FolderRow
                          key={f.folder_id}
                          folder={f}
                          on={view === folderView(f.folder_id)}
                          onPick={() => pick(folderView(f.folder_id))}
                          edit={
                            mayPropose
                              ? editOf({ kind: "folder", folder: f }, list.map((x) => x.name), (name) => workspace.renameFolder(clientId, f.folder_id, name))
                              : undefined
                          }
                        />
                      ))}
                    </>
                  ) : (
                    <p className="mx-2 text-xs text-ink-faint">{t("aia.library.noFolders")}</p>
                  )
                }
              </Loaded>
              {mayPropose ? (
                <div className="px-1 pt-1">
                  <InlineCreateRow label={t("aia.library.newFolder")} icon="projects" existing={folderList.map((f) => f.name)} onCreate={newFolder} />
                </div>
              ) : null}

              <p className={SECTION_HEAD}>{t("aia.library.labelsTitle")}</p>
              <Loaded res={labels} retry={retryLabels}>
                {(list) =>
                  list.length ? (
                    <div role="group" aria-label={t("aia.library.labelsTitle")} className="flex flex-col">
                      {list.map((l) => (
                        <LabelRow
                          key={l.label_id}
                          label={l}
                          on={label === l.label_id}
                          disabled={view === "review"}
                          onPick={() => setLabel(label === l.label_id ? null : l.label_id)}
                          edit={
                            mayPropose
                              ? editOf({ kind: "label", label: l }, list.map((x) => x.name), (name) => workspace.changeLabel(clientId, l.label_id, { name }))
                              : undefined
                          }
                          recolour={mayPropose ? (colour) => void attempt(workspace.changeLabel(clientId, l.label_id, { colour })) : undefined}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="mx-2 text-xs text-ink-faint">{t("aia.library.noLabels")}</p>
                  )
                }
              </Loaded>
              {mayPropose ? (
                <div className="px-1 pt-1">
                  <NewLabelRow existing={labelList.map((l) => l.name)} suggested={nextLabelColour(labelList)} onCreate={newLabel} />
                </div>
              ) : null}
              <p className="mx-2 mt-3 border-t border-border pt-2 text-[11px] leading-4 text-ink-faint">{t("aia.library.filingNote")}</p>
            </nav>

            <div className="flex min-w-0 flex-[999_1_40rem] flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="min-w-0 flex-1 text-lg font-semibold">{heading}</h2>
              </div>
              {activeLabel && view !== "review" ? (
                <div className="flex flex-wrap items-center gap-2 text-[13px]">
                  <span className="text-ink-muted">{t("aia.library.labelFilter")}</span>
                  <span className="inline-flex items-center gap-1.5 font-medium">
                    <span aria-hidden="true" className={`size-[7px] rounded-full ${LABEL_DOT[activeLabel.colour]}`} />
                    {activeLabel.name}
                  </span>
                  <Button small variant="quiet" onClick={() => setLabel(null)}>{t("aia.library.clearLabel")}</Button>
                </div>
              ) : null}
              {view === "review" ? (
                <Pending clientId={clientId} mayApprove={mayApprove} onDecided={changed} />
              ) : (
                <>
                  <div role="group" aria-label={t("aia.library.kindsLabel")} className="flex flex-wrap gap-1.5">
                    {KINDS.map((k) => (
                      <button
                        key={k}
                        type="button"
                        aria-pressed={section === k}
                        onClick={() => setSection(k)}
                        className={`inline-flex min-h-8 items-center rounded-pill border px-3 text-[13px] ${FOCUS} ${section === k ? "border-signal bg-signal-wash font-semibold text-signal" : "border-border bg-surface-raised text-ink hover:border-border-strong"}`}
                      >
                        {t(`aia.library.kinds.${k}`)}
                      </button>
                    ))}
                  </div>
                  <KnowledgeLibrary
                    initialOpen={linkedItem}
                    clientId={clientId}
                    view={view}
                    label={label}
                    section={section}
                    folders={folderList}
                    labels={labelList}
                    mayPropose={mayPropose}
                    ai={ai}
                    version={version}
                    onChanged={changed}
                  />
                </>
              )}
            </div>
          </div>
          <UndoToast offer={undo.current} onDone={undo.clear} />
        </>
      )}
    </ClientPage>
  );
}
