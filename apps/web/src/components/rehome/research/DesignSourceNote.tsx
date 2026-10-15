"use client";

// Where a reused study's design came from (plans/project-memory-reuse.md M3e): on every stage of a
// study whose design was reused from a past study, which study and revision, and the labels the
// source carries -- fictional data, a draft report, never run -- as the server recorded them when
// it was reused. A study that was not reused shows nothing.

import Link from "next/link";
import { useEffect, useState } from "react";

import { t, tv } from "@/i18n/t";
import { type DesignSource, research, workspace } from "@/lib/api";
import { appRoutes } from "@/lib/app-routes";
import { sourceLabelWords } from "@/lib/memory";

const D = "aia.designSource";

const isSource = (v: unknown): v is DesignSource =>
  typeof v === "object" && v !== null && typeof (v as DesignSource).source_study_id === "string" && typeof (v as DesignSource).labels === "object";

export function DesignSourceNote({ clientId, studyId }: { clientId: string; studyId: string }) {
  const [source, setSource] = useState<DesignSource | null>(null);
  const [name, setName] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    research.designSource(studyId).then(
      (s) => {
        if (!live || !isSource(s)) return;
        setSource(s);
        // The source's name, read through its own scope; its id when that fails.
        workspace.study(s.source_study_id).then(
          (w) => live && setName(w.study.name),
          () => {},
        );
      },
      () => {}, // 404: this study's design was not reused.
    );
    return () => {
      live = false;
    };
  }, [studyId]);
  if (!source) return null;
  const words = sourceLabelWords(source.labels);
  return (
    <section role="note" aria-label={t(`${D}.title`)} className="mb-4 rounded-sm border border-status-you-ink/40 bg-status-you-wash p-3 text-sm">
      <p className="font-semibold">{t(`${D}.title`)}</p>
      <p className="mt-1">
        {tv(`${D}.from`, { name: name ?? source.source_study_id, revision: source.source_revision })}{" "}
        <Link href={appRoutes.memoryStudy(clientId, source.source_study_id)} className="font-medium text-signal underline">
          {t(`${D}.open`)}
        </Link>
      </p>
      <p className="mt-1 text-ink-muted">
        {t(`${D}.labels`)}: {words.length ? words.map((w) => t(`${D}.${w}`)).join(" · ") : t(`${D}.none`)}
      </p>
    </section>
  );
}
