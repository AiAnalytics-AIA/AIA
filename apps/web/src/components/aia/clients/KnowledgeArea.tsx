"use client";

// Znalosti: this client's own context (ADR 0015 decision 7) -- never a global
// knowledge base -- as a library (client-workspace C4). Views (everything, waiting on a
// person, in no folder, unchanged for a year), the client's folders and labels, the kinds;
// the items as a table with the open item beside it. What a person adds or edits takes
// effect at once (ADR 0019); what a study or an AI offers waits as a proposal a person
// accepts -- the one who offered it may accept it, unless the client turned that off and
// the API says so. Folders and labels are organization, never knowledge (D4).

import { useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import {
  type KnowledgeFolder,
  type KnowledgeLabel,
  type KnowledgeSection,
  LABEL_COLOURS,
  type LabelColour,
  type Proposal,
  type SourceAdded,
  workspace,
} from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { takesFile, titleFromFilename, withSource } from "@/lib/client-sources";
import { relative } from "@/lib/format";
import { LABEL_DOT, type LibraryView, type StaleEdit, folderOf, folderView, staleEdit } from "@/lib/knowledge-library";
import { type Ask, AskDialog, Button, Chip, Field, Select, TextArea, TextInput } from "../../rehome/ui";
import { CARD, EYEBROW, Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { ClientPage, useClient } from "./ClientContext";
import { KnowledgeLibrary, said } from "./KnowledgeLibrary";
import { SourceCard, SourcePicker } from "./SourceFile";

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
  const decide = (p: Proposal, approve: boolean, reviewedRevision?: number) =>
    workspace.decide(clientId, p.proposal_id, approve, "", reviewedRevision).then(
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
          setError(e instanceof Error ? e.message : String(e));
        }
      },
    );
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
                      <p className="mt-2 text-xs text-ink-faint">
                        {p.study_name ? tv("aia.knowledge.fromStudy", { name: p.study_name }) : t("aia.knowledge.fromClient")} · {relative(p.proposed_at)}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {p.yours ? <Chip tone="neutral">{t("aia.knowledge.yours")}</Chip> : null}
                      {mayApprove ? (
                        <>
                          <Button small variant="primary" onClick={() => void decide(p, true)}>{t("aia.knowledge.approve")}</Button>
                          <Button small onClick={() => void decide(p, false)}>{t("aia.knowledge.reject")}</Button>
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
  const [kind, setKind] = useState<string>("FACT");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  // The file a Dokument, Zdroj or Datová sada carries: already the client's source (C7a).
  const [source, setSource] = useState<SourceAdded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const withFile = takesFile(kind);
  const submit = () => {
    if (!title.trim()) return;
    const content = withFile && source ? withSource({}, source.source_id) : {};
    workspace.propose(clientId, { kind, title: title.trim(), summary, content }).then((added) => onDone(added), (e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  };
  return (
    <section className={`${CARD} mb-5`} aria-labelledby="kn-propose">
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
      {withFile ? (
        <div className="mt-3 flex flex-col gap-2" role="group" aria-label={t("aia.sources.file")}>
          <span className="text-xs font-medium text-ink-muted">{t("aia.sources.file")}</span>
          {source ? <SourceCard clientId={clientId} sourceId={source.source_id} /> : null}
          <SourcePicker
            clientId={clientId}
            label={source ? t("aia.sources.replace") : t("aia.sources.pick")}
            onStored={(s) => {
              setSource(s);
              if (!title.trim()) setTitle(titleFromFilename(s.filename));
            }}
          />
          <p className="text-xs leading-5 text-ink-faint">{t("aia.sources.notKnowledge")}</p>
        </div>
      ) : null}
      <Field label={t("aia.knowledge.proposeSummary")} className="mt-3">
        <TextArea value={summary} onChange={(e) => setSummary(e.target.value)} />
      </Field>
      {error ? <p role="alert" className="mt-2 text-sm text-status-fault">{error}</p> : null}
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={!title.trim()} onClick={submit}>{t("aia.knowledge.propose")}</Button>
        <Button variant="quiet" onClick={() => onDone()}>{t("aia.cancel")}</Button>
      </div>
    </section>
  );
}

/** A view another page links to (Přehled's "Projít", its health lines); any other value is ignored. */
const viewRequested = (params: URLSearchParams): LibraryView | null => {
  const v = params.get("view");
  return v === "review" || v === "unfiled" || v === "old" ? v : null;
};

function NavButton({ on, onClick, children, count, attention = false }: { on: boolean; onClick: () => void; children: ReactNode; count?: number | null; attention?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`flex min-h-9 w-full items-center gap-2 rounded-control px-2 text-left text-[13px] ${FOCUS} ${on ? "bg-signal-wash font-semibold text-signal" : "text-ink hover:bg-surface-sunken"}`}
    >
      <span className="min-w-0 flex-1 truncate">{children}</span>{" "}
      {count != null && count > 0 ? (
        <span className={`rounded-pill px-1.5 font-mono text-[11px] ${attention ? "bg-status-you text-ink" : "text-ink-faint"}`}>{count}</span>
      ) : null}
    </button>
  );
}

const SECTION_HEAD = "mx-2 mb-1 mt-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-ink-faint";

function NewLabel({ onCreate }: { onCreate: (name: string, colour: LabelColour) => Promise<boolean> }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [colour, setColour] = useState<LabelColour>("BLUE");
  if (!open) {
    return (
      <Button small variant="quiet" icon="plus" onClick={() => setOpen(true)}>
        {t("aia.library.newLabel")}
      </Button>
    );
  }
  return (
    <form
      className="flex flex-col gap-2 rounded-sm border border-border p-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!name.trim()) return;
        void onCreate(name, colour).then((ok) => {
          if (!ok) return;
          setName("");
          setOpen(false);
        });
      }}
    >
      <Field label={t("aia.library.labelName")}>
        <TextInput value={name} onChange={(e) => setName(e.target.value)} autoFocus />
      </Field>
      <Field label={t("aia.library.labelColour")}>
        <Select value={colour} onChange={(e) => setColour(e.target.value as LabelColour)}>
          {LABEL_COLOURS.map((c) => (
            <option key={c} value={c}>{t(`aia.library.colours.${c}`)}</option>
          ))}
        </Select>
      </Field>
      <div className="flex gap-2">
        <Button small variant="primary" type="submit" disabled={!name.trim()}>{t("aia.library.create")}</Button>
        <Button small variant="quiet" onClick={() => setOpen(false)}>{t("aia.cancel")}</Button>
      </div>
    </form>
  );
}

export function KnowledgeArea() {
  // `reload` re-reads the client, so the tabs' counts follow an addition or a decision.
  const { client, reload } = useClient();
  const router = useRouter();
  const clientId = client.client_id;
  const mayView = client.permissions.includes("VIEW_CLIENT_KNOWLEDGE");
  const mayPropose = client.permissions.includes("PROPOSE_CLIENT_KNOWLEDGE");
  const mayApprove = client.permissions.includes("APPROVE_CLIENT_KNOWLEDGE");
  // What another page asked for (?add=1, ?view=…), from the router: after an in-app navigation
  // window.location is not yet the new URL when this first renders.
  const params = useSearchParams();
  const addRequested = params.get("add") === "1";
  const asked = params.get("add") !== null || params.get("view") !== null;
  const [view, setView] = useState<LibraryView>(() => viewRequested(new URLSearchParams(params.toString())) ?? "all");
  const [label, setLabel] = useState<string | null>(null);
  const [section, setSection] = useState<KnowledgeSection | "all">("all");
  // "Přidat znalost" on any other area of the client lands here with ?add=1: the form opens.
  const [proposing, setProposing] = useState(() => mayPropose && mayView && addRequested);
  const [version, setVersion] = useState(0);
  const [ask, setAsk] = useState<Ask | null>(null);
  const [error, setError] = useState<string | null>(null);
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

  const newFolder = () =>
    setAsk({
      kind: "prompt",
      message: t("aia.library.newFolderAsk"),
      initial: "",
      resolve: (name) => {
        if (name?.trim()) void attempt(workspace.createFolder(clientId, name));
      },
    });
  const renameFolder = (f: KnowledgeFolder) =>
    setAsk({
      kind: "prompt",
      message: t("aia.library.renameFolderAsk"),
      initial: f.name,
      resolve: (name) => {
        if (name?.trim() && name.trim() !== f.name) void attempt(workspace.renameFolder(clientId, f.folder_id, name));
      },
    });
  const deleteFolder = (f: KnowledgeFolder) =>
    setAsk({
      kind: "confirm",
      message: tv("aia.library.deleteFolderAsk", { name: f.name, n: f.item_count }),
      resolve: (ok) => {
        if (ok) void attempt(workspace.deleteFolder(clientId, f.folder_id), () => setView("all"));
      },
    });
  const renameLabel = (l: KnowledgeLabel) =>
    setAsk({
      kind: "prompt",
      message: t("aia.library.renameLabelAsk"),
      initial: l.name,
      resolve: (name) => {
        if (name?.trim() && name.trim() !== l.name) void attempt(workspace.changeLabel(clientId, l.label_id, { name }));
      },
    });
  const deleteLabel = (l: KnowledgeLabel) =>
    setAsk({
      kind: "confirm",
      message: tv("aia.library.deleteLabelAsk", { name: l.name, n: l.item_count }),
      resolve: (ok) => {
        if (ok) void attempt(workspace.deleteLabel(clientId, l.label_id), () => setLabel(null));
      },
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
      actions={mayPropose ? <Button variant="primary" icon="plus" onClick={() => setProposing(true)}>{t("aia.knowledge.propose")}</Button> : null}
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
                        <NavButton key={f.folder_id} on={view === folderView(f.folder_id)} onClick={() => pick(folderView(f.folder_id))} count={f.item_count}>
                          {f.name}
                        </NavButton>
                      ))}
                    </>
                  ) : (
                    <p className="mx-2 text-xs text-ink-faint">{t("aia.library.noFolders")}</p>
                  )
                }
              </Loaded>
              {mayPropose ? (
                <Button small variant="quiet" icon="plus" onClick={newFolder}>
                  {t("aia.library.newFolder")}
                </Button>
              ) : null}

              <p className={SECTION_HEAD}>{t("aia.library.labelsTitle")}</p>
              <Loaded res={labels} retry={retryLabels}>
                {(list) =>
                  list.length ? (
                    <div role="group" aria-label={t("aia.library.labelsTitle")} className="flex flex-wrap gap-1.5 px-2 pb-1">
                      {list.map((l) => (
                        <button
                          key={l.label_id}
                          type="button"
                          aria-pressed={label === l.label_id}
                          disabled={view === "review"}
                          onClick={() => setLabel(label === l.label_id ? null : l.label_id)}
                          className={`inline-flex min-h-7 items-center gap-1.5 rounded-pill border px-2.5 text-xs disabled:opacity-50 ${FOCUS} ${label === l.label_id ? "border-signal bg-signal-wash font-medium text-signal" : "border-border bg-surface-raised text-ink hover:border-border-strong"}`}
                        >
                          <span aria-hidden="true" className={`size-[7px] rounded-full ${LABEL_DOT[l.colour]}`} />
                          {l.name}{" "}
                          {l.item_count ? <span className="font-mono text-[10px] text-ink-faint">{l.item_count}</span> : null}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="mx-2 text-xs text-ink-faint">{t("aia.library.noLabels")}</p>
                  )
                }
              </Loaded>
              {mayPropose ? (
                <div className="px-1 pt-1">
                  <NewLabel onCreate={(name, colour) => attempt(workspace.createLabel(clientId, name, colour))} />
                </div>
              ) : null}
              <p className="mx-2 mt-3 border-t border-border pt-2 text-[11px] leading-4 text-ink-faint">{t("aia.library.filingNote")}</p>
            </nav>

            <div className="flex min-w-0 flex-[999_1_40rem] flex-col gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="min-w-0 flex-1 text-lg font-semibold">{heading}</h2>
                {mayPropose && folder ? (
                  <>
                    <Button small onClick={() => renameFolder(folder)}>{t("aia.library.rename")}</Button>
                    <Button small onClick={() => deleteFolder(folder)}>{t("aia.library.deleteFolder")}</Button>
                  </>
                ) : null}
              </div>
              {activeLabel && view !== "review" ? (
                <div className="flex flex-wrap items-center gap-2 text-[13px]">
                  <span className="text-ink-muted">{t("aia.library.labelFilter")}</span>
                  <span className="inline-flex items-center gap-1.5 font-medium">
                    <span aria-hidden="true" className={`size-[7px] rounded-full ${LABEL_DOT[activeLabel.colour]}`} />
                    {activeLabel.name}
                  </span>
                  {mayPropose ? (
                    <>
                      <label className="flex items-center gap-1">
                        <span className="sr-only">{t("aia.library.labelColour")}</span>
                        <Select
                          value={activeLabel.colour}
                          className="w-auto min-h-8"
                          onChange={(e) => void attempt(workspace.changeLabel(clientId, activeLabel.label_id, { colour: e.target.value as LabelColour }))}
                        >
                          {LABEL_COLOURS.map((c) => (
                            <option key={c} value={c}>{t(`aia.library.colours.${c}`)}</option>
                          ))}
                        </Select>
                      </label>
                      <Button small onClick={() => renameLabel(activeLabel)}>{t("aia.library.rename")}</Button>
                      <Button small onClick={() => deleteLabel(activeLabel)}>{t("aia.library.deleteLabel")}</Button>
                    </>
                  ) : null}
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
                    clientId={clientId}
                    view={view}
                    label={label}
                    section={section}
                    folders={folderList}
                    labels={labelList}
                    mayPropose={mayPropose}
                    version={version}
                    onChanged={changed}
                  />
                </>
              )}
            </div>
          </div>
          <AskDialog ask={ask} onDone={() => setAsk(null)} />
        </>
      )}
    </ClientPage>
  );
}
