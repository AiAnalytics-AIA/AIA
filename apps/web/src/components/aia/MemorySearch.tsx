"use client";

// Project memory's search (plans/project-memory-reuse.md M1d): one client's past studies,
// matched on what their designs say. The client is always given -- from the route in the
// client workspace, from the person's choice on Projektová paměť -- and never inferred;
// the server searches that client alone. Each hit says what matched and whether it came
// from a design, a working draft (no design yet) or the name. Nothing here writes.

import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type MemoryHit, type StudyKind, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { relative } from "@/lib/format";
import { evidence, ofKind, sendable } from "@/lib/memory";
import { Icon } from "../rehome/icons";
import { Field, Tag, TextInput } from "../rehome/ui";
import { Empty, Loaded } from "./states";
import { useResource } from "./useResource";

const M = "aia.memory";

/** The search box; ``children`` render while nothing is being searched. */
export function MemorySearch({
  clientId,
  kind = null,
  children,
}: {
  clientId: string;
  kind?: StudyKind | null;
  children?: ReactNode;
}) {
  const [typed, setTyped] = useState("");
  const [query, setQuery] = useState<string | null>(null);
  useEffect(() => {
    const id = setTimeout(() => setQuery(sendable(typed)), 300);
    return () => clearTimeout(id);
  }, [typed]);
  return (
    <div className="flex flex-col gap-4">
      <Field label={t(`${M}.search`)} className="max-w-md">
        <TextInput type="search" value={typed} onChange={(e) => setTyped(e.target.value)} />
      </Field>
      {query ? (
        <MemoryHits key={`${clientId}:${query}`} clientId={clientId} query={query} kind={kind} />
      ) : typed.trim() ? (
        <p className="text-sm text-ink-muted">{t(`${M}.typeMore`)}</p>
      ) : (
        children
      )}
    </div>
  );
}

function MemoryHits({ clientId, query, kind }: { clientId: string; query: string; kind: StudyKind | null }) {
  const [res, retry] = useResource(() => workspace.memorySearch(clientId, query), [clientId, query]);
  return (
    <Loaded res={res} retry={retry}>
      {(all) => {
        const hits = ofKind(all, kind);
        if (!hits.length) return <Empty>{t(`${M}.noHits`)}</Empty>;
        return (
          <div>
            <p role="status" className="mb-2 text-xs text-ink-muted">{tv(`${M}.hits`, { n: hits.length })}</p>
            <ul className="flex flex-col divide-y divide-border rounded-md border border-border bg-surface-raised">
              {hits.map((h) => (
                <MemoryHitRow key={h.study_id} clientId={clientId} hit={h} />
              ))}
            </ul>
          </div>
        );
      }}
    </Loaded>
  );
}

function MemoryHitRow({ clientId, hit }: { clientId: string; hit: MemoryHit }) {
  const said = evidence(hit);
  return (
    <li>
      <Link
        href={hit.kind === "RESEARCH" ? appRoutes.memoryStudy(clientId, hit.study_id) : appRoutes.study(clientId, hit.study_id, hit.kind)}
        className="flex flex-col gap-1 px-5 py-3 no-underline hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-focus-ring"
      >
        <span className="flex flex-wrap items-center gap-3">
          <Icon name={hit.kind === "SIMULATION" ? "simulation" : "research"} className="text-ink-faint" />
          <span className="flex-1 font-medium text-ink">{hit.name}</span>
          <Tag>{tv(`${M}.source.${hit.source}`, { revision: hit.design_revision ?? "" })}</Tag>
          <span className="w-28 text-right text-xs text-ink-faint">{relative(hit.modified_at)}</span>
        </span>
        {said.length ? (
          <span className="flex flex-col gap-0.5 pl-8">
            {said.slice(0, 4).map((e, i) => (
              <span key={`${e.field}-${i}`} className="text-xs text-ink-muted">
                <span className="text-ink-faint">{t(`${M}.field.${e.field}`)}:</span> {e.text}
              </span>
            ))}
          </span>
        ) : null}
      </Link>
    </li>
  );
}
