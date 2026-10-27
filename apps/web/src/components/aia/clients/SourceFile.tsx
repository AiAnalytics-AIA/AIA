"use client";

// A file on a client's knowledge item (client-workspace C7a). The file is kept as the
// client's source (lifecycle K2: POST /clients/{id}/sources), read at once, and the item
// names it by id. SourcePicker stores one file and says what reading produced; SourceCard
// shows a named file: its name, size, the reading in words, what was read, the original,
// whether a person marked it "Interní dokument" (Class C for AI, the owner's rule of
// 2026-10-19) and, for a document, Navrhnout znalosti (lifecycle K2d5).

import { useRef, useState } from "react";

import { t, tv } from "@/i18n/t";
import { ApiError, type ClientSource, type SourceAdded, type SourceDetail, workspace } from "@/lib/api";
import { FILE_ACCEPT, FILE_MAX_BYTES, locatorWords, readingLine, reasonKnown, reasonWords, sizeWords } from "@/lib/client-sources";
import { saveBlob } from "@/lib/download";
import { canPropose } from "@/lib/source-proposals";
import { plural, relative } from "@/lib/format";
import { fileToBase64 } from "@/research/brief";
import { Button, Chip, Tag } from "../../rehome/ui";
import { useResource } from "../useResource";
import { type AiRights, SourceProposals } from "./SourceProposals";
import { errorText } from "@/lib/error-words";

/** How many of a source's segments the card shows; the original holds the rest. */
const SHOWN_SEGMENTS = 8;

type Upload =
  | { phase: "idle" }
  | { phase: "uploading"; name: string }
  | { phase: "stored"; source: SourceAdded }
  | { phase: "failed"; message: string };

/** A refusal of the upload in words: the API's reason where AIA has words for it. */
function refusal(e: unknown): string {
  if (e instanceof ApiError && e.status === 422 && reasonKnown(e.code)) {
    return tv("aia.sources.refused", { reason: reasonWords(e.code) });
  }
  return errorText(e);
}

/** One file, stored as the client's source the moment it is picked. */
export function SourcePicker({
  clientId,
  label,
  onStored,
}: {
  clientId: string;
  label: string;
  onStored: (source: SourceAdded) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [upload, setUpload] = useState<Upload>({ phase: "idle" });
  const pick = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > FILE_MAX_BYTES) return setUpload({ phase: "failed", message: t("aia.sources.tooLarge") });
    setUpload({ phase: "uploading", name: file.name });
    try {
      const source = await workspace.addSource(clientId, { filename: file.name, data_b64: await fileToBase64(file) });
      setUpload({ phase: "stored", source });
      onStored(source);
    } catch (e) {
      setUpload({ phase: "failed", message: refusal(e) });
    }
  };
  return (
    <div className="flex flex-col gap-1.5">
      <input
        ref={input}
        type="file"
        hidden
        aria-label={label}
        accept={FILE_ACCEPT}
        onChange={(e) => {
          void pick(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button small icon="attach" disabled={upload.phase === "uploading"} onClick={() => input.current?.click()}>
          {label}
        </Button>
        <span className="text-xs text-ink-faint">{t("aia.sources.kinds")}</span>
      </div>
      <p aria-live="polite" className="text-xs">
        {upload.phase === "uploading" ? <span className="text-ink-muted">{tv("aia.sources.uploading", { name: upload.name })}</span> : null}
        {upload.phase === "stored" ? (
          <span className="text-ink-muted">{upload.source.created ? t("aia.sources.stored") : t("aia.sources.storedAgain")}</span>
        ) : null}
      </p>
      {upload.phase === "failed" ? <p role="alert" className="text-xs text-status-fault">{upload.message}</p> : null}
    </div>
  );
}

/** A named file: what it is, what reading produced, what was read, and the original. */
export function SourceCard({
  clientId,
  sourceId,
  compact = false,
  ai,
  mayMark = false,
}: {
  clientId: string;
  sourceId: string;
  compact?: boolean;
  /** Offer AI proposals from the file (lifecycle K2d5), with what the person may do. */
  ai?: AiRights;
  /** PROPOSE_CLIENT_KNOWLEDGE: the person may mark the file "Interní dokument" or unmark it. */
  mayMark?: boolean;
}) {
  const [res, retry] = useResource(() => workspace.source(clientId, sourceId), [clientId, sourceId]);
  const [error, setError] = useState<string | null>(null);
  // The mark as the API last answered it; null until the person changes it here.
  const [mark, setMark] = useState<ClientSource["internal"] | undefined>(undefined);
  if (res.state === "loading") return <p className="text-xs text-ink-muted">{t("aia.loading")}</p>;
  if (res.state === "not-found") return <p className="text-xs text-ink-muted">{t("aia.sources.noFile")}</p>;
  if (res.state === "failed") {
    return (
      <p role="alert" className="text-xs text-status-fault">
        {res.message}{" "}
        <button type="button" className="underline" onClick={retry}>{t("aia.retry")}</button>
      </p>
    );
  }
  const s = res.data;
  const line = readingLine(s);
  const download = () =>
    workspace.sourceOriginal(clientId, s.source_id).then(
      (blob) => saveBlob(blob, s.filename),
      (e: unknown) => setError(errorText(e)),
    );
  const added = s.occurrences[0]?.added_at ?? s.created_at;
  return (
    <div className="flex flex-col gap-2 rounded-sm border border-border bg-surface p-3" data-source={s.source_id}>
      <div className="flex flex-wrap items-start gap-2">
        <span className="min-w-0 flex-1">
          <span className="block break-words text-sm font-medium">{s.filename}</span>
          <span className="text-xs text-ink-faint">
            {sizeWords(s.size_bytes)}
            {added ? ` · ${tv("aia.sources.addedBy", { when: relative(added) ?? "" })}` : null}
          </span>
        </span>
        <Button small variant="quiet" icon="download" onClick={() => void download()}>{t("aia.sources.download")}</Button>
      </div>
      <span><Chip tone={line.tone}>{line.text}</Chip></span>
      <InternalMark
        clientId={clientId}
        sourceId={s.source_id}
        internal={mark === undefined ? (s.internal ?? null) : mark}
        mayMark={mayMark && !compact}
        onMarked={setMark}
      />
      {error ? <p role="alert" className="text-xs text-status-fault">{error}</p> : null}
      {compact ? null : <WhatWasRead source={s} />}
      {!compact && ai && canPropose(s) ? <SourceProposals clientId={clientId} source={s} rights={ai} /> : null}
    </div>
  );
}

/** "Interní dokument": a toggle that says what it does, and who marked the file and when. */
function InternalMark({
  clientId,
  sourceId,
  internal,
  mayMark,
  onMarked,
}: {
  clientId: string;
  sourceId: string;
  internal: ClientSource["internal"] | null;
  mayMark: boolean;
  onMarked: (internal: ClientSource["internal"] | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const marked = !!internal;
  if (!marked && !mayMark) return null;
  const toggle = async () => {
    setBusy(true);
    setFailed(null);
    try {
      const saved = await workspace.markSourceInternal(clientId, sourceId, !marked);
      onMarked(saved.internal ?? null);
    } catch (e) {
      setFailed(tv("aia.sources.internal.failed", { reason: errorText(e) }));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-1 text-xs" data-internal={marked ? "true" : "false"}>
      {mayMark ? (
        <span className="flex flex-wrap items-center gap-2">
          <Button
            small
            variant={marked ? "primary" : "secondary"}
            aria-pressed={marked}
            aria-describedby={`internal-${sourceId}`}
            disabled={busy}
            onClick={() => void toggle()}
          >
            {t("aia.sources.internal.toggle")}
          </Button>
          <span id={`internal-${sourceId}`} className="text-ink-faint">{t("aia.sources.internal.what")}</span>
        </span>
      ) : (
        <span><Tag>{t("aia.sources.internal.toggle")}</Tag></span>
      )}
      {internal ? <MarkedBy internal={internal} /> : null}
      {failed ? <p role="alert" className="text-status-fault">{failed}</p> : null}
    </div>
  );
}

/** Who marked a source and when. Asks who the reader is only where a mark is shown, so a list of
 * unmarked sources sends no identity request per card. */
function MarkedBy({ internal }: { internal: NonNullable<ClientSource["internal"]> }) {
  const [me] = useResource(() => workspace.me(), []);
  const who =
    me.state === "ready" && me.data.user_id === internal.by
      ? t("aia.sources.internal.you")
      : tv("aia.sources.internal.other", { id: internal.by });
  return (
    <span className="text-ink-muted">
      {tv("aia.sources.internal.marked", { when: (internal.at ? relative(internal.at) : null) ?? "", who })}
    </span>
  );
}

function WhatWasRead({ source }: { source: SourceDetail }) {
  const { reading } = source;
  const sheet = reading.dataset?.sheets[0];
  if (sheet) {
    return (
      <details className="text-xs">
        <summary className="cursor-pointer font-medium text-ink-muted">{t("aia.sources.whatWasRead")}</summary>
        <p className="mt-2 text-ink-faint">
          {sheet.name ? `${tv("aia.sources.sheet", { name: sheet.name })} · ` : null}
          {plural(sheet.rows, "řádek", "řádky", "řádků")}
        </p>
        <div className="mt-1 overflow-x-auto">
          <table className="w-full text-left">
            <caption className="sr-only">{t("aia.sources.columns")}</caption>
            <thead className="text-ink-faint">
              <tr>
                <th scope="col" className="py-1 pr-2 font-medium">{t("aia.sources.column.header")}</th>
                <th scope="col" className="py-1 pr-2 font-medium">{t("aia.sources.column.kind")}</th>
                <th scope="col" className="py-1 pr-2 font-medium">{t("aia.sources.column.filled")}</th>
                <th scope="col" className="py-1 font-medium">{t("aia.sources.column.sample")}</th>
              </tr>
            </thead>
            <tbody>
              {sheet.columns.map((c) => (
                <tr key={c.index} className="border-t border-border align-top">
                  <td className="py-1 pr-2">{c.header ?? c.letter}</td>
                  <td className="py-1 pr-2">{t(`aia.sources.columnKinds.${c.kind}`)}</td>
                  <td className="py-1 pr-2 font-mono">{c.filled}</td>
                  <td className="py-1 text-ink-muted">
                    {c.personal ? <em>{t("aia.sources.personal")}</em> : c.sample.join(" · ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    );
  }
  if (!reading.segments.length) return null;
  const shown = reading.segments.slice(0, SHOWN_SEGMENTS);
  return (
    <details className="text-xs">
      <summary className="cursor-pointer font-medium text-ink-muted">{t("aia.sources.whatWasRead")}</summary>
      {reading.segments.length > SHOWN_SEGMENTS ? (
        <p className="mt-2 text-ink-faint">{tv("aia.sources.firstSegments", { n: SHOWN_SEGMENTS, total: reading.segments.length })}</p>
      ) : null}
      <ol className="mt-2 flex flex-col gap-2">
        {shown.map((seg, i) => (
          <li key={i} className="grid gap-0.5">
            <span className="font-mono text-[11px] text-ink-faint">{locatorWords(seg.locator)}</span>
            <span className="line-clamp-4 whitespace-pre-wrap text-ink">{seg.text}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}
