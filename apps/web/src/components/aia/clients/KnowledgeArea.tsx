"use client";

// Znalosti: this client's own context (ADR 0015 decision 7) -- never a global
// knowledge base. The three layers are said at the top, so it is plain where a
// piece of knowledge comes from; changes arrive only as proposals a person
// approves, and the proposer is not the one who approves.

import { useState } from "react";

import { t, tv } from "@/i18n/t";
import { type KnowledgeItem, type KnowledgeSection, type Proposal, workspace } from "@/lib/api";
import { relative } from "@/lib/format";
import { Button, Chip, Field, Select, Tag, TextArea, TextInput } from "../../rehome/ui";
import { CARD, EYEBROW, Empty, Loaded } from "../states";
import { useResource } from "../useResource";
import { ClientPage, useClient } from "./ClientContext";
import { studyHref } from "./ClientOverview";
import Link from "next/link";

type Section = KnowledgeSection | "previous" | "pending";
const SECTIONS: Section[] = ["sources", "knowledge", "previous", "dimensions", "audiences", "pending"];
const PROPOSABLE = ["SOURCE", "DOCUMENT", "FACT", "FINDING", "TERM", "ENTITY", "DIMENSION", "AUDIENCE", "DATASET"] as const;

export function Layers() {
  const layers: [string, string][] = [
    [t("aia.knowledge.layerShared"), t("aia.knowledge.layerSharedText")],
    [t("aia.knowledge.layerClient"), t("aia.knowledge.layerClientText")],
    [t("aia.knowledge.layerStudy"), t("aia.knowledge.layerStudyText")],
  ];
  return (
    <section aria-label={t("aia.knowledge.layers")} className="mb-5 flex flex-wrap items-stretch gap-2 text-sm">
      {layers.map(([name, text], i) => (
        <div key={name} className="flex items-center gap-2">
          {i > 0 ? <span aria-hidden="true" className="text-ink-faint">→</span> : null}
          <div className={`rounded-sm border px-3 py-2 ${i === 1 ? "border-signal-edge bg-signal-wash" : "border-border bg-surface-raised"}`}>
            <div className="font-medium">{name}</div>
            <div className="text-xs text-ink-muted">{text}</div>
          </div>
        </div>
      ))}
    </section>
  );
}

function Items({ clientId, section }: { clientId: string; section: KnowledgeSection }) {
  const [q, setQ] = useState("");
  const [res, retry] = useResource(() => workspace.knowledge(clientId, section, q || undefined), [clientId, section, q]);
  return (
    <>
      <Field label={t("aia.knowledge.search")} className="mb-3 max-w-md">
        <TextInput type="search" value={q} onChange={(e) => setQ(e.target.value)} />
      </Field>
      <Loaded res={res} retry={retry}>
        {(items: KnowledgeItem[]) =>
          items.length ? (
            <ul className="grid gap-3 md:grid-cols-2">
              {items.map((i) => (
                <li key={i.item_id} className={CARD}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium">{i.title}</span>
                    <Tag>{t(`aia.knowledge.kinds.${i.kind}`)}</Tag>
                  </div>
                  {i.summary ? <p className="mt-1 text-sm text-ink-muted">{i.summary}</p> : null}
                  <p className="mt-2 text-xs text-ink-faint">
                    {tv("aia.knowledge.revision", { n: i.revision })} · {relative(i.modified_at)}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>{t(`aia.knowledge.empty.${section}`)}</Empty>
          )
        }
      </Loaded>
    </>
  );
}

function Previous({ clientId }: { clientId: string }) {
  const [res, retry] = useResource(() => workspace.studies(clientId), [clientId]);
  return (
    <Loaded res={res} retry={retry}>
      {(studies) => {
        const done = studies.filter((s) => s.status === "DELIVERED" || s.status === "ARCHIVED");
        return done.length ? (
          <ul className="flex flex-col gap-2">
            {done.map((s) => (
              <li key={s.study_id} className={`${CARD} flex items-center gap-3 py-3`}>
                <Link href={studyHref(clientId, s)} className="flex-1 font-medium text-ink underline-offset-2 hover:underline">{s.name}</Link>
                <Tag>{t(`aia.kind.${s.kind}`)}</Tag>
                <Chip tone="done">{t(`aia.status.${s.status}`)}</Chip>
              </li>
            ))}
          </ul>
        ) : (
          <Empty>{t("aia.knowledge.empty.previous")}</Empty>
        );
      }}
    </Loaded>
  );
}

function Pending({ clientId, mayApprove }: { clientId: string; mayApprove: boolean }) {
  const [res, retry] = useResource(() => workspace.proposals(clientId, "PROPOSED"), [clientId]);
  const [error, setError] = useState<string | null>(null);
  const decide = (p: Proposal, approve: boolean) =>
    workspace.decide(clientId, p.proposal_id, approve).then(retry, (e: unknown) => setError(e instanceof Error ? e.message : String(e)));
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
                      <p className="mt-2 text-xs text-ink-faint">
                        {p.study_name ? tv("aia.knowledge.fromStudy", { name: p.study_name }) : t("aia.knowledge.fromClient")} · {relative(p.proposed_at)}
                      </p>
                    </div>
                    {mayApprove && !p.yours ? (
                      <div className="flex gap-2">
                        <Button small variant="primary" onClick={() => void decide(p, true)}>{t("aia.knowledge.approve")}</Button>
                        <Button small onClick={() => void decide(p, false)}>{t("aia.knowledge.reject")}</Button>
                      </div>
                    ) : p.yours ? (
                      <Chip tone="neutral">{t("aia.knowledge.yours")}</Chip>
                    ) : null}
                  </div>
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

function ProposeForm({ clientId, onDone }: { clientId: string; onDone: () => void }) {
  const [kind, setKind] = useState<string>("FACT");
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = () => {
    if (!title.trim()) return;
    workspace.propose(clientId, { kind, title: title.trim(), summary }).then(onDone, (e: unknown) => setError(e instanceof Error ? e.message : String(e)));
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
      <Field label={t("aia.knowledge.proposeSummary")} className="mt-3">
        <TextArea value={summary} onChange={(e) => setSummary(e.target.value)} />
      </Field>
      {error ? <p role="alert" className="mt-2 text-sm text-status-fault">{error}</p> : null}
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={!title.trim()} onClick={submit}>{t("aia.knowledge.propose")}</Button>
        <Button variant="quiet" onClick={onDone}>{t("aia.cancel")}</Button>
      </div>
    </section>
  );
}

export function KnowledgeArea() {
  const { client } = useClient();
  const [section, setSection] = useState<Section>("sources");
  const [proposing, setProposing] = useState(false);
  const [version, setVersion] = useState(0);
  const mayView = client.permissions.includes("VIEW_CLIENT_KNOWLEDGE");
  const mayPropose = client.permissions.includes("PROPOSE_CLIENT_KNOWLEDGE");
  const mayApprove = client.permissions.includes("APPROVE_CLIENT_KNOWLEDGE");
  return (
    <ClientPage
      sub={t("aia.knowledge.sub")}
      actions={mayPropose ? <Button variant="primary" icon="plus" onClick={() => setProposing(true)}>{t("aia.knowledge.propose")}</Button> : null}
    >
      {!mayView ? (
        <Empty>{t("aia.knowledge.noAccess")}</Empty>
      ) : (
        <>
          <Layers />
          {proposing ? (
            <ProposeForm
              clientId={client.client_id}
              onDone={() => {
                setProposing(false);
                setSection("pending");
                setVersion((v) => v + 1);
              }}
            />
          ) : null}
          <div role="tablist" aria-label={t("aia.knowledge.sectionsLabel")} className="mb-4 flex flex-wrap gap-1">
            {SECTIONS.map((s) => (
              <button
                key={s}
                type="button"
                role="tab"
                aria-selected={section === s}
                onClick={() => setSection(s)}
                className={`rounded-sm border px-3 py-1.5 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${section === s ? "border-signal bg-signal-wash font-semibold text-ink" : "border-border bg-surface-raised text-ink-muted hover:text-ink"}`}
              >
                {t(`aia.knowledge.sections.${s}`)}
              </button>
            ))}
          </div>
          <div role="tabpanel" key={`${section}-${version}`}>
            {section === "previous" ? (
              <Previous clientId={client.client_id} />
            ) : section === "pending" ? (
              <Pending clientId={client.client_id} mayApprove={mayApprove} />
            ) : (
              <Items clientId={client.client_id} section={section} />
            )}
          </div>
        </>
      )}
    </ClientPage>
  );
}
