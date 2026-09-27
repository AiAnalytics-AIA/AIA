// One project on the Projects screen: what pmCard1810 shows, drawn with the
// design system. Every text comes from cardText() and the label functions in
// src/unit/projects.ts (parity-tested against the originals); this only lays
// them out and wires the actions.

import { classicHref } from "@/lib/interface-handoff";
import { t, tv } from "@/i18n/t";
import {
  type ProjectRow, ago, cardText, jobBadges, providerLabel, stageLabel, statusLabel, statusTone,
} from "@/unit/projects";
import { Button, Chip, ClassicLink, Tag } from "../ui";

export type CardAction = "pin" | "unpin" | "tags" | "duplicate" | "archive" | "unarchive" | "trash";

export function ProjectCard({ row, now, onAction, onCopyDemo }: {
  row: ProjectRow;
  now: number;
  onAction: (row: ProjectRow, action: CardAction) => void;
  onCopyDemo: (row: ProjectRow) => void;
}) {
  const text = cardText(row);
  const demo = !!row.is_demo;
  const status = row.status || "DRAFT";
  const badges = jobBadges(row);

  return (
    <article
      data-project={row.project_id}
      className={`flex min-w-0 flex-col gap-4 rounded-md border bg-surface-raised p-5 ${row.pinned ? "border-signal-edge" : "border-border"}`}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-faint">{text.kind}</div>
          <h2 className="mt-1 text-base font-semibold leading-6 text-ink">{text.title}</h2>
        </div>
        <Chip tone={statusTone(status)}>{statusLabel(status.toUpperCase())}</Chip>
      </header>

      {row.pinned || row.tags?.length || row.current_stage || (!demo && row.preferred_provider) || badges.length ? (
        <div className="flex flex-wrap gap-1.5">
          {row.pinned ? <Tag icon="pin">{t("projects.pinned")}</Tag> : null}
          {(row.tags ?? []).map((tag) => (
            <Tag key={tag} icon="tag">{tag}</Tag>
          ))}
          {row.current_stage ? <Tag>{stageLabel(row.current_stage)}</Tag> : null}
          {!demo && row.preferred_provider ? <Tag>{providerLabel(row.preferred_provider)}</Tag> : null}
          {badges.map((b) => (
            <Chip key={b.label} tone={b.tone}>{b.label}</Chip>
          ))}
        </div>
      ) : null}

      <div className="flex flex-col gap-1.5 text-sm leading-6">
        <p>
          <span className="font-medium text-ink">{text.questionLabel}:</span>{" "}
          <span className="text-ink-muted">{text.question}</span>
        </p>
        <p>
          <span className="font-medium text-ink">{text.resultLabel}:</span>{" "}
          <span className="text-ink-muted">{text.result}</span>
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-2">
        {[[t("projects.population"), text.population], [t("projects.client"), text.client]].map(([label, value]) => (
          <div key={label} className="min-w-0 rounded-sm border border-border bg-surface-sunken px-3 py-2">
            <dt className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-faint">{label}</dt>
            <dd className="mt-0.5 line-clamp-3 text-sm font-medium text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      {!demo ? (
        <div className="flex flex-col gap-2 border-t border-border pt-3 text-xs">
          <p className="text-ink-muted">
            <span className="font-medium text-ink">{t("projects.safePoint")}:</span> {text.safePoint}
          </p>
          <p className="text-ink-faint">{tv("projects.updatedAgo", { ago: ago(row.modified_at, now), rev: row.revision ?? 0 })}</p>
          <div className="flex items-center gap-2">
            <div className="h-1 flex-1 rounded-sm bg-surface-sunken" aria-hidden="true">
              <div className="h-1 rounded-sm bg-signal" style={{ width: `${text.progress}%` }} />
            </div>
            <span className="tabular-nums text-ink-muted">{tv("projects.progress", { pct: Number(row.progress_pct ?? 0) })}</span>
          </div>
        </div>
      ) : null}

      <footer className="mt-auto flex flex-wrap items-center gap-1.5 border-t border-border pt-3">
        <ClassicLink href={classicHref({ open: row.project_id })} variant="secondary" small>
          {demo ? t("projects.openDemo") : t("projects.open")}
        </ClassicLink>
        {demo ? (
          <Button variant="quiet" small icon="copy" onClick={() => onCopyDemo(row)}>{t("projects.copyDemo")}</Button>
        ) : (
          <>
            <Button variant="quiet" small icon="pin" onClick={() => onAction(row, row.pinned ? "unpin" : "pin")}>
              {row.pinned ? t("projects.unpin") : t("projects.pin")}
            </Button>
            <Button variant="quiet" small icon="tag" onClick={() => onAction(row, "tags")}>{t("projects.tags")}</Button>
            <Button variant="quiet" small icon="copy" onClick={() => onAction(row, "duplicate")}>{t("projects.duplicate")}</Button>
            <Button variant="quiet" small icon="archive" onClick={() => onAction(row, row.archived ? "unarchive" : "archive")}>
              {row.archived ? t("projects.unarchive") : t("projects.archive")}
            </Button>
            {status !== "TRASHED" ? (
              <Button variant="quiet" small icon="trash" onClick={() => onAction(row, "trash")}>{t("projects.toTrash")}</Button>
            ) : null}
          </>
        )}
      </footer>
    </article>
  );
}
